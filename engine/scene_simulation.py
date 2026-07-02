"""Deterministic V1 scene simulation layer.

This module owns concrete scene objects for basic play commands before any
narration model is asked to improvise prose.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any

from engine.core_game import by_id, load_core_game

ENTITY_KINDS = {"npc", "object", "landmark", "exit", "hazard", "item", "creature", "vehicle", "structure"}


@dataclass
class SceneEntity:
    id: str
    name: str
    kind: str
    description: str
    visible: bool = True
    interactable: bool = True
    tags: list[str] = field(default_factory=list)
    state: dict[str, Any] = field(default_factory=dict)
    memory: list[str] = field(default_factory=list)


@dataclass
class SceneExit:
    direction: str
    destination_name: str
    description: str
    blocked: bool = False
    tags: list[str] = field(default_factory=list)


@dataclass
class SceneStateV1:
    location_id: str
    location_name: str
    summary: str
    atmosphere: str
    time_of_day: str = "day"
    weather: str = "clear"
    entities: list[SceneEntity] = field(default_factory=list)
    exits: list[SceneExit] = field(default_factory=list)
    active_hooks: list[str] = field(default_factory=list)
    recent_changes: list[str] = field(default_factory=list)


@dataclass
class SceneSimulationResult:
    intent: str
    handled: bool
    state_updates: dict[str, Any] = field(default_factory=dict)
    messages: list[str] = field(default_factory=list)
    created_entities: list[dict[str, Any]] = field(default_factory=list)
    changed_entities: list[dict[str, Any]] = field(default_factory=list)
    consequences: list[str] = field(default_factory=list)
    suggested_next_actions: list[str] = field(default_factory=list)
    debug: dict[str, Any] = field(default_factory=dict)


def to_dict(obj: Any) -> dict[str, Any]:
    return asdict(obj)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "scene"


def _entity_from_raw(raw: Any) -> SceneEntity | None:
    if isinstance(raw, SceneEntity):
        return raw
    if not isinstance(raw, dict):
        return None
    kind = _clean(raw.get("kind") or "object").lower()
    if kind not in ENTITY_KINDS:
        kind = "object"
    name = _clean(raw.get("name"))
    if not name:
        return None
    return SceneEntity(
        id=_clean(raw.get("id")) or _slug(name),
        name=name,
        kind=kind,
        description=_clean(raw.get("description")) or name,
        visible=bool(raw.get("visible", True)),
        interactable=bool(raw.get("interactable", True)),
        tags=[_clean(v).lower() for v in raw.get("tags", []) if _clean(v)],
        state=dict(raw.get("state", {})) if isinstance(raw.get("state", {}), dict) else {},
        memory=[_clean(v) for v in raw.get("memory", []) if _clean(v)],
    )


def _exit_from_raw(raw: Any) -> SceneExit | None:
    if isinstance(raw, SceneExit):
        return raw
    if not isinstance(raw, dict):
        return None
    direction = _clean(raw.get("direction"))
    destination = _clean(raw.get("destination_name"))
    if not direction or not destination:
        return None
    return SceneExit(direction, destination, _clean(raw.get("description")) or f"{direction} toward {destination}", bool(raw.get("blocked", False)), [_clean(v).lower() for v in raw.get("tags", []) if _clean(v)])


def normalize_scene_v1(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raw = {}
    location_name = _clean(raw.get("location_name")) or "Old Gate"
    scene = SceneStateV1(
        location_id=_clean(raw.get("location_id")) or _slug(location_name),
        location_name=location_name,
        summary=_clean(raw.get("summary")) or _clean(raw.get("scene_summary")) or f"You are at {location_name}.",
        atmosphere=_clean(raw.get("atmosphere")) or "uneasy, watchful, ready for change",
        time_of_day=_clean(raw.get("time_of_day")) or "day",
        weather=_clean(raw.get("weather")) or "clear",
        entities=[e for e in (_entity_from_raw(v) for v in raw.get("entities", [])) if e],
        exits=[e for e in (_exit_from_raw(v) for v in raw.get("exits", [])) if e],
        active_hooks=[_clean(v) for v in raw.get("active_hooks", []) if _clean(v)],
        recent_changes=[_clean(v) for v in raw.get("recent_changes", []) if _clean(v)],
    )
    return asdict(scene)



def initialize_scene_v1_from_core_game(starting_zone_id: str = "guildhall_crossing") -> dict[str, Any]:
    core = load_core_game()
    zones = by_id(core["zones"])
    npcs = by_id(core["npcs"])
    zone = zones.get(starting_zone_id) or zones[core["manifest"].get("starting_zone", "guildhall_crossing")]
    entities: list[SceneEntity] = []
    for npc_id in zone.get("npcs", []):
        npc = npcs.get(npc_id)
        if npc:
            entities.append(SceneEntity(npc["id"], npc["name"], "npc", npc["description"], True, True, list(npc.get("tags", [])) + [npc.get("faction_id", "")], {"dialogue": npc.get("dialogue_seed", "")}))
    for obj in zone.get("objects", []):
        entities.append(SceneEntity(_slug(obj), str(obj).replace("_", " ").title(), "object", f"A notable feature of {zone['name']}.", True, True, [_slug(obj)]))
    scene = SceneStateV1(
        location_id=zone["id"],
        location_name=zone["name"],
        summary=zone["summary"],
        atmosphere=zone["atmosphere"],
        entities=entities,
        exits=[_exit_from_raw(ex) for ex in zone.get("exits", []) if _exit_from_raw(ex)],
        active_hooks=list(zone.get("active_hooks", [])),
    )
    return asdict(scene)

def initialize_scene_v1_from_campaign(state: Any) -> dict[str, Any]:
    meta = getattr(state, "world_meta", None)
    requested_world = _clean(getattr(meta, "world_name", ""))
    requested_location = _clean(getattr(meta, "starting_location_name", ""))
    if (not requested_world or requested_world == "The Shattered Realms") and (not requested_location or requested_location == "Guildhall Crossing"):
        return initialize_scene_v1_from_core_game("guildhall_crossing")
    location = getattr(state, "locations", {}).get(getattr(state, "current_location_id", "")) if isinstance(getattr(state, "locations", {}), dict) else None
    location_name = _clean(getattr(meta, "starting_location_name", "")) or _clean(getattr(location, "name", "")) or "Old Gate"
    if location_name.lower() in {"starting area", "arrival threshold"}:
        location_name = "Old Gate"
    world = _clean(getattr(meta, "world_name", "")) or "the realm"
    theme = _clean(getattr(meta, "world_theme", "")) or "classic fantasy"
    premise = _clean(getattr(meta, "premise", "")) or "urgent news is moving faster than rumor"
    role = _clean(getattr(getattr(state, "player", None), "char_class", "")) or "adventurer"
    hook = f"{premise[:140]}" if premise else f"A {role} is needed before the news reaches {world}."
    old_gate_desc = f"{location_name}, a weathered threshold of pale stone marked by old scorch marks and traveler sigils."
    current_location_id = _clean(getattr(state, "current_location_id", "")) or _slug(location_name)
    existing_npc_entities = []
    npcs = getattr(state, "npcs", {})
    if isinstance(npcs, dict):
        for npc_id, npc in npcs.items():
            if _clean(getattr(npc, "location_id", "")) == current_location_id and _clean(getattr(npc, "name", "")):
                existing_npc_entities.append(SceneEntity(_clean(getattr(npc, "id", npc_id)) or _slug(getattr(npc, "name", "npc")), _clean(getattr(npc, "name", "NPC")), "npc", f"{_clean(getattr(npc, 'name', 'Someone'))} is present and watching the scene.", True, True, [_slug(_clean(getattr(npc, "name", "npc"))).replace("_", " "), "local"], {"dialogue": "I can tell you what has been happening here."}))
    scene = SceneStateV1(
        location_id=current_location_id,
        location_name=location_name,
        summary=f"You stand at {location_name} in {world}. Theme: {theme}.",
        atmosphere="uneasy, old stone, travelers whispering",
        entities=existing_npc_entities + [
            SceneEntity(_slug(location_name), location_name, "landmark", old_gate_desc, True, True, ["gate", "landmark", "stone"]),
            SceneEntity("local_messenger", "Local Messenger", "npc", "A road-worn messenger clutches urgent news and scans each traveler with anxious eyes.", True, True, ["messenger", "news", "courier"], {"dialogue": f"Something is wrong: {hook}", "mood": "urgent"}),
            SceneEntity("sealed_notice", "Sealed Notice", "object", f"A sealed notice marked for anyone brave enough to act: {hook}", True, True, ["notice", "news", "scroll", "sealed", "readable"], {"text": f"Urgent notice: {hook}"}),
            SceneEntity("wary_travelers", "Wary Travelers", "npc", "A small knot of travelers linger nearby, trading low warnings and watching the road.", True, True, ["travelers", "group", "witness"], {"dialogue": "The road has felt wrong since dawn. Ask the messenger; they know more."}),
        ],
        exits=[
            SceneExit("north", "North Road", "The north road leads toward open country and whatever trouble the notice names.", False, ["road", "north"]),
            SceneExit("east", "Village Path", "A narrow village path bends east toward roofs, smoke, and possible answers.", False, ["village", "path", "east"]),
        ],
        active_hooks=[hook],
    )
    return asdict(scene)


def ensure_scene_v1(state: Any) -> dict[str, Any]:
    runtime = state.structured_state.runtime
    scene_state = runtime.scene_state if isinstance(runtime.scene_state, dict) else {}
    existing = scene_state.get("scene_v1") if isinstance(scene_state.get("scene_v1"), dict) else None
    if existing and existing.get("entities"):
        scene_state["scene_v1"] = normalize_scene_v1(existing)
    else:
        scene_state["scene_v1"] = initialize_scene_v1_from_campaign(state)
    runtime.scene_state = scene_state
    return scene_state["scene_v1"]


def _visible_entities(scene: dict[str, Any]) -> list[dict[str, Any]]:
    return [e for e in scene.get("entities", []) if isinstance(e, dict) and e.get("visible", True)]


def _match_entity(text: str, scene: dict[str, Any]) -> dict[str, Any] | None:
    q = text.lower()
    stop = {"read", "the", "a", "an", "examine", "inspect", "look", "at", "talk", "to", "ask", "speak", "with", "what", "happened"}
    tokens = [t for t in re.findall(r"[a-z0-9]+", q) if t not in stop]
    candidates = _visible_entities(scene)
    if any(word in q for word in ("read", "notice", "news", "scroll")):
        candidates = sorted(candidates, key=lambda e: 0 if e.get("kind") in {"object", "item"} else 1)
    for e in candidates:
        hay = " ".join([str(e.get("name", "")), str(e.get("kind", "")), " ".join(e.get("tags", []))]).lower()
        if any(t in hay for t in tokens):
            return e
    return None


def _available(scene: dict[str, Any]) -> str:
    names = [e.get("name", "") for e in _visible_entities(scene) if e.get("interactable", True)]
    return ", ".join(names) if names else "nothing obvious"


def _look(scene: dict[str, Any]) -> str:
    return render_scene_result(SceneSimulationResult(intent="look", handled=True), scene)



def get_visible_scene_entities(state: Any) -> list[dict[str, Any]]:
    scene = ensure_scene_v1(state) if not isinstance(state, dict) else normalize_scene_v1(state)
    entities = _visible_entities(scene)
    for ex in scene.get("exits", []):
        if isinstance(ex, dict) and not ex.get("blocked", False):
            entities.append({"id": f"exit_{ex.get('direction')}", "name": f"{ex.get('direction')} to {ex.get('destination_name')}", "kind": "exit", "description": ex.get("description", ""), "visible": True, "interactable": True})
    return entities

def get_visible_npcs(state: Any) -> list[dict[str, Any]]:
    return [e for e in get_visible_scene_entities(state) if e.get("kind") in {"npc", "creature"}]

def get_visible_objects(state: Any) -> list[dict[str, Any]]:
    return [e for e in get_visible_scene_entities(state) if e.get("kind") in {"object", "item", "landmark", "hazard", "vehicle", "structure", "exit"}]

def get_scene_entity_counts(state: Any) -> dict[str, int]:
    ents = get_visible_scene_entities(state)
    return {"npc_count": len([e for e in ents if e.get("kind") in {"npc", "creature"}]), "visible_count": len(ents), "object_count": len([e for e in ents if e.get("kind") not in {"npc", "creature"}])}

def summarize_scene_for_prompt(state: Any) -> str:
    scene = ensure_scene_v1(state) if not isinstance(state, dict) else normalize_scene_v1(state)
    names = ", ".join(e.get("name", "") for e in _visible_entities(scene) if e.get("name"))
    exits = ", ".join(f"{e.get('direction')} to {e.get('destination_name')}" for e in scene.get("exits", []) if isinstance(e, dict) and not e.get("blocked", False))
    return f"{scene.get('location_name')}: {scene.get('summary')} Visible: {names or 'none'}. Exits: {exits or 'none'}. Hooks: {', '.join(scene.get('active_hooks', [])) or 'none'}."

def _sentence(text: str) -> str:
    text = _clean(text)
    return text if text.endswith(('.', '!', '?')) else text + '.'

def render_scene_result(result: SceneSimulationResult, scene_v1: dict[str, Any], style: str = "storybook") -> str:
    scene = normalize_scene_v1(scene_v1)
    loc = scene.get("location_name", "the scene")
    ents = _visible_entities(scene)
    landmark = next((e for e in ents if e.get("kind") in {"landmark", "structure"}), None)
    npcs = [e for e in ents if e.get("kind") == "npc"]
    objects = [e for e in ents if e.get("kind") in {"object", "item", "hazard"}]
    parts = [f"You stand before {loc}."]
    if landmark: parts = [_sentence(str(landmark.get("description") or f"You stand before {loc}"))]
    for e in npcs[:3] + objects[:2]:
        desc = str(e.get("description") or e.get("name"))
        name = str(e.get("name") or "").strip()
        if name and name not in desc:
            desc = f"{name}: {desc}"
        parts.append(_sentence(desc))
    exits = [_clean(e.get("description")) for e in scene.get("exits", []) if isinstance(e, dict) and not e.get("blocked", False)]
    if exits: parts.append(_sentence(" ".join(exits)))
    if scene.get("active_hooks"):
        parts.append(_sentence("Hook: " + str(scene.get("active_hooks", [""])[0])))
    return " ".join(parts).strip() + " What do you do?"

def _targeted_entity(lower: str, scene: dict[str, Any]) -> dict[str, Any] | None:
    stop = {"i", "me", "my", "the", "a", "an", "on", "at", "to", "with", "ground", "toe", "toes"}
    tokens = [token for token in re.findall(r"[a-z0-9]+", lower) if token not in stop and len(token) >= 3]
    for ent in _visible_entities(scene):
        hay = " ".join([str(ent.get("name", "")), " ".join(ent.get("tags", []))]).lower()
        if hay and any(token in hay for token in tokens):
            return ent
    return None


def _bump_npc_state(entity: dict[str, Any], *, suspicion: int = 0, discomfort: int = 0, anger: int = 0, memory: str = "") -> None:
    state = entity.setdefault("state", {}) if isinstance(entity.get("state", {}), dict) else {}
    entity["state"] = state
    state["suspicion"] = int(state.get("suspicion", 0) or 0) + suspicion
    state["discomfort"] = int(state.get("discomfort", 0) or 0) + discomfort
    state["anger"] = int(state.get("anger", 0) or 0) + anger
    if memory:
        entity.setdefault("memory", []).append(memory)


def resolve_generic_action(text: str, scene_v1: dict[str, Any], character: Any = None, settings: Any = None) -> SceneSimulationResult:
    scene = normalize_scene_v1(scene_v1)
    raw = _clean(text) or "do something"
    lower = raw.lower()
    name = _clean(getattr(character, "name", "")) or "You"
    loc = scene.get("location_name", "nearby")
    npcs = [e for e in _visible_entities(scene) if e.get("kind") == "npc"]
    messenger = next((e for e in npcs if "messenger" in str(e.get("name","")).lower()), None)
    travelers = next((e for e in npcs if "traveler" in str(e.get("name","")).lower()), None)
    target = _targeted_entity(lower, scene)
    target_is_npc = bool(target and target.get("kind") == "npc")
    target_name = str(target.get("name")) if target else ""
    action_type = "generic"
    consequences: list[str] = [f"Attempted action: {raw}"]

    if "twiddle" in lower:
        action_type = "idle"
        narration = f"{name} waits at {loc}, quietly twiddling thumbs while the roadside tension continues without interruption."
    elif "spit" in lower and target_is_npc:
        action_type = "hostile_contact"
        _bump_npc_state(target, suspicion=1, discomfort=2, anger=3, memory=f"The player spat on {target_name}.")
        anger = int(target.get("state", {}).get("anger", 0) or 0)
        narration = f"{name} spits on {target_name}. {target_name} recoils, anger flashing across their face."
        narration += " They call for guards and square up for a confrontation." if anger >= 6 else " They give a sharp warning that the next insult will bring consequences."
        consequences.append(f"Hostile contact against {target_name}")
    elif "lick" in lower and target_is_npc:
        action_type = "unwanted_contact"
        _bump_npc_state(target, suspicion=1, discomfort=3, anger=2, memory=f"The player licked {target_name} without consent.")
        anger = int(target.get("state", {}).get("anger", 0) or 0)
        narration = f"{name} leans in and licks {target_name}. {target_name} jerks back, visibly disgusted by the unwanted contact."
        narration += " Their voice rises as they demand help and the situation turns confrontational." if anger >= 4 else " They back away and warn you not to touch them again."
        consequences.append(f"Unwanted contact with {target_name}")
    elif "spit" in lower:
        action_type = "rude_minor"
        narration = f"{name} spits on the ground at {loc}. It is rude enough to earn frowns, but it does not stop the scene."
        if travelers: _bump_npc_state(travelers, suspicion=1, discomfort=1, memory="The player spat on the ground nearby.")
    elif "lick" in lower and any(w in lower for w in ("toe", "toes", "myself", "hand", "finger")):
        action_type = "self_directed_odd"
        narration = f"{name} bends into an awkward self-directed act, licking their own toes. Nearby onlookers stare, unsure what to make of it."
        if messenger: _bump_npc_state(messenger, suspicion=1, discomfort=1, memory="The player behaved bizarrely by licking their own toes.")
    elif any(w in lower for w in ("dance", "strip", "naked")):
        action_type = "bizarre_social"
        narration = f"{name} makes a spectacle at {loc}, dancing naked enough to draw every nearby eye and embarrassed whispers."
        if messenger: _bump_npc_state(messenger, suspicion=1, discomfort=2, memory="The player caused a naked public spectacle.")
        consequences.append("Public indecency draws social consequences")
    elif any(w in lower for w in ("insult", "curse", "mock")) or "spit" in lower:
        action_type = "insulting"
        narration = f"{name}'s insult cuts through {loc}; the mood cools as people wait to see whether it becomes a fight."
    elif any(w in lower for w in ("wave", "shout", "whistle", "talk")):
        action_type = "social"
        narration = f"{name} makes a clear social overture at {loc}; heads turn, waiting for who answers."
    else:
        narration = f"{name} tries to {raw}. The action lands plainly in the scene without becoming a stock gesture."

    if action_type in {"self_directed_odd", "bizarre_social"} and messenger:
        discomfort = int(messenger.get("state", {}).get("discomfort", 0) or 0)
        narration += " The messenger backs away and keeps the sealed notice between you." if discomfort >= 2 else " The messenger stares while travelers begin whispering."
    elif action_type not in {"idle", "hostile_contact", "unwanted_contact"}:
        if travelers: narration += " The wary travelers watch more closely."
        if messenger: narration += " The local messenger clutches the sealed notice tighter."
    narration += " What do you do?"
    scene["recent_changes"] = (scene.get("recent_changes", []) + [f"Generic action ({action_type}): {raw}"])[-6:]
    return SceneSimulationResult(intent="generic_action", handled=True, state_updates={"scene_v1": scene}, messages=[narration], changed_entities=scene.get("entities", []), consequences=consequences, suggested_next_actions=["look around", "talk to messenger"], debug={"handled_by": "scene_v1_generic", "action_type": action_type, "target": target_name})

def resolve_scene_action(text: str, scene_v1: dict[str, Any]) -> SceneSimulationResult:
    scene = normalize_scene_v1(scene_v1)
    raw = _clean(text)
    lower = raw.lower().strip(" .!?\n\t")
    intent = "unknown"
    messages: list[str] = []
    consequences: list[str] = []
    if re.fullmatch(r"(i )?(look|look around|observe|examine surroundings|survey the area|what do i see)", lower):
        intent = "look"; messages.append(_look(scene))
    elif lower.startswith(("read", "examine", "inspect", "look at")):
        intent = "examine"; ent = _match_entity(lower, scene)
        if ent:
            text_value = ent.get("state", {}).get("text") or ent.get("state", {}).get("dialogue") or ent.get("description")
            messages.append(f"You study {ent.get('name')}. {text_value}")
        else:
            messages.append(f"You do not see that here. Available things to examine: {_available(scene)}.")
    elif lower.startswith(("talk", "ask", "speak")):
        intent = "talk"; ent = _match_entity(lower, scene)
        npcs = [e for e in _visible_entities(scene) if e.get("kind") == "npc"]
        if ent and ent.get("kind") == "npc":
            line = ent.get("state", {}).get("dialogue") or (scene.get("active_hooks") or ["There is trouble nearby."])[0]
            messages.append(f"{ent.get('name')} says, “{line}”")
            ent.setdefault("memory", []).append(f"Spoke with the player about {line}")
            consequences.append(f"Spoke with {ent.get('name')}")
        else:
            messages.append("Who are you speaking to? Visible NPCs: " + (", ".join(e.get("name", "") for e in npcs) if npcs else "none") + ".")
    elif lower.startswith(("go ", "take ", "enter ", "follow ", "move ")):
        intent = "move"
        for ex in scene.get("exits", []):
            hay = " ".join([str(ex.get("direction", "")), str(ex.get("destination_name", "")), " ".join(ex.get("tags", []))]).lower()
            if any(t and t in hay for t in re.findall(r"[a-z0-9]+", lower)):
                if ex.get("blocked"):
                    messages.append(f"The way to {ex.get('destination_name')} is blocked. {ex.get('description')}")
                else:
                    dest = str(ex.get("destination_name"))
                    scene["location_name"] = dest; scene["location_id"] = _slug(dest); scene["summary"] = f"You have moved to {dest}."; scene["atmosphere"] = "watchful and newly unsettled"
                    scene["recent_changes"] = (scene.get("recent_changes", []) + [f"Moved to {dest}"])[-6:]
                    messages.append(f"You follow {ex.get('description')} You arrive at {dest}. What do you do?")
                break
        if not messages:
            messages.append("You do not see that route. Available exits: " + ", ".join(f"{e.get('direction')} to {e.get('destination_name')}" for e in scene.get("exits", [])) + ".")
    elif lower in {"wait", "rest", "listen", "i wait", "i listen"}:
        intent = "wait"; change = "The messenger shifts nervously as travelers lower their voices."
        scene["recent_changes"] = (scene.get("recent_changes", []) + [change])[-6:]
        messages.append(change + " The scene holds, but the urgency grows.")
    else:
        return resolve_generic_action(raw, scene)
    return SceneSimulationResult(intent=intent, handled=True, state_updates={"scene_v1": scene}, messages=messages, changed_entities=scene.get("entities", []), consequences=consequences, suggested_next_actions=["look around", "read notice", "talk to messenger", "go north"], debug={"handled_by": "scene_v1"})
