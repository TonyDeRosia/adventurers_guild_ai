# Adventurer's Lair combat lifecycle reference

This note records the behavior Smart MUD mirrors from Tony DeRosia's `tbamud_adventurers_lair` `main` branch without copying the C implementation.

## Reference sequence

- `set_fighting()` adds a character to the global combat list only when it is not already fighting, points that character's `FIGHTING()` slot at the victim, and moves a standing-capable actor into the fighting position.
- `stop_fighting()` removes exactly that character from the combat list, clears its `FIGHTING()` pointer, and restores a living actor to standing.
- `perform_violence()` walks the combat list with a saved next pointer, skips or stops entries whose opponent is gone, dead, or no longer in the same room, and performs the attack only for valid same-room opponents.
- Successful flee chooses or uses an available exit, performs normal movement with combat bypass, then calls the stop-fighting path for the fleeing actor. The actor is no longer on the combat list, no one keeps a `FIGHTING()` pointer to the actor, queued violence is cancelled, and the actor stands in the destination room.
- Failed flee does not call the stop-fighting path. The actor remains in combat with the same opponent and position.
- Attempting `FLEE` while not fighting reports that the actor is not fighting and does not move the actor.
- Target death runs damage position update, death handling, raw kill/extraction, then stops all combat references to the dead target. Attackers that were only fighting that target are restored to standing after combat.
- Attacker death follows the same cleanup from the attacker's participant side: the dead attacker is removed from active combat and any opponent pointer to it is cleared.
- Room separation is not ordinary movement while fighting. Ordinary movement is rejected for active fighters; if an actor is nevertheless no longer in the same room as its target during violence processing, combat is stopped for that actor and target pointers are cleared.
- Combat-list removal is authoritative for whether a character receives future violence ticks. Smart MUD maps this to resident participant status plus queue cancellation.
- `FIGHTING()` pointer cleanup is bidirectional for lifecycle exits: the participant's target is cleared and every other participant targeting that actor is cleared.
- Position after combat is standing for any living actor whose combat ended. Dead and incapacitated positions remain health-derived.
- The command position table allows `flee` while fighting and blocks ordinary directional movement through movement/combat checks rather than treating movement as a combat command.
