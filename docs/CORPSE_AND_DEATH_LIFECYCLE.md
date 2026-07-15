# Corpse and Death Lifecycle

This patch tightens the existing canonical combat/lifecycle path rather than adding another combat engine or lifecycle authority.

## Combat and death

Opening attacks remain direct command-response attacks, but the opening path no longer adds an extra forced damage packet or completes a hidden death before the first normal violence pulse. Later attacks are driven by the heartbeat violence pulse. NPC death now queues an explicit attacker-visible attack/death line and uses the existing lifecycle handoff for corpse creation, reward processing, kill credit, respawn scheduling, and encounter cleanup.

Player death remains policy-driven through the existing lifecycle respawn schedule. Administrative `restore`, `restore self`, `restore all`, and `restorestat` now restore HP, Mana, Move/Stamina, standing posture, dirty marking, prompt-invalidating resident projection, and one deliberate admin save checkpoint.

## Resident authority

Actual character entry hydrates once and registers a resident actor with a hydration-generation counter. Ordinary commands no longer rehydrate and re-register online characters. Logout saves once, removes the active character, unregisters actor state, cancels queued combat actions, and removes the resident combat actor so logged-out characters stop point-update regeneration.

## Corpse behavior

`create_corpse()` writes source, owner, room, creation monotonic time, decay seconds, and container state. The heartbeat corpse-decay pulse moves contents back to the room and destroys the corpse once. `get all corpse`, `get all cor`, `get all from corpse`, and numbered corpse resolution now use the same entity resolver as `look in corpse`, with a corpse fallback for common abbreviations.

## Movement and flee

Normal movement while fighting is rejected with an explicit `Use FLEE` message. `flee` routes through the canonical combat runtime, moves through a valid exit when possible, cancels queued actions for the fleeing actor, and asks encounter cleanup to end fights that no longer have valid opposition.

## Loot correction

The runtime no longer invents starter weapons during corpse parser handling. Basic wolf corpse contents come from the authored `forest_wolf` loot table; the Wolf Pelt quest item remains available through authored loot. Old persisted corpses may still contain historical items until they decay or are looted.

## Manual Windows checklist status

Not executed here. Tony should pull the branch on Windows, start Smart MUD, verify one heartbeat-start path, use `pulseinfo`, `residentstat`, `restore self`, `kill fox`, idle for two-second rounds, inspect/loot corpses with `get all corpse` and `get all cor`, test movement block/flee, quit Kraevok, enter Player, and confirm Kraevok no longer appears in `residentlist` or regeneration diagnostics.
