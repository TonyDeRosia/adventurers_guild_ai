# Examination and Interaction

Phase 3E makes classic MUD examination runtime-owned. Transport input flows through `MudRuntime`, registry alias resolution, deterministic target resolution, interaction APIs, semantic rendering, and then web/telnet output.

## Description hierarchy

Objects, room features, players, NPCs, and mobs may expose `name`, `keywords`, `short_description`, `long_description`, and `extended_description`. Room rendering uses short display text only. Targeted `look`, `examine`, and `identify` render title, long/extended descriptions, and available interactions.

## Room features

Features such as doors, gates, bridges, stairs, portals, fountains, statues, altars, trees, campfires, levers, buttons, switches, signs, water, and windows are scenery, not inventory. They cannot be picked up and use placeholder read/use behavior until future Builder Mode scripts attach behavior.

## Target resolution

Targets resolve deterministically: equipped items, inventory, room objects, players, NPCs, mobs, exits, then room features. Ambiguous matches ask for clarification instead of selecting randomly.

## Semantic rendering and events

Runtime output uses semantic roles including `object_title`, `object_description`, `object_interaction`, `usage`, `placeholder`, `feature`, `entity_title`, `entity_description`, and `direction`. EventBus publishes examination and interaction events such as `object_examined`, `entity_examined`, `feature_examined`, `self_examined`, `command_usage`, `command_placeholder`, `identify_requested`, `read_requested`, and `use_requested`.

## Future hooks

Builder Mode may later provide readable text, exit descriptions, scripted feature interactions, and additional identify details without moving gameplay authority into transports or clients.
