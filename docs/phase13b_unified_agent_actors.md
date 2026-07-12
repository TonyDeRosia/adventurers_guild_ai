# Phase 13B: Unified Agent Actors and Deterministic Controller Foundation

Phase 13A shipped the canonical agent gateway, but the implementation still resolved and observed only saved player characters. The audit found character-only assumptions in actor resolution, lifecycle lookup, observation self-state, available action checks, request validation, target re-resolution, movement, speech, posture, items, combat wrappers, and the manual test controller path.

Phase 13B keeps one `AgentRuntimeGateway` and adds a normalized immutable `ControlledActorContext` plus `CharacterActorAdapter` and `EntityActorAdapter`. Agent actor ids are explicit (`character:<id>` or `entity:<entity_instance_id>`); bare ids are rejected. Entity lifecycles come from persisted entity state and corpses/dead/despawned/retired entities are not controllable.

Observations are now actor-neutral. The same room lookup, visible entity queries, exits, feature resolution, recent-event table, and canonical `engine.conditions.condition_key` condition bands are used for character and entity actors. The controlled actor sees exact self resources, while other actors remain perception-filtered and expose condition bands instead of exact health.

Action availability is evaluated against `ControlledActorContext`. Entity actors can wait, look, inspect, move, posture-change, and enter supported combat through canonical services. Unsupported entity item/container and some combat queue operations return `ACTION_NOT_AVAILABLE` rather than fake success. Non-speaking mobs do not advertise available speech unless authored capability metadata allows it.

Movement for entity actors uses the runtime exit resolver and a runtime entity movement service that persists room changes, publishes movement events, and sends normal departure/arrival observer messages. It does not pathfind and does not teleport.

Combat now exposes `CombatRuntimeService.start_actor_attack`, with the player wrapper retained. Entity attacks join the same persistent combat encounter/participant/action-queue path used by characters and record lifecycle through existing combat participant fields.

Speech uses the normal room delivery path for entity actors that have an authored `agent_capabilities` speech capability. Text is HTML-escaped before delivery; no generative dialogue or LLM call is introduced.

Deterministic controller profiles are authored data in `worlds/shattered_realms/controller_profiles/controller_profiles.json` and persisted in `agent_controller_profiles`. The evaluator selects at most one action from registered, available actions and submits an `AgentActionRequest` back through the gateway. It stores compact `agent_decision_audit` rows containing ids, selected rule/action, request/result, lifecycle/world, and time; it never stores chain-of-thought or full observations.

`MudRuntime` owns the scheduler. Runtime pulses claim due deterministic controllers in SQLite transaction order, evaluate bounded actors, clear claims, and persist next-decision times. The scheduler is restart-safe enough for Phase 13B and avoids per-NPC threads or infinite loops. Agent `wait` advances world time without recursively invoking the scheduler.

Player-control precedence remains conservative: autonomous control requires a lease; connected-player takeover is not automatic; explicit override is required to replace an existing lease. Disconnect does not grant AI control. Admin diagnostics can inspect the same gateway state without exposing agent internals in normal player output.

Phase 13B does **not** add intelligent AI. It adds deterministic canonical actor control using the same legal engine actions that future behavior-tree, utility, or LLM systems may request.

Known conservative limitations: entity inventory ownership is not fully unified with character inventory commands, so entity item/container actions are unavailable. Entity target/defend/flee queue wrappers remain limited where canonical combat methods are still character-shaped.
