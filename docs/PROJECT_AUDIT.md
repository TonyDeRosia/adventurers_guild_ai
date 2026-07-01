# Adventurer's Guild AI Project Audit

## A. High-level architecture

### What launches the app
- `run.py` is the desktop-friendly launcher. It checks/installs Python dependencies, finds an available local port, starts the FastAPI backend with Uvicorn, waits for `/health`, and opens the local browser UI.
- `app/main.py` is the direct backend entry point. It creates the FastAPI app from `app.web.create_app()` and runs Uvicorn.
- `run.bat`, `Build_AdventurersGuildAI.bat`, `Build_AdventurersGuildAI.py`, `packaging/windows/AdventurerGuildAI.spec`, and `installer/AdventurerGuildAI.iss` support Windows packaging/installer flows.

### How the major layers connect
1. **Player UI**: `app/static/index.html`, `app/static/app.js`, and `app/static/styles.css` implement a single-page campaign UI.
2. **HTTP backend/runtime**: `app/web.py` creates the FastAPI app, static mounts, routes, and `WebRuntime`. `WebRuntime` owns active session state, message history, saves, runtime config, model adapter, image adapter, ComfyUI manager, desktop integration, and intelligence library.
3. **Campaign engine**: `engine/campaign_engine.py` processes player turns and mutates `engine.entities.CampaignState`. It uses prompt rendering, memory, content registries, character sheets, inventory/spellbook helpers, and model adapters.
4. **Prompts**: `prompts/renderer.py` builds system and turn prompts from campaign settings, world metadata, structured state, narrator rules, character sheets, memory, and Campaign Intelligence core files.
5. **Models**: `models/provider.py`, `models/registry.py`, `models/ollama_adapter.py`, and `models/gpt4all_adapter.py` provide AI adapter selection. Basic DM Mode uses the null/basic path, while Local AI uses Ollama when configured.
6. **Runtime config**: `app/runtime_config.py` defines global model/image config persisted by `RuntimeConfigStore` under user data config, seeded from `data/defaults/app_config.json`.
7. **Data and saves**: `engine/game_state_manager.py` loads content data and creates/loads saves via `engine/save_manager.py`. User data paths are initialized in `app/pathing.py`; bundled data lives in `data/`.
8. **Memory/runtime state**: `memory/` modules summarize campaign state, NPC memory/personality, retrieval, quests, and world state. `WebRuntime` also persists web message history and scene visual state in campaign memory JSON files.
9. **Campaign Intelligence Library**: `app/intelligence.py` manages `data/intelligence/manifest.json` plus `core/`, `packs/`, and `imported/` source files. Current prompt injection only includes enabled `core` sources through `build_core_guidance()`.
10. **Image tools**: `images/` builds scene image prompts/workflows and provides null, local placeholder, and ComfyUI adapters. Image generation is hidden/disabled by default in the V1 player UI and exposed as Developer Tools/future addon.
11. **Packaging**: `app/installer_layout.py`, `app/desktop_capabilities.py`, `tools/audit_distribution.py`, `packaging/windows/`, and installer files validate/prepare desktop distribution and bundled engine/data paths.

### Development vs packaged mode
- Development mode runs from the source checkout (`run.py` or `python -m app.main`) and serves `app/static` plus generated images from the initialized user data directory.
- Packaged mode is discoverable through `app/pathing.py`, packaging specs, installer layout validation, bundled ComfyUI/workflow path helpers, and startup image backend auto-bootstrap. The runtime tries to use bundled resources/user-data paths rather than assuming the repo tree is writable.

## B. Folder and file map

