# Phase 14B Test Suite Triage

Date: 2026-07-14

## Focused Phase 14B suite

Command: `pytest -q tests/test_phase14b_advanced_abilities.py`

- Passed: 3
- Failed: 0
- Skipped: 0
- XFailed: 0
- Errors: 0

Classification: all focused Phase 14B checks passed.

## Phase 14A + Phase 14B regression smoke

Command: `pytest -q tests/test_phase14b_advanced_abilities.py tests/test_phase14a_ability_foundation.py`

- Passed: 7
- Failed: 0
- Skipped: 0
- XFailed: 0
- Errors: 0

Classification: no Phase 14B regression observed in the canonical ability foundation or new advanced-operation tests.

## Broad suite

Command: `pytest -q`

- Passed: 1,954
- Failed: 421
- Skipped: 17
- XFailed: 0
- Errors: 0

Classification summary from the failure surface:

- Phase 14B regression: none identified from the focused advanced-ability failures; the focused suite and Phase 14A smoke pass.
- Obsolete expectation: examples include navigation wording expecting `You head south.` while runtime returns `You travel south.`
- Pre-existing failure: numerous Builder template/content-pack tests fail because expected template JSON files are absent from `worlds/shattered_realms/builder/templates` in the checked-out repository.
- Dependency/environment: many web/image/Ollama/ComfyUI readiness tests fail in this non-interactive Linux environment without those managed Windows dependencies.
- Flaky: not isolated in this run.

Representative broad-suite failures captured during this run:

- `tests/test_builder_list_filters_phase4h_hotfix.py::test_runtime_rlist_and_rooms_filters_use_active_drafts_after_import`
- `tests/test_builder_navigation_phase4b.py::test_visible_target_room_id_exit_moves_through_canonical_graph`
- `tests/test_builder_phase4f.py::test_builder_import_validate_preview_apply_round_trip`
- `tests/test_builder_phase4g_hotfix.py::test_template_files_exist_and_commands_copy_without_overwrite`
- `tests/test_builder_phase4h_content_pack.py::test_phase4h_content_pack_files_and_shape`
- Multiple `tests/test_web_runtime.py::*` dependency/readiness and campaign-output expectation failures.

The Phase 14B-specific regressions found during focused development were fixed before commit.
