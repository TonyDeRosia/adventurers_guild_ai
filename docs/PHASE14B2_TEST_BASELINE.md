# Phase 14B2 Test Baseline

## Focused Baseline

Before the Phase 14B2 schema/registry patch, the focused Phase 14A/14B tests were used as the practical baseline because a full-suite run is outside the time available for this corrective patch.

- Focused command: `pytest -q tests/test_phase14a_ability_foundation.py tests/test_phase14b_advanced_abilities.py`
- Before count observed during this work: not separately recorded before code edits.
- After count: 9 passed when including the new schema/registry tests.

## Failure Grouping

No failures were observed in the focused suite after the patch.

| Module | Count after | Classification | Root cause |
|---|---:|---|---|
| `tests/test_phase14a_ability_foundation.py` | 0 | N/A | Passed. |
| `tests/test_phase14b_advanced_abilities.py` | 0 | N/A | Passed. |
| `tests/test_phase14b2_schema_registry.py` | 0 | N/A | Passed. |

## Full Suite Status

A complete full-suite run was completed after the patch with `pytest -q`. Result: **421 failed, 1956 passed, 17 skipped, 20 warnings** in 544.43 seconds. This matches the broad failure scale called out by the phase prompt, but this run did not include a pre-edit full-suite count, so before/after reduction is not claimed. Failures are broad and concentrated in legacy builder template/content-pack expectations, campaign-extension expectations, and extensive web-runtime/adventure-mode expectations. They should not be blanket-classified as unrelated; the groups below remain open for follow-up triage.


## Full Suite Failure Groups After Patch

| Group | Representative modules | Count evidence | Classification | Root cause summary |
|---|---|---:|---|---|
| Builder legacy/content-pack expectations | `tests/test_builder_*` | multiple failures in early output | known pre-existing defect / obsolete expectation mixed | Missing builder template files and output wording mismatches such as movement text and area range formatting. |
| Campaign ability suggestion expectations | `tests/test_campaign_extensions.py` | multiple failures in output | known pre-existing defect | Campaign narration ability suggestion events were not emitted as older tests expect. |
| Web runtime and image setup expectations | `tests/test_web_runtime.py` | majority of listed failures | unsupported legacy subsystem / missing dependency mixed | Many failures relate to offline dependency readiness, image setup orchestration, and older adventure-mode narrative behavior. |
| Phase 14A/14B focused ability tests | `tests/test_phase14a_ability_foundation.py`, `tests/test_phase14b_advanced_abilities.py`, `tests/test_phase14b2_schema_registry.py` | 0 focused failures | passed | Schema adapter, registry metadata, and advanced primitive tests pass. |

## Exact Counts

- Focused Phase 14A/14B/14B2 command after patch: `pytest -q tests/test_phase14b2_schema_registry.py tests/test_phase14a_ability_foundation.py tests/test_phase14b_advanced_abilities.py` → **9 passed**.
- Full-suite command after patch: `pytest -q` → **421 failed, 1956 passed, 17 skipped, 20 warnings**.

## Phase 14B3 Runtime Patch Test Baseline

Before this Phase 14B3 runtime patch, no fresh pre-edit full-suite run was recorded in this worktree. The most recent documented broad baseline remains the Phase 14B2 result above: **421 failed, 1956 passed, 17 skipped, 0 xfailed recorded, 0 errors recorded in the summary text**.

After the Phase 14B3 patch, focused runtime checks were run instead of a new full-suite pass because the full suite is already documented as long-running and broadly failing from legacy subsystems. The focused after-result is:

- `pytest -q tests/test_phase14a_ability_foundation.py tests/test_phase14b_advanced_abilities.py tests/test_phase14b2_schema_registry.py` → **9 passed, 0 failed, 0 skipped, 0 xfailed, 0 errors**.

| Module | Before | After | Root cause / note |
|---|---:|---:|---|
| `tests/test_phase14a_ability_foundation.py` | Not re-run before edit | 0 failures | Canonical foundation still passes after service injection changes. |
| `tests/test_phase14b_advanced_abilities.py` | Not re-run before edit | 0 failures | Advanced primitive stance/transform/summon/item/room-effect/profile tests still pass. |
| `tests/test_phase14b2_schema_registry.py` | Not re-run before edit | 0 failures | Schema adaptation and operation registry tests still pass. |

No regressions were observed in the focused ability suites. A new broad-suite after-count is not claimed for this patch.

## Phase 14B3B Prioritized Runtime Slice Baseline

This Phase 14B3B pass intentionally completed the prompt's fallback priority items 1–3 only: aura room reconciliation; summon room presence/follow/cleanup/restart hooks; and room-effect entry/exit/resident/tick behavior. Stances, transformations, passive triggers, item ability grants/activation, profiles beyond existing primitive support, Set Camp/Build Campfire migration, full command parity, backend acceptance, and Windows manual acceptance were not touched in this commit.

### Focused checks after patch

- `pytest -q tests/test_phase14b3b_auras.py tests/test_phase14b3b_summons.py tests/test_phase14b3b_room_effects.py` → **3 passed, 0 failed, 0 skipped, 0 xfailed, 0 errors, 0 warnings** in 0.75 seconds.
- `pytest -q tests/test_phase14b_advanced_abilities.py tests/test_phase14b3b_auras.py tests/test_phase14b3b_summons.py tests/test_phase14b3b_room_effects.py` → **6 passed, 0 failed, 0 skipped, 0 xfailed, 0 errors, 0 warnings** in 1.29 seconds.

### Full suite after patch

- Command: `pytest -q`
- Result: **421 failed, 1959 passed, 17 skipped, 0 xfailed, 0 errors, 20 warnings**
- Runtime duration: **574.71 seconds (0:09:34)**

### Before / after comparison

| Run | Passed | Failed | Skipped | Xfailed | Errors | Warnings | Duration |
|---|---:|---:|---:|---:|---:|---:|---:|
| Previous documented Phase 14B2 full suite | 1956 | 421 | 17 | 0 | 0 | 20 | 544.43s |
| Phase 14B3B full suite after this patch | 1959 | 421 | 17 | 0 | 0 | 20 | 574.71s |

The broad failure count remains unchanged from the documented baseline. The pass count increased by three because this patch adds three focused Phase 14B3B tests for the completed prioritized slice.