| Path | Role | Audience/category | Status |
|---|---|---|---|
| `app/` | Web runtime, launch entrypoint, config/pathing, ComfyUI and desktop integration. | Backend/config/packaging | Active |
| `app/web.py` | Main FastAPI route map and `WebRuntime`; owns campaign session, settings, saves, model/image adapters, setup flows. | Backend/runtime | Active, very large hotspot |
| `app/static/index.html` | Single-page UI markup for play screen, campaign browser, settings, creator tools, developer tools. | Player/creator/developer UI | Active |
| `app/static/app.js` | Frontend controller: state refresh, modal management, settings, route calls, creator/developer tools. | Frontend | Active, large hotspot |
| `app/static/styles.css` | Styling for main UI, modals, settings, panels, add-on states. | Frontend | Active |
| `app/intelligence.py` | Campaign Intelligence Library manifest/source management and core prompt guidance builder. | Backend/developer data | Active but early-stage |
| `app/runtime_config.py` | Global runtime model/image config dataclasses and persistence. | Config/backend | Active |
| `app/pathing.py` | Project/user-data/bundled path resolution. | Config/packaging | Active |
| `app/comfy_manager.py` | Managed ComfyUI process lifecycle. | Backend/image setup | Active optional |
| `app/desktop_capabilities.py` | Folder/file picker and desktop integration capability detection. | Desktop/packaging | Active optional |
| `app/installer_layout.py` | Validates installer/bundled file layout. | Packaging/test | Active |
| `app/npc_identity.py` | Helps route narrator/NPC dialogue identity. | Backend/runtime | Active |
| `app/terminal_presenter.py` | Terminal presentation helper. | Developer/legacy | Possibly optional |
| `engine/` | Core campaign domain, turn engine, saves, character sheets, content registry, rules helpers. | Engine/backend | Active |
| `engine/campaign_engine.py` | Main turn processor and fallback narrator logic. | Engine | Active hotspot |
| `engine/entities.py` | Campaign state/settings/entity dataclasses and legacy conversion. | Data model | Active |
| `engine/game_state_manager.py` | Creates/loads campaigns from content and saves. | Backend/data | Active |
| `engine/save_manager.py` | Save-slot persistence. | Backend/data | Active |
| `engine/character_sheets.py`, `character_sheet.py` | Character sheet structures and prompt formatting. | Engine/creator | Active; naming overlap may confuse |
| `engine/inventory.py`, `spellbook.py` | Inventory and ability normalization/ownership helpers. | Engine/creator | Active |
| `engine/content_registry.py`, `dialogue_service.py` | Load static content and dialogue. | Data/engine | Active |
| `rules/` | Dice/combat rules helpers. | Engine | Active support |
| `memory/` | Memory, summaries, NPC personality, quest/world state orchestration. | Engine/runtime | Active |
| `models/` | Model adapter abstractions, Ollama adapter, supported model registry. | Backend/local AI | Active optional |
| `prompts/` | Prompt templates and renderer. | AI/runtime | Active |
| `images/` | Image generation adapters, prompt builder, workflow manager. | Optional addon | Active but disabled by default |
| `data/` | Bundled sample/default JSON content, workflows, intelligence manifest/sources. | Data/config | Active seeds |
| `data/defaults/app_config.json` | Default global runtime config. | Config | Active seed |
| `data/intelligence/manifest.json` | Intelligence source registry. | Developer data | Active |
| `data/workflows/*.json` | ComfyUI workflows. | Optional image addon | Active optional |
| `tests/` | Unit/integration/frontend DOM tests. | Test | Active |
| `tools/audit_distribution.py` | Distribution/readiness auditing utility. | Packaging/developer | Active |
| `docs/desktop_packaging_readiness.md` | Existing packaging readiness documentation. | Documentation | Active reference |
| `docs/PROJECT_AUDIT.md` | This complete audit. | Documentation | Active new |
| `docs/UI_CONTROL_MAP.md` | Concise UI control reference. | Documentation | Active new |
| `docs/API_ROUTE_MAP.md` | Concise API route reference. | Documentation | Active new |
| `packaging/windows/` | PyInstaller spec and packaging README. | Packaging | Active optional |
| `installer/` | Inno Setup installer script. | Packaging | Active optional |
| `Build_AdventurersGuildAI.*` | Build helpers. | Packaging/developer | Active optional |
| `README.md`, `README_FIRST.txt`, `LICENSE`, `requirements.txt` | Project metadata, setup, dependencies. | Developer/user | Active |

## C. UI screen map

### Main campaign screen
- **Purpose**: Primary play experience: campaign status, story log, input bar, sidebar campaign selection, and adventure references.
- **Audience**: Player.
- **Controls**: Campaigns (`openCampaignBrowser()`), Settings (`openSetupModal()`), IC/OOC toggle (`toggleInputMode()`), chat input Enter/Send (`sendInput()` → `POST /api/campaign/input`), Character Sheets, Inventory, Abilities, hidden Image Addon.
- **Data**: Reads play view/state/messages/saves/scene visual. Writes turns and autosaves through `WebRuntime.handle_player_input()`.

