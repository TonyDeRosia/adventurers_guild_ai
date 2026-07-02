# Known Test Baseline

Last checked while cleaning player-facing Adventure Mode output and Basic DM fallbacks.

## Command

```bash
python -m pytest tests/test_web_runtime.py tests/test_campaign_extensions.py tests/test_setup_modal_dom.py
```

## Current result

- `tests/test_campaign_extensions.py`: passed in the combined run.
- `tests/test_setup_modal_dom.py`: passed in the combined run.
- Combined suite result: **339 passed, 11 failed, 12 skipped**.

## Current failures observed

The remaining failures are in `tests/test_web_runtime.py` and are unrelated to the Adventure Mode player-output filter, diagnostic routing, Basic DM fallback, ability-use quarantine, or bootstrap role parsing changes in this branch:

- ComfyUI/image setup validation and orchestration baseline failures:
  - incomplete portable folder messaging still expects `python_embeded or .venv`
  - missing `pyvenv.cfg` validation is not marked broken
  - managed ComfyUI root inference is not considered valid in the test fixture
  - preferred-checkpoint setup monkeypatch does not accept `setup_lock_owned`
  - missing python runtime and launch-target validation do not report expected missing-file sentinels
- Legacy direct runtime expectations unrelated to this output-filter change:
  - lightweight NPC persistence still observes an auto-created main character sheet
  - prompt-feed retention expectations differ from current runtime behavior
  - gameplay narrator-output counting still sees retry generation
  - recalibration no longer auto-adds missing abilities directly when player-owned ability proposals are required
  - NPC dialogue split assertion expects the pre-routed message list shape

Use the focused DM/output tests and the passing `tests/test_campaign_extensions.py`/`tests/test_setup_modal_dom.py` results for this change's acceptance behavior.

## 2026-07-02 Scene Simulation V1 run

Command:
`python -m pytest tests/test_web_runtime.py tests/test_campaign_extensions.py tests/test_setup_modal_dom.py`

Observed failures outside the Scene Simulation V1 and wizard option-card scope:
- `tests/test_web_runtime.py::test_validate_comfyui_import_source_rejects_incomplete_folder_with_precise_missing_details`
- `tests/test_web_runtime.py::test_validate_comfyui_install_marks_missing_pyvenv_cfg_as_broken_runtime`
- `tests/test_web_runtime.py::test_visual_pipeline_validation_uses_managed_comfyui_for_checkpoint_inference`
- `tests/test_web_runtime.py::test_image_setup_succeeds_without_preferred_checkpoint`
- `tests/test_web_runtime.py::test_lightweight_npc_scene_state_persists_and_stays_campaign_scoped`
- `tests/test_web_runtime.py::test_turn_prompt_retains_player_system_feeds`
- `tests/test_web_runtime.py::test_gameplay_turn_still_generates_narrator_output`
- `tests/test_web_runtime.py::test_validate_comfyui_install_reports_missing_python_runtime`
- `tests/test_web_runtime.py::test_validate_comfyui_install_requires_resolvable_launch_target`
- `tests/test_web_runtime.py::test_recalibration_adds_missing_ability_when_learning_mode_enabled`
- `tests/test_web_runtime.py::test_narration_plus_resolved_npc_line_splits_to_narrator_and_npc_and_reuses_identity`

Focused checks for this change passed separately:
- `node --check app/static/app.js`
- `python -m pytest tests/test_scene_simulation.py tests/test_campaign_extensions.py tests/test_setup_modal_dom.py -q`

## 2026-07-02 Campaign Intelligence / Scene V1 run

Command:
`python -m pytest tests/test_intelligence_library.py tests/test_scene_simulation.py tests/test_campaign_extensions.py tests/test_setup_modal_dom.py tests/test_web_runtime.py`

Observed baseline failures outside the Campaign Intelligence retrieval, Scene V1 renderer/generic action, and Journal UX scope:
- `tests/test_web_runtime.py::test_validate_comfyui_import_source_rejects_incomplete_folder_with_precise_missing_details`
- `tests/test_web_runtime.py::test_validate_comfyui_install_marks_missing_pyvenv_cfg_as_broken_runtime`
- `tests/test_web_runtime.py::test_visual_pipeline_validation_uses_managed_comfyui_for_checkpoint_inference`
- `tests/test_web_runtime.py::test_image_setup_succeeds_without_preferred_checkpoint`
- `tests/test_web_runtime.py::test_lightweight_npc_scene_state_persists_and_stays_campaign_scoped`
- `tests/test_web_runtime.py::test_turn_prompt_retains_player_system_feeds`
- `tests/test_web_runtime.py::test_gameplay_turn_still_generates_narrator_output`
- `tests/test_web_runtime.py::test_validate_comfyui_install_reports_missing_python_runtime`
- `tests/test_web_runtime.py::test_validate_comfyui_install_requires_resolvable_launch_target`
- `tests/test_web_runtime.py::test_recalibration_adds_missing_ability_when_learning_mode_enabled`
- `tests/test_web_runtime.py::test_narration_plus_resolved_npc_line_splits_to_narrator_and_npc_and_reuses_identity`

Focused checks for this change passed separately:
- `node --check app/static/app.js`
- `python -m pytest tests/test_scene_simulation.py`
- `python -m pytest tests/test_intelligence_library.py tests/test_setup_modal_dom.py -q`

## 2026-07-02 GM Orchestrator integration run

Command:
`node --check app/static/app.js && python -m py_compile engine/gm_orchestrator.py engine/core_game.py engine/campaign_engine.py engine/dm_pipeline.py app/web.py && python -m pytest tests/test_core_game.py tests/test_scene_simulation.py tests/test_intelligence_library.py tests/test_setup_modal_dom.py tests/test_web_runtime.py`

Observed baseline failures outside the GM Orchestrator provider/fallback integration, context construction, validation, and structured state application scope:
- `tests/test_web_runtime.py::test_validate_comfyui_import_source_rejects_incomplete_folder_with_precise_missing_details`
- `tests/test_web_runtime.py::test_validate_comfyui_install_marks_missing_pyvenv_cfg_as_broken_runtime`
- `tests/test_web_runtime.py::test_visual_pipeline_validation_uses_managed_comfyui_for_checkpoint_inference`
- `tests/test_web_runtime.py::test_image_setup_succeeds_without_preferred_checkpoint`
- `tests/test_web_runtime.py::test_lightweight_npc_scene_state_persists_and_stays_campaign_scoped`
- `tests/test_web_runtime.py::test_turn_prompt_retains_player_system_feeds`
- `tests/test_web_runtime.py::test_gameplay_turn_still_generates_narrator_output`
- `tests/test_web_runtime.py::test_validate_comfyui_install_reports_missing_python_runtime`
- `tests/test_web_runtime.py::test_validate_comfyui_install_requires_resolvable_launch_target`
- `tests/test_web_runtime.py::test_recalibration_adds_missing_ability_when_learning_mode_enabled`
- `tests/test_web_runtime.py::test_narration_plus_resolved_npc_line_splits_to_narrator_and_npc_and_reuses_identity`

Focused GM checks added in `tests/test_core_game.py` passed with the broader non-web suites in this command before the known `tests/test_web_runtime.py` baseline failures.
