# Phase 13C0 Canonical Player Display Contract

Smart MUD player-visible output now has a documented display pipeline:
command/action/event → canonical runtime perception → display intent → structured `DisplayDocument` → perspective-aware renderer → safe MUD markup/browser HTML or plain text.

## Global style

- Major displays use one heading, then exactly one blank line between sections.
- Ordinary one-line action messages do not receive headings.
- Engine fallback punctuation is normalized to avoid doubled punctuation.
- Builder-authored capitalization and safe MUD color markup remain authoritative.
- Default descriptive prose is white in the standard renderer; semantic colors are reserved for room titles, exits, prompt, combat, warning, error, success, quest, admin, and Builder roles.
- Internal IDs, Python dictionaries, SQLite details, event payloads, lifecycle IDs, controller IDs, and stack traces are not normal player display fields.

## Display intents

`DisplayIntent` defines the canonical vocabulary for ROOM, TARGET_LOOK, TARGET_EXAMINE, IDENTIFY, READ, LOOK_INSIDE, LOOK_DIRECTION, EXITS, INVENTORY, EQUIPMENT, SCORE, ATTRIBUTES, AFFECTS, SKILLS, SPELLS, COOLDOWNS, PROMPT, COMBAT_STATUS, QUEST_STATUS, ITEM_ACTION, MOVEMENT, POSTURE, COMMUNICATION, SOCIAL, SHOP, BOARD, QUEST, TRAINER, CRAFTING, GATHERING, COMBAT, DEATH, REWARD, RESPAWN, AMBIENT, HELP, WHO, WHERE, SYSTEM, SUCCESS, WARNING, ERROR, ADMIN, and BUILDER.

## Structured model

`DisplayDocument`, `DisplaySection`, and `DisplayEntry` carry intent, semantic role, headings, paragraphs, lines, grouped entries, key/value fields, renderer hints, and debug metadata. Debug metadata is intentionally excluded from player rendering. Plain, MUD-tagged, and browser-safe HTML renderers are supplied by `engine.mud_displays`.

## Audited existing display families

| Family | Current canonical source/service | Contract status |
|---|---|---|
| Room look, room entry, refresh | `render_room`, `MudRuntime._current_room` | Implemented; room title, description, visible actors/objects, exits in order. |
| Target look/examine/inspect/identify/read/look in/look direction | `MudRuntime.inspect_target` | Implemented; no successful target inspection falls back to full room rendering. |
| Inventory | `MudRuntime._render_inventory`, `build_inventory_document` | Repaired; heading, grouped duplicate entries, carrying summary, no IDs. |
| Equipment | `MudRuntime._render_equipment`, `build_equipment_document` | Repaired; supported wear-slot order, player-facing slot names, no enum leakage. |
| Score/stats/attributes/effects/skills/spells/cooldowns | Runtime command handlers and ability/effect services | Existing systems audited; incremental migration should return `DisplayDocument` for every subsection. |
| Prompt | `render_prompt`, `build_prompt_document` | Repaired; single canonical prompt document with HP/MP/ST degradation. |
| Movement/posture/item actions | `MudRuntime.handle_input`, item/runtime services, EventBus | Existing messages audited; perspective helper remains incremental work for all minor variants. |
| Communication/socials | command registry/runtime dialogue and social paths | Existing actor/observer patterns audited; placeholders documented for tell/reply/whisper/ask where not fully implemented. |
| Combat/death/reward/corpse/respawn | `CombatRuntimeService`, `MudRuntime.create_corpse`, `process_due_entity_respawns` | Existing descriptive messages preserved; output ordering documented. |
| Quest/shop/board/trainer/crafting/gathering/help/who/where | Existing services and command registry | Existing displays are in scope only where implemented; missing mechanics are deferred. |
| Admin/Builder diagnostics | Builder/admin command services | Authorized-only IDs/debug details remain intentional. |

## Adventurer's Lair behavioral audit

The requested GitHub repository could not be cloned in this environment because outbound GitHub access returned `CONNECT tunnel failed, response 403`. The functional audit therefore uses the prompt-provided Adventurer's Lair behavior as the reference: clean room sections, separate target look, condition bands, grouped duplicates, wear-slot equipment, perspective-specific communication/combat, configurable prompt values, and natural errors without implementation details. No C code, structs, tables, macros, file formats, or message tables were copied.

## Fallback policy

- Item room line: `room_description → long_description → short_description → name`.
- Item LOOK: `look_description → description → long_description → short_description → natural fallback`.
- Item EXAMINE: `examine_description → examine_text → extended_description → look_description → long_description → natural fallback`.
- Actor description: current state/authored runtime fields → template fields → natural fallback.
- Missing values must not render as `None`, raw dictionaries, empty command output, full-room fallback, or implementation text.

## Acceptance walkthrough notes

Automated runtime tests cover the structural model, inventory grouping, equipment slots, prompt, punctuation, target inspection, and respawn lifecycle. A live two-session browser walkthrough was not possible in this non-interactive terminal environment; observer-perspective checks remain documented for manual desktop acceptance.
