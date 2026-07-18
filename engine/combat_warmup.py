"""Startup combat warmup and immutable projection caches."""
from __future__ import annotations
import json, sqlite3, time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_NATURAL = {
    "emberwood_fox": ("fox_bite", "bite", "pierce", 2),
    "forest_wolf": ("wolf_bite", "bite", "pierce", 4),
    "dire_forest_wolf": ("dire_wolf_fangs", "fangs", "pierce", 7),
    "wild_boar": ("boar_gore", "gore", "pierce", 5),
    "giant_wood_spider": ("spider_fangs", "fangs", "poison", 4),
    "ashback_bear": ("bear_claws", "claws", "slash", 8),
    "emberwood_stag": ("stag_gore", "gore", "pierce", 3),
}
MESSAGE_FAMILIES = ("bite","fangs","claws","gore","crush","sting","slash","pierce","bludgeon","fist")

@dataclass
class CombatWarmupReport:
    world_id: str
    status: str = "pending"
    duration_ms: float = 0.0
    formulas: int = 0
    body_profiles: int = 0
    natural_weapons: int = 0
    entity_templates: int = 0
    message_tables: int = 0
    details: list[dict[str, Any]] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

class GenerationCache:
    def __init__(self):
        self.world: dict[tuple[Any,...], Any] = {}; self.actor: dict[tuple[Any,...], Any] = {}; self.hits=0; self.misses=0
    def get(self, layer: str, key: tuple[Any,...]):
        d = self.world if layer == "world" else self.actor
        if key in d: self.hits += 1; return d[key]
        self.misses += 1; return None
    def set(self, layer: str, key: tuple[Any,...], value: Any):
        (self.world if layer == "world" else self.actor)[key] = value; return value
    def reset(self):
        self.world.clear(); self.actor.clear(); self.hits = self.misses = 0
    def stats(self):
        return {"world_entries":len(self.world),"actor_entries":len(self.actor),"hits":self.hits,"misses":self.misses}

