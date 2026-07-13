"""Canonical live combat runtime for Smart MUD.

`engine.combat.CombatEngine` remains the canonical single-attack resolver.
This module owns persistent encounters, participants, rounds, target state,
Actor synchronization, runtime legality checks, and player-facing combat flow.
The legacy `rules.combat` module is not imported here and is compatibility-only.
"""
from __future__ import annotations

import json, sqlite3, uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engine.actors import Actor, ActorIdentity, ActorResources, actor_from_runtime_character, default_derived_statistics
from engine.combat import CombatEngine, CombatState
from engine.combat_equipment import CombatContentRegistry
from engine.formulas import FormulaEngine
from engine.character_stats import CharacterAttributeService, CombatStatService
from engine.conditions import condition_label, condition_key, transition_text


def _ensure_column(con: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    cols = {row[1] for row in con.execute(f"PRAGMA table_info({table})")}
    if column not in cols:
        con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

def init_combat_runtime_schema(db_path: str | Path) -> None:
    with sqlite3.connect(db_path) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS combat_encounters(encounter_id TEXT PRIMARY KEY,world_id TEXT,room_id TEXT,status TEXT,started_world_time INTEGER,current_round INTEGER,next_round_world_time INTEGER,created_at TEXT,updated_at TEXT,ended_at TEXT,end_reason TEXT,metadata_json TEXT)""")
        con.execute("""CREATE TABLE IF NOT EXISTS combat_participants(encounter_id TEXT,actor_id TEXT,actor_type TEXT,entity_instance_id TEXT,character_id TEXT,side_id TEXT,current_target_actor_id TEXT,participation_status TEXT,initiative_value INTEGER,joined_round INTEGER,last_action_round INTEGER,next_action_world_time INTEGER,contribution_damage INTEGER DEFAULT 0,contribution_healing INTEGER DEFAULT 0,contribution_support INTEGER DEFAULT 0,fled INTEGER DEFAULT 0,defeated INTEGER DEFAULT 0,metadata_json TEXT,PRIMARY KEY(encounter_id,actor_id))""")
        _ensure_column(con, 'combat_participants', 'lifecycle_id', 'TEXT')
        con.execute("""CREATE TABLE IF NOT EXISTS combat_action_queue(action_id TEXT PRIMARY KEY,encounter_id TEXT,actor_id TEXT,action_type TEXT,ability_id TEXT,target_actor_id TEXT,queued_round INTEGER,execute_world_time INTEGER,status TEXT,source TEXT,metadata_json TEXT,created_at TEXT,resolved_at TEXT)""")
        _ensure_column(con, 'combat_action_queue', 'claim_token', 'TEXT')
        _ensure_column(con, 'combat_action_queue', 'claimed_at', 'TEXT')
        con.execute("""CREATE TABLE IF NOT EXISTS combat_round_history(history_id TEXT PRIMARY KEY,encounter_id TEXT,round_number INTEGER,actor_id TEXT,target_actor_id TEXT,action_type TEXT,ability_id TEXT,outcome TEXT,damage INTEGER,healing INTEGER,result_json TEXT,world_time INTEGER,created_at TEXT)""")
        con.execute("""CREATE TABLE IF NOT EXISTS combat_outbound_messages(message_id INTEGER PRIMARY KEY AUTOINCREMENT,world_id TEXT,room_id TEXT,character_id TEXT,encounter_id TEXT,category TEXT,message TEXT,created_world_time INTEGER,created_at TEXT,delivered INTEGER DEFAULT 0)""")
        _ensure_column(con, 'combat_outbound_messages', 'claim_token', 'TEXT')
        _ensure_column(con, 'combat_outbound_messages', 'claimed_at', 'TEXT')
        con.execute("CREATE INDEX IF NOT EXISTS idx_combat_outbound_character ON combat_outbound_messages(character_id,delivered,message_id)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_combat_encounters_active ON combat_encounters(world_id,room_id,status)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_combat_participants_actor ON combat_participants(actor_id,participation_status)")
        con.execute("""CREATE TABLE IF NOT EXISTS combat_death_transactions(death_id TEXT PRIMARY KEY,encounter_id TEXT,actor_id TEXT,killer_actor_id TEXT,corpse_entity_id TEXT,world_id TEXT,room_id TEXT,created_world_time INTEGER,created_at TEXT,metadata_json TEXT)""")
        _ensure_column(con, 'combat_death_transactions', 'lifecycle_id', 'TEXT')
        con.execute("UPDATE combat_death_transactions SET lifecycle_id=COALESCE(lifecycle_id, json_extract(metadata_json, '$.lifecycle_id'), actor_id || ':legacy') WHERE lifecycle_id IS NULL OR lifecycle_id=''")
        con.execute("DROP INDEX IF EXISTS idx_combat_death_actor_once")
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_combat_death_actor_lifecycle_once ON combat_death_transactions(world_id,actor_id,lifecycle_id)")
        con.commit()

@dataclass
class CombatRuntimeResult:
    ok: bool
    messages: list[str] = field(default_factory=list)
    encounter_id: str = ""

class CombatRuntimeService:
    ROUND_DELAY = 1
    MAX_ACTIONS_PER_PULSE = 8
    def __init__(self, runtime: Any):
        self.runtime = runtime; self.db_path = runtime.state_store.db_path; self.event_bus = runtime.event_bus
        init_combat_runtime_schema(self.db_path)
        
        if not getattr(runtime, 'combat_stat_service', None):
            runtime.attribute_service = CharacterAttributeService(runtime.state_store, getattr(runtime, 'active_world_id', None) or 'shattered_realms', event_bus=self.event_bus)
            runtime.attribute_service.runtime = runtime
            runtime.combat_stat_service = CombatStatService(runtime.attribute_service)
        self.engine = CombatEngine(FormulaEngine(), content=CombatContentRegistry(getattr(runtime, 'active_world', None)), combat_stats=runtime.combat_stat_service, event_bus=self.event_bus)
        self.engine.runtime = runtime
        self.engine.resolution.runtime = runtime
        if not (self.engine.combat_stats is runtime.combat_stat_service and self.engine.resolution.combat_stats is runtime.combat_stat_service and self.engine.resolution.runtime is runtime):
            raise RuntimeError('Combat runtime invariant failed: canonical combat services are not wired to MudRuntime')
        self.cancel_active_encounters_on_restart()

    def refresh_content(self) -> None:
        self.engine.content = CombatContentRegistry(getattr(self.runtime, 'active_world', None))
        if getattr(self.runtime, 'combat_stat_service', None):
            self.engine.combat_stats = self.runtime.combat_stat_service; self.engine.resolution.combat_stats = self.runtime.combat_stat_service; self.engine.runtime = self.runtime; self.engine.resolution.runtime = self.runtime

    def world_time(self) -> int:
        wt = self.runtime.get_world_time(self.runtime.active_world_id or '')
        return int(wt.get('total_minutes') or (int(wt.get('day', 1))*1440 + int(wt.get('hour', 0))*60 + int(wt.get('minute', 0))))

    def _publish(self, name: str, payload: dict[str, Any]) -> None:
        if self.event_bus: self.event_bus.publish(name, payload, source_system='combat_runtime', world_id=payload.get('world_id') or self.runtime.active_world_id or '')

    def actor_id_for_entity(self, ent: dict[str, Any]) -> str: return 'entity:' + str(ent.get('instance_id') or ent.get('entity_id'))
    def actor_id_for_character(self, ch: Any) -> str: return 'character:' + str(getattr(ch, 'id', ''))

    def actor_from_entity(self, ent: dict[str, Any]) -> Actor:
        tmpl = dict(self.runtime.entity_templates.get(str(ent.get('template_id') or ''), {}))
        st = ent.get('state') or {}; stats = tmpl.get('stats') or {}
        maxhp = int(st.get('maximum_health') or st.get('max_health') or stats.get('max_health') or stats.get('maximum_health') or 100)
        hp = int(st.get('current_health') or st.get('health') or maxhp)
        a = Actor.create(self.actor_id_for_entity(ent), ent.get('name') or tmpl.get('name','Entity'), 'npc' if ent.get('entity_type')=='npc' else 'mob')
        a.identity = ActorIdentity(name=a.identity.name, current_location=ent.get('room_id',''), current_world=self.runtime.active_world_id or '')
        a.resources = ActorResources(health=hp, maximum_health=maxhp, mana=int(st.get('current_mana') or 0), maximum_mana=int(st.get('maximum_mana') or 0), stamina=int(st.get('current_stamina') or 0), maximum_stamina=int(st.get('maximum_stamina') or 0))
        a.attributes.update({k:int(v) for k,v in (stats.get('attributes') or {}).items() if isinstance(v,(int,float,str)) and str(v).isdigit()})
        a.combat_profile.update(tmpl.get('combat_profile') or {})
        for k in ('combat_behavior_profile_id','behavior_profile_id','ability_loadout_id','natural_weapon_profile_id'):
            if tmpl.get(k): a.combat_profile[k]=tmpl.get(k)
        if tmpl.get('natural_weapon_profile_id'): a.combat_profile['natural_weapon_profile_ids']=[tmpl.get('natural_weapon_profile_id')]
        if stats.get('attack_power'): a.combat_profile['attack_power']=stats.get('attack_power')
        a.body_profile_id = str(tmpl.get('body_profile_id') or tmpl.get('body_profile') or 'humanoid')
        a.lifecycle_state = 'dead' if not ent.get('is_alive', True) or hp <= 0 else 'alive'
        a.lifecycle_profile['lifecycle_id'] = str(st.get('lifecycle_id') or ent.get('entity_id') or a.actor_id)
        a.derived_statistics_cache = default_derived_statistics(); return a

    def persist_actor(self, actor: Actor) -> None:
        if actor.actor_id.startswith('character:'):
            cid=actor.actor_id.split(':',1)[1]; ch=self.runtime.state_store.load_character(cid)
            if ch:
                ch.hp=actor.resources.health; ch.max_hp=actor.resources.maximum_health; ch.mana=actor.resources.mana; ch.max_mana=actor.resources.maximum_mana; ch.stamina=actor.resources.stamina; ch.max_stamina=actor.resources.maximum_stamina; ch.actor_data=actor.to_dict(); self.runtime.state_store.save_character(ch,self.runtime.active_world_id or '')
        elif actor.actor_id.startswith('entity:'):
            eid=actor.actor_id.split(':',1)[1]; ent=self.runtime.find_entity(eid)
            if ent:
                st=ent.get('state') or {}; st.update({'current_health':actor.resources.health,'maximum_health':actor.resources.maximum_health,'combat_state':actor.combat_profile.get('combat_state','idle'),'is_alive': actor.resources.health>0 and actor.lifecycle_state!='dead','current_state':'dead' if actor.resources.health<=0 else st.get('current_state','idle')})
                self.runtime.update_entity_state(eid, st, source_system='combat_runtime')

    def resolve_target(self, character: Any, query: str) -> dict[str, Any] | None:
        visible = self.runtime.find_visible_entities(character.room_id, character); cands = [e for e in visible.get('npcs',[])+visible.get('mobs',[]) if e.get('is_alive') and e.get('current_state') not in {'dead','corpse','despawned'}]
        return self.runtime.resolve_entity_keywords(query, cands).get('entity')

    def validate_attack(self, attacker: Actor, defender: Actor, ent: dict[str,Any]|None=None) -> str:
        if attacker.actor_id == defender.actor_id: return 'You cannot attack yourself.'
        if attacker.resources.health <= 0 or attacker.combat_profile.get('combat_state') in {'dead','sleeping','unconscious','incapacitated'}: return 'You cannot attack right now.'
        if defender.resources.health <= 0 or defender.lifecycle_state == 'dead': return f'There is no living {defender.identity.name.lower()} here.'
        if attacker.identity.current_location != defender.identity.current_location: return 'They are not here.'
        if ent:
            tmpl = dict(self.runtime.entity_templates.get(str(ent.get('template_id') or ''), {})); flags=set(tmpl.get('flags') or [])|set(ent.get('flags') or [])|set(tmpl.get('tags') or [])
            policy = tmpl.get('combat_policy') or {}
            if policy.get('protected') or policy.get('no_kill') or 'protected' in flags or 'trainer_protected' in flags or tmpl.get('kind') == 'trainer': return f"{defender.identity.name} is protected and cannot be attacked."
            if policy.get('attackable') is False or ('hostile' not in flags and 'attackable' not in flags and not policy.get('attackable')): return f"{defender.identity.name} is not a valid combat target."
        return ''

    def actor_display_name(self, actor_id: str) -> str:
        a = self._load_actor(actor_id)
        return a.identity.name if a else "Someone"

    def active_character_ids_in_room(self, room_id: str) -> list[str]:
        ids=[]
        for session in getattr(self.runtime, "sessions", {}).values():
            if getattr(session, "state", "playing") == "disconnected":
                continue
            cid=getattr(session, "character_id", "")
            ch=self.runtime.state_store.load_character(cid) if cid else None
            if ch and ch.room_id == room_id and cid not in ids:
                ids.append(cid)
        return ids

    def enqueue_output(self, character_id: str, message: str, *, encounter_id: str = "", room_id: str = "", category: str = "combat") -> None:
        if not character_id or not str(message or "").strip():
            return
        with sqlite3.connect(self.db_path) as con:
            con.execute("INSERT INTO combat_outbound_messages(world_id,room_id,character_id,encounter_id,category,message,created_world_time,created_at,delivered) VALUES(?,?,?,?,?,?,?,?,0)", (self.runtime.active_world_id or "", room_id, character_id, encounter_id, category, str(message).strip(), self.world_time(), datetime.now(timezone.utc).isoformat()))

    def drain_output(self, character_id: str, limit: int = 50) -> list[str]:
        token='claim_'+uuid.uuid4().hex; now=datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path, timeout=30) as con:
            con.execute('BEGIN IMMEDIATE')
            ids=[r[0] for r in con.execute("SELECT message_id FROM combat_outbound_messages WHERE character_id=? AND delivered=0 AND (claim_token IS NULL OR claim_token='') ORDER BY message_id LIMIT ?", (character_id, int(limit))).fetchall()]
            if ids:
                con.executemany("UPDATE combat_outbound_messages SET claim_token=?,claimed_at=?,delivered=1 WHERE message_id=? AND character_id=? AND delivered=0", [(token,now,i,character_id) for i in ids])
            rows=con.execute("SELECT message FROM combat_outbound_messages WHERE character_id=? AND claim_token=? ORDER BY message_id", (character_id, token)).fetchall()
            con.commit()
        return [r[0] for r in rows]

    def _deliver_combat_messages(self, eid: str, attacker: Actor, defender: Actor, result: Any, category: str = "attack_hit", skip_attacker: bool = False) -> None:
        room_id = attacker.identity.current_location
        messages = result.messages if hasattr(result, "messages") else {}
        attacker_cid = attacker.actor_id.split(':',1)[1] if attacker.actor_id.startswith('character:') else ''
        defender_cid = defender.actor_id.split(':',1)[1] if defender.actor_id.startswith('character:') else ''
        for cid in self.active_character_ids_in_room(room_id):
            if cid == attacker_cid:
                if skip_attacker:
                    continue
                msg = messages.get('attacker') or ''
            elif cid == defender_cid:
                msg = messages.get('victim') or ''
            else:
                msg = messages.get('observers') or ''
            self.enqueue_output(cid, msg, encounter_id=eid, room_id=room_id, category=category)

    def queue_action(self, eid: str, actor_id: str, action_type: str, target_actor_id: str = "", ability_id: str = "", source: str = "player", metadata: dict[str, Any] | None = None) -> None:
        wt=self.world_time(); aid='act_'+uuid.uuid4().hex
        with sqlite3.connect(self.db_path, timeout=30) as con:
            con.execute("BEGIN IMMEDIATE")
            old=con.execute("SELECT action_id FROM combat_action_queue WHERE encounter_id=? AND actor_id=? AND status='queued'", (eid,actor_id)).fetchone()
            if old:
                con.execute("UPDATE combat_action_queue SET status='replaced',resolved_at=? WHERE action_id=?", (datetime.now(timezone.utc).isoformat(), old[0]))
                self._publish('combat_action_replaced', {'encounter_id':eid,'actor_id':actor_id,'old_action_id':old[0],'world_time':wt})
            con.execute("INSERT INTO combat_action_queue(action_id,encounter_id,actor_id,action_type,ability_id,target_actor_id,queued_round,execute_world_time,status,source,metadata_json,created_at,resolved_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (aid,eid,actor_id,action_type,ability_id,target_actor_id,self._round(eid),wt,'queued',source,json.dumps(metadata or {}),datetime.now(timezone.utc).isoformat(),None))
        self._publish('combat_action_queued', {'encounter_id':eid,'actor_id':actor_id,'action_type':action_type,'ability_id':ability_id,'target_actor_id':target_actor_id,'world_time':wt})

    def _consume_action(self, eid: str, actor_id: str) -> dict[str, Any] | None:
        token='actclaim_'+uuid.uuid4().hex; now=datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path, timeout=30) as con:
            con.row_factory=sqlite3.Row; con.execute('BEGIN IMMEDIATE')
            row=con.execute("SELECT * FROM combat_action_queue WHERE encounter_id=? AND actor_id=? AND status='queued' ORDER BY created_at LIMIT 1", (eid,actor_id)).fetchone()
            if not row: con.commit(); return None
            changed=con.execute("UPDATE combat_action_queue SET status='consumed',claim_token=?,claimed_at=?,resolved_at=? WHERE action_id=? AND status='queued'", (token,now,now,row['action_id'])).rowcount
            con.commit()
            return dict(row) if changed == 1 else None

    def is_actor_in_active_combat(self, actor_id: str) -> bool:
        return bool(self.find_actor_encounter(actor_id))

    def start_player_attack(self, character: Any, query: str) -> CombatRuntimeResult:
        if not query.strip():
            eid=self.find_actor_encounter(self.actor_id_for_character(character))
            if eid:
                with sqlite3.connect(self.db_path) as con: row=con.execute("SELECT current_target_actor_id FROM combat_participants WHERE encounter_id=? AND actor_id=?",(eid,self.actor_id_for_character(character))).fetchone()
                self.queue_action(eid, self.actor_id_for_character(character), 'basic_attack', row[0] if row else '', source='player')
                return CombatRuntimeResult(True, ['You focus on your current opponent.'], eid)
            return CombatRuntimeResult(False, ['Attack whom?'])
        ent=self.resolve_target(character, query)
        if not ent: return CombatRuntimeResult(False, ["You don't see that target here."])
        self.refresh_content(); attacker=actor_from_runtime_character(character,self.runtime.active_world_id or ''); attacker.actor_id=self.actor_id_for_character(character); defender=self.actor_from_entity(ent)
        err=self.validate_attack(attacker,defender,ent)
        if err: return CombatRuntimeResult(False,[err])
        enc=self.find_actor_encounter(attacker.actor_id) or self.start_encounter(character.room_id)
        already=bool(self.find_actor_encounter(attacker.actor_id))
        self.join_encounter(enc, attacker, 'side_1'); self.join_encounter(enc, defender, 'side_2'); self.set_target(enc, attacker.actor_id, defender.actor_id); self.set_target(enc, defender.actor_id, attacker.actor_id)
        self.queue_action(enc, attacker.actor_id, 'basic_attack', defender.actor_id, source='default')
        if already:
            return CombatRuntimeResult(True, [f'You keep fighting {defender.identity.name}.'], enc)
        rr=self._execute_attack(enc, attacker, defender, opening=True)
        for cid in self.active_character_ids_in_room(character.room_id):
            if cid != character.id: self.enqueue_output(cid, f'{character.name} attacks {defender.identity.name}.', encounter_id=enc, room_id=character.room_id, category='combat_start')
        return rr

    def start_actor_attack(self, attacker_source: Any, target_ent: dict[str, Any]) -> CombatRuntimeResult:
        if hasattr(attacker_source, "id"):
            return self.start_player_attack(attacker_source, target_ent.get("name") or "")
        self.refresh_content()
        attacker = self.actor_from_entity(attacker_source); defender = self._actor_from_source(target_ent)
        err = ""
        if defender.actor_id.startswith("entity:"):
            err = self.validate_attack(attacker, defender, target_ent)
        elif attacker.actor_id == defender.actor_id or attacker.identity.current_location != defender.identity.current_location or defender.resources.health <= 0:
            err = "That is not a valid combat target."
        if err: return CombatRuntimeResult(False, [err])
        enc = self.find_actor_encounter(attacker.actor_id) or self.start_encounter(attacker.identity.current_location)
        already = bool(self.find_actor_encounter(attacker.actor_id))
        self.join_encounter(enc, attacker, "side_1"); self.join_encounter(enc, defender, "side_2")
        self.set_target(enc, attacker.actor_id, defender.actor_id); self.set_target(enc, defender.actor_id, attacker.actor_id)
        self.queue_action(enc, attacker.actor_id, "basic_attack", defender.actor_id, source="agent")
        if already:
            return CombatRuntimeResult(True, [f"{attacker.identity.name} keeps fighting {defender.identity.name}."], enc)
        rr = self._execute_attack(enc, attacker, defender, opening=True)
        for cid in self.active_character_ids_in_room(attacker.identity.current_location):
            self.enqueue_output(cid, f"{attacker.identity.name} attacks {defender.identity.name}.", encounter_id=enc, room_id=attacker.identity.current_location, category="combat_start")
        return rr

    def _actor_from_source(self, source: Any) -> Actor:
        if hasattr(source, "id"):
            a = actor_from_runtime_character(source, self.runtime.active_world_id or ""); a.actor_id = self.actor_id_for_character(source); return a
        return self.actor_from_entity(source)

    def _actor_id_from_source(self, source: Any) -> str:
        return self.actor_id_for_character(source) if hasattr(source, "id") else self.actor_id_for_entity(source)

    def actor_target(self, actor_source: Any, target_source: Any) -> CombatRuntimeResult:
        aid = self._actor_id_from_source(actor_source); eid = self.find_actor_encounter(aid)
        if not eid: return CombatRuntimeResult(False, ["You are not currently fighting anyone."])
        target = self._actor_from_source(target_source)
        target_eid = self.find_actor_encounter(target.actor_id)
        if target_eid != eid: return CombatRuntimeResult(False, ["That target is not in this fight."])
        actor = self._actor_from_source(actor_source)
        if actor.identity.current_location != target.identity.current_location: return CombatRuntimeResult(False, ["They are not here."])
        if target.resources.health <= 0 or target.lifecycle_state == "dead": return CombatRuntimeResult(False, [f"There is no living {target.identity.name.lower()} here."])
        self.set_target(eid, aid, target.actor_id)
        self.queue_action(eid, aid, "basic_attack", target.actor_id, source="agent" if not hasattr(actor_source, "id") else "player_target")
        return CombatRuntimeResult(True, [f"{actor.identity.name} turns attention to {target.identity.name}."], eid)

    def actor_defend(self, actor_source: Any) -> CombatRuntimeResult:
        aid = self._actor_id_from_source(actor_source); eid = self.find_actor_encounter(aid)
        if not eid: return CombatRuntimeResult(False, ["You are not currently fighting anyone."])
        self.queue_action(eid, aid, "defend", source="agent" if not hasattr(actor_source, "id") else "player")
        return CombatRuntimeResult(True, ["You prepare to defend yourself." if hasattr(actor_source, "id") else f"{self._actor_from_source(actor_source).identity.name} prepares to defend."], eid)

    def actor_flee(self, actor_source: Any, direction: str = "") -> CombatRuntimeResult:
        aid = self._actor_id_from_source(actor_source); eid = self.find_actor_encounter(aid)
        if not eid: return CombatRuntimeResult(False, ["You are not currently fighting anyone."])
        actor = self._actor_from_source(actor_source)
        if not direction:
            exits = self.runtime.canonical_exits(actor_source, actor.identity.current_location) if hasattr(self.runtime, "canonical_exits") else {}
            direction = next((d for d, e in exits.items() if not e.get("hidden") and not e.get("closed") and not e.get("locked")), "")
        if not direction: return CombatRuntimeResult(False, ["There is nowhere to flee."])
        self._publish("combat_flee_attempted", {"encounter_id": eid, "actor_id": aid, "direction": direction, "world_time": self.world_time()})
        move = self.runtime._move_character(actor_source, direction, bypass_combat=True) if hasattr(actor_source, "id") else self.runtime.move_entity_actor(actor_source, direction, bypass_combat=True)
        if not move.ok:
            self._publish("combat_flee_failed", {"encounter_id": eid, "actor_id": aid, "direction": direction, "world_time": self.world_time()})
            return CombatRuntimeResult(False, [f"You try to flee {direction}, but cannot escape that way."])
        with sqlite3.connect(self.db_path) as con:
            con.execute("UPDATE combat_participants SET participation_status='fled',fled=1 WHERE encounter_id=? AND actor_id=?", (eid, aid))
            con.execute("UPDATE combat_action_queue SET status='cancelled',resolved_at=? WHERE encounter_id=? AND actor_id=? AND status='queued'", (datetime.now(timezone.utc).isoformat(), eid, aid))
        self._publish("combat_participant_fled", {"encounter_id": eid, "actor_id": aid, "direction": direction, "world_time": self.world_time()}); self.end_if_finished(eid)
        return CombatRuntimeResult(True, [f"You break away and flee {direction}!" if hasattr(actor_source, "id") else f"{actor.identity.name} flees {direction}."], eid)

    def actor_assist(self, actor_source: Any, ally_source: Any | None = None) -> CombatRuntimeResult:
        actor = self._actor_from_source(actor_source); room_id = actor.identity.current_location
        visible = self.runtime.find_visible_entities(room_id, actor_source)
        candidates = ["entity:" + str(e.get("instance_id") or e.get("entity_id")) for e in visible.get("npcs", []) + visible.get("mobs", [])]
        candidates += ["character:" + c.get("character_id", "") for c in self.runtime.list_characters(self.runtime.active_world_id or "") if c.get("room_id") == room_id]
        for ally_id in sorted(set(candidates)):
            if ally_id == actor.actor_id: continue
            aeid = self.find_actor_encounter(ally_id)
            if not aeid: continue
            with sqlite3.connect(self.db_path) as con:
                row = con.execute("SELECT current_target_actor_id FROM combat_participants WHERE encounter_id=? AND actor_id=?", (aeid, ally_id)).fetchone()
            target_id = row[0] if row else ""
            target = self._load_actor(target_id)
            if target and target.actor_id != actor.actor_id and target.identity.current_location == room_id:
                self.join_encounter(aeid, actor, "side_1")
                self.set_target(aeid, actor.actor_id, target.actor_id)
                self.queue_action(aeid, actor.actor_id, "basic_attack", target.actor_id, source="agent")
                self._broadcast_room(aeid, room_id, f"{actor.identity.name} joins the fight.", category="combat_assist")
                return CombatRuntimeResult(True, [f"{actor.identity.name} assists in combat."], aeid)
        return CombatRuntimeResult(False, ["You do not see an ally here who needs assistance."])

    def start_encounter(self, room_id: str) -> str:
        eid='enc_'+uuid.uuid4().hex; now=datetime.now(timezone.utc).isoformat(); wt=self.world_time()
        with sqlite3.connect(self.db_path) as con: con.execute("INSERT INTO combat_encounters VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(eid,self.runtime.active_world_id or '',room_id,'active',wt,0,wt+self.ROUND_DELAY,now,now,None,None,'{}'))
        self._publish('combat_encounter_started', {'encounter_id':eid,'world_id':self.runtime.active_world_id or '', 'room_id':room_id,'round':0,'world_time':wt}); return eid

    def join_encounter(self,eid:str,actor:Actor,side:str)->None:
        kind, raw = actor.actor_id.split(':',1); wt=self.world_time(); init=int(actor.attributes.get('dexterity') or 10)
        with sqlite3.connect(self.db_path) as con: con.execute("INSERT OR IGNORE INTO combat_participants(encounter_id,actor_id,actor_type,entity_instance_id,character_id,side_id,current_target_actor_id,participation_status,initiative_value,joined_round,last_action_round,next_action_world_time,metadata_json,lifecycle_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(eid,actor.actor_id,actor.actor_type,raw if kind=='entity' else '',raw if kind=='character' else '',side,'','active',init,0,-1,wt,'{}',str(actor.lifecycle_profile.get('lifecycle_id') or raw or actor.actor_id)))
        actor.combat_profile['combat_state']='in_combat'; self.persist_actor(actor); self._publish('combat_participant_joined',{'encounter_id':eid,'actor_id':actor.actor_id,'world_id':self.runtime.active_world_id or '', 'side_id':side,'world_time':wt})

    def set_target(self,eid:str,actor_id:str,target_id:str)->None:
        with sqlite3.connect(self.db_path) as con: con.execute("UPDATE combat_participants SET current_target_actor_id=? WHERE encounter_id=? AND actor_id=?",(target_id,eid,actor_id))
        self._publish('combat_target_set',{'encounter_id':eid,'actor_id':actor_id,'target_actor_id':target_id,'world_time':self.world_time()})

    def find_actor_encounter(self, actor_id: str) -> str:
        with sqlite3.connect(self.db_path) as con:
            r=con.execute("SELECT p.encounter_id FROM combat_participants p JOIN combat_encounters e ON e.encounter_id=p.encounter_id WHERE p.actor_id=? AND e.status='active' AND p.participation_status='active'",(actor_id,)).fetchone()
        return r[0] if r else ''
    def find_room_encounters(self, room_id: str) -> list[str]:
        with sqlite3.connect(self.db_path) as con: return [r[0] for r in con.execute("SELECT encounter_id FROM combat_encounters WHERE room_id=? AND status='active'",(room_id,))]

    def _load_actor(self, actor_id:str)->Actor|None:
        if actor_id.startswith('character:'):
            ch=self.runtime.state_store.load_character(actor_id.split(':',1)[1]);
            if not ch: return None
            a=actor_from_runtime_character(ch,self.runtime.active_world_id or ''); a.actor_id=actor_id; return a
        ent=self.runtime.find_entity(actor_id.split(':',1)[1]) if actor_id.startswith('entity:') else None
        return self.actor_from_entity(ent) if ent else None

    def _execute_attack(self,eid:str,attacker:Actor,defender:Actor,opening:bool=False)->CombatRuntimeResult:
        wt=self.world_time(); self._publish('combat_action_started',{'encounter_id':eid,'actor_id':attacker.actor_id,'target_actor_id':defender.actor_id,'action_type':'basic_attack','world_time':wt})
        res=self.engine.resolve_attack(attacker,defender,room_id=attacker.identity.current_location,world_time=wt); self.last_resolution={'attacker_id':attacker.actor_id,'defender_id':defender.actor_id,'hit':res.hit,'damage':res.damage_event.final_damage if res.damage_event else 0,'trace':res.trace,'messages':res.messages}; self.persist_actor(attacker); self.persist_actor(defender)
        dmg=res.damage_event.final_damage if res.damage_event else 0; outcome='hit' if res.hit else 'miss'
        with sqlite3.connect(self.db_path) as con:
            con.execute("INSERT INTO combat_round_history VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",('hist_'+uuid.uuid4().hex,eid,self._round(eid),attacker.actor_id,defender.actor_id,'basic_attack','',outcome,dmg,0,json.dumps({'hit':res.hit,'damage':dmg,'trace':res.trace,'messages':res.messages}),wt,datetime.now(timezone.utc).isoformat()))
            con.execute("UPDATE combat_participants SET last_action_round=?,next_action_world_time=?,contribution_damage=contribution_damage+? WHERE encounter_id=? AND actor_id=?",(self._round(eid),wt+max(1,self.engine.attack_profile(attacker).speed),dmg,eid,attacker.actor_id))
            con.execute("UPDATE combat_encounters SET next_round_world_time=?,updated_at=? WHERE encounter_id=?",(wt+self.ROUND_DELAY,datetime.now(timezone.utc).isoformat(),eid))
        self._publish('combat_attack_resolved',{'encounter_id':eid,'actor_id':attacker.actor_id,'target_actor_id':defender.actor_id,'result':outcome,'damage':dmg,'round':self._round(eid),'world_time':wt})
        if dmg: self._publish('combat_damage_applied',{'encounter_id':eid,'actor_id':attacker.actor_id,'target_actor_id':defender.actor_id,'damage':dmg,'round':self._round(eid),'world_time':wt})
        self._publish('combat_action_completed',{'encounter_id':eid,'actor_id':attacker.actor_id,'target_actor_id':defender.actor_id,'result':outcome,'world_time':wt})
        self._deliver_combat_messages(eid, attacker, defender, res, 'critical_hit' if (res.damage_event and res.damage_event.critical) else ('attack_hit' if res.hit else 'attack_miss'), skip_attacker=opening)
        msgs=[res.messages.get('attacker','')]
        prev_key = condition_key({"current_health": max(0, defender.resources.health + dmg), "maximum_health": defender.resources.maximum_health})
        now_key = condition_key(defender)
        if dmg and defender.resources.health > 0 and prev_key != now_key:
            msg = transition_text(defender.identity.name, defender)
            msgs.append(msg)
            self._broadcast_room(eid, attacker.identity.current_location, msg, category='condition_changed')
        if defender.resources.health<=0:
            death = self._handle_lethal_damage(eid, attacker, defender)
            msgs.extend(death.get('messages', []))
        return CombatRuntimeResult(True,msgs,eid)

    def _round(self,eid):
        with sqlite3.connect(self.db_path) as con: r=con.execute('SELECT current_round FROM combat_encounters WHERE encounter_id=?',(eid,)).fetchone(); return int(r[0] if r else 0)

    def process_due_rounds(self, world_time:int|None=None)->list[str]:
        wt=self.world_time() if world_time is None else int(world_time); out=[]
        with sqlite3.connect(self.db_path) as con: eids=[r[0] for r in con.execute("SELECT encounter_id FROM combat_encounters WHERE status='active' AND next_round_world_time<=?",(wt,))]
        processed=0
        for eid in eids:
            if processed >= self.MAX_ACTIONS_PER_PULSE:
                self._publish('combat_pulse_backlog', {'world_id':self.runtime.active_world_id or '', 'remaining':len(eids)-processed, 'world_time':wt})
                break
            out += self.process_encounter_round(eid, wt); processed += 1
        self._publish('combat_pulse_processed', {'world_id':self.runtime.active_world_id or '', 'encounters':processed, 'world_time':wt})
        return out

    def process_encounter_round(self,eid:str,wt:int|None=None)->list[str]:
        wt=self.world_time() if wt is None else wt; rnd=self._round(eid)+1
        with sqlite3.connect(self.db_path) as con:
            con.execute('UPDATE combat_encounters SET current_round=?,next_round_world_time=?,updated_at=? WHERE encounter_id=?',(rnd,wt+self.ROUND_DELAY,datetime.now(timezone.utc).isoformat(),eid))
            rows=con.execute("SELECT actor_id,current_target_actor_id,initiative_value,next_action_world_time FROM combat_participants WHERE encounter_id=? AND participation_status='active' AND defeated=0 AND fled=0 ORDER BY initiative_value DESC, actor_id",(eid,)).fetchall()
        self._publish('combat_round_started',{'encounter_id':eid,'round':rnd,'world_time':wt,'world_id':self.runtime.active_world_id or ''})
        msgs=[]
        for aid,tid,init,nextt in rows:
            if int(nextt or 0)>wt: continue
            a=self._load_actor(aid); d=self._load_actor(tid)
            if not a or not d or a.resources.health<=0 or d.resources.health<=0 or a.identity.current_location!=d.identity.current_location: continue
            act=self._consume_action(eid, aid)
            atype=(act or {}).get('action_type') or 'basic_attack'
            if atype == 'defend':
                self._start_defense(eid, a); msgs.append('You raise your guard and prepare for the next attack.' if aid.startswith('character:') else f'{a.identity.name} raises a guard.')
                with sqlite3.connect(self.db_path) as con: con.execute("UPDATE combat_participants SET last_action_round=?,next_action_world_time=? WHERE encounter_id=? AND actor_id=?",(rnd,wt+1,eid,aid))
            elif atype == 'flee':
                pass
            elif atype == 'ability' and (act or {}).get('ability_id'):
                rr=self._execute_ability(eid,a,d,act); msgs += rr.messages
            else:
                rr=self._execute_attack(eid,a,d); msgs += rr.messages
        self.end_if_finished(eid); return msgs

    def _broadcast_room(self, eid: str, room_id: str, message: str, *, category: str = 'combat') -> None:
        for cid in self.active_character_ids_in_room(room_id):
            self.enqueue_output(cid, message, encounter_id=eid, room_id=room_id, category=category)

    def _defeat(self,eid,actor_id):
        with sqlite3.connect(self.db_path) as con:
            con.execute("UPDATE combat_participants SET participation_status='defeated',defeated=1,current_target_actor_id='' WHERE encounter_id=? AND actor_id=?",(eid,actor_id))
            con.execute("UPDATE combat_action_queue SET status='cancelled',resolved_at=? WHERE encounter_id=? AND actor_id=? AND status='queued'", (datetime.now(timezone.utc).isoformat(), eid, actor_id))
            con.execute("UPDATE combat_participants SET current_target_actor_id='' WHERE encounter_id=? AND current_target_actor_id=?", (eid, actor_id))
        self._publish('combat_participant_defeated',{'encounter_id':eid,'actor_id':actor_id,'world_time':self.world_time()})

    def _handle_lethal_damage(self, eid: str, attacker: Actor, defender: Actor) -> dict[str, Any]:
        self._publish('combat_lethal_damage_detected', {'encounter_id':eid,'actor_id':attacker.actor_id,'target_actor_id':defender.actor_id,'world_time':self.world_time()})
        if not defender.actor_id.startswith('entity:'):
            self._defeat(eid, defender.actor_id); self.end_if_finished(eid); return {'messages':['You collapse and die.']}
        entity_id = defender.actor_id.split(':',1)[1]; ent = self.runtime.find_entity(entity_id) or {}; room_id = defender.identity.current_location
        lifecycle_id = str((ent.get('state') or {}).get('lifecycle_id') or entity_id)
        death_id = 'death_' + uuid.uuid5(uuid.NAMESPACE_URL, f"{self.runtime.active_world_id}:{defender.actor_id}:{lifecycle_id}").hex
        with sqlite3.connect(self.db_path) as con:
            inserted = con.execute("INSERT OR IGNORE INTO combat_death_transactions(death_id,encounter_id,actor_id,killer_actor_id,world_id,room_id,created_world_time,created_at,metadata_json,lifecycle_id) VALUES(?,?,?,?,?,?,?,?,?,?)", (death_id,eid,defender.actor_id,attacker.actor_id,self.runtime.active_world_id or '',room_id,self.world_time(),datetime.now(timezone.utc).isoformat(),json.dumps({'source_entity_id':entity_id,'lifecycle_id':lifecycle_id}),lifecycle_id)).rowcount
        if not inserted:
            self._defeat(eid, defender.actor_id); self.end_if_finished(eid); return {'messages': []}
        self._publish('actor_death_started', {'death_id':death_id,'actor_id':defender.actor_id,'killer_actor_id':attacker.actor_id,'world_id':self.runtime.active_world_id or '', 'room_id':room_id,'world_time':self.world_time(),'lifecycle_id':lifecycle_id})
        defender.lifecycle_state='dead'; defender.resources.health=0; self.persist_actor(defender)
        self._defeat(eid, defender.actor_id)
        corpse = self.runtime.create_corpse(entity_id, source_system='combat_runtime', death_id=death_id, killer_actor_id=attacker.actor_id)
        with sqlite3.connect(self.db_path) as con:
            con.execute("UPDATE combat_death_transactions SET corpse_entity_id=? WHERE death_id=?", (corpse.get('entity_id',''), death_id))
        self._publish('actor_died', {'death_id':death_id,'actor_id':defender.actor_id,'killer_actor_id':attacker.actor_id,'world_id':self.runtime.active_world_id or '', 'room_id':room_id,'world_time':self.world_time(),'lifecycle_id':lifecycle_id})
        self._publish('living_entity_retired', {'death_id':death_id,'entity_id':entity_id,'room_id':room_id,'world_time':self.world_time(),'lifecycle_id':lifecycle_id})
        self.end_if_finished(eid)
        msg = f"{defender.identity.name} collapses and dies."
        self._broadcast_room(eid, room_id, msg, category='actor_died')
        attacker_msg = f"You strike {defender.identity.name} with a killing blow!"
        if attacker.actor_id.startswith('character:'):
            self.enqueue_output(attacker.actor_id.split(':',1)[1], "Your opponent is dead. Combat ends.", encounter_id=eid, room_id=room_id, category='combat_end')
        room_text = self.runtime._room_text(self.runtime._current_room(self.runtime.state_store.load_character(attacker.actor_id.split(':',1)[1]))) if attacker.actor_id.startswith('character:') else ''
        if room_text and attacker.actor_id.startswith('character:'):
            self.enqueue_output(attacker.actor_id.split(':',1)[1], room_text, encounter_id=eid, room_id=room_id, category='room_refresh')
        self._publish('room_refresh_requested', {'room_id':room_id,'world_id':self.runtime.active_world_id or '', 'reason':'actor_died','corpse_entity_id':corpse.get('entity_id','')})
        return {'death_id': death_id, 'corpse': corpse, 'messages': [attacker_msg, msg]}

    def end_if_finished(self,eid):
        with sqlite3.connect(self.db_path) as con: rows=con.execute("SELECT side_id FROM combat_participants WHERE encounter_id=? AND participation_status='active' AND defeated=0 AND fled=0",(eid,)).fetchall()
        if len(set(r[0] for r in rows)) < 2: self.end_encounter(eid,'victory')

    def end_encounter(self,eid,reason):
        now=datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as con: con.execute("UPDATE combat_encounters SET status='ended',ended_at=?,updated_at=?,end_reason=? WHERE encounter_id=? AND status='active'",(now,now,reason,eid))
        self._publish('combat_encounter_ended',{'encounter_id':eid,'end_reason':reason,'world_time':self.world_time()})

    def _start_defense(self, eid: str, actor: Actor) -> None:
        meta={'defending': True, 'defense_bonus': 5, 'started_world_time': self.world_time(), 'expires_world_time': self.world_time()+1}
        with sqlite3.connect(self.db_path) as con:
            con.execute("UPDATE combat_participants SET metadata_json=? WHERE encounter_id=? AND actor_id=?", (json.dumps(meta), eid, actor.actor_id))
        self._publish('combat_defense_started', {'encounter_id':eid,'actor_id':actor.actor_id,'world_time':self.world_time()})
        if actor.actor_id.startswith('character:'):
            self.enqueue_output(actor.actor_id.split(':',1)[1], 'You raise your guard and prepare for the next attack.', encounter_id=eid, room_id=actor.identity.current_location, category='defended_hit')

    def defend(self, character: Any) -> CombatRuntimeResult:
        return self.actor_defend(character)

    def _execute_ability(self, eid: str, attacker: Actor, defender: Actor, action: dict[str, Any] | None) -> CombatRuntimeResult:
        ability_id=str((action or {}).get('ability_id') or '')
        svc=getattr(self.runtime, 'abilities', None)
        if not svc: return self._execute_attack(eid, attacker, defender)
        svc.register_actor(attacker); svc.register_actor(defender); setattr(svc, '_world_time', self.world_time())
        res=svc.execute_instant_ability(attacker.actor_id.split(':',1)[1] if attacker.actor_id.startswith('character:') else attacker.actor_id, ability_id, defender)
        # Ability service commonly uses character ids; retry canonical actor id if needed.
        if not res.get('ok') and attacker.actor_id.startswith('character:'):
            svc.register_actor(attacker); res=svc.execute_instant_ability(attacker.actor_id, ability_id, defender)
        if not res.get('ok'):
            return CombatRuntimeResult(False, [res.get('message') or 'You cannot use that ability right now.'], eid)
        self.persist_actor(attacker); self.persist_actor(defender)
        dmg=sum(int(e.get('final_amount') or e.get('final_damage') or 0) for e in res.get('damage_events', []))
        msg=f"You use {ability_id.replace('_',' ')} on {defender.identity.name}." + (f" It deals {dmg} damage." if dmg else "")
        self.enqueue_output(attacker.actor_id.split(':',1)[1] if attacker.actor_id.startswith('character:') else '', msg, encounter_id=eid, room_id=attacker.identity.current_location, category='ability_used')
        with sqlite3.connect(self.db_path) as con:
            con.execute("INSERT INTO combat_round_history VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",('hist_'+uuid.uuid4().hex,eid,self._round(eid),attacker.actor_id,defender.actor_id,'ability',ability_id,'used',dmg,0,json.dumps(res),self.world_time(),datetime.now(timezone.utc).isoformat()))
            con.execute("UPDATE combat_participants SET last_action_round=?,next_action_world_time=? WHERE encounter_id=? AND actor_id=?",(self._round(eid),self.world_time()+1,eid,attacker.actor_id))
        if defender.resources.health<=0: self._handle_lethal_damage(eid, attacker, defender)
        return CombatRuntimeResult(True, [msg], eid)

    def queue_ability(self, character: Any, ability_query: str, target_query: str = "") -> CombatRuntimeResult:
        aid=self.actor_id_for_character(character); eid=self.find_actor_encounter(aid)
        if not eid: return CombatRuntimeResult(False, ['You are not currently fighting anyone.'])
        svc=getattr(self.runtime, 'abilities', None)
        rows=svc.get_actor_abilities(character.id) if svc else []
        q=ability_query.lower().replace(' ','_')
        row=next((r for r in rows if q in {str(r.get('id','')).lower(), str(r.get('name','')).lower().replace(' ','_')}), None)
        if not row: return CombatRuntimeResult(False, ["You do not know that ability."])
        with sqlite3.connect(self.db_path) as con: t=con.execute("SELECT current_target_actor_id FROM combat_participants WHERE encounter_id=? AND actor_id=?",(eid,aid)).fetchone()
        self.queue_action(eid, aid, 'ability', t[0] if t else '', ability_id=str(row.get('id')), source='player')
        return CombatRuntimeResult(True, [f"You ready {row.get('name') or row.get('id')} for your next opening."], eid)

    def target(self, character: Any, query: str) -> CombatRuntimeResult:
        aid = self.actor_id_for_character(character); eid = self.find_actor_encounter(aid)
        if not eid: return CombatRuntimeResult(False, ['You are not currently fighting anyone.'])
        ent = self.resolve_target(character, query)
        if not ent: return CombatRuntimeResult(False, ["You don't see that target here."])
        defender = self.actor_from_entity(ent)
        err = self.validate_attack(actor_from_runtime_character(character, self.runtime.active_world_id or ''), defender, ent)
        if err and 'yourself' not in err.lower(): return CombatRuntimeResult(False, [err])
        self.join_encounter(eid, defender, 'side_2')
        self.set_target(eid, aid, defender.actor_id)
        self.queue_action(eid, aid, 'basic_attack', defender.actor_id, source='player_target')
        return CombatRuntimeResult(True, [f'You turn your attention to {defender.identity.name}.'], eid)

    def assist(self, character: Any, query: str = '') -> CombatRuntimeResult:
        allies = [c for c in self.runtime.list_characters(self.runtime.active_world_id or '') if c.get('room_id') == character.room_id and c.get('character_id') != character.id]
        ally = None
        if query.strip():
            q=query.lower().strip(); ally=next((c for c in allies if q in str(c.get('name','')).lower()), None)
        else:
            ally=next((c for c in allies if self.find_actor_encounter('character:'+str(c.get('character_id','')))), None)
        if not ally: return CombatRuntimeResult(False, ['You do not see an ally here who needs assistance.'])
        aeid=self.find_actor_encounter('character:'+str(ally.get('character_id','')))
        if not aeid: return CombatRuntimeResult(False, [f"{ally.get('name')} is not fighting anyone."])
        with sqlite3.connect(self.db_path) as con:
            row=con.execute("SELECT current_target_actor_id FROM combat_participants WHERE encounter_id=? AND actor_id=?",(aeid,'character:'+str(ally.get('character_id','')))).fetchone()
        target_id=row[0] if row else ''
        target=self._load_actor(target_id)
        if not target or not target.actor_id.startswith('entity:'): return CombatRuntimeResult(False, ['There is no clear opponent to assist against.'])
        ent=self.runtime.find_entity(target.actor_id.split(':',1)[1])
        return self.start_player_attack(character, ent.get('name','') if ent else target.identity.name)

    def flee(self, character:Any, direction:str='')->CombatRuntimeResult:
        return self.actor_flee(character, direction)

    def status(self, character:Any)->str:
        aid=self.actor_id_for_character(character); eid=self.find_actor_encounter(aid)
        if not eid: return 'You are not in combat.'
        with sqlite3.connect(self.db_path) as con: row=con.execute("SELECT current_target_actor_id FROM combat_participants WHERE encounter_id=? AND actor_id=?",(eid,aid)).fetchone(); er=con.execute('SELECT current_round FROM combat_encounters WHERE encounter_id=?',(eid,)).fetchone()
        opp=self._load_actor(row[0]) if row else None
        return f"Combat Status\nOpponent: {opp.identity.name if opp else 'Unknown'}\nYour condition: {self.condition(actor_from_runtime_character(character,self.runtime.active_world_id or ''))}\nOpponent condition: {self.condition(opp) if opp else 'unknown'}\nRound: {er[0] if er else 0}\nNext action: basic attack"

    def condition(self, actor:Actor|None)->str:
        if not actor: return 'unknown'
        if actor.resources.health<=0: return 'dead'
        pct=actor.resources.health/max(1,actor.resources.maximum_health)
        return condition_label(actor)

    def diagnose(self, character:Any, query:str)->str:
        ent=self.resolve_target(character, query); return "You don't see that target here." if not ent else f"{ent.get('name')} is {self.condition(self.actor_from_entity(ent))}."
    def consider(self, character:Any, query:str)->str:
        ent=self.resolve_target(character, query); return "You don't see that target here." if not ent else f"You consider {ent.get('name')}. They look {self.engine.consider(actor_from_runtime_character(character,self.runtime.active_world_id or ''), self.actor_from_entity(ent))}."
    def leave_encounter(self,eid,actor_id,reason='left'): self._defeat(eid,actor_id); self.end_if_finished(eid)
    def suspend_or_cancel_invalid_encounter(self,eid,reason='invalid_state'): self.end_encounter(eid,reason)
    def trace_encounter(self,eid):
        with sqlite3.connect(self.db_path) as con: return {'encounter': dict(con.execute('SELECT * FROM combat_encounters WHERE encounter_id=?',(eid,)).fetchone() or {}), 'participants':[dict(r) for r in con.execute('SELECT * FROM combat_participants WHERE encounter_id=?',(eid,))]}
    def cancel_active_encounters_on_restart(self):
        now=datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as con: con.execute("UPDATE combat_encounters SET status='ended',ended_at=?,updated_at=?,end_reason='cancelled_on_restart' WHERE status='active'",(now,now))
