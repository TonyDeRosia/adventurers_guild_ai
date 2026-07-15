# Phase 13C1G-B4 Display Theme Publish Audit

## Scope
This audit covers Builder draft display themes and display-theme assignments for world, area, and zone scopes.

## Draft source
- Builder draft collections are owned by `smart_mud.builder.BuilderWorkspace`.
- Display themes are drafted in `worlds/<world_id>/builder/display_themes.json`.
- World display settings are drafted in `worlds/<world_id>/builder/world.json`.
- Area assignments are drafted in `worlds/<world_id>/builder/areas.json`.
- Zone assignments are drafted in `worlds/<world_id>/builder/zones.json`.

## Published destination
- Themes publish to `worlds/<world_id>/display_themes/display_themes.json`.
- World defaults publish to `worlds/<world_id>/world/world.json`.
- Area assignments publish with area records in `worlds/<world_id>/areas/areas.json`.
- Zone assignments publish with zone records in `worlds/<world_id>/zones/zones.json`.

## Validator
- Theme data is validated with `engine.display_themes.validate_display_theme`.
- Publish reference validation is performed by `BuilderWorkspace.publish_drafts` before any published files are written.
- Family names are checked against `engine.display_themes.SUPPORTED_FAMILIES`.
- World prompt presets are checked against built-in prompt presets and prompt presets supplied by the candidate theme set.

## Publish function
- The canonical publish entry point is `BuilderWorkspace.publish_drafts`.
- The Builder command router calls it from `builder publish`.
- The function builds the full candidate published state and aborts before writing if validation fails.
- Successful writes use temporary JSON files followed by `Path.replace` for atomic file replacement.

## Runtime loader
- Runtime display themes are loaded only from published package data by `engine.display_themes.load_display_themes`.
- Normal runtime assignments are loaded by `engine.display_themes.load_published_theme_assignments` through `load_theme_assignments`.
- Builder preview explicitly opts into drafts with `ThemeResolutionMode.BUILDER_DRAFT_PREVIEW`.

## Reload requirement
Published display changes are package-file changes. Existing in-memory runtime state does not automatically reload those files. Builders receive: `Display theme changes were published. Reload the world or restart Smart MUD to apply them.`

## Tests
- `tests/test_backend_startup_smoke.py` imports the backend dependency chain and constructs the web app.
- `tests/test_phase13c1g_b4_builder_publish.py` covers draft isolation, publishing themes and assignments, reload-by-re-resolve behavior, transactional failure, and repository mutation guard snapshot helpers.
- Existing Phase 13C1G display tests cover runtime/draft resolution, preview output, labels, roles, and accessibility rendering.
