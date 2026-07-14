"""Canonical live combat runtime for Smart MUD.

`engine.combat.CombatEngine` remains the canonical single-attack resolver.
This module owns persistent encounters, participants, rounds, target state,
Actor synchronization, runtime legality checks, and player-facing combat flow.
The legacy `rules.combat` module is not imported here and is compatibility-only.
"""
from __future__ import annotations

import hashlib, json, sqlite3, uuid, time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engine.actors import Actor, ActorIdentity, ActorResources, actor_from_runtime_character, default_derived_statistics
from engine.combat import CombatEngine, CombatState, CombatResult
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
        con.execute("""CREATE TABLE IF NOT EXISTS combat_action_requests(action_id TEXT PRIMARY KEY,status TEXT,result_json TEXT,created_at TEXT,updated_at TEXT)""")
        con.execute("""CREATE TABLE IF NOT EXISTS character_attributes(character_id TEXT,attribute_id TEXT,base_value INTEGER,permanent_modifier INTEGER,created_at TEXT,updated_at TEXT,source TEXT,metadata_json TEXT,PRIMARY KEY(character_id,attribute_id))""")
        con.commit()


@dataclass(frozen=True)
class LifecycleTransitionResult:
    ok: bool
    actor_id: str
    character_id: str = ""
    transition_id: str = ""
    transition_type: str = "death"
    trigger_action_id: str = ""
    previous_state: str = "alive"
    new_state: str = "dead"
    already_processed: bool = False
    defeat_processed: bool = False
    death_processed: bool = False
    corpse_processed: bool = False
    rewards_processed: bool = False
    respawn_processed: bool = False
    combat_end_processed: bool = False
    corpse_status: str = "not_applicable"
    reward_status: str = "not_applicable"
    loot_status: str = "not_applicable"
    kill_credit_status: str = "not_applicable"
    quest_credit_status: str = "not_applicable"
    respawn_status: str = "not_applicable"
    combat_end_status: str = "not_applicable"
    corpse_id: str = ""
    respawn_id: str = ""
    reward_claim_id: str = ""
    events: tuple[str, ...] = ()
    reason_code: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class CorpseCreationResult:
    ok: bool
    transition_id: str
    corpse_id: str
    actor_id: str
    room_id: str
    created: bool = False
    existing: bool = False
    items_transferred: tuple[str, ...] = ()
    items_retained: tuple[str, ...] = ()
    items_destroyed: tuple[str, ...] = ()
    currency_transferred: int = 0
    currency_retained: int = 0
    loot_policy_id: str = "default_npc_death_loot"
    decay_schedule_id: str = ""
    status: str = "pending"
    reason_code: str = ""
    events: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class KillRewardResult:
    ok: bool
    transition_id: str
    reward_claim_id: str
    killer_actor_id: str
    victim_actor_id: str
    eligible_actor_ids: tuple[str, ...] = ()
    experience_awards: tuple[dict[str, Any], ...] = ()
    currency_awards: tuple[dict[str, Any], ...] = ()
    kill_credit_awards: tuple[dict[str, Any], ...] = ()
    quest_credit_awards: tuple[dict[str, Any], ...] = ()
    campaign_credit_awards: tuple[dict[str, Any], ...] = ()
    group_credit: dict[str, Any] = field(default_factory=dict)
    loot_eligibility: tuple[dict[str, Any], ...] = ()
    status: str = "pending"
    reason_code: str = ""
    events: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class RespawnScheduleResult:
    ok: bool
    transition_id: str
    respawn_id: str
    actor_id: str
    scheduled: bool = False
    existing: bool = False
    scheduled_world_time: int = 0
    scheduled_real_time: str = ""
    destination_world_id: str = ""
    destination_room_id: str = ""
    status: str = "pending"
    reason_code: str = ""
    events: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class CombatActionRequest:
    action_id: str
    round_id: str = ""
    world_id: str = ""
    zone_id: str = ""
    area_id: str = ""
    room_id: str = ""
    attacker_id: str = ""
    defender_id: str = ""
    ability_id: str = ""
    attack_kind: str = "basic_attack"
    damage_type: str = "physical"
    base_amount: int = 0
    formula_id: str = ""
    coefficient: float = 1.0
    requires_hit_roll: bool = True
    can_critical: bool = True
    critical_type: str = "weapon"
    armor_applies: bool = True
    resistance_applies: bool = True
    save_definition: dict[str, Any] = field(default_factory=dict)
    resource_costs: tuple[dict[str, Any], ...] = ()
    source_type: str = "runtime"
    source_id: str = ""
    distance: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    parent_action_id: str = ""
    reaction_chain_id: str = ""
    reaction_depth: int = 0

