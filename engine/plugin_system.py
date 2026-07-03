"""Plugin discovery, manifests, and registration for Smart MUD."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


class PluginError(ValueError):
    """Raised when an installed plugin is invalid."""


@dataclass(frozen=True)
class PluginManifest:
    id: str
    name: str
    version: str
    description: str = ""
    dependencies: list[str] = field(default_factory=list)
    registers: dict[str, list[str]] = field(default_factory=dict)


@dataclass(frozen=True)
class PluginPackage:
    root: Path
    manifest: PluginManifest


class PluginRegistry:
    """Discovers installed plugins and records extension registrations."""

    REGISTRATION_KEYS = (
        "commands",
        "database_tables",
        "builder_editors",
        "runtime_hooks",
        "scheduled_events",
        "ai_context_providers",
        "render_extensions",
    )

    def __init__(self, plugins_dir: Path) -> None:
        self.plugins_dir = plugins_dir
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self.plugins: dict[str, PluginPackage] = {}
        self.registrations: dict[str, list[tuple[str, str]]] = {key: [] for key in self.REGISTRATION_KEYS}

    def discover(self) -> list[PluginPackage]:
        discovered: dict[str, PluginPackage] = {}
        for manifest_path in sorted(self.plugins_dir.glob("*/manifest.json")):
            package = self._load_plugin(manifest_path.parent)
            if package.manifest.id in discovered:
                raise PluginError(f"Duplicate plugin id: {package.manifest.id}")
            discovered[package.manifest.id] = package
        self.plugins = discovered
        self._register_all()
        return list(discovered.values())

    def resolve_required(self, required: list[str]) -> list[PluginPackage]:
        missing = [plugin_id for plugin_id in required if plugin_id not in self.plugins]
        if missing:
            raise PluginError(f"Missing required plugin(s): {', '.join(missing)}")
        resolved: list[PluginPackage] = []
        seen: set[str] = set()
        def visit(plugin_id: str) -> None:
            if plugin_id in seen:
                return
            plugin = self.plugins[plugin_id]
            for dep in plugin.manifest.dependencies:
                if dep not in self.plugins:
                    raise PluginError(f"Plugin {plugin_id} requires missing dependency {dep}")
                visit(dep)
            seen.add(plugin_id)
            resolved.append(plugin)
        for plugin_id in required:
            visit(plugin_id)
        return resolved

    def _load_plugin(self, root: Path) -> PluginPackage:
        try:
            raw = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise PluginError(f"Invalid plugin manifest JSON in {root}: {exc}") from exc
        for field_name in ("id", "name", "version"):
            if not raw.get(field_name):
                raise PluginError(f"Plugin manifest {root} missing required field: {field_name}")
        registers = raw.get("registers", {}) or {}
        manifest = PluginManifest(
            id=str(raw["id"]),
            name=str(raw["name"]),
            version=str(raw["version"]),
            description=str(raw.get("description", "")),
            dependencies=[str(v) for v in raw.get("dependencies", [])],
            registers={key: [str(v) for v in registers.get(key, [])] for key in self.REGISTRATION_KEYS},
        )
        return PluginPackage(root=root, manifest=manifest)

    def _register_all(self) -> None:
        self.registrations = {key: [] for key in self.REGISTRATION_KEYS}
        for plugin in self.plugins.values():
            for key, values in plugin.manifest.registers.items():
                for value in values:
                    self.registrations[key].append((plugin.manifest.id, value))


class HookRegistry:
    """Runtime hook dispatcher used by engine systems and plugins."""

    HOOKS = (
        "player_login", "player_logout", "character_creation", "character_death",
        "npc_death", "room_enter", "room_leave", "quest_accepted", "quest_completed",
        "item_created", "item_destroyed", "combat_started", "combat_ended",
        "spell_cast", "skill_used", "builder_save", "world_loaded", "plugin_loaded",
    )

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[..., Any]]] = {hook: [] for hook in self.HOOKS}

    def register(self, hook: str, handler: Callable[..., Any]) -> None:
        if hook not in self._handlers:
            raise KeyError(f"Unknown runtime hook: {hook}")
        self._handlers[hook].append(handler)

    def emit(self, hook: str, **payload: Any) -> list[Any]:
        if hook not in self._handlers:
            raise KeyError(f"Unknown runtime hook: {hook}")
        return [handler(**payload) for handler in self._handlers[hook]]