### Campaign Browser
- **Purpose**: Browse, load, create, rename, or delete campaign saves.
- **Audience**: Player.
- **Controls**: Play selected (`loadSelectedCampaign()` → `POST /api/campaign/start`), New campaign (`openNewCampaignModal()`), Rename selected (`POST /api/campaign/rename`), Delete selected (`POST /api/campaign/delete`), Close.
- **Data**: Reads `/api/campaigns` and `/api/campaign/saves`; writes save metadata or removes saves.

### New Campaign
- **Purpose**: Create a campaign with theme/tone/premise and optional advanced play-style/sheet drafts.
- **Audience**: Player by default; advanced rules/sheet drafting are creator-oriented.
- **Controls**: Campaign/theme/tone/premise fields; Advanced Campaign Rules; draft Character Sheets Manager; Create campaign (`createCampaignFromForm()` → `POST /api/campaign/start` mode new); Cancel.
- **Backend**: `WebRuntime.create_campaign()` → `GameStateManager.create_new_campaign()` or sample path.
- **Data**: Writes a new save/session, settings/play style, optional sheets, `startup_state`.

### Settings
- **Purpose**: Player-accessible global and campaign preferences.
- **Audience**: Player, with creator and developer subsections.
- **Controls**: suggested moves, narration format, Narrator Rules, World Building, Creator Mode, play-style toggles, Story DM mode, scene visual mode, Developer Tools toggle, Cancel changes.
- **Routes**: `GET/POST /api/settings/global`, `POST /api/settings/campaign`.
- **Data**: Writes runtime config and active campaign settings.

### Developer Tools
- **Purpose**: Local AI setup, model inventory, Campaign Intelligence management, Image AI setup, diagnostics.
- **Audience**: Developer/power user only.
- **Controls/routes**: See Developer Tools audit and UI control map. Most controls call `/api/setup/*`, `/api/models/*`, `/api/developer/intelligence/*`, or `/api/providers/readiness`.

### Character
- **Purpose**: View attached character sheets during play; create sheets in Creator Mode.
- **Audience**: Player view; creator editing.
- **Controls**: Character Sheets opens runtime viewer; Create Character Sheet opens dialog; Create Sheet posts `/api/campaign/character-sheets`; close/cancel buttons.
- **Backend**: `WebRuntime.upsert_character_sheet()` updates campaign sheets.
- **Data**: Reads active campaign sheets from play/state, writes campaign sheets.

### Inventory
- **Purpose**: View inventory; edit items in Creator Mode.
- **Controls**: Save Item (`POST /api/campaign/inventory`), Clear Form, Close.
- **Backend**: `WebRuntime.get_inventory_state()`, `upsert_inventory_entry()`.
- **Data**: Structured inventory categories and quantities.

### Abilities
- **Purpose**: View abilities/spellbook; edit in Creator Mode.
- **Controls**: Save Entry (`POST /api/campaign/spellbook`), Clear Form, Close.
- **Backend**: `WebRuntime.get_spellbook_state()`, `upsert_spellbook_entry()`.

### Narrator Rules
- **Purpose**: Campaign-specific hard rules injected into prompts.
- **Audience**: Creator.
- **Controls**: Save Rule (`POST /api/campaign/narrator-rules`), Clear Editor, Save Rules to Campaign (`POST /api/campaign/save`), Close.
- **Prompt path**: Custom rules are included in `PromptRenderer.build_system_prompt()` and turn narrator-rules blocks.

### World Building
- **Purpose**: Inspect generated NPC personalities, world design, reactive changes.
- **Audience**: Creator/developer.
- **Controls**: Recalibrate (`POST /api/campaign/recalibrate`), Close.
- **Data**: Reads structured world-building view from active campaign state.

### Creator Mode confirmation
- **Purpose**: Guardrail before exposing edit tools.
- **Audience**: Creator.
- **Controls**: confirmation checkbox; Enable Creator Mode (`setCampaignMode('creator')` → `POST /api/settings/campaign`); Stay in Adventure Mode.
- **Data**: Persists `campaign_mode` in active campaign settings.

### Character creation dialogs / guided startup
- **Purpose**: After new campaign creation, the runtime asks for player identity/concept and converts the answer into a main character sheet.
- **UI**: Uses normal campaign log/input, not a separate HTML modal.
- **Backend**: `startup_state == "character_creation"` routes the next qualifying input to `_handle_character_creation_answer()`, `_upsert_guided_main_character_sheet()`, and `_guided_opening_scene()`.
- **Data**: Updates player name/class, main sheet, recent memory, message history, save.