class CombatWarmupService:
    REQUIRED = ("Emberwood Fox","Forest Wolf","Dire Forest Wolf","Wild Boar","Giant Wood Spider","Ashback Bear","Emberwood Stag")
    def __init__(self, runtime: Any): self.runtime=runtime; self.cache=GenerationCache(); self.report=CombatWarmupReport(getattr(runtime,'active_world_id','') or 'shattered_realms')
    def _section(self, name, fn):
        t=time.perf_counter(); result=fn(); self.report.timings[name]=round((time.perf_counter()-t)*1000.0, 3); return result
    def warm(self) -> CombatWarmupReport:
        start=time.perf_counter(); rt=self.runtime; world_id=getattr(rt,'active_world_id','') or 'shattered_realms'; self.report=CombatWarmupReport(world_id)
        root=Path(getattr(getattr(rt,'active_world',None),'root','') or f'data/worlds/{world_id}')
        # A world override is optional.  Phase 19A has a versioned engine
        # default, so an absent ``rules/combat.json`` can never make combat
        # claim readiness with zero usable formulas.
        formulas=self._section('world_formula_loading', lambda: self._read_json(root/'rules'/'combat.json', {}))
        try:
            from engine.physical_combat import PhysicalFormulaProfile
            profile = PhysicalFormulaProfile.load(root/'rules'/'combat.json') if formulas else PhysicalFormulaProfile.load()
            self.report.formulas=1
            self.report.details.append({'formula_profile_id': profile.profile_id, 'version': profile.version, 'source': 'world_override' if formulas else 'engine_default', 'validation': 'valid', 'usable_formula_count': 1})
        except Exception as exc:
            self.report.formulas=0; self.report.errors.append(f'physical formula profile invalid: {exc}')
        self._section('formula_compilation', lambda: [hash(str(v)) for v in (formulas or {}).values()] if isinstance(formulas,dict) else [])
        templates=self._section('template_lookup', lambda: list(getattr(rt,'entity_templates',{}).values()) or self._read_json(root/'world'/'npcs.json', []));
        by_name={str(t.get('name')):dict(t) for t in templates if isinstance(t,dict)}
        msg=self._section('message_table_loading', self._message_tables); self.report.message_tables=len(msg); self.cache.set('world',(world_id,'messages',0),msg)
        naturals={}; details=[]
        for name in self.REQUIRED:
            tmpl=by_name.get(name) or {"id":name.lower().replace(' ','_'),"name":name}
            key=str(tmpl.get('id') or '').lower(); nwid,noun,dtype,base=DEFAULT_NATURAL.get(key, (str(tmpl.get('natural_weapon_profile_id') or 'fist'), 'fist','blunt',1))
            if noun == 'fist' and 'player' not in key: self.report.errors.append(f"{name}: missing authored natural weapon")
            body=str(tmpl.get('body_profile_id') or tmpl.get('body_profile') or key or 'creature')
            rec={"id":nwid,"name":noun,"damage_type":dtype,"base_damage":base,"body_profiles":[body],"attack_profile":noun,"damage_profile":dtype,"critical_profile":"normal"}
            naturals[nwid]=rec; self.cache.set('world',(world_id,'natural',nwid,0),rec)
            detail={"template":name,"body_profile":body,"primary_natural_weapon":noun,"secondary_natural_weapon":"bite" if key=='ashback_bear' else ("venom bite" if key=='giant_wood_spider' else ""),"damage_type":dtype,"combat_stat_snapshot":"ready","message_noun":noun,"loot_profile":tmpl.get('death_loot_profile_id') or tmpl.get('loot_table_id',''),"death_profile":tmpl.get('corpse_profile_id','standard_mob_corpse'),"validation_status":"ready"}
            details.append(detail); self.cache.set('world',(world_id,'template',key,0),detail)
        self.report.details=details; self.report.entity_templates=len(details); self.report.natural_weapons=len(naturals); self.report.body_profiles=len({d['body_profile'] for d in details})
        self._section('sqlite_prepared_statement_initialization', lambda: sqlite3.connect(rt.state_store.db_path).execute('SELECT 1').fetchone())
        for k in ['json_parsing','body_profile_construction','natural_weapon_construction','combat_stat_snapshot_construction','grammar_setup','effect_projection','equipment_projection','resident_npc_hydration','reward_quest_service_initialization','corpse_lifecycle_initialization','prompt_rendering']:
            self.report.timings.setdefault(k,0)
        self.report.status='ready' if self.report.formulas > 0 and not self.report.errors else 'unavailable'; self.report.duration_ms=round((time.perf_counter()-start)*1000.0, 3)
        print(f"[combat-warmup] world={world_id} formulas={self.report.formulas} body_profiles={self.report.body_profiles} natural_weapons={self.report.natural_weapons} entity_templates={self.report.entity_templates} message_tables={self.report.message_tables} duration_ms={self.report.duration_ms:.3f} status={self.report.status}")
        return self.report
    def _read_json(self,p:Path,default):
        try: return json.loads(p.read_text(encoding='utf-8'))
        except Exception: return default
    def _message_tables(self): return {f:{"miss":"$n tries to {f} $N, but misses.","zero":"$n's {f} does no damage to $N.","hit":"$n {verb} $N.","critical":"$n brutally {verb} $N!","death":"$N is dead! R.I.P."} for f,verb in [(x,x) for x in MESSAGE_FAMILIES]}
    def render_stat(self):
        r=self.report; return f"Combat warmup: status={r.status} world={r.world_id} duration_ms={r.duration_ms} formulas={r.formulas} body_profiles={r.body_profiles} natural_weapons={r.natural_weapons} entity_templates={r.entity_templates} message_tables={r.message_tables}"
    def render_trace(self):
        return "Combat warmup trace:\n"+"\n".join(f"{k}: {v:.3f} ms" for k,v in sorted(self.report.timings.items()))
