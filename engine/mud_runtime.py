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
from engine.mud_displays import render_prompt, render_room
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
        self._seed_room_items()
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
        return {"html": html, "text": room.description, "prompt": prompt, "room_id": char.room_id}

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
        return {"ok": result.ok, "output": result.narrative, "view": self.play_view(character_id)}

    def _handle_runtime_command(self, char: MudCharacter, command: str):
        tokens = command.strip().split()
        if not tokens:
            return self.command_engine.handle_command(char, command)
        raw_cmd = tokens[0].lower()
        cmd_name = self.command_engine.resolve_alias(raw_cmd)
        self.event_bus.publish("command_resolved", {"raw_input": command, "canonical_command": cmd_name, "arguments": tokens[1:], "character_id": char.id, "character_name": char.name, "current_room_id": char.room_id}, source_system="command", world_id=self.active_world_id or "", character_id=char.id, command=command)
        item_result = self._handle_item_command(char, command, cmd_name, tokens[1:])
        if item_result is not None:
            self.event_bus.publish("command_executed", {"raw_input": command, "canonical_command": cmd_name, "arguments": tokens[1:], "character_id": char.id, "character_name": char.name, "current_room_id": char.room_id, "result_summary": item_result.narrative[:120]}, source_system="command", world_id=self.active_world_id or "", character_id=char.id, command=command)
            return item_result
        if cmd_name in {"north", "south", "east", "west", "up", "down", "in", "out"}:
            result = self._move_character(char, cmd_name)
            self.event_bus.publish("command_executed", {"raw_input": command, "canonical_command": cmd_name, "arguments": tokens[1:], "character_id": char.id, "character_name": char.name, "current_room_id": char.room_id, "result_summary": result.narrative[:120]}, source_system="command", world_id=self.active_world_id or "", character_id=char.id, command=command)
            return result
        result = self.command_engine.handle_command(char, command)
        if result.state_updates and result.state_updates.get("render_room"):
            room = self._current_room(char)
            result.narrative = self._room_text(room)
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
            return CommandResult(narrative=f"You head {direction}.\n\n{self._room_text(new_room)}")
        self.event_bus.publish("movement_failed", {"canonical_command": direction, "character_id": char.id, "character_name": char.name, "current_room_id": room.id, "result_summary": "no_exit"}, source_system="movement", world_id=self.active_world_id or "", character_id=char.id, command=direction)
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
                    objects=self.get_visible_room_items(str(room_data.get("id", char.room_id))),
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
        item = res["item"]; self._publish_item_event("before_item_pickup", item, character_id=character_id, room_id=room_id)
        moved = self.transfer_item(item["instance_id"], to_owner=("character", character_id)); self._publish_item_event("item_picked_up", moved, character_id=character_id, room_id=room_id); self._publish_item_event("inventory_changed", moved, character_id=character_id); self._publish_item_event("room_inventory_changed", moved, room_id=room_id); self._publish_item_event("after_item_pickup", moved, character_id=character_id, room_id=room_id)
        return f"You pick up {moved['name']}."

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
        if cmd in {"get","take"}: return CommandResult(self.pickup_item(char.id, char.room_id, q) if q else "Get what?")
        if cmd=="drop": return CommandResult(self.drop_item(char.id, q) if q else "Drop what?")
        if cmd=="wear": return CommandResult(self.equip_item(char.id, q, self._preferred_slot(q,"wear")) if q else "Wear what?")
        if cmd=="wield": return CommandResult(self.equip_item(char.id, q, self._preferred_slot(q,"wield")) if q else "Wield what?")
        if cmd=="hold": return CommandResult(self.equip_item(char.id, q, self._preferred_slot(q,"hold")) if q else "Hold what?")
        if cmd in {"remove","unwield"}: return CommandResult(self.unequip_item(char.id, q or ("main_hand" if cmd=="unwield" else "")) if q or cmd=="unwield" else "Remove what?")
        if cmd in {"look","examine"} and q: return CommandResult(self._look_item(char.id, char.room_id, q))
        return None

    def _preferred_slot(self, query: str, mode: str) -> str | None:
        if mode == "wield": return "main_hand"
        if mode == "hold": return "light"
        return None

    def _render_inventory(self, character_id: str) -> str:
        items=self.find_inventory_items(character_id)
        return "You are carrying nothing." if not items else "You are not carrying anything.\nYou are carrying:\n" + "\n".join(f"  {i['name']}" + (f" x{i['stack_count']}" if i.get('stack_count',1)>1 else "") for i in items)

    def _render_equipment(self, character_id: str) -> str:
        equipped = self.find_equipped_items(character_id)
        by={i.get("equipped_slot"): i for i in equipped}
        prefix = "" if equipped else "You are not wearing anything.\n"
        return prefix + "Equipment:\n" + "\n".join(f"  {s.replace('_',' ').title()}: {by[s]['name'] if s in by else 'nothing'}" for s in self.EQUIPMENT_SLOTS)

    def _look_item(self, character_id: str, room_id: str, query: str) -> str:
        res=self.resolve_item_keywords(query, self.get_visible_room_items(room_id)+self.find_inventory_items(character_id)+self.find_equipped_items(character_id))
        if res["status"] != "ok": return self._resolve_message(res, "You don't see that.")
        t=res["item"].get("template",{}); return str(t.get("long_description") or t.get("short_description") or res["item"]["name"])

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
