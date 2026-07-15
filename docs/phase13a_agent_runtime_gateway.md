# Phase 13A Agent Runtime Gateway

The **Agent Runtime Gateway** is the sole supported contract boundary for future autonomous controllers. A controller chooses among legal structured requests; the canonical Smart MUD engine determines reality.

## Action-entry audit

Ready for Phase 13A exposure:

- `wait`: `MudRuntime.runtime_pulse` advances canonical world time.
- `look`: `MudRuntime._current_room` and `_room_text` render canonical room perception.
- `inspect`: target refs are re-resolved through room-visible actors, objects, exits, and features before summaries are returned.
- `move`: `MudRuntime._move_character` uses canonical exit resolution, movement persistence, and room output.
- `speak`: routed through the existing speech command boundary because no lower-level speech service exists yet.
- `attack`, `target`, `defend`, `flee`, `assist`, `use_ability`: routed through `CombatRuntimeService` and ability queue paths.
- `get_item`, `drop_item`, `loot_container`: routed through canonical runtime item/container transfer helpers.
- `rest`, `stand`, `sleep`, `wake`: currently update the canonical character posture field and persist it; a richer posture service remains future work.
- `interact`: resolves a canonical target ref and then uses the existing runtime interaction handler.

Deferred for future exposure: camp creation, campfire creation, campfire lighting/extinguishing, gathering, crafting, quest interaction, and full conversations. They have command/content support in parts of the codebase, but this phase does not expose them until stable service contracts exist.

## Contracts

- `AgentObservation` contains compact structured state: observation id, world id, actor/lifecycle ids, world time, room, self state, visible actors/objects/features/exits, combat context, recent bounded events, available actions, and version.
- Self state includes exact personal health, mana, stamina, posture, lifecycle state, room reference, visible effects, queued action summary, cooldown summaries, and inventory capacity summary.
- Visible actors expose lifecycle-safe target refs, display names, actor type, condition bands rather than exact NPC HP, posture, combat status, and interaction capabilities.
- Visible objects expose only visible item/corpse/container state and safe keywords. Closed-container contents and loot-table definitions are not exposed.
- Visible exits expose direction, perceptible open/locked state, movement availability, and blocking reason codes; hidden exits are omitted.
- Available actions are advisory snapshots. Execution revalidates lifecycle, lease, target visibility, target lifecycle, room, combat state, exit state, and parameters.
- `AgentActionRequest` is structured; arbitrary command strings, method names, SQL, Python, filesystem, and network authority are not accepted.
- `AgentActionResult` separates accepted, executed, queued, rejected, retryable, result code, reason code, summary, world time, state changes, and relevant ids.

## Stable codes

Result codes are `SUCCESS`, `QUEUED`, `NO_OP`, and `REJECTED`. Reason codes include `SUCCESS`, `TARGET_NOT_FOUND`, `TARGET_NOT_VISIBLE`, `TARGET_DEAD`, `INVALID_TARGET_TYPE`, `ACTION_NOT_AVAILABLE`, `ACTION_NOT_ALLOWED`, `STALE_LIFECYCLE`, `STALE_OBSERVATION`, `ACTOR_DEAD`, `ACTOR_INCAPACITATED`, `ACTOR_IN_COMBAT`, `ACTOR_NOT_IN_COMBAT`, `COOLDOWN_ACTIVE`, `INSUFFICIENT_RESOURCE`, `MOVEMENT_BLOCKED`, `EXIT_CLOSED`, `EXIT_LOCKED`, `CONTAINER_CLOSED`, `INVENTORY_FULL`, `ITEM_NOT_FOUND`, `AMBIGUOUS_TARGET`, `INVALID_PARAMETERS`, `UNSUPPORTED_ACTION`, `CONTROLLER_LEASE_REQUIRED`, `CONTROLLER_DISABLED`, `DUPLICATE_CONTROLLER`, and `CONTRACT_VERSION_UNSUPPORTED`.

## Target references

Target refs are opaque strings in the `agentref:v1:<world>:<category>:...` namespace. They are not ordinary player output. Actor refs include lifecycle ids, exit refs include the observed room and direction, and item/corpse/feature refs include stable runtime identifiers. Re-resolution rejects fabricated refs, cross-world refs, stale actor lifecycles, invisible targets, dead living actors, and wrong target categories.

## SQLite persistence

The migration creates:

- `agent_controllers`;
- `agent_control_leases` with one active lease per world/actor/lifecycle;
- `agent_observations` storing metadata and observation hashes, not full observations;
- `agent_action_audit` with unique `(world_id, actor_id, lifecycle_id, request_id)` idempotency;
- `agent_recent_events` for bounded observation event views.

Duplicate request ids return the stored prior result after restart and do not replay movement, speech, combat queues, or item transfers.

## Control leases

Controllers must register and acquire a lifecycle-scoped lease before observation/action submission. Disabled or non-owning controllers cannot act. Respawn/lifecycle changes invalidate old leases. Player control is not automatically assigned to autonomous controllers; manual test control is explicit.

## EventBus

The gateway publishes compact serializable events: `agent_observation_created`, `agent_action_requested`, `agent_action_rejected`, `agent_action_accepted`, `agent_action_queued`, `agent_action_executed`, `agent_action_completed`, `agent_control_acquired`, and `agent_control_released`. Payloads contain ids, action/result/reason codes, target refs where safe, and world time. Full observations, prompts, mutable actor objects, and raw runtime rows are never published.

## Security boundary

The gateway uses an explicit action registry with fixed parameter schemas, target categories, executors, availability evaluators, and contract versions. Unknown action types are rejected. No autonomous decision loops, LLM calls, behavior trees, utility scoring, long-term memory, or AI world mutation are implemented.

## Manual walkthrough

Use `AgentTestControllerAdapter` in tests/tools to acquire a test actor, observe, submit caller-chosen `wait`, `move`, `attack`, and `defend` requests, resubmit a duplicate request id, and verify stale lifecycle/target/corpse/fabricated/action-without-lease rejections. The adapter never chooses goals or actions.
