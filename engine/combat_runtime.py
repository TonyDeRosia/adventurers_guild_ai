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


def init_combat_runtime_schema(db_path: str | Path) -> None:
    with sqlite3.connect(db_path) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS combat_encounters(encounter_id TEXT PRIMARY KEY,world_id TEXT,room_id TEXT,status TEXT,started_world_time INTEGER,current_round INTEGER,next_round_world_time INTEGER,created_at TEXT,updated_at TEXT,ended_at TEXT,end_reason TEXT,metadata_json TEXT)""")
        con.execute("""CREATE TABLE IF NOT EXISTS combat_participants(encounter_id TEXT,actor_id TEXT,actor_type TEXT,entity_instance_id TEXT,character_id TEXT,side_id TEXT,current_target_actor_id TEXT,participation_status TEXT,initiative_value INTEGER,joined_round INTEGER,last_action_round INTEGER,next_action_world_time INTEGER,contribution_damage INTEGER DEFAULT 0,contribution_healing INTEGER DEFAULT 0,contribution_support INTEGER DEFAULT 0,fled INTEGER DEFAULT 0,defeated INTEGER DEFAULT 0,metadata_json TEXT,PRIMARY KEY(encounter_id,actor_id))""")
        con.execute("""CREATE TABLE IF NOT EXISTS combat_action_queue(action_id TEXT PRIMARY KEY,encounter_id TEXT,actor_id TEXT,action_type TEXT,ability_id TEXT,target_actor_id TEXT,queued_round INTEGER,execute_world_time INTEGER,status TEXT,source TEXT,metadata_json TEXT,created_at TEXT,resolved_at TEXT)""")
        con.execute("""CREATE TABLE IF NOT EXISTS combat_round_history(history_id TEXT PRIMARY KEY,encounter_id TEXT,round_number INTEGER,actor_id TEXT,target_actor_id TEXT,action_type TEXT,ability_id TEXT,outcome TEXT,damage INTEGER,healing INTEGER,result_json TEXT,world_time INTEGER,created_at TEXT)""")
        con.execute("CREATE INDEX IF NOT EXISTS idx_combat_encounters_active ON combat_encounters(world_id,room_id,status)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_combat_participants_actor ON combat_participants(actor_id,participation_status)")
        con.commit()

@dataclass
class CombatRuntimeResult:
    ok: bool
    messages: list[str] = field(default_factory=list)
    encounter_id: str = ""

class CombatRuntimeService:
    ROUND_DELAY = 1
    def __init__(self, runtime: Any):
        self.runtime = runtime; self.db_path = runtime.state_store.db_path; self.event_bus = runtime.event_bus
        init_combat_runtime_schema(self.db_path)
        self.engine = CombatEngine(FormulaEngine(), content=CombatContentRegistry(getattr(runtime, 'active_world', None)))
        self.cancel_active_encounters_on_restart()

    def refresh_content(self) -> None:
        self.engine.content = CombatContentRegistry(getattr(self.runtime, 'active_world', None))

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
        a.body_profile_id = str(tmpl.get('body_profile_id') or ('wolf' if 'wolf' in str(tmpl.get('id','')) else 'humanoid'))
        a.lifecycle_state = 'dead' if not ent.get('is_alive', True) or hp <= 0 else 'alive'
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
        visible = self.runtime.find_visible_entities(character.room_id, character); cands = visible.get('npcs',[])+visible.get('mobs',[])
        return self.runtime.resolve_entity_keywords(query, cands).get('entity')

    def validate_attack(self, attacker: Actor, defender: Actor, ent: dict[str,Any]|None=None) -> str:
        if attacker.actor_id == defender.actor_id: return 'You cannot attack yourself.'
        if attacker.resources.health <= 0 or attacker.combat_profile.get('combat_state') in {'dead','sleeping','unconscious','incapacitated'}: return 'You cannot attack right now.'
        if defender.resources.health <= 0 or defender.lifecycle_state == 'dead': return 'They are already dead.'
        if attacker.identity.current_location != defender.identity.current_location: return 'They are not here.'
        if ent:
            tmpl = dict(self.runtime.entity_templates.get(str(ent.get('template_id') or ''), {})); flags=set(tmpl.get('flags') or [])|set(ent.get('flags') or [])|set(tmpl.get('tags') or [])
            policy = tmpl.get('combat_policy') or {}
            if policy.get('protected') or policy.get('no_kill') or 'protected' in flags or 'trainer_protected' in flags or tmpl.get('kind') == 'trainer': return f"{defender.identity.name} is protected and cannot be attacked."
            if policy.get('attackable') is False or ('hostile' not in flags and 'attackable' not in flags and not policy.get('attackable')): return f"{defender.identity.name} is not a valid combat target."
        return ''

    def start_player_attack(self, character: Any, query: str) -> CombatRuntimeResult:
        if not query.strip(): return CombatRuntimeResult(False, ['Attack whom?'])
        ent=self.resolve_target(character, query)
        if not ent: return CombatRuntimeResult(False, ["You don't see that target here."])
        self.refresh_content(); attacker=actor_from_runtime_character(character,self.runtime.active_world_id or ''); attacker.actor_id=self.actor_id_for_character(character); defender=self.actor_from_entity(ent)
        err=self.validate_attack(attacker,defender,ent)
        if err: return CombatRuntimeResult(False,[err])
        enc=self.find_actor_encounter(attacker.actor_id) or self.start_encounter(character.room_id)
        self.join_encounter(enc, attacker, 'side_1'); self.join_encounter(enc, defender, 'side_2'); self.set_target(enc, attacker.actor_id, defender.actor_id); self.set_target(enc, defender.actor_id, attacker.actor_id)
        return self._execute_attack(enc, attacker, defender, opening=True)

    def start_encounter(self, room_id: str) -> str:
        eid='enc_'+uuid.uuid4().hex; now=datetime.now(timezone.utc).isoformat(); wt=self.world_time()
        with sqlite3.connect(self.db_path) as con: con.execute("INSERT INTO combat_encounters VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(eid,self.runtime.active_world_id or '',room_id,'active',wt,0,wt+self.ROUND_DELAY,now,now,None,None,'{}'))
        self._publish('combat_encounter_started', {'encounter_id':eid,'world_id':self.runtime.active_world_id or '', 'room_id':room_id,'round':0,'world_time':wt}); return eid

    def join_encounter(self,eid:str,actor:Actor,side:str)->None:
        kind, raw = actor.actor_id.split(':',1); wt=self.world_time(); init=int(actor.attributes.get('dexterity') or 10)
        with sqlite3.connect(self.db_path) as con: con.execute("INSERT OR IGNORE INTO combat_participants(encounter_id,actor_id,actor_type,entity_instance_id,character_id,side_id,current_target_actor_id,participation_status,initiative_value,joined_round,last_action_round,next_action_world_time,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(eid,actor.actor_id,actor.actor_type,raw if kind=='entity' else '',raw if kind=='character' else '',side,'','active',init,0,-1,wt,'{}'))
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
        res=self.engine.resolve_attack(attacker,defender,room_id=attacker.identity.current_location,world_time=wt); self.persist_actor(attacker); self.persist_actor(defender)
        dmg=res.damage_event.final_damage if res.damage_event else 0; outcome='hit' if res.hit else 'miss'
        with sqlite3.connect(self.db_path) as con:
            con.execute("INSERT INTO combat_round_history VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",('hist_'+uuid.uuid4().hex,eid,self._round(eid),attacker.actor_id,defender.actor_id,'basic_attack','',outcome,dmg,0,json.dumps({'hit':res.hit,'damage':dmg}),wt,datetime.now(timezone.utc).isoformat()))
            con.execute("UPDATE combat_participants SET last_action_round=?,next_action_world_time=?,contribution_damage=contribution_damage+? WHERE encounter_id=? AND actor_id=?",(self._round(eid),wt+max(1,self.engine.attack_profile(attacker).speed),dmg,eid,attacker.actor_id))
            con.execute("UPDATE combat_encounters SET next_round_world_time=?,updated_at=? WHERE encounter_id=?",(wt+self.ROUND_DELAY,datetime.now(timezone.utc).isoformat(),eid))
        self._publish('combat_attack_resolved',{'encounter_id':eid,'actor_id':attacker.actor_id,'target_actor_id':defender.actor_id,'result':outcome,'damage':dmg,'round':self._round(eid),'world_time':wt})
        if dmg: self._publish('combat_damage_applied',{'encounter_id':eid,'actor_id':attacker.actor_id,'target_actor_id':defender.actor_id,'damage':dmg,'round':self._round(eid),'world_time':wt})
        self._publish('combat_action_completed',{'encounter_id':eid,'actor_id':attacker.actor_id,'target_actor_id':defender.actor_id,'result':outcome,'world_time':wt})
        msgs=[res.messages.get('attacker','')]
        if defender.resources.health<=0: msgs.append(f"{defender.identity.name} falls."); self._defeat(eid, defender.actor_id); self.end_if_finished(eid)
        return CombatRuntimeResult(True,msgs,eid)

    def _round(self,eid):
        with sqlite3.connect(self.db_path) as con: r=con.execute('SELECT current_round FROM combat_encounters WHERE encounter_id=?',(eid,)).fetchone(); return int(r[0] if r else 0)

    def process_due_rounds(self, world_time:int|None=None)->list[str]:
        wt=self.world_time() if world_time is None else int(world_time); out=[]
        with sqlite3.connect(self.db_path) as con: eids=[r[0] for r in con.execute("SELECT encounter_id FROM combat_encounters WHERE status='active' AND next_round_world_time<=?",(wt,))]
        for eid in eids: out += self.process_encounter_round(eid, wt)
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
            rr=self._execute_attack(eid,a,d); msgs += [m for m in rr.messages if not aid.startswith('character:') or aid == rows[0][0]]
        self.end_if_finished(eid); return msgs

    def _defeat(self,eid,actor_id):
        with sqlite3.connect(self.db_path) as con: con.execute("UPDATE combat_participants SET participation_status='defeated',defeated=1 WHERE encounter_id=? AND actor_id=?",(eid,actor_id))
        self._publish('combat_participant_defeated',{'encounter_id':eid,'actor_id':actor_id,'world_time':self.world_time()})

    def end_if_finished(self,eid):
        with sqlite3.connect(self.db_path) as con: rows=con.execute("SELECT side_id FROM combat_participants WHERE encounter_id=? AND participation_status='active' AND defeated=0 AND fled=0",(eid,)).fetchall()
        if len(set(r[0] for r in rows)) < 2: self.end_encounter(eid,'victory')

    def end_encounter(self,eid,reason):
        now=datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as con: con.execute("UPDATE combat_encounters SET status='ended',ended_at=?,updated_at=?,end_reason=? WHERE encounter_id=? AND status='active'",(now,now,reason,eid))
        self._publish('combat_encounter_ended',{'encounter_id':eid,'end_reason':reason,'world_time':self.world_time()})

    def flee(self, character:Any, direction:str='')->CombatRuntimeResult:
        aid=self.actor_id_for_character(character); eid=self.find_actor_encounter(aid)
        if not eid: return CombatRuntimeResult(False,['You are not in combat.'])
        exits=self.runtime._current_room(character).exits; dirs=[e.get('direction') for e in exits]
        direction=direction or (dirs[0] if dirs else '')
        if not direction: return CombatRuntimeResult(False,['There is nowhere to flee.'])
        move=self.runtime._move_character(character,direction)
        if not move.ok: return CombatRuntimeResult(False,[move.narrative])
        with sqlite3.connect(self.db_path) as con: con.execute("UPDATE combat_participants SET participation_status='fled',fled=1 WHERE encounter_id=? AND actor_id=?",(eid,aid))
        self._publish('combat_participant_fled',{'encounter_id':eid,'actor_id':aid,'direction':direction,'world_time':self.world_time()}); self.end_if_finished(eid)
        return CombatRuntimeResult(True,[f'You flee {direction}.'],eid)

    def status(self, character:Any)->str:
        aid=self.actor_id_for_character(character); eid=self.find_actor_encounter(aid)
        if not eid: return 'You are not in combat.'
        with sqlite3.connect(self.db_path) as con: row=con.execute("SELECT current_target_actor_id FROM combat_participants WHERE encounter_id=? AND actor_id=?",(eid,aid)).fetchone(); er=con.execute('SELECT current_round FROM combat_encounters WHERE encounter_id=?',(eid,)).fetchone()
        opp=self._load_actor(row[0]) if row else None
        return f"Combat Status\nOpponent: {opp.identity.name if opp else 'Unknown'}\nYour condition: {character.hp} / {character.max_hp} health\nOpponent condition: {self.condition(opp) if opp else 'unknown'}\nRound: {er[0] if er else 0}\nNext action: basic attack"

    def condition(self, actor:Actor|None)->str:
        if not actor: return 'unknown'
        if actor.resources.health<=0: return 'dead'
        pct=actor.resources.health/max(1,actor.resources.maximum_health)
        return 'unwounded' if pct>=.95 else 'lightly hurt' if pct>=.7 else 'wounded' if pct>=.4 else 'badly wounded' if pct>=.15 else 'near collapse'

    def diagnose(self, character:Any, query:str)->str:
        ent=self.resolve_target(character, query); return "You don't see that target here." if not ent else f"{ent.get('name')} is {self.condition(self.actor_from_entity(ent))}."
    def consider(self, character:Any, query:str)->str:
        ent=self.resolve_target(character, query); return "You don't see that target here." if not ent else f"You consider {ent.get('name')}. They look {self.engine.consider(actor_from_runtime_character(character,self.runtime.active_world_id or ''), self.actor_from_entity(ent))}."
    def queue_action(self,*a,**k): return ''
    def leave_encounter(self,eid,actor_id,reason='left'): self._defeat(eid,actor_id); self.end_if_finished(eid)
    def suspend_or_cancel_invalid_encounter(self,eid,reason='invalid_state'): self.end_encounter(eid,reason)
    def trace_encounter(self,eid):
        with sqlite3.connect(self.db_path) as con: return {'encounter': dict(con.execute('SELECT * FROM combat_encounters WHERE encounter_id=?',(eid,)).fetchone() or {}), 'participants':[dict(r) for r in con.execute('SELECT * FROM combat_participants WHERE encounter_id=?',(eid,))]}
    def cancel_active_encounters_on_restart(self):
        now=datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as con: con.execute("UPDATE combat_encounters SET status='ended',ended_at=?,updated_at=?,end_reason='cancelled_on_restart' WHERE status='active'",(now,now))
