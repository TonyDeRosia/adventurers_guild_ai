"""World package discovery, validation, and loading for Smart MUD."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORLDS_DIR = PROJECT_ROOT / "worlds"

REQUIRED_RUNTIME_DIRS = (
    "rules", "areas", "rooms", "zones", "npcs", "items", "quests", "shops",
    "trainers", "classes", "races", "skills", "spells", "abilities", "factions",
    "lore", "dialogue", "intelligence", "colors",
)
REQUIRED_BUILDER_DIRS = ("audit", "history", "snapshots", "imports", "exports", "templates")
REQUIRED_WORLD_DIRS = REQUIRED_RUNTIME_DIRS  # Backward-compatible alias for runtime-required content.
REQUIRED_MANIFEST_FIELDS = (
    "world_id", "display_name", "author", "description", "version",
    "engine_version_required", "minimum_engine_version", "maximum_engine_version",
    "dependencies", "required_plugins", "optional_plugins", "world_type",
    "default_starting_area", "default_starting_room", "supported_languages",
    "supported_character_slots", "builder", "load_priority", "package_guid",
)

class WorldRegistryError(ValueError):
    pass

class WorldValidationError(WorldRegistryError):
    def __init__(self, world_id: str, errors: list[str]) -> None:
        super().__init__(f"World {world_id} failed validation:\n- " + "\n- ".join(errors))
        self.world_id = world_id
        self.errors = errors

def _read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise WorldRegistryError(f"World file not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorldRegistryError(f"Invalid JSON in {path}: {exc}") from exc

def _records(root: Path, dirname: str) -> list[dict[str, Any]]:
    path = root / dirname
    out: list[dict[str, Any]] = []
    for json_path in sorted(path.glob("*.json")):
        data = _read_json(json_path, [])
        if isinstance(data, list):
            out.extend(x for x in data if isinstance(x, dict))
        elif isinstance(data, dict):
            values = data.get(dirname) or data.get("records")
            if isinstance(values, list):
                out.extend(x for x in values if isinstance(x, dict))
            else:
                out.append(data)
    return out

def by_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(r.get("id")): r for r in records if r.get("id")}

@dataclass(frozen=True)
class WorldPackage:
    root: Path
    manifest: dict[str, Any]
    rules: dict[str, Any]
    races: list[dict[str, Any]]
    classes: list[dict[str, Any]]
    abilities: list[dict[str, Any]]
    skills: list[dict[str, Any]]
    spells: list[dict[str, Any]]
    items: list[dict[str, Any]]
    areas: list[dict[str, Any]]
    rooms: list[dict[str, Any]]
    zones: list[dict[str, Any]]
    factions: list[dict[str, Any]]
    npcs: list[dict[str, Any]]
    quests: list[dict[str, Any]]
    shops: list[dict[str, Any]]
    trainers: list[dict[str, Any]]
    lore: list[dict[str, Any]]
    dialogue: list[dict[str, Any]]
    intelligence: dict[str, str]

    @property
    def id(self) -> str: return str(self.manifest["world_id"])
    @property
    def default_starting_room_id(self) -> str: return str(self.manifest.get("default_starting_room", ""))
    @property
    def default_starting_room(self) -> dict[str, Any]: return self.room(self.default_starting_room_id)
    def room(self, room_id: str) -> dict[str, Any]:
        for room in self.rooms:
            if room.get("id") == room_id:
                return room
        raise WorldRegistryError(f"Room not found in {self.id}: {room_id}")
    def world_intelligence_source_dir(self) -> Path | None:
        path = self.root / "intelligence"
        return path if path.exists() else None
    def campaign_intelligence_source_dir(self) -> Path | None:
        return None

class WorldRegistry:
    def __init__(self, worlds_dir: Path | None = None) -> None:
        self.worlds_dir = worlds_dir or WORLDS_DIR
        self.worlds_dir.mkdir(parents=True, exist_ok=True)

    def list_worlds(self) -> list[dict[str, Any]]:
        worlds = []
        seen: set[str] = set()
        for manifest_path in sorted(self.worlds_dir.glob("*/manifest.json")):
            manifest = _read_json(manifest_path)
            world_id = str(manifest.get("world_id") or manifest.get("id") or manifest_path.parent.name)
            if world_id in seen:
                raise WorldRegistryError(f"Duplicate world id: {world_id}")
            seen.add(world_id)
            worlds.append(self._public_manifest(manifest, world_id))
        return sorted(worlds, key=lambda m: (int(m.get("load_priority", 100)), str(m.get("id"))))

    def prepare_builder_workspace(self, world_id: str) -> list[Path]:
        """Create non-gameplay Builder workspace folders without affecting validation."""
        root = self.worlds_dir / world_id
        created: list[Path] = []
        for directory in (root / "builder", *(root / "builder" / dirname for dirname in REQUIRED_BUILDER_DIRS)):
            if not directory.exists():
                directory.mkdir(parents=True, exist_ok=True)
                created.append(directory)
        return created

    def validate_world(self, world_id: str) -> None:
        root = self.worlds_dir / world_id
        manifest = self._manifest(root)
        actual_id = str(manifest.get("world_id", world_id))
        errors: list[str] = []
        self.prepare_builder_workspace(world_id)
        for dirname in REQUIRED_RUNTIME_DIRS:
            if not (root / dirname).is_dir():
                errors.append(f"Missing required runtime folder: {dirname}/")
        for field in REQUIRED_MANIFEST_FIELDS:
            if field not in manifest:
                errors.append(f"Manifest missing required field: {field}")
        rooms = by_id(_records(root, "rooms")); npcs = by_id(_records(root, "npcs")); items = by_id(_records(root, "items"))
        quests = by_id(_records(root, "quests")); classes = by_id(_records(root, "classes")); abilities = by_id(_records(root, "abilities"))
        races = by_id(_records(root, "races")); spells = by_id(_records(root, "spells")); skills = by_id(_records(root, "skills"))
        for label, records in (("room", rooms), ("NPC", npcs), ("item", items), ("quest", quests), ("class", classes), ("race", races)):
            if "" in records:
                errors.append(f"A {label} record is missing an id")
        start_room = manifest.get("default_starting_room")
        if start_room and str(start_room) not in rooms:
            errors.append(f"Default starting room references missing room: {start_room}")
        for room in rooms.values():
            for exit_data in room.get("exits", []) or []:
                target = exit_data.get("to") or exit_data.get("room_id") or exit_data.get("target")
                if target and str(target) not in rooms:
                    errors.append(f"Room {room.get('id')} exit references missing room: {target}")
            for npc_id in room.get("npcs", []) or []:
                if str(npc_id) not in npcs:
                    errors.append(f"Room {room.get('id')} references missing NPC: {npc_id}")
        for npc in npcs.values():
            for room_id in npc.get("rooms", []) or ([npc.get("room_id")] if npc.get("room_id") else []):
                if str(room_id) not in rooms:
                    errors.append(f"NPC {npc.get('id')} references missing room: {room_id}")
        for item in items.values():
            template = item.get("template_id")
            if template and str(template) not in items:
                errors.append(f"Item {item.get('id')} references missing template: {template}")
        for quest in quests.values():
            for npc_id in quest.get("npc_ids", []) or ([] if not quest.get("npc_id") else [quest.get("npc_id")]):
                if str(npc_id) not in npcs:
                    errors.append(f"Quest {quest.get('id')} references missing NPC: {npc_id}")
        for trainer in _records(root, "trainers"):
            for class_id in trainer.get("class_ids", []) or ([] if not trainer.get("class_id") else [trainer.get("class_id")]):
                if str(class_id) not in classes:
                    errors.append(f"Trainer {trainer.get('id')} references missing class: {class_id}")
        schools = {str(s.get("id")) for s in _records(root / "rules", "spell_schools")} | {str(s.get("school")) for s in spells.values() if s.get("school")}
        for spell in spells.values():
            school = spell.get("school")
            if school and str(school) not in schools:
                errors.append(f"Spell {spell.get('id')} references missing school: {school}")
        for cls in classes.values():
            for ability_id in cls.get("ability_ids", []) or []:
                if str(ability_id) not in abilities and str(ability_id) not in skills and str(ability_id) not in spells:
                    errors.append(f"Class {cls.get('id')} references missing ability: {ability_id}")
        for race in races.values():
            if not isinstance(race, dict) or not race.get("id"):
                errors.append("Race record has invalid data")
        if errors:
            raise WorldValidationError(actual_id, errors)

    def load_world(self, world_id: str) -> WorldPackage:
        self.validate_world(world_id)
        root = self.worlds_dir / world_id
        manifest = self._manifest(root)
        rules = {p.stem: _read_json(p, {}) for p in sorted((root / "rules").glob("*.json"))}
        intelligence = {p.stem: p.read_text(encoding="utf-8") for p in sorted((root / "intelligence").glob("*.md"))}
        return WorldPackage(root, manifest, rules, _records(root,"races"), _records(root,"classes"), _records(root,"abilities"), _records(root,"skills"), _records(root,"spells"), _records(root,"items"), _records(root,"areas"), _records(root,"rooms"), _records(root,"zones"), _records(root,"factions"), _records(root,"npcs"), _records(root,"quests"), _records(root,"shops"), _records(root,"trainers"), _records(root,"lore"), _records(root,"dialogue"), intelligence)

    def reload_room(self, world: WorldPackage, room_id: str) -> dict[str, Any]:
        return self.load_world(world.id).room(room_id)
    def reload_npc(self, world: WorldPackage, npc_id: str) -> dict[str, Any]:
        return by_id(self.load_world(world.id).npcs)[npc_id]
    def reload_area(self, world: WorldPackage, area_id: str) -> dict[str, Any]:
        return by_id(self.load_world(world.id).areas)[area_id]
    def reload_quest(self, world: WorldPackage, quest_id: str) -> dict[str, Any]:
        return by_id(self.load_world(world.id).quests)[quest_id]
    def reload_item(self, world: WorldPackage, item_id: str) -> dict[str, Any]:
        return by_id(self.load_world(world.id).items)[item_id]

    def _manifest(self, root: Path) -> dict[str, Any]:
        return _read_json(root / "manifest.json")
    def _public_manifest(self, manifest: dict[str, Any], world_id: str) -> dict[str, Any]:
        return {
            "id": world_id,
            "world_id": world_id,
            "name": manifest.get("display_name") or manifest.get("name") or world_id,
            "display_name": manifest.get("display_name") or manifest.get("name") or world_id,
            "description": manifest.get("description", ""),
            "version": manifest.get("version", ""),
            "world_type": manifest.get("world_type") or manifest.get("genre", ""),
            "default_start_room": manifest.get("default_starting_room") or manifest.get("default_start_room", ""),
            "load_priority": manifest.get("load_priority", 100),
        }
