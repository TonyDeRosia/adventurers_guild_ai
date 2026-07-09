"""Smart MUD runtime layer - primary application runtime."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Optional
from datetime import datetime, timezone

from engine.mud_commands import MudCommandEngine
from engine.mud_displays import render_prompt, render_room
from smart_mud.world_registry import WorldRegistry
from engine.plugin_system import HookRegistry, PluginRegistry


@dataclass
class MudCharacter:
    """Runtime character state in MUD."""
    id: str
    name: str
    role: str  # "player", "helper", "builder", "admin", "implementor"
    immortal_level: int = 0  # 0=player, 1-50=immortal
    room_id: str = ""
    hp: int = 100
    max_hp: int = 100
    mana: int = 50
    max_mana: int = 50
    stamina: int = 100
    max_stamina: int = 100
    xp: int = 0
    level: int = 1
    gold: int = 0
    inventory: list[dict[str, Any]] = field(default_factory=list)
    equipment: dict[str, Any] = field(default_factory=dict)
    abilities: list[str] = field(default_factory=list)
    affects: dict[str, Any] = field(default_factory=dict)
    last_input: str = ""
    last_input_time: str = ""


@dataclass
class MudRoom:
    """Runtime room state in MUD."""
    id: str
    area_id: str
    title: str
    description: str
    exits: list[dict[str, str]] = field(default_factory=list)
    npcs: list[str] = field(default_factory=list)
    objects: list[dict[str, Any]] = field(default_factory=list)
    ambient_text: str = ""


@dataclass
class MudSession:
    """Active MUD session for a connected character."""
    session_id: str
    character_id: str
    world_id: str
    connected_at: str
    last_activity: str
    command_count: int = 0


class MudStateStore:
    """SQLite persistence for MUD runtime state."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_schema()

    def _init_schema(self) -> None:
        """Initialize SQLite schema for MUD persistence."""
        with sqlite3.connect(self.db_path) as conn:
            # Characters
            conn.execute("""
                CREATE TABLE IF NOT EXISTS characters (
                    id TEXT PRIMARY KEY,
                    world_id TEXT,
                    name TEXT,
                    role TEXT,
                    immortal_level INTEGER,
                    data JSON,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Character stats (denormalized for performance)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS character_stats (
                    id INTEGER PRIMARY KEY,
                    character_id TEXT UNIQUE,
                    hp INTEGER,
                    max_hp INTEGER,
                    mana INTEGER,
                    max_mana INTEGER,
                    stamina INTEGER,
                    max_stamina INTEGER,
                    xp INTEGER,
                    level INTEGER,
                    gold INTEGER,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(character_id) REFERENCES characters(id)
                )
            """)
            
            # Inventory
            conn.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    id INTEGER PRIMARY KEY,
                    character_id TEXT,
                    item_id TEXT,
                    item_data JSON,
                    quantity INTEGER DEFAULT 1,
                    FOREIGN KEY(character_id) REFERENCES characters(id)
                )
            """)
            
            # Command history
            conn.execute("""
                CREATE TABLE IF NOT EXISTS command_history (
                    id INTEGER PRIMARY KEY,
                    character_id TEXT,
                    world_id TEXT,
                    turn INTEGER,
                    command TEXT,
                    executed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(character_id) REFERENCES characters(id)
                )
            """)
            
            # Scrollback (recent output)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scrollback (
                    id INTEGER PRIMARY KEY,
                    character_id TEXT,
                    world_id TEXT,
                    turn INTEGER,
                    output TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(character_id) REFERENCES characters(id)
                )
            """)
            
            # Room runtime state
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rooms_runtime (
                    id TEXT PRIMARY KEY,
                    world_id TEXT,
                    area_id TEXT,
                    data JSON,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # NPC runtime state
            conn.execute("""
                CREATE TABLE IF NOT EXISTS npc_runtime (
                    id TEXT PRIMARY KEY,
                    world_id TEXT,
                    room_id TEXT,
                    data JSON,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # NPC relationships
            conn.execute("""
                CREATE TABLE IF NOT EXISTS npc_relationships (
                    id INTEGER PRIMARY KEY,
                    npc_id TEXT,
                    character_id TEXT,
                    relationship_type TEXT,
                    value INTEGER,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Builder audit log
            conn.execute("""
                CREATE TABLE IF NOT EXISTS builder_audit_log (
                    id INTEGER PRIMARY KEY,
                    builder_id TEXT,
                    action TEXT,
                    target_type TEXT,
                    target_id TEXT,
                    details JSON,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Quest runtime
            conn.execute("""
                CREATE TABLE IF NOT EXISTS quests_runtime (
                    id TEXT PRIMARY KEY,
                    character_id TEXT,
                    world_id TEXT,
                    status TEXT,
                    progress JSON,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Death log
            conn.execute("""
                CREATE TABLE IF NOT EXISTS death_log (
                    id INTEGER PRIMARY KEY,
                    character_id TEXT,
                    world_id TEXT,
                    died_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    killer TEXT,
                    location_id TEXT,
                    notes TEXT
                )
            """)
            
            conn.commit()

    def save_character(self, char: MudCharacter, world_id: str) -> None:
        """Save character to SQLite."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO characters 
                   (id, world_id, name, role, immortal_level, data, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (char.id, world_id, char.name, char.role, char.immortal_level, 
                 json.dumps(asdict(char)))
            )
            conn.execute(
                """INSERT OR REPLACE INTO character_stats
                   (character_id, hp, max_hp, mana, max_mana, stamina, max_stamina, xp, level, gold, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (char.id, char.hp, char.max_hp, char.mana, char.max_mana, 
                 char.stamina, char.max_stamina, char.xp, char.level, char.gold)
            )
            conn.commit()
        print(f"[mud-persistence] Saved character {char.name} ({char.id})")

    def load_character(self, char_id: str) -> Optional[MudCharacter]:
        """Load character from SQLite."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT data FROM characters WHERE id = ?",
                (char_id,)
            ).fetchone()
            if row:
                data = json.loads(row[0])
                print(f"[mud-persistence] Loaded character {data.get('name')} ({char_id})")
                return MudCharacter(**data)
        return None

    def save_command(self, char_id: str, world_id: str, turn: int, command: str) -> None:
        """Save command to history (SQLite only, not campaign-memory)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO command_history (character_id, world_id, turn, command)
                   VALUES (?, ?, ?, ?)""",
                (char_id, world_id, turn, command)
            )
            conn.commit()
        print(f"[mud-persistence] Command history: {command}")

    def save_scrollback(self, char_id: str, world_id: str, turn: int, output: str) -> None:
        """Save output to scrollback."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO scrollback (character_id, world_id, turn, output)
                   VALUES (?, ?, ?, ?)""",
                (char_id, world_id, turn, output)
            )
            # Keep only recent scrollback
            conn.execute(
                """DELETE FROM scrollback WHERE character_id = ? AND id NOT IN
                   (SELECT id FROM scrollback WHERE character_id = ? ORDER BY id DESC LIMIT 1000)""",
                (char_id, char_id)
            )
            conn.commit()

    def audit_builder_action(self, builder_id: str, action: str, target_type: str, 
                            target_id: str, details: dict) -> None:
        """Log builder/admin actions for audit trail."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO builder_audit_log 
                   (builder_id, action, target_type, target_id, details)
                   VALUES (?, ?, ?, ?, ?)""",
                (builder_id, action, target_type, target_id, json.dumps(details))
            )
            conn.commit()
        print(f"[mud-builder] Audit: {builder_id} {action} {target_type}:{target_id}")


class MudRuntime:
    """Primary Smart MUD application runtime."""

    def __init__(self, root: Path, user_data_dir: Path, world_registry: WorldRegistry | None = None, plugin_registry: PluginRegistry | None = None):
        self.root = root
        self.user_data_dir = user_data_dir
        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        self.state_store = MudStateStore(user_data_dir / "mud_state.db")
        self.world_registry = world_registry or WorldRegistry()
        self.plugin_registry = plugin_registry or PluginRegistry(root / "plugins")
        self.hooks = HookRegistry()
        self.active_world_id: Optional[str] = None
        self.active_world: Any = None
        self.sessions: dict[str, MudSession] = {}
        self.command_engine = MudCommandEngine(self.state_store)
        self.sqlite_ready = (user_data_dir / "mud_state.db").exists()
        print("[mud-runtime] Smart MUD runtime initialized")

    def load_world(self, world_id: str) -> Any:
        """Load a read-only world template package for gameplay."""
        self.active_world = self.world_registry.load_world(world_id)
        self.plugin_registry.resolve_required([str(p) for p in self.active_world.manifest.get("required_plugins", [])])
        self.active_world_id = world_id
        self.hooks.emit("world_loaded", world_id=world_id, world=self.active_world)
        return self.active_world

    def list_characters(self, world_id: str = "") -> list[dict[str, Any]]:
        """List SQLite-backed characters for a world."""
        with sqlite3.connect(self.state_store.db_path) as conn:
            rows = conn.execute(
                "SELECT id, world_id, name, role, immortal_level, data FROM characters WHERE (? = '' OR world_id = ?) ORDER BY name",
                (world_id, world_id),
            ).fetchall()
        characters: list[dict[str, Any]] = []
        for row in rows:
            data = json.loads(row[5] or "{}")
            characters.append(
                {
                    "character_id": row[0],
                    "world_id": row[1],
                    "name": row[2],
                    "role": row[3],
                    "immortal_level": row[4],
                    "room_id": data.get("room_id", ""),
                    "level": data.get("level", 1),
                }
            )
        return characters

    def create_character(self, *, world_id: str, name: str, race_id: str = "", class_id: str = "") -> dict[str, Any]:
        """Create one authoritative SQLite character state."""
        if not self.active_world or self.active_world_id != world_id:
            self.load_world(world_id)
        character_id = f"player_{name.lower().strip().replace(' ', '_') or 'player'}"
        start_room = getattr(self.active_world, "default_starting_room_id", "") or ""
        char = MudCharacter(
            id=character_id,
            name=name,
            role="player",
            room_id=start_room,
            abilities=[value for value in (race_id, class_id) if value],
        )
        self.state_store.save_character(char, world_id)
        self.hooks.emit("character_creation", world_id=world_id, character=char)
        return self._character_payload(char, world_id)

    def enter_world(self, character_id: str) -> dict[str, Any]:
        """Enter the loaded world as a SQLite-backed character."""
        char = self.state_store.load_character(character_id)
        if char is None:
            raise ValueError(f"Character not found: {character_id}")
        if not self.active_world_id:
            with sqlite3.connect(self.state_store.db_path) as conn:
                row = conn.execute("SELECT world_id FROM characters WHERE id = ?", (character_id,)).fetchone()
            if row and row[0]:
                self.load_world(str(row[0]))
        self.hooks.emit("player_login", world_id=self.active_world_id or "", character=char)
        self.sessions[character_id] = MudSession(
            session_id=character_id,
            character_id=character_id,
            world_id=self.active_world_id or "",
            connected_at=datetime.now(timezone.utc).isoformat(),
            last_activity=datetime.now(timezone.utc).isoformat(),
        )
        return {"ok": True, "character": self._character_payload(char, self.active_world_id or ""), "view": self.play_view(character_id)}

    def play_view(self, character_id: str) -> dict[str, Any]:
        """Render the current room through the single MUD display pipeline."""
        char = self.state_store.load_character(character_id) if character_id else None
        if char is None:
            return {"html": "", "text": "Create a character to enter the world.", "prompt": ">"}
        room = self._current_room(char)
        colors = self.get_effective_mud_colors()
        html = render_room(room, colors, char)
        prompt = render_prompt(char, colors)
        return {"html": html, "text": room.description, "prompt": prompt, "room_id": char.room_id}

    def handle_input(self, character_id: str, command: str) -> dict[str, Any]:
        """Execute a command and persist command/output scrollback to SQLite."""
        char = self.state_store.load_character(character_id)
        if char is None:
            raise ValueError(f"Character not found: {character_id}")
        result = self._handle_runtime_command(char, command)
        session = self.sessions.get(character_id)
        turn = (session.command_count + 1) if session else 1
        self.state_store.save_command(character_id, self.active_world_id or "", turn, command)
        self.state_store.save_scrollback(character_id, self.active_world_id or "", turn, result.narrative)
        if session:
            session.command_count = turn
            session.last_activity = datetime.now(timezone.utc).isoformat()
        return {"ok": result.ok, "output": result.narrative, "view": self.play_view(character_id)}

    def _handle_runtime_command(self, char: MudCharacter, command: str):
        tokens = command.strip().split()
        if not tokens:
            return self.command_engine.handle_command(char, command)
        cmd_name = self.command_engine.resolve_alias(tokens[0].lower())
        if cmd_name in {"north", "south", "east", "west", "up", "down", "in", "out"}:
            return self._move_character(char, cmd_name)
        result = self.command_engine.handle_command(char, command)
        if result.state_updates and result.state_updates.get("render_room"):
            room = self._current_room(char)
            result.narrative = self._room_text(room)
        return result

    def _move_character(self, char: MudCharacter, direction: str):
        from engine.mud_commands import CommandResult
        room = self._current_room(char)
        for exit_data in room.exits:
            if not isinstance(exit_data, dict):
                continue
            exit_direction = str(exit_data.get("direction") or exit_data.get("dir") or "").lower()
            if exit_direction != direction:
                continue
            target = exit_data.get("destination_room_id") or exit_data.get("to") or exit_data.get("room_id") or exit_data.get("target")
            if not target:
                break
            char.room_id = str(target)
            self.state_store.save_character(char, self.active_world_id or "")
            new_room = self._current_room(char)
            return CommandResult(narrative=f"You head {direction}.\n\n{self._room_text(new_room)}")
        return CommandResult(narrative="You cannot go that way.", ok=False)

    def _room_text(self, room: MudRoom) -> str:
        from smart_mud.transport import html_to_plain_text
        return html_to_plain_text(render_room(room, self.get_effective_mud_colors()))

    def _current_room(self, char: MudCharacter) -> MudRoom:
        if self.active_world is not None:
            try:
                room_data = self.active_world.room(char.room_id)
                return MudRoom(
                    id=str(room_data.get("id", char.room_id)),
                    area_id=str(room_data.get("area_id", "")),
                    title=str(room_data.get("name") or room_data.get("title") or char.room_id),
                    description=str(room_data.get("long_description") or room_data.get("description") or room_data.get("short_description") or ""),
                    exits=list(room_data.get("exits", []) or []),
                    npcs=self._room_npcs(room_data),
                    objects=self._room_objects(room_data),
                )
            except Exception:
                pass
        return MudRoom(id=char.room_id or "void", area_id="", title="The Void", description="An unfinished room.", exits=[])

    def _room_npcs(self, room_data: dict[str, Any]) -> list[Any]:
        ids = [str(v) for v in room_data.get("npcs", []) or []]
        direct = [npc for npc in getattr(self.active_world, "npcs", []) if str(npc.get("default_room_id") or npc.get("room_id") or "") == str(room_data.get("id"))]
        by_id = {str(npc.get("id")): npc for npc in getattr(self.active_world, "npcs", [])}
        records = [by_id.get(npc_id, npc_id) for npc_id in ids]
        for npc in direct:
            if npc not in records:
                records.append(npc)
        return records

    def _room_objects(self, room_data: dict[str, Any]) -> list[Any]:
        values = list(room_data.get("objects", []) or [])
        by_id = {str(item.get("id")): item for item in getattr(self.active_world, "items", [])}
        return [by_id.get(str(value), value) if not isinstance(value, dict) else value for value in values]

    def _character_payload(self, char: MudCharacter, world_id: str) -> dict[str, Any]:
        return {
            "character_id": char.id,
            "world_id": world_id,
            "name": char.name,
            "role": char.role,
            "room_id": char.room_id,
            "health": {"current": char.hp, "max": char.max_hp},
            "mana": {"current": char.mana, "max": char.max_mana},
            "stamina": {"current": char.stamina, "max": char.max_stamina},
            "experience": char.xp,
            "gold": char.gold,
            "inventory": char.inventory,
            "equipment": char.equipment,
            "known_abilities": char.abilities,
            "known_skills": [a for a in char.abilities if str(a).startswith("skill_")],
            "quest_progress": {},
            "npc_relationships": {},
            "faction_reputation": {},
        }

    def get_effective_mud_colors(self) -> dict[str, str]:
        """Get current MUD color configuration."""
        config_file = self.user_data_dir / "mud_colors.json"
        if config_file.exists():
            try:
                return json.loads(config_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        
        # Defaults
        return {
            "room_name": "#ffff00",
            "area_name": "#00ffff",
            "room_description": "#ffffff",
            "exit": "#00ff00",
            "npc": "#ff00ff",
            "mob": "#ff6600",
            "player": "#ffff00",
            "object": "#ff00ff",
            "item_common": "#cccccc",
            "item_uncommon": "#00ff00",
            "item_rare": "#0088ff",
            "item_epic": "#ff00ff",
            "item_legendary": "#ffff00",
            "command_echo": "#888888",
            "system": "#00ff00",
            "error": "#ff0000",
            "warning": "#ffff00",
            "combat": "#ff0000",
            "damage": "#ff0000",
            "healing": "#00ff00",
            "spell": "#0088ff",
            "skill": "#00ff00",
            "quest": "#ffff00",
            "score_label": "#00ffff",
            "score_value": "#ffffff",
            "equipment_slot": "#00ffff",
            "equipment_item": "#ffffff",
            "dialogue": "#ffff00",
            "prompt_marker": "#00ff00",
            "prompt_hp": "#ff0000",
            "prompt_mana": "#0088ff",
            "prompt_stamina": "#ffff00",
            "prompt_xp": "#00ff00",
            "prompt_gold": "#ffff00",
            "prompt_mv": "#00ffff",
            "prompt_alignment": "#ff00ff",
            "prompt_position": "#00ffff",
            "prompt_target": "#ff00ff",
            "prompt_area": "#00ffff",
            "prompt_time": "#888888",
        }

    def set_mud_colors(self, colors: dict[str, str]) -> None:
        """Update MUD color configuration."""
        config_file = self.user_data_dir / "mud_colors.json"
        config_file.write_text(json.dumps(colors, indent=2), encoding="utf-8")
        print(f"[mud-runtime] Updated {len(colors)} mud colors")
