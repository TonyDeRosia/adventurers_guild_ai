# UI Control Map

| Label/control | Element id/class | Screen/modal | Handler/function | API route | Expected result | Audience |
|---|---|---|---|---|---|---|
| Campaigns | `open-campaign-browser` | Main campaign sidebar | `openCampaignBrowser()` | `GET /api/campaigns`, `GET /api/campaign/saves` via refresh | Opens Campaign Save Journal. | Player |
| Settings | `open-setup-modal` | Main campaign sidebar | `openSetupModal()` | `GET /api/settings/global` during load/refresh | Opens Settings. | Player |
| Input mode toggle | `input-mode-toggle` | Main input bar | `toggleInputMode()` | None | Toggles IC/OOC submission mode. | Player |
| Chat input | `chat-input` | Main input bar | Enter key calls `sendInput()` | `POST /api/campaign/input` | Submits typed action. | Player |
| Send | `send-btn` | Main input bar | `sendInput()` | `POST /api/campaign/input` | Adds player message, gets narrator response, autosaves. | Player |
| Character Sheets | `open-runtime-character-sheets` | Adventure Panel | inline handler → `renderRuntimeCharacterSheets()` | `GET /api/campaign/play-view`/state-backed data | Opens attached sheets viewer. | Player; create button is Creator |
| Inventory | `open-runtime-inventory` | Adventure Panel | inline handler → `refreshInventory()` | `GET /api/campaign/inventory` | Opens inventory viewer/editor. | Player; editor Creator |
| Abilities | `open-runtime-spellbook` | Adventure Panel | inline handler → `refreshSpellbook()` | `GET /api/campaign/spellbook` | Opens abilities viewer/editor. | Player; editor Creator |
| Image prompt | `image-prompt-input` | Image Addon panel | read by `generateImage()` | `POST /api/images/generate` | Supplies manual image prompt. | Future addon/creator |
| Generate Image | `image-generate-submit` | Image Addon panel | `generateImage()` | `POST /api/images/generate` | Creates/updates scene visual if manual addon enabled. | Future addon/creator |
| Campaign Name | `form-campaign-name` | New Campaign | read by `createCampaignFromForm()` | `POST /api/campaign/start` | Campaign display/save name. | Player/creator |
| Genre / Theme | `form-world-theme` | New Campaign | read by `createCampaignFromForm()` | `POST /api/campaign/start` | Sets world theme. | Player/creator |
| Tone / Style | `form-tone` | New Campaign | read by `createCampaignFromForm()` | `POST /api/campaign/start` | Sets world tone. | Player/creator |
| World Premise | `form-premise` | New Campaign | read by `createCampaignFromForm()` | `POST /api/campaign/start` | Seeds world premise. | Player/creator |
| Hidden world/player fields | `form-world-name`, `form-starting-location`, `form-player-name`, `form-player-class`, `form-player-concept` | New Campaign | read by `createCampaignFromForm()` | `POST /api/campaign/start` | Supplies default hidden campaign/player metadata. | Internal/possibly confusing |
| Advanced Campaign Rules toggle | `advanced-campaign-rules` details | New Campaign | Native details element | None until create | Shows creation-time play-style options. | Creator |
| Allow freeform powers | `form-allow-freeform-powers` | New Campaign | read by `createCampaignFromForm()` | `POST /api/campaign/start` | Sets initial play style. | Creator |
| Auto-update character sheet | `form-auto-update-sheet-from-actions` | New Campaign | read by `createCampaignFromForm()` | `POST /api/campaign/start` | Sets initial play style. | Creator |
| Strict sheet enforcement | `form-strict-sheet-enforcement` | New Campaign | read by `createCampaignFromForm()` | `POST /api/campaign/start` | Sets initial play style. | Creator |
| Auto-sync player identity | `form-auto-sync-player-identity` | New Campaign | read by `createCampaignFromForm()` | `POST /api/campaign/start` | Sets initial play style. | Creator |
| Auto-generate NPC personalities | `form-auto-generate-npc-personalities` | New Campaign | read by `createCampaignFromForm()` | `POST /api/campaign/start` | Sets initial play style. | Creator |
| Auto-evolve NPC personalities | `form-auto-evolve-npc-personalities` | New Campaign | read by `createCampaignFromForm()` | `POST /api/campaign/start` | Sets initial play style. | Creator |
| Persist reactive consequences | `form-reactive-world-persistence` | New Campaign | read by `createCampaignFromForm()` | `POST /api/campaign/start` | Sets initial play style. | Creator |
| Narration format | `form-narration-format-mode` | New Campaign | read by `createCampaignFromForm()` | `POST /api/campaign/start` | Sets initial narration format. | Creator |
| Scene visual mode | `form-scene-visual-mode` | New Campaign | read by `createCampaignFromForm()` | `POST /api/campaign/start` | Sets initial image timing. | Future addon/creator |
| Create Sheet | `character-sheet-create` | New Campaign sheet manager | `openSheetEditor(-1)` | None until campaign create | Adds draft sheet to new campaign payload. | Creator |
| Close | `character-sheet-close` | New Campaign sheet manager | hides manager | None | Closes draft sheet manager. | Creator; manager appears hidden/possibly orphaned |
| Save Sheet | `character-sheet-save` | New Campaign sheet editor | `buildSheetFromEditor()` | None until campaign create | Saves draft sheet locally. | Creator |
| Cancel Edit | `character-sheet-cancel` | New Campaign sheet editor | hides editor | None | Cancels draft sheet edit. | Creator |
| Add Loadout Entry | `sheet-add-guaranteed-ability` | New Campaign sheet editor | `addGuaranteedAbilityEditorRow()` | None | Adds draft loadout row. | Creator |
| Create campaign | `create-campaign-confirm` | New Campaign | `createCampaignFromForm()` | `POST /api/campaign/start` | Creates campaign, enters guided startup/character creation. | Player |
| Cancel | `create-campaign-cancel` | New Campaign | `closeNewCampaignModal()` | None | Closes modal. | Player |
| Close | `close-campaign-browser` | Campaign Browser | `closeCampaignBrowser()` | None | Closes browser. | Player |
| Play selected campaign | `load-selected` | Campaign Browser | `loadSelectedCampaign()` | `POST /api/campaign/start` | Loads selected save. | Player |
| New campaign | `new-campaign` | Campaign Browser | `openNewCampaignModal()` | None | Opens new campaign modal. | Player |
| Rename selected | `rename-campaign` | Campaign Browser | `renameCampaign()` | `POST /api/campaign/rename` | Renames save. | Player |
| Delete selected | `delete-campaign` | Campaign Browser | `deleteCampaign()` | `POST /api/campaign/delete` | Deletes save after browser interaction. | Player |
| Save Item | `inventory-entry-save` | Inventory | inline async handler | `POST /api/campaign/inventory` | Upserts inventory entry and refreshes list. | Creator |
| Clear Form | `inventory-entry-clear` | Inventory | inline handler | None | Clears inventory editor fields. | Creator |
| Close | `close-runtime-inventory` | Inventory | closes modal | None | Closes inventory. | Player |
| Save Entry | `spellbook-entry-save` | Abilities | inline async handler | `POST /api/campaign/spellbook` | Upserts ability and refreshes list. | Creator |
| Clear Form | `spellbook-entry-clear` | Abilities | inline handler | None | Clears ability editor. | Creator |
| Close | `close-runtime-spellbook` | Abilities | closes modal | None | Closes abilities. | Player |
| Create Character Sheet | `runtime-character-sheet-create-toggle` | Character Sheets | opens dialog | None | Opens runtime sheet creation dialog. | Creator |
| Close | `close-runtime-character-sheets` | Character Sheets | closes modal/dialog | None | Closes sheet viewer. | Player |
| Runtime sheet fields | `runtime-sheet-create-*` | Create Character Sheet dialog | read by `createRuntimeCharacterSheet()` | `POST /api/campaign/character-sheets` | Defines new attached sheet. | Creator |
| Add Loadout Entry | `runtime-sheet-add-guaranteed-ability` | Create Character Sheet dialog | `addGuaranteedAbilityEditorRow()` | None | Adds loadout row. | Creator |
| Create Sheet | `runtime-character-sheet-create-save` | Create Character Sheet dialog | `createRuntimeCharacterSheet()` | `POST /api/campaign/character-sheets` | Creates attached sheet and refreshes view. | Creator |
| Cancel | `runtime-character-sheet-create-cancel` | Create Character Sheet dialog | closes dialog/reset | None | Cancels sheet creation. | Creator |
| Close | `close-runtime-character-sheet-create` | Create Character Sheet dialog | closes dialog/reset | None | Closes sheet creation. | Creator |
| Narrator Rules | `open-narrator-rules` | Settings > Campaign | inline async handler → `refreshNarratorRules()` | `GET /api/campaign/narrator-rules` | Opens rules editor. | Creator |
| World Building | `open-world-building` | Settings > Campaign | inline async handler → `refreshWorldBuilding()` | `GET /api/campaign/world-building` | Opens world-building viewer. | Creator |
| Close | `close-narrator-rules` | Narrator Rules | closes modal | None | Closes rules modal. | Creator |
| Rule text | `narrator-rule-input` | Narrator Rules | read by save handler | `POST /api/campaign/narrator-rules` | Text for custom narrator rule. | Creator |
| Save Rule | `narrator-rule-save` | Narrator Rules | inline async handler | `POST /api/campaign/narrator-rules` | Upserts rule. | Creator |
| Clear Editor | `narrator-rule-clear` | Narrator Rules | clears fields | None | Clears editor. | Creator |
| Save Rules to Campaign | `narrator-rules-save-campaign` | Narrator Rules | inline async handler | `POST /api/campaign/save` | Forces save. | Creator |
| Recalibrate | `recalibrate-world-building` | World Building | `recalibrateWorldBuilding()` | `POST /api/campaign/recalibrate` | Rebuilds/syncs derived world state. | Creator/developer |
| Close | `close-world-building` | World Building | closes modal | None | Closes world building. | Creator |
| Creator Mode checkbox | `creator-mode-toggle` | Settings > Campaign Mode | change handler opens confirmation or `setCampaignMode('adventure')` | `POST /api/settings/campaign` | Enables/disables editing mode. | Creator |
| Confirmation checkbox | `creator-mode-confirm-checkbox` | Creator confirmation | change handler enables button | None | Acknowledges risk. | Creator |
| Enable Creator Mode | `creator-mode-confirm-enable` | Creator confirmation | `setCampaignMode('creator')` | `POST /api/settings/campaign` | Persists creator mode. | Creator |
| Stay in Adventure Mode | `creator-mode-confirm-cancel` | Creator confirmation | closes/reset | None | Leaves Adventure Mode active. | Player |
| Close Settings | `close-setup-modal` | Settings | `closeSetupModal()` | possibly auto-save already queued | Closes Settings. | Player |
| Show narrator suggested next moves | `suggested-moves-toggle` | Settings > General | onchange queues `autoApplyCampaignSettings()` | `POST /api/settings/campaign` | Toggles suggested moves. | Player |
| Narration format | `narration-format-mode` | Settings > General | onchange queues auto-apply | `POST /api/settings/campaign` | Changes narration style. | Player |
| Campaign Rules toggles | `allow-freeform-powers`, `auto-update-sheet-from-actions`, `strict-sheet-enforcement`, `auto-sync-player-identity`, `auto-generate-npc-personalities`, `auto-evolve-npc-personalities`, `reactive-world-persistence` | Settings > Campaign | onchange queues auto-apply | `POST /api/settings/campaign` | Updates play-style behavior. | Creator |
| Story DM mode | `model-provider` | Settings > Story DM | read by `applySettings()` | `POST /api/settings/global` | Selects Basic DM Mode or Ollama. | Player/developer |
| Scene visual mode | `scene-visual-mode` | Settings > Story DM | onchange queues auto-apply and `syncVisualModeUi()` | `POST /api/settings/campaign` | Controls off/manual/auto image timing. | Future addon/creator |
| Manual image addon enabled | `manual-image-enabled` | Settings > Story DM hidden advanced | onchange `syncVisualModeUi()`; saved by `applySettings()` | `POST /api/settings/global` | Enables manual image panel. | Developer/future addon |
| Show Developer Tools | `developer-tools-toggle` | Settings > Advanced | `setDeveloperToolsVisible()` | None | Shows/hides developer tools, stores preference locally. | Developer |
| Cancel changes | `cancel-settings` | Settings > Advanced | resets campaign UI | None | Reverts unsaved campaign setting edits. | Player |
| Set Up Text AI | `setup-text-ai` | Developer Tools | `runReadinessAction('setup_text_ai')` | `POST /api/setup/orchestrate-text` | Installs/starts Ollama/model as needed. | Developer |
| Set Up Everything | `setup-everything` | Developer Tools | `runReadinessAction('setup_everything')` | `POST /api/setup/orchestrate-everything` | Runs text + image setup. | Developer |
| Recheck dependencies | `recheck-readiness` | Developer Tools | `runReadinessAction('recheck')` | `GET /api/providers/readiness` | Refreshes readiness. | Developer |
| Model Name | `model-name` | Developer Tools | read by install/setup/settings | setup/model routes | Selects Ollama model name. | Developer |
| Download Ollama | `download-ollama` | Developer Tools | `openOfficialDownload()` | `POST /api/setup/open-external-url` | Opens Ollama download page. | Developer |
| Select Ollama Folder | `pick-ollama-folder` | Developer Tools | `pickFolder()` | `POST /api/setup/pick-folder` | Chooses install folder. | Developer |
| Connect Ollama Folder | `connect-ollama-folder` | Developer Tools | `connectOllamaFolder()` | `POST /api/setup/connect-ollama-path` | Saves/validates Ollama path. | Developer |
| Install Story Model | `install-story-model` | Developer Tools | `runReadinessAction('install_model')` | `POST /api/setup/install-model` | Starts model pull/install. | Developer |
| Refresh inventory | `refresh-supported-models` | Model Inventory | inline async handler | `POST /api/models/refresh`, `GET /api/models/supported` | Refreshes supported model cards. | Developer |
| Model card install/activate buttons | dynamic classes/data attrs | Model Inventory | dynamic render handlers | `POST /api/models/install`, `GET /api/models/install-status`, `POST /api/models/activate` | Installs or activates supported models. | Developer |
| Refresh Sources | `refresh-intelligence-sources` | Campaign Intelligence Library | `refreshIntelligenceSources()` | `GET /api/developer/intelligence` | Reloads source list. | Developer |
| Add Source File | `add-intelligence-source` | Campaign Intelligence Library | `postIntelligence('/import')` | `POST /api/developer/intelligence/import` | Imports source. | Developer |
| Replace Source File | `replace-intelligence-source` | Campaign Intelligence Library | `postIntelligence('/replace')` | `POST /api/developer/intelligence/replace` | Replaces source. | Developer |
| Rebuild Index placeholder | `rebuild-intelligence-index` | Campaign Intelligence Library | status-only placeholder | None | Shows not implemented message. | Developer/future |
| Test Retrieval placeholder | `test-intelligence-retrieval` | Campaign Intelligence Library | status-only placeholder | None | Shows not implemented message. | Developer/future |
| Intelligence source fields | `intelligence-source-*` | Campaign Intelligence Library | `intelligencePayload()` | developer intelligence routes | Defines source id/path/title/category/priority/enabled. | Developer |
| Apply Enable/Disable | `apply-intelligence-enabled` | Campaign Intelligence Library | `postIntelligence('/enabled')` | `POST /api/developer/intelligence/enabled` | Updates enabled state. | Developer |
| Apply Priority | `apply-intelligence-priority` | Campaign Intelligence Library | `postIntelligence('/priority')` | `POST /api/developer/intelligence/priority` | Updates priority. | Developer |
| Open ComfyUI Download Page | `open-comfyui-download-page` | Image AI setup | `openOfficialDownload()` | `POST /api/setup/open-external-url` | Opens ComfyUI releases. | Developer |
| Open Preferred Model Download Page | `open-model-download-page` | Image AI setup | `openOfficialDownload()` | `POST /api/setup/open-external-url` | Opens model download page. | Developer |
| Pick ComfyUI Zip | `pick-image-import-comfy-file` | Image AI setup | `pickFile()` | `POST /api/setup/pick-file` | Selects archive. | Developer |
| Pick ComfyUI Folder | `pick-image-import-comfy-folder` | Image AI setup | `pickFolder()` | `POST /api/setup/pick-folder` | Selects extracted folder. | Developer |
| Pick Model File | `pick-image-import-model-file` | Image AI setup | `pickFile()` | `POST /api/setup/pick-file` | Selects checkpoint file. | Developer |
| Pick Model Folder | `pick-image-import-model-folder` | Image AI setup | `pickFolder()` | `POST /api/setup/pick-folder` | Selects checkpoint folder. | Developer |
| Import, Set Up, and Start Image AI | `import-image-ai` | Image AI setup | `importAndSetupImageAi()` | `POST /api/setup/import-image-ai` | Imports assets and starts backend. | Developer |
| Retry Setup | `retry-image-ai-setup` | Image AI setup | `importAndSetupImageAi({allowExisting:true})` | `POST /api/setup/import-image-ai` | Retries setup. | Developer |
| Disable Image AI | `disable-image-ai` | Image AI setup | `skipImagesForNow()` | `POST /api/setup/skip-images` | Disables image AI. | Developer/player-safe |
| Hidden advanced image fields | `image-provider`, `image-enabled`, `comfyui-*`, `checkpoint-*`, `preferred-*` | Advanced diagnostics hidden block | read by `applySettings()`/legacy path functions | settings/setup routes | Legacy/advanced image configuration. | Developer/possibly obsolete |
| Browse Folder/File buttons | `pick-comfyui-folder`, `pick-comfyui-workflow-file`, `pick-comfyui-output-folder`, `pick-checkpoint-folder` | Advanced diagnostics hidden block | picker helpers where bound/legacy | `POST /api/setup/pick-folder` or `pick-file` | Selects paths if exposed. | Developer/legacy |
| Open Backend Folder | `open-image-backend-folder` | Advanced diagnostics | `openLocalPath()` | `POST /api/setup/open-local-path` | Opens configured backend folder. | Developer |
| Refresh Diagnostics | `show-image-diagnostics` | Advanced diagnostics | `refreshImageBackendDiagnostics()` | `GET /api/setup/image-backend-diagnostics` | Refreshes diagnostics. | Developer |
