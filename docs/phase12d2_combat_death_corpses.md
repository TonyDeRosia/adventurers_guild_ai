# Phase 12D2: Classic MUD Look, Combat Death, and Corpse Integration

Smart MUD treats tbaMUD Adventurer's Lair as a behavioral reference only. No C architecture, globals, structs, combat lists, THAC0 assumptions, file formats, or message tables were copied. The implementation remains Builder-driven, SQLite-backed, service-oriented, and EventBus-based.

## Reused canonical systems

- `CombatEngine` remains the single-attack resolver.
- `CombatRuntimeService` remains encounter authority for targets, turns, queued actions, async combat output, and encounter end state.
- `MudRuntime` remains room/object/entity authority and owns runtime entity visibility, inspection, item transfer, room rendering, and world-time access.
- The runtime object/entity system owns corpses; corpses are `entity_instances` with `entity_type='corpse'`, not room text.
- `RewardService` and loot tables generate corpse contents idempotently for Builder-authored loot tables.
- SQLite remains mutable authority for combat encounters, participants, outbound messages, death transactions, entities, and item instances.
- Builder/world packages own NPC descriptions, attack profiles, natural weapons, corpse extraction profiles, and loot tables.
- The EventBus publishes compact scalar death/corpse/reward/refresh events. Future AI may observe these events but must not mutate death or corpse state directly.

## LOOK and inspection

Bare `look` uses the canonical room renderer. Room occupants now render meaningful live state instead of raw enum values: fighting targets, sleeping/resting/sitting posture, stunned/incapacitated/unconscious state, and non-unharmed condition bands are expressed as MUD prose. Dead NPCs and mobs are excluded from living lists; their corpse appears as a normal runtime object.

Direct `look`, `look at`, `examine`, and `inspect` continue through the canonical interaction target path. Actor inspection shows the display name, authored description, condition band, status, and visible equipment summary without internal IDs or exact NPC HP. Object and corpse inspection show player-facing descriptions and container/extraction state. `look in`/`look inside` validates containers and lists contents through item ownership APIs.

## Condition bands

`engine.conditions` is the single health-condition formatter. LOOK, DIAGNOSE, combat status, room rendering, and combat condition transitions use the same calculation. Default bands are: unharmed, barely scratched, lightly wounded, wounded, badly wounded, seriously injured, near collapse, incapacitated, and dead.

## Combat messages

Normal combat output no longer depends on repetitive raw numeric lines. `CombatEngine` keeps numeric damage in `DamageEvent` and history, but player messages use prose with attack-profile names, relative damage severity, misses, critical wording, and separate attacker/victim/observer perspectives. The message text is original Smart MUD wording.

Condition transition messages are emitted only when an attack moves the target to a different canonical condition band, preventing repeated wound spam every round.

## Lethal-damage transaction and idempotency

When live combat reduces an entity actor to lethal health, `CombatRuntimeService._handle_lethal_damage` performs a single authoritative handoff:

1. publishes lethal-damage and death-start events;
2. records a stable SQLite death transaction with a unique `(world_id, actor_id)` constraint;
3. persists actor health/lifecycle state as dead;
4. marks the participant defeated;
5. cancels queued actions and clears targeting involving the dead actor;
6. ends the encounter if fewer than two live sides remain;
7. creates or reuses exactly one corpse object;
8. generates corpse contents once through `RewardService`;
9. publishes actor/corpse/room refresh events;
10. delivers death, combat-end, and room-refresh output through the async combat queue.

Repeated lethal processing or retries are harmless because the death transaction and corpse lookup are stable and idempotent.

## Corpse model, containers, and loot

A corpse is a persistent runtime entity with source entity/template/name metadata, room ID, container-open state, creation world time, decay state, skinned/butchered flags, and normal runtime visibility. Corpse contents are ordinary `item_instances` owned by the corpse. `look corpse`, `look in corpse`, `get <item> corpse`, `get all corpse`, and `loot corpse` use the same entity/item resolution and transfer APIs used elsewhere.

Loot comes from authored loot tables (for example `wolf_common_loot`) via `RewardService`; command handlers do not hardcode wolf drops. Taking items moves item ownership atomically from corpse to character and publishes `corpse_looted`.

## Decay, extraction, rewards, quests, and respawn

Corpse state includes fresh/decay metadata and source actor metadata required by existing gathering/extraction services. Existing extraction services remain responsible for `skin`, `butcher`, and `harvest` operations and duplicate-prevention records.

Reward delivery uses the canonical reward packet/delivery-event schema. Quest kill-credit events are preserved as extension points through EventBus; no duplicate quest/reward calculation was added to command handlers.

Dead living entities are retired from normal visibility but remain internally available for lifecycle audit and spawn bookkeeping. Respawn remains the existing materialization/spawn concern: a later living spawn is a separate entity and never reuses the corpse.

## Async browser output

Death output uses the combat outbound queue. The attacker receives final hit/death/end messaging and one canonical room refresh showing the corpse and not the living wolf. Polling marks messages delivered, avoiding replay on subsequent polls.

## Manual browser walkthrough notes

The expected browser walkthrough is:

1. Enter Kraevok and travel to Emberwood Hunting Trail.
2. Run `look`, `look wolf`, `consider wolf`, `diagnose wolf`, `kill wolf`.
3. Let combat proceed. Attacks use prose and condition transitions, not only raw numeric damage lines.
4. On death, a killing-blow/death message appears, the wolf stops acting, combat ends, a room refresh appears, and the living wolf disappears.
5. Run `look`, `look wolf`, `look corpse`, `look in corpse`, `combat`.
6. Run `get all corpse`, then `look in corpse` to confirm contents moved once.

Automated tests cover the runtime slices that can be exercised in this environment; full browser acceptance requires an interactive browser session.