class RuntimeLifecycleService:
    def __init__(self, combat_runtime: "CombatRuntimeService"):
        self.combat = combat_runtime; self.runtime = combat_runtime.runtime; self.db_path = combat_runtime.db_path
        self.init_schema()
    def init_schema(self):
        with sqlite3.connect(self.db_path) as con:
            con.execute("""CREATE TABLE IF NOT EXISTS actor_lifecycle_transitions(transition_id TEXT PRIMARY KEY,world_id TEXT,room_id TEXT,actor_id TEXT,character_id TEXT,transition_type TEXT,trigger_action_id TEXT,previous_state TEXT,new_state TEXT,defeat_status TEXT DEFAULT 'pending',death_status TEXT DEFAULT 'pending',corpse_status TEXT DEFAULT 'pending',reward_status TEXT DEFAULT 'pending',respawn_status TEXT DEFAULT 'pending',combat_end_status TEXT DEFAULT 'pending',corpse_id TEXT,reward_claim_id TEXT,respawn_id TEXT,created_at TEXT,updated_at TEXT,metadata_json TEXT)""")
            for col, ddl in {'world_id':'TEXT','room_id':'TEXT','transition_id':'TEXT','actor_id':'TEXT','character_id':'TEXT','transition_type':'TEXT','trigger_action_id':'TEXT','previous_state':'TEXT','new_state':'TEXT','defeat_status':"TEXT DEFAULT 'pending'",'death_status':"TEXT DEFAULT 'pending'",'corpse_status':"TEXT DEFAULT 'pending'",'reward_status':"TEXT DEFAULT 'pending'",'loot_status':"TEXT DEFAULT 'pending'",'kill_credit_status':"TEXT DEFAULT 'pending'",'quest_credit_status':"TEXT DEFAULT 'pending'",'respawn_status':"TEXT DEFAULT 'pending'",'combat_end_status':"TEXT DEFAULT 'pending'",'corpse_id':'TEXT','reward_claim_id':'TEXT','respawn_id':'TEXT','created_at':'TEXT','updated_at':'TEXT','metadata_json':'TEXT'}.items():
                _ensure_column(con,'actor_lifecycle_transitions',col,ddl)
            con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_actor_lifecycle_once ON actor_lifecycle_transitions(world_id,actor_id,transition_id)")
            con.execute("""CREATE TABLE IF NOT EXISTS lifecycle_reward_claims(reward_claim_id TEXT PRIMARY KEY,transition_id TEXT UNIQUE,world_id TEXT,killer_actor_id TEXT,victim_actor_id TEXT,status TEXT,created_at TEXT,updated_at TEXT,result_json TEXT)""")
            con.execute("""CREATE TABLE IF NOT EXISTS actor_kill_credits(credit_id TEXT PRIMARY KEY,world_id TEXT,actor_id TEXT,victim_actor_id TEXT,victim_template_id TEXT,source_actor_id TEXT,transition_id TEXT,created_world_time INTEGER,created_at TEXT,metadata_json TEXT)""")
            con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_kill_credit_once ON actor_kill_credits(actor_id,transition_id,victim_actor_id)")
            con.execute("""CREATE TABLE IF NOT EXISTS actor_respawn_schedules(respawn_id TEXT PRIMARY KEY,transition_id TEXT UNIQUE,actor_id TEXT,world_id TEXT,destination_room_id TEXT,scheduled_world_time INTEGER,scheduled_at TEXT,status TEXT,completed_at TEXT,metadata_json TEXT)""")
            con.commit()

    def _stable_id(self, prefix: str, *parts: Any) -> str:
        raw = "|".join(json.dumps(p, sort_keys=True, default=str) for p in parts)
        return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:32]}"

    def _corpse_result(self, *, transition_id: str, actor: Actor, status: str, reason: str = "", corpse_id: str = "") -> CorpseCreationResult:
        return CorpseCreationResult(ok=status == "completed", transition_id=transition_id, corpse_id=corpse_id, actor_id=actor.actor_id, room_id=actor.identity.current_location, status=status, reason_code=reason)

    def create_corpse(self, transition_id: str, actor: Actor, killer_actor_id: str) -> CorpseCreationResult:
        if not actor.actor_id.startswith("entity:"):
            return self._corpse_result(transition_id=transition_id, actor=actor, status="skipped_by_policy", reason="player_corpse_policy_keeps_body_in_play")
        entity_id = actor.actor_id.split(":", 1)[1]
        stable_corpse_id = self._stable_id("corpse", self.runtime.active_world_id or "", actor.actor_id, transition_id)
        ent = self.runtime.find_entity(entity_id) or {}
        if not ent:
            return self._corpse_result(transition_id=transition_id, actor=actor, status="failed", reason="source_entity_missing")
        existing = [c for c in self.runtime.find_entities(entity_type="corpse", room_id=actor.identity.current_location) if (c.get("state") or {}).get("transition_id") == transition_id]
        if existing:
            cid = str(existing[0].get("entity_id") or existing[0].get("instance_id"))
            items = [i["instance_id"] for i in self.runtime.find_container_items(cid)]
            return CorpseCreationResult(True, transition_id, cid, actor.actor_id, actor.identity.current_location, existing=True, items_transferred=tuple(items), status="completed", reason_code="already_created", metadata={"stable_corpse_id": stable_corpse_id})
        corpse = self.runtime.create_corpse(entity_id, death_id=transition_id, killer_actor_id=killer_actor_id, source_system="runtime_lifecycle")
        cid = str(corpse.get("entity_id") or corpse.get("instance_id") or "")
        if not cid:
            return self._corpse_result(transition_id=transition_id, actor=actor, status="failed", reason="corpse_create_failed")
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as con:
            st = json.loads((corpse.get("state") or {}) if isinstance(corpse.get("state"), str) else json.dumps(corpse.get("state") or {}))
            st.update({"transition_id": transition_id, "stable_corpse_id": stable_corpse_id, "source_actor_id": actor.actor_id})
            con.execute("UPDATE entity_instances SET state=?,updated_at=? WHERE entity_id=?", (json.dumps(st), now, cid))
        items = self.runtime._fetch_items("owner_type IN ('entity','equipment','npc') AND owner_id=?", (entity_id,))
        moved: list[str] = []; kept: list[str] = []; destroyed: list[str] = []
        for item in items:
            flags = set(item.get("custom_flags") or {}) | set(item.get("template", {}).get("flags") or []) | set(item.get("template", {}).get("tags") or [])
            if "destroy_on_death" in flags:
                self.runtime.destroy_item(item["instance_id"], reason="destroy_on_death"); destroyed.append(item["instance_id"])
            elif flags.intersection({"keep_on_death", "soulbound", "quest_item"}):
                kept.append(item["instance_id"])
            else:
                self.runtime.move_item(item["instance_id"], "corpse", cid); moved.append(item["instance_id"])
        return CorpseCreationResult(True, transition_id, cid, actor.actor_id, actor.identity.current_location, created=True, items_transferred=tuple(moved), items_retained=tuple(kept), items_destroyed=tuple(destroyed), status="completed", events=("corpse_created",), metadata={"stable_corpse_id": stable_corpse_id})

    def award_kill_rewards(self, transition_id: str, encounter_id: str, killer: Actor, victim: Actor, trigger_action_id: str) -> KillRewardResult:
        rid = self._stable_id("reward", self.runtime.active_world_id or "", transition_id)
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as con:
            con.row_factory = sqlite3.Row
            old = con.execute("SELECT result_json FROM lifecycle_reward_claims WHERE transition_id=?", (transition_id,)).fetchone()
            if old:
                data = json.loads(old["result_json"] or "{}")
                return KillRewardResult(**data)
        environmental = (not killer.actor_id.startswith("character:")) or killer.actor_id == victim.actor_id
        eligible = (killer.actor_id,) if killer.actor_id.startswith("character:") and not environmental else ()
        xp_awards: list[dict[str, Any]] = []; currency_awards: list[dict[str, Any]] = []; credits: list[dict[str, Any]] = []
        tmpl = self.runtime.entity_templates.get(victim.actor_id.split(":", 1)[1], {}) if False else {}
        if victim.actor_id.startswith("entity:"):
            ent = self.runtime.find_entity(victim.actor_id.split(":", 1)[1]) or {}
            tmpl = self.runtime.entity_templates.get(str(ent.get("template_id") or ""), {})
        xp = int((tmpl.get("rewards") or {}).get("experience", tmpl.get("xp_reward", tmpl.get("experience_reward", 0))) or 0)
        gold = int((tmpl.get("rewards") or {}).get("currency", tmpl.get("gold", tmpl.get("currency_reward", 0))) or 0)
        with sqlite3.connect(self.db_path) as con:
            for aid in eligible:
                cid = aid.split(":", 1)[1]
                stat = con.execute("SELECT xp,gold FROM character_stats WHERE character_id=?", (cid,)).fetchone() or (0, 0)
                before_xp, before_gold = int(stat[0] or 0), int(stat[1] or 0)
                con.execute("UPDATE character_stats SET xp=COALESCE(xp,0)+?, gold=COALESCE(gold,0)+?, updated_at=CURRENT_TIMESTAMP WHERE character_id=?", (xp, gold, cid))
                ch_row = con.execute("SELECT data FROM characters WHERE id=?", (cid,)).fetchone()
                if ch_row:
                    try:
                        data = json.loads(ch_row[0] or "{}")
                    except Exception:
                        data = {}
                    data["xp"] = int(data.get("xp", before_xp) or 0) + xp
                    data["gold"] = int(data.get("gold", before_gold) or 0) + gold
                    con.execute("UPDATE characters SET data=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (json.dumps(data), cid))
                if xp:
                    xp_awards.append({"actor_id": aid, "before": before_xp, "after": before_xp + xp, "amount": xp})
                if gold:
                    currency_awards.append({"actor_id": aid, "currency_id": "gold", "before": before_gold, "after": before_gold + gold, "amount": gold})
                credit = {"actor_id": aid, "victim_actor_id": victim.actor_id, "transition_id": transition_id}
                con.execute("INSERT OR IGNORE INTO actor_kill_credits VALUES(?,?,?,?,?,?,?,?,?,?)", (self._stable_id("killcredit", aid, transition_id, victim.actor_id), self.runtime.active_world_id or "", aid, victim.actor_id, str(tmpl.get("id") or ""), killer.actor_id, transition_id, self.combat.world_time(), now, json.dumps({"trigger_action_id": trigger_action_id})))
                credits.append(credit)
            status = "completed" if eligible else "skipped_by_policy"
            result = KillRewardResult(bool(eligible), transition_id, rid, killer.actor_id, victim.actor_id, tuple(eligible), tuple(xp_awards), tuple(currency_awards), tuple(credits), status=status, reason_code="" if eligible else "no_eligible_player_reward", events=("experience_awarded", "kill_credit_awarded") if eligible else ())
            con.execute("INSERT OR IGNORE INTO lifecycle_reward_claims VALUES(?,?,?,?,?,?,?,?,?)", (rid, transition_id, self.runtime.active_world_id or "", killer.actor_id, victim.actor_id, status, now, now, json.dumps(result.__dict__, default=str)))
        return result

    def schedule_respawn(self, transition_id: str, actor: Actor) -> RespawnScheduleResult:
        rid = self._stable_id("respawn", self.runtime.active_world_id or "", transition_id)
        now = datetime.now(timezone.utc).isoformat(); wt = self.combat.world_time()
        dest = actor.identity.current_location
        delay = 5 if actor.actor_id.startswith("entity:") else 1
        with sqlite3.connect(self.db_path) as con:
            con.row_factory = sqlite3.Row
            old = con.execute("SELECT * FROM actor_respawn_schedules WHERE transition_id=?", (transition_id,)).fetchone()
            if old:
                return RespawnScheduleResult(True, transition_id, old["respawn_id"], actor.actor_id, existing=True, scheduled_world_time=int(old["scheduled_world_time"] or 0), scheduled_real_time=old["scheduled_at"] or "", destination_world_id=old["world_id"] or "", destination_room_id=old["destination_room_id"] or "", status=old["status"] or "pending")
            con.execute("INSERT OR IGNORE INTO actor_respawn_schedules VALUES(?,?,?,?,?,?,?,?,?,?)", (rid, transition_id, actor.actor_id, self.runtime.active_world_id or "", dest, wt + delay, now, "pending", "", json.dumps({"delay": delay})))
        return RespawnScheduleResult(True, transition_id, rid, actor.actor_id, scheduled=True, scheduled_world_time=wt + delay, scheduled_real_time=now, destination_world_id=self.runtime.active_world_id or "", destination_room_id=dest, status="pending", events=("respawn_scheduled",))
    def process_defeat_or_death(self, *, encounter_id:str, attacker:Actor, defender:Actor, trigger_action_id:str='') -> LifecycleTransitionResult:
        now=datetime.now(timezone.utc).isoformat(); world=self.runtime.active_world_id or ''; room=defender.identity.current_location
        transition_id='life_'+uuid.uuid5(uuid.NAMESPACE_URL, f"{world}:{defender.actor_id}:{trigger_action_id or defender.lifecycle_profile.get('lifecycle_id') or defender.actor_id}").hex
        with sqlite3.connect(self.db_path, timeout=30) as con:
            con.row_factory=sqlite3.Row; con.execute('BEGIN IMMEDIATE')
            inserted=con.execute("INSERT OR IGNORE INTO actor_lifecycle_transitions(transition_id,world_id,room_id,actor_id,character_id,transition_type,trigger_action_id,previous_state,new_state,created_at,updated_at,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(transition_id,world,room,defender.actor_id,defender.actor_id.split(':',1)[1] if defender.actor_id.startswith('character:') else '', 'death','' if not trigger_action_id else trigger_action_id,defender.lifecycle_state or 'alive','dead',now,now,json.dumps({'encounter_id':encounter_id,'killer_actor_id':attacker.actor_id}))).rowcount
            row=con.execute('SELECT * FROM actor_lifecycle_transitions WHERE transition_id=?',(transition_id,)).fetchone(); con.commit()
        already = not bool(inserted) and row['corpse_status']=='completed' and row['reward_status']=='completed' and row['respawn_status'] in {'pending','completed'} and row['combat_end_status']=='completed'
        events=[]; corpse_id=row['corpse_id'] or ''; reward_id=row['reward_claim_id'] or ''; respawn_id=row['respawn_id'] or ''
        corpse_status = row['corpse_status'] or 'pending'; reward_status = row['reward_status'] or 'pending'; loot_status = (row['loot_status'] if 'loot_status' in row.keys() else 'pending') or 'pending'; kill_credit_status = (row['kill_credit_status'] if 'kill_credit_status' in row.keys() else 'pending') or 'pending'; quest_credit_status = (row['quest_credit_status'] if 'quest_credit_status' in row.keys() else 'pending') or 'pending'; respawn_status = row['respawn_status'] or 'pending'; combat_end_status = row['combat_end_status'] or 'pending'
        self.combat._defeat(encounter_id, defender.actor_id); events.append('combat_participant_defeated')
        death_status = 'completed'; defeat_status = 'completed'
        if defender.actor_id.startswith('entity:'):
            defender.lifecycle_state='dead'; defender.resources.health=0; self.combat.persist_actor(defender)
            if row['corpse_status']!='completed':
                corpse_res = self.create_corpse(transition_id, defender, attacker.actor_id)
                corpse_id = corpse_res.corpse_id; corpse_status = corpse_res.status; loot_status = 'completed' if corpse_res.status == 'completed' else corpse_res.status
                with sqlite3.connect(self.db_path) as con:
                    con.execute("UPDATE actor_lifecycle_transitions SET corpse_status=?,loot_status=?,corpse_id=?,death_status='completed',defeat_status='completed',updated_at=? WHERE transition_id=?",(corpse_status,loot_status,corpse_id,now,transition_id))
                    con.execute("INSERT OR IGNORE INTO combat_death_transactions(death_id,encounter_id,actor_id,killer_actor_id,corpse_entity_id,world_id,room_id,created_world_time,created_at,metadata_json,lifecycle_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(transition_id,encounter_id,defender.actor_id,attacker.actor_id,corpse_id,world,room,self.combat.world_time(),now,json.dumps({'lifecycle_transition_id':transition_id}),str(defender.lifecycle_profile.get('lifecycle_id') or defender.actor_id)))
                events += ['actor_died'] + list(corpse_res.events)
            if row['reward_status'] not in {'completed','skipped_by_policy'}:
                reward_res = self.award_kill_rewards(transition_id, encounter_id, attacker, defender, trigger_action_id)
                reward_id = reward_res.reward_claim_id; reward_status = reward_res.status; kill_credit_status = 'completed' if reward_res.kill_credit_awards else reward_res.status; quest_credit_status = 'unsupported'
                with sqlite3.connect(self.db_path) as con: con.execute("UPDATE actor_lifecycle_transitions SET reward_status=?,kill_credit_status=?,quest_credit_status=?,reward_claim_id=?,updated_at=? WHERE transition_id=?",(reward_status,kill_credit_status,quest_credit_status,reward_id,now,transition_id))
                events += list(reward_res.events)
            if row['respawn_status'] not in {'pending','completed'} or not row['respawn_id']:
                respawn_res = self.schedule_respawn(transition_id, defender)
                respawn_id = respawn_res.respawn_id; respawn_status = respawn_res.status
                with sqlite3.connect(self.db_path) as con: con.execute("UPDATE actor_lifecycle_transitions SET respawn_status=?,respawn_id=?,updated_at=? WHERE transition_id=?",(respawn_status,respawn_id,now,transition_id))
                events += list(respawn_res.events)
        else:
            corpse_status='skipped_by_policy'; loot_status='skipped_by_policy'; reward_status='skipped_by_policy'; kill_credit_status='skipped_by_policy'; quest_credit_status='unsupported'
            respawn_res = self.schedule_respawn(transition_id, defender); respawn_id = respawn_res.respawn_id; respawn_status = respawn_res.status
            with sqlite3.connect(self.db_path) as con: con.execute("UPDATE actor_lifecycle_transitions SET defeat_status='completed',death_status='completed',corpse_status=?,loot_status=?,reward_status=?,kill_credit_status=?,quest_credit_status=?,respawn_status=?,respawn_id=?,updated_at=? WHERE transition_id=?",(corpse_status,loot_status,reward_status,kill_credit_status,quest_credit_status,respawn_status,respawn_id,now,transition_id))
        self.combat.end_if_finished(encounter_id)
        with sqlite3.connect(self.db_path) as con:
            ended = con.execute("SELECT status FROM combat_encounters WHERE encounter_id=?", (encounter_id,)).fetchone()
            combat_end_status = 'completed' if ended and ended[0] == 'ended' else 'pending'
            con.execute("UPDATE actor_lifecycle_transitions SET combat_end_status=?,updated_at=? WHERE transition_id=?",(combat_end_status,now,transition_id))
        for ev in events: self.combat._publish(ev, {'transition_id':transition_id,'actor_id':defender.actor_id,'world_id':world,'room_id':room})
        return LifecycleTransitionResult(True, defender.actor_id, defender.actor_id.split(':',1)[1] if defender.actor_id.startswith('character:') else '', transition_id, trigger_action_id=trigger_action_id, already_processed=already, defeat_processed=defeat_status=='completed', death_processed=death_status=='completed', corpse_processed=corpse_status=='completed', rewards_processed=reward_status=='completed', respawn_processed=respawn_status=='completed', combat_end_processed=combat_end_status=='completed', corpse_status=corpse_status, reward_status=reward_status, loot_status=loot_status, kill_credit_status=kill_credit_status, quest_credit_status=quest_credit_status, respawn_status=respawn_status, combat_end_status=combat_end_status, corpse_id=corpse_id, respawn_id=respawn_id, reward_claim_id=reward_id, events=tuple(events), metadata={'encounter_id':encounter_id})

@dataclass
class CombatRuntimeResult:
    ok: bool
    messages: list[str] = field(default_factory=list)
    encounter_id: str = ""

class CombatRuntimeService:
    ROUND_DELAY = 2.0
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
        self.lifecycle = RuntimeLifecycleService(self)
        self._real_start = time.monotonic()
        self.completed_actions: dict[str, Any] = {}
        self.resident_actors: dict[str, Actor] = {}
        self.dirty_resident_entities: set[str] = set()
        self._output_seq = 0
        self._output_queues: dict[str, list[dict[str, Any]]] = {}
        if not (self.engine.combat_stats is runtime.combat_stat_service and self.engine.resolution.combat_stats is runtime.combat_stat_service and self.engine.resolution.runtime is runtime):
            raise RuntimeError('Combat runtime invariant failed: canonical combat services are not wired to MudRuntime')
        self.cancel_active_encounters_on_restart()

    def refresh_content(self) -> None:
        self.engine.content = CombatContentRegistry(getattr(self.runtime, 'active_world', None))
        if getattr(self.runtime, 'combat_stat_service', None):
            self.engine.combat_stats = self.runtime.combat_stat_service; self.engine.resolution.combat_stats = self.runtime.combat_stat_service; self.engine.runtime = self.runtime; self.engine.resolution.runtime = self.runtime

    def world_time(self) -> int:
        return int((time.monotonic() - getattr(self, "_real_start", time.monotonic())) * 1000)

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
            cid=actor.actor_id.split(':',1)[1]; ch=getattr(self.runtime, "active_characters", {}).get(cid)
            if ch:
                ch.hp=actor.resources.health; ch.max_hp=actor.resources.maximum_health; ch.mana=actor.resources.mana; ch.max_mana=actor.resources.maximum_mana; ch.stamina=actor.resources.stamina; ch.max_stamina=actor.resources.maximum_stamina; ch.actor_data=actor.to_dict()
                if hasattr(self.runtime, "mark_character_dirty"):
                    self.runtime.mark_character_dirty(cid, "combat")
        elif actor.actor_id.startswith('entity:'):
            eid=actor.actor_id.split(':',1)[1]
            self.dirty_resident_entities.add(eid)
            if actor.resources.health <= 0 or actor.lifecycle_state == "dead":
                ent=self.runtime.find_entity(eid)
            else:
                ent = None
            if ent:
                st=ent.get('state') or {}; st.update({'current_health':actor.resources.health,'maximum_health':actor.resources.maximum_health,'combat_state':actor.combat_profile.get('combat_state','idle'),'is_alive': actor.resources.health>0 and actor.lifecycle_state!='dead','current_state':'dead' if actor.resources.health<=0 else st.get('current_state','idle')})
                self.runtime.update_entity_state(eid, st, source_system='combat_runtime')
                self.runtime.performance_counters["combat_entity_sql_writes"] = self.runtime.performance_counters.get("combat_entity_sql_writes", 0) + 1

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
        for cid, ch in getattr(self.runtime, "active_characters", {}).items():
            if ch and ch.room_id == room_id and cid not in ids:
                ids.append(cid)
        return ids

    def enqueue_output(self, character_id: str, message: str, *, encounter_id: str = "", room_id: str = "", category: str = "combat") -> None:
        if not character_id or not str(message or "").strip():
            return
        self._output_seq += 1
        now = time.monotonic()
        sess = getattr(self.runtime, "character_session_ids", {}).get(character_id, "")
        self._output_queues.setdefault(character_id, []).append({"sequence_id": self._output_seq, "character_id": character_id, "session_id": sess, "world_id": self.runtime.active_world_id or "", "room_id": room_id, "encounter_id": encounter_id, "category": category, "message": str(message).strip(), "prompt_invalidated": category.startswith("attack") or category in {"death","combat_end","condition_changed"}, "room_invalidated": category in {"death","combat_end"}, "created_monotonic": now, "delivery_monotonic": 0.0})
        self._output_queues[character_id] = self._output_queues[character_id][-200:]
        self.runtime.performance_counters["combat_messages_queued"] = self.runtime.performance_counters.get("combat_messages_queued", 0) + 1
        self.runtime.performance_counters["combat_output_in_memory_queued"] = self.runtime.performance_counters.get("combat_output_in_memory_queued", 0) + 1

    def drain_output(self, character_id: str, limit: int = 50) -> list[str]:
        queue = self._output_queues.get(character_id, [])
        rows = queue[: int(limit)]
        self._output_queues[character_id] = queue[int(limit):]
        now = time.monotonic()
        if rows:
            latency = max(0, int((now - min(float(r.get("created_monotonic") or now) for r in rows)) * 1000))
            self.runtime.performance_counters["combat_message_delivery_latency_ms"] = latency
        self.runtime.performance_counters["combat_messages_delivered"] = self.runtime.performance_counters.get("combat_messages_delivered", 0) + len(rows)
        return [str(r.get("message") or "") for r in rows]

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
        if rr.ok and not self.find_actor_encounter(attacker.actor_id):
            self.enqueue_output(character.id, f"The attack is over.", encounter_id=enc, room_id=character.room_id, category='combat_end')
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
        with sqlite3.connect(self.db_path) as con: con.execute("INSERT INTO combat_encounters VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(eid,self.runtime.active_world_id or '',room_id,'active',wt,0,wt+int(self.ROUND_DELAY*1000),now,now,None,None,'{}'))
        self._publish('combat_encounter_started', {'encounter_id':eid,'world_id':self.runtime.active_world_id or '', 'room_id':room_id,'round':0,'world_time':wt}); return eid

    def join_encounter(self,eid:str,actor:Actor,side:str)->None:
        kind, raw = actor.actor_id.split(':',1); wt=self.world_time(); init=int(actor.attributes.get('dexterity') or 10)
        self.resident_actors[actor.actor_id] = actor
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
        if actor_id in self.resident_actors:
            self.runtime.performance_counters["resident_actor_cache_hits"] = self.runtime.performance_counters.get("resident_actor_cache_hits", 0) + 1
            return self.resident_actors[actor_id]
        self.runtime.performance_counters["resident_actor_cache_misses"] = self.runtime.performance_counters.get("resident_actor_cache_misses", 0) + 1
        if actor_id.startswith('character:'):
            cid=actor_id.split(':',1)[1]
            ch=getattr(self.runtime, "active_characters", {}).get(cid) or self.runtime._resident_character(cid)
            if not ch: return None
            a=actor_from_runtime_character(ch,self.runtime.active_world_id or ''); a.actor_id=actor_id; self.resident_actors[actor_id] = a; return a
        ent=self.runtime.find_entity(actor_id.split(':',1)[1]) if actor_id.startswith('entity:') else None
        if ent:
            a = self.actor_from_entity(ent); self.resident_actors[actor_id] = a; return a
        return None

    def submit_action(self, request: CombatActionRequest) -> Any:
        forbidden={'hit','critical','final_damage','health_after','forced_success','ignore_save','ignore_cooldown','ignore_cost'}
        if forbidden.intersection(request.metadata):
            self._publish('combat_action_validation_denied', {'action_id':request.action_id,'reason':'controller_outcome_fields_denied','fields':sorted(forbidden.intersection(request.metadata))})
            return CombatRuntimeResult(False, ['That combat action was denied.'])
        with sqlite3.connect(self.db_path, timeout=30) as con:
            con.row_factory=sqlite3.Row; con.execute('BEGIN IMMEDIATE')
            prior=con.execute('SELECT result_json FROM combat_action_requests WHERE action_id=? AND status=?',(request.action_id,'completed')).fetchone()
            if prior:
                con.commit()
                try:
                    data=json.loads(prior['result_json'] or '{}')
                    return CombatRuntimeResult(bool(data.get('ok', True)), list(data.get('messages') or ['Duplicate action ignored.']), str(data.get('encounter_id') or ''))
                except Exception:
                    return CombatRuntimeResult(True, ['Duplicate action ignored.'])
            con.execute('INSERT OR IGNORE INTO combat_action_requests(action_id,status,created_at,updated_at) VALUES(?,?,?,?)',(request.action_id,'claimed',datetime.now(timezone.utc).isoformat(),datetime.now(timezone.utc).isoformat()))
            con.commit()
        attacker=self._load_actor(request.attacker_id); defender=self._load_actor(request.defender_id)
        if not attacker or not defender: return CombatRuntimeResult(False, ['Combat action actors are unavailable.'])
        if attacker.resources.health<=0: return CombatRuntimeResult(False, ['Combat action is no longer valid.'])
        if defender.resources.health<=0 and request.attack_kind not in {'resurrection'}: return CombatRuntimeResult(False, ['Combat action is no longer valid.'])
        rr=self._execute_attack_direct(request, attacker, defender)
        with sqlite3.connect(self.db_path) as con: con.execute('UPDATE combat_action_requests SET status=?,result_json=?,updated_at=? WHERE action_id=?',('completed',json.dumps(rr.__dict__, default=str),datetime.now(timezone.utc).isoformat(),request.action_id))
        return rr

    def _execute_attack_direct(self, request: CombatActionRequest, attacker:Actor, defender:Actor)->CombatRuntimeResult:
        eid=request.round_id or self.find_actor_encounter(attacker.actor_id)
        wt=self.world_time(); self._publish('combat_action_started',{'action_id':request.action_id,'encounter_id':eid,'actor_id':attacker.actor_id,'target_actor_id':defender.actor_id,'action_type':request.attack_kind,'source_type':request.source_type,'source_id':request.source_id,'world_time':wt})
        if request.attack_kind in {'healing','heal'}:
            from engine.runtime_resources import RuntimeResourceService
            amount=max(0, int(request.base_amount or 0))
            rr=RuntimeResourceService(self.runtime, db_path=self.db_path, event_bus=self.event_bus, world_id=self.runtime.active_world_id or '').apply_healing(defender, amount, action_id=request.action_id, metadata={'source':request.source_type,'ability_id':request.ability_id,'encounter_id':eid,'room_id':request.room_id})
            self.persist_actor(defender)
            msg=f"{attacker.identity.name} heals {defender.identity.name} for {rr.applied_amount}."
            with sqlite3.connect(self.db_path) as con:
                con.execute("INSERT INTO combat_round_history VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",('hist_'+uuid.uuid4().hex,eid,self._round(eid),attacker.actor_id,defender.actor_id,request.attack_kind,request.ability_id,'healed',0,rr.applied_amount,json.dumps({'action_id':request.action_id,'resource_result':rr.__dict__,'source_type':request.source_type,'source_id':request.source_id}),wt,datetime.now(timezone.utc).isoformat()))
            return CombatRuntimeResult(True,[msg],eid)
        old_weapons = attacker.combat_profile.get('natural_weapons')
        if request.base_amount and request.attack_kind not in {'basic_attack','melee','ranged','unarmed'}:
            attacker.combat_profile['natural_weapons']=[{'id':request.source_id or request.ability_id or request.attack_kind,'name':request.ability_id or request.attack_kind,'damage_type':request.damage_type,'base_damage':max(0,int(request.base_amount))}]
        ctx=__import__('engine.combat', fromlist=['CombatResolutionContext']).CombatResolutionContext(world_id=request.world_id, zone_id=request.zone_id, area_id=request.area_id, room_id=request.room_id or attacker.identity.current_location, attacker_id=attacker.actor_id, defender_id=defender.actor_id, ability_id=request.ability_id or None, attack_kind=request.attack_kind, damage_kind=request.damage_type, distance=request.distance, world_time=wt, round_id=eid, action_id=request.action_id, metadata={**(request.metadata or {}), 'base_amount': request.base_amount, 'formula_id': request.formula_id, 'coefficient': request.coefficient, 'requires_hit_roll': request.requires_hit_roll, 'can_critical': request.can_critical, 'critical_type': request.critical_type, 'armor_applies': request.armor_applies, 'resistance_applies': request.resistance_applies, **(request.save_definition or {})})
        rr=self.engine.resolution.resolve(attacker, defender, ctx)
        res=CombatResult(rr.hit, __import__('engine.combat', fromlist=['DamageEvent']).DamageEvent(attacker.actor_id, defender.actor_id, {}, rr.diagnostics.get('selected_attack_profile', {'name':'attack'}), rr.damage_type, rr.raw_amount, rr.critical, rr.mitigated_amount, rr.final_amount, self.engine.tick) if rr.hit else None, 'recovering', 'in_combat', rr.messages, list(rr.diagnostics.get('trace', [])))
        if request.base_amount and request.attack_kind not in {'basic_attack','melee','ranged','unarmed'}:
            if old_weapons is None: attacker.combat_profile.pop('natural_weapons', None)
            else: attacker.combat_profile['natural_weapons']=old_weapons
        self.last_resolution={'attacker_id':attacker.actor_id,'defender_id':defender.actor_id,'hit':res.hit,'damage':res.damage_event.final_damage if res.damage_event else 0,'source_type':request.source_type,'source_id':request.source_id,'attack_kind':request.attack_kind,'trace':res.trace,'messages':res.messages}; self.persist_actor(attacker); self.persist_actor(defender)
        dmg=res.damage_event.final_damage if res.damage_event else 0; outcome='hit' if res.hit else 'miss'
        if dmg <= 0 and request.source_type == 'opening' and defender.resources.health <= 1:
            from engine.runtime_resources import RuntimeResourceService
            rr = RuntimeResourceService(self.runtime, db_path=self.db_path, event_bus=self.event_bus, world_id=self.runtime.active_world_id or '').apply_damage(defender, 1, action_id=request.action_id, metadata={'source':request.source_type,'encounter_id':eid,'room_id':request.room_id})
            self.persist_actor(defender); dmg = int(rr.applied_amount or 0); outcome = 'hit' if dmg else outcome
            try:
                res.messages['attacker'] = f"You strike {defender.identity.name} with a killing blow!"
            except Exception:
                pass
        with sqlite3.connect(self.db_path) as con:
            con.execute("INSERT INTO combat_round_history VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",('hist_'+uuid.uuid4().hex,eid,self._round(eid),attacker.actor_id,defender.actor_id,request.attack_kind,request.ability_id,outcome,dmg,0,json.dumps({'action_id':request.action_id,'hit':res.hit,'damage':dmg,'trace':res.trace,'messages':res.messages,'source_type':request.source_type,'source_id':request.source_id,'attack_kind':request.attack_kind,'lifecycle_result':getattr(self,'last_resolution',{}).get('lifecycle_result')}),wt,datetime.now(timezone.utc).isoformat()))
            con.execute("UPDATE combat_participants SET last_action_round=?,next_action_world_time=?,contribution_damage=contribution_damage+? WHERE encounter_id=? AND actor_id=?",(self._round(eid),wt+max(1,int(self.engine.attack_profile(attacker).speed*1000)),dmg,eid,attacker.actor_id))
            con.execute("UPDATE combat_encounters SET next_round_world_time=?,updated_at=? WHERE encounter_id=?",(wt+int(self.ROUND_DELAY*1000),datetime.now(timezone.utc).isoformat(),eid))
        self._publish('combat_attack_resolved',{'encounter_id':eid,'actor_id':attacker.actor_id,'target_actor_id':defender.actor_id,'result':outcome,'damage':dmg,'round':self._round(eid),'world_time':wt})
        if dmg: self._publish('combat_damage_applied',{'encounter_id':eid,'actor_id':attacker.actor_id,'target_actor_id':defender.actor_id,'damage':dmg,'round':self._round(eid),'world_time':wt})
        self._publish('combat_action_completed',{'encounter_id':eid,'actor_id':attacker.actor_id,'target_actor_id':defender.actor_id,'result':outcome,'world_time':wt})
        self._deliver_combat_messages(eid, attacker, defender, res, 'critical_hit' if (res.damage_event and res.damage_event.critical) else ('attack_hit' if res.hit else 'attack_miss'), skip_attacker=bool(request.metadata.get('opening')))
        msgs=[res.messages.get('attacker','')]
        prev_key = condition_key({"current_health": max(0, defender.resources.health + dmg), "maximum_health": defender.resources.maximum_health})
        now_key = condition_key(defender)
        if dmg and defender.resources.health > 0 and prev_key != now_key:
            msg = transition_text(defender.identity.name, defender)
            msgs.append(msg)
            self._broadcast_room(eid, attacker.identity.current_location, msg, category='condition_changed')
        if defender.resources.health<=0:
            life = self.lifecycle.process_defeat_or_death(encounter_id=eid, attacker=attacker, defender=defender, trigger_action_id=request.action_id)
            self.last_resolution['lifecycle_result'] = life.__dict__
            msgs.append(f'{defender.identity.name} collapses and dies.')
        return CombatRuntimeResult(True,msgs,eid)

    def _execute_attack(self,eid:str,attacker:Actor,defender:Actor,opening:bool=False)->CombatRuntimeResult:
        return self.submit_action(CombatActionRequest(action_id="act_"+uuid.uuid4().hex, round_id=eid, world_id=self.runtime.active_world_id or "", room_id=attacker.identity.current_location, attacker_id=attacker.actor_id, defender_id=defender.actor_id, source_type="opening" if opening else "round", metadata={"opening": opening}))

    def _round(self,eid):
        with sqlite3.connect(self.db_path) as con: r=con.execute('SELECT current_round FROM combat_encounters WHERE encounter_id=?',(eid,)).fetchone(); return int(r[0] if r else 0)

    def process_due_rounds(self, world_time:int|None=None)->list[str]:
        wt=self.world_time() if world_time is None else int(world_time); out=[]
        with sqlite3.connect(self.db_path) as con: eids=[r[0] for r in con.execute("SELECT encounter_id FROM combat_encounters WHERE status='active' AND next_round_world_time<=?",(wt,))]
        self.runtime.performance_counters["combat_encounter_sql_reads"] = self.runtime.performance_counters.get("combat_encounter_sql_reads", 0) + 1
        self.runtime.performance_counters["combat_encounters_active"] = len(eids)
        processed=0
        for eid in eids:
            if processed >= self.MAX_ACTIONS_PER_PULSE:
                self.runtime.performance_counters["combat_backlog"] = len(eids)-processed
                self._publish('combat_pulse_backlog', {'world_id':self.runtime.active_world_id or '', 'remaining':len(eids)-processed, 'world_time':wt})
                break
            out += self.process_encounter_round(eid, wt); processed += 1
        self.runtime.performance_counters["combat_rounds_processed"] = self.runtime.performance_counters.get("combat_rounds_processed", 0) + processed
        self._publish('combat_pulse_processed', {'world_id':self.runtime.active_world_id or '', 'encounters':processed, 'world_time':wt})
        return out

    def process_due_respawns(self, world_time: int | None = None) -> list[RespawnScheduleResult]:
        wt = self.world_time() if world_time is None else int(world_time)
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as con:
            con.row_factory = sqlite3.Row; con.execute("BEGIN IMMEDIATE")
            rows = [dict(r) for r in con.execute("SELECT * FROM actor_respawn_schedules WHERE status='pending' AND scheduled_world_time<=? ORDER BY scheduled_world_time,respawn_id", (wt,))]
            for r in rows:
                con.execute("UPDATE actor_respawn_schedules SET status='claimed' WHERE respawn_id=? AND status='pending'", (r["respawn_id"],))
            con.commit()
        out: list[RespawnScheduleResult] = []
        for r in rows:
            aid = r["actor_id"]; actor = self._load_actor(aid)
            if actor:
                actor.lifecycle_state = "alive"; actor.resources.health = max(1, actor.resources.maximum_health)
                actor.resources.mana = max(actor.resources.mana, actor.resources.maximum_mana)
                actor.resources.stamina = max(actor.resources.stamina, actor.resources.maximum_stamina)
                actor.identity = ActorIdentity(name=actor.identity.name, current_location=r["destination_room_id"], current_world=r["world_id"])
                if aid.startswith("character:"):
                    ch = self.runtime.state_store.load_character(aid.split(":", 1)[1])
                    if ch:
                        ch.room_id = r["destination_room_id"]; ch.hp = actor.resources.health; ch.mana = actor.resources.mana; ch.stamina = actor.resources.stamina
                        self.runtime.state_store.save_character(ch, self.runtime.active_world_id or "")
                else:
                    self.persist_actor(actor)
            with sqlite3.connect(self.db_path) as con:
                con.execute("UPDATE actor_respawn_schedules SET status='completed',completed_at=? WHERE respawn_id=? AND status='claimed'", (now, r["respawn_id"]))
                con.execute("UPDATE actor_lifecycle_transitions SET respawn_status='completed',updated_at=? WHERE transition_id=?", (now, r["transition_id"]))
                con.execute("UPDATE combat_participants SET participation_status='respawned',current_target_actor_id='' WHERE actor_id=?", (aid,))
            self._publish("actor_respawned", {"respawn_id": r["respawn_id"], "transition_id": r["transition_id"], "actor_id": aid, "world_id": r["world_id"], "room_id": r["destination_room_id"], "world_time": wt})
            out.append(RespawnScheduleResult(True, r["transition_id"], r["respawn_id"], aid, existing=True, scheduled_world_time=int(r["scheduled_world_time"] or 0), scheduled_real_time=r["scheduled_at"] or "", destination_world_id=r["world_id"] or "", destination_room_id=r["destination_room_id"] or "", status="completed", events=("actor_respawned",)))
        return out

    def process_encounter_round(self,eid:str,wt:int|None=None)->list[str]:
        started = time.monotonic()
        wt=self.world_time() if wt is None else wt; rnd=self._round(eid)+1
        with sqlite3.connect(self.db_path) as con:
            con.execute('UPDATE combat_encounters SET current_round=?,next_round_world_time=?,updated_at=? WHERE encounter_id=?',(rnd,wt+int(self.ROUND_DELAY*1000),datetime.now(timezone.utc).isoformat(),eid))
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
                with sqlite3.connect(self.db_path) as con: con.execute("UPDATE combat_participants SET last_action_round=?,next_action_world_time=? WHERE encounter_id=? AND actor_id=?",(rnd,wt+1000,eid,aid))
            elif atype == 'flee':
                pass
            elif atype == 'ability' and (act or {}).get('ability_id'):
                rr=self._execute_ability(eid,a,d,act); msgs += rr.messages
            else:
                rr=self._execute_attack(eid,a,d); msgs += rr.messages
        self.runtime.performance_counters["combat_rounds_processed"] = self.runtime.performance_counters.get("combat_rounds_processed", 0) + 1
        self.runtime.performance_counters["combat_round_duration_ms"] = int((time.monotonic() - started) * 1000)
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
        life = self.lifecycle.process_defeat_or_death(encounter_id=eid, attacker=attacker, defender=defender, trigger_action_id='')
        msg = 'You collapse and die.' if defender.actor_id.startswith('character:') else f"{defender.identity.name} collapses and dies."
        self._broadcast_room(eid, defender.identity.current_location, msg, category='actor_died')
        if attacker.actor_id.startswith('character:'):
            self.enqueue_output(attacker.actor_id.split(':',1)[1], "Your opponent is dead. Combat ends.", encounter_id=eid, room_id=defender.identity.current_location, category='combat_end')
        return {'lifecycle_transition_id': life.transition_id, 'corpse_id': life.corpse_id, 'messages': [msg]}

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
