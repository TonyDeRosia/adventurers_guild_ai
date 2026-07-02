"""World package registry and MUD V2 room helpers."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

WORLDS_DIR = Path(__file__).resolve().parents[1] / "data" / "worlds"
REQUIRED_PLAYABLE_FILES = (
    "manifest.json", "world_bible.md", "rules/stats.json", "character/races.json", "character/classes.json",
    "abilities/spells.json", "abilities/skills.json", "abilities/passives.json", "items/weapons.json", "items/armor.json",
    "items/consumables.json", "items/tools.json", "items/misc.json", "map/areas.json", "map/rooms.json", "world/factions.json",
    "world/npcs.json", "world/quests.json",
)

class WorldRegistryError(ValueError):
    pass

def _read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise WorldRegistryError(f"World file not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorldRegistryError(f"Invalid JSON in {path}: {exc}") from exc

@dataclass(frozen=True)
class WorldPackage:
    root: Path
    manifest: dict[str, Any]
    world_bible: str
    rules: dict[str, Any]
    races: list[dict[str, Any]]
    classes: list[dict[str, Any]]
    backgrounds: list[dict[str, Any]]
    abilities: list[dict[str, Any]]
    items: list[dict[str, Any]]
    areas: list[dict[str, Any]]
    rooms: list[dict[str, Any]]
    factions: list[dict[str, Any]]
    npcs: list[dict[str, Any]]
    quests: list[dict[str, Any]]

    @property
    def id(self) -> str: return str(self.manifest["id"])
    @property
    def default_starting_room_id(self) -> str: return str(self.manifest.get("default_start_room", ""))
    @property
    def default_starting_room(self) -> dict[str, Any]:
        return self.room(self.default_starting_room_id)
    def room(self, room_id: str) -> dict[str, Any]:
        for room in self.rooms:
            if room.get("id") == room_id:
                return room
        raise WorldRegistryError(f"Room not found in {self.id}: {room_id}")
    def campaign_intelligence_source_dir(self) -> Path | None:
        path = self.root / "campaign_intelligence"
        return path if path.exists() else None

class WorldRegistry:
    def __init__(self, worlds_dir: Path | None = None) -> None:
        self.worlds_dir = worlds_dir or WORLDS_DIR
    def list_worlds(self) -> list[dict[str, Any]]:
        worlds = []
        for manifest_path in sorted(self.worlds_dir.glob("*/manifest.json")):
            worlds.append(_read_json(manifest_path))
        return worlds
    def validate_world(self, world_id: str) -> None:
        root = self.worlds_dir / world_id
        manifest = _read_json(root / "manifest.json")
        for field in ("id", "name", "genre", "description", "status", "default_start_room", "default_color_theme", "version"):
            if field not in manifest:
                raise WorldRegistryError(f"World manifest {world_id} missing {field}")
        if manifest.get("status") == "playable":
            missing = [rel for rel in REQUIRED_PLAYABLE_FILES if not (root / rel).exists()]
            if missing:
                raise WorldRegistryError(f"World {world_id} missing required file(s): {', '.join(missing)}")
    def load_world(self, world_id: str) -> WorldPackage:
        self.validate_world(world_id)
        root = self.worlds_dir / world_id
        manifest = _read_json(root / "manifest.json")
        rules = {name: _read_json(root / "rules" / f"{name}.json", {}) for name in ("stats", "combat", "magic", "progression")}
        abilities = []
        for name in ("spells", "skills", "passives"):
            abilities.extend(_read_json(root / "abilities" / f"{name}.json", []))
        items = []
        for name in ("weapons", "armor", "consumables", "tools", "misc"):
            items.extend(_read_json(root / "items" / f"{name}.json", []))
        return WorldPackage(root, manifest, (root / "world_bible.md").read_text(encoding="utf-8") if (root / "world_bible.md").exists() else "", rules,
            _read_json(root / "character/races.json", []), _read_json(root / "character/classes.json", []), _read_json(root / "character/backgrounds.json", []),
            abilities, items, _read_json(root / "map/areas.json", []), _read_json(root / "map/rooms.json", []),
            _read_json(root / "world/factions.json", []), _read_json(root / "world/npcs.json", []), _read_json(root / "world/quests.json", []))

def by_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(r.get("id")): r for r in records}
