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


## Phase 18K canonical combat lifecycle

Offensive commands and abilities now share the active encounter as the single source of truth. `kill`, `hit`, `murder`, queued skills such as `kick` and `bash`, Magic Missile, future offensive abilities, NPC aggression, and pet/summon hooks enter combat by joining the existing `CombatRuntimeService` encounter instead of creating duplicate combat state. Once participants are fighting, their resident participant record is the canonical current opponent. Violent single-enemy spells with no typed target resolve that opponent exactly like legacy `TAR_FIGHT_VICT`; if combat has ended and no target was supplied, the command reports that no current opponent is available rather than returning a false invalid-room-target error.

The damage lifecycle remains Ability → validation → target resolution → `DamageService`/combat action request → `CombatRuntimeService` resolution → health mutation → death check → lifecycle death handler → corpse creation → XP/reward hooks → EventBus publication. Spell damage does not own a parallel damage path; Magic Missile submits a combat action so kill credit, corpse creation, XP, audit rows, and cleanup are performed once by the runtime.

Combat exit clears participant targets on death, flee, disconnect, movement, and encounter completion. Dead actors are marked defeated, reciprocal target references are removed, pending resident actions are ignored when targets are invalid, corpses are created from the lifecycle transition with transferred contents, and `combat_ended`/death/corpse/XP events remain the integration points for future group, pet, summon, assist, skinning, butchering, and resurrection work.

Natural weapon wording is authored-first. Runtime actors retain body/profile natural weapons and combat messages normalize wolf bites, snake bites, bear claws/bites, bird pecks, and similar authored attacks instead of falling back to generic unarmed punch wording when a natural weapon exists. Health transitions use perspective-specific grammar: players see `You look wounded.`, victims and observers see third-person names such as `Forest Wolf looks wounded.`

Wait-state parity is represented by canonical queued/recovery combat actions: melee rounds advance on the violence pulse, kick/bash/cast actions enter the same queue and recovery timing, movement/flee clear combat through the exit path, and future recovery tuning should be expressed in combat action timing rather than separate cooldown-only mechanics.
