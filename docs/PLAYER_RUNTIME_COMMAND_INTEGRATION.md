# Player Runtime Command Integration

Phase 12A.1 connects normal player commands to the existing canonical services instead of exposing implementation placeholders.

## Command Registry and Handler Ownership

Player commands are registered in `CommandRegistry` and routed by `MudRuntime`/`MudCommandEngine` to the owning service:

- training: `train`, `practice`, `prac` use `TrainingService`.
- quests/conversation: `quest`, `quests`, `journal`, `progress`, `objectives`, `accept`, `turnin`, `talk`, and `greet` use `QuestService` and runtime conversation routing.
- combat: `consider` is read-only; `attack` and `kill` use the combat command path and no longer expose runtime placeholders.
- gathering/corpses: `resources`, `gather`, `forage`, `mine`, `harvest`, `skin`, `butcher`, and `extract` use `GatheringService`.
- campfire/cooking: `campfire`, `fire`, `campsite`, `light campfire`, `add fuel`, `ingredients`, `cook`, and consumption commands use `SurvivalNeedsService` and `CraftingService`.
- economy/property: `shop`, `sell`, `property`, `properties`, `rent`, `home`, `storage`, and access commands use `EconomyService`/`PropertyService` where supported.

Missing arguments must produce player-facing syntax guidance. Builder/Admin diagnostic commands remain permission-gated.

## Default World Manual Test Guide

A normal player can use this starter walkthrough, subject to local room prerequisites:

1. `help`, `look`, `say hello`, and `'hello` verify command help, room rendering, and white speech.
2. `greet borik`, `train`, and `practice` verify conversation fallback safety and `TrainingService` listings.
3. `quest`, `journal`, `talk maren`, `accept <quest>`, and `turnin <quest>` verify `QuestService` journal and lifecycle routing.
4. `consider borik` verifies read-only threat assessment.
5. `resources here`, `gather <resource>`, `skin <corpse>`, or `butcher <corpse>` verify gathering and corpse syntax.
6. `campfire`, `light campfire`, `ingredients`, `cook <recipe> at campfire`, `eat <item>`, and `needs` verify survival/cooking integration.
7. `shop`, `sell <item>`, `property`, `rent`, and `sleep` verify economy/property/survival routing.

## Speech Rendering Standard

All player, NPC, mob, companion, pet, scripted, and Builder-authored spoken dialogue is displayed in white. This is a presentation rule only; exits, headings, combat, warnings, errors, item names, and other semantic game colors may retain their existing colors.

Dialogue output uses the shared `dialogue` semantic role. Browser CSS and backend color presets pin that role to white, including the green terminal preset.

## Placeholder Removal Checklist

Normal player command output must not contain development-phase wording such as “not implemented yet,” “foundation is available,” “Builder/Admin command,” “runtime Actor instance,” “command recognized,” or “not available yet” for implemented player systems. Admin-only diagnostics and developer documentation may still describe implementation details when permission-gated.
