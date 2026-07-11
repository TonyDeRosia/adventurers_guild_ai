# Phase 12B2 Starter Character Runtime

## Starter Ability Initialization
Builder-authored abilities `set_camp`, `build_campfire`, and `recall` live in the world package ability collection. Runtime character creation and login call the canonical ProgressionService initializer and learn these abilities through `actor_ability_progression`, so the AbilityExecutionService can list and validate them without hardcoded grants.

## Starter Character Grants
New and existing demonstration characters receive an idempotent starter migration: the three starter abilities are learned with starter metadata and missing characters receive the one-time 30 attribute point grant. Duplicate ability rows are prevented by the progression table primary key.

## Training Runtime
TRAIN and PRACTICE continue to use TrainingService. The player view now includes available points, current stat context, lesson costs, and remaining points after purchase. TrainingService spends advancement currencies through ProgressionService and records EventBus training events.

## Ability Execution Flow
Player commands route through AbilityExecutionService first. Progression-owned ability rows are merged into the ability service view, preserving cooldown, cost, mana, and grant validation before runtime side effects happen.

## Recall Spell Flow
Recall is Builder-authored with mana cost, cooldown, text, and destination metadata. `CAST RECALL` validates through AbilityExecutionService, spends mana, starts cooldown, publishes ability events, moves the character through canonical persistence, publishes movement events, and renders the destination room.

## Camp Skill Flow
`SET CAMP` is a learned skill. The command validates ability knowledge and execution through AbilityExecutionService before delegating campsite creation to SurvivalNeedsService.

## Campfire Runtime Objects
`BUILD CAMPFIRE` is a learned skill. The command validates ability execution and reuses SurvivalNeedsService campfire persistence. Existing room runtime assembly renders persisted campfires in LOOK output and canonical inspection resolves them like other room objects.

## Inspection Pipeline
LOOK and EXAMINE share the existing interaction target resolution and rendering path. Runtime-created campsite and campfire objects are included in room contents before target resolution, so they are inspectable without separate runtime inspection code.

## Runtime Object Lifecycle
Campsites and campfires are persisted in SQLite survival tables. Campfires can be lit, fueled, extinguished, inspected, rendered in rooms, and survive restart when the SQLite state store is reused.

## Starter Character Experience
A fresh demonstration character can immediately use LOOK, SKILLS, SPELLS, TRAIN, PRACTICE, CAST RECALL, SET CAMP, BUILD CAMPFIRE, LIGHT CAMPFIRE, LOOK/EXAMINE CAMPFIRE, CONSIDER BORIK, GREET BORIK, QUEST, JOURNAL, and PROPERTY through the established command, progression, ability, survival, conversation, and rendering services.
