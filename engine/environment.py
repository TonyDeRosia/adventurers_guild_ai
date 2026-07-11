"""Canonical Phase 11A environment service.

This module intentionally centralizes climate, seasons, daylight, weather,
lighting, visibility, and exposure foundations behind one service boundary.
It is conservative: data-driven world-package profiles drive deterministic
runtime state persisted in SQLite, while movement/combat/quest/property/etc.
consume context hooks instead of owning environment state.
"""
from __future__ import annotations

import hashlib, json, random, sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

COLLECTIONS = (
    "climate_profiles", "season_profiles", "daylight_profiles", "moonlight_profiles",
    "weather_type_definitions", "weather_transition_profiles", "room_environment_profiles",
    "light_source_profiles", "actor_vision_profiles", "environment_exposure_profiles",
    "environment_message_profiles", "environment_override_profiles", "environment_render_profiles",
    "environment_hazard_profiles",
)

WEATHER_SCOPE_TYPES = {"world", "area", "zone", "custom"}
LIGHT_CLASSES = [(0.05,"pitch_black"),(0.2,"dark"),(0.45,"dim"),(0.9,"normal"),(1.5,"bright"),(999,"blinding_placeholder")]


def _read_records(world_root: Path, collection: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    path = world_root / collection
    if not path.exists():
        return out
    for p in sorted(path.glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, list):
            out.extend(x for x in data if isinstance(x, dict))
        elif isinstance(data, dict):
            value = data.get(collection) or data.get("records")
            out.extend(value if isinstance(value, list) else [data])
    return out


def _by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(r.get("id")): r for r in rows if r.get("id")}


def init_environment_schema(db_path: Path | str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS environment_weather_state (
            weather_state_id TEXT PRIMARY KEY, world_id TEXT, scope_type TEXT, scope_id TEXT,
            climate_profile_id TEXT, current_weather_type TEXT, previous_weather_type TEXT,
            temperature REAL, humidity REAL, wind_speed REAL, wind_direction TEXT,
            precipitation_intensity REAL, fog_density REAL, storm_intensity REAL, visibility_modifier REAL,
            started_world_time INTEGER, next_transition_world_time INTEGER, transition_seed INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            metadata_json TEXT DEFAULT '{}', UNIQUE(world_id, scope_type, scope_id)
        )""")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS environment_light_sources (
            light_source_id TEXT PRIMARY KEY, world_id TEXT, source_type TEXT, source_id TEXT,
            owner_type TEXT, owner_id TEXT, room_id TEXT, profile_id TEXT, status TEXT,
            light_level REAL, fuel_current REAL, started_world_time INTEGER, expires_world_time INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            metadata_json TEXT DEFAULT '{}', UNIQUE(world_id, source_type, source_id, owner_type, owner_id)
        )""")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS actor_environment_exposure (
            exposure_state_id TEXT PRIMARY KEY, world_id TEXT, actor_id TEXT UNIQUE,
            temperature_exposure REAL DEFAULT 0, wetness REAL DEFAULT 0, wind_exposure REAL DEFAULT 0,
            storm_exposure REAL DEFAULT 0, sun_exposure_placeholder REAL DEFAULT 0,
            last_updated_world_time INTEGER DEFAULT 0, current_environment_hash TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            metadata_json TEXT DEFAULT '{}'
        )""")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS environment_runtime_overrides (
            override_instance_id TEXT PRIMARY KEY, profile_id TEXT, scope_type TEXT, scope_id TEXT,
            source_type TEXT, source_id TEXT, priority INTEGER, started_world_time INTEGER,
            expires_world_time INTEGER, status TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP, metadata_json TEXT DEFAULT '{}'
        )""")

