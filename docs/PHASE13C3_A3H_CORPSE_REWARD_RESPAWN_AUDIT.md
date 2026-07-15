# Phase 13C3-A3H Corpse, Reward, and Respawn Audit

## Existing corpse path

- `MudRuntime.create_corpse(entity_id, **ctx)` is the live corpse creation entry point. It marks the source entity dead, spawns a persisted `entity_instances` row with `entity_type='corpse'`, stores source entity/template/lifecycle/death/killer metadata in the corpse state, names the corpse visibly, calls corpse content generation, schedules entity respawn, publishes `corpse_created`, and returns the corpse entity.
- Corpse contents previously came only from authored loot tables through `MudRuntime._generate_corpse_contents`, `RewardService.resolve_loot_table`, and `RewardService.deliver_reward_packet`. That generated new reward item instances owned by `corpse:<corpse_id>` rather than proving existing inventory/equipment transfer.
- Canonical runtime item instances live in `item_instances(instance_id, world_id, template_id, owner_type, owner_id, room_id, equipped_slot, stack_count, condition, durability, custom_flags, plugin_data, destroyed_at)`. Runtime movement uses `MudRuntime.move_item`/`transfer_item`; container reads use `find_container_items(owner_id)` for `owner_type IN ('corpse','container')`.
- Equipment is represented as item ownership (`owner_type='equipment'`, `owner_id=<actor/character/entity id>`, `equipped_slot=<slot>`) in the canonical runtime item table.
- Room corpses also exist in legacy `room_corpses`, but live look/loot/open support for current runtime corpses is entity/item based, not that legacy JSON list.
- Respawn already had `entity_respawn_queue` for entity respawns, with `schedule_entity_respawn` and `process_due_entity_respawns`, but lifecycle status previously marked respawn as completed at reservation time.

## Implemented A3H path

- `RuntimeLifecycleService.create_corpse` now returns immutable `CorpseCreationResult` and treats the persisted corpse entity as the canonical corpse.
- Stable corpse identity is derived from world, actor, and transition as metadata; repeat processing looks up the corpse by transition metadata and returns the same corpse.
- Existing canonical item instances owned by the dead entity or its equipment are evaluated by death flags/tags. `destroy_on_death` destroys once, `keep_on_death`/`soulbound`/`quest_item` retain, and other items move to the corpse container with instance ids, quantities, durability, condition, flags, and plugin data preserved.
- Equipped items are moved through the same canonical item update, clearing `equipped_slot` when the item is placed in the corpse.
- `RuntimeLifecycleService.award_kill_rewards` creates an idempotent reward claim keyed by transition, applies authored XP/currency on eligible player kills, and persists `actor_kill_credits`. Environmental/self/non-player sources are skipped by policy.
- Quest/campaign credit is reported as `unsupported` unless a future canonical hook is connected; it is not marked completed by ID reservation.
- `RuntimeLifecycleService.schedule_respawn` creates exactly one pending `actor_respawn_schedules` row. `CombatRuntimeService.process_due_respawns` claims due rows, restores resources, moves player characters to the destination, clears combat targeting, publishes `actor_respawned`, and marks the schedule completed.
