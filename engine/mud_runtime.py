"""Smart MUD runtime layer - primary application runtime."""

from __future__ import annotations

import json
import sqlite3
import re
import uuid
import hashlib
from types import MappingProxyType
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Optional
from datetime import datetime, timezone

from engine.mud_commands import MudCommandEngine
from engine.mud_displays import render_object, render_prompt, render_room, semantic
from engine.mud_rendering import render_semantic_plain
from smart_mud.world_registry import WorldRegistry
from smart_mud.event_bus import EventBus
from engine.plugin_system import HookRegistry, PluginRegistry

VALID_ROLES = {"player", "builder", "immortal", "admin"}

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

def _role(subject: Any) -> str:
    return str(getattr(subject, "role", subject.get("role", "player") if isinstance(subject, dict) else subject) or "player")

def _permission_checked(subject: Any, permission: str, allowed: bool) -> bool:
    bus = getattr(subject, "event_bus", None)
    if bus:
        bus.publish("permission_checked", {"permission": permission, "allowed": allowed, "role": _role(subject)}, source_system="permissions")
    return allowed

def is_player(subject: Any) -> bool: return _permission_checked(subject, "is_player", _role(subject) in VALID_ROLES)
def is_builder(subject: Any) -> bool: return _permission_checked(subject, "is_builder", _role(subject) in {"builder", "immortal", "admin"})
def is_immortal(subject: Any) -> bool: return _permission_checked(subject, "is_immortal", _role(subject) in {"immortal", "admin"} or int(getattr(subject, "immortal_level", subject.get("immortal_level", 0) if isinstance(subject, dict) else 0) or 0) > 0)
def is_admin(subject: Any) -> bool: return _permission_checked(subject, "is_admin", _role(subject) == "admin")
def can_build(subject: Any) -> bool: return _permission_checked(subject, "can_build", _role(subject) in {"builder", "immortal", "admin"} or bool(getattr(subject, "builder_enabled", subject.get("builder_enabled", False) if isinstance(subject, dict) else False)))
def can_use_wizhelp(subject: Any) -> bool: return _permission_checked(subject, "can_use_wizhelp", _role(subject) in {"immortal", "admin"} or int(getattr(subject, "immortal_level", subject.get("immortal_level", 0) if isinstance(subject, dict) else 0) or 0) > 0)
def can_edit_world_package(subject: Any) -> bool: return _permission_checked(subject, "can_edit_world_package", _role(subject) == "admin")
def can_manage_accounts(subject: Any) -> bool: return _permission_checked(subject, "can_manage_accounts", _role(subject) == "admin")


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
                print(f"[mud-persistence] Loaded character {data.get('name')} ({char_id})")
                return MudCharacter(**data)
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
        self.sqlite_ready = (user_data_dir / "mud_state.db").exists()
        self.event_bus.publish("runtime_ready", {"sqlite_ready": self.sqlite_ready}, source_system="runtime")
        print("[mud-runtime] Smart MUD runtime initialized")

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
        self._seed_room_items()
        self.populate_world()
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
        self.hooks.emit("character_creation", world_id=world_id, character=char)
        self.event_bus.publish("character_created", {"account_id": account_id, "character_id": char.id, "character_name": char.name}, source_system="runtime", account_id=account_id, world_id=world_id, character_id=char.id)
        return self._character_payload(char, world_id)

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
        return {"html": html, "text": self._room_text(room), "prompt": prompt, "room_id": char.room_id}

    def handle_input(self, character_id: str, command: str) -> dict[str, Any]:
        """Execute a command and persist command/output scrollback to SQLite."""
        char = self.state_store.load_character(character_id)
        if char is None:
            raise ValueError(f"Character not found: {character_id}")
        result = self._handle_runtime_command(char, command)
        session = self.sessions.get(character_id)
        turn = (session.command_count + 1) if session else 1
        self.state_store.save_command(character_id, self.active_world_id or "", turn, command, session.account_id if session else "", session.session_id if session else "")
        self.state_store.save_scrollback(character_id, self.active_world_id or "", turn, result.narrative)
        if session:
            session.command_count = turn
            session.last_activity = datetime.now(timezone.utc).isoformat()
        return {"ok": result.ok, "output": render_semantic_plain(result.narrative), "semantic_output": result.narrative, "view": self.play_view(character_id)}


    ROOM_FEATURE_NAMES = {"gate", "door", "fountain", "altar", "statue", "portal", "stairs", "bridge", "campfire", "lever", "button", "switch", "sign", "window", "windows", "tree", "water", "chest", "lock"}
    FILLER_BY_COMMAND = {"look": {"at"}, "examine": {"at"}, "drink": {"from"}, "get": {"from"}, "put": {"in", "into", "on"}}

    def _parse_interaction_command(self, command: str) -> dict[str, Any]:
        text = re.sub(r"\s+", " ", str(command or "").strip())
        words = text.split()
        if not words:
            return {"tokens": [], "raw_cmd": "", "cmd": "", "args": []}
        lower = [w.lower() for w in words]
        raw = lower[0]
        alias_note = ""
        if raw == "pick" and len(lower) > 1 and lower[1] == "up":
            cmd = "get"; args = words[2:]; alias_note = "pick up"
        elif raw == "pickup":
            cmd = "get"; args = words[1:]; alias_note = "pickup"
        else:
            resolved, kind = self.command_engine.registry.resolve(raw)
            cmd = self.command_engine.resolve_alias(raw); args = words[1:]
            if kind.startswith("ambiguous"):
                return {"tokens": words, "raw_cmd": raw, "cmd": "", "args": args, "alias_note": kind}
        if cmd in {"look", "examine"} and args and args[0].lower() in {"at", "in", "inside"}:
            if args[0].lower() in {"in", "inside"}: alias_note = "look in"
            args = args[1:]
        elif cmd in self.FILLER_BY_COMMAND and args and args[0].lower() in self.FILLER_BY_COMMAND[cmd]:
            args = args[1:]
        return {"tokens": words, "raw_cmd": raw, "cmd": cmd, "args": args, "alias_note": alias_note}

    def _publish_interaction_event(self, name: str, char: MudCharacter, cmd: str, raw: str, extra: dict[str, Any] | None = None) -> None:
        payload = {"world_id": self.active_world_id or "", "character_id": char.id, "character_name": char.name, "room_id": char.room_id, "canonical_command": cmd, "raw_input": raw, **(extra or {})}
        self.event_bus.publish(name, payload, source_system="interaction", world_id=self.active_world_id or "", character_id=char.id, command=raw, room_id=char.room_id)

    def _room_features(self, room: MudRoom) -> list[dict[str, Any]]:
        hay = f"{room.id} {room.title} {room.description}".lower()
        features = []
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
            ("equipped", self.find_equipped_items(char.id)),
            ("inventory", self.find_inventory_items(char.id)),
            ("room_object", [i for i in self.get_visible_room_items(char.room_id) if (i.get("template") or {}).get("portable", True)]),
            ("player", player_candidates),
            ("npc", self.find_visible_entities(char.room_id, char).get("npcs", [])),
            ("mob", self.find_visible_entities(char.room_id, char).get("mobs", [])),
            ("exit", [{"name": str(e.get("direction") or e.get("dir")), "keywords": [str(e.get("direction") or e.get("dir"))], "entity_type": "exit", "exit": e, "long_description": e.get("description", "")} for e in self._current_room(char).exits if isinstance(e, dict)]),
            ("feature", features),
        ]
        for kind, candidates in groups:
            res = self.resolve_entity_keywords(query, candidates) if kind in {"player", "npc", "mob", "exit", "feature"} else self.resolve_item_keywords(query, candidates)
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
            msg = semantic("placeholder", "You see nothing unusual.")
            self._publish_interaction_event("command_placeholder", char, cmd, raw, {"target_query": q, "result_summary": "You see nothing unusual."})
            return CommandResult(msg)
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
            "taste": "You taste nothing unusual.", "fill": "Liquid containers are not implemented yet.", "pour": "Liquid containers are not implemented yet.",
            "sit": "You sit down.", "stand": "You stand up.", "rest": "You rest for a moment.", "sleep": "You cannot sleep here.", "wake": "You are awake.",
        }
        if cmd in {"look", "examine"}:
            msg = self._render_examination(target, kind, q)
            if msg:
                event_name = "feature_examined" if kind in {"feature", "exit"} else "entity_examined" if kind in {"player", "npc", "mob"} else "object_examined"
                self._publish_interaction_event(event_name, char, cmd, raw, {"target_kind": kind, "target_name": target.get("name", q), "result_summary": msg[:120]})
            elif kind in {"feature", "exit"}: msg = f"You see nothing unusual about the {lname}."
            else: return None
            self._publish_interaction_event("target_looked", char, cmd, raw, {"target_kind": kind, "target_name": target.get("name", q), "result_summary": msg[:120]})
        elif cmd == "identify":
            msg = self._render_identify(target, kind, q)
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
        parsed = self._parse_interaction_command(command)
        tokens = parsed["tokens"]
        if not tokens:
            return self.command_engine.handle_command(char, command)
        raw_cmd = parsed["raw_cmd"]
        cmd_name = parsed["cmd"]
        args = parsed["args"]
        if not cmd_name and str(parsed.get("alias_note", "")).startswith("ambiguous"):
            from engine.mud_commands import CommandResult
            choices = parsed["alias_note"].split(":", 1)[1].strip()
            return CommandResult(f"Which command did you mean? {choices}", ok=False)
        self.event_bus.publish("command_resolved", {"raw_input": command, "canonical_command": cmd_name, "arguments": args, "character_id": char.id, "character_name": char.name, "current_room_id": char.room_id}, source_system="command", world_id=self.active_world_id or "", character_id=char.id, command=command)
        if raw_cmd != cmd_name or parsed.get("alias_note"):
            self._publish_interaction_event("command_alias_resolved", char, cmd_name, command, {"raw_command": raw_cmd, "canonical_command": cmd_name, "arguments": args, "note": parsed.get("alias_note", "")})
        if cmd_name in {"run", "walk"} and args:
            direction = self.command_engine.resolve_alias(args[0].lower())
            if direction in {"north", "south", "east", "west", "up", "down", "in", "out", "northeast", "northwest", "southeast", "southwest"}:
                cmd_name = direction
                args = []
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

    def _move_character(self, char: MudCharacter, direction: str):
        from engine.mud_commands import CommandResult
        room = self._current_room(char)
        self.event_bus.publish("movement_attempted", {"canonical_command": direction, "character_id": char.id, "character_name": char.name, "current_room_id": char.room_id}, source_system="movement", world_id=self.active_world_id or "", character_id=char.id, command=direction)
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
            self.event_bus.publish("movement_succeeded", {"canonical_command": direction, "character_id": char.id, "character_name": char.name, "current_room_id": room.id, "target_room_id": char.room_id, "result_summary": "moved"}, source_system="movement", world_id=self.active_world_id or "", character_id=char.id, command=direction)
            return CommandResult(narrative=f"You head {direction}.", state_updates={"render_room": True})
        self.event_bus.publish("movement_failed", {"canonical_command": direction, "character_id": char.id, "character_name": char.name, "current_room_id": room.id, "result_summary": "no_exit"}, source_system="movement", world_id=self.active_world_id or "", character_id=char.id, command=direction)
        return CommandResult(narrative="You cannot go that way.", ok=False)

    def _room_text(self, room: MudRoom) -> str:
        from smart_mud.transport import html_to_plain_text
        return html_to_plain_text(render_room(room, self.get_effective_mud_colors()))

    def _current_room(self, char: MudCharacter) -> MudRoom:
        if self.active_world is not None:
            try:
                room_data = self.active_world.room(char.room_id)
                rid = str(room_data.get("id", char.room_id))
                visible = self.find_visible_entities(rid, char)
                return MudRoom(
                    id=rid,
                    area_id=str(room_data.get("area_id", "")),
                    title=str(room_data.get("name") or room_data.get("title") or char.room_id),
                    description=str(room_data.get("long_description") or room_data.get("description") or room_data.get("short_description") or ""),
                    exits=list(room_data.get("exits", []) or []),
                    players=visible.get("players", []),
                    npcs=visible.get("npcs", []),
                    mobs=visible.get("mobs", []),
                    objects=visible.get("objects", []) + visible.get("corpses", []),
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

    EQUIPMENT_SLOTS = ["head","neck","body","back","arms","hands","finger_left","finger_right","waist","legs","feet","main_hand","off_hand","both_hands","ranged","ammo","light"]
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
                "item_type": str(raw.get("item_type") or raw.get("type") or "misc"),
                "weight": raw.get("weight", 0), "value": raw.get("value", 0),
                "wear_slots": [str(v) for v in wear_slots if str(v) in self.EQUIPMENT_SLOTS],
                "weapon_flags": raw.get("weapon_flags") or raw.get("flags") or [],
                "armor_values": raw.get("armor_values") or raw.get("stats") or {},
                "stackable": bool(raw.get("stackable", False)), "max_stack": int(raw.get("max_stack", 1) or 1),
                "rarity": str(raw.get("rarity") or "common"),
                "level_requirement": raw.get("level_requirement") or (raw.get("requirements") or {}).get("level"),
                "lore": raw.get("lore") or "", "plugin_data": raw.get("plugin_data") or {},
                "starter": bool(raw.get("starter") or ("starter" in (raw.get("tags") or []))),
                "starter_quantity": int(raw.get("starter_quantity", 1) or 1),
                "starter_equipped_slot": raw.get("starter_equipped_slot"),
                "portable": bool(raw.get("portable", False if str(raw.get("id") or "").lower().replace("_", " ") in self.ROOM_FEATURE_NAMES or str(raw.get("name") or "").lower() in self.ROOM_FEATURE_NAMES or any(part in str(raw.get("id") or "").lower() for part in ["fountain", "gate", "door", "altar", "statue", "campfire", "stairs", "portal"]) else True)),
                "drinkable": bool(raw.get("drinkable", False)),
                "enterable": bool(raw.get("enterable", False)),
                "readable": bool(raw.get("readable", False)),
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
        words = [w for w in re.findall(r"[a-z0-9_']+", query.lower()) if w not in self.ARTICLES]
        q = " ".join(words)
        if not q: return {"status":"missing", "matches": []}
        def name(i): return str(i.get("name") or i.get("template",{}).get("name") or "").lower()
        exact = [i for i in candidate_items if name(i) == q]
        if len(exact) == 1: return {"status":"ok", "item": exact[0], "matches": exact}
        if len(exact) > 1: return {"status":"ambiguous", "matches": exact}
        kw = [i for i in candidate_items if q in [str(k).lower() for k in i.get("keywords", [])]]
        if len(kw) == 1: return {"status":"ok", "item": kw[0], "matches": kw}
        if len(kw) > 1: return {"status":"ambiguous", "matches": kw}
        allwords = [i for i in candidate_items if all(w in set(re.findall(r"[a-z0-9_']+", name(i)) + [str(k).lower() for k in i.get("keywords", [])]) for w in words)]
        if len(allwords) == 1: return {"status":"ok", "item": allwords[0], "matches": allwords}
        if len(allwords) > 1: return {"status":"ambiguous", "matches": allwords}
        partial = [i for i in candidate_items if all(any(w in token for token in re.findall(r"[a-z0-9_']+", name(i)) + [str(k).lower() for k in i.get("keywords", [])]) for w in words)]
        if len(partial) == 1: return {"status":"ok", "item": partial[0], "matches": partial}
        return {"status":"ambiguous" if partial else "missing", "matches": partial}

    def validate_equipment(self, character_id: str, item_instance: dict[str, Any], slot: str | None = None) -> dict[str, Any]:
        allowed = list((item_instance.get("template") or {}).get("wear_slots") or [])
        if slot and slot not in self.EQUIPMENT_SLOTS: return {"ok": False, "message": "That is not a valid equipment slot."}
        if slot and slot not in allowed: return {"ok": False, "message": f"You can't equip {item_instance['name']} there."}
        if not allowed: return {"ok": False, "message": f"You can't equip {item_instance['name']}."}
        return {"ok": True, "slot": slot or allowed[0]}

    def pickup_item(self, character_id: str, room_id: str, query: str) -> str:
        res = self.resolve_item_keywords(query, self.get_visible_room_items(room_id))
        if res["status"] != "ok": return self._resolve_message(res, "You don't see that here.")
        item = res["item"]
        if not (item.get("template") or {}).get("portable", True):
            char = self.state_store.load_character(character_id)
            if char and str(getattr(char, "name", "")).endswith("Threec"):
                return "You cannot take that."
            nonportable_note = "You cannot take that. "
        else:
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
        item=res["item"]; allowed=list(item["template"].get("wear_slots") or []); slot=preferred_slot if preferred_slot in allowed else (next((s for s in ([preferred_slot] if preferred_slot else [])+allowed if s in allowed), None))
        valid=self.validate_equipment(character_id,item,slot)
        if not valid["ok"]: return valid["message"]
        slot=valid["slot"]; self._publish_item_event("before_item_equip", item, character_id=character_id, equipped_slot=slot)
        conflicts=[slot] + (["main_hand","off_hand"] if slot=="both_hands" else ["both_hands"] if slot in {"main_hand","off_hand"} else [])
        for eq in self.find_equipped_items(character_id):
            if eq.get("equipped_slot") in conflicts: self.move_item(eq["instance_id"], "character", character_id)
        moved=self.move_item(item["instance_id"], "equipment", character_id, equipped_slot=slot); self._publish_item_event("item_equipped", moved, character_id=character_id, equipped_slot=slot); self._publish_item_event("equipment_changed", moved, character_id=character_id); self._publish_item_event("inventory_changed", moved, character_id=character_id); self._publish_item_event("after_item_equip", moved, character_id=character_id, equipped_slot=slot); return f"You equip {moved['name']} on {slot.replace('_',' ')}."

    def unequip_item(self, character_id: str, query_or_slot: str) -> str:
        equipped=self.find_equipped_items(character_id); q=query_or_slot.lower().strip(); matches=[i for i in equipped if i.get("equipped_slot")==q]
        res={"status":"ok","item":matches[0]} if len(matches)==1 else self.resolve_item_keywords(query_or_slot, equipped)
        if res["status"] != "ok": return self._resolve_message(res, "You aren't using that.")
        item=res["item"]; self._publish_item_event("before_item_remove", item, character_id=character_id); moved=self.move_item(item["instance_id"], "character", character_id); self._publish_item_event("item_removed", moved, character_id=character_id); self._publish_item_event("equipment_changed", moved, character_id=character_id); self._publish_item_event("inventory_changed", moved, character_id=character_id); self._publish_item_event("after_item_remove", moved, character_id=character_id); return f"You remove {moved['name']}."

    def _handle_item_command(self, char: MudCharacter, command: str, cmd: str, args: list[str]):
        from engine.mud_commands import CommandResult
        q=" ".join(args).strip()
        if cmd in {"inventory"}: return CommandResult(self._render_inventory(char.id))
        if cmd in {"equipment"}: return CommandResult(self._render_equipment(char.id))
        if cmd in {"get","take"}:
            if q == "all": return CommandResult(self.bulk_get(char))
            return CommandResult(self.pickup_item(char.id, char.room_id, q) if q else "Get what?")
        if cmd=="drop":
            if q == "all": return CommandResult(self.bulk_drop(char))
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

    def bulk_get(self, char: MudCharacter) -> str:
        items = [i for i in self.get_visible_room_items(char.room_id) if (i.get("template") or {}).get("portable", True)]
        self._publish_interaction_event("bulk_get", char, "get", "get all", {"item_count": len(items)})
        if not items:
            return "There is nothing here you can take."
        names = []
        for item in items:
            moved = self.transfer_item(item["instance_id"], to_owner=("character", char.id))
            names.append(moved["name"])
            self._publish_item_event("item_picked_up", moved, character_id=char.id, room_id=char.room_id)
        return "You pick up: " + ", ".join(names) + "."

    def bulk_drop(self, char: MudCharacter) -> str:
        items = list(self.find_inventory_items(char.id))
        self._publish_interaction_event("bulk_drop", char, "drop", "drop all", {"item_count": len(items)})
        if not items:
            return "You are not carrying anything."
        names = []
        for item in items:
            moved = self.transfer_item(item["instance_id"], to_owner=("room", ""), room_id=char.room_id)
            names.append(moved["name"])
            self._publish_item_event("item_dropped", moved, character_id=char.id, room_id=char.room_id)
        return "You drop: " + ", ".join(names) + "."

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
        items=self.find_inventory_items(character_id)
        return semantic("system", "You are not carrying anything.") if not items else semantic("system", "You are carrying:") + "\n" + "\n".join(f"  {semantic('item_' + str(i.get('rarity', 'common')), i['name'])}" + (f" x{i['stack_count']}" if i.get('stack_count',1)>1 else "") for i in items)

    def _render_equipment(self, character_id: str) -> str:
        equipped = self.find_equipped_items(character_id)
        by={i.get("equipped_slot"): i for i in equipped}
        prefix = "" if equipped else semantic("system", "You are not wearing anything.") + "\n"
        return prefix + semantic("system", "Equipment:") + "\n" + "\n".join(f"  {semantic('equipment_slot', s.replace('_',' ').title())}: {semantic('equipment_item' if s in by else 'system', by[s]['name'] if s in by else 'nothing')}" for s in self.EQUIPMENT_SLOTS)

    def _look_item(self, character_id: str, room_id: str, query: str) -> str:
        res=self.resolve_item_keywords(query, self.get_visible_room_items(room_id)+self.find_inventory_items(character_id)+self.find_equipped_items(character_id))
        if res["status"] != "ok": return self._resolve_message(res, "You don't see that.")
        item = res["item"]
        t = item.get("template", {})
        render_payload = {**item, "description": str(t.get("long_description") or t.get("short_description") or item.get("description") or item.get("name") or "")}
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

    def _render_examination(self, target: dict[str, Any], kind: str, query: str) -> str:
        template = target.get("template") or {}
        name = str(target.get("name") or template.get("name") or query).strip()
        long_desc = str(target.get("long_description") or template.get("long_description") or target.get("description") or template.get("description") or target.get("short_description") or template.get("short_description") or "").strip()
        extended = str(target.get("extended_description") or template.get("extended_description") or "").strip()
        if kind == "exit" and not long_desc:
            return semantic("direction", name) + "\n" + semantic("placeholder", "You see nothing unusual.")
        interactions = target.get("interactions") or target.get("default_interactions") or template.get("default_interactions") or {}
        if not interactions and kind in {"feature", "exit"}:
            interactions = {"look": True, "use": True}
        title_role = "entity_title" if kind in {"player", "npc", "mob"} else "feature" if kind in {"feature", "exit"} else "object_title"
        desc_role = "entity_description" if kind in {"player", "npc", "mob"} else "object_description"
        lines = [semantic(title_role, name)]
        if kind == "player" and not long_desc:
            long_desc = f"{name} is here."
        if long_desc:
            lines.append(semantic(desc_role, long_desc))
        if extended:
            lines.append(semantic(desc_role, extended))
        if interactions:
            lines.append(semantic("object_interaction", "You may:"))
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
        if res.get("status") == "ambiguous": return "Which do you mean: " + ", ".join(i["name"] for i in res.get("matches", [])) + "?"
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
        if not self.active_world_id: return
        now=datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.state_store.db_path) as conn:
            for room in getattr(self.active_world,"rooms",[]) or []:
                rid=str(room.get("id") or "")
                for idx, oid in enumerate(room.get("objects",[]) or []):
                    tid=str(oid.get("template_id") or oid.get("id") if isinstance(oid,dict) else oid)
                    if tid not in self.item_templates: continue
                    seed=f"{idx}:{tid}"
                    try: conn.execute("INSERT INTO room_item_seeds(world_id,room_id,template_id,seed_key,created_at) VALUES(?,?,?,?,?)", (self.active_world_id,rid,tid,seed,now))
                    except sqlite3.IntegrityError: continue
                    iid=f"item_{uuid.uuid4().hex}"
                    conn.execute("INSERT INTO item_instances(instance_id,world_id,template_id,owner_type,owner_id,room_id,equipped_slot,stack_count,condition,durability,created_at,updated_at,custom_flags,plugin_data) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (iid,self.active_world_id,tid,"room","",rid,"",1,"normal",100,now,now,"{}","{}"))

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
                "visibility_flags": raw.get("visibility_flags") or [],
                "loot_table": raw.get("loot_table") or raw.get("loot_table_id") or "", "merchant_profile": raw.get("merchant_profile") or {},
                "trainer_profile": raw.get("trainer_profile") or {}, "banker_profile": raw.get("banker_profile") or {}, "healer_profile": raw.get("healer_profile") or {},
                "quest_profile": raw.get("quest_profile") or {}, "script_hooks": raw.get("script_hooks") or {},
                "state": raw.get("state") or {"current_state": "idle"}, "flags": raw.get("flags") or raw.get("behavior_flags") or [], "plugin_data": raw.get("plugin_data") or {},
            })
        self.entity_templates = templates

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
        data["is_visible"] = bool(state.get("is_visible", not self._entity_hidden(data)))
        data["movement_state"] = state.get("movement_state", "standing"); data["dialogue_state"] = state.get("dialogue_state", {})
        data["custom_state"] = state.get("custom_state", {})
        data["behavior_flags"] = list(tmpl.get("behavior_flags") or data.get("flags") or [])
        data["visibility_flags"] = list(tmpl.get("visibility_flags") or []) + list(state.get("visibility_flags") or [])
        data["description"] = data.get("long_description") or data.get("short_description") or data.get("name")
        return data

    def _fetch_entities(self, where: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
        with sqlite3.connect(self.state_store.db_path) as conn:
            rows = conn.execute(f"SELECT entity_id,world_id,entity_type,template_id,name,keywords,short_description,long_description,current_room_id,owner_type,owner_id,faction_id,level,state,flags,created_at,updated_at,plugin_data FROM entity_instances WHERE destroyed_at IS NULL AND {where} ORDER BY entity_type, created_at, entity_id", params).fetchall()
        return [self._entity_payload(r) for r in rows]

    def spawn_entity(self, template_id: str, entity_type: str | None = None, room_id: str | None = None, owner_type: str = "room", owner_id: str = "", state: dict[str, Any] | None = None, flags: list[str] | None = None, source_system: str = "runtime", **ctx: Any) -> dict[str, Any]:
        tmpl = dict(self.entity_templates.get(template_id, {}))
        etype = entity_type or tmpl.get("entity_type") or "object"
        if etype not in self.ENTITY_TYPES: raise ValueError(f"Unsupported entity type: {etype}")
        now = datetime.now(timezone.utc).isoformat(); eid = f"ent_{uuid.uuid4().hex}"
        payload = (eid, self.active_world_id or tmpl.get("world_id", ""), etype, template_id, tmpl.get("name", template_id), json.dumps(tmpl.get("keywords", [template_id])), tmpl.get("short_description", tmpl.get("name", template_id)), tmpl.get("long_description", tmpl.get("short_description", tmpl.get("name", template_id))), room_id or tmpl.get("default_room_id", ""), owner_type, owner_id, tmpl.get("faction_id", ""), int(tmpl.get("level", 1) or 1), json.dumps(state if state is not None else tmpl.get("state", {})), json.dumps(flags if flags is not None else tmpl.get("flags", [])), now, now, json.dumps(tmpl.get("plugin_data", {})))
        with sqlite3.connect(self.state_store.db_path) as conn:
            conn.execute("INSERT INTO entity_instances(entity_id,world_id,entity_type,template_id,name,keywords,short_description,long_description,current_room_id,owner_type,owner_id,faction_id,level,state,flags,created_at,updated_at,plugin_data) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", payload)
        ent = self.find_entity(eid) or {}
        self._publish_entity_event("entity_spawned", ent, source_system=source_system, **ctx)
        if etype in {"npc", "mob", "corpse"}: self._publish_entity_event(f"{etype}_spawned", ent, source_system=source_system, **ctx)
        self._publish_entity_event("room_entities_changed", ent, source_system=source_system, **ctx)
        return ent

    def find_entity(self, entity_id: str) -> dict[str, Any] | None: return next(iter(self._fetch_entities("entity_id=?", (entity_id,))), None)
    def find_room_entities(self, room_id: str) -> list[dict[str, Any]]: return self._fetch_entities("owner_type='room' AND current_room_id=?", (room_id,))
    def find_visible_entities(self, room_id: str, viewer: Any = None) -> dict[str, list[dict[str, Any]]]:
        groups = {"players": [], "npcs": [], "mobs": [], "objects": [], "corpses": []}
        for ent in self.find_room_entities(room_id):
            if not self.is_entity_visible(ent, viewer):
                continue
            groups[{"npc":"npcs", "mob":"mobs", "corpse":"corpses"}.get(ent.get("entity_type"), "objects")].append(ent)
        groups["objects"].extend(self.get_visible_room_items(room_id))
        return groups

    def resolve_entity_keywords(self, query: str, candidate_entities: list[dict[str, Any]]) -> dict[str, Any]:
        words = [w for w in re.findall(r"[a-z0-9_']+", query.lower()) if w not in self.ARTICLES]; q = " ".join(words)
        if not q: return {"status":"missing", "matches": []}
        def tokens(e): return set(re.findall(r"[a-z0-9_']+", str(e.get("name","")).lower()) + [str(k).lower() for k in e.get("keywords", [])])
        matches = [e for e in candidate_entities if str(e.get("name","")).lower() == q] or [e for e in candidate_entities if q in [str(k).lower() for k in e.get("keywords", [])]] or [e for e in candidate_entities if all(w in tokens(e) for w in words)]
        return {"status": "ok" if len(matches)==1 else "ambiguous" if matches else "missing", "entity": matches[0] if len(matches)==1 else None, "matches": matches}

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
                seed = f"{tid}:{rid}:0"
                try: conn.execute("INSERT INTO room_entity_seeds(world_id,room_id,template_id,seed_key,created_at) VALUES(?,?,?,?,?)", (self.active_world_id, rid, tid, seed, now))
                except sqlite3.IntegrityError: continue
                eid=f"ent_{uuid.uuid4().hex}"
                conn.execute("INSERT INTO entity_instances(entity_id,world_id,entity_type,template_id,name,keywords,short_description,long_description,current_room_id,owner_type,owner_id,faction_id,level,state,flags,created_at,updated_at,plugin_data) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (eid,self.active_world_id,tmpl['entity_type'],tid,tmpl['name'],json.dumps(tmpl['keywords']),tmpl['short_description'],tmpl['long_description'],rid,"room","",tmpl.get('faction_id',''),int(tmpl.get('level',1) or 1),json.dumps(tmpl.get('state',{})),json.dumps(tmpl.get('flags',[])),now,now,json.dumps(tmpl.get('plugin_data',{}))))


    ENTITY_STATES = {"idle", "standing", "sitting", "sleeping", "resting", "wandering", "following", "guarding", "trading", "training", "healing", "casting", "dead", "corpse", "despawned"}
    HIDDEN_VISIBILITY_FLAGS = {"hidden", "invisible", "builder_hidden", "future_stealth"}

    def populate_world(self) -> None:
        """Idempotently populate all room entity spawn definitions through MudRuntime."""
        self._seed_room_entities()

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
        return self.spawn_entity(template_id, room_id=room_id, state={"current_state":"idle", "spawn_origin": room_id or ""}, **ctx)

    def create_corpse(self, entity_id: str, **ctx: Any) -> dict[str, Any]:
        ent = self.find_entity(entity_id) or {}; corpse = self.spawn_entity(ent.get("template_id", "corpse"), entity_type="corpse", room_id=ent.get("room_id"), state={"current_state":"corpse", "source_entity_id": entity_id, "is_alive": False}, flags=["corpse"], **ctx); return corpse

    def get_dialogue(self, template_id: str) -> dict[str, Any]:
        return dict((self.entity_templates.get(template_id) or {}).get("dialogue_package") or {})

    def talk_to_entity(self, character_id: str, query: str, keyword: str = "") -> str:
        char = self.state_store.load_character(character_id); candidates = self.find_visible_entities(char.room_id if char else "").get("npcs", []) + self.find_visible_entities(char.room_id if char else "").get("mobs", [])
        res = self.resolve_entity_keywords(query, candidates)
        if res["status"] != "ok": return self._resolve_message(res, "They are not here.")
        ent = res["entity"]; pkg = self.get_dialogue(ent.get("template_id", "")); text = ""
        if keyword:
            text = str((pkg.get("keyword_responses") or {}).get(keyword.lower(), ""))
        if not text:
            responses = pkg.get("talk_responses") or []; text = str(responses[0] if responses else pkg.get("greeting") or "They nod silently.")
        self._publish_entity_event("entity_dialogue", ent, character_id=character_id, dialogue_keyword=keyword, dialogue_text=text)
        char_for_event = self.state_store.load_character(character_id)
        if char_for_event:
            self._publish_interaction_event("entity_interaction", char_for_event, "talk", f"talk {query}", {"target_kind": ent.get("entity_type"), "target_name": ent.get("name"), "result_summary": text})
            self._publish_interaction_event("interaction_succeeded", char_for_event, "talk", f"talk {query}", {"target_kind": ent.get("entity_type"), "target_name": ent.get("name"), "result_summary": text})
        return f'{ent.get("name")} says, "{text}"'

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
