# Current SmartMUD death foundation audit

Phase 19A detects terminal HP at `-11`, sets `DEAD`, emits its combat defeat
event, and previously stopped at the `DEFEATED_PENDING_DEATH_PROCESSING`
boundary.  The live runtime already has canonical entity instances, item
ownership transfer, container/corpse inspection, room object placement, and a
corpse decay pulse that spills contained items to the room before removal.

The prior combat lifecycle could create NPC corpses, but did not provide a
single durable, terminal-damage death claim.  Items use `owner_type`/`owner_id`
and equipment is distinct from carried ownership. NPC template loot is present
in template data; legacy runtime generation is not the Phase 20A authority.
Restart could revisit incomplete lifecycle work because it had no death-ledger
claim. This phase supplies that ledger and leaves the existing canonical
container runtime intact. No player command is used to extract a dead actor.