@dataclass
class EnvironmentService:
    db_path: Path | str
    world_root: Path | str
    world_id: str = "shattered_realms"
    event_bus: Any = None

    def __post_init__(self) -> None:
        self.db_path = Path(self.db_path); self.world_root = Path(self.world_root)
        init_environment_schema(self.db_path)
        self.records = {c: _by_id(_read_records(self.world_root, c)) for c in COLLECTIONS}

    def _world_minutes(self, world_time: dict[str, Any] | int | None) -> int:
        if isinstance(world_time, int): return world_time
        wt = world_time or {"day":1,"hour":12,"minute":0}
        return (int(wt.get("day",1))-1)*1440 + int(wt.get("hour",0))*60 + int(wt.get("minute",0))

    def validate_content(self) -> dict[str, list[str]]:
        errors: list[str] = []; warnings: list[str] = []
        seasons = self.records["season_profiles"]; transitions = self.records["weather_transition_profiles"]
        daylight = self.records["daylight_profiles"]; exposure = self.records["environment_exposure_profiles"]
        weather = self.records["weather_type_definitions"]
        for c in self.records["climate_profiles"].values():
            if c.get("season_profile_id") and c["season_profile_id"] not in seasons: errors.append(f"Climate {c['id']} references missing season profile")
            if c.get("weather_transition_profile_id") and c["weather_transition_profile_id"] not in transitions: errors.append(f"Climate {c['id']} references missing transition profile")
            if c.get("daylight_profile_id") and c["daylight_profile_id"] not in daylight: errors.append(f"Climate {c['id']} references missing daylight profile")
            if c.get("exposure_profile_id") and c["exposure_profile_id"] not in exposure: errors.append(f"Climate {c['id']} references missing exposure profile")
            for key in ("temperature_range","humidity_range","wind_range"):
                r=c.get(key,[0,0]);
                if not isinstance(r,list) or len(r)!=2 or float(r[0])>float(r[1]): errors.append(f"Climate {c['id']} has invalid {key}")
        for p in seasons.values():
            ranges=[]
            for s in p.get("seasons",[]):
                if int(s.get("start_day",0))>int(s.get("end_day",0)): errors.append(f"Season {s.get('id')} has invalid range")
                ranges.append((int(s.get("start_day",0)), int(s.get("end_day",0)), s.get("id")))
            for i,a in enumerate(ranges):
                for b in ranges[i+1:]:
                    if max(a[0],b[0]) <= min(a[1],b[1]): errors.append(f"Season profile {p['id']} overlaps {a[2]} and {b[2]}")
        for p in transitions.values():
            if int(p.get("minimum_duration",1)) <= 0: errors.append(f"Transition {p['id']} has non-positive duration")
            for r in p.get("transition_rules",[]):
                if r.get("to_weather_id") not in weather: errors.append(f"Transition {p['id']} references missing weather {r.get('to_weather_id')}")
                if float(r.get("weight",0)) < 0: errors.append(f"Transition {p['id']} has negative weight")
        for p in self.records["room_environment_profiles"].values():
            if p.get("outdoor") and p.get("underground"): warnings.append(f"Room environment {p['id']} is both outdoor and underground")
        return {"errors": errors, "warnings": warnings}

    def default_climate(self) -> dict[str, Any]:
        return self.records["climate_profiles"].get("guildlands_temperate") or next(iter(self.records["climate_profiles"].values()), {"id":"safe_fallback","base_temperature":18,"humidity_range":[30,60],"wind_range":[0,10],"weather_transition_profile_id":""})

    def resolve_season(self, world_time: dict[str, Any] | int | None, season_profile_id: str = "") -> dict[str, Any]:
        profile = self.records["season_profiles"].get(season_profile_id) or self.records["season_profiles"].get(self.default_climate().get("season_profile_id","")) or {}
        day = (self._world_minutes(world_time)//1440) % max(1, int(profile.get("cycle_length_days", 365))) + 1
        for season in profile.get("seasons",[]):
            if int(season.get("start_day",1)) <= day <= int(season.get("end_day",1)): return {**season, "profile_id": profile.get("id"), "cycle_day": day}
        return {"id": profile.get("starting_season_id","seasonless"), "profile_id": profile.get("id",""), "cycle_day": day}

    def resolve_day_period(self, world_time: dict[str, Any] | int | None, daylight_profile_id: str = "") -> dict[str, Any]:
        p = self.records["daylight_profiles"].get(daylight_profile_id) or self.records["daylight_profiles"].get(self.default_climate().get("daylight_profile_id","")) or {}
        minute = self._world_minutes(world_time) % int(p.get("day_length_minutes",1440))
        sr=int(p.get("sunrise_world_minute",360)); ss=int(p.get("sunset_world_minute",1080)); dawn=int(p.get("dawn_duration",60)); dusk=int(p.get("dusk_duration",60))
        if sr-dawn <= minute < sr: name="dawn"
        elif sr <= minute < sr+180: name="morning"
        elif sr+180 <= minute < ss-180: name="day"
        elif ss-180 <= minute < ss: name="afternoon"
        elif ss <= minute < ss+dusk: name="dusk"
        elif minute >= ss+dusk or minute < max(0, sr-dawn-180): name="deep_night"
        else: name="night"
        light = 1.0 if name in {"morning","day","afternoon"} else (0.35 if name in {"dawn","dusk"} else float(p.get("night_light_level",0.05)))
        return {"period": name, "minute": minute, "natural_light": light, "profile_id": p.get("id","")}

    def _state_id(self, scope_type: str, scope_id: str) -> str: return f"env_weather_{self.world_id}_{scope_type}_{scope_id}"
    def _seed(self, *parts: Any) -> int: return int(hashlib.sha256(":".join(map(str,parts)).encode()).hexdigest()[:12],16)

    def get_weather(self, scope_type: str = "world", scope_id: str = "default") -> dict[str, Any]:
        if scope_type not in WEATHER_SCOPE_TYPES: scope_type="world"
        with sqlite3.connect(self.db_path) as conn:
            row=conn.execute("SELECT * FROM environment_weather_state WHERE world_id=? AND scope_type=? AND scope_id=?",(self.world_id,scope_type,scope_id)).fetchone()
            cols=[d[0] for d in conn.execute("SELECT * FROM environment_weather_state LIMIT 0").description]
        if row: return dict(zip(cols,row))
        climate=self.default_climate(); seed=self._seed(self.world_id,scope_type,scope_id,"init"); weather="clear"
        temp=float(climate.get("base_temperature",18)); humidity=sum(map(float, climate.get("humidity_range",[30,60])))/2; wind=sum(map(float, climate.get("wind_range",[0,10])))/2
        nxt=60
        state={"weather_state_id":self._state_id(scope_type,scope_id),"world_id":self.world_id,"scope_type":scope_type,"scope_id":scope_id,"climate_profile_id":climate.get("id",""),"current_weather_type":weather,"previous_weather_type":"","temperature":temp,"humidity":humidity,"wind_speed":wind,"wind_direction":"variable","precipitation_intensity":0,"fog_density":0,"storm_intensity":0,"visibility_modifier":1,"started_world_time":0,"next_transition_world_time":nxt,"transition_seed":seed,"metadata_json":"{}"}
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""INSERT OR IGNORE INTO environment_weather_state(weather_state_id,world_id,scope_type,scope_id,climate_profile_id,current_weather_type,previous_weather_type,temperature,humidity,wind_speed,wind_direction,precipitation_intensity,fog_density,storm_intensity,visibility_modifier,started_world_time,next_transition_world_time,transition_seed,metadata_json) VALUES(:weather_state_id,:world_id,:scope_type,:scope_id,:climate_profile_id,:current_weather_type,:previous_weather_type,:temperature,:humidity,:wind_speed,:wind_direction,:precipitation_intensity,:fog_density,:storm_intensity,:visibility_modifier,:started_world_time,:next_transition_world_time,:transition_seed,:metadata_json)""", state)
        return self.get_weather(scope_type, scope_id)

    def _choose_next(self, current: str, profile: dict[str, Any], now: int, seed: int, season_id: str="") -> str:
        rules=[r for r in profile.get("transition_rules",[]) if r.get("from_weather_id") in {"*", current, None, ""} and (not r.get("season_ids") or season_id in r.get("season_ids",[]))]
        if not rules: return current
        total=sum(max(0,float(r.get("weight",0))) for r in rules) or 1
        pick=random.Random(self._seed(seed, current, now)).uniform(0,total); acc=0.0
        for r in rules:
            acc += max(0,float(r.get("weight",0)))
            if pick <= acc: return str(r.get("to_weather_id") or current)
        return str(rules[-1].get("to_weather_id") or current)

    def process_environment_time(self, world_id: str, world_time: dict[str, Any] | int) -> list[dict[str, Any]]:
        self.world_id=world_id; now=self._world_minutes(world_time); changed=[]; state=self.get_weather("world","default")
        climate=self.records["climate_profiles"].get(state["climate_profile_id"]) or self.default_climate(); profile=self.records["weather_transition_profiles"].get(climate.get("weather_transition_profile_id","")) or {}
        maxn=int(profile.get("maximum_transitions_per_tick",3)); count=0
        while now >= int(state["next_transition_world_time"] or 0) and count < maxn:
            season=self.resolve_season(state["next_transition_world_time"], climate.get("season_profile_id",""))
            new=self._choose_next(state["current_weather_type"], profile, int(state["next_transition_world_time"]), int(state["transition_seed"]), season.get("id",""))
            wdef=self.records["weather_type_definitions"].get(new,{})
            interval=int(profile.get("interval_minutes",120)); old=state["current_weather_type"]
            temp=float(climate.get("base_temperature",18))+float(wdef.get("temperature_modifier",0))+float(season.get("temperature_modifier",0) or 0)
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("UPDATE environment_weather_state SET previous_weather_type=?, current_weather_type=?, temperature=?, precipitation_intensity=?, fog_density=?, storm_intensity=?, visibility_modifier=?, started_world_time=?, next_transition_world_time=?, transition_seed=?, updated_at=CURRENT_TIMESTAMP WHERE weather_state_id=?",(old,new,temp,float(wdef.get("precipitation_intensity",0)),float(wdef.get("fog_density",0)),float(wdef.get("storm_intensity",0)),float(wdef.get("visibility_modifier",1)),int(state["next_transition_world_time"]),int(state["next_transition_world_time"])+interval,self._seed(state["transition_seed"],new),state["weather_state_id"]))
            changed.append({"from":old,"to":new}); count += 1; state=self.get_weather("world","default")
        return changed

    def get_forecast(self, scope_type="world", scope_id="default", horizon: int | None=None) -> dict[str, Any]:
        state=self.get_weather(scope_type, scope_id); climate=self.records["climate_profiles"].get(state["climate_profile_id"]) or self.default_climate(); profile=self.records["weather_transition_profiles"].get(climate.get("weather_transition_profile_id","")) or {}
        nxt=self._choose_next(state["current_weather_type"], profile, int(state["next_transition_world_time"]), int(state["transition_seed"]), self.resolve_season(state["next_transition_world_time"]).get("id",""))
        return {"current_conditions": state["current_weather_type"], "likely_next_weather": nxt, "transition_window": state["next_transition_world_time"], "temperature_trend": "steady", "precipitation_risk": self.records["weather_type_definitions"].get(nxt,{}).get("precipitation_intensity",0), "uncertainty_label": "deterministic_model"}

    def resolve_room_environment(self, room: dict[str, Any] | str, world: Any=None, world_time: dict[str, Any] | int | None=None) -> dict[str, Any]:
        if isinstance(room,str) and world: room = world.room(room)
        r = room if isinstance(room,dict) else {}
        profile_id=r.get("environment_profile_id") or ("underground_dark" if r.get("terrain")=="underground" else "indoor_sheltered" if r.get("terrain")=="indoor" else "outdoor_temperate")
        profile=self.records["room_environment_profiles"].get(profile_id) or {}
        weather=self.get_weather("world","default"); day=self.resolve_day_period(world_time or 720); wdef=self.records["weather_type_definitions"].get(weather["current_weather_type"],{})
        light=self.resolve_room_light(r, world_time, weather, profile)
        return {"room_id":r.get("id",""),"profile_id":profile_id,"environment_profile":profile,"weather":weather,"day_period":day,"light":light,"sheltered":bool(profile.get("sheltered")),"temperature":float(weather.get("temperature") or 18)+float(profile.get("temperature_modifier",0)),"visibility_modifier":float(profile.get("visibility_modifier",1))*float(weather.get("visibility_modifier") or 1)*float(wdef.get("visibility_modifier",1))}

    def resolve_room_light(self, room: dict[str, Any], world_time=None, weather: dict[str, Any] | None=None, profile: dict[str, Any] | None=None) -> dict[str, Any]:
        weather=weather or self.get_weather(); profile=profile or {}; day=self.resolve_day_period(world_time or 720); wdef=self.records["weather_type_definitions"].get(weather["current_weather_type"],{})
        ambient=day["natural_light"]*float(wdef.get("light_modifier",1))*float(profile.get("natural_light_multiplier",1))
        artificial=0.0
        with sqlite3.connect(self.db_path) as conn:
            rows=conn.execute("SELECT light_level FROM environment_light_sources WHERE world_id=? AND status='active' AND (room_id=? OR owner_id=?)",(self.world_id,room.get("id",""),room.get("actor_id",""))).fetchall()
        artificial += sum(float(x[0] or 0) for x in rows)
        effective=max(0.0, ambient+artificial)
        cls=next(name for limit,name in LIGHT_CLASSES if effective <= limit)
        return {"ambient_light":ambient,"artificial_light":artificial,"magical_light":0,"darkness_penalty":0,"effective_light":effective,"light_class":cls}

    def activate_light_source(self, source_type: str, source_id: str, profile_id: str, owner_type="", owner_id="", room_id="", world_time: int=0) -> dict[str, Any]:
        p=self.records["light_source_profiles"].get(profile_id) or {}; lid=f"env_light_{self.world_id}_{source_type}_{source_id}"
        fuel=float(p.get("duration_minutes") or 0); level=float(p.get("base_light_level",0))
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT OR REPLACE INTO environment_light_sources(light_source_id,world_id,source_type,source_id,owner_type,owner_id,room_id,profile_id,status,light_level,fuel_current,started_world_time,expires_world_time,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(lid,self.world_id,source_type,source_id,owner_type,owner_id,room_id,profile_id,"active",level,fuel,world_time,world_time+int(fuel) if fuel else None,"{}"))
        return {"light_source_id":lid,"status":"active","light_level":level}

    def extinguish_light_source(self, source_type: str, source_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur=conn.execute("UPDATE environment_light_sources SET status='extinguished', updated_at=CURRENT_TIMESTAMP WHERE world_id=? AND source_type=? AND source_id=?",(self.world_id,source_type,source_id))
        return cur.rowcount>0

    def evaluate_visibility(self, observer_actor_id: str, target_type: str, target_id: str, room: dict[str, Any] | None=None) -> dict[str, Any]:
        env=self.resolve_room_environment(room or {}, world_time=720); light=env["light"]["effective_light"]; fog=float(env["weather"].get("fog_density") or 0)
        profile=self.records["actor_vision_profiles"].get("normal_vision") or {"minimum_light_threshold":0.2,"fog_penetration":0.0}
        threshold=float(profile.get("minimum_light_threshold",0.2)); visible = light >= threshold and fog < (1+float(profile.get("fog_penetration",0)))
        result="visible" if visible else ("silhouette" if light>0.05 else "not_visible")
        return {"observer_actor_id":observer_actor_id,"target_type":target_type,"target_id":target_id,"result":result,"visible":visible,"light_class":env["light"]["light_class"],"fog_density":fog,"vision_profile_id":profile.get("id","normal_vision")}

    def accumulate_exposure(self, actor_id: str, room: dict[str, Any], world_time: int) -> dict[str, Any]:
        env=self.resolve_room_environment(room, world_time=world_time); reduction=0.75 if env["sheltered"] else 0.0; wet=max(0,float(env["weather"].get("precipitation_intensity") or 0)-reduction)
        eid=f"env_exposure_{self.world_id}_{actor_id}"; h=hashlib.sha1(json.dumps({"w":env["weather"]["current_weather_type"],"s":env["sheltered"]},sort_keys=True).encode()).hexdigest()
        with sqlite3.connect(self.db_path) as conn:
            row=conn.execute("SELECT wetness,last_updated_world_time FROM actor_environment_exposure WHERE actor_id=?",(actor_id,)).fetchone(); old=float(row[0]) if row else 0; last=int(row[1]) if row else world_time
            if row and last==world_time: val=old
            else: val=max(0,min(100, old + wet))
            conn.execute("INSERT OR REPLACE INTO actor_environment_exposure(exposure_state_id,world_id,actor_id,wetness,last_updated_world_time,current_environment_hash,metadata_json) VALUES(?,?,?,?,?,?,?)",(eid,self.world_id,actor_id,val,world_time,h,"{}"))
        return {"actor_id":actor_id,"wetness":val,"sheltered":env["sheltered"],"current_environment_hash":h}

    def movement_context(self, room: dict[str, Any]) -> dict[str, Any]:
        env=self.resolve_room_environment(room); weather=env["weather"]["current_weather_type"]
        wdef=self.records["weather_type_definitions"].get(weather,{})
        return {"movement_modifier": float(wdef.get("movement_modifier",1)), "visibility_warning": env["light"]["light_class"] in {"pitch_black","dark"}}
    def combat_context(self, room: dict[str, Any]) -> dict[str, Any]:
        env=self.resolve_room_environment(room); return {"visibility_modifier": env["visibility_modifier"], "darkness_penalty": env["light"]["darkness_penalty"], "combat_modifier_profile_id": self.records["weather_type_definitions"].get(env["weather"]["current_weather_type"],{}).get("combat_modifier_profile_id","")}
    def living_world_context(self, room: dict[str, Any], world_time: int=720) -> dict[str, Any]:
        env=self.resolve_room_environment(room, world_time=world_time); return {"day_period":env["day_period"]["period"],"weather":env["weather"]["current_weather_type"],"temperature":env["temperature"],"sheltered":env["sheltered"],"precipitation":env["weather"].get("precipitation_intensity",0)}
    def quest_condition_context(self, room: dict[str, Any], world_time: int=720) -> dict[str, Any]:
        env=self.resolve_room_environment(room, world_time=world_time); return {"current_weather":env["weather"]["current_weather_type"],"season":self.resolve_season(world_time).get("id"),"day_period":env["day_period"]["period"],"light_class":env["light"]["light_class"],"sheltered":env["sheltered"]}
    def trace_weather(self, scope_type="world", scope_id="default") -> dict[str, Any]: return {"state":self.get_weather(scope_type,scope_id),"forecast":self.get_forecast(scope_type,scope_id),"validation":self.validate_content()}
    def trace_room_environment(self, room: dict[str, Any]) -> dict[str, Any]: return {"environment":self.resolve_room_environment(room),"visibility":self.evaluate_visibility("trace","room",room.get("id",""),room),"movement":self.movement_context(room),"combat":self.combat_context(room)}
