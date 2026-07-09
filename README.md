# Smart MUD

Smart MUD is a package-driven, SQLite-backed MUD engine. It is not a fantasy campaign app: the engine owns runtime lifecycle, persistence, command routing, plugin discovery, and world package loading, while installable data packages under `worlds/` own genre, lore, rooms, NPCs, items, quests, classes, races, skills, spells, and colors.

## Current startup path

1. `run.bat` launches `run.py` on Windows.
2. `run.py` initializes Smart MUD paths, starts the FastAPI backend in web mode, or dispatches to terminal mode.
3. `app/web.py` performs Smart MUD startup: configuration, SQLite opening and migrations, plugin discovery, plugin dependency resolution, world scanning, runtime package validation, Builder workspace preparation, world asset availability, runtime initialization, and readiness.
4. `engine/mud_runtime.py` owns the live runtime session, SQLite-backed character state, command handling, and world loading.
5. `smart_mud/world_registry.py` is the canonical world registry and validation implementation.

Normal startup does not initialize the legacy Adventure Guild AI campaign runtime, campaign save flow, image generation runtime, ComfyUI process ownership, campaign browser, or character-sheet campaign editor.

## Runtime systems

- **World packages:** Smart MUD loads installable packages from `worlds/<world_id>/`.
- **SQLite persistence:** Runtime state is stored in SQLite under the user data directory.
- **Plugins:** Optional extension packages are discovered from `plugins/` and resolved before world loading.
- **Builder workspace:** `builder/` workspace folders inside a world package are prepared automatically when missing. They are infrastructure for future tools, not gameplay assets.
- **AI extension layer:** AI may provide optional context or behavior through extensions later, but authored world packages and SQLite runtime state remain the source of truth.

## Running

```bash
python run.py --mode web
python run.py --terminal
```

On Windows, use:

```bat
run.bat
```

The application is ready when startup reports `Ready` and the health endpoint returns `runtime: smart_mud`.

## Repository map

- `app/web.py` — web shell startup and HTTP API.
- `app/main.py` — terminal shell using the same Smart MUD runtime.
- `engine/mud_runtime.py` — SQLite-backed runtime sessions and command flow.
- `smart_mud/world_registry.py` — canonical world package discovery, validation, Builder workspace preparation, and loading.
- `engine/world_registry.py` — compatibility reexports only.
- `engine/plugin_system.py` — plugin discovery, registration metadata, dependencies, and hooks.
- `worlds/` — installable world packages.
- `plugins/` — installable plugins.
- `docs/WORLD_PACKAGE_SPEC.md` — world package layout and validation rules.
- `docs/SMART_MUD_ARCHITECTURE.md` — ownership and lifecycle guide.
- `docs/SMART_MUD_MASTER_ROADMAP.md` — phased project roadmap.
