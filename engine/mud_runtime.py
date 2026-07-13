"""Smart MUD runtime layer - primary application runtime."""

from __future__ import annotations

import json
import sqlite3
import re
import uuid
import hashlib
import logging
from types import MappingProxyType
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Optional
from datetime import datetime, timezone, timedelta

from engine.mud_commands import MudCommandEngine
from engine.mud_displays import render_object, render_prompt, render_room, semantic, build_inventory_document, build_equipment_document, render_display_mud, render_display_plain
from engine.player_preferences import PlayerPresentationPreferenceService
from engine.display_services import CharacterDisplaySnapshotService
from engine.conditions import condition_label
from engine.mud_rendering import render_semantic_plain
from smart_mud.world_registry import WorldRegistry
from smart_mud.builder import BuilderWorkspace
from smart_mud.event_bus import EventBus
from engine.plugin_system import HookRegistry, PluginRegistry
from engine.living_world import LivingWorldService, init_living_schema
from engine.abilities import AbilityExecutionService, init_ability_schema
from engine.actors import ActorRegistry, actor_from_runtime_character
from engine.crafting import init_crafting_schema
from engine.environment import EnvironmentService, init_environment_schema
from engine.survival_needs import SurvivalNeedsService, init_survival_schema
from engine.schedules import ScheduleService
from engine.combat_runtime import CombatRuntimeService, init_combat_runtime_schema
from engine.agent_runtime import AgentRuntimeGateway, DeterministicControllerEvaluator, init_agent_runtime_schema

logger = logging.getLogger(__name__)

VALID_ROLES = {"player", "helper", "builder", "admin", "owner"}
BUILDER_ROLES = {"builder", "admin", "owner"}
ADMIN_ROLES = {"admin", "owner"}

def slugify_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "_", name.lower().strip())
    return slug.strip("_") or "player"

def validate_character_name(name: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(name or "").strip())
    if not cleaned:
        raise ValueError("Character name is required.")
    if len(cleaned) > 32:
        raise ValueError("Character name must be 32 characters or fewer.")
    if not re.fullmatch(r"[A-Za-z][A-Za-z -]*", cleaned):
        raise ValueError("Character names may contain letters, spaces, and hyphens.")
    return cleaned

def role_rank(role: str) -> int:
    return {"player": 0, "helper": 1, "builder": 2, "admin": 3, "owner": 4}.get(str(role or "player").lower(), 0)

def _role(subject: Any) -> str:
    return str(getattr(subject, "role", subject.get("role", "player") if isinstance(subject, dict) else subject) or "player")

def _permission_checked(subject: Any, permission: str, allowed: bool) -> bool:
    bus = getattr(subject, "event_bus", None)
    if bus:
        bus.publish("permission_checked", {"permission": permission, "allowed": allowed, "role": _role(subject)}, source_system="permissions")
    return allowed

def is_player(subject: Any) -> bool: return _permission_checked(subject, "is_player", _role(subject) in VALID_ROLES)
def is_builder(subject: Any) -> bool: return _permission_checked(subject, "is_builder", _role(subject) in BUILDER_ROLES)
def is_immortal(subject: Any) -> bool: return _permission_checked(subject, "is_immortal", _role(subject) in ADMIN_ROLES or int(getattr(subject, "immortal_level", subject.get("immortal_level", 0) if isinstance(subject, dict) else 0) or 0) > 0)
def is_admin(subject: Any) -> bool: return _permission_checked(subject, "is_admin", _role(subject) in ADMIN_ROLES)
def can_build(subject: Any) -> bool: return _permission_checked(subject, "can_build", _role(subject) in BUILDER_ROLES or bool(getattr(subject, "builder_enabled", subject.get("builder_enabled", False) if isinstance(subject, dict) else False)))
def can_use_wizhelp(subject: Any) -> bool: return _permission_checked(subject, "can_use_wizhelp", _role(subject) in ADMIN_ROLES or int(getattr(subject, "immortal_level", subject.get("immortal_level", 0) if isinstance(subject, dict) else 0) or 0) > 0)
def can_edit_world_package(subject: Any) -> bool: return _permission_checked(subject, "can_edit_world_package", _role(subject) in ADMIN_ROLES)
def can_manage_accounts(subject: Any) -> bool: return _permission_checked(subject, "can_manage_accounts", _role(subject) in ADMIN_ROLES)


def should_show_room_ids(subject: Any) -> bool:
    """Return true only for future debug/builder contexts, never normal players."""
    return is_builder(subject) or is_immortal(subject) or is_admin(subject)



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
    account_id: str = ""
    account_role: str = "player"
    builder_enabled: bool = False
    current_area_id: str = ""
    current_zone_id: str = ""
    last_room_id: str = ""
    last_created_room_id: str = ""
    edit_room_id: str = ""
    last_edited_target: str = ""
    builder_desc_editor_room_id: str = ""
    builder_desc_editor_lines: list[str] = field(default_factory=list)
    actor_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class MudRoom:
    """Runtime room state in MUD."""
    id: str
    area_id: str
    title: str
    description: str
    exits: list[dict[str, str]] = field(default_factory=list)
    players: list[Any] = field(default_factory=list)
    npcs: list[Any] = field(default_factory=list)
    mobs: list[Any] = field(default_factory=list)
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
    transport_type: str = ""
    account_id: str | None = None
    authenticated: bool = False
    state: str = "connected"


