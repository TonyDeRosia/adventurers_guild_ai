# Smart MUD Architecture

## Runtime lifecycle

Normal startup is `run.bat` -> `run.py` -> `app/web.py` -> `engine/mud_runtime.py`. Terminal mode enters through `app/main.py`, which constructs the same `WebRuntime` used by the web shell.

Startup reports these phases: loading configuration, opening SQLite, running migrations, discovering plugins, resolving plugin dependencies, scanning worlds, preparing Builder workspace, validating runtime packages, loading world assets, initializing runtime, and ready.

## Module ownership

- `run.py`: launcher, backend process readiness, desktop/web mode selection, terminal dispatch.
- `app/web.py`: single web startup lifecycle and API facade.
- `app/main.py`: terminal UI over the same runtime.
- `engine/mud_runtime.py`: live sessions, SQLite-backed character state, command execution, and active world loading.
- `smart_mud/world_registry.py`: canonical world package discovery, validation, Builder workspace preparation, and package loading.
- `engine/world_registry.py`: compatibility reexports only; do not add validation logic here.
- `engine/plugin_system.py`: plugin manifests, dependency resolution, registration metadata, and hooks.

## World registry ownership

`smart_mud/world_registry.py` owns validation logic. Runtime code must import `WorldRegistry` from `smart_mud.world_registry`. Legacy imports from `engine.world_registry` are allowed only because that module reexports the canonical implementation.

## SQLite ownership

`engine/mud_runtime.py` owns runtime SQLite schema creation and MUD state persistence. SQLite stores runtime state; world packages remain read-only content templates.

## Plugin ownership

`engine/plugin_system.py` discovers plugins from `plugins/`, validates plugin manifests, records registrations, and resolves required dependencies before a world is loaded.

## World package ownership

World packages under `worlds/` own gameplay content and reference data. Required runtime directories are documented in `docs/WORLD_PACKAGE_SPEC.md`. Missing runtime content is fatal.

## Builder workspace ownership

Builder workspace folders under `worlds/<world_id>/builder/` are infrastructure for future Builder tools. They are automatically created by the canonical world registry and must never block startup.

## Legacy systems excluded from startup

Normal Smart MUD startup must not initialize the Adventure Guild AI campaign runtime, legacy campaign save flow, image generation runtime, ComfyUI process ownership, campaign browser ownership, or old character-sheet campaign editor ownership. Legacy files may remain for history or compatibility tests, but they are not part of the startup path.

## Where future Codex prompts should modify systems

- World validation or Builder workspace behavior: `smart_mud/world_registry.py`.
- Runtime persistence or command session state: `engine/mud_runtime.py`.
- Startup logging or HTTP API: `app/web.py`.
- Launcher behavior: `run.py`.
- Plugin metadata or dependency behavior: `engine/plugin_system.py`.
- Package layout rules: `docs/WORLD_PACKAGE_SPEC.md`.
