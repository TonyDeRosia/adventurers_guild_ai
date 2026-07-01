# API Route Map

| Method/path | Purpose | Frontend caller | Runtime/backend function | Data read/written | Audience |
|---|---|---|---|---|---|
| GET `/` | Serve the single-page web UI. | Browser navigation. | `root()` returns `app/static/index.html`. | Reads static HTML. | Player-facing |
| GET `/health` | Basic server health probe. | Launcher/tests/manual diagnostics. | `health()`. | None. | Internal/developer |
| GET `/api/developer/intelligence` | List Campaign Intelligence Library sources. | `refreshIntelligenceSources()`. | `runtime.list_intelligence_sources()` → `CampaignIntelligenceLibrary.list_sources()`. | Reads `data/intelligence/manifest.json`. | Developer-only |
| GET `/api/developer/intelligence/enabled` | Return enabled intelligence source contents. | No visible direct caller found. | `runtime.read_enabled_intelligence_sources()`. | Reads enabled files under `data/intelligence`. | Developer-only/internal |
| POST `/api/developer/intelligence/import` | Import a `.txt`, `.md`, or `.json` source file. | `postIntelligence()` from Add Source File. | `runtime.import_intelligence_source()`. | Copies file into `data/intelligence/imported|packs`; updates manifest. | Developer-only |
| POST `/api/developer/intelligence/replace` | Replace an existing source file. | `postIntelligence()` from Replace Source File. | `runtime.replace_intelligence_source()`. | Rewrites target source; updates manifest timestamp/title. | Developer-only |
| POST `/api/developer/intelligence/enabled` | Enable/disable a source. | Apply Enable/Disable. | `runtime.set_intelligence_enabled()`. | Updates manifest. | Developer-only |
| POST `/api/developer/intelligence/priority` | Set source priority. | Apply Priority. | `runtime.set_intelligence_priority()`. | Updates manifest. | Developer-only |
| GET `/api/debug/comfyui-last` | Return latest ComfyUI debug bundle. | No visible direct caller found. | `runtime.get_comfy_debug_bundle()`. | Reads runtime debug state. | Developer-only |
| GET `/api/campaign/state` | Serialize active campaign state. | `refreshState()`. | `runtime.serialize_state()`. | Reads active `CampaignState`. | Player-facing |
| GET `/api/campaign/messages` | Return recent UI message history. | `refreshMessages()`. | `runtime.session.message_history`. | Reads memory history JSON/session. | Player-facing |
| GET `/api/campaign/play-view` | Return campaign state plus display-oriented view. | `refreshState()`/play rendering. | `runtime.get_play_view()`. | Reads active campaign and message history. | Player-facing |
| GET `/api/campaign/scene-visual` | Return current scene visual metadata. | `refreshSceneVisual()`. | `runtime._scene_visual_for_slot()`. | Reads scene visual store. | Player-facing when image addon visible |
| GET `/api/campaign/inventory` | Return active campaign inventory. | `refreshInventory()`. | `runtime.get_inventory_state()`. | Reads structured state inventory. | Player/creator |
| POST `/api/campaign/inventory` | Upsert inventory entry. | Inventory Save Item. | `runtime.upsert_inventory_entry()`. | Writes structured state; autosaves active campaign. | Creator-facing |
| GET `/api/campaign/spellbook` | Return abilities/spellbook. | `refreshSpellbook()`. | `runtime.get_spellbook_state()`. | Reads structured spellbook. | Player/creator |
| POST `/api/campaign/spellbook` | Upsert ability/spellbook entry. | Abilities Save Entry. | `runtime.upsert_spellbook_entry()`. | Writes structured spellbook; autosaves. | Creator-facing |
| GET `/api/campaign/narrator-rules` | Return custom narrator rules. | `refreshNarratorRules()`. | `runtime.get_narrator_rules()`. | Reads canon narrator rules. | Creator-facing |
| POST `/api/campaign/narrator-rules` | Upsert narrator rule. | Save Rule. | `runtime.upsert_narrator_rule()`. | Writes canon narrator rules. | Creator-facing |
| GET `/api/campaign/world-building` | Return generated NPC/world/reactive data. | `refreshWorldBuilding()`. | `runtime.get_world_building_view()`. | Reads structured runtime/canon/world state. | Creator-facing |
| POST `/api/campaign/recalibrate` | Recalculate/sync derived campaign state. | Recalibrate. | `runtime.recalibrate_campaign_state()`. | Writes normalized structured state; may autosave. | Creator/developer |
| GET `/api/campaign/debug/narrator-packet` | Return prompt/debug packet for narrator. | No visible direct caller found. | `runtime.get_narrator_debug_packet()`. | Reads prompt-relevant state. | Developer-only |
| GET `/api/campaign/saves` | List save slots. | `refreshSaves()`. | `runtime.list_saves()`. | Reads saves directory. | Player-facing |
| GET `/api/campaigns` | List campaign summaries. | `refreshSaves()`/browser. | `runtime.list_campaigns()`. | Reads saves directory. | Player-facing |
| POST `/api/campaign/input` | Submit in-character or out-of-character player input. | `sendInput()`. | `runtime.handle_player_input()` or `runtime.handle_ooc_input()`. | Updates state, messages, memory, autosave; may queue images. | Player-facing |
| POST `/api/campaign/start` | Create or load campaign. | `createCampaignFromForm()`, `loadSelectedCampaign()`. | `runtime.create_campaign()` or `runtime.switch_campaign()`. | Creates/loads save, resets history/session. | Player-facing |
| POST `/api/campaign/save` | Save active campaign to slot. | Narrator rules Save Rules to Campaign; runtime save calls. | `runtime.save_active_campaign()`. | Writes save JSON. | Player/creator/internal |
| POST `/api/campaign/delete` | Delete selected campaign save. | Delete selected. | `runtime.delete_campaign()`. | Deletes save/history. | Player-facing with risk |
| POST `/api/campaign/rename` | Rename selected campaign. | Rename selected. | `runtime.rename_campaign()`. | Updates save metadata. | Player-facing |
| GET `/api/settings/global` | Load global runtime settings and readiness. | `loadSettings()`. | `runtime.get_global_settings()`. | Reads app config, readiness, path status. | Player/developer |
| POST `/api/settings/global` | Persist global model/image settings. | `applySettings()`. | `runtime.set_global_settings()`. | Writes runtime config JSON. | Player/developer |
| POST `/api/settings/campaign` | Persist active campaign mode/play-style settings. | `applySettings()`, auto-apply setting toggles, `setCampaignMode()`. | `runtime.set_campaign_settings()`. | Writes active campaign settings and save. | Player/creator |
| POST `/api/settings/visual-pipeline/validate` | Validate visual pipeline paths without saving. | No visible direct caller found. | `runtime.validate_visual_pipeline_config()`. | Reads filesystem paths. | Developer-only |
| POST `/api/settings/visual-pipeline` | Save validated ComfyUI/workflow/checkpoint paths. | `applyVisualPipelineSettings()` if legacy button exists. | `runtime.apply_visual_pipeline_settings()`. | Writes runtime config. | Developer-only |
| GET `/api/model/options` | List local model options. | No visible direct caller found. | `runtime.list_available_local_models()`. | Reads Ollama/model environment. | Developer-only/possibly obsolete |
| GET `/api/model/status` | Return model readiness/status. | No visible direct caller found. | `runtime.get_model_status()`. | Reads runtime/provider status. | Developer/internal |
| GET `/api/models/supported` | Return supported model inventory. | `refreshSupportedModels(false)`. | `runtime.get_supported_model_inventory(refresh=False)`. | Reads supported registry/Ollama status. | Developer-only |
| GET `/api/models/active` | Return active supported model id/status. | No visible direct caller found. | `runtime.get_supported_model_inventory()` + `get_model_status()`. | Reads config/provider status. | Developer/internal |
| POST `/api/models/refresh` | Refresh supported model inventory. | Refresh inventory. | `runtime.get_supported_model_inventory(refresh=True)`. | Reads Ollama status. | Developer-only |
| POST `/api/models/install` | Install a supported model by id. | Model inventory install buttons. | `runtime.install_supported_model()`. | Starts install job. | Developer-only |
| GET `/api/models/install-status` | Poll model install job. | Model inventory polling. | `runtime.get_model_install_status()`. | Reads install job state. | Developer-only |
| POST `/api/models/activate` | Activate a supported model. | Model inventory activate buttons. | `runtime.activate_supported_model()`. | Writes runtime config. | Developer-only |
| GET `/api/providers/readiness` | Dependency readiness for local AI/image tools. | `refreshDependencyReadiness()`, Recheck. | `runtime.get_dependency_readiness()`. | Reads runtime config/filesystem/services. | Developer-only |
| GET `/api/desktop/capabilities` | Desktop integration capability report. | No visible direct caller found. | `runtime.get_desktop_capabilities()`. | Reads platform capabilities. | Developer/internal |
| POST `/api/setup/start-ollama` | Start Ollama service. | Readiness orchestration. | `runtime.start_ollama_service()`. | Launches local service. | Developer-only |
| POST `/api/setup/install-ollama` | Download/install Ollama. | Readiness orchestration. | `runtime.install_ollama()`. | External installer action. | Developer-only |
| POST `/api/setup/install-model` | Install configured Ollama model. | Install Story Model/readiness orchestration. | `runtime._start_model_install()`. | Starts model install job. | Developer-only |
| POST `/api/setup/test-image-pipeline` | End-to-end ComfyUI test image. | No visible direct caller found. | `runtime.test_image_pipeline()`. | Calls ComfyUI; may create generated image. | Developer-only |
| POST `/api/setup/install-image-engine` | Install image engine. | Readiness orchestration. | `runtime.install_image_engine()`. | Downloads/extracts/repairs ComfyUI. | Developer-only |
| POST `/api/setup/start-image-engine` | Start managed ComfyUI. | Readiness orchestration. | `runtime.start_image_engine()`. | Launches subprocess. | Developer-only |
| POST `/api/setup/stop-image-engine` | Stop managed ComfyUI. | No visible direct caller found. | `runtime.stop_image_engine()`. | Stops subprocess. | Developer-only |
| GET `/api/setup/image-engine-status` | Return managed image engine status. | Setup/image status polling. | `runtime.get_image_engine_service_status()`. | Reads process/status. | Developer-only |
| POST `/api/setup/open-image-engine-ui` | Open ComfyUI UI. | No visible direct caller found. | `runtime.open_image_engine_debug_ui()`. | Opens browser. | Developer-only |
| POST `/api/setup/orchestrate-text` | Guided text-AI setup flow. | Set Up Text AI. | `runtime.orchestrate_setup_text_ai()`. | May install/start Ollama/model. | Developer-only |
| POST `/api/setup/orchestrate-image` | Guided image setup flow. | Readiness action. | `runtime.orchestrate_setup_image_ai()`. | May install/start image backend. | Developer-only |
| POST `/api/setup/orchestrate-everything` | Guided text and image setup. | Set Up Everything. | `runtime.orchestrate_setup_everything()`. | May install/start services/models. | Developer-only |
| POST `/api/setup/pick-folder` | Native folder picker. | Pick folder buttons. | `runtime.pick_folder()`. | Uses desktop integration. | Developer-only |
| POST `/api/setup/pick-file` | Native file picker. | Pick file buttons. | `runtime.pick_file()`. | Uses desktop integration. | Developer-only |
| POST `/api/setup/open-external-url` | Open official download URL. | Download buttons. | `runtime.open_external_url()`. | Opens browser. | Developer-only |
| POST `/api/setup/open-local-path` | Open local folder/path. | Open Backend Folder. | `runtime.open_local_path()`. | Opens file explorer. | Developer-only |
| POST `/api/setup/connect-ollama-path` | Save/connect selected Ollama path. | Connect Ollama Folder. | `runtime.connect_ollama_path()`. | Writes runtime config. | Developer-only |
| POST `/api/setup/connect-comfyui-path` | Save/connect selected ComfyUI path. | Legacy/advanced image setup. | `runtime.connect_comfyui_path()`. | Writes runtime config. | Developer-only |
| GET `/api/setup/image-readiness-card` | Return simplified Image AI setup snapshot. | `refreshImageSetupSnapshot()`. | `runtime.get_image_setup_snapshot()`. | Reads image config/status. | Developer-only |
| GET `/api/setup/image-backend-diagnostics` | Return image backend diagnostics. | `refreshImageBackendDiagnostics()`, Refresh Diagnostics. | `runtime.get_image_backend_diagnostics()`. | Reads filesystem/service diagnostics. | Developer-only |
| POST `/api/setup/use-bundled-image-engine` | Use bundled ComfyUI engine if packaged. | No visible direct caller found. | `runtime.use_bundled_image_engine()`. | Writes config/path. | Developer/internal packaged |
| POST `/api/setup/save-checkpoint-folder` | Save checkpoint folder path. | Legacy/advanced path tooling. | `runtime.save_checkpoint_folder()`. | Writes runtime config. | Developer-only |
| POST `/api/setup/import-image-ai` | Import ComfyUI and model sources, set up, start. | Import, Set Up, and Start Image AI / Retry. | `runtime.import_and_setup_image_ai()`. | Copies/extracts sources; updates config; starts service. | Developer-only |
| POST `/api/setup/skip-images` | Disable image AI for now. | Disable Image AI. | `runtime.skip_images_for_now()`. | Writes runtime image settings. | Developer/player-safe setup |
| GET `/api/setup/comfyui-models` | List ComfyUI model/checkpoint status. | `refreshComfyuiModelList()`. | `runtime.get_comfyui_model_status()`. | Reads ComfyUI model folders/status. | Developer-only |
| POST `/api/images/generate` | Manual scene image generation. | Generate Image. | `runtime._request_scene_visual_generation()`. | Calls image adapter; writes generated image/scene visual store. | Future addon/creator |
