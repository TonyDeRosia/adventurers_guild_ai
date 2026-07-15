# Phase 12A.3 Runtime Stabilization

This note documents the default runtime alpha stabilization work for the current demonstration world. Shattered Realms, Guildlands, Borik, Maren, and related content remain temporary engine-validation content, not a final production world design.

## MudCharacter and ProgressionService

`ProgressionService.initialize_actor_progression()` accepts canonical runtime `MudCharacter` objects, actor-like objects, SQLite row/mapping records, and supported dictionaries through one safe field accessor. The service reads IDs, level, experience/XP, class/profession hints, room/world/account-adjacent fields where present without treating runtime objects as dictionaries.

## Training command flow

`TRAIN`, `TRAIN <lesson>`, `TRAIN <number>`, `PRACTICE`, `PRACTICE <lesson>`, and `PRAC` route through the canonical `TrainingService` and `ProgressionService`. `TRAIN` lists trainer-authored lessons, numbered selection, costs, and current practice-session balance. Numeric and textual selection resolve against the same displayed lesson list before quote creation and confirmation. `PRACTICE` without arguments shows balance and guidance rather than trying to purchase an empty lesson.

Borik's lessons are authored in world-package training collections. They are demonstration lessons only and are not commitments for a final game design.

## Campfire light routing

Normal player `LIGHT`, `LIGHT CAMPFIRE`, and related campfire commands route to `SurvivalNeedsService`. Player output must be gameplay text and must not expose Builder, phase, JSON, instance ID, or draft terminology. Duplicate lighting reports the campfire is already lit rather than emitting duplicate ignition text.

## Session commands and browser transitions

`QUIT`, `LOGOUT`, and `DISCONNECT` save the active character, publish a session-leave event, and return the browser to character selection through a structured session-transition flag consumed by the frontend. They never stop the backend server or delete a character. `RECONNECT` reports that the player is already connected. `RESTART` is denied to normal players with guidance to use `LOGOUT`.

## Deterministic social commands

Common socials such as `HUG`, `HIGHFIVE`, `WAVE`, `SMILE`, `LAUGH`, `BOW`, `NOD`, `SHAKE`, `DANCE`, `CHEER`, `CLAP`, `SALUTE`, `SPIT`, `GLARE`, and `THANK` produce deterministic emote/action text and publish `social_emote_performed` events containing actor, target, social ID, and room. Socials are not speech, do not use quotation marks, do not mutate relationships, and do not start combat.

AI-controlled NPC reactions are deferred. Future NPC bots may observe social events, but they may never bypass canonical services for persistence, combat, progression, conversation, or world mutation.

## Conversation usability

`GREET` and `TALK` remain conversation-service commands. They should produce visible spoken dialogue or useful usage/fallback text, with speech rendered as speech and actions rendered as actions.

## Player-visible development text prohibition

Normal player command output must not include phase labels, Builder draft language, JSON collection instructions, Python tracebacks, runtime class names, raw dictionaries, internal instance IDs, or implementation roadmap text. Builder/admin diagnostics and developer documentation may still use technical language when permission-gated.

## Manual browser acceptance sequence

Use the real browser runtime to validate:

```text
look
greet borik
talk borik
train
practice
train 1
skills
spells
consider borik
consi borik
campfire
light
light campfire
cook
property
quest
journal
hug borik
highfive borik
wave borik
dance
spit borik
save
quit
```

Then return to character selection, re-enter the same character, and verify room, progression, inventory, quests, needs, and campfire/campsite persistence where the relevant service persists those states. Also test `reconnect` and `restart` as a normal player and verify safe contextual behavior.