### Image addon/tools
- **Purpose**: Optional/future scene visuals and ComfyUI setup.
- **Audience**: Developer/future addon; hidden in default V1 player mode.
- **Controls**: manual prompt/generate; scene visual mode; Developer Tools Image AI setup; diagnostics.
- **Routes**: `/api/images/generate`, `/api/setup/import-image-ai`, `/api/setup/image-readiness-card`, `/api/setup/image-backend-diagnostics`, related setup routes.
- **Backend**: `TurnImagePromptBuilder`, `ComfyUIAdapter`, `WorkflowManager`, `ComfyProcessManager`.

### Campaign Intelligence Library
- **Purpose**: Developer-managed guidance files for AI behavior.
- **Audience**: Developer-only.
- **Controls**: Refresh Sources, Add, Replace, Enable/Disable, Priority; Rebuild Index/Test Retrieval placeholders.
- **Routes**: `/api/developer/intelligence*`.
- **Data**: Manifest plus source files. Only enabled `core` files are injected today.

## D. Button/control inventory

The complete concise inventory is maintained in [`docs/UI_CONTROL_MAP.md`](UI_CONTROL_MAP.md). Important findings:
- All visible primary play controls are player-facing except creator edit forms and developer setup tools.
- Runtime edit controls are hidden with `creator-mode-only` classes and should remain creator-only.
- Image controls are currently hidden/advanced or future-addon oriented and should not be prominent in V1 player mode.
- Several legacy/hidden advanced image controls and orphaned ids exist and may be cleanup candidates.

## E. API route map

The complete route table is maintained in [`docs/API_ROUTE_MAP.md`](API_ROUTE_MAP.md). Summary:
- Player routes: campaign state/messages/play-view/saves/campaigns/input/start/save/rename/delete and basic settings.
- Creator routes: inventory/spellbook/character-sheets/narrator-rules/world-building/recalibrate/campaign settings.
- Developer routes: `/api/setup/*`, `/api/models/*`, `/api/developer/intelligence*`, debug/diagnostics routes.
- Internal/possibly obsolete routes: `/api/model/options`, `/api/model/status`, `/api/models/active`, `/api/debug/comfyui-last`, `/api/campaign/debug/narrator-packet`, some visual-pipeline validation/setup routes with no visible caller.

## F. Campaign data flow

### Campaign creation
1. User opens Campaign Browser → New Campaign.
2. `createCampaignFromForm()` collects visible campaign fields, hidden defaults, play-style options, and draft sheets.
3. Frontend posts `mode: "new"` to `/api/campaign/start`.
4. `WebRuntime.create_campaign()` calls `GameStateManager.create_new_campaign()` unless sample/premade mode is requested.
5. Runtime applies play style, campaign mode/defaults, seeds scene state/opening guidance, switches session slot/history, saves.

### Guided character creation
- New campaigns enter `startup_state = "character_creation"` when applicable.
- The next qualifying player message is detected by `_looks_like_character_creation_answer()`.
- `_handle_character_creation_answer()` appends the player answer, infers identity with `_infer_character_identity()`, creates/updates the main character sheet, sets `startup_state = "ready"`, appends opening scene, flushes history, and saves.

### `startup_state`
- `character_creation`: player input is interpreted as character setup if it looks descriptive.
- `ready`: normal turn processing through `CampaignEngine.run_turn()`.
- If input during startup looks like an action (`look`, `go`, `attack`, etc.), the runtime exits startup and treats it as a normal turn.

### Save loading
- Campaign Browser selection posts `/api/campaign/start` with load mode and slot.
- `WebRuntime.switch_campaign()` loads state via `GameStateManager`, sets active slot, loads per-slot web message history, syncs runtime/campaign settings, and returns serialized state.

### Turn submission and state update
1. `sendInput()` posts `{text, mode}` to `/api/campaign/input`.
2. OOC mode calls `handle_ooc_input()`; IC calls `handle_player_input()`.
3. `handle_player_input()` appends player message, optionally triggers before-narration image generation, calls `CampaignEngine.run_turn()`, routes/display-splits narrator/NPC messages, maybe queues after-narration image generation, flushes history, and `save_active_campaign()` autosaves.
4. Frontend refreshes messages/state/visuals and updates status/autosave indicators.

