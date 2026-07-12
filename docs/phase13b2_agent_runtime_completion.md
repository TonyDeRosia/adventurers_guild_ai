# Phase 13B2 Agent Runtime Completion Notes

Phase 13B2 tightens the deterministic NPC foundation without adding needs, schedules, utility scoring, behavior trees, LLMs, or long-term memory.

## Gap audit

| Action | Characters | NPC entities | Mob entities | Canonical service | Remaining limitation |
|---|---:|---:|---:|---|---|
| `wait` | yes | yes | yes | `AgentRuntimeGateway` world-time wait | Minimal deterministic wait only. |
| `look` / `inspect` | yes | yes | yes | runtime room render and visible target resolution | Entity inspect remains compact diagnostic text. |
| `move` | yes | yes | yes | `_move_character` / `move_entity_actor` | Movement policy boundaries are still authored-data follow-up. |
| `speak` | yes | yes when authored | yes when authored | command say / `deliver_room_action` | Entity languages are not yet modeled. |
| `attack` | yes | yes | yes | `CombatRuntimeService.start_actor_attack` | Hostility policy remains conservative and service-owned. |
| `target` | yes | yes | yes | `CombatRuntimeService.actor_target` | Target must already be in the active encounter. |
| `defend` | yes | yes | yes | `CombatRuntimeService.actor_defend` queue | Defensive mechanics execute on combat pulse. |
| `flee` | yes | yes | yes | `CombatRuntimeService.actor_flee` + movement | Uses one visible/legal exit; no route planning. |
| `assist` | yes | yes | yes | `CombatRuntimeService.actor_assist` | Relationship policy remains minimal/conservative. |
| `interact` | yes | limited | limited | canonical interaction command for characters | Entity interaction remains unavailable unless a canonical non-character service exists. |
| `get_item` / `drop_item` / `loot_container` | yes | unavailable | unavailable | player item services | Entity inventory still needs owner-neutral item transfer work. |

## Player visibility and unified observed actors

NPC observations now include visible player characters in the same room as lifecycle-safe actor target refs. The gateway uses one observed-actor builder for character and entity observations, producing the same compact fields: target ref, actor id, lifecycle id, display name, actor type, room line, condition band, posture, combat status, visible summaries, relationship, and legal interaction capabilities. Player exact hit points, account data, session metadata, and inventory are not exposed.

## Authored speech capability

Speech is no longer categorically denied to all mobs. Player characters retain speech by default. NPCs and mobs must be authored with `agent_capabilities: ["speak"]` on entity state/plugin data or on the entity template. A deterministic controller profile may list `speak`, but the final available action still depends on the actor capability intersection, so a profile alone cannot grant speech.

## Canonical combat parity

Entity `target`, `defend`, `flee`, and `assist` now call generalized `CombatRuntimeService` actor entry points instead of returning gateway-level unavailable errors. The gateway still validates lifecycle, lease, observation freshness, target refs, visibility, and action contract before the combat service mutates combat state.

## TBA behavioral-reference boundary

The implementation preserves the useful behavioral principles from classic mobile activity loops: actors must be alive, present, able to perceive a legal target, and routed through movement/combat/item services. It does not copy C code, macros, global character loops, message tables, file formats, or Diku/TBA structures.

## Remaining known limitations

* Entity item ownership is still blocked because current high-level pickup/drop/loot helpers are character-shaped. Entity `get_item`, `drop_item`, and `loot_container` remain unavailable rather than faking success.
* Entity `interact` remains limited until canonical non-character runtime-object/feature interaction service entry points exist.
* Full world-package controller profile loading, authored movement boundaries, admin `agent ...` diagnostics, and automatic controller reconciliation are still tracked as follow-up work.
* The manual browser walkthrough was not performed in this non-interactive test run; coverage was added through runtime integration tests.

Deterministic controllers select legal actions. The `AgentRuntimeGateway` validates requests. Canonical runtime services determine outcomes.