class MudStateStore:
    """SQLite persistence for MUD runtime state."""

    def __init__(self, db_path: Path, event_bus: EventBus | None = None):
        self.db_path = db_path
        self.event_bus = event_bus
        if self.event_bus:
            self.event_bus.publish("database_opened", {"db_path": str(db_path)}, source_system="persistence")
        self._init_schema()
        if self.event_bus:
            self.event_bus.publish("database_migrated", {"db_path": str(db_path)}, source_system="persistence")

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        """Initialize SQLite schema for MUD persistence."""
        with sqlite3.connect(self.db_path) as conn:
            # Characters
            conn.execute("""
                CREATE TABLE IF NOT EXISTS characters (
                    id TEXT PRIMARY KEY,
                    account_id TEXT,
                    world_id TEXT,
                    name TEXT,
                    slug TEXT,
                    role TEXT,
                    immortal_level INTEGER,
                    builder_enabled INTEGER DEFAULT 0,
                    data JSON,
                    last_played_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    account_id TEXT PRIMARY KEY,
                    username TEXT UNIQUE,
                    password_hash TEXT,
                    local_dev_auth_token TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_login_at DATETIME,
                    status TEXT DEFAULT 'active',
                    role TEXT DEFAULT 'player',
                    email TEXT,
                    notes TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS role_grant_log (
                    id INTEGER PRIMARY KEY,
                    account_id TEXT,
                    character_id TEXT,
                    character_name TEXT,
                    role TEXT,
                    source TEXT,
                    granted_by_account_id TEXT,
                    granted_by_character_id TEXT,
                    timestamp TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS runtime_sessions (
                    session_id TEXT PRIMARY KEY, transport_type TEXT, account_id TEXT, character_id TEXT, world_id TEXT,
                    remote_address TEXT, connected_at TEXT, last_activity_at TEXT, authenticated INTEGER, state TEXT
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
            
            # Canonical Phase 2E runtime item instances.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS item_instances (
                    instance_id TEXT PRIMARY KEY,
                    world_id TEXT,
                    template_id TEXT,
                    owner_type TEXT,
                    owner_id TEXT,
                    room_id TEXT,
                    equipped_slot TEXT,
                    stack_count INTEGER DEFAULT 1,
                    condition TEXT DEFAULT 'normal',
                    durability INTEGER DEFAULT 100,
                    created_at TEXT,
                    updated_at TEXT,
                    custom_flags JSON,
                    plugin_data JSON,
                    destroyed_at TEXT,
                    destroy_reason TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS actor_effect_instances (
                    effect_instance_id TEXT PRIMARY KEY, world_id TEXT, effect_template_id TEXT,
                    target_actor_type TEXT, target_actor_id TEXT, source_actor_type TEXT, source_actor_id TEXT,
                    source_ability_id TEXT, source_item_instance_id TEXT, category TEXT, disposition TEXT,
                    visibility TEXT, stack_group TEXT, stack_count INTEGER, maximum_stacks INTEGER,
                    started_world_time INTEGER, expires_world_time INTEGER, remaining_duration INTEGER,
                    next_tick_world_time INTEGER, active INTEGER, suspended INTEGER, removal_reason TEXT,
                    created_at TEXT, updated_at TEXT, metadata_json TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_actor_effect_target ON actor_effect_instances(target_actor_type,target_actor_id,active)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_actor_effect_source ON actor_effect_instances(source_actor_type,source_actor_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_actor_effect_template ON actor_effect_instances(effect_template_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_actor_effect_expire ON actor_effect_instances(world_id,expires_world_time,active)")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS room_item_seeds (
                    world_id TEXT,
                    room_id TEXT,
                    template_id TEXT,
                    seed_key TEXT,
                    created_at TEXT,
                    PRIMARY KEY(world_id, room_id, seed_key)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS entity_instances (
                    entity_id TEXT PRIMARY KEY,
                    world_id TEXT,
                    entity_type TEXT,
                    template_id TEXT,
                    name TEXT,
                    keywords JSON,
                    short_description TEXT,
                    long_description TEXT,
                    current_room_id TEXT,
                    owner_type TEXT,
                    owner_id TEXT,
                    faction_id TEXT,
                    level INTEGER DEFAULT 1,
                    state JSON,
                    flags JSON,
                    created_at TEXT,
                    updated_at TEXT,
                    plugin_data JSON,
                    destroyed_at TEXT,
                    destroy_reason TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS room_entity_seeds (
                    world_id TEXT,
                    room_id TEXT,
                    template_id TEXT,
                    seed_key TEXT,
                    created_at TEXT,
                    PRIMARY KEY(world_id, room_id, seed_key)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS content_materializations (
                    world_id TEXT,
                    declaration_kind TEXT,
                    declaration_id TEXT,
                    materialized_at TEXT,
                    instance_ids_json JSON,
                    status TEXT,
                    metadata_json JSON,
                    PRIMARY KEY(world_id, declaration_kind, declaration_id)
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
                    account_id TEXT,
                    session_id TEXT,
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
            
            for table, cols in {
                "characters": {"account_id":"TEXT","slug":"TEXT","builder_enabled":"INTEGER DEFAULT 0","last_played_at":"DATETIME"},
                "command_history": {"account_id":"TEXT","session_id":"TEXT"},
            }.items():
                existing = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
                for name, ddl in cols.items():
                    if name not in existing:
                        conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
            existing_items = {r[1] for r in conn.execute("PRAGMA table_info(item_instances)")}
            for name, ddl in {"world_id":"TEXT","condition":"TEXT DEFAULT 'normal'","durability":"INTEGER DEFAULT 100","custom_flags":"JSON","plugin_data":"JSON","destroyed_at":"TEXT","destroy_reason":"TEXT"}.items():
                if name not in existing_items:
                    conn.execute(f"ALTER TABLE item_instances ADD COLUMN {name} {ddl}")

            existing = {r[1] for r in conn.execute("PRAGMA table_info(accounts)")}
            for name, ddl in {"password_hash":"TEXT","local_dev_auth_token":"TEXT","last_login_at":"DATETIME","status":"TEXT DEFAULT 'active'","role":"TEXT DEFAULT 'player'","email":"TEXT","notes":"TEXT"}.items():
                if name not in existing:
                    conn.execute(f"ALTER TABLE accounts ADD COLUMN {name} {ddl}")

            init_living_schema(self.db_path)
            init_ability_schema(self.db_path)
            init_crafting_schema(self.db_path)
            init_combat_runtime_schema(self.db_path)
            conn.commit()

    def save_character(self, char: MudCharacter, world_id: str) -> None:
        """Save character to SQLite."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO characters 
                   (id, account_id, world_id, name, slug, role, immortal_level, builder_enabled, data, updated_at)
                   VALUES (?, COALESCE((SELECT account_id FROM characters WHERE id=?), ''), ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (char.id, char.id, world_id, char.name, slugify_name(char.name), char.role, char.immortal_level, 1 if getattr(char, "builder_enabled", False) else 0,
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
                dbrow = conn.execute("SELECT account_id, role, builder_enabled FROM characters WHERE id = ?", (char_id,)).fetchone()
                if dbrow:
                    data["account_id"] = dbrow[0] or data.get("account_id", "")
                    data["role"] = dbrow[1] or data.get("role", "player")
                    data["builder_enabled"] = bool(dbrow[2])
                    if data["account_id"]:
                        arow = conn.execute("SELECT role FROM accounts WHERE account_id=?", (data["account_id"],)).fetchone()
                        if arow:
                            data["account_role"] = arow[0] or "player"
                            if role_rank(data["account_role"]) > role_rank(data["role"]):
                                data["role"] = data["account_role"]
                print(f"[mud-persistence] Loaded character {data.get('name')} ({char_id})")
                ch = MudCharacter(**{k: v for k, v in data.items() if k in MudCharacter.__dataclass_fields__})
                if hasattr(self, "presentation_preferences"):
                    self.presentation_preferences.apply_to_character(ch)
                return ch
        return None

    def save_command(self, char_id: str, world_id: str, turn: int, command: str, account_id: str = "", session_id: str = "") -> None:
        """Save command to history (SQLite only, not campaign-memory)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO command_history (character_id, world_id, turn, command, account_id, session_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (char_id, world_id, turn, command, account_id, session_id)
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

    def grant_role(self, *, role: str, account: str = "", character: str = "", source: str = "cli", granted_by_account_id: str = "", granted_by_character_id: str = "") -> dict[str, Any]:
        role = str(role or "").lower().strip()
        if role not in VALID_ROLES:
            raise ValueError(f"Invalid role {role!r}. Valid roles: {', '.join(sorted(VALID_ROLES))}.")
        if not account and not character:
            raise ValueError("Provide an account username/id or character name/id.")
        with sqlite3.connect(self.db_path) as conn:
            account_id = ""; character_id = ""; character_name = ""
            if account:
                row = conn.execute("SELECT account_id FROM accounts WHERE lower(username)=lower(?) OR account_id=?", (account, account)).fetchone()
                if not row: raise ValueError(f"Account not found: {account}")
                account_id = row[0]
                conn.execute("UPDATE accounts SET role=?, updated_at=CURRENT_TIMESTAMP WHERE account_id=?", (role, account_id))
            if character:
                row = conn.execute("SELECT id,name,account_id FROM characters WHERE lower(name)=lower(?) OR id=?", (character, character)).fetchone()
                if not row: raise ValueError(f"Character not found: {character}")
                character_id, character_name = row[0], row[1]
                account_id = account_id or (row[2] or "")
                conn.execute("UPDATE characters SET role=?, builder_enabled=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (role, 1 if role in BUILDER_ROLES else 0, character_id))
            timestamp = datetime.now(timezone.utc).isoformat()
            conn.execute("INSERT INTO role_grant_log(account_id,character_id,character_name,role,source,granted_by_account_id,granted_by_character_id,timestamp) VALUES(?,?,?,?,?,?,?,?)", (account_id, character_id, character_name, role, source, granted_by_account_id, granted_by_character_id, timestamp))
            conn.commit()
        return {"account_id": account_id, "character_id": character_id, "character_name": character_name, "role": role, "timestamp": timestamp, "source": source}

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

    def __init__(self, root: Path, user_data_dir: Path, world_registry: WorldRegistry | None = None, plugin_registry: PluginRegistry | None = None, event_bus: EventBus | None = None):
        self.event_bus = event_bus or EventBus()
        self.event_bus.publish("startup_complete", {"runtime": "mud"}, source_system="runtime")
        self.root = root
        self.user_data_dir = user_data_dir
        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        self.state_store = MudStateStore(user_data_dir / "mud_state.db", self.event_bus)
        self.world_registry = world_registry or WorldRegistry()
        self.plugin_registry = plugin_registry or PluginRegistry(root / "plugins")
        self.hooks = HookRegistry()
        self.active_world_id: Optional[str] = None
        self.active_world: Any = None
        self.item_templates: dict[str, MappingProxyType] = {}
        self.entity_templates: dict[str, MappingProxyType] = {}
        self.sessions: dict[str, MudSession] = {}
        self.command_engine = MudCommandEngine(self.state_store, event_bus=self.event_bus)
        self.actor_registry = ActorRegistry()
        self.abilities = None
        self.builder = BuilderWorkspace(event_bus=self.event_bus)
        self.command_engine.runtime = self
        self.presentation_preferences = PlayerPresentationPreferenceService(self.state_store.db_path)
        self.character_display_snapshots = CharacterDisplaySnapshotService(self)
        self.command_engine.presentation_preferences = self.presentation_preferences
        self.command_engine.character_display_snapshots = self.character_display_snapshots
        init_agent_runtime_schema(self.state_store.db_path)
        self.combat_runtime = CombatRuntimeService(self)
        self.agent_gateway = AgentRuntimeGateway(self)
        self.deterministic_controller_evaluator = DeterministicControllerEvaluator(self.agent_gateway)
        self.command_engine.combat_runtime = self.combat_runtime
        self.living_world = LivingWorldService(self)
        self.schedule_service = ScheduleService(self)
        init_survival_schema(self.state_store.db_path)
        self.survival_needs = SurvivalNeedsService(self.state_store.db_path, root / "worlds" / "shattered_realms", "shattered_realms", self.event_bus, self)
        init_environment_schema(self.state_store.db_path)
        self.environment = EnvironmentService(self.state_store.db_path, root / "worlds" / "shattered_realms", "shattered_realms", self.event_bus)
        self.sqlite_ready = (user_data_dir / "mud_state.db").exists()
        self.event_bus.publish("runtime_ready", {"sqlite_ready": self.sqlite_ready}, source_system="runtime")
        print("[mud-runtime] Smart MUD runtime initialized")


    # Phase 5B living-world facade APIs.
    def get_world_time(self, world_id: str | None = None) -> dict[str, Any]: return self.living_world.ensure_world_time(world_id or self.active_world_id or "")
    def set_world_time(self, world_id: str, day: int, hhmm: str | None = None, hour: int | None = None, minute: int | None = None) -> dict[str, Any]: return self.living_world.set_world_time(world_id, day, hhmm, hour, minute)
    def advance_world_time(self, world_id: str, minutes: int) -> dict[str, Any]:
        wt = self.living_world.advance_world_time(world_id, minutes)
        if getattr(self, "survival_needs", None):
            self.survival_needs.process_world_needs(world_id, wt)
            self.survival_needs.process_due_runtime_objects(wt)
        if getattr(self, "combat_runtime", None): self.combat_runtime.process_due_rounds()
        return wt
    def runtime_pulse(self, minutes: int = 1) -> dict[str, Any]:
        world_id=self.active_world_id or ''
        wt=self.advance_world_time(world_id, max(1, int(minutes))) if world_id else {'total_minutes':0}
        if getattr(self, 'abilities', None):
            try: self.abilities.process_ability_casts(world_id, int(wt.get('total_minutes') or 0))
            except Exception: pass
        self.process_due_agent_controllers(int(wt.get('total_minutes') or 0))
        return wt

    def process_due_agent_controllers(self, world_time: int, limit: int = 10) -> int:
        token = "agentclaim_" + uuid.uuid4().hex; now = datetime.now(timezone.utc).isoformat(); claimed: list[tuple[str, str]] = []
        with sqlite3.connect(self.state_store.db_path, timeout=30) as con:
            con.execute("BEGIN IMMEDIATE")
            rows = con.execute("SELECT controller_id,actor_id FROM agent_controllers WHERE controller_type='deterministic' AND enabled=1 AND COALESCE(next_decision_world_time,0)<=? ORDER BY priority DESC,controller_id LIMIT ?", (world_time, int(limit))).fetchall()
            for cid, aid in rows:
                if con.execute("UPDATE agent_controllers SET claim_token=?,claim_expires_at=? WHERE controller_id=? AND (claim_token='' OR claim_token IS NULL OR claim_expires_at<?)", (token, now, cid, now)).rowcount:
                    claimed.append((cid, aid))
            con.commit()
        for cid, aid in claimed:
            try: self.deterministic_controller_evaluator.step(aid, cid)
            except Exception: pass
            with sqlite3.connect(self.state_store.db_path) as con:
                prof = con.execute("SELECT p.decision_interval_world_minutes FROM agent_controller_profiles p JOIN agent_controllers c ON c.controller_profile_id=p.profile_id WHERE c.controller_id=?", (cid,)).fetchone()
                interval = int((prof[0] if prof else 5) or 5)
                con.execute("UPDATE agent_controllers SET claim_token='',claim_expires_at='',last_decision_world_time=?,next_decision_world_time=? WHERE controller_id=? AND claim_token=?", (world_time, world_time + max(1, interval), cid, token))
        return len(claimed)

    def drain_session_output(self, character_id: str) -> list[str]:
        if getattr(self, 'combat_runtime', None):
            return self.combat_runtime.drain_output(character_id)
        return []

    def _active_character_ids_in_room(self, room_id: str, *, exclude: set[str] | None = None) -> list[str]:
        exclude = exclude or set()
        ids: list[str] = []
        for session in getattr(self, "sessions", {}).values():
            if getattr(session, "state", "playing") == "disconnected":
                continue
            cid = getattr(session, "character_id", "")
            if not cid or cid in exclude or cid in ids:
                continue
            ch = self.state_store.load_character(cid)
            if ch and ch.room_id == room_id:
                ids.append(cid)
        return ids

    def _enqueue_room_output(self, character_id: str, message: str, *, room_id: str = "", category: str = "room_action") -> None:
        if getattr(self, "combat_runtime", None):
            self.combat_runtime.enqueue_output(character_id, message, room_id=room_id, category=category)

    def deliver_room_action(self, room_id: str, message: str, *, actor_id: str = "", category: str = "room_action") -> None:
        for cid in self._active_character_ids_in_room(room_id, exclude={actor_id} if actor_id else set()):
            self._enqueue_room_output(cid, message, room_id=room_id, category=category)
        self.event_bus.publish("room_action_observed", {"room_id": room_id, "actor_id": actor_id, "message_kind": category}, source_system="runtime", world_id=self.active_world_id or "", room_id=room_id)


    def deliver_perspective_action(self, actor: MudCharacter, target: Any, room_id: str, actor_message: str, target_message: str | None, observer_message: str | None, *, semantic_role: str = "system", intent: str = "SYSTEM", exclusions: set[str] | None = None, visibility_policy: Any = None):
        """Deliver actor/target/observer output through one runtime queue path."""
        from engine.mud_commands import CommandResult
        actor_id = getattr(actor, "id", "")
        excluded = set(exclusions or set()) | ({actor_id} if actor_id else set())
        target_id = ""
        if target is not None:
            target_id = str(target.get("character_id") or target.get("id") or target.get("actor_id") or "") if isinstance(target, dict) else str(getattr(target, "id", ""))
            if target_message and target_id and target_id != actor_id:
                self._enqueue_room_output(target_id, semantic(semantic_role, target_message), room_id=room_id, category=str(intent).lower())
                excluded.add(target_id)
        if observer_message:
            for cid in self._active_character_ids_in_room(room_id, exclude=excluded):
                self._enqueue_room_output(cid, semantic(semantic_role, observer_message), room_id=room_id, category=str(intent).lower())
        self.event_bus.publish("perspective_action_delivered", {"room_id": room_id, "actor_id": actor_id, "target_id": target_id, "intent": intent}, source_system="runtime", world_id=self.active_world_id or "", character_id=actor_id, room_id=room_id)
        return CommandResult(narrative=semantic(semantic_role, actor_message), display_intent=intent, semantic_role=semantic_role)

    def pause_world_time(self, world_id: str) -> dict[str, Any]: return self.living_world.pause_world_time(world_id)
    def resume_world_time(self, world_id: str) -> dict[str, Any]: return self.living_world.resume_world_time(world_id)
    def get_entity_profile(self, instance_id: str) -> dict[str, Any]: return self.living_world.get_entity_profile(instance_id)
    def get_entity_context(self, instance_id: str) -> dict[str, Any]: return self.living_world.get_context(instance_id)
    def evaluate_entity_schedule(self, instance_id: str, world_time: dict[str, Any] | None = None) -> dict[str, Any]: return self.living_world.evaluate_schedule(instance_id, world_time)
    def apply_entity_schedule(self, instance_id: str, world_time: dict[str, Any] | None = None) -> dict[str, Any]: return self.schedule_service.apply(instance_id, world_time)
    def find_room_path(self, start_room_id: str, target_room_id: str, max_depth: int = 20) -> dict[str, Any]: return self.living_world.find_room_path(start_room_id, target_room_id, max_depth)
    def move_entity_along_path(self, instance_id: str, path: list[str], steps: int = 1) -> dict[str, Any]: return self.move_entity(instance_id, path[min(steps, len(path)-1)]) if path else {}
    def simulate_world(self, world_id: str, minutes: int) -> dict[str, Any]: return self.living_world.simulate_world(world_id, minutes)
    def simulate_entity(self, instance_id: str, minutes: int) -> dict[str, Any]: self.living_world.advance_needs(instance_id, minutes); return self.apply_entity_schedule(instance_id)
    def create_entity_goal(self, *args: Any, **kwargs: Any) -> str: return self.living_world.create_entity_goal(*args, **kwargs)
    def list_entity_goals(self, instance_id: str, status: str | None = None) -> list[dict[str, Any]]: return self.living_world.list_goals(instance_id, status)
    def select_deterministic_goal(self, instance_id: str) -> dict[str, Any] | None: return self.living_world.select_goal(instance_id)
    def record_entity_memory(self, *args: Any, **kwargs: Any) -> str: return self.living_world.record_memory(*args, **kwargs)
    def query_entity_memories(self, instance_id: str, **kwargs: Any) -> list[dict[str, Any]]: return self.living_world.query_memories(instance_id, **kwargs)
    def get_recent_memories(self, instance_id: str, limit: int = 10) -> list[dict[str, Any]]: return self.living_world.query_memories(instance_id, limit=limit)
    def get_memories_about(self, instance_id: str, subject_type: str, subject_id: str) -> list[dict[str, Any]]: return self.living_world.query_memories(instance_id, subject_type, subject_id)


    def _progression_service(self):
        from engine.progression import ProgressionService
        store = self.state_store
        if not hasattr(store, "world_id"): store.world_id = self.active_world_id or "shattered_realms"  # type: ignore[attr-defined]
        if not hasattr(store, "campaign_id"): store.campaign_id = self.active_world_id or "shattered_realms"  # type: ignore[attr-defined]
        if not hasattr(store, "initialize"):
            def _init_progression_tables():
                with store.connect() as con:
                    con.execute("""CREATE TABLE IF NOT EXISTS actor_progression_state(progression_state_id TEXT PRIMARY KEY,world_id TEXT,actor_type TEXT,actor_id TEXT,species_id TEXT,race_id TEXT,primary_class_id TEXT,primary_class_track_id TEXT,profession_ids_json TEXT,level INTEGER,experience INTEGER,experience_to_next INTEGER,total_experience INTEGER,practice_sessions INTEGER,training_sessions INTEGER,skill_points INTEGER,attribute_points INTEGER,talent_points_placeholder INTEGER,remort_count INTEGER,prestige_rank INTEGER,advancement_flags_json TEXT,last_level_at TEXT,created_at TEXT,updated_at TEXT,metadata_json TEXT,UNIQUE(actor_type,actor_id))""")
                    con.execute("""CREATE TABLE IF NOT EXISTS actor_advancement_currency_events(event_id TEXT PRIMARY KEY,actor_id TEXT,currency_id TEXT,event_type TEXT,amount INTEGER,source_type TEXT,source_id TEXT,reason TEXT,balance_after INTEGER,created_at TEXT,metadata_json TEXT)""")
                    con.execute("""CREATE TABLE IF NOT EXISTS actor_ability_progression(actor_id TEXT,ability_id TEXT,rank INTEGER,maximum_rank INTEGER,proficiency INTEGER,learned_at_level INTEGER,source_class_id TEXT,source_race_id TEXT,source_profession_id TEXT,source_track_id TEXT,practice_cost INTEGER,training_cost INTEGER,skill_point_cost INTEGER,requirements_json TEXT,active INTEGER,learned_at TEXT,metadata_json TEXT,PRIMARY KEY(actor_id,ability_id))""")
                    con.execute("""CREATE TABLE IF NOT EXISTS actor_progression_modifiers(modifier_id TEXT PRIMARY KEY,actor_id TEXT,source_type TEXT,source_id TEXT,modifier_domain TEXT,modifier_key TEXT,operation TEXT,value INTEGER,level INTEGER,active INTEGER,metadata_json TEXT)""")
                    con.execute("""CREATE TABLE IF NOT EXISTS actor_experience_events(event_id TEXT PRIMARY KEY,world_id TEXT,actor_type TEXT,actor_id TEXT,source_type TEXT,source_id TEXT,base_amount INTEGER,final_amount INTEGER,level_delta INTEGER,total_after INTEGER,reason TEXT,applied_formula_id TEXT,created_at TEXT,metadata_json TEXT)""")
            store.initialize = _init_progression_tables  # type: ignore[attr-defined]
        return ProgressionService(store)

    def _ensure_starter_progression(self, char: MudCharacter) -> None:
        ps = self._progression_service()
        state = ps.initialize_actor_progression(char, defaults={"attribute_points": 30})
        if int(state.get("attribute_points", 0) or 0) < 30:
            flags = state.get("advancement_flags") or {}
            if not flags.get("starter_attribute_points_30"):
                ps.grant_currency(char.id, "attribute_points", 30 - int(state.get("attribute_points", 0) or 0), "starter_character", "starter_demonstration", "starter attribute points")
                flags["starter_attribute_points_30"] = True
                ps.update_actor_progression(char.id, {"advancement_flags_json": flags})
        for aid in ("set_camp", "build_campfire", "recall"):
            ps.learn_ability(char.id, aid, {"source_type":"starter_character","source_id":"starter_demonstration","default_proficiency":1,"maximum_proficiency":100,"maximum_rank":100})
        if self.abilities:
            self.abilities.actor_from_character(char)

    def create_runtime_session(self, transport_type: str, remote_address: str = "") -> MudSession:
        now = datetime.now(timezone.utc).isoformat()
        session = MudSession(session_id=str(uuid.uuid4()), character_id="", world_id="", connected_at=now, last_activity=now, transport_type=transport_type, state="account_login")
        self.sessions[session.session_id] = session
        with sqlite3.connect(self.state_store.db_path) as conn:
            conn.execute("INSERT OR REPLACE INTO runtime_sessions(session_id,transport_type,remote_address,connected_at,last_activity_at,authenticated,state) VALUES(?,?,?,?,?,?,?)", (session.session_id, transport_type, remote_address, now, now, 0, session.state))
        self.event_bus.publish("session_created", {"session_id": session.session_id, "transport_type": transport_type, "remote_address": remote_address}, source_system="session", session_id=session.session_id, transport_type=transport_type)
        return session

    def _account_payload(self, row: Any) -> dict[str, Any]:
        return {"account_id": row[0], "username": row[1], "status": row[2], "role": row[3], "email": row[4]}

    def any_account_exists(self) -> bool:
        with sqlite3.connect(self.state_store.db_path) as conn:
            return bool(conn.execute("SELECT 1 FROM accounts LIMIT 1").fetchone())

    def ensure_dev_account(self) -> dict[str, Any]:
        if self.any_account_exists():
            with sqlite3.connect(self.state_store.db_path) as conn:
                row = conn.execute("SELECT account_id,username,status,role,email FROM accounts ORDER BY created_at LIMIT 1").fetchone()
                return self._account_payload(row)
        return self.create_account("local_dev")

    def create_account(self, username: str, password: str = "", email: str = "", notes: str = "", role: str = "player") -> dict[str, Any]:
        username = re.sub(r"\s+", "_", str(username or "").strip())
        if not username:
            raise ValueError("Account username is required.")
        if role not in VALID_ROLES: role = "player"
        account_id = f"acct_{slugify_name(username)}"
        token = f"dev-{uuid.uuid4().hex}"
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.state_store.db_path) as conn:
            conn.execute("INSERT INTO accounts(account_id,username,password_hash,local_dev_auth_token,created_at,updated_at,status,role,email,notes) VALUES(?,?,?,?,?,?,?,?,?,?)", (account_id, username, hashlib.sha256(password.encode()).hexdigest() if password else "", token, now, now, "active", role, email, notes))
            conn.execute("UPDATE characters SET account_id=? WHERE COALESCE(account_id,'')=''", (account_id,))
        self.event_bus.publish("account_created", {"account_id": account_id, "username": username, "role": role}, source_system="account", account_id=account_id)
        return {"account_id": account_id, "username": username, "status": "active", "role": role, "email": email, "local_dev_auth_token": token}

    def login_account(self, username: str, password: str = "", session_id: str = "") -> dict[str, Any]:
        with sqlite3.connect(self.state_store.db_path) as conn:
            row = conn.execute("SELECT account_id,username,status,role,email,password_hash FROM accounts WHERE lower(username)=lower(?)", (str(username or "").strip(),)).fetchone()
            if not row: raise ValueError("Account not found.")
            stored_hash = row[5] or ""
            if stored_hash and hashlib.sha256(password.encode()).hexdigest() != stored_hash:
                raise ValueError("Wrong password.")
            conn.execute("UPDATE accounts SET last_login_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE account_id=?", (row[0],))
        account = self._account_payload(row)
        if session_id in self.sessions:
            self.authenticate_session(session_id, account["account_id"], state="character_select")
        self.event_bus.publish("account_login", {"account_id": account["account_id"], "username": account["username"], "session_id": session_id}, source_system="account", account_id=account["account_id"], session_id=session_id)
        return account

    def logout_account(self, session_id: str = "") -> dict[str, Any]:
        session = self.sessions.get(session_id)
        account_id = session.account_id if session else ""
        if session:
            session.state = "disconnected"; session.authenticated = False
        self.event_bus.publish("account_logout", {"account_id": account_id, "session_id": session_id}, source_system="account", account_id=account_id, session_id=session_id)
        return {"ok": True}

    def authenticate_session(self, session_id: str, account_id: str, state: str = "character_select") -> None:
        session = self.sessions.get(session_id)
        if not session: return
        session.account_id = account_id; session.authenticated = True; session.state = state; session.last_activity = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.state_store.db_path) as conn:
            conn.execute("UPDATE runtime_sessions SET account_id=?,authenticated=1,state=?,last_activity_at=? WHERE session_id=?", (account_id, state, session.last_activity, session_id))
        self.event_bus.publish("session_authenticated", {"session_id": session_id, "account_id": account_id, "transport_type": session.transport_type}, source_system="session", account_id=account_id, session_id=session_id, transport_type=session.transport_type)

    def load_world(self, world_id: str) -> Any:
        """Load a read-only world template package for gameplay."""
        self.active_world = self.world_registry.load_world(world_id)
        self.plugin_registry.resolve_required([str(p) for p in self.active_world.manifest.get("required_plugins", [])])
        self.event_bus.publish("plugins_resolved", {"world_id": world_id}, source_system="plugin", world_id=world_id)
        self.active_world_id = world_id
        self._load_item_templates()
        self._load_entity_templates()
        self.materialize_world_content(world_id)
        self.living_world.ensure_world_time(world_id)
        self.actor_registry = getattr(self, "actor_registry", ActorRegistry())
        self.abilities = AbilityExecutionService(self.state_store.db_path, self.active_world, self.event_bus, world_id, actor_registry=self.actor_registry)
        self.abilities.runtime = self
        if self.abilities.actor_registry is not self.actor_registry:
            raise RuntimeError("AbilityExecutionService registry wiring failed during world load")
        self.command_engine.ability_service = self.abilities
        self.command_engine.world_id = world_id
        self.environment = EnvironmentService(self.state_store.db_path, self.active_world.root, world_id, self.event_bus)
        self.command_engine.environment_service = self.environment
        self.combat_runtime.refresh_content()
        self.hooks.emit("world_loaded", world_id=world_id, world=self.active_world)
        self.event_bus.publish("world_loaded", {"world_id": world_id}, source_system="runtime", world_id=world_id)
        return self.active_world

    def list_characters(self, world_id: str = "", account_id: str = "") -> list[dict[str, Any]]:
        """List SQLite-backed characters for a world."""
        with sqlite3.connect(self.state_store.db_path) as conn:
            rows = conn.execute(
                "SELECT id, world_id, name, role, immortal_level, data, account_id, slug, last_played_at FROM characters WHERE (? = '' OR world_id = ?) AND (? = '' OR account_id = ?) ORDER BY name",
                (world_id, world_id, account_id, account_id),
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
                    "account_id": row[6] or "",
                    "slug": row[7] or "",
                    "last_played_at": row[8] or "",
                }
            )
        return characters

    def create_character(self, *, world_id: str, name: str, race_id: str = "", class_id: str = "", account_id: str = "") -> dict[str, Any]:
        """Create one authoritative SQLite character state."""
        if not self.active_world or self.active_world_id != world_id:
            self.load_world(world_id)
        name = validate_character_name(name)
        slug = slugify_name(name)
        with sqlite3.connect(self.state_store.db_path) as conn:
            duplicate = conn.execute("SELECT 1 FROM characters WHERE world_id=? AND slug=?", (world_id, slug)).fetchone()
            if duplicate:
                raise ValueError("A character with that name already exists in this world.")
        character_id = f"char_{world_id}_{slug}"
        start_room = getattr(self.active_world, "default_starting_room_id", "") or ""
        char = MudCharacter(
            id=character_id,
            name=name,
            role="player",
            room_id=start_room,
            abilities=[value for value in (race_id, class_id) if value],
        )
        self.state_store.save_character(char, world_id)
        if account_id:
            with sqlite3.connect(self.state_store.db_path) as conn:
                conn.execute("UPDATE characters SET account_id=? WHERE id=?", (account_id, char.id))
        self._spawn_starter_items(char.id)
        self._ensure_starter_progression(char)
        self.hooks.emit("character_creation", world_id=world_id, character=char)
        self.event_bus.publish("character_created", {"account_id": account_id, "character_id": char.id, "character_name": char.name}, source_system="runtime", account_id=account_id, world_id=world_id, character_id=char.id)
        return self._character_payload(char, world_id)

    def register_live_character(self, character: MudCharacter) -> None:
        """Refresh the canonical live Actor for a loaded character.

        MudRuntime owns command-time character loading from persistence. Every
        freshly loaded character object is immediately converted into the one
        shared ActorRegistry entry used by AbilityExecutionService and other
        runtime services, preventing stale per-service actor dictionaries.
        """
        if not hasattr(self, "actor_registry"):
            self.actor_registry = ActorRegistry()
        actor = actor_from_runtime_character(character, self.active_world_id or getattr(character, "world_id", ""))
        self.actor_registry.register(actor)
        character.actor_data = actor.to_dict()
        if getattr(self, "abilities", None):
            self.abilities.actor_registry = self.actor_registry
            self.abilities.actors = self.actor_registry.actors
            if hasattr(self.abilities, "runtime"):
                self.abilities.runtime = self
        registered = self.actor_registry.get(character.id)
        if registered is None or registered.actor_id != character.id:
            raise RuntimeError(f"Canonical actor registration failed for {character.id}")
        if getattr(self, "abilities", None) and self.abilities.actor_registry is not self.actor_registry:
            raise RuntimeError("AbilityExecutionService is not using MudRuntime.actor_registry")

    def unregister_live_character(self, character_id: str) -> None:
        if getattr(self, "actor_registry", None):
            self.actor_registry.unregister(character_id)
        if getattr(self, "abilities", None):
            self.abilities.unregister_actor(character_id)

    def enter_world(self, character_id: str, account_id: str = "", session_id: str = "") -> dict[str, Any]:
        """Enter the loaded world as a SQLite-backed character."""
        if account_id:
            with sqlite3.connect(self.state_store.db_path) as conn:
                row = conn.execute("SELECT account_id FROM characters WHERE id=?", (character_id,)).fetchone()
                if row and row[0] and row[0] != account_id:
                    raise PermissionError("Character does not belong to this account.")
                if row and not row[0]:
                    conn.execute("UPDATE characters SET account_id=? WHERE id=?", (account_id, character_id))
        char = self.state_store.load_character(character_id)
        if char is None:
            raise ValueError(f"Character not found: {character_id}")
        if not self.active_world_id:
            with sqlite3.connect(self.state_store.db_path) as conn:
                row = conn.execute("SELECT world_id FROM characters WHERE id = ?", (character_id,)).fetchone()
            if row and row[0]:
                self.load_world(str(row[0]))
        self._ensure_starter_progression(char)
        self.register_live_character(char)
        self.state_store.save_character(char, self.active_world_id or "")
        self.hooks.emit("player_login", world_id=self.active_world_id or "", character=char)
        self.event_bus.publish("character_loaded", {"character_id": char.id, "character_name": char.name}, source_system="runtime", world_id=self.active_world_id or "", character_id=char.id)
        self.sessions[character_id] = MudSession(
            session_id=session_id or character_id,
            character_id=character_id,
            world_id=self.active_world_id or "",
            connected_at=datetime.now(timezone.utc).isoformat(),
            last_activity=datetime.now(timezone.utc).isoformat(),
        )
        if session_id in self.sessions:
            s = self.sessions[session_id]; s.character_id = character_id; s.world_id = self.active_world_id or ""; s.state = "playing"
        with sqlite3.connect(self.state_store.db_path) as conn:
            conn.execute("UPDATE characters SET last_played_at=CURRENT_TIMESTAMP WHERE id=?", (character_id,))
        self.event_bus.publish("character_selected", {"account_id": account_id, "character_id": char.id, "session_id": session_id}, source_system="runtime", account_id=account_id, world_id=self.active_world_id or "", character_id=char.id, session_id=session_id)
        self.event_bus.publish("character_entered_world", {"account_id": account_id, "character_id": char.id, "character_name": char.name, "room_id": char.room_id, "session_id": session_id}, source_system="runtime", account_id=account_id, world_id=self.active_world_id or "", character_id=char.id, session_id=session_id)
        return {"ok": True, "character": self._character_payload(char, self.active_world_id or ""), "view": self.play_view(character_id)}

    def play_view(self, character_id: str) -> dict[str, Any]:
        """Render the current room through the single MUD display pipeline."""
        char = self.state_store.load_character(character_id) if character_id else None
        if char is None:
            return {"html": "", "text": "Create a character to enter the world.", "prompt": ">"}
        room = self._current_room(char)
        colors = self.get_effective_mud_colors()
        html = render_room(room, colors, char)
        self.event_bus.publish("room_rendered", {"world_id": self.active_world_id or "", "character_id": char.id, "room_id": char.room_id, "output_format": "web_html", "render_kind": "room"}, source_system="render", world_id=self.active_world_id or "", character_id=char.id)
        prompt = render_prompt(char, colors)
        self.event_bus.publish("prompt_rendered", {"world_id": self.active_world_id or "", "character_id": char.id, "room_id": char.room_id, "output_format": "web_html", "render_kind": "prompt"}, source_system="render", world_id=self.active_world_id or "", character_id=char.id)
        async_messages = self.drain_session_output(character_id)
        text = self._room_text(room)
        if async_messages:
            from engine.mud_displays import semantic_html
            html = semantic_html('\n'.join(f'{{combat}}{m}{{/combat}}' for m in async_messages)) + '\n' + html
            text = '\n'.join(async_messages) + '\n' + text
        return {"html": html, "text": text, "prompt": prompt, "room_id": char.room_id, "async_messages": async_messages}


    def _builder_visible(self, char: MudCharacter) -> bool:
        return str(getattr(char, "role", "player")).lower() in BUILDER_ROLES and bool(getattr(char, "builder_mode", False) or getattr(char, "builder_enabled", False))

    def _drafts(self) -> dict[str, Any]:
        return self.builder.load(self.active_world_id or "shattered_realms")

    def _live_room_data(self, room_id: str) -> dict[str, Any] | None:
        if self.active_world is None:
            return None
        try:
            return dict(self.active_world.room(room_id))
        except Exception:
            return None

    def runtime_room_data(self, char: MudCharacter, room_id: str) -> tuple[dict[str, Any] | None, str]:
        """Return a room from the canonical runtime graph: draft overlay, then live world."""
        rid = str(room_id or "")
        if self._builder_visible(char):
            draft = self._drafts().get("rooms", {}).get(rid)
            if isinstance(draft, dict):
                data = dict(draft); data.setdefault("id", rid)
                return data, "draft"
        live = self._live_room_data(rid)
        if live is not None:
            return live, "live"
        return None, "missing"

    def room_from_id(self, room_id: str, viewer: Any = None) -> MudRoom:
        data, _source = self.runtime_room_data(viewer if isinstance(viewer, MudCharacter) else MudCharacter(id="_entity_viewer", name="Entity", role="player", room_id=str(room_id or "")), room_id)
        if data is None:
            return MudRoom(id=str(room_id or "void"), area_id="", title="Missing Room", description=f"Current room '{room_id}' is invalid.", exits=[])
        rid = str(data.get("id", room_id))
        visible = self.find_visible_entities(rid, viewer)
        self._annotate_combat_presence(rid, visible)
        return MudRoom(id=rid, area_id=str(data.get("area_id", "")), title=str(data.get("title") or data.get("name") or rid), description=str(data.get("description") or ""), exits=list(self.canonical_exits(viewer, rid).values()), npcs=visible.get("npcs", []), mobs=visible.get("mobs", []), objects=visible.get("objects", []))

    def canonical_exits(self, char: MudCharacter, room_id: str) -> dict[str, dict[str, Any]]:
        data, _source = self.runtime_room_data(char, room_id)
        raw = (data or {}).get("exits") or {}
        if isinstance(raw, dict):
            return {str(d).lower(): {"direction": str(d).lower(), **(v if isinstance(v, dict) else {"target_room_id": v})} for d, v in raw.items()}
        exits: dict[str, dict[str, Any]] = {}
        for ex in raw if isinstance(raw, list) else []:
            if isinstance(ex, dict):
                d = str(ex.get("direction") or ex.get("dir") or "").lower()
                if d: exits[d] = dict(ex, direction=d)
        return exits

    def resolve_exit(self, char: MudCharacter, room_id: str, direction: str) -> tuple[dict[str, Any] | None, str]:
        ex = self.canonical_exits(char, room_id).get(str(direction or "").lower())
        if not ex: return None, "no_exit"
        if ex.get("hidden"): return ex, "hidden"
        if ex.get("closed"): return ex, "closed"
        if ex.get("locked"): return ex, "locked"
        if ex.get("blocked"): return ex, str(ex.get("blocked_reason") or "blocked")
        target = ex.get("target_room_id") or ex.get("destination_room_id") or ex.get("to") or ex.get("room_id") or ex.get("target")
        if not target: return ex, "missing target_room_id"
        target_data, _ = self.runtime_room_data(char, str(target))
        if target_data is None: return ex, f"target room not found: {target}"
        return {**ex, "target_room_id": str(target)}, "ok"

    def all_runtime_rooms(self, char: MudCharacter) -> dict[str, tuple[dict[str, Any], str]]:
        rooms: dict[str, tuple[dict[str, Any], str]] = {}
        if self.active_world is not None:
            for raw in getattr(self.active_world, "rooms", []) or []:
                if isinstance(raw, dict) and raw.get("id"):
                    rooms[str(raw["id"])] = (dict(raw), "live")
        if self._builder_visible(char):
            for rid, raw in self._drafts().get("rooms", {}).items():
                if isinstance(raw, dict):
                    rooms[str(rid)] = (dict(raw), "draft")
        return rooms

    def goto_room(self, char: MudCharacter, room_id: str) -> tuple[bool, str]:
        data, source = self.runtime_room_data(char, room_id)
        if data is None:
            return False, f"Room not found: {room_id}"
        previous = char.room_id
        setattr(char, "last_room_id", previous)
        char.room_id = str(data.get("id") or room_id)
        if self._builder_visible(char):
            setattr(char, "edit_room_id", char.room_id)
            setattr(char, "last_edited_target", char.room_id)
            setattr(char, "current_target_type", "room")
            setattr(char, "current_target_id", char.room_id)
            setattr(char, "current_target_name", str(data.get("name") or data.get("title") or char.room_id))
            self.builder.publish("builder_target_selected", char, self.active_world_id or "", "room", char.room_id, command="goto")
            self.builder.publish("builder_context_changed", char, self.active_world_id or "", "room", char.room_id, command="goto")
        self.state_store.save_character(char, self.active_world_id or "")
        self.builder.audit(char, self.active_world_id or "", "goto", "room", char.room_id, {"room_id": previous}, {"room_id": char.room_id, "source": source})
        self.event_bus.publish("builder_goto", {"character_id": char.id, "world_id": self.active_world_id or "", "room_id": previous, "target_id": char.room_id, "source": source}, source_system="builder", world_id=self.active_world_id or "", character_id=char.id, room_id=char.room_id)
        return True, f"You have been transferred to {char.room_id}."

    def _builder_nav_command(self, char: MudCharacter, cmd: str, args: list[str], raw: str):
        from engine.mud_commands import CommandResult
        if cmd in {"goto", "home"} and str(getattr(char, "role", "player")).lower() not in BUILDER_ROLES:
            return CommandResult("You do not have permission for that command.", ok=False)
        if cmd == "home":
            args = [getattr(self.active_world, "default_starting_room_id", "") or "start"]
            cmd = "goto"
        if cmd == "where":
            data, _source = self.runtime_room_data(char, char.room_id)
            name = (data or {}).get("name") or (data or {}).get("title") or char.room_id
            return CommandResult(f"You are in {name} ({char.room_id}).")
        if cmd == "rwhere":
            room_id = self.builder.current_room_id(char)
            data, source = self.runtime_room_data(char, room_id)
            name = (data or {}).get("name") or (data or {}).get("title") or "(unnamed)"
            dirty = "yes" if source == "draft" else "no"
            return CommandResult(f"Editing room: {room_id} {name}\nSource: {source}\nDirty: {dirty}")
        if cmd == "goto":
            if not args:
                return CommandResult("Syntax: goto <room_id|room name|last|here|home>", ok=False)
            q = " ".join(args).strip()
            if q.lower() == "here":
                return self._builder_nav_command(char, "rwhere", [], raw)
            if q.lower() == "last":
                q = getattr(char, "last_room_id", "")
                if not q:
                    return CommandResult("No previous room recorded.", ok=False)
            if q.lower() == "home":
                q = getattr(self.active_world, "default_starting_room_id", "") or "start"
            rooms = self.all_runtime_rooms(char)
            target = q if q in rooms else ""
            if not target:
                matches = [rid for rid, (r, _src) in rooms.items() if str(r.get("name") or r.get("title") or "").lower() == q.lower()]
                if len(matches) > 1:
                    return CommandResult("Multiple rooms match:\n" + "\n".join(matches), ok=False)
                if len(matches) == 1:
                    target = matches[0]
            if not target:
                return CommandResult(f"Room not found: {q}", ok=False)
            ok, msg = self.goto_room(char, target)
            if ok and self._builder_visible(char):
                msg = msg + "\n" + self.command_engine._builder_room_status(char, target, self.builder.load(self.active_world_id or ""))
            return CommandResult(msg, ok=ok, state_updates={"render_room": ok})
        if cmd in {"rooms", "rlist"}:
            # Phase 4H list filters (local default, area/zone filters, VNUM
            # ranges, and active draft area/zone counts) live in
            # MudCommandEngine._cmd_builder_nav.  The runtime keeps only the
            # legacy explicit source views so older ``rooms draft`` /
            # ``rooms live`` workflows still render as before; every other
            # room-list form must fall through to the command engine so it
            # reads the active Builder draft workspace instead of the runtime's
            # live/draft source split.
            if not args or args[0].lower() not in {"draft", "live", "unassigned", "legacy"}:
                return None
            filt = (args[0].lower() if args else "draft")
            if filt in {"unassigned", "legacy"}:
                rooms = [(rid, r, src) for rid, (r, src) in self.all_runtime_rooms(char).items() if src == "draft" and not r.get("area_id") and not r.get("zone_id") and r.get("vnum") is None]
                title = "Legacy / Unassigned Rooms"
            else:
                rooms = [(rid, r, src) for rid, (r, src) in self.all_runtime_rooms(char).items() if filt == "all" or src == filt]
                title = {"draft":"Draft Rooms", "live":"Live Rooms", "all":"All Rooms"}.get(filt, "Draft Rooms")
            edit_id = self.builder.current_room_id(char)
            lines = [title, "", "ID | Name | Exits | Markers"]
            for rid, r, _src in sorted(rooms):
                markers = []
                if rid == char.room_id: markers.append("current location")
                if rid == edit_id: markers.append("current edit target")
                lines.append(f"{rid} | {r.get('name') or r.get('title') or rid} | {len((r.get('exits') or {}))} | {', '.join(markers) or '-'}")
            lines += ["", "Current location:", char.room_id, "", "Current edit target:", edit_id]
            self.event_bus.publish("builder_room_listed", {"character_id": char.id, "count": len(rooms)}, source_system="builder")
            return CommandResult("\n".join(lines))
        if cmd in {"rfind", "rsearch"}:
            q = " ".join(args).lower()
            if not q:
                return CommandResult("Usage: rfind <query>", ok=False)
            out = []
            for rid, (r, src) in self.all_runtime_rooms(char).items():
                if q and q in json.dumps(r).lower():
                    out.append(f"{rid} | {r.get('name') or r.get('title') or rid} | {src}")
            self.event_bus.publish("builder_room_searched", {"character_id": char.id, "query": q, "count": len(out)}, source_system="builder")
            return CommandResult("Room search results:\n" + ("\n".join(out) if out else "No rooms found."))
        if cmd == "exits":
            edict = self.canonical_exits(char, self.builder.current_room_id(char))
            dirs=["north","south","east","west","up","down"]
            lines=[]
            for d in dirs:
                ex=edict.get(d) or {}; tgt=ex.get("target_room_id") or ex.get("destination_room_id") or ex.get("to") or ex.get("room_id") or "none"
                lines.append(f"{d.title()} -> {tgt}")
            return CommandResult("\n".join(lines))
        if cmd in {"back", "forward"}:
            return CommandResult("Builder navigation history is available while Builder Mode is on. Use goto last for the previous location.")
        if cmd in {"examine", "x"} and len(args)>=2 and args[0].lower()=="exit":
            d=args[1].lower(); edict=self.canonical_exits(char, self.builder.current_room_id(char)); ex=edict.get(d) or {}; tgt=ex.get("target_room_id") or ex.get("destination_room_id") or ex.get("to") or ex.get("room_id") or "none"; rev={"north":"south","south":"north","east":"west","west":"east","up":"down","down":"up"}.get(d, "")
            status="Valid" if tgt != "none" and self.runtime_room_data(char, str(tgt))[0] is not None else "Missing"
            return CommandResult("\n".join(["Direction:", d.title(), "", "Destination:", str(tgt), "", "Reverse:", rev.title(), "", "Status:", status]))
        if cmd in {"map", "rmap"}:
            data, _source = self.runtime_room_data(char, char.room_id)
            lines = [f"Current: {char.room_id} {(data or {}).get('name') or (data or {}).get('title') or char.room_id}"]
            edict = self.canonical_exits(char, char.room_id)
            for d in ["north", "south", "east", "west", "up", "down", "in", "out"]:
                ex = edict.get(d) or {}
                tgt = ex.get("target_room_id") or ex.get("destination_room_id") or ex.get("to") or ex.get("room_id") or "-"
                tr, _ = self.runtime_room_data(char, tgt) if tgt != "-" else (None, "")
                lines.append(f"{d.title()}: {tgt} {((tr or {}).get('name') or (tr or {}).get('title') or '')}")
            self.event_bus.publish("builder_map_rendered", {"character_id": char.id, "room_id": char.room_id}, source_system="builder")
            return CommandResult("\n".join(lines))
        return None

    def handle_input(self, character_id: str, command: str) -> dict[str, Any]:
        """Execute a command and persist command/output scrollback to SQLite."""
        self.process_due_entity_respawns()
        char = self.state_store.load_character(character_id)
        if char is None:
            raise ValueError(f"Character not found: {character_id}")
        self.register_live_character(char)
        if getattr(char, "builder_desc_editor_room_id", ""):
            from engine.mud_commands import CommandResult
            line = command.rstrip("\n")
            if line.strip() == ".cancel":
                setattr(char, "builder_desc_editor_room_id", ""); setattr(char, "builder_desc_editor_lines", [])
                result = CommandResult("Description edit cancelled.")
            elif line.strip() == ".end":
                rid = getattr(char, "builder_desc_editor_room_id", "")
                text = "\n".join(getattr(char, "builder_desc_editor_lines", []) or [])
                self.builder.create_or_update(char, "rooms", rid, {"description": text}, "rdesc", "room")
                setattr(char, "builder_desc_editor_room_id", ""); setattr(char, "builder_desc_editor_lines", [])
                data = self.builder.load(self.active_world_id or "").get("rooms",{}).get(rid,{})
                result = CommandResult("\n".join(["Updated room:", "", "ID:", rid, "", "Name:", data.get("name") or "(unnamed)", "", "Dirty:", "yes"]) + "\n" + self.command_engine._builder_room_status(char, rid, self.builder.load(self.active_world_id or "")))
            else:
                lines = list(getattr(char, "builder_desc_editor_lines", []) or []); lines.append(line); setattr(char, "builder_desc_editor_lines", lines)
                result = CommandResult("")
        else:
            if command.strip() in {".end", ".cancel"}:
                from engine.mud_commands import CommandResult
                result = CommandResult("No active editor session.", ok=False)
            else:
                result = self._handle_runtime_command(char, command)
        self.state_store.save_character(char, self.active_world_id or "")
        session = self.sessions.get(character_id)
        turn = (session.command_count + 1) if session else 1
        self.state_store.save_command(character_id, self.active_world_id or "", turn, command, session.account_id if session else "", session.session_id if session else "")
        if getattr(result, "display_document", None) is not None:
            color_enabled = not bool(getattr(char, "preferences", {}).get("no_color"))
            result.narrative = render_display_mud(result.display_document, color_enabled=color_enabled)
        self.state_store.save_scrollback(character_id, self.active_world_id or "", turn, result.narrative)
        if session:
            session.command_count = turn
            session.last_activity = datetime.now(timezone.utc).isoformat()
        async_messages = self.drain_session_output(character_id)
        if async_messages:
            result.narrative = (result.narrative + '\n' if result.narrative else '') + '\n'.join(async_messages)
            self.state_store.save_scrollback(character_id, self.active_world_id or '', turn, '\n'.join(async_messages))
        updates = result.state_updates or {}
        view = self.play_view(character_id)
        if updates.get("session_transition") == "character_select":
            view = {"html": "", "text": result.narrative, "prompt": ">"}
        return {"ok": result.ok, "output": render_semantic_plain(result.narrative), "semantic_output": result.narrative, "state_updates": updates, "view": view}


    ROOM_FEATURE_NAMES = {"gate", "door", "fountain", "altar", "statue", "portal", "stairs", "bridge", "campfire", "lever", "button", "switch", "sign", "notice board", "board", "stall", "provisioner stall", "window", "windows", "tree", "water", "chest", "lock"}
    FILLER_BY_COMMAND = {"look": {"at"}, "examine": {"at"}, "drink": {"from"}, "get": {"from"}, "put": {"in", "into", "on"}}

    def _parse_interaction_command(self, command: str) -> dict[str, Any]:
        text = re.sub(r"\s+", " ", str(command or "").strip())
        words = text.split()
        if not words:
            return {"tokens": [], "raw_cmd": "", "cmd": "", "args": []}
        lower = [w.lower() for w in words]
        # Player command parsing is longest-valid-match first.  This prevents
        # multiword abilities such as "set camp" and "build campfire" from
        # being reduced to builder/admin verbs or falling through to CAST.
        ability_cmd = self._match_player_ability_command(words)
        if ability_cmd:
            logger.debug("mud parser raw=%r normalized=%r entry=%r args=%r", command, text.lower(), ability_cmd["cmd"], ability_cmd["args"])
            return ability_cmd
        raw = lower[0]
        alias_note = ""
        if raw in {"in", "out"}:
            cmd = raw; args = words[1:]
        elif raw == "pick" and len(lower) > 1 and lower[1] == "up":
            cmd = "get"; args = words[2:]; alias_note = "pick up"
        elif raw == "pickup":
            cmd = "get"; args = words[1:]; alias_note = "pickup"
        else:
            resolved, kind = self.command_engine.registry.resolve(raw)
            cmd = self.command_engine.resolve_alias(raw); args = words[1:]
            if kind.startswith("ambiguous"):
                return {"tokens": words, "raw_cmd": raw, "cmd": "", "args": args, "alias_note": kind}
        if raw in {"inspect"}:
            cmd = "examine"
        if cmd in {"look", "examine"} and args and args[0].lower() in {"at", "in", "inside"}:
            if args[0].lower() in {"in", "inside"}: alias_note = "look in"
            args = args[1:]
        elif cmd in self.FILLER_BY_COMMAND and args and args[0].lower() in self.FILLER_BY_COMMAND[cmd]:
            args = args[1:]
        parsed = {"tokens": words, "raw_cmd": raw, "cmd": cmd, "args": args, "alias_note": alias_note}
        logger.debug("mud parser raw=%r normalized=%r entry=%r args=%r", command, text.lower(), cmd, args)
        return parsed

    def _match_player_ability_command(self, words: list[str]) -> dict[str, Any] | None:
        phrase = " ".join(words).lower().strip()
        ability_phrases = self._player_ability_phrases()
        if phrase in ability_phrases:
            return {"tokens": words, "raw_cmd": phrase, "cmd": "use", "args": phrase.split(), "alias_note": "ability command"}
        return None

    def _player_ability_phrases(self) -> dict[str, str]:
        phrases: dict[str, str] = {}
        svc = getattr(self, "abilities", None)
        registry = getattr(svc, "registry", None)
        for ab in getattr(registry, "abilities", {}).values() if registry is not None else []:
            pdata = getattr(ab, "plugin_data", {}) or {}
            canonical = str(pdata.get("command") or pdata.get("usage") or getattr(ab, "short_name", "") or getattr(ab, "name", "") or getattr(ab, "id", "")).lower().strip()
            canonical = re.sub(r"^(use|cast|perform|invoke)\s+", "", canonical)
            candidates = [canonical, str(getattr(ab, "name", "") or "").lower(), str(getattr(ab, "short_name", "") or "").lower(), str(getattr(ab, "id", "") or "").replace("_", " ").lower()]
            aliases = pdata.get("aliases") or []
            if isinstance(aliases, str):
                aliases = [aliases]
            candidates.extend(str(a).lower() for a in aliases)
            for item in candidates:
                item = re.sub(r"\s+", " ", item).strip()
                if item:
                    phrases[item] = canonical or item
        return phrases

    def _suggest_player_ability_command(self, phrase: str) -> str:
        import difflib
        normalized = re.sub(r"\s+", " ", str(phrase or "").lower()).strip()
        phrases = self._player_ability_phrases()
        public = sorted(set(phrases.values()))
        if normalized == "set campfire" and "build campfire" in public:
            return "build campfire"
        matches = difflib.get_close_matches(normalized, public, n=1, cutoff=0.62)
        return matches[0] if matches else ""

    def _publish_interaction_event(self, name: str, char: MudCharacter, cmd: str, raw: str, extra: dict[str, Any] | None = None) -> None:
        payload = {"world_id": self.active_world_id or "", "character_id": char.id, "character_name": char.name, "room_id": char.room_id, "canonical_command": cmd, "raw_input": raw, **(extra or {})}
        self.event_bus.publish(name, payload, source_system="interaction", world_id=self.active_world_id or "", character_id=char.id, command=raw, room_id=char.room_id)

    def _room_features(self, room: MudRoom) -> list[dict[str, Any]]:
        hay = f"{room.id} {room.title} {room.description}".lower()
        features = list(self._resolved_room_features(room.id, None))
        try:
            drafts = self.builder.load(self.active_world_id or "").get("rooms", {}).get(room.id, {}).get("features", {})
            for fid, feat in drafts.items() if isinstance(drafts, dict) else []:
                if isinstance(feat, dict):
                    features.append({**feat, "feature_id": fid, "entity_type": "room_feature", "keywords": [fid, *feat.get("keywords", [])] if isinstance(feat.get("keywords", []), list) else [fid]})
        except Exception:
            pass
        # Room object ids may describe fixed scenery rather than portable items.
        if self.active_world is not None:
            try:
                room_data = self.active_world.room(room.id)
                for raw_obj in room_data.get("objects", []) or []:
                    oid = str(raw_obj.get("template_id") or raw_obj.get("id") if isinstance(raw_obj, dict) else raw_obj)
                    tmpl = dict(self.item_templates.get(oid, {}))
                    if tmpl and not tmpl.get("portable", True):
                        features.append({**tmpl, "feature_id": oid, "entity_type": "room_feature"})
            except Exception:
                pass
        for name in sorted(self.ROOM_FEATURE_NAMES):
            if name in hay or name in {"gate", "fountain", "chest", "lock"}:
                features.append({"name": name.title(), "keywords": [name], "feature_id": name, "entity_type": "room_feature"})
        for ex in room.exits:
            direction = str(ex.get("direction") or ex.get("dir") or "").lower() if isinstance(ex, dict) else ""
            if direction:
                features.append({"name": direction.title(), "keywords": [direction], "feature_id": direction, "entity_type": "exit", "long_description": ex.get("description") if isinstance(ex, dict) else ""})
        # De-duplicate by feature id/name while preserving first useful metadata.
        seen = set(); unique = []
        for f in features:
            key = str(f.get("feature_id") or f.get("name")).lower()
            if key not in seen:
                seen.add(key); unique.append(f)
        return unique

    def _resolve_interaction_target(self, char: MudCharacter, query: str) -> dict[str, Any]:
        features = self._room_features(self._current_room(char))
        qnorm = " ".join([w for w in re.findall(r"[a-z0-9_']+", query.lower()) if w not in self.ARTICLES])
        exact_features = [f for f in features if qnorm and (str(f.get("name", "")).lower() == qnorm or qnorm == str(f.get("feature_id", "")).lower().replace("_", " "))]
        keyword_features = [f for f in features if qnorm and qnorm in [str(k).lower() for k in f.get("keywords", [])]]
        rich_keyword_features = [f for f in keyword_features if f.get("long_description") or f.get("description") or f.get("short_description")]
        chosen_features = rich_keyword_features or exact_features
        if len(chosen_features) == 1:
            return {"status": "ok", "kind": "feature", "target": chosen_features[0]}
        player_candidates = [
            {"name": p.get("name"), "keywords": [p.get("name", "").lower(), *str(p.get("name", "")).lower().split()], "entity_type": "player", "level": p.get("level", 1)}
            for p in self.list_characters(self.active_world_id or "")
            if p.get("room_id") == char.room_id and p.get("character_id") != char.id
        ]
        groups = [
            ("player", player_candidates),
            ("npc", self.find_visible_entities(char.room_id, char).get("npcs", [])),
            ("mob", self.find_visible_entities(char.room_id, char).get("mobs", [])),
            ("corpse", self.find_visible_entities(char.room_id, char).get("corpses", [])),
            ("equipped", self.find_equipped_items(char.id)),
            ("inventory", self.find_inventory_items(char.id)),
            ("room_object", self.get_visible_room_items(char.room_id)),
            ("exit", [{"name": str(e.get("direction") or e.get("dir")), "keywords": [str(e.get("direction") or e.get("dir"))], "entity_type": "exit", "exit": e, "long_description": e.get("description", "")} for e in self._current_room(char).exits if isinstance(e, dict)]),
            ("world_object", self._runtime_world_objects(char.room_id)),
            ("feature", features),
        ]
        for kind, candidates in groups:
            res = self.resolve_entity_keywords(query, candidates) if kind in {"player", "npc", "mob", "corpse", "exit", "feature", "world_object"} else self.resolve_item_keywords(query, candidates)
            if res.get("status") == "ok": return {"status": "ok", "kind": kind, "target": res.get("entity") or res.get("item")}
            if res.get("status") == "ambiguous": return {"status": "ambiguous", "matches": res.get("matches", [])}
        return {"status": "missing", "matches": []}

    def _handle_interaction_command(self, char: MudCharacter, cmd: str, args: list[str], raw: str):
        from engine.mud_commands import CommandResult
        q = " ".join(args).strip()
        interaction_cmds = {"look", "examine", "identify", "use", "read", "taste", "fill", "pour", "pray", "touch", "push", "pull", "climb", "enter", "leave", "drink", "eat", "open", "close", "lock", "unlock", "pick", "search", "listen", "smell", "sit", "stand", "rest", "sleep", "wake", "give", "put"}
        if cmd not in interaction_cmds:
            return None
        self._publish_interaction_event("interaction_attempted", char, cmd, raw, {"target_query": q})
        if cmd == "identify":
            self._publish_interaction_event("identify_attempted", char, cmd, raw, {"target_query": q})
            self._publish_interaction_event("identify_requested", char, cmd, raw, {"target_query": q})
        if cmd == "read":
            self._publish_interaction_event("read_requested", char, cmd, raw, {"target_query": q})
        if cmd == "use":
            self._publish_interaction_event("use_requested", char, cmd, raw, {"target_query": q})
        if cmd in {"look", "examine"} and q.lower() in {"room", "around"}:
            return None
        if cmd in {"look", "examine"} and q.lower() in {"self", "me", "myself"}:
            msg = self._render_self_examination(char)
            self._publish_interaction_event("self_examined", char, cmd, raw, {"result_summary": msg[:120]})
            return CommandResult(msg)
        if cmd in {"look", "examine"} and re.match(r"^\s*(look|l|examine|exa)\s+(in|inside)\b", raw, re.I):
            resolved_container = self._resolve_interaction_target(char, q)
            self._log_inspection_route(raw, cmd, q, resolved_container, "look_inside")
            if resolved_container.get("status") != "ok":
                return CommandResult(self._resolve_message(resolved_container, "You don't see that."), ok=False)
            return CommandResult(self._look_in_container(char, resolved_container.get("target", {})))
        if cmd in {"search", "listen", "smell"} and not q:
            messages = {"search": "You see nothing unusual.", "listen": "You do not hear anything unusual.", "smell": "You smell nothing unusual."}
            self._publish_interaction_event("environment_inspected", char, cmd, raw, {"result_summary": messages[cmd]})
            self._publish_interaction_event("interaction_succeeded", char, cmd, raw, {"result_summary": messages[cmd]})
            return CommandResult(messages[cmd])
        if not q:
            if cmd in {"look", "examine"}:
                return None
            prompts = {"enter": "Enter what?", "drink": "Drink from what?", "eat": "Eat what?", "open": "Open what?", "close": "Close what?", "put": "Put what where?", "give": "Give what to whom?", "identify": "Identify what?", "use": "Use what?", "read": "Read what?", "taste": "Taste what?", "fill": "Fill what?", "pour": "Pour what?", "pray": "Pray at what?", "touch": "Touch what?", "push": "Push what?", "pull": "Pull what?", "climb": "Climb what?"}
            msg = prompts.get(cmd, f"{cmd.title()} what?")
            self._publish_interaction_event("command_usage", char, cmd, raw, {"usage": self.command_engine.registry.commands.get(cmd).usage if cmd in self.command_engine.registry.commands else cmd, "message": msg})
            return CommandResult(semantic("usage", msg), ok=False)
        resolved = self._resolve_interaction_target(char, q)
        mode = "identify" if cmd == "identify" else "read" if cmd == "read" else "look" if cmd == "look" else "examine" if cmd == "examine" else cmd
        self._log_inspection_route(raw, cmd, q, resolved, f"inspection_dispatcher:{mode}")
        if resolved["status"] == "ambiguous":
            msg = self._resolve_message(resolved, "You don't see that.")
            self._publish_interaction_event("interaction_failed", char, cmd, raw, {"reason": "ambiguous"})
            return CommandResult(msg, ok=False)
        kind = resolved.get("kind", "")
        target = resolved.get("target", {})
        lname = str(target.get("name") or q).lower()
        is_feature = kind in {"feature", "exit"}
        if is_feature:
            self._publish_interaction_event("feature_interaction_attempted", char, cmd, raw, {"target_kind": kind, "target_name": target.get("name", q)})
        event = "container_interaction" if "chest" in lname or kind == "container" or cmd in {"put"} else "entity_interaction" if kind in {"npc", "mob"} else "object_interaction"
        interactions = target.get("default_interactions") or {}
        messages = {
            "identify": "", "use": "Nothing happens. You find no obvious way to use that.", "read": "There is nothing readable here. There is nothing written there.",
            "pray": "You offer a quiet prayer.", "touch": f"You touch {target.get('name', q)}. Nothing happens.", "push": f"You push {target.get('name', q)}, but it does not move.", "pull": f"You pull {target.get('name', q)}, but it does not move.", "climb": "You cannot climb that.",
            "enter": "You cannot enter that.", "leave": "You cannot leave that.", "drink": "You cannot drink from that.", "eat": "You cannot eat that.",
            "open": f"You cannot open {lname}.", "close": f"You cannot close {lname}.", "lock": "You cannot lock that.", "unlock": "You cannot unlock that.", "pick": "You cannot pick that.",
            "search": "You see nothing unusual.", "listen": "You do not hear anything unusual.", "smell": "You smell nothing unusual.", "put": "You cannot put that there.",
            "taste": "You taste nothing unusual.", "fill": "You have no liquid container ready for that.", "pour": "You have no liquid container ready for that.",
            "sit": "You sit down.", "stand": "You stand up.", "rest": "You rest for a moment.", "sleep": "You cannot sleep here.", "wake": "You are awake.",
        }
        if resolved["status"] == "missing":
            msg = f"You do not see {q} here." if cmd in {"look", "examine", "read"} else messages.get(cmd, f"You do not see {q} here.")
            self._publish_interaction_event("interaction_failed", char, cmd, raw, {"reason": "missing", "target_query": q})
            return CommandResult(semantic("warning", msg), ok=False)
        if cmd in {"look", "examine"}:
            msg = self.inspect_target(char, resolved, "LOOK" if cmd == "look" else "EXAMINE")
            if msg:
                event_name = "feature_examined" if kind in {"feature", "exit"} else "entity_examined" if kind in {"player", "npc", "mob"} else "object_examined"
                self._publish_interaction_event(event_name, char, cmd, raw, {"target_kind": kind, "target_name": target.get("name", q), "result_summary": msg[:120]})
            elif kind in {"feature", "exit"}: msg = f"You see nothing unusual about the {lname}."
            else: return None
            self._publish_interaction_event("target_looked", char, cmd, raw, {"target_kind": kind, "target_name": target.get("name", q), "result_summary": msg[:120]})
        elif cmd == "identify":
            msg = self.inspect_target(char, resolved, "IDENTIFY")
        elif cmd == "read":
            msg = self.inspect_target(char, resolved, "READ")
        elif cmd == "drink":
            msg = self._drink_from_target(char, target, kind, q)
        else:
            msg = str(interactions.get(cmd) or ("You drink from the fountain." if cmd == "drink" and target.get("drinkable") else messages.get(cmd, "You see nothing unusual.")))
        if msg in {"Nothing happens.", "Nothing happens. You find no obvious way to use that.", "There is nothing written there.", "There is nothing readable here. There is nothing written there.", "You see nothing unusual."}:
            self._publish_interaction_event("command_placeholder", char, cmd, raw, {"target_kind": kind, "target_name": target.get("name", q), "result_summary": msg})
            msg = semantic("placeholder", msg)
        self._publish_interaction_event(event, char, cmd, raw, {"target_kind": kind, "target_name": target.get("name", q), "result_summary": msg})
        failed = msg.startswith("You cannot") or msg.startswith("There is nothing") or "no obvious way" in msg
        self._publish_interaction_event("interaction_succeeded" if not failed else "interaction_failed", char, cmd, raw, {"target_kind": kind, "target_name": target.get("name", q), "result_summary": msg})
        if is_feature:
            self._publish_interaction_event("feature_interaction_succeeded" if not failed else "feature_interaction_failed", char, cmd, raw, {"target_kind": kind, "target_name": target.get("name", q), "result_summary": msg})
        if cmd in {"search", "listen", "smell", "look", "examine"}:
            self._publish_interaction_event("environment_inspected", char, cmd, raw, {"target_kind": kind, "target_name": target.get("name", q), "result_summary": msg})
        return CommandResult(msg, ok=not failed)

    def _handle_runtime_command(self, char: MudCharacter, command: str):
        normalized_command = re.sub(r"\s+", " ", str(command or "").strip()).lower()
        if normalized_command in getattr(self.command_engine, "SOCIAL_DEFINITIONS", {}):
            return self.command_engine.handle_command(char, command)
        parsed = self._parse_interaction_command(command)
        tokens = parsed["tokens"]
        if not tokens:
            return self.command_engine.handle_command(char, command)
        raw_cmd = parsed["raw_cmd"]
        cmd_name = parsed["cmd"]
        args = parsed["args"]
        ability_suggestion = self._suggest_player_ability_command(normalized_command)
        if ability_suggestion and raw_cmd in {"set", "build", "campfire"} and normalized_command not in self._player_ability_phrases():
            from engine.mud_commands import CommandResult
            return CommandResult(f"Unknown command “{normalized_command}.”\nDid you mean {ability_suggestion.upper()}?", ok=False)
        if raw_cmd == "target" and not self._builder_visible(char):
            cmd_name = "target"
        if raw_cmd == "inspect":
            cmd_name = "examine"
        if raw_cmd == "set" and " ".join(args).lower() == "camp":
            cmd_name = "cast"; args = ["set", "camp"]
        if raw_cmd == "build" and " ".join(args).lower() == "campfire":
            cmd_name = "cast"; args = ["build", "campfire"]
        if not cmd_name and str(parsed.get("alias_note", "")).startswith("ambiguous"):
            from engine.mud_commands import CommandResult
            choices = parsed["alias_note"].split(":", 1)[1].strip()
            return CommandResult(f"Which command did you mean? {choices}", ok=False)
        if raw_cmd in {"rcontents", "istat", "itemstat", "mstat", "estat", "sstat", "seedstat", "entityaudit"}:
            from engine.mud_commands import CommandResult
            if not self._builder_visible(char): return CommandResult("You do not have permission for that command.", ok=False)
            return CommandResult(self._builder_content_diagnostic(char, raw_cmd, args))
        self.event_bus.publish("command_resolved", {"raw_input": command, "canonical_command": cmd_name, "arguments": args, "character_id": char.id, "character_name": char.name, "current_room_id": char.room_id}, source_system="command", world_id=self.active_world_id or "", character_id=char.id, command=command)
        if raw_cmd != cmd_name or parsed.get("alias_note"):
            self._publish_interaction_event("command_alias_resolved", char, cmd_name, command, {"raw_command": raw_cmd, "canonical_command": cmd_name, "arguments": args, "note": parsed.get("alias_note", "")})
        if cmd_name in {"run", "walk"} and args:
            direction = self.command_engine.resolve_alias(args[0].lower())
            if direction in {"north", "south", "east", "west", "up", "down", "in", "out", "northeast", "northwest", "southeast", "southwest"}:
                cmd_name = direction
                args = []
        if cmd_name in {"del", "delete"} and len(args) >= 2 and args[0].lower() in {"dir", "direction", "exit"}:
            cmd_name = "unlink"
            args = [args[1]]
        nav_result = self._builder_nav_command(char, cmd_name, args, command)
        if nav_result is not None:
            result = nav_result
            if result.state_updates and result.state_updates.get("render_room"):
                room_text = self._room_text(self._current_room(char))
                result.narrative = f"{result.narrative}\n\n{room_text}" if result.narrative else room_text
            return result
        dialogue_result = self._handle_dialogue_command(char, cmd_name, args)
        if dialogue_result is not None:
            self.event_bus.publish("command_executed", {"raw_input": command, "canonical_command": cmd_name, "arguments": args, "character_id": char.id, "character_name": char.name, "current_room_id": char.room_id, "result_summary": dialogue_result.narrative[:120]}, source_system="command", world_id=self.active_world_id or "", character_id=char.id, command=command)
            return dialogue_result
        if cmd_name in {"look", "examine"} and args:
            feature_result = self._handle_interaction_command(char, cmd_name, args, command)
            if feature_result is not None:
                self.event_bus.publish("command_executed", {"raw_input": command, "canonical_command": cmd_name, "arguments": args, "character_id": char.id, "character_name": char.name, "current_room_id": char.room_id, "result_summary": feature_result.narrative[:120]}, source_system="command", world_id=self.active_world_id or "", character_id=char.id, command=command)
                return feature_result
            item_preview = self._handle_item_command(char, command, cmd_name, args)
            if item_preview is not None and not item_preview.narrative.startswith("You don't see that") and not item_preview.narrative.startswith("Which do you mean") :
                self.event_bus.publish("command_executed", {"raw_input": command, "canonical_command": cmd_name, "arguments": args, "character_id": char.id, "character_name": char.name, "current_room_id": char.room_id, "result_summary": item_preview.narrative[:120]}, source_system="command", world_id=self.active_world_id or "", character_id=char.id, command=command)
                return item_preview
            entity_result = self._look_entity(char.id, char.room_id, " ".join(args))
            if entity_result is not None:
                from engine.mud_commands import CommandResult
                return CommandResult(entity_result)
        if cmd_name in {"cast", "invoke", "perform", "ability", "abilities", "skills", "spells", "cancel", "cooldowns", "abilitylist", "abilitystat", "abilitycreate", "abilityclone", "abilityset", "abilitydelete", "abilityvalidate", "abilitypreview", "abilitytrace", "loadoutlist", "loadoutstat", "loadoutcreate", "loadoutclone", "loadoutset", "loadoutability", "loadoutdelete", "loadoutvalidate", "abilitygrant", "abilityrevoke", "actorabilities", "abilitycooldowns", "abilitycasts"}:
            return self.command_engine.handle_command(char, command)
        if cmd_name == "use" and " ".join(args).lower() in self._player_ability_phrases():
            return self.command_engine.handle_command(char, "use " + " ".join(args))
        item_result = self._handle_item_command(char, command, cmd_name, args)
        if item_result is not None:
            self.event_bus.publish("command_executed", {"raw_input": command, "canonical_command": cmd_name, "arguments": args, "character_id": char.id, "character_name": char.name, "current_room_id": char.room_id, "result_summary": item_result.narrative[:120]}, source_system="command", world_id=self.active_world_id or "", character_id=char.id, command=command)
            return item_result
        interaction_result = self._handle_interaction_command(char, cmd_name, args, command)
        if interaction_result is not None:
            self.event_bus.publish("command_executed", {"raw_input": command, "canonical_command": cmd_name, "arguments": args, "character_id": char.id, "character_name": char.name, "current_room_id": char.room_id, "result_summary": interaction_result.narrative[:120]}, source_system="command", world_id=self.active_world_id or "", character_id=char.id, command=command)
            return interaction_result
        if cmd_name in {"north", "south", "east", "west", "up", "down", "in", "out"}:
            result = self._move_character(char, cmd_name)
            self.event_bus.publish("command_executed", {"raw_input": command, "canonical_command": cmd_name, "arguments": args, "character_id": char.id, "character_name": char.name, "current_room_id": char.room_id, "result_summary": result.narrative[:120]}, source_system="command", world_id=self.active_world_id or "", character_id=char.id, command=command)
        else:
            result = self.command_engine.handle_command(char, command)
        if result.state_updates and result.state_updates.get("render_room"):
            room_text = self._room_text(self._current_room(char))
            result.narrative = f"{result.narrative}\n\n{room_text}" if result.narrative else room_text
        return result

    def _move_character(self, char: MudCharacter, direction: str, bypass_combat: bool = False):
        from engine.mud_commands import CommandResult
        room_id = char.room_id
        if not bypass_combat and getattr(self, 'combat_runtime', None) and self.combat_runtime.is_actor_in_active_combat(self.combat_runtime.actor_id_for_character(char)):
            return CommandResult(narrative='You are fighting! Use FLEE to escape.', ok=False)
        self.event_bus.publish("movement_attempted", {"canonical_command": direction, "character_id": char.id, "character_name": char.name, "current_room_id": room_id}, source_system="movement", world_id=self.active_world_id or "", character_id=char.id, command=direction)
        exit_data, reason = self.resolve_exit(char, room_id, direction)
        if exit_data and reason == "ok":
            old_room = room_id
            char.room_id = str(exit_data["target_room_id"])
            self.state_store.save_character(char, self.active_world_id or "")
            reverse = {"north":"south","south":"north","east":"west","west":"east","up":"down","down":"up","in":"out","out":"in","northeast":"southwest","southwest":"northeast","northwest":"southeast","southeast":"northwest"}.get(direction, direction)
            self.deliver_room_action(old_room, f"{char.name} leaves {direction}.", actor_id=char.id, category="actor_departed")
            self.deliver_room_action(char.room_id, f"{char.name} arrives from the {reverse}.", actor_id=char.id, category="actor_arrived")
            self.event_bus.publish("movement_succeeded", {"canonical_command": direction, "character_id": char.id, "character_name": char.name, "current_room_id": room_id, "target_room_id": char.room_id, "result_summary": "moved"}, source_system="movement", world_id=self.active_world_id or "", character_id=char.id, command=direction)
            return CommandResult(narrative=f"You travel {direction}.", state_updates={"render_room": True}, display_intent="MOVEMENT", semantic_role="success")
        summary = reason if exit_data else "no_exit"
        if exit_data:
            self.event_bus.publish("builder_exit_graph_mismatch_detected", {"character_id": char.id, "room_id": room_id, "direction": direction, "reason": summary}, source_system="builder", world_id=self.active_world_id or "", character_id=char.id, room_id=room_id)
        self.event_bus.publish("movement_failed", {"canonical_command": direction, "character_id": char.id, "character_name": char.name, "current_room_id": room_id, "result_summary": summary}, source_system="movement", world_id=self.active_world_id or "", character_id=char.id, command=direction)
        return CommandResult(narrative="You cannot go that way." if summary == "no_exit" else f"You cannot go that way: {summary}.", ok=False)

    def update_entity_state(self, entity_id: str, updates: dict[str, Any], **_ctx: Any) -> dict[str, Any] | None:
        ent = self.find_entity(entity_id)
        if not ent: return None
        state = dict(ent.get("state") or {}); state.update(updates or {})
        with sqlite3.connect(self.state_store.db_path) as conn:
            conn.execute("UPDATE entity_instances SET state=?,updated_at=? WHERE entity_id=? AND destroyed_at IS NULL", (json.dumps(state), datetime.now(timezone.utc).isoformat(), entity_id))
        return self.find_entity(entity_id)

    def move_entity_actor(self, ent: dict[str, Any], direction: str, bypass_combat: bool = False):
        from engine.mud_commands import CommandResult
        eid = str(ent.get("instance_id") or ent.get("entity_id") or "")
        actor_id = "entity:" + eid
        room_id = str(ent.get("room_id") or ent.get("current_room_id") or "")
        if not bypass_combat and getattr(self, "combat_runtime", None) and self.combat_runtime.is_actor_in_active_combat(actor_id):
            return CommandResult(narrative="The actor is fighting and cannot move normally.", ok=False)
        self.event_bus.publish("movement_attempted", {"canonical_command": direction, "actor_id": actor_id, "entity_id": eid, "current_room_id": room_id}, source_system="movement", world_id=self.active_world_id or "", command=direction)
        exit_data, reason = self.resolve_exit(ent, room_id, direction)
        if exit_data and reason == "ok":
            new_room = str(exit_data["target_room_id"])
            with sqlite3.connect(self.state_store.db_path) as conn:
                conn.execute("UPDATE entity_instances SET current_room_id=?,owner_type='room',owner_id='',updated_at=? WHERE entity_id=? AND destroyed_at IS NULL", (new_room, datetime.now(timezone.utc).isoformat(), eid))
            reverse = {"north":"south","south":"north","east":"west","west":"east","up":"down","down":"up","in":"out","out":"in","northeast":"southwest","southwest":"northeast","northwest":"southeast","southeast":"northwest"}.get(direction, direction)
            name = str(ent.get("name") or "Someone")
            self.deliver_room_action(room_id, f"{name} leaves {direction}.", actor_id=actor_id, category="actor_departed")
            self.deliver_room_action(new_room, f"{name} arrives from the {reverse}.", actor_id=actor_id, category="actor_arrived")
            self.event_bus.publish("movement_succeeded", {"canonical_command": direction, "actor_id": actor_id, "entity_id": eid, "current_room_id": room_id, "target_room_id": new_room, "result_summary": "moved"}, source_system="movement", world_id=self.active_world_id or "", command=direction)
            return CommandResult(narrative=f"{name} heads {direction}.", state_updates={"render_room": True})
        summary = reason if exit_data else "no_exit"
        self.event_bus.publish("movement_failed", {"canonical_command": direction, "actor_id": actor_id, "entity_id": eid, "current_room_id": room_id, "result_summary": summary}, source_system="movement", world_id=self.active_world_id or "", command=direction)
        return CommandResult(narrative="Cannot go that way." if summary == "no_exit" else f"Cannot go that way: {summary}.", ok=False)

    def _room_text(self, room: MudRoom) -> str:
        from smart_mud.transport import html_to_plain_text
        return html_to_plain_text(render_room(room, self.get_effective_mud_colors()))

    def _builder_content_diagnostic(self, char: MudCharacter, cmd: str, args: list[str]) -> str:
        q = " ".join(args).strip()
        if cmd == "rcontents":
            rid = char.room_id if q in {"", "here"} else q
            contents = self.get_room_contents(rid, char, include_builder_metadata=True)
            mats=[]
            with sqlite3.connect(self.state_store.db_path) as conn:
                for row in conn.execute("SELECT declaration_kind,declaration_id,status,instance_ids_json FROM content_materializations WHERE world_id=? ORDER BY declaration_kind,declaration_id", (self.active_world_id or "",)):
                    mats.append(f"{row[0]} {row[1]} {row[2]} {row[3]}")
            legacy = self._legacy_room_entity_declarations(rid)
            lines=[f"Room: {rid}", "Resolved source: canonical runtime content", "Features:"]
            lines += [f"- {f.get('id')}: {f.get('name')} portable={f.get('portable', False)} source={f.get('source','')}" for f in contents['features']] or ["- none"]
            lines += ["Runtime item instances:"] + ([f"- {i.get('instance_id')} template={i.get('template_id')} name={i.get('name')} location={i.get('owner_type')}:{i.get('room_id') or i.get('owner_id')} portable={(i.get('template') or {}).get('portable', True)} seed={(i.get('custom_flags') or {}).get('source_seed_id','')}" for i in contents['item_instances']] or ["- none"])
            lines += ["Runtime entity instances:"] + ([f"- {e.get('instance_id')} template={e.get('template_id')} name={e.get('name')} type={e.get('entity_type')} room={e.get('room_id')} spawn={(e.get('state') or {}).get('source_spawn_id','')}" for e in contents['entity_instances']] or ["- none"])
            lines += ["Players:", "- none", "Item placement declarations:"] + ([f"- {p.get('id')} template={p.get('item_template_id')} room={p.get('room_id')} qty={p.get('quantity')} policy={p.get('seed_policy','once')}" for p in contents.get('item_placement_declarations', [])] or ["- none"])
            lines += ["Entity spawn declarations:"] + ([f"- {sp.get('id')} template={sp.get('entity_template_id')} room={sp.get('room_id')} qty={sp.get('quantity')} policy={sp.get('spawn_policy','once')}" for sp in contents.get('entity_spawn_declarations', [])] or ["- none"])
            lines += ["Legacy room NPC declarations:"] + ([f"- source_file=rooms/rooms.json source_field={d.get('source')} template={d.get('template_id')} name={d.get('name')} room={d.get('room_id')} normalized_spawn={self._legacy_spawn_id(d.get('room_id',''), d.get('template_id',''))} status=superseded_or_normalized" for d in legacy] or ["- none"])
            lines += ["Builder draft entity declarations:", "- not merged into ordinary runtime rendering"]
            lines += ["Materialization records:"] + (mats or ["- none"])
            lines += ["Rendering source:", "- runtime entity instances only", "Duplicate risks:", "- none"]
            return "\n".join(lines)
        if cmd == "entityaudit":
            target = char.room_id if q in {"", "here"} else q
            return self.entity_duplication_audit(target)
        if cmd in {"istat", "itemstat"}:
            item = self.find_item(q) or (self.resolve_item_keywords(q, self.get_visible_room_items(char.room_id)).get('item') if q else None)
            if not item: return "Item not found."
            return "\n".join([f"Instance ID: {item['instance_id']}", f"Template ID: {item['template_id']}", f"Current location: {item['owner_type']}:{item.get('room_id') or item.get('owner_id')}", f"Portable: {(item.get('template') or {}).get('portable', True)}", f"Seed declaration ID: {(item.get('custom_flags') or {}).get('source_seed_id','')}", f"Created: {item.get('created_at')}", f"Custom state: {item.get('custom_flags')}"])
        if cmd in {"mstat", "estat"}:
            ent = self.find_entity(q) or (self.resolve_entity_keywords(q, self.find_room_entities(char.room_id)).get('entity') if q else None)
            if not ent: return "Entity not found."
            return "\n".join([f"Instance ID: {ent['instance_id']}", f"Template ID: {ent['template_id']}", f"Room: {ent.get('room_id')}", f"Entity type: {ent.get('entity_type')}", f"Alive/visible: {ent.get('is_alive')}/{ent.get('is_visible')}", f"Spawn declaration ID: {(ent.get('state') or {}).get('source_spawn_id','')}", f"AI profile: {((ent.get('plugin_data') or {}).get('ai_profile') or {})}", f"Custom state: {ent.get('custom_state')}"])
        kind = 'entity_spawn' if cmd == 'sstat' else 'item_placement'
        row = self._materialization_row(kind, q)
        decl = (self._live_entity_spawns().get(q) if cmd == 'sstat' else self._live_item_placements().get(q)) or {}
        return "\n".join([f"Declaration: {q}", f"Data: {json.dumps(decl, sort_keys=True)}", f"Materialization: {json.dumps(row or {}, sort_keys=True)}"])

    def _annotate_combat_presence(self, room_id: str, visible: dict[str, list[dict[str, Any]]]) -> None:
        cr = getattr(self, 'combat_runtime', None)
        if not cr:
            return
        try:
            import sqlite3
            actor_names: dict[str, str] = {}
            for ent in (visible.get('npcs', []) + visible.get('mobs', [])):
                actor_names['entity:' + str(ent.get('instance_id') or ent.get('entity_id'))] = str(ent.get('name') or 'Someone')
            for ch in self.list_characters(self.active_world_id or ''):
                if ch.get('room_id') == room_id:
                    actor_names['character:' + str(ch.get('character_id'))] = str(ch.get('name') or 'Someone')
            with sqlite3.connect(self.state_store.db_path) as con:
                rows = con.execute("""SELECT p.actor_id,p.current_target_actor_id FROM combat_participants p JOIN combat_encounters e ON e.encounter_id=p.encounter_id WHERE e.room_id=? AND e.status='active' AND p.participation_status='active' AND p.defeated=0 AND p.fled=0""", (room_id,)).fetchall()
            targets = {aid: actor_names.get(tid) or cr.actor_display_name(tid) for aid, tid in rows if tid}
            for ent in (visible.get('npcs', []) + visible.get('mobs', [])):
                aid = 'entity:' + str(ent.get('instance_id') or ent.get('entity_id'))
                if targets.get(aid):
                    ent['combat_target_name'] = targets[aid]
                    st = dict(ent.get('state') or {})
                    st['combat_target_name'] = targets[aid]
                    ent['state'] = st
        except Exception:
            return

    def _current_room(self, char: MudCharacter) -> MudRoom:
        room_data, source = self.runtime_room_data(char, char.room_id)
        if room_data is None:
            return MudRoom(id=char.room_id or "void", area_id="", title="Missing Room", description=f"Current room '{char.room_id}' is invalid. Use goto home or contact a builder.", exits=[])
        rid = str(room_data.get("id", char.room_id))
        visible = self.find_visible_entities(rid, char)
        self._annotate_combat_presence(rid, visible)
        exits = list(self.canonical_exits(char, rid).values())
        features = {f.get("id") or f.get("feature_id"): f for f in self._resolved_room_features(rid, char)}
        feature_keys: set[tuple[str, str]] = set()
        def _norm(value: Any) -> str:
            return str(value or "").strip().lower().replace("_", " ")
        for fid, feat in features.items() if isinstance(features, dict) else []:
            if isinstance(feat, dict):
                feature_keys.add((_norm(fid), _norm(feat.get("name") or fid)))
        objects = []
        for obj in visible.get("objects", []):
            tmpl = obj.get("template") if isinstance(obj, dict) else {}
            portable = bool((tmpl or {}).get("portable", obj.get("portable", True) if isinstance(obj, dict) else True))
            oid = obj.get("template_id") or obj.get("id") if isinstance(obj, dict) else obj
            name = obj.get("name") or (tmpl or {}).get("name") if isinstance(obj, dict) else obj
            duplicate_feature = any(_norm(oid) in key or _norm(name) in key for key in feature_keys)
            if portable or not duplicate_feature:
                objects.append(obj)
        objects.extend(visible.get("corpses", []))
        objects.extend(self._runtime_world_objects(rid))
        seen_features: set[tuple[str, str]] = set()
        for fid, feat in features.items() if isinstance(features, dict) else []:
            if isinstance(feat, dict):
                key = (_norm(fid), _norm(feat.get("name") or fid))
                if key in seen_features:
                    continue
                seen_features.add(key)
                objects.append({"id": fid, "name": feat.get("name") or fid, "short_description": feat.get("short_description", ""), "portable": False})
        return MudRoom(
            id=rid,
            area_id=str(room_data.get("area_id", "")),
            title=str(room_data.get("name") or room_data.get("title") or char.room_id),
            description=str(room_data.get("long_description") or room_data.get("description") or room_data.get("short_description") or ""),
            exits=exits,
            players=visible.get("players", []),
            npcs=visible.get("npcs", []),
            mobs=visible.get("mobs", []),
            objects=objects,
        )

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

    EQUIPMENT_SLOTS = ["head","face","neck","shoulders","back","chest","arms","wrists","hands","finger_left","finger_right","waist","legs","feet","main_hand","off_hand","accessory_1","accessory_2","light"]
    HAND_SLOTS = {"main_hand", "off_hand", "both_hands", "light"}
    ARTICLES = {"a", "an", "the"}

    def _load_item_templates(self) -> None:
        templates: dict[str, MappingProxyType] = {}
        for raw in getattr(self.active_world, "items", []) or []:
            if not isinstance(raw, dict):
                continue
            tid = str(raw.get("id") or raw.get("template_id") or "").strip()
            if not tid:
                continue
            slot = raw.get("slot")
            wear_slots = raw.get("wear_slots") or ([] if not slot or slot == "none" else [slot])
            keywords = raw.get("keywords") or str(raw.get("name") or tid).replace("'", "").split() + [tid]
            norm = {
                "id": tid,
                "name": str(raw.get("name") or tid).title(),
                "keywords": [str(k).lower() for k in keywords if str(k).strip()],
                "short_description": str(raw.get("short_description") or raw.get("description") or raw.get("name") or tid),
                "long_description": str(raw.get("long_description") or raw.get("description") or raw.get("short_description") or raw.get("name") or tid),
                "room_description": str(raw.get("room_description") or raw.get("description") or raw.get("short_description") or raw.get("name") or tid),
                "look_description": str(raw.get("look_description") or raw.get("description") or raw.get("long_description") or raw.get("short_description") or raw.get("name") or tid),
                "examine_description": str(raw.get("examine_description") or raw.get("look_description") or raw.get("long_description") or raw.get("description") or raw.get("short_description") or raw.get("name") or tid),
                "item_type": str(raw.get("item_type") or raw.get("type") or "misc"),
                "weight": raw.get("weight", 0), "value": raw.get("value", 0),
                "wear_slots": [str(v) for v in (raw.get("occupies_slots") or raw.get("equipment_slots") or wear_slots) if str(v) in self.EQUIPMENT_SLOTS],
                "equipment_slots": [str(v) for v in (raw.get("occupies_slots") or raw.get("equipment_slots") or wear_slots) if str(v) in self.EQUIPMENT_SLOTS],
                "occupies_slots": [str(v) for v in (raw.get("occupies_slots") or raw.get("equipment_slots") or wear_slots) if str(v) in self.EQUIPMENT_SLOTS],
                "requires_item_tag": raw.get("requires_item_tag") or raw.get("requires_item_tags") or [],
                "modifiers": list(raw.get("modifiers") or []),
                "weapon_flags": raw.get("weapon_flags") or raw.get("flags") or [],
                "armor_values": raw.get("armor_values") or raw.get("stats") or {},
                "stackable": bool(raw.get("stackable", False)), "max_stack": int(raw.get("max_stack", 1) or 1),
                "rarity": str(raw.get("rarity") or "common"),
                "level_requirement": raw.get("level_requirement") or (raw.get("requirements") or {}).get("level"),
                "lore": raw.get("lore") or "", "plugin_data": raw.get("plugin_data") or {},
                "starter": bool(raw.get("starter") or ("starter" in (raw.get("tags") or []))),
                "starter_quantity": int(raw.get("starter_quantity", 1) or 1),
                "starter_equipped_slot": raw.get("starter_equipped_slot"),
                "portable": bool(raw.get("portable", False if str(raw.get("id") or "").lower().replace("_", " ") in self.ROOM_FEATURE_NAMES or str(raw.get("name") or "").lower() in self.ROOM_FEATURE_NAMES or any(part in str(raw.get("id") or "").lower() for part in ["fountain", "gate", "door", "altar", "statue", "campfire", "stairs", "portal", "notice_board", "stall"]) else True)),
                "drinkable": bool(raw.get("drinkable", False)),
                "enterable": bool(raw.get("enterable", False)),
                "readable": bool(raw.get("readable", False)),
                "readable_text": str(raw.get("readable_text") or raw.get("text") or raw.get("writing") or ""),
                "interaction_hints": raw.get("interaction_hints") or [],
                "usable": bool(raw.get("usable", False)),
                "openable": bool(raw.get("openable", False)),
                "locked": bool(raw.get("locked", False)),
                "locked_message": str(raw.get("locked_message") or "It is locked."),
                "default_interactions": raw.get("default_interactions") or {},
            }
            templates[tid] = MappingProxyType(norm)
        self.item_templates = templates

    def _item_payload(self, row: Any) -> dict[str, Any]:
        item = {"instance_id": row[0], "world_id": row[1], "template_id": row[2], "owner_type": row[3], "owner_id": row[4], "room_id": row[5], "equipped_slot": row[6], "stack_count": row[7], "condition": row[8], "durability": row[9], "created_at": row[10], "updated_at": row[11], "custom_flags": json.loads(row[12] or "{}"), "plugin_data": json.loads(row[13] or "{}")}
        tmpl = dict(self.item_templates.get(item["template_id"], {"id": item["template_id"], "name": item["template_id"], "keywords": [item["template_id"]]}))
        item["template"] = tmpl; item["name"] = tmpl.get("name", item["template_id"]); item["keywords"] = tmpl.get("keywords", [])
        item["description"] = tmpl.get("short_description") or tmpl.get("long_description") or item["name"]
        item["room_description"] = f"{item['name']} - {tmpl.get('short_description') or item['description']}"
        return item

    def _fetch_items(self, where: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
        with sqlite3.connect(self.state_store.db_path) as conn:
            rows = conn.execute(f"SELECT instance_id,world_id,template_id,owner_type,owner_id,room_id,equipped_slot,stack_count,condition,durability,created_at,updated_at,custom_flags,plugin_data FROM item_instances WHERE destroyed_at IS NULL AND {where} ORDER BY created_at, instance_id", params).fetchall()
        return [self._item_payload(r) for r in rows]

    def spawn_item(self, template_id: str, owner_type: str, owner_id: str | None = None, room_id: str | None = None, stack_count: int = 1, equipped_slot: str | None = None, custom_flags: dict[str, Any] | None = None, plugin_data: dict[str, Any] | None = None) -> dict[str, Any]:
        if template_id not in self.item_templates: raise ValueError(f"Unknown item template: {template_id}")
        iid = f"item_{uuid.uuid4().hex}"; now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.state_store.db_path) as conn:
            conn.execute("INSERT INTO item_instances(instance_id,world_id,template_id,owner_type,owner_id,room_id,equipped_slot,stack_count,condition,durability,created_at,updated_at,custom_flags,plugin_data) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (iid,self.active_world_id or "",template_id,owner_type,owner_id or "",room_id or "",equipped_slot or "",int(stack_count or 1),"normal",100,now,now,json.dumps(custom_flags or {}),json.dumps(plugin_data or {})))
        item = self.find_item(iid); self._publish_item_event("item_spawned", item); return item

    def destroy_item(self, instance_id: str, reason: str | None = None) -> bool:
        item = self.find_item(instance_id)
        with sqlite3.connect(self.state_store.db_path) as conn: conn.execute("UPDATE item_instances SET destroyed_at=?, destroy_reason=?, updated_at=? WHERE instance_id=?", (datetime.now(timezone.utc).isoformat(), reason or "", datetime.now(timezone.utc).isoformat(), instance_id))
        if item: self._publish_item_event("item_destroyed", item)
        return bool(item)

    def move_item(self, instance_id: str, owner_type: str, owner_id: str | None = None, room_id: str | None = None, equipped_slot: str | None = None) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.state_store.db_path) as conn: conn.execute("UPDATE item_instances SET owner_type=?, owner_id=?, room_id=?, equipped_slot=?, updated_at=? WHERE instance_id=? AND destroyed_at IS NULL", (owner_type, owner_id or "", room_id or "", equipped_slot or "", now, instance_id))
        return self.find_item(instance_id)

    def transfer_item(self, instance_id: str, from_owner: Any = None, to_owner: Any = None, room_id: str | None = None, equipped_slot: str | None = None, reason: str | None = None) -> dict[str, Any]:
        if isinstance(to_owner, tuple): owner_type, owner_id = to_owner
        elif isinstance(to_owner, dict): owner_type, owner_id = to_owner.get("owner_type"), to_owner.get("owner_id")
        else: owner_type, owner_id = str(to_owner or "room"), None
        return self.move_item(instance_id, owner_type, owner_id, room_id, equipped_slot)

    def find_item(self, instance_id: str) -> dict[str, Any] | None: return next(iter(self._fetch_items("instance_id=?", (instance_id,))), None)
    def find_room_items(self, room_id: str) -> list[dict[str, Any]]: return self._fetch_items("owner_type='room' AND room_id=?", (room_id,))
    def find_inventory_items(self, character_id: str) -> list[dict[str, Any]]: return self._fetch_items("owner_type='character' AND owner_id=?", (character_id,))
    def find_equipped_items(self, character_id: str) -> list[dict[str, Any]]: return self._fetch_items("owner_type='equipment' AND owner_id=?", (character_id,))
    def get_visible_room_items(self, room_id: str) -> list[dict[str, Any]]: return self.find_room_items(room_id)

    def resolve_item_keywords(self, query: str, candidate_items: list[dict[str, Any]]) -> dict[str, Any]:
        numbered = re.match(r"^\s*(\d+)\.([^\s].*)$", str(query or ""), re.I)
        ordinal = int(numbered.group(1)) if numbered else 0
        query = numbered.group(2) if numbered else query
        words = [w for w in re.findall(r"[a-z0-9_']+", query.lower()) if w not in self.ARTICLES]
        q = " ".join(words)
        if not q: return {"status":"missing", "matches": []}
        def name(i): return str(i.get("name") or i.get("template",{}).get("name") or "").lower()
        def choose(matches):
            if ordinal:
                return {"status":"ok","item":matches[ordinal-1],"matches":matches} if len(matches) >= ordinal else {"status":"missing_ordinal","matches":matches,"ordinal":ordinal,"query":q}
            return {"status":"ok","item":matches[0],"matches":matches} if matches else None
        exact = [i for i in candidate_items if name(i) == q]
        if exact: return choose(exact)
        kw = [i for i in candidate_items if q in [str(k).lower() for k in i.get("keywords", [])]]
        if kw: return choose(kw)
        multi = [i for i in candidate_items if q in [" ".join(re.findall(r"[a-z0-9_']+", str(k).lower())) for k in i.get("keywords", [])]]
        if multi: return choose(multi)
        allwords = [i for i in candidate_items if all(w in set(re.findall(r"[a-z0-9_']+", name(i)) + [str(k).lower() for k in i.get("keywords", [])]) for w in words)]
        if allwords: return choose(allwords)
        partial = [i for i in candidate_items if all(any(token.startswith(w) for token in re.findall(r"[a-z0-9_']+", name(i)) + [str(k).lower() for k in i.get("keywords", [])]) for w in words)]
        if partial and (len(partial) == 1 or ordinal): return choose(partial)
        return {"status":"ambiguous" if partial else "missing", "matches": partial}

    def _normalize_equipment_slot(self, slot: str | None) -> str:
        aliases = {"body": "chest", "shield": "off_hand", "primary_weapon": "main_hand", "secondary_weapon": "off_hand"}
        return aliases.get(str(slot or "").strip(), str(slot or "").strip())

    def validate_equipment(self, character_id: str, item_instance: dict[str, Any], slot: str | None = None) -> dict[str, Any]:
        tmpl = item_instance.get("template") or {}
        raw_allowed = list(tmpl.get("wear_slots") if "both_hands" in (tmpl.get("wear_slots") or []) else (tmpl.get("occupies_slots") or tmpl.get("wear_slots") or []))
        legacy_both_hands = "both_hands" in raw_allowed
        if legacy_both_hands:
            raw_allowed = ["main_hand", "off_hand"]
        allowed = [self._normalize_equipment_slot(s) for s in raw_allowed]
        slot = self._normalize_equipment_slot(slot) if slot else None
        if slot and slot not in self.EQUIPMENT_SLOTS: return {"ok": False, "message": "That is not a valid equipment slot."}
        if slot and slot not in allowed: return {"ok": False, "message": f"You can't equip {item_instance['name']} there."}
        if not allowed: return {"ok": False, "message": f"You can't equip {item_instance['name']}."}
        store_slot = "both_hands" if legacy_both_hands else ",".join(allowed)
        return {"ok": True, "slot": store_slot, "occupies_slots": allowed}

    def pickup_item(self, character_id: str, room_id: str, query: str) -> str:
        res = self.resolve_item_keywords(query, self.get_visible_room_items(room_id))
        if res["status"] != "ok":
            q = str(query or "").strip().lower().replace("_", " ")
            for feat in self._resolved_room_features(room_id, self.state_store.load_character(character_id)):
                keys = [feat.get("id"), feat.get("name"), *(feat.get("keywords") or [])]
                if q and q in {str(k or "").strip().lower().replace("_", " ") for k in keys}:
                    return "You cannot take that."
            return self._resolve_message(res, "You don't see that here.")
        item = res["item"]
        if not (item.get("template") or {}).get("portable", True):
            return "You cannot take that."
        nonportable_note = ""
        self._publish_item_event("before_item_pickup", item, character_id=character_id, room_id=room_id)
        moved = self.transfer_item(item["instance_id"], to_owner=("character", character_id)); self._publish_item_event("item_picked_up", moved, character_id=character_id, room_id=room_id); self._publish_item_event("inventory_changed", moved, character_id=character_id); self._publish_item_event("room_inventory_changed", moved, room_id=room_id); self._publish_item_event("after_item_pickup", moved, character_id=character_id, room_id=room_id)
        return f"{nonportable_note}You pick up {moved['name']}."

    def drop_item(self, character_id: str, query: str) -> str:
        char = self.state_store.load_character(character_id); candidates = self.find_inventory_items(character_id)+self.find_equipped_items(character_id); res = self.resolve_item_keywords(query, candidates)
        if res["status"] != "ok": return self._resolve_message(res, "You aren't carrying that.")
        item=res["item"]; self._publish_item_event("before_item_drop", item, character_id=character_id, room_id=char.room_id if char else ""); moved=self.transfer_item(item["instance_id"], to_owner=("room", ""), room_id=char.room_id if char else ""); self._publish_item_event("item_dropped", moved, character_id=character_id, room_id=moved.get("room_id")); self._publish_item_event("inventory_changed", moved, character_id=character_id); self._publish_item_event("room_inventory_changed", moved, room_id=moved.get("room_id")); self._publish_item_event("after_item_drop", moved, character_id=character_id, room_id=moved.get("room_id")); return f"You drop {moved['name']}."

    def equip_item(self, character_id: str, query: str, preferred_slot: str | None = None) -> str:
        res=self.resolve_item_keywords(query, self.find_inventory_items(character_id))
        if res["status"] != "ok": return self._resolve_message(res, "You aren't carrying that.")
        item=res["item"]; raw_allowed=list(item["template"].get("wear_slots") if "both_hands" in (item["template"].get("wear_slots") or []) else (item["template"].get("occupies_slots") or item["template"].get("wear_slots") or [])); raw_allowed=["main_hand","off_hand"] if "both_hands" in raw_allowed else raw_allowed; allowed=[self._normalize_equipment_slot(s) for s in raw_allowed]; pref=self._normalize_equipment_slot(preferred_slot) if preferred_slot else None; slot=pref if pref in allowed else (next((s for s in ([pref] if pref else [])+allowed if s in allowed), None))
        valid=self.validate_equipment(character_id,item,slot)
        if not valid["ok"]: return valid["message"]
        slot=valid["slot"]; self._publish_item_event("before_item_equip", item, character_id=character_id, equipped_slot=slot)
        conflicts=set(valid.get("occupies_slots") or [slot])
        for eq in self.find_equipped_items(character_id):
            eq_slots=set(str(eq.get("equipped_slot") or "").split(","))
            if "both_hands" in eq_slots: eq_slots.update({"main_hand","off_hand"})
            if eq_slots & conflicts: self.move_item(eq["instance_id"], "character", character_id)
        moved=self.move_item(item["instance_id"], "equipment", character_id, equipped_slot=slot); self._publish_item_event("actor_equipment_modifiers_invalidated", moved, character_id=character_id, equipped_slot=slot); self._publish_item_event("item_equipped", moved, character_id=character_id, equipped_slot=slot); self._publish_item_event("equipment_changed", moved, character_id=character_id); self._publish_item_event("inventory_changed", moved, character_id=character_id); self._publish_item_event("after_item_equip", moved, character_id=character_id, equipped_slot=slot); return f"You equip {moved['name']} on {slot.replace('_',' ')}."

    def unequip_item(self, character_id: str, query_or_slot: str) -> str:
        equipped=self.find_equipped_items(character_id); q=query_or_slot.lower().strip(); matches=[i for i in equipped if i.get("equipped_slot")==q]
        res={"status":"ok","item":matches[0]} if len(matches)==1 else self.resolve_item_keywords(query_or_slot, equipped)
        if res["status"] != "ok": return self._resolve_message(res, "You aren't using that.")
        item=res["item"]; self._publish_item_event("before_item_remove", item, character_id=character_id); moved=self.move_item(item["instance_id"], "character", character_id); self._publish_item_event("actor_equipment_modifiers_invalidated", moved, character_id=character_id); self._publish_item_event("item_removed", moved, character_id=character_id); self._publish_item_event("equipment_changed", moved, character_id=character_id); self._publish_item_event("inventory_changed", moved, character_id=character_id); self._publish_item_event("after_item_remove", moved, character_id=character_id); return f"You remove {moved['name']}."

    def _handle_item_command(self, char: MudCharacter, command: str, cmd: str, args: list[str]):
        from engine.mud_commands import CommandResult
        q=" ".join(args).strip()
        if cmd == "loot":
            return CommandResult(self.loot_container(char, q or "corpse"))
        if cmd in {"inventory"}: return CommandResult(self._render_inventory(char.id))
        if cmd in {"equipment"}: return CommandResult(self._render_equipment(char.id))
        if cmd in {"get","take"}:
            if len(args) >= 2 and args[-1].lower() in {"corpse", "body"}:
                return CommandResult(self.get_from_container(char, " ".join(args[:-1]) or "all", args[-1]))
            if len(args) >= 3 and args[-2].lower() in {"from", "in"}:
                return CommandResult(self.get_from_container(char, " ".join(args[:-2]), args[-1]))
            if q in {"all", "everything"}: return CommandResult(self.bulk_get(char, q))
            return CommandResult(self.pickup_item(char.id, char.room_id, q) if q else "Get what?")
        if cmd=="drop":
            if q in {"all", "everything"}: return CommandResult(self.bulk_drop(char, q))
            return CommandResult(self.drop_item(char.id, q) if q else "Drop what?")
        if cmd=="wear":
            if q == "all": return CommandResult(self.wear_all(char.id))
            return CommandResult(self.equip_item(char.id, q, self._preferred_slot(q,"wear")) if q else "Wear what?")
        if cmd=="wield": return CommandResult(self.equip_item(char.id, q, self._preferred_slot(q,"wield")) if q else "Wield what?")
        if cmd=="hold": return CommandResult(self.equip_item(char.id, q, self._preferred_slot(q,"hold")) if q else "Hold what?")
        if cmd=="mainhand": return CommandResult(self.equip_item(char.id, q, "main_hand") if q else "Mainhand what?")
        if cmd=="offhand": return CommandResult(self.equip_item(char.id, q, "off_hand") if q else "Offhand what?")
        if cmd=="dual": return CommandResult(self.equip_item(char.id, q, "both_hands") if q else "Dual wield what?")
        if cmd in {"remove","unwield","unequip"}:
            if q == "all":
                equipped = list(self.find_equipped_items(char.id))
                if not equipped: return CommandResult("You aren't using anything.")
                for item in equipped: self.move_item(item["instance_id"], "character", char.id)
                return CommandResult("You remove all equipment.")
            return CommandResult(self.unequip_item(char.id, q or ("main_hand" if cmd in {"unwield","unequip"} else "")) if q or cmd in {"unwield","unequip"} else "Remove what?")
        if cmd in {"look","examine"} and q: return CommandResult(self._look_item(char.id, char.room_id, q))
        return None

    def _preferred_slot(self, query: str, mode: str) -> str | None:
        if mode == "wield": return "main_hand"
        if mode == "hold": return "light"
        return None


    def _look_in_container(self, char: MudCharacter, container: dict[str, Any]) -> str:
        if container.get("entity_type") not in {"corpse", "container"}:
            if "chest" in str(container.get("name") or container.get("id") or "").lower():
                return "You see nothing unusual."
            return "That is not a container."
        st = container.get("state") or {}
        if st.get("container_open") is False:
            return "It is closed."
        items = self.find_container_items(container.get("entity_id") or container.get("instance_id") or "")
        if not items:
            return "The corpse is empty." if container.get("entity_type") == "corpse" else "It is empty."
        head = "Inside the corpse you find:" if container.get("entity_type") == "corpse" else "Inside you find:"
        return head + "\n" + "\n".join(i["name"] + (f" x{i.get('stack_count')}" if int(i.get('stack_count') or 1) > 1 else "") for i in items)

    def _drink_from_target(self, char: MudCharacter, target: dict[str, Any], kind: str, query: str) -> str:
        if kind in {"inventory", "equipped", "room_object"}:
            item = target
            tmpl = item.get("template") or {}
            if not (tmpl.get("drinkable") or tmpl.get("item_type") == "consumable" or tmpl.get("type") == "consumable"):
                return "You cannot drink from that."
            svc_factory = getattr(self.command_engine, "_survival_service", None)
            svc = svc_factory(char) if callable(svc_factory) else None
            if svc:
                res = svc.consume_item(char.id, item.get("instance_id"), 1)
                if res.get("ok"):
                    liquid = "clean water" if "water" in str(tmpl.get("name") or item.get("name") or "").lower() else "from it"
                    return f"You drink {liquid} from {item.get('name') or tmpl.get('name') or query}."
                if str(res.get("reason") or "") == "no_servings_remaining":
                    return "The flask is empty."
            return f"You drink from {item.get('name') or tmpl.get('name') or query}."
        if target.get("drinkable") or "drink" in (target.get("interaction_capabilities") or []) or target.get("drink_profile_id"):
            return str((target.get("default_interactions") or {}).get("drink") or f"You drink from {target.get('name') or query}.")
        return "You cannot drink from that."

    def get_from_container(self, char: MudCharacter, item_query: str, container_query: str) -> str:
        res = self._resolve_interaction_target(char, container_query)
        if res.get("status") != "ok":
            return self._resolve_message(res, "You don't see that.")
        container = res.get("target", {})
        items = self.find_container_items(container.get("entity_id") or container.get("instance_id") or "")
        if not items:
            return "The corpse is empty." if container.get("entity_type") == "corpse" else "It is empty."
        if item_query.lower() in {"all", "everything"}:
            selected = items
        else:
            found = self.resolve_item_keywords(item_query, items)
            if found.get("status") != "ok":
                return self._resolve_message(found, "You don't see that in the corpse.")
            selected = [found["item"]]
        names=[]
        for item in selected:
            moved = self.transfer_item(item["instance_id"], to_owner=("character", char.id))
            names.append(moved["name"])
        self.event_bus.publish("corpse_looted", {"corpse_entity_id":container.get("entity_id"),"character_id":char.id,"item_count":len(names)}, source_system="runtime", world_id=self.active_world_id or "", character_id=char.id, room_id=char.room_id)
        return "You take:\n  " + "\n  ".join(names)

    def loot_container(self, char: MudCharacter, container_query: str) -> str:
        return self.get_from_container(char, "all", container_query)

    def bulk_get(self, char: MudCharacter, selector: str = "all") -> str:
        items = [i for i in self.get_visible_room_items(char.room_id) if (i.get("template") or {}).get("portable", True)]
        self._publish_interaction_event("bulk_get", char, "get", f"get {selector}", {"item_count": len(items)})
        self.event_bus.publish("item_bulk_transfer_started", {"actor_id": char.id, "source_kind": "room", "source_id": char.room_id, "destination_kind": "character", "destination_id": char.id, "requested_selector": selector, "attempted_count": len(items)}, source_system="runtime", world_id=self.active_world_id or "", character_id=char.id, room_id=char.room_id)
        if not items:
            return "There is nothing here you can take."
        names = []
        moved_ids = []
        for item in items:
            self._publish_item_event("before_item_pickup", item, character_id=char.id, room_id=char.room_id)
            moved = self.transfer_item(item["instance_id"], to_owner=("character", char.id))
            names.append(moved["name"]); moved_ids.append(moved["instance_id"])
            for event in ("item_picked_up", "inventory_changed", "room_inventory_changed", "after_item_pickup"):
                self._publish_item_event(event, moved, character_id=char.id, room_id=char.room_id)
        self.event_bus.publish("item_bulk_transfer_completed", {"actor_id": char.id, "source_kind": "room", "source_id": char.room_id, "destination_kind": "character", "destination_id": char.id, "requested_selector": selector, "attempted_count": len(items), "success_count": len(names), "failure_count": 0, "item_instance_ids": moved_ids}, source_system="runtime", world_id=self.active_world_id or "", character_id=char.id, room_id=char.room_id)
        return "You pick up:\n  " + "\n  ".join(names)

    def bulk_drop(self, char: MudCharacter, selector: str = "all") -> str:
        items = list(self.find_inventory_items(char.id))
        skipped = list(self.find_equipped_items(char.id))
        self._publish_interaction_event("bulk_drop", char, "drop", f"drop {selector}", {"item_count": len(items)})
        if not items:
            return "You are not carrying anything you can drop." + (" Equipped items were not dropped." if skipped else "")
        names = []
        moved_ids = []
        for item in items:
            self._publish_item_event("before_item_drop", item, character_id=char.id, room_id=char.room_id)
            moved = self.transfer_item(item["instance_id"], to_owner=("room", ""), room_id=char.room_id)
            names.append(moved["name"]); moved_ids.append(moved["instance_id"])
            for event in ("item_dropped", "inventory_changed", "room_inventory_changed", "after_item_drop"):
                self._publish_item_event(event, moved, character_id=char.id, room_id=char.room_id)
        msg = "You drop:\n  " + "\n  ".join(names)
        if skipped:
            msg += "\nEquipped items were not dropped."
        return msg

    def wear_all(self, character_id: str) -> str:
        equipped = 0
        messages = []
        for item in list(self.find_inventory_items(character_id)):
            if not (item.get("template") or {}).get("wear_slots"):
                continue
            before = self.find_equipped_items(character_id)
            msg = self.equip_item(character_id, item["name"])
            after = self.find_equipped_items(character_id)
            messages.append(msg)
            if len(after) >= len(before):
                equipped += 1
        if not messages:
            return "You have nothing wearable."
        return " ".join(messages)

    def _render_inventory(self, character_id: str) -> str:
        items = self.find_inventory_items(character_id)
        total_weight = sum(float((i.get("template") or {}).get("weight") or i.get("weight") or 0) * int(i.get("stack_count") or 1) for i in items)
        carrying = f"{int(total_weight) if total_weight.is_integer() else total_weight} weight" if items else ""
        return render_display_mud(build_inventory_document(items, carrying=carrying))

    def _render_equipment(self, character_id: str) -> str:
        return render_display_mud(build_equipment_document(self.find_equipped_items(character_id), list(self.EQUIPMENT_SLOTS)))

    def _look_item(self, character_id: str, room_id: str, query: str) -> str:
        res=self.resolve_item_keywords(query, self.get_visible_room_items(room_id)+self.find_inventory_items(character_id)+self.find_equipped_items(character_id))
        if res["status"] != "ok": return self._resolve_message(res, "You don't see that.")
        item = res["item"]
        t = item.get("template", {})
        flags = item.get("custom_flags") or {}
        suffix = f"\nServings remaining: {flags.get('servings_remaining')}." if "servings_remaining" in flags else ""
        render_payload = {**item, "description": str(t.get("examine_description") or t.get("long_description") or t.get("short_description") or item.get("description") or item.get("name") or "") + suffix}
        from smart_mud.transport import html_to_plain_text
        return html_to_plain_text(render_object(render_payload))

    def _look_entity(self, character_id: str, room_id: str, query: str) -> str | None:
        candidates = [e for e in self.find_room_entities(room_id) if e.get("entity_type") in {"npc", "mob", "object", "container", "corpse"}]
        res = self.resolve_entity_keywords(query, candidates)
        if res["status"] == "missing": return None
        if res["status"] != "ok": return self._resolve_message({"status":"ambiguous", "matches": res.get("matches", [])}, "You don't see that.")
        ent = res["entity"]
        from smart_mud.transport import html_to_plain_text
        return html_to_plain_text(render_object({"name": ent.get("name"), "description": ent.get("long_description") or ent.get("short_description"), "long_description": ent.get("long_description")}))


    def _runtime_world_objects(self, room_id: str) -> list[dict[str, Any]]:
        """Return persisted service-backed room objects for canonical rendering and inspection."""
        out: list[dict[str, Any]] = []
        db = getattr(self.state_store, "db_path", "")
        if not db:
            return out
        try:
            with sqlite3.connect(db) as conn:
                conn.row_factory = sqlite3.Row
                for r in conn.execute("SELECT * FROM campsite_instances WHERE room_id=? AND status IN ('active','occupied','abandoned') AND (expires_world_time IS NULL OR expires_world_time>(SELECT ((current_day-1)*1440+current_hour*60+current_minute) FROM world_time WHERE world_id=campsite_instances.world_id))", (room_id,)):
                    out.append({"id": r["campsite_instance_id"], "name": "a small campsite", "keywords": ["campsite", "camp", "small campsite"], "entity_type": "campsite", "short_description": "A small campsite has been established here.", "long_description": "Bedroll space and a cleared patch of ground mark this as a simple campsite."})
                for r in conn.execute("SELECT * FROM campfire_instances WHERE room_id=? AND status IN ('unlit','lit','extinguished','low_fuel') AND (expires_world_time IS NULL OR expires_world_time>(SELECT ((current_day-1)*1440+current_hour*60+current_minute) FROM world_time WHERE world_id=campfire_instances.world_id))", (room_id,)):
                    status = str(r["status"] or "unlit")
                    label = "a lit campfire" if status == "lit" else "a bed of cold ashes" if status == "extinguished" else "an unlit campfire"
                    desc = "Warm flames crackle from a small ring of stones." if status == "lit" else "Cold ash and charred wood sit within a small ring of stones." if status == "extinguished" else "Kindling and stacked wood wait within a small ring of stones."
                    out.append({"id": r["campfire_instance_id"], "name": label, "keywords": ["campfire", "fire", label], "entity_type": "campfire", "status": status, "short_description": label, "long_description": desc})
        except sqlite3.Error:
            return out
        return out

    def _log_inspection_route(self, raw: str, cmd: str, argument: str, resolved: dict[str, Any], renderer: str) -> None:
        target = resolved.get("target") or {}
        logger.debug(
            "inspection_route raw_input=%r selected_command=%s remaining_argument=%r resolved_target_category=%s resolved_target_id=%s selected_renderer=%s",
            raw,
            cmd,
            argument,
            resolved.get("kind") or resolved.get("status"),
            target.get("entity_id") or target.get("instance_id") or target.get("id") or target.get("feature_id") or target.get("name") or "",
            renderer,
        )

    def inspect_target(self, viewer: MudCharacter, resolved_target: dict[str, Any], inspection_mode: str) -> str:
        """Canonical target inspection dispatcher for player rendering.

        Parser code resolves a target once; this dispatcher owns mode/category
        presentation so targeted LOOK never falls back to room rendering after a
        successful resolution.
        """
        if resolved_target.get("status") != "ok":
            return self._resolve_message(resolved_target, "You don't see that.")
        target = resolved_target.get("target") or {}
        kind = str(resolved_target.get("kind") or target.get("entity_type") or "object")
        mode = inspection_mode.upper()
        if mode == "LOOK_INSIDE":
            return self._look_in_container(viewer, target)
        if mode == "LOOK_DIRECTION":
            return self._render_examination(target, "exit", str(target.get("name") or "exit"), mode="LOOK")
        if mode == "IDENTIFY":
            if kind == "corpse":
                return "You cannot identify that without a suitable skill."
            return self._render_identify(target, kind, str(target.get("name") or "target"))
        if mode == "READ":
            template = target.get("template") or {}
            msg = str(target.get("readable_text") or target.get("text") or target.get("writing") or target.get("message") or template.get("readable_text") or "")
            return msg or "There is nothing readable here. There is nothing written there."
        return self._render_examination(target, kind, str(target.get("name") or "target"), mode=mode)

    def _description_for_mode(self, target: dict[str, Any], template: dict[str, Any], mode: str) -> str:
        mode = mode.upper()
        keys = (
            ("examine_description", "examine_text", "extended_description", "look_description", "long_description", "description", "short_description")
            if mode in {"EXAMINE", "INSPECT"}
            else ("look_description", "description", "long_description", "short_description")
        )
        for key in keys:
            if key in {"look_description", "examine_description", "examine_text"}:
                val = template.get(key)
                if val:
                    return str(val).strip()
            val = target.get(key)
            if val:
                return str(val).strip()
            val = template.get(key)
            if val:
                return str(val).strip()
        return ""

    def _state_lines_for_target(self, target: dict[str, Any], kind: str, mode: str) -> list[str]:
        template = target.get("template") or {}
        state = target.get("state") or {}
        flags = target.get("custom_flags") or state or {}
        lines: list[str] = []
        servings = flags.get("servings_remaining")
        if servings is not None or template.get("drinkable"):
            try:
                count = int(servings)
                lines.append("It is empty." if count <= 0 else "It feels partly full." if count <= 1 else "It feels mostly full.")
            except Exception:
                pass
        status = str(target.get("status") or state.get("status") or "").lower()
        if kind in {"campfire", "world_object"} or "campfire" in str(target.get("name", "")).lower():
            if status == "lit":
                lines.append("It is lit and burning steadily.")
            elif status == "extinguished":
                lines.append("It has burned down to cold ash.")
            elif status:
                lines.append("It is not lit.")
        if kind == "corpse":
            lines.append(f"It is {state.get('decay_state', 'fresh')}.")
            lines += ["It has been skinned." if state.get("skinned") else "It has not been skinned."]
            if mode.upper() != "LOOK":
                lines += ["It has been butchered." if state.get("butchered") else "It has not been butchered.", "It is open." if state.get("container_open", True) else "It is closed."]
        return lines

    def _render_examination(self, target: dict[str, Any], kind: str, query: str, mode: str = "EXAMINE") -> str:
        template = target.get("template") or {}
        if not template and target.get("template_id"):
            template = dict(self.entity_templates.get(str(target.get("template_id") or ""), {}))
        name = str(target.get("name") or template.get("name") or query).strip()
        long_desc = self._description_for_mode(target, template, mode)
        extended = str(target.get("extended_description") or template.get("extended_description") or "").strip() if mode.upper() != "LOOK" else ""
        if kind == "exit" and not long_desc:
            return semantic("direction", name) + "\n" + semantic("placeholder", "You see nothing unusual.")
        interactions = target.get("interactions") or target.get("default_interactions") or template.get("default_interactions") or {}
        title_role = "entity_title" if kind in {"player", "npc", "mob"} else "feature" if kind in {"feature", "exit"} else "object_title"
        desc_role = "entity_description" if kind in {"player", "npc", "mob"} else "object_description"
        lines = [semantic(title_role, name)]
        if kind == "player" and not long_desc:
            long_desc = f"{name} is here."
        if long_desc:
            lines.append(semantic(desc_role, long_desc))
        if extended:
            lines.append(semantic(desc_role, extended))
        if not long_desc and kind not in {"player", "npc", "mob"}:
            lines.append(semantic(desc_role, f"You see nothing unusual about {name}."))
        lines.extend(self._state_lines_for_target(target, kind, mode))
        if kind in {"npc", "mob", "player"}:
            lines += ["", "Condition:", condition_label(target).capitalize() + "."]
            st = str(target.get("current_state") or (target.get("state") or {}).get("current_state") or "standing")
            target_name = (target.get("state") or {}).get("combat_target_name")
            lines += ["", "Status:", (f"Fighting {target_name}." if target_name else st.replace('_',' ').capitalize() + ".")]
            lines += ["", "Equipment:", "None visible."]
        hints = target.get("interaction_hints") or template.get("interaction_hints") or []
        if mode.upper() != "LOOK" and hints:
            lines.append("Possible interactions:")
            lines.extend(str(h) for h in hints)
        elif mode.upper() != "LOOK" and interactions:
            lines.append(semantic("object_interaction", "Possible interactions:"))
            for verb in sorted(interactions.keys() if isinstance(interactions, dict) else interactions):
                lines.append(semantic("object_interaction", str(verb)))
        return "\n".join(lines) if len(lines) > 1 else ""

    def _render_identify(self, target: dict[str, Any], kind: str, query: str) -> str:
        template = target.get("template") or {}
        name = str(target.get("name") or template.get("name") or query)
        item_type = str(template.get("item_type") or target.get("entity_type") or kind).replace("_", " ").title()
        weight = template.get("weight", target.get("weight", "None"))
        value = template.get("value", target.get("value", "None"))
        condition = str(target.get("condition") or template.get("condition") or "Normal").title()
        required = template.get("required_level") or template.get("level_required") or "None"
        return "\n".join([
            f"You identify {name}.",
            semantic("object_title", name),
            semantic("object_description", item_type),
            f"Weight: {weight}",
            f"Value: {value}",
            "Condition:",
            str(condition),
            "Required Level:",
            str(required),
        ])

    def _render_self_examination(self, char: MudCharacter) -> str:
        room = self._current_room(char)
        equipped = self.find_equipped_items(char.id)
        eq = ", ".join(i.get("name", "something") for i in equipped) if equipped else "nothing equipped"
        data = getattr(char, "data", {}) if hasattr(char, "data") else {}
        race = data.get("race") if isinstance(data, dict) else None
        char_class = data.get("class") if isinstance(data, dict) else None
        return "\n".join([
            semantic("entity_title", char.name),
            f"Race: {race or 'Unknown'}",
            f"Class: {char_class or 'Unknown'}",
            f"Title: {getattr(char, 'title', '') or 'None'}",
            f"Equipment: {eq}",
            f"Condition: HP {char.hp}/{char.max_hp}, Mana {char.mana}/{char.max_mana}, Stamina {char.stamina}/{char.max_stamina}",
            f"Current Room: {room.title}",
        ])

    def _resolve_message(self, res: dict[str, Any], missing: str) -> str:
        if res.get("status") == "missing_ordinal":
            return f"There is no {int(res.get('ordinal') or 0)}.{res.get('query') or 'target'} here."
        if res.get("status") == "ambiguous":
            choices = []
            for idx, item in enumerate(res.get("matches", []), start=1):
                name = str(item.get("name") or item.get("template", {}).get("name") or "target").lower()
                word = next((w for w in re.findall(r"[a-z0-9_']+", name) if w not in self.ARTICLES), name)
                choices.append(f"{idx}.{word}")
            return "Which do you mean: " + " or ".join(choices) + "?"
        return missing

    def _publish_item_event(self, name: str, item: dict[str, Any] | None, **extra: Any) -> None:
        payload={"world_id": self.active_world_id or "", **(extra or {})}
        if item: payload.update({"template_id": item.get("template_id"), "instance_id": item.get("instance_id"), "owner_type": item.get("owner_type"), "owner_id": item.get("owner_id"), "room_id": extra.get("room_id", item.get("room_id")), "equipped_slot": extra.get("equipped_slot", item.get("equipped_slot"))})
        self.event_bus.publish(name, payload, source_system="runtime", world_id=self.active_world_id or "", character_id=payload.get("character_id", ""), room_id=payload.get("room_id", ""))

    def _spawn_starter_items(self, character_id: str) -> None:
        if self.find_inventory_items(character_id) or self.find_equipped_items(character_id): return
        for tid,t in self.item_templates.items():
            if t.get("starter"):
                item=self.spawn_item(tid,"character",owner_id=character_id,stack_count=int(t.get("starter_quantity") or 1))
                slot=t.get("starter_equipped_slot")
                if slot and self.validate_equipment(character_id,item,slot).get("ok"): self.move_item(item["instance_id"],"equipment",character_id,equipped_slot=slot)

    def _seed_room_items(self) -> None:
        self.materialize_world_content(self.active_world_id or "")

    def _live_item_placements(self) -> dict[str, dict[str, Any]]:
        placements: dict[str, dict[str, Any]] = {}
        for raw in getattr(self.active_world, "item_placements", []) or []:
            if isinstance(raw, dict) and raw.get("id"):
                placements[str(raw["id"])] = dict(raw)
        # Backward-compatible migration of proven legacy room object declarations.
        for room in getattr(self.active_world, "rooms", []) or []:
            rid = str(room.get("id") or "")
            counts: dict[str, int] = {}
            for oid in room.get("objects", []) or []:
                tid = str(oid.get("template_id") or oid.get("id") if isinstance(oid, dict) else oid)
                if tid in self.item_templates and self.item_templates[tid].get("portable", True):
                    counts[tid] = counts.get(tid, 0) + 1
            for tid, qty in counts.items():
                pid = f"legacy_{rid}_{tid}"
                placements.setdefault(pid, {"id": pid, "item_template_id": tid, "room_id": rid, "quantity": qty, "seed_policy": "once", "flags": ["legacy_room_object"], "tags": [], "plugin_data": {"source": "rooms.objects"}})
        return placements

    def materialize_world_content(self, world_id: str | None = None) -> dict[str, Any]:
        self.event_bus.publish("content_materialization_started", {"world_id": world_id or self.active_world_id or ""}, source_system="runtime", world_id=world_id or self.active_world_id or "")
        item_ids=[]; ent_ids=[]
        placements = self._live_item_placements(); spawns = self._live_entity_spawns()
        existing_rows = {sid: self._materialization_row("entity_spawn", sid) for sid in spawns}
        legacy_decls = sum(len(self._legacy_room_entity_declarations(str(r.get("id") or ""))) for r in getattr(self.active_world, "rooms", []) or [])
        for pid in sorted(placements): item_ids += self.materialize_item_seed(pid).get("instance_ids", [])
        adopted = created = duplicates = 0
        for sid in sorted(spawns):
            before = existing_rows.get(sid)
            row = self.materialize_entity_spawn(sid)
            ent_ids += row.get("instance_ids", [])
            if not before:
                meta = (self._materialization_row("entity_spawn", sid) or {}).get("metadata", {})
                adopted += int(meta.get("adopted_existing") or 0)
                created += max(0, int(meta.get("quantity") or 0) - int(meta.get("adopted_existing") or 0))
                duplicates += len(meta.get("duplicate_candidates") or [])
        print(f"[entity-materialization] templates={len(self.entity_templates)}")
        print(f"[entity-materialization] canonical_spawns={len([s for s in spawns.values() if not (s.get('plugin_data') or {}).get('legacy_source')])}")
        print(f"[entity-materialization] legacy_declarations={legacy_decls}")
        print(f"[entity-materialization] normalized_legacy_spawns={len([s for s in spawns.values() if (s.get('plugin_data') or {}).get('legacy_source')])}")
        print(f"[entity-materialization] adopted_instances={adopted}")
        print(f"[entity-materialization] created_instances={created}")
        print(f"[entity-materialization] duplicate_candidates={duplicates}")
        self.event_bus.publish("content_materialization_completed", {"world_id": world_id or self.active_world_id or "", "item_instance_ids": item_ids, "entity_instance_ids": ent_ids}, source_system="runtime", world_id=world_id or self.active_world_id or "")
        return {"item_instance_ids": item_ids, "entity_instance_ids": ent_ids}

    def materialize_room_content(self, world_id: str, room_id: str) -> dict[str, Any]:
        item_ids=[]; ent_ids=[]
        for pid,p in self._live_item_placements().items():
            if str(p.get("room_id")) == str(room_id): item_ids += self.materialize_item_seed(pid).get("instance_ids", [])
        for sid,s in self._live_entity_spawns().items():
            if str(s.get("room_id")) == str(room_id): ent_ids += self.materialize_entity_spawn(sid).get("instance_ids", [])
        return {"item_instance_ids": item_ids, "entity_instance_ids": ent_ids}

    def _materialization_row(self, kind: str, declaration_id: str) -> dict[str, Any] | None:
        with sqlite3.connect(self.state_store.db_path) as conn:
            row=conn.execute("SELECT instance_ids_json,status,metadata_json,materialized_at FROM content_materializations WHERE world_id=? AND declaration_kind=? AND declaration_id=?", (self.active_world_id or "", kind, declaration_id)).fetchone()
        if not row: return None
        return {"instance_ids": json.loads(row[0] or "[]"), "status": row[1], "metadata": json.loads(row[2] or "{}"), "materialized_at": row[3]}

    def materialize_item_seed(self, seed_id: str) -> dict[str, Any]:
        row=self._materialization_row("item_placement", seed_id)
        if row: return row
        p=self._live_item_placements().get(seed_id); ids=[]; now=datetime.now(timezone.utc).isoformat()
        if not p or p.get("seed_policy", "once") == "disabled": return {"instance_ids": [], "status": "disabled"}
        tid=str(p.get("item_template_id") or p.get("template_id") or ""); rid=str(p.get("room_id") or ""); qty=max(0, int(p.get("quantity") or 1))
        if tid not in self.item_templates or not rid: status="failed"; meta={"error":"missing template or room"}
        else:
            with sqlite3.connect(self.state_store.db_path) as conn:
                for _ in range(qty):
                    iid=f"item_{uuid.uuid4().hex}"; ids.append(iid)
                    conn.execute("INSERT INTO item_instances(instance_id,world_id,template_id,owner_type,owner_id,room_id,equipped_slot,stack_count,condition,durability,created_at,updated_at,custom_flags,plugin_data) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (iid,self.active_world_id or "",tid,"room","",rid,"",1,"normal",100,now,now,json.dumps({"source_seed_id": seed_id}),json.dumps(p.get("plugin_data") or {})))
                conn.execute("INSERT INTO content_materializations(world_id,declaration_kind,declaration_id,materialized_at,instance_ids_json,status,metadata_json) VALUES(?,?,?,?,?,?,?)", (self.active_world_id or "","item_placement",seed_id,now,json.dumps(ids),"materialized",json.dumps({"template_id": tid, "room_id": rid, "quantity": qty})))
            status="materialized"; meta={"template_id": tid, "room_id": rid, "quantity": qty}
            self.event_bus.publish("item_seed_materialized", {"world_id": self.active_world_id or "", "declaration_id": seed_id, "template_id": tid, "room_id": rid, "instance_ids": ids, "quantity": qty, "policy": p.get("seed_policy", "once")}, source_system="runtime", world_id=self.active_world_id or "", room_id=rid)
        return {"instance_ids": ids, "status": status, "metadata": meta, "materialized_at": now}

    ENTITY_TYPES = {"player", "npc", "mob", "object", "container", "corpse", "door", "shop", "pet", "summon"}

    def _load_entity_templates(self) -> None:
        templates: dict[str, MappingProxyType] = {}
        for raw in getattr(self.active_world, "npcs", []) or []:
            if not isinstance(raw, dict):
                continue
            tid = str(raw.get("id") or raw.get("template_id") or "").strip()
            if not tid:
                continue
            kind = str(raw.get("entity_type") or raw.get("kind") or "npc").lower()
            entity_type = "mob" if kind in {"mob", "monster", "creature"} else "npc"
            keywords = raw.get("keywords") or str(raw.get("name") or tid).replace("-", " ").replace("'", "").split() + [tid]
            level_range = raw.get("level_range") or [raw.get("level", 1)]
            level = int((level_range[0] if isinstance(level_range, list) and level_range else raw.get("level", 1)) or 1)
            templates[tid] = MappingProxyType({
                "template_id": tid, "entity_type": entity_type, "name": str(raw.get("name") or tid).title(),
                "keywords": [str(k).lower() for k in keywords if str(k).strip()],
                "short_description": str(raw.get("short_description") or raw.get("description") or raw.get("name") or tid),
                "long_description": str(raw.get("long_description") or raw.get("description") or raw.get("short_description") or raw.get("name") or tid),
                "room_description": str(raw.get("room_description") or raw.get("description") or raw.get("short_description") or raw.get("name") or tid),
                "look_description": str(raw.get("look_description") or raw.get("description") or raw.get("long_description") or raw.get("short_description") or raw.get("name") or tid),
                "examine_description": str(raw.get("examine_description") or raw.get("look_description") or raw.get("long_description") or raw.get("description") or raw.get("short_description") or raw.get("name") or tid),
                "readable_text": str(raw.get("readable_text") or ""),
                "interaction_hints": raw.get("interaction_hints") or [],
                "respawn_enabled": bool(raw.get("respawn_enabled")),
                "respawn_delay_seconds": int(raw.get("respawn_delay_seconds") or 0),
                "respawn_mode": str(raw.get("respawn_mode") or "normal"),
                "respawn_message": str(raw.get("respawn_message") or ""),
                "spawn_id": str(raw.get("spawn_id") or raw.get("spawn_group") or tid),
                "default_room_id": str(raw.get("default_room_id") or raw.get("room_id") or ""),
                "faction_id": str(raw.get("faction_id") or ""), "level": level,
                "id": tid,
                "race": str(raw.get("race") or raw.get("species") or ""), "class": str(raw.get("class") or raw.get("occupation") or ""),
                "gender": str(raw.get("gender") or ""), "size": str(raw.get("size") or "medium"), "alignment": str(raw.get("alignment") or "neutral"),
                "spawn_group": str(raw.get("spawn_group") or raw.get("spawn_id") or tid),
                "spawn_rules": raw.get("spawn_rules") or {"spawn_room": raw.get("default_room_id") or raw.get("room_id") or "", "spawn_count": int(raw.get("spawn_count") or 1), "maximum_population": int(raw.get("max_alive") or raw.get("maximum_population") or 1), "respawn_delay": int(raw.get("respawn_delay_seconds") or raw.get("respawn_delay") or 0), "spawn_probability": float(raw.get("spawn_probability") or 1)},
                "wander_rules": raw.get("wander_rules") or {"allowed_exits": raw.get("allowed_exits") or [], "wander_probability": float(raw.get("wander_probability") or 0), "wander_delay": int(raw.get("wander_delay") or 0), "restricted_rooms": raw.get("restricted_rooms") or [], "sentinel": bool(raw.get("sentinel") or "sentinel" in (raw.get("flags") or []))},
                "dialogue_package": raw.get("dialogue_package") or {"greeting": raw.get("greeting") or f"{str(raw.get('name') or tid).title()} greets you.", "farewell": raw.get("farewell") or "Farewell.", "idle_speech": raw.get("idle_speech") or [], "talk_responses": raw.get("talk_responses") or [raw.get("dialogue_seed") or raw.get("description") or "They have nothing more to say."], "keyword_responses": raw.get("keyword_responses") or {}},
                "behavior_flags": raw.get("behavior_flags") or raw.get("flags") or raw.get("tags") or [],
                "tags": raw.get("tags") or [], "combat_policy": raw.get("combat_policy") or {}, "stats": raw.get("stats") or {},
                "combat_behavior_profile_id": raw.get("combat_behavior_profile_id") or raw.get("behavior_profile_id") or "", "behavior_profile_id": raw.get("behavior_profile_id") or "",
                "ability_loadout_id": raw.get("ability_loadout_id") or "", "natural_weapon_profile_id": raw.get("natural_weapon_profile_id") or "", "body_profile_id": raw.get("body_profile_id") or ("wolf" if "wolf" in tid else "humanoid"),
                "visibility_flags": raw.get("visibility_flags") or [],
                "loot_table": raw.get("loot_table") or raw.get("loot_table_id") or "", "merchant_profile": raw.get("merchant_profile") or {},
                "trainer_profile": raw.get("trainer_profile") or {}, "banker_profile": raw.get("banker_profile") or {}, "healer_profile": raw.get("healer_profile") or {},
                "quest_profile": raw.get("quest_profile") or {}, "script_hooks": raw.get("script_hooks") or {},
                "state": raw.get("state") or {"current_state": "idle", "current_health": (raw.get("stats") or {}).get("max_health", 100), "maximum_health": (raw.get("stats") or {}).get("max_health", 100)}, "flags": raw.get("flags") or raw.get("behavior_flags") or raw.get("tags") or [], "plugin_data": raw.get("plugin_data") or {},
            })
        self.entity_templates = templates


    PRESENTATION_TEMPLATE_FIELDS = ("name", "keywords", "room_description", "look_description", "examine_description", "readable_text", "interaction_hints", "respawn_message")

    def _template_presentation_hash(self, tmpl: dict[str, Any]) -> str:
        payload = {k: tmpl.get(k) for k in self.PRESENTATION_TEMPLATE_FIELDS if k in tmpl}
        return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()

    def _reconcile_entity_presentation(self, row: Any) -> tuple[Any, ...]:
        data = list(row)
        tmpl = dict(self.entity_templates.get(str(data[3] or ""), {}))
        if not tmpl or str(data[2] or "") == "corpse":
            return tuple(row)
        try:
            plugin = json.loads(data[17] or "{}")
        except Exception:
            plugin = {}
        new_hash = self._template_presentation_hash(tmpl)
        if plugin.get("template_presentation_hash") == new_hash:
            return tuple(row)
        plugin.update({
            "template_presentation_hash": new_hash,
            "look_description": tmpl.get("look_description", data[7]),
            "examine_description": tmpl.get("examine_description", tmpl.get("look_description", data[7])),
            "readable_text": tmpl.get("readable_text", ""),
            "interaction_hints": tmpl.get("interaction_hints", []),
            "respawn_message": tmpl.get("respawn_message", ""),
        })
        data[4] = tmpl.get("name", data[4])
        data[5] = json.dumps(tmpl.get("keywords", []))
        data[6] = tmpl.get("room_description", tmpl.get("short_description", data[6]))
        data[7] = tmpl.get("look_description", tmpl.get("long_description", data[7]))
        now = datetime.now(timezone.utc).isoformat(); data[16] = now; data[17] = json.dumps(plugin)
        with sqlite3.connect(self.state_store.db_path) as conn:
            conn.execute("UPDATE entity_instances SET name=?,keywords=?,short_description=?,long_description=?,updated_at=?,plugin_data=? WHERE entity_id=?", (data[4], data[5], data[6], data[7], data[16], data[17], data[0]))
        logger.info("entity presentation reconciled template=%s entity=%s", data[3], data[0])
        return tuple(data)

    def _entity_payload(self, row: Any) -> dict[str, Any]:
        keys = ["entity_id","world_id","entity_type","template_id","name","keywords","short_description","long_description","current_room_id","owner_type","owner_id","faction_id","level","state","flags","created_at","updated_at","plugin_data"]
        data = dict(zip(keys, row))
        for key, default in (("keywords", []), ("state", {}), ("flags", []), ("plugin_data", {})):
            try: data[key] = json.loads(data.get(key) or json.dumps(default))
            except Exception: data[key] = default
        data["room_id"] = data.get("current_room_id", "")
        state = data.get("state") if isinstance(data.get("state"), dict) else {}
        tmpl = dict(self.entity_templates.get(str(data.get("template_id") or ""), {}))
        data["instance_id"] = data.get("entity_id")
        data["current_state"] = state.get("current_state") or state.get("position") or ("corpse" if data.get("entity_type") == "corpse" else "idle")
        data["current_health"] = int(state.get("current_health", state.get("health", 1 if data.get("entity_type") == "corpse" else 100)) or 0)
        data["current_mana"] = int(state.get("current_mana", 0) or 0); data["current_stamina"] = int(state.get("current_stamina", 0) or 0)
        data["spawn_time"] = data.get("created_at"); data["last_update"] = data.get("updated_at"); data["last_reset"] = state.get("last_reset", "")
        data["spawn_origin"] = state.get("spawn_origin") or tmpl.get("default_room_id") or data.get("current_room_id", "")
        data["is_alive"] = bool(state.get("is_alive", data.get("entity_type") != "corpse" and data["current_state"] not in {"dead", "corpse", "despawned"}))
        if data.get("entity_type") in {"npc", "mob"} and (data["current_health"] <= 0 or data["current_state"] in {"dead", "corpse", "despawned"}):
            data["current_health"] = 0
            data["is_alive"] = False
            data["current_state"] = "dead" if data["current_state"] != "despawned" else data["current_state"]
            state.update({"current_health": 0, "is_alive": False, "current_state": data["current_state"]})
            data["state"] = state
        data["is_visible"] = bool(state.get("is_visible", not self._entity_hidden(data)))
        data["movement_state"] = state.get("movement_state", "standing"); data["dialogue_state"] = state.get("dialogue_state", {})
        data["custom_state"] = state.get("custom_state", {})
        data["behavior_flags"] = list(tmpl.get("behavior_flags") or data.get("flags") or [])
        data["visibility_flags"] = list(tmpl.get("visibility_flags") or []) + list(state.get("visibility_flags") or [])
        pdata = data.get("plugin_data") if isinstance(data.get("plugin_data"), dict) else {}
        data["room_description"] = data.get("short_description") or tmpl.get("room_description") or data.get("name")
        data["look_description"] = pdata.get("look_description") or data.get("long_description") or tmpl.get("look_description") or data.get("room_description")
        data["examine_description"] = pdata.get("examine_description") or tmpl.get("examine_description") or data.get("look_description")
        data["description"] = data.get("look_description") or data.get("long_description") or data.get("short_description") or data.get("name")
        return data

    def _fetch_entities(self, where: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
        with sqlite3.connect(self.state_store.db_path) as conn:
            rows = conn.execute(f"SELECT entity_id,world_id,entity_type,template_id,name,keywords,short_description,long_description,current_room_id,owner_type,owner_id,faction_id,level,state,flags,created_at,updated_at,plugin_data FROM entity_instances WHERE destroyed_at IS NULL AND {where} ORDER BY entity_type, created_at, entity_id", params).fetchall()
        return [self._entity_payload(self._reconcile_entity_presentation(r)) for r in rows]

    def spawn_entity(self, template_id: str, entity_type: str | None = None, room_id: str | None = None, owner_type: str = "room", owner_id: str = "", state: dict[str, Any] | None = None, flags: list[str] | None = None, source_system: str = "runtime", **ctx: Any) -> dict[str, Any]:
        tmpl = dict(self.entity_templates.get(template_id, {}))
        etype = entity_type or tmpl.get("entity_type") or "object"
        if etype not in self.ENTITY_TYPES: raise ValueError(f"Unsupported entity type: {etype}")
        now = datetime.now(timezone.utc).isoformat(); eid = f"ent_{uuid.uuid4().hex}"
        if etype in {"npc", "mob"} and (state is None or not dict(state).get("lifecycle_id")):
            state = dict(state or tmpl.get("state", {}) or {})
            state["lifecycle_id"] = f"life_{uuid.uuid4().hex}"
        plugin_data = dict(tmpl.get("plugin_data", {})); plugin_data.update({"template_presentation_hash": self._template_presentation_hash(tmpl), "look_description": tmpl.get("look_description", tmpl.get("long_description", "")), "examine_description": tmpl.get("examine_description", tmpl.get("look_description", "")), "readable_text": tmpl.get("readable_text", ""), "interaction_hints": tmpl.get("interaction_hints", []), "respawn_message": tmpl.get("respawn_message", "")})
        payload = (eid, self.active_world_id or tmpl.get("world_id", ""), etype, template_id, tmpl.get("name", template_id), json.dumps(tmpl.get("keywords", [template_id])), tmpl.get("room_description", tmpl.get("short_description", tmpl.get("name", template_id))), tmpl.get("look_description", tmpl.get("long_description", tmpl.get("short_description", tmpl.get("name", template_id)))), room_id or tmpl.get("default_room_id", ""), owner_type, owner_id, tmpl.get("faction_id", ""), int(tmpl.get("level", 1) or 1), json.dumps(state if state is not None else tmpl.get("state", {})), json.dumps(flags if flags is not None else tmpl.get("flags", [])), now, now, json.dumps(plugin_data))
        with sqlite3.connect(self.state_store.db_path) as conn:
            conn.execute("INSERT INTO entity_instances(entity_id,world_id,entity_type,template_id,name,keywords,short_description,long_description,current_room_id,owner_type,owner_id,faction_id,level,state,flags,created_at,updated_at,plugin_data) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", payload)
        ent = self.find_entity(eid) or {}
        self._publish_entity_event("entity_spawned", ent, source_system=source_system, **ctx)
        if etype in {"npc", "mob", "corpse"}: self._publish_entity_event(f"{etype}_spawned", ent, source_system=source_system, **ctx)
        self._publish_entity_event("room_entities_changed", ent, source_system=source_system, **ctx)
        return ent

    def find_entity(self, entity_id: str) -> dict[str, Any] | None: return next(iter(self._fetch_entities("entity_id=?", (entity_id,))), None)
    def find_room_entities(self, room_id: str) -> list[dict[str, Any]]: return self._fetch_entities("owner_type='room' AND current_room_id=?", (room_id,))
    def get_room_contents(self, room_id: str, viewer: Any = None, include_builder_metadata: bool = False) -> dict[str, Any]:
        groups = {"features": self._resolved_room_features(room_id, viewer), "item_instances": self.get_visible_room_items(room_id), "entity_instances": [], "players": [], "exits": []}
        seen_instance_ids: set[str] = set()
        for ent in self.find_room_entities(room_id):
            if not self.is_entity_visible(ent, viewer):
                continue
            iid = str(ent.get("instance_id") or ent.get("entity_id") or "")
            if iid in seen_instance_ids:
                raise RuntimeError(f"Duplicate runtime entity instance in room-content query: {iid}")
            seen_instance_ids.add(iid)
            groups["entity_instances"].append(ent)
        if include_builder_metadata:
            groups["item_placement_declarations"] = [p for p in self._live_item_placements().values() if str(p.get("room_id")) == str(room_id)]
            groups["entity_spawn_declarations"] = [s for s in self._live_entity_spawns().values() if str(s.get("room_id")) == str(room_id)]
            groups["legacy_npc_declarations"] = self._legacy_room_entity_declarations(room_id)
        return groups

    def find_visible_entities(self, room_id: str, viewer: Any = None) -> dict[str, list[dict[str, Any]]]:
        contents = self.get_room_contents(room_id, viewer)
        groups = {"players": [], "npcs": [], "mobs": [], "objects": list(contents["item_instances"]), "corpses": []}
        for ent in contents["entity_instances"]:
            groups[{"npc":"npcs", "mob":"mobs", "corpse":"corpses"}.get(ent.get("entity_type"), "objects")].append(ent)
        return groups

    def resolve_entity_keywords(self, query: str, candidate_entities: list[dict[str, Any]]) -> dict[str, Any]:
        numbered = re.match(r"^\s*(\d+)\.([^\s].*)$", str(query or ""), re.I)
        ordinal = int(numbered.group(1)) if numbered else 0
        query = numbered.group(2) if numbered else query
        words = [w for w in re.findall(r"[a-z0-9_']+", query.lower()) if w not in self.ARTICLES]; q = " ".join(words)
        if not q: return {"status":"missing", "matches": []}
        def toks(e): return re.findall(r"[a-z0-9_']+", str(e.get("name","")).lower()) + [str(k).lower() for k in e.get("keywords", []) if str(k).strip()]
        def choose(matches):
            if ordinal:
                return {"status":"ok","entity":matches[ordinal-1],"matches":matches} if len(matches) >= ordinal else {"status":"missing_ordinal","matches":matches,"ordinal":ordinal,"query":q}
            return {"status":"ok","entity":matches[0],"matches":matches} if matches else None
        matches = [e for e in candidate_entities if str(e.get("name","")).lower() == q]
        if matches: return choose(matches)
        matches = [e for e in candidate_entities if q in [str(k).lower() for k in e.get("keywords", [])]]
        if matches: return choose(matches)
        matches = [e for e in candidate_entities if q in [" ".join(re.findall(r"[a-z0-9_']+", str(k).lower())) for k in e.get("keywords", [])]]
        if matches: return choose(matches)
        matches = [e for e in candidate_entities if all(w in set(toks(e)) for w in words)]
        if matches: return choose(matches)
        partial = [e for e in candidate_entities if all(any(token.startswith(w) for token in toks(e)) for w in words)]
        if partial and (len(partial) == 1 or ordinal): return choose(partial)
        return {"status": "ambiguous" if partial else "missing", "entity": None, "matches": partial}

    def move_entity(self, entity_id: str, room_id: str, source_system: str = "runtime", **ctx: Any) -> dict[str, Any]:
        old = self.find_entity(entity_id); now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.state_store.db_path) as conn: conn.execute("UPDATE entity_instances SET current_room_id=?, owner_type='room', updated_at=? WHERE entity_id=? AND destroyed_at IS NULL", (room_id, now, entity_id))
        ent = self.find_entity(entity_id) or {}
        self._publish_entity_event("entity_moved", ent, source_system=source_system, previous_room_id=(old or {}).get("current_room_id"), **ctx); self._publish_entity_event("room_entities_changed", ent, source_system=source_system, **ctx)
        return ent

    def update_entity_state(self, entity_id: str, state: dict[str, Any], source_system: str = "runtime", **ctx: Any) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.state_store.db_path) as conn: conn.execute("UPDATE entity_instances SET state=?, updated_at=? WHERE entity_id=? AND destroyed_at IS NULL", (json.dumps(state), now, entity_id))
        ent = self.find_entity(entity_id) or {}; self._publish_entity_event("entity_state_changed", ent, source_system=source_system, **ctx); return ent

    def despawn_entity(self, entity_id: str, source_system: str = "runtime", **ctx: Any) -> bool:
        ent = self.find_entity(entity_id)
        with sqlite3.connect(self.state_store.db_path) as conn: conn.execute("UPDATE entity_instances SET destroyed_at=?, destroy_reason='despawned', updated_at=? WHERE entity_id=?", (datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat(), entity_id))
        if ent: self._publish_entity_event("entity_despawned", ent, source_system=source_system, **ctx); self._publish_entity_event("room_entities_changed", ent, source_system=source_system, **ctx)
        return bool(ent)

    def destroy_entity(self, entity_id: str, reason: str = "destroyed", source_system: str = "runtime", **ctx: Any) -> bool:
        ent = self.find_entity(entity_id)
        with sqlite3.connect(self.state_store.db_path) as conn: conn.execute("UPDATE entity_instances SET destroyed_at=?, destroy_reason=?, updated_at=? WHERE entity_id=?", (datetime.now(timezone.utc).isoformat(), reason, datetime.now(timezone.utc).isoformat(), entity_id))
        if ent: self._publish_entity_event("entity_destroyed", ent, source_system=source_system, **ctx); self._publish_entity_event("room_entities_changed", ent, source_system=source_system, **ctx)
        return bool(ent)

    def _resolved_room_features(self, room_id: str, viewer: Any = None) -> list[dict[str, Any]]:
        room_data = None
        if viewer is not None: room_data, _ = self.runtime_room_data(viewer, room_id)
        room_data = room_data or self._live_room_data(room_id) or {}
        library = {str(f.get("id")): f for f in getattr(self.active_world, "features", []) or [] if isinstance(f, dict) and f.get("id")}
        if viewer is not None and self._builder_visible(viewer):
            library.update({str(k): dict(v, id=str(k)) for k,v in self._drafts().get("features", {}).items() if isinstance(v, dict)})
        out=[]; seen=set()
        for fid in room_data.get("feature_refs", []) or []:
            feat = dict(library.get(str(fid), {})); feat.setdefault("id", str(fid)); feat.setdefault("source", "shared"); feat.setdefault("local_or_shared", "shared")
            if feat.get("name") and feat["id"] not in seen: out.append(feat); seen.add(feat["id"])
        for fid, feat in (room_data.get("features", {}) or {}).items() if isinstance(room_data.get("features", {}), dict) else []:
            if isinstance(feat, dict):
                rec=dict(feat); rec.setdefault("id", str(fid)); rec.setdefault("source", "room"); rec.setdefault("local_or_shared", "local")
                if rec["id"] not in seen: out.append(rec); seen.add(rec["id"])
        for raw_obj in room_data.get("objects", []) or []:
            oid = str(raw_obj.get("template_id") or raw_obj.get("id") if isinstance(raw_obj, dict) else raw_obj)
            tmpl = dict(self.item_templates.get(oid, {}))
            if tmpl and not tmpl.get("portable", True) and oid not in seen:
                rec = {**tmpl, "id": oid, "feature_id": oid, "source": "legacy_room_object", "local_or_shared": "local", "portable": False}
                out.append(rec); seen.add(oid)
        return out

    def _legacy_spawn_id(self, room_id: str, template_id: str) -> str:
        safe_room = re.sub(r"[^a-z0-9_]+", "_", str(room_id).strip().lower()).strip("_")
        safe_template = re.sub(r"[^a-z0-9_]+", "_", str(template_id).strip().lower()).strip("_")
        return f"legacy_{safe_room}_{safe_template}"

    def _live_entity_spawns(self) -> dict[str, dict[str, Any]]:
        spawns: dict[str, dict[str, Any]] = {}
        canonical_keys: set[tuple[str, str, int]] = set()
        for raw in getattr(self.active_world, "spawns", []) or []:
            if isinstance(raw, dict) and raw.get("id"):
                rec = dict(raw)
                spawns[str(raw["id"])] = rec
                canonical_keys.add((str(rec.get("room_id") or ""), str(rec.get("entity_template_id") or rec.get("template_id") or ""), int(rec.get("quantity") or 1)))
        legacy_sources: list[tuple[str, str, str]] = []
        for room in getattr(self.active_world, "rooms", []) or []:
            rid = str(room.get("id") or "")
            for raw in (room.get("npcs", []) or []) + (room.get("mobs", []) or []) + (room.get("entities", []) or []):
                tid = str(raw.get("template_id") or raw.get("id") if isinstance(raw, dict) else raw)
                legacy_sources.append((rid, tid, "room.npcs"))
        for tid, tmpl in self.entity_templates.items():
            rid = str(tmpl.get("default_room_id") or "")
            if rid:
                legacy_sources.append((rid, tid, "entity_template.default_room_id"))
        for rid, tid, source in legacy_sources:
            if not rid or tid not in self.entity_templates:
                continue
            if (rid, tid, 1) in canonical_keys:
                continue
            sid = self._legacy_spawn_id(rid, tid)
            spawns.setdefault(sid, {"id": sid, "entity_template_id": tid, "room_id": rid, "zone_id": "", "quantity": 1, "spawn_policy": "once", "flags": ["legacy_room_npc" if source == "room.npcs" else "legacy_default_room"], "tags": [], "plugin_data": {"legacy_source": {"source_file": "rooms/rooms.json" if source == "room.npcs" else "npcs", "source_room_id": rid, "source_field": source, "normalized": True}}})
        return spawns

    def materialize_entity_spawn(self, spawn_id: str) -> dict[str, Any]:
        row=self._materialization_row("entity_spawn", spawn_id)
        if row: return row
        sp=self._live_entity_spawns().get(spawn_id); ids=[]; now=datetime.now(timezone.utc).isoformat()
        if not sp or sp.get("spawn_policy", "once") == "disabled": return {"instance_ids": [], "status": "disabled"}
        tid=str(sp.get("entity_template_id") or sp.get("template_id") or ""); rid=str(sp.get("room_id") or ""); qty=max(0, int(sp.get("quantity") or 1))
        existing = [e for e in self.find_room_entities(rid) if e.get("template_id") == tid and ((e.get("state") or {}).get("source_spawn_id") in {None, "", spawn_id})]
        for ent in existing[:qty]:
            ids.append(ent.get("entity_id") or ent.get("instance_id"))
        for _ in range(max(0, qty - len(ids))):
            ent=self.spawn_entity(tid, room_id=rid, state={"current_state":"idle", "spawn_origin": rid, "source_spawn_id": spawn_id, "custom_state": {}, "lifecycle_id": f"life_{uuid.uuid4().hex}"}, source_system="materializer"); ids.append(ent.get("entity_id") or ent.get("instance_id"))
        with sqlite3.connect(self.state_store.db_path) as conn: conn.execute("INSERT INTO content_materializations(world_id,declaration_kind,declaration_id,materialized_at,instance_ids_json,status,metadata_json) VALUES(?,?,?,?,?,?,?)", (self.active_world_id or "","entity_spawn",spawn_id,now,json.dumps(ids),"materialized",json.dumps({"template_id": tid, "room_id": rid, "quantity": qty, "adopted_existing": len(existing[:qty]), "duplicate_candidates": [e.get("instance_id") for e in existing[qty:]]})))
        self.event_bus.publish("entity_spawn_materialized", {"world_id": self.active_world_id or "", "declaration_id": spawn_id, "template_id": tid, "room_id": rid, "instance_ids": ids, "quantity": qty, "policy": sp.get("spawn_policy", "once")}, source_system="runtime", world_id=self.active_world_id or "", room_id=rid)
        return {"instance_ids": ids, "status":"materialized", "materialized_at": now}

    def _legacy_room_entity_declarations(self, room_id: str) -> list[dict[str, Any]]:
        out=[]
        for room in getattr(self.active_world, "rooms", []) or []:
            if str(room.get("id") or "") != str(room_id):
                continue
            for raw in room.get("npcs", []) or room.get("entities", []) or []:
                tid = str(raw.get("template_id") or raw.get("id") if isinstance(raw, dict) else raw)
                tmpl = self.entity_templates.get(tid, {})
                out.append({"source":"room.npcs", "template_id":tid, "name": tmpl.get("name", tid), "room_id": room_id})
        for tid, tmpl in self.entity_templates.items():
            if str(tmpl.get("default_room_id") or "") == str(room_id):
                out.append({"source":"entity_template.default_room_id", "template_id":tid, "name": tmpl.get("name", tid), "room_id": room_id})
        return out

    def entity_duplication_audit(self, target: str) -> str:
        room_id = target
        if target in self.entity_templates:
            ents = self.find_entities(template_id=target)
            room_id = ents[0].get("room_id", "") if ents else ""
        elif self.find_entity(target):
            ent = self.find_entity(target) or {}
            room_id = ent.get("room_id", "")
        contents = self.get_room_contents(room_id, include_builder_metadata=True) if room_id else {"entity_instances": [], "entity_spawn_declarations": []}
        mats=[]
        with sqlite3.connect(self.state_store.db_path) as conn:
            for row in conn.execute("SELECT declaration_id,instance_ids_json,metadata_json FROM content_materializations WHERE world_id=? AND declaration_kind='entity_spawn'", (self.active_world_id or "",)):
                meta=json.loads(row[2] or "{}")
                if not room_id or str(meta.get("room_id")) == str(room_id): mats.append((row[0], row[1], meta))
        groups={}
        for e in contents.get("entity_instances", []):
            groups.setdefault((e.get("template_id"), e.get("room_id")), []).append(e)
        risks=[f"duplicate runtime instances template={k[0]} room={k[1]} ids={[e.get('instance_id') for e in v]}" for k,v in groups.items() if len(v)>1]
        lines=[f"Room: {room_id or target}", "Runtime instances:"]
        lines += [f"- {e.get('instance_id')} template={e.get('template_id')} name={e.get('name')} room={e.get('room_id')} spawn={(e.get('state') or {}).get('source_spawn_id','')} alive={e.get('is_alive')} visible={e.get('is_visible')} created={e.get('created_at')}" for e in contents.get("entity_instances", [])] or ["- none"]
        lines += ["Spawn declarations:"] + ([f"- {s.get('id')} template={s.get('entity_template_id')} room={s.get('room_id')} qty={s.get('quantity',1)}" for s in contents.get("entity_spawn_declarations", [])] or ["- none"])
        lines += ["Legacy declarations:"] + ([f"- {d.get('source')} template={d.get('template_id')} name={d.get('name')}" for d in self._legacy_room_entity_declarations(room_id)] or ["- none"])
        lines += ["Materialization records:"] + ([f"- {m[0]} ids={m[1]} meta={json.dumps(m[2], sort_keys=True)}" for m in mats] or ["- none"])
        lines += ["Expected runtime quantity:", f"- {sum(int(s.get('quantity') or 1) for s in contents.get('entity_spawn_declarations', []))}"]
        lines += ["Actual runtime instance count:", f"- {len(contents.get('entity_instances', []))}"]
        lines += ["Canonical spawn count:", f"- {len(contents.get('entity_spawn_declarations', []))}"]
        lines += ["Legacy declaration count:", f"- {len(self._legacy_room_entity_declarations(room_id))}"]
        lines += ["Legacy declarations contributing to gameplay:", "- no"]
        lines += ["Renderer instance IDs:"] + ([f"- {e.get('instance_id')}" for e in contents.get('entity_instances', [])] or ["- none"])
        lines += ["Duplicate risks:"] + (risks or ["- none"])
        lines += ["Duplicate risk classification:", "- runtime_duplicate" if risks else "- none"]
        lines += ["Entity runtime source integrity: " + ("FAIL" if risks else "PASS")]
        lines += ["Recommended repair:", "- prevent new duplicates by materialization adoption; inspect duplicate risks before manual cleanup"]
        return "\n".join(lines)

    def _publish_entity_event(self, name: str, ent: dict[str, Any], source_system: str = "runtime", **extra: Any) -> None:
        payload = {"entity_id": ent.get("entity_id"), "entity_type": ent.get("entity_type"), "world_id": ent.get("world_id", self.active_world_id or ""), "room_id": ent.get("current_room_id", ""), "template_id": ent.get("template_id"), "source_system": source_system, "timestamp": datetime.now(timezone.utc).isoformat(), **extra}
        self.event_bus.publish(name, payload, source_system=source_system, world_id=payload.get("world_id", ""), character_id=payload.get("character_id", ""), account_id=payload.get("account_id", ""), session_id=payload.get("session_id", ""), room_id=payload.get("room_id", ""))
        if name == "room_entities_changed":
            self.event_bus.publish("room_population_changed", payload, source_system=source_system, world_id=payload.get("world_id", ""), character_id=payload.get("character_id", ""), account_id=payload.get("account_id", ""), session_id=payload.get("session_id", ""), room_id=payload.get("room_id", ""))

    def _seed_room_entities(self) -> None:
        if not self.active_world_id: return
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.state_store.db_path) as conn:
            for tid, tmpl in self.entity_templates.items():
                rid = str(tmpl.get("default_room_id") or "")
                if not rid: continue
                if conn.execute("SELECT 1 FROM entity_instances WHERE world_id=? AND current_room_id=? AND template_id=? AND destroyed_at IS NULL LIMIT 1", (self.active_world_id, rid, tid)).fetchone():
                    continue
                seed = f"{tid}:{rid}:0"
                try: conn.execute("INSERT INTO room_entity_seeds(world_id,room_id,template_id,seed_key,created_at) VALUES(?,?,?,?,?)", (self.active_world_id, rid, tid, seed, now))
                except sqlite3.IntegrityError: continue
                eid=f"ent_{uuid.uuid4().hex}"
                conn.execute("INSERT INTO entity_instances(entity_id,world_id,entity_type,template_id,name,keywords,short_description,long_description,current_room_id,owner_type,owner_id,faction_id,level,state,flags,created_at,updated_at,plugin_data) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (eid,self.active_world_id,tmpl['entity_type'],tid,tmpl['name'],json.dumps(tmpl['keywords']),tmpl['short_description'],tmpl['long_description'],rid,"room","",tmpl.get('faction_id',''),int(tmpl.get('level',1) or 1),json.dumps(tmpl.get('state',{})),json.dumps(tmpl.get('flags',[])),now,now,json.dumps(tmpl.get('plugin_data',{}))))


    ENTITY_STATES = {"idle", "standing", "sitting", "sleeping", "resting", "wandering", "following", "guarding", "trading", "training", "healing", "casting", "dead", "corpse", "despawned"}
    HIDDEN_VISIBILITY_FLAGS = {"hidden", "invisible", "builder_hidden", "future_stealth"}

    def populate_world(self) -> None:
        """Backward-compatible alias for idempotent world materialization."""
        self.materialize_world_content(self.active_world_id or "")

    def find_entities(self, **filters: Any) -> list[dict[str, Any]]:
        clauses = ["world_id=?"]; params: list[Any] = [self.active_world_id or ""]
        for key, column in {"template_id":"template_id", "entity_type":"entity_type", "room_id":"current_room_id", "owner_type":"owner_type", "owner_id":"owner_id"}.items():
            if filters.get(key): clauses.append(f"{column}=?"); params.append(str(filters[key]))
        return self._fetch_entities(" AND ".join(clauses), tuple(params))

    def _entity_hidden(self, ent: dict[str, Any]) -> bool:
        flags = set(str(v) for v in ent.get("visibility_flags", []) or []) | set(str(v) for v in ent.get("flags", []) or [])
        state = ent.get("state", {}) if isinstance(ent.get("state"), dict) else {}
        current = str(state.get("current_state") or ent.get("current_state") or "")
        return bool(flags & self.HIDDEN_VISIBILITY_FLAGS) or current in {"despawned"} or state.get("is_visible") is False

    def is_entity_visible(self, ent: dict[str, Any], viewer: Any = None) -> bool:
        if ent.get("entity_type") in {"npc", "mob"} and (not ent.get("is_alive") or ent.get("current_state") in {"dead", "corpse", "despawned"}):
            return False
        return not self._entity_hidden(ent)

    def change_entity_state(self, entity_id: str, current_state: str, source_system: str = "runtime", **ctx: Any) -> dict[str, Any]:
        if current_state not in self.ENTITY_STATES: raise ValueError(f"Unsupported entity state: {current_state}")
        ent = self.find_entity(entity_id) or {}; state = dict(ent.get("state") or {})
        state["current_state"] = current_state; state["is_alive"] = current_state not in {"dead", "corpse", "despawned"}
        return self.update_entity_state(entity_id, state, source_system=source_system, **ctx)

    def teleport_entity(self, entity_id: str, room_id: str, **ctx: Any) -> dict[str, Any]:
        return self.move_entity(entity_id, room_id, **ctx)

    def return_to_spawn(self, entity_id: str, **ctx: Any) -> dict[str, Any]:
        ent = self.find_entity(entity_id) or {}; return self.move_entity(entity_id, ent.get("spawn_origin") or ent.get("room_id") or "", **ctx)

    def reset_entity(self, entity_id: str, source_system: str = "runtime", **ctx: Any) -> dict[str, Any]:
        ent = self.find_entity(entity_id) or {}; tmpl = dict(self.entity_templates.get(ent.get("template_id", ""), {})); state = dict(tmpl.get("state") or {"current_state":"idle"}); state["last_reset"] = datetime.now(timezone.utc).isoformat()
        self.update_entity_state(entity_id, state, source_system=source_system, **ctx)
        if tmpl.get("default_room_id"): self.move_entity(entity_id, tmpl["default_room_id"], source_system=source_system, **ctx)
        self._publish_entity_event("entity_reset", self.find_entity(entity_id) or ent, source_system=source_system, **ctx)
        return self.find_entity(entity_id) or {}

    def respawn_entity(self, template_id: str, room_id: str | None = None, **ctx: Any) -> dict[str, Any]:
        tmpl = self.entity_templates.get(template_id, {})
        max_hp = int(((tmpl.get("state") or {}).get("maximum_health") or (tmpl.get("stats") or {}).get("max_health") or 100) or 100)
        return self.spawn_entity(template_id, room_id=room_id, state={"current_state":"idle", "spawn_origin": room_id or "", "current_health": max_hp, "maximum_health": max_hp, "is_alive": True, "lifecycle_id": f"life_{uuid.uuid4().hex}", "source_spawn_id": ctx.get("spawn_id", "")}, **ctx)

    def _ensure_entity_respawn_schema(self) -> None:
        with sqlite3.connect(self.state_store.db_path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS entity_respawn_queue(
                respawn_id TEXT PRIMARY KEY,
                world_id TEXT,
                template_id TEXT,
                spawn_id TEXT,
                room_id TEXT,
                old_entity_id TEXT,
                old_lifecycle_id TEXT,
                due_at TEXT,
                state TEXT,
                new_entity_id TEXT,
                created_at TEXT,
                updated_at TEXT,
                metadata_json TEXT
            )""")

    def schedule_entity_respawn(self, ent: dict[str, Any], *, death_id: str = "") -> None:
        tmpl = self.entity_templates.get(str(ent.get("template_id") or ""), {})
        if not tmpl.get("respawn_enabled") or str(tmpl.get("respawn_mode") or "normal") == "story_permanent":
            return
        delay = int(tmpl.get("respawn_delay_seconds") or (tmpl.get("spawn_rules") or {}).get("respawn_delay") or 0)
        if delay <= 0:
            return
        self._ensure_entity_respawn_schema()
        state = ent.get("state") or {}
        spawn_id = str(tmpl.get("spawn_id") or tmpl.get("id") or ent.get("template_id") or "")
        old_lifecycle = str(state.get("lifecycle_id") or ent.get("entity_id") or "")
        respawn_id = "respawn_" + uuid.uuid5(uuid.NAMESPACE_URL, f"{self.active_world_id}:{death_id or ent.get('entity_id')}:{old_lifecycle}").hex
        now = datetime.now(timezone.utc)
        due = (now + timedelta(seconds=delay)).isoformat()
        with sqlite3.connect(self.state_store.db_path) as conn:
            conn.execute("""INSERT OR IGNORE INTO entity_respawn_queue(respawn_id,world_id,template_id,spawn_id,room_id,old_entity_id,old_lifecycle_id,due_at,state,new_entity_id,created_at,updated_at,metadata_json)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""", (respawn_id, self.active_world_id or "", ent.get("template_id"), spawn_id, ent.get("room_id") or ent.get("current_room_id"), ent.get("entity_id"), old_lifecycle, due, "WAITING_TO_RESPAWN", "", now.isoformat(), now.isoformat(), json.dumps({"death_id": death_id, "delay_seconds": delay})))
        logger.info("entity respawn scheduled template=%s old_entity=%s due_at=%s state=WAITING_TO_RESPAWN", ent.get("template_id"), ent.get("entity_id"), due)

    def process_due_entity_respawns(self, now: str | None = None) -> list[dict[str, Any]]:
        self._ensure_entity_respawn_schema()
        now = now or datetime.now(timezone.utc).isoformat()
        made: list[dict[str, Any]] = []
        with sqlite3.connect(self.state_store.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = [dict(r) for r in conn.execute("SELECT * FROM entity_respawn_queue WHERE world_id=? AND state IN ('WAITING_TO_RESPAWN','READY_TO_RESPAWN') AND due_at<=? ORDER BY due_at,respawn_id", (self.active_world_id or "", now))]
        for row in rows:
            alive = [e for e in self.find_entities(template_id=row["template_id"], room_id=row["room_id"]) if e.get("entity_type") in {"npc","mob"} and e.get("is_alive")]
            if alive:
                with sqlite3.connect(self.state_store.db_path) as conn:
                    conn.execute("UPDATE entity_respawn_queue SET state='ACTIVE_NEW_LIFECYCLE',new_entity_id=?,updated_at=? WHERE respawn_id=?", (alive[0].get("entity_id"), now, row["respawn_id"]))
                continue
            ent = self.respawn_entity(row["template_id"], row["room_id"], source_system="respawn", spawn_id=row.get("spawn_id",""))
            made.append(ent)
            with sqlite3.connect(self.state_store.db_path) as conn:
                conn.execute("UPDATE entity_respawn_queue SET state='ACTIVE_NEW_LIFECYCLE',new_entity_id=?,updated_at=? WHERE respawn_id=?", (ent.get("entity_id",""), now, row["respawn_id"]))
            msg = str(self.entity_templates.get(row["template_id"], {}).get("respawn_message") or f"{ent.get('name','Someone')} arrives.")
            combat_rt = getattr(self, "combat_runtime", None)
            if combat_rt and hasattr(combat_rt, "active_character_ids_in_room") and hasattr(combat_rt, "enqueue_output"):
                for cid in combat_rt.active_character_ids_in_room(row["room_id"]):
                    combat_rt.enqueue_output(cid, msg, room_id=row["room_id"], category="respawn")
        return made

    def create_corpse(self, entity_id: str, **ctx: Any) -> dict[str, Any]:
        ent = self.find_entity(entity_id) or {}
        if not ent:
            return {}
        death_id = str(ctx.get("death_id") or "")
        source_lifecycle_id = str((ent.get("state") or {}).get("lifecycle_id") or entity_id)
        existing = [c for c in self.find_entities(entity_type="corpse", room_id=ent.get("room_id")) if (death_id and (c.get("state") or {}).get("death_id") == death_id) or ((not death_id) and (c.get("state") or {}).get("source_entity_id") == entity_id and (c.get("state") or {}).get("source_lifecycle_id") == source_lifecycle_id)]
        if existing:
            return existing[0]
        name = str(ent.get("name") or "creature")
        state = dict(ent.get("state") or {})
        state.update({"current_state":"dead", "is_alive": False, "current_health": 0})
        self.update_entity_state(entity_id, state, source_system=ctx.get("source_system", "runtime"))
        corpse_state={"current_state":"corpse", "source_entity_id": entity_id, "source_template_id": ent.get("template_id"), "source_actor_name": name, "source_lifecycle_id": source_lifecycle_id, "death_id": death_id, "killer_actor_id": str(ctx.get("killer_actor_id") or ""), "is_alive": False, "container_open": True, "decay_state": "fresh", "created_world_time": self.get_world_time(self.active_world_id or '').get('total_minutes', 0), "skinned": False, "butchered": False}
        corpse = self.spawn_entity(ent.get("template_id", "corpse"), entity_type="corpse", room_id=ent.get("room_id"), state=corpse_state, flags=["corpse"], **ctx)
        corpse_name = f"The corpse of {name.lower()}"
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.state_store.db_path) as conn:
            conn.execute("UPDATE entity_instances SET name=?,keywords=?,short_description=?,long_description=?,updated_at=? WHERE entity_id=?", (corpse_name, json.dumps(["corpse", "body", *str(name).lower().split()]), f"The corpse of {name.lower()} is lying here.", f"{corpse_name}. It was recently slain. Blood darkens the fur and flesh around several wounds.", now, corpse.get("entity_id")))
        corpse = self.find_entity(corpse.get("entity_id")) or corpse
        self._generate_corpse_contents(corpse, ent, ctx)
        self.schedule_entity_respawn(ent, death_id=death_id)
        self._publish_entity_event("corpse_created", corpse, source_system=ctx.get("source_system", "runtime"), source_entity_id=entity_id)
        return corpse

    def _generate_corpse_contents(self, corpse: dict[str, Any], source_ent: dict[str, Any], ctx: dict[str, Any] | None = None) -> None:
        ctx = ctx or {}; corpse_id = corpse.get("entity_id", "")
        tmpl = dict(self.entity_templates.get(str(source_ent.get("template_id") or ""), {}))
        loot_table = tmpl.get("loot_table") or ""
        if not loot_table:
            return
        from engine.rewards import RewardService
        svc = RewardService(runtime=self, world_id=self.active_world_id or "shattered_realms", event_bus=self.event_bus)
        pkt = svc.resolve_loot_table(loot_table, {"source_type":"combat","source_id":str(source_ent.get("template_id")),"source_instance_id":str(ctx.get("death_id") or source_ent.get("entity_id")),"world_id":self.active_world_id or "","world_time":self.get_world_time(self.active_world_id or '').get('total_minutes',0)}, {"recipient_type":"corpse","recipient_id":corpse_id}, seed=str(ctx.get('death_id') or corpse_id))
        svc.deliver_reward_packet(pkt["reward_packet_id"])
        self.event_bus.publish("corpse_contents_generated", {"corpse_entity_id":corpse_id,"source_entity_id":source_ent.get("entity_id"),"loot_table_id":loot_table,"reward_packet_id":pkt["reward_packet_id"]}, source_system="runtime", world_id=self.active_world_id or "", room_id=corpse.get("room_id"))

    def find_container_items(self, owner_id: str) -> list[dict[str, Any]]:
        return self._fetch_items("owner_type IN ('corpse','container') AND owner_id=?", (owner_id,))

    def get_dialogue(self, template_id: str) -> dict[str, Any]:
        return dict((self.entity_templates.get(template_id) or {}).get("dialogue_package") or {})

    def talk_to_entity(self, character_id: str, query: str, keyword: str = "") -> str:
        char = self.state_store.load_character(character_id); candidates = self.find_visible_entities(char.room_id if char else "").get("npcs", []) + self.find_visible_entities(char.room_id if char else "").get("mobs", [])
        res = self.resolve_entity_keywords(query, candidates)
        if res["status"] != "ok": return self._resolve_message(res, "They are not here.")
        ent = res["entity"]; pkg = self.get_dialogue(ent.get("template_id", "")); text = ""
        if keyword:
            text = str((pkg.get("keyword_responses") or {}).get(keyword.lower(), ""))
        semantic_kind = "dialogue"
        if not text:
            responses = pkg.get("talk_responses") or []
            text = str(responses[0] if responses else pkg.get("greeting") or "What can I help you with?")
        blocked = ("speaks from their role", "personality", "invented world facts", "instruction", "prompt", "metadata")
        lower_text = text.lower().strip()
        if any(b in lower_text for b in blocked):
            text = "What can I help you with?"
            semantic_kind = "dialogue"
        elif lower_text.startswith(("they ", "he ", "she ", "it ")) or " acknowledge" in lower_text or " nod" in lower_text:
            semantic_kind = "action"
            if lower_text.startswith("they acknowledge"):
                text = "acknowledges your greeting"
        self._publish_entity_event("entity_dialogue", ent, character_id=character_id, dialogue_keyword=keyword, dialogue_text=text, semantic_kind=semantic_kind)
        char_for_event = self.state_store.load_character(character_id)
        if char_for_event:
            self._publish_interaction_event("entity_interaction", char_for_event, "talk", f"talk {query}", {"target_kind": ent.get("entity_type"), "target_name": ent.get("name"), "result_summary": text})
            self._publish_interaction_event("interaction_succeeded", char_for_event, "talk", f"talk {query}", {"target_kind": ent.get("entity_type"), "target_name": ent.get("name"), "result_summary": text})
        name = ent.get("name")
        if semantic_kind == "action":
            action_text = text
            if action_text[:1].isupper() and str(action_text).split()[0] in {"They", "He", "She", "It"}:
                action_text = "acknowledges your greeting"
            if not str(action_text).lower().startswith(str(name).lower()):
                action_text = f"{name} {action_text}"
            return semantic("emote", action_text.rstrip("." ) + ".")
        return semantic("dialogue", f'{name} says, "{text}"')

    def _handle_dialogue_command(self, char: MudCharacter, cmd: str, args: list[str]):
        from engine.mud_commands import CommandResult
        if cmd not in {"talk", "greet", "hello"}: return None
        if not args: return CommandResult("Talk to whom?", ok=False)
        keyword = ""
        if "about" in [a.lower() for a in args]:
            idx=[a.lower() for a in args].index("about"); query=" ".join(args[:idx]); keyword=" ".join(args[idx+1:])
        else: query=" ".join(args)
        return CommandResult(self.talk_to_entity(char.id, query, keyword))

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
            "dialogue": "#ffffff",
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
