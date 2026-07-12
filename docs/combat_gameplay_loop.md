# Combat Gameplay Integration

## Combat Gameplay Loop

The live MUD combat loop is player-command driven and pulse advanced:

1. `consider <target>` uses the live combat runtime to assess a visible authored entity without starting combat.
2. `kill`, `attack`, or `hit` resolves the target through the runtime keyword resolver, validates attack legality, creates or joins one active encounter, and performs the opening attack.
3. Combat rounds continue from runtime pulses via `MudRuntime.advance_world_time()` / `runtime_pulse()` and `CombatRuntimeService.process_due_rounds()`.
4. Each round consumes at most one queued action for a participant. New player choices replace older queued actions, preventing stacked duplicate attacks.
5. Damage updates actor condition, persists health to SQLite, publishes EventBus combat events, and emits attacker/victim/observer room messages.
6. Lethal damage retires the living entity, creates one corpse, generates corpse loot, ends the encounter when one side remains, and requests a room refresh.

## Combat Runtime Flow

Canonical services remain responsible for their own domains:

- `CombatRuntimeService` owns encounters, participants, targets, queued actions, pulses, outbound combat messages, and persistence.
- `CombatEngine` resolves individual attacks and formulas.
- `AbilityExecutionService` validates and executes abilities, including costs, cooldowns, and ability events.
- `MudRuntime` renders rooms, moves characters, creates corpses, persists runtime entities, and advances world time.
- `EventBus` receives combat, movement, ability, room, corpse, and loot events.

## Combat Messaging

Combat messages are delivered by role:

- attacker messages describe the player action and result;
- victim messages describe incoming attacks;
- observer messages are queued for other active characters in the room;
- room refresh messages are sent after death so the corpse and remaining room state are visible.

Room rendering now annotates live combatants with their current opponent, for example: `Forest Wolf is here, fighting Kraevok.` The annotation is derived from active combat participants and disappears as soon as the encounter ends or the participant is defeated.

## Respawn Flow

Respawn remains service-backed. Death retires the original living entity and leaves a corpse. Later respawn materialization creates a new independent entity from authored spawn data; the corpse remains until its own lifecycle expires.

## Corpse Lifecycle

Lethal combat creates exactly one corpse per source entity. Corpse inspection, container lookup, loot transfer, and extraction commands use the existing runtime object, reward, inventory, and gathering paths. Corpse state tracks source entity, source template, decay state, and extraction flags.

## Gameplay Walkthrough

A representative manual flow is:

```text
look
consider wolf
kill wolf
combat
look
(target or ability commands as needed)
look corpse
look in corpse
loot corpse
skin corpse
wait / pulse until respawn
look
kill wolf
```

After restart, active encounters are cancelled rather than replayed, while persisted character health, retired entities, corpses, loot, and generated runtime records remain in SQLite.
