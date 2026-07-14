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
