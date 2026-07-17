# Known Baseline Failures — Phase 16A.1

Date: 2026-07-17

## Reproducibility contract

Future runtime phases should compare their focused tests and broad-suite deltas against this document instead of summarizing the inherited state as "unrelated failures." The last complete Phase 16A broad-suite report recorded **2032 passed** and **477 failed**. Phase 16A.1 did not treat those failures as implementation scope and did not change runtime behavior.

## Phase 16A.1 local check

`pytest -q` was started in this container to verify that the suite can still collect and execute. It was manually interrupted after 60.98 seconds because a full broad-suite run exceeds the interactive verification window; at interruption it had **146 passed** and no observed failures before the interrupt. The interrupt location was `engine/zone_resets.py`, which means this run is not a replacement for the Phase 16A complete baseline.

## Failure groups to preserve as baseline categories

| Subsystem | Baseline treatment | Classification | Follow-up rule |
| --- | --- | --- | --- |
| Builder | Builder/editor workflow, draft/publish validation, content diagnostics, and schema import/export failures from the 477-failure set. | Mixed: known unfinished feature, legacy expectation, or broken test until each failure is re-run. | Implementation phases must list exact failing tests when they touch Builder-owned files. |
| Combat | Live combat, equipment, criticals, surrender/flee/assist, death/corpse, and behavior-profile failures. | Mixed: known unfinished feature for parity gaps; unknown where failure lacks subsystem owner. | Compare focused combat tests before/after each combat-facing change. |
| Commands | Parser, command registry, movement/item/social/admin command failures. | Known unfinished feature for commands listed as partial/missing in parity inventory; unknown otherwise. | Do not claim command parity without command-handler evidence and an acceptance transcript. |
| Equipment and inventory | Wear/remove, containers, object instances, item grants, shop stock, reward containers, and corpse inventory. | Known unfinished feature for containers/object use; possible legacy expectation elsewhere. | Container/object-use phases must establish new focused baselines. |
| World Registry and resets | Room/exit data, zone reset application, content registry lookup, spawn bridges. | Known unfinished feature where reset dependency semantics are absent; unknown for unrelated fixtures. | Door/reset work must run targeted world-registry and reset tests. |
| Event Bus and runtime services | Event publication/idempotency failures for achievements, factions, quests, economy, perception, and combat. | Mixed: broken test or unfinished feature depending on event owner. | New runtime state must publish explicit events and assert them in focused tests. |
| Rendering and player output | SCORE, look/examine, room rendering, themes, display service, output queues. | Known regression only if a focused display test changed after a display commit; otherwise legacy expectation. | Preserve player-visible output snapshots when touching renderer code. |
| Persistence | Save manager, MudStateStore, player/resource state, property/storage, restart behavior. | Known unfinished feature for persistent doors, containers, corpses, and world-state gaps. | Persistence work must include restart assertions. |
| Content/data | JSON world definitions, profiles, manifests, imports/exports, and validation failures. | Mixed: schema-only/prototype content vs broken data fixture. | Treat schema-only content as non-runtime until command/service ownership exists. |
| Testing infrastructure | Slow tests, environmental assumptions, broad-suite fixture coupling. | Broken test or environment limitation, not product behavior by default. | Mark infrastructure failures separately from runtime parity failures. |

## Required failure triage fields for future updates

Every future change to this file should add exact test names under the affected subsystem and classify each as one of: known regression, known unfinished feature, broken test, legacy expectation, or unknown.