### Autosave
- The UI says campaigns autosave automatically.
- Runtime saves after campaign creation, guided character creation completion, each normal turn, many creator edits, campaign settings updates, and explicit `/api/campaign/save` calls.

### Campaign settings and modes
- Global settings are in runtime config JSON (`RuntimeConfigStore`).
- Per-campaign settings are stored on `CampaignState.settings` and saved with the campaign.
- Adventure/Creator Mode is `campaign_mode` in campaign settings. Adventure hides edit tools; Creator unlocks editor panels.
- Display mode/story mode appears in campaign UI metadata; play-style fields control narration, suggested moves, image timing, freeform powers, auto sheet updates, NPC personality behavior, and reactive persistence.

## G. AI/prompt flow

### Prompt construction
- `CampaignEngine.run_turn()` builds/retrieves current scene/memory/context, then uses `PromptRenderer` to create model-ready messages.
- `PromptRenderer.build_system_prompt()` includes system role/tone, story quality, player agency, dialogue quality, examples, narrator rules, campaign play style, campaign tone/content settings, world setup, requested mode, and Campaign Intelligence Guidance.
- `PromptRenderer.build_turn_prompt()` includes current action priority, scene block, NPC/enemy blocks, player facts/character sheet guidance, recent consequences/memory, narrator rules, writing instructions, and structured turn snapshot.

### Included data today
- **Narrator rules**: built-in hard rules plus campaign custom narrator rules.
- **World building**: world metadata and structured scene/world state appear through system/turn prompt blocks and engine context.
- **Campaign settings**: play style and content/tone settings are explicitly injected.
- **Character sheets**: formatter guidance is included in player facts/character sheet prompt sections.
- **Campaign Intelligence Library**: enabled `core` category files only, capped by `build_core_guidance(max_chars=4000)`.

### Intelligence files injected now
The seeded core files are:
- `core/player_agency.md`
- `core/dialogue_realism.md`
- `core/npc_identity.md`
- `core/world_consistency.md`
- `core/memory_rules.md`

### Not injected yet
- Enabled `packs` and `imported` intelligence sources are manageable in the UI but are not included by `build_core_guidance()`.
- Rebuild Index and Test Retrieval are placeholders; no embeddings/vector semantic retrieval currently feeds prompts.
- The `/api/developer/intelligence/enabled` route can read enabled contents, but prompt injection still uses core-only guidance.

### Basic DM Mode, Local AI, Ollama
- Settings `model.provider = "null"` means Basic DM Mode: the app can run without local AI setup, relying on deterministic/fallback/basic response behavior.
- Settings `model.provider = "ollama"` selects Local AI. Developer Tools can download/connect Ollama and install/activate models.
- Model inventory uses supported model registry plus Ollama status. Setup routes can orchestrate Ollama start/install/model pull.

### Image generation
- Image prompt flow uses `TurnImagePromptBuilder` and adapters in `images/`.
- Manual `/api/images/generate` refuses requests unless `manual_image_generation_enabled` is true.
- Campaign image generation also requires campaign setting `image_generation_enabled`, provider `comfyui`, and configured/ready paths/service.
- Default V1 player experience hides Image Addon panels and states optional image addon is disabled.

## H. Developer Tools audit

| Section | What it does | Needed now? | Future-only? | Visibility recommendation | Confusing/duplicate notes |
|---|---|---|---|---|---|
| Text AI setup | Set Up Text AI, Set Up Everything, Recheck dependencies. | Useful for local AI users. | No. | Developer-only. | “Set Up Everything” includes image setup and may be too broad for normal players. |
| Ollama and Model Setup | Download/connect Ollama, install story model, configure model name. | Needed only for Ollama mode. | No. | Developer-only. | `Model Name` plus model inventory activation can duplicate model choice concepts. |
| Model Inventory | Refresh, install, activate supported models. | Useful for local AI setup. | No. | Developer-only. | Separate legacy `/api/model/*` routes appear unused beside `/api/models/*`. |
| Image addon setup | Guided ComfyUI/model source import, start, disable image AI. | Optional; not needed for V1 default. | Partly future/addon. | Developer-only or future plugin. | Multiple stages and hidden advanced fields can overwhelm; `Set Up Everything` may surface image complexity too soon. |
| Campaign Intelligence Library | Manage source manifest/files and priorities. | Useful for prompt tuning. | Retrieval/index buttons are future-only. | Developer-only for now; later creator content packs could be separate. | UI says enabled core files loaded; packs/imported not injected, so Add Source may imply more than it does. |
| Diagnostics/debug | Backend folder, refresh diagnostics, readiness panels, debug routes. | Needed for support/testing. | No. | Developer-only. | Hidden advanced path fields with Browse buttons are partially legacy and not all visibly reachable. |
| Setup guidance | Shows dependency readiness guidance. | Useful when local tools fail. | No. | Developer-only. | Should stay separate from player Settings. |

