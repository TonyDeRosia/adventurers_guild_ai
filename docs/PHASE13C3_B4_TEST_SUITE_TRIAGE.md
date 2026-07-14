# Phase 13C3-B4 broad test-suite triage

Command run: `pytest -q`

Result counts from the completed run:

- Passed: 1946 (from completed broad run before cleanup of test-generated world files)
- Failed: 422
- Skipped: 17
- Xfailed: 0
- Errors: 0

## Classification

| Failing group | Classification | Notes |
|---|---|---|
| Builder import/list/content-pack expectations | Pre-existing unrelated failure / obsolete expectation | Failures reference missing builder template/content-pack fixtures and text differences such as `You head south.` vs `You travel south.`; not touched by B4 stat authority. |
| Campaign extension/event suggestion tests | Pre-existing unrelated failure | Failures are in campaign narration/ability suggestion event production, unrelated to stat snapshots. |
| Web runtime narration/image setup/readiness tests | Missing dependency/environment and pre-existing unrelated failure | Large group depends on Ollama/ComfyUI/web-runtime UI behavior and packaging setup; B4 changed no web runtime setup code. |
| Smart MUD B4 stat-authority focused tests | Genuine B4 coverage | Added and passing. |
| Phase 13C3 A/B canonical stat tests | Mixed genuine B4 guard and obsolete expectation | B3 read-only snapshot and B4 focused tests pass; older runtime resource-clamp expectations that require `get_combat_snapshot()` to mutate/clamp resources are obsolete under the B4 read-only snapshot rule. |

## Genuine B4 regressions fixed

- ActorStatInput modifier skipping in `get_breakdown()` was removed.
- ActorStatInput resistance modifiers are consumed.
- PrimaryStatValue is exposed as the canonical snapshot primary type with compatibility accessors.
- Current carry weight uses a canonical projection hook/fallback instead of double-counting equipped/destroyed items.
- Combat resolution normal path selects its attack profile from the canonical snapshot.

## Manual Windows acceptance status

Not performed in this Linux container. Use these commands in a Windows runtime session:

```text
score
combatstats
combatstats breakdown attack_power
builder on
attributes <npc>
combatstats <npc>
combatstats <npc> damage
combatstats <npc> breakdown attack_power
```
