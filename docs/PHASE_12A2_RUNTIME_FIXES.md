# Phase 12A.2 Runtime Command Fixes

This pass repairs browser/runtime command contracts without adding replacement gameplay systems.

## Command output normalization
Player command handlers must return `CommandResult` or an accepted room-render response. The command engine now normalizes handler outputs and catches unexpected handler exceptions with server-side traceback logging and a safe player-facing failure.

## Training contract
`train` and `practice` use the canonical `TrainingService`. `TRAIN` with no arguments lists trainers, current session balances, offers, costs, and selection syntax. `PRACTICE`/`PRAC` with no arguments shows practice balance and guidance instead of trying to buy an empty lesson. Malformed training failures are logged and surfaced safely.

## Alias safety
Command aliases and abbreviations are resolved through `CommandRegistry`. Ambiguous prefixes ask for clarification instead of selecting a mutating command. `consider`, `consid`, and `consi` must resolve to read-only consideration and never initiate combat.

## Conversation semantic roles
Only actual spoken words are rendered as dialogue and enclosed in quotation marks. Actions and narration must never be wrapped as speech. All actual spoken dialogue from players, NPCs, mobs, companions, pets, and scripted sources renders in white.

Conversation fallbacks avoid prompt guidance, role metadata, and pronoun-only action text. Action/emote responses use an emote semantic role and render without `says` quotes.

## Campfire rendering
Campfire and campsite player commands convert service dictionaries into prose. Normal players should not see internal IDs, raw JSON, booleans, database keys, or implementation field names.

## API gameplay-error handling
Handled gameplay failures return safe command output. Unexpected runtime exceptions are logged with traceback server-side and return a safe visible message to the client.

## Default-world content hygiene
Default player-facing room descriptions must be in-world prose. They must not contain Builder/GM instruction language such as “playable MUD room,” “fixed truth,” “GM to narrate,” or “without inventing.”

## Manual browser verification
Run this sequence in the browser client on `main-v2`:

```text
look
'hello
greet borik
train
practice
consider borik
consi borik
look
campfire
campfire status
light campfire
resources
property
```

Expected: speech remains white, actions are not quoted as speech, `train` returns HTTP 200 with visible output, `practice` gives balance/guidance, `consider` and `consi` are read-only, campfire output is prose, resources/property still work, and no developer guidance appears in room text.
