# Phase 14A Test Suite Triage

## Focused Phase 14A tests

Command: `pytest -q tests/test_phase14a_ability_foundation.py`

- Passed: 4
- Failed: 0
- Skipped: 0
- XFailed: 0
- Errors: 0

Classification: all focused Phase 14A foundation tests passed.

## Full suite

Command attempted: `pytest -q`

Result: 1951 passed, 421 failed, 17 skipped, 0 xfailed reported, 0 collection errors reported by pytest, 20 warnings in 412.04s.

Classification: the visible failures cluster in builder fixture/template expectations, legacy campaign/web runtime narrator/image dependency tests, and environment/dependency readiness checks. The focused Phase 14A ability tests and existing Phase 6C ability tests passed, so no observed failure is classified as a Phase 14A regression in this run. The broad failures should be treated as pre-existing/obsolete expectation/environment clusters unless a later focused reproduction ties one to the ability foundation.

## Runtime/backend smoke

Command attempted: `python - <<'PY' ... create_web_app ... WebRuntime ... PY`

Status: see final implementation report for exact command outcome. Manual Windows acceptance was not performed in this Linux container.
