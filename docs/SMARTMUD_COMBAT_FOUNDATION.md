# Smart MUD combat foundation — Phase 19A

`engine.physical_combat` is the reusable physical attack foundation.  It has
no independent state store: `CombatActor` is an adapter-shaped projection and
`DamageService` persists through its injected canonical gateway.  Player IDs
normalize from `player:<id>`/`character:<id>` to `character:<id>`; NPCs retain
their live `entity:<instance-id>` identity.

`AttackResolutionService` validates living/attackable actors, resolves weapon,
NPC natural, then player unarmed source, calculates 5–95 hit chance, damage,
position multiplier, critical, armor, and delegates mutation to `DamageService`.
The existing `CombatRuntimeService` remains the production adapter that owns
resident actors and engagements.  Its opening `kill`/`attack` attack is already
immediate and marks the next violence pulse; Phase 19A does not add scheduling.

At HP <= -11 the result code is `DEFEATED_PENDING_DEATH_PROCESSING`; this
module deliberately creates no corpse, rewards, loot, or respawn.
