# Phase 12D3 Classic MUD Perception

Smart MUD keeps one service-oriented perception path. Player commands parse aliases through the command registry, normalize filler words such as `look at` and `look in`, and then resolve visible room, inventory, equipment, feature, exit, runtime-object, corpse, player, NPC, and mob targets through `MudRuntime._resolve_interaction_target` with the shared `resolve_entity_keywords` and `resolve_item_keywords` helpers.

## Keyword and numbered-target rules

Resolution is deterministic and player-facing IDs are never exposed. The matching order is: exact visible name, exact keyword, exact multiword keyword, all keyword/name words, unambiguous prefix, then explicit numbered selection. Dot notation is supported for classic commands such as `look 2.wolf`, `kill 2.wolf`, `look 2.corpse`, and `get sword 2.corpse`. If multiple prefix matches remain, the engine asks which numbered target was meant instead of choosing arbitrarily.

Builder-authored keywords are accepted from room features, exits, item templates, entity templates, and runtime object metadata. Empty keyword strings are ignored during matching. Runtime corpses, campsites, and campfires provide derived keywords such as corpse/body/remains, camp/campsite, and fire/campfire/flames.

## Room presence, grouping, and exits

`engine.mud_displays.render_room` remains the canonical room renderer. Presence lines distinguish players, NPCs, mobs, objects, corpses, and runtime world objects while preserving Builder-authored MUD color markup and default white text. Actors use authored room descriptions when they are in a normal state; live state can override that line for sleeping, resting, stunned, fighting, and wounded actors. Connected players are never grouped.

Identical non-player room lines use `presence_group_key`, which groups only when template/name, condition, position, owner, lit state, and corpse source do not differ. Corpse, campfire, and campsite lines remain ungrouped when their state matters. Numbered targeting follows the same stable database/runtime ordering used by room rendering.

Exits render in the classic order `north west south east up down`, followed by diagonal/in/out directions. Closed or locked exits are parenthesized, and destination room IDs are not printed.

## Direct inspection and object tiers

`look`, `examine`, and `inspect` share the canonical interaction resolver. Direct actor inspection uses authored long descriptions, the canonical condition formatter, visible combat/status text, position, visible equipment placeholders, and public effect placeholders without exact NPC HP or internal IDs. Objects support room display, short carried names, long/examine descriptions, readable/action text from interaction metadata, and runtime state text.

## Containers

Corpses and future container entities use one generic flow: `look in`, `look inside`, `get <item> from <container>`, `get all <container>`, and `loot <container>`. Closed containers block inspection; non-closeable corpses remain open by default. Contents move via canonical item instance transfer APIs, preserving ownership and preventing duplication.

## Movement and room actions

Normal directional movement uses the current movement service and now emits observer async output through the existing browser/combat outbound queue. Old-room observers see departure, new-room observers see arrival from the reverse direction, and the moving actor does not receive duplicate third-person text. The same `deliver_room_action` helper is available for posture, camp, loot, combat, death, and future room-action integrations so command handlers do not need bespoke broadcast code.

## Visibility, refresh, and browser output

Room rendering, resolution, and observer delivery reuse `get_room_contents`, `find_visible_entities`, and `is_entity_visible`, excluding hidden, invisible, dead living entities, and destroyed runtime rows. Full room refresh remains reserved for topology/content changes such as entering a new room; observer action messages are appended through async polling and drained once in order.

## Adventurer's Lair behavioral-reference boundary

The implementation used Adventurer's Lair/TBA behavior as a reference for classic concepts: numbered targets, actor state room lines, object description tiers, exit ordering, corpse/container inspection, and movement observer lines. No C source, structs, message tables, global-list architecture, file formats, or licensed code were copied.

## Future AI observation boundary

Domain events such as target resolution, movement, room actions, object inspection, and container inspection stay compact and serializable. Rendered HTML remains in the output layer. Future AI may observe these events, but this phase does not add AI behavior.

## Manual browser walkthrough

Recommended acceptance script: enter with Kraevok; run `look`, `look borik`, `examine borik`, `look gate`, `look north`, and `exits`; move another player between rooms to confirm departure/arrival; test `look wolf`, `look 2.wolf`, `consider 1.wolf`, and `kill 2.wolf`; kill a wolf and verify one corpse refresh; run `look corpse`, `look in corpse`, `get all corpse`; test `set camp`, `build campfire`, `light campfire`, `look fire`, `extinguish fire`; test `sit`, `stand`, `rest`, `sleep`, and `wake`; verify unmarked text remains white and Builder color markup resets cleanly.
