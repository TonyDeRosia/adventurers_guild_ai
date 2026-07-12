# Phase 13C1 Runtime Display Migration Checklist

This checklist records the audited active runtime path and the migration status for the core player-facing commands in the current `main-v2` state.

| Path | Active registry / handler | Runtime service / renderer | Events / async delivery | Post-13C1 status |
|---|---|---|---|---|
| look / room entry | `MudRuntime._handle_runtime_command`, `_cmd_look` fallback | `build_room_document` via `render_room` compatibility wrapper | `room_rendered`; room async drained in `play_view` | Implemented: room DisplayDocument drives plain/HTML; normal contents default white. |
| inventory | `MudRuntime._handle_item_command` / `_render_inventory`; engine fallback `_cmd_inventory` | `build_inventory_document` and display renderers | command events; no observer output | Implemented for structured grouped display path. |
| equipment | `MudRuntime._handle_item_command` / `_render_equipment`; engine fallback `_cmd_equipment` | `build_equipment_document` and display renderers | command events | Implemented for structured slot display path. |
| score / stats / attributes / worth | `MudCommandEngine._cmd_score`, aliases and focused score sections | `DisplayDocument` sections; legacy `ActorScoreRenderer` retained for diagnostics | command events | Implemented normal-player structured score without service/SQLite/raw dictionary placeholders. |
| affects | `MudCommandEngine._cmd_affects` | `DisplayDocument` effect sections | command events | Implemented structured normal output and natural empty message. |
| skills / spells / abilities / cooldowns | `MudCommandEngine` ability handlers | Existing ability service rows, player-facing formatter | command events | Audited; formatter avoids room/HTML coupling; deeper validation remains Phase 13C2. |
| prompt | `MudRuntime.play_view` | `build_prompt_document` / `render_prompt` | `prompt_rendered` | Structured prompt path retained; configurable expansion remains limited to safe canonical tokens. |
| north / movement | `MudRuntime._move_character` | canonical room document after movement | `movement_*`, `deliver_room_action` queues | Implemented actor wording update and classic exit order. |
| say / emote | `MudCommandEngine._cmd_say`, `_cmd_emote` | `deliver_perspective_action` when runtime attached | `perspective_action_delivered`; async queue once per recipient | Implemented actor/observer perspective delivery. |
| socials | `MudCommandEngine._cmd_social` | existing social definitions | `social_emote_performed` | Audited; perspective definition expansion remains known follow-up. |
| get / drop / wear / wield / remove / drink / eat | `MudRuntime._handle_item_command`, survival handlers | canonical item ownership/equipment/survival services | item and command events; room refresh where applicable | Audited; legacy narratives remain compatible through CommandResult roles. |
| combat / death / reward / corpse / respawn | `CombatRuntimeService`, runtime lifecycle helpers | async output queue and room renderer refresh | combat/lifecycle/reward events | Audited; message ordering retained, structured one-line documents are compatible through CommandResult. |

## Adventurer's Lair parity audit

Smart MUD now matches the player-visible room fundamentals from Adventurer's Lair: a single room title, authored description paragraphs, visible contents, grouped identical room objects, and the canonical exit order `north west south east up down northeast northwest southeast southwest in out`. Category membership no longer automatically colors ordinary players, mobs, NPCs, objects, corpses, or descriptions.

## Intentional differences

Smart MUD uses Builder-authored safe MUD markup and semantic display roles instead of copying Circle/TBA command tables, C structs, macros, raw message tables, or file formats. Admin diagnostics remain separate from normal player display contracts.