## I. Redundancy and cleanup candidates

### Duplicate or confusing controls/statuses
- Autosave messaging appears in sidebar, campaign browser, status strip, and status stack. This is reassuring but repetitive.
- Scene visual/image addon status appears in main scene panel, progress strip, right panel, settings, and Developer Tools despite being hidden by default.
- Basic DM Mode vs Story DM mode vs Local AI wording is improved but still mixed with developer setup in the same Settings modal.
- `Model Name`, `Install Story Model`, model inventory install/activate, and supported model refresh overlap conceptually.

### Controls in wrong mode
- New Campaign advanced campaign rules are visible behind a details element before Creator Mode exists; they are creator-oriented and may be too advanced for first-time players.
- Scene visual mode appears in player Settings even though image addon is hidden/disabled by default; consider moving to Creator/Developer until addon is productized.
- Manual image addon controls should remain hidden unless image addon is explicitly enabled.

### Move candidates
- **Developer Tools**: all setup/install/path/diagnostic/model inventory/image backend controls.
- **Creator Mode**: narrator rules, world building recalibration, inventory/abilities/sheet editing, advanced campaign rules.
- **Future plugins/addons**: ComfyUI Image AI, semantic Campaign Intelligence retrieval/indexing, additional AI model providers.

### Dead or possibly obsolete code paths
- `open-character-sheets` handler exists in JS but no matching element appears in `index.html`; likely legacy.
- `bindClickById('apply-settings', applySettings)` references `apply-settings`, but no visible button exists; settings now mostly auto-apply campaign settings and close/cancel.
- Several constants reference missing elements such as `setup-summary`, `comfyui-models-list`, path validation labels, and `path-config-status`; likely removed UI remnants or hidden legacy path tooling.
- `/api/model/options`, `/api/model/status`, `/api/models/active`, `/api/debug/comfyui-last`, `/api/campaign/debug/narrator-packet`, `/api/settings/visual-pipeline/validate`, and some image engine UI routes have no visible frontend caller.
- Campaign Intelligence Rebuild Index/Test Retrieval buttons are explicitly placeholders.

## J. Recommended next steps

### 1. Critical UX bugs/confusion
1. Decide whether Settings should have an explicit Apply button or rely fully on auto-apply; remove/restore `apply-settings` accordingly.
2. Hide or relocate Scene visual mode until image addon is enabled/productized.
3. Move New Campaign advanced rules behind Creator Mode language or a clearer “Advanced/Creator options” warning.
4. Reduce duplicate autosave and image disabled status messages.

### 2. Cleanup/refactor before monetization/backend
1. Split `app/web.py` into route modules/runtime services without behavior change.
2. Split `app/static/app.js` into modules: state/API, modals, campaign browser, play screen, settings, creator tools, developer tools.
3. Remove or document legacy/no-caller routes and orphaned DOM ids after test coverage confirms they are unused.
4. Add a permission/audience model for player/creator/developer controls rather than relying on scattered classes and local UI state.

### 3. Campaign Intelligence improvements
1. Make UI explicit: “Only core files currently affect prompts.”
2. Add controlled injection of enabled pack/imported sources by campaign or creator setting.
3. Implement retrieval/indexing or remove placeholder buttons until planned.
4. Add tests proving which intelligence sources enter prompts.

### 4. Cloud/account/billing preparation
1. Separate local-only setup routes from future account/cloud API namespace.
2. Add an auth/session abstraction before exposing save/settings APIs beyond localhost.
3. Define user-owned save/config/intelligence storage boundaries.
4. Add audit logging around destructive actions (delete campaign, creator edits, setup installs).

### 5. Packaging/release improvements
1. Keep image AI as optional downloadable addon; do not bundle model files without clear license flow.
2. Add packaged-mode smoke tests for static serving, user data paths, save creation, and Basic DM Mode.
3. Add a release checklist that runs launcher readiness, installer layout validation, frontend syntax check, and targeted pytest suite.
4. Ensure Developer Tools are hidden by default in packaged player builds.
