# Guildlands Starter Quest Flow

Phase 11F Part 1 adds the first playable Guildlands starter loop using existing canonical services and Builder/world-package content.

## Player walkthrough

1. `look` in `guildhall_crossing_square` and find Guild Registrar Maren in the starter Guildlands route.
2. `talk guild_registrar_maren` / open `maren_emberleaf_errand` through the conversation system.
3. Choose the authored offer branch and accept **Emberleaf for the Guild**.
4. `journal` shows the active quest, current stage, reward reference, prerequisite data, and objective progress.
5. `resources here` shows the existing `emberleaf_patch_crossing` resource node.
6. `gather emberleaf` / `harvest emberleaf` completes through `GatheringService`.
7. Gathering publishes `resource_gathered`; `QuestEventRouter` consumes the event once and updates the `harvest_resource` objective.
8. `journal` shows the quest is ready to turn in.
9. Return to Maren, turn in the quest, and receive the `guildlands_emberleaf_errand_reward` through `RewardService`.
10. `journal`, `score`, `inventory`, and currency display show completed state and delivered rewards. The follow-up foundation quest **Guildlands Next Steps** becomes available only after completion.

## Canonical runtime chain

`GatheringService.complete_gathering()` records the SQLite-authoritative gathering session and node capacity, then publishes the canonical `resource_gathered` event with actor, node, resource, item template, and quantity fields. `QuestEventRouter` subscribes to objective event types and routes `resource_gathered` into `QuestService.process_quest_event()`. The service matches the authored objective target (`item_template_id: emberleaf`), inserts an idempotency row in `actor_quest_event_consumption`, updates objective progress, advances the quest to `ready_to_turn_in`, and persists all state in the same SQLite authority.

## Conversation integration

The starter NPC dialogue is authored in world-package conversation collections. Branches cover greeting, offer, accept, decline, progress guidance, insufficient progress, completion text, already-completed text, farewell, and a locked follow-up explanation. Conversation actions use QuestService action types such as `accept_quest`; Python command handlers do not own starter dialogue text.

## Rewards and persistence

The starter reward packet is `guildlands_emberleaf_errand_reward` and uses supported reward entries only: experience, copper currency, practice sessions, and one Emberleaf item. Quest turn-in resolves exactly one reward packet per quest instance and stores `quest_reward_claims`; retrying after completion returns the completed quest without another packet.

## Builder authoring notes

The starter slice is owned by these world-package collections:

- `quest_definitions`, `quest_stages`, `quest_objectives`, and `quest_availability_profiles` for quest data and the follow-up prerequisite.
- `conversation_definitions`, `conversation_nodes`, and `conversation_choices` for all NPC dialogue branches.
- `reward_definitions` for turn-in reward content.
- Existing `resource_definitions` and `resource_node_definitions` for Emberleaf and the starter patch.

Run `pytest -q tests/test_guildlands_starter_phase11f.py` to validate content references, EventBus-style objective progress, restart persistence, idempotent event consumption, idempotent reward delivery, decline handling, and follow-up availability.
