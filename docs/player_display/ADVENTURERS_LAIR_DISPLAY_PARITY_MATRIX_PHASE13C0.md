# Adventurer's Lair Player Display Parity Matrix — Phase 13C0

| Display/Command | Adventurer's Lair behavior | Previous Smart MUD behavior | Repaired Smart MUD behavior | Canonical Smart MUD source/service | Intentional difference | Implemented | Tested |
|---|---|---|---|---|---|---|---|
| look / room entry | Room name, description, contents, exits separated. | Canonical renderer existed with some style drift. | Contract documents room order and spacing. | `render_room`, `_current_room` | Browser semantic spans retained internally. | Yes | Existing + focused |
| look target | Target display distinct from room display. | Recent parity existed. | Preserved through `inspect_target`. | `_resolve_interaction_target`, `inspect_target` | Builder-native fields. | Yes | Yes |
| examine/inspect | More detail than look. | Existing path mixed text styles. | Contracted fallback tiers. | `_render_examination` | No copied C descriptions. | Yes | Yes |
| identify | Mechanical item facts when allowed. | Plain lines. | Intent recorded; no room fallback. | `_render_identify` | Permissions are Smart MUD-specific. | Yes | Existing |
| read | Authored readable content. | Existing path. | Intent documented. | `inspect_target` READ | Missing content uses natural fallback. | Yes | Existing |
| look in container | Container contents. | Existing corpse/container path. | Intent documented. | `_look_in_container` | Corpse service-backed. | Yes | Existing |
| exits/look direction | Direction state/description. | Existing direction resolver. | Intent documented. | target resolver, `_render_examination` | Destination data Builder-authored. | Yes | Existing |
| inventory | Grouped carried objects. | Unstructured “You are carrying” list. | `Inventory` document with grouped quantities and carrying summary. | `_render_inventory`, `build_inventory_document` | Stack + instance metadata retained internally. | Yes | Yes |
| equipment | Wear-slot display. | Unstructured equipment list. | `Equipment` document in supported slot order. | `_render_equipment`, `build_equipment_document` | Empty supported slots shown as “nothing”. | Yes | Yes |
| score/status | Organized character status. | Mixed runtime formatting. | Contracted as structured sections. | runtime command handlers | Incremental conversion remains. | Partial | Existing |
| attributes/effects | Human-readable headings/durations. | Service-specific. | Contracted. | effect/formula services | Raw diagnostics admin-only. | Partial | Existing |
| skills/spells/cooldowns | Availability and cost lists. | Service-specific. | Contracted. | ability service | Exact blocker migration incremental. | Partial | Existing |
| prompt | Configurable resource prompt. | HTML prompt printed debug line. | Canonical prompt document; no debug print. | `render_prompt`, `build_prompt_document` | Template customization prepared, not full parser. | Yes | Yes |
| movement | Actor/old-room/new-room perspectives. | Some command-local messages. | Contracted. | runtime movement + EventBus | Full helper migration incremental. | Partial | Existing |
| posture | Actor/observer state messages. | Existing socials/posture. | Contracted. | social/runtime handlers | Furniture capacity only where implemented. | Partial | Existing |
| item actions | Actor/observer item messages. | Command-local strings. | Inventory/equipment document standardized; action contract documented. | item ownership/runtime services | No new item mechanics. | Partial | Existing |
| say/tell/whisper/ask | Perspective-specific communication. | Say implemented; some placeholders. | Contracted; missing placeholders deferred. | command registry/runtime dialogue | Unimplemented channels not fabricated. | Partial | Existing |
| socials/emotes | Actor/target/observer templates. | Deterministic socials exist. | Contracted. | social commands | Existing socials only. | Partial | Existing |
| combat round | Attacker/victim/observer prose and condition bands. | Descriptive combat existed. | Contracted ordering and no numeric spam. | `CombatRuntimeService` | Admin diagnostics may show numbers. | Partial | Existing |
| death/reward/corpse | Final blow, death, rewards, corpse. | Existing lifecycle/respawn. | Contracted no internal lifecycle leakage. | combat runtime, `create_corpse` | SQLite lifecycle hidden. | Yes | Existing |
| respawn | Natural room appearance. | Existing queue message. | Contracted. | `process_due_entity_respawns` | Dev one-minute wolf policy retained. | Yes | Existing |
| shop | Numbered stock/prices. | Economy/service-specific. | Contract documented. | shop/economy services | No new shop mechanics. | Partial | Existing |
| board | Board title, posts, authors. | Board service-specific. | Contract documented. | board/readable services | No portable boards. | Partial | Existing |
| quest | Details, objectives, rewards. | Quest service-specific. | Contract documented. | quest services | No new quest mechanics. | Partial | Existing |
| trainer/practice | Trainable skills/costs/blockers. | Training service-specific. | Contract documented. | training services | Existing lessons only. | Partial | Existing |
| crafting/gathering | Requirements, outputs, depletion. | Service-specific. | Contract documented. | crafting/gathering services | Existing systems only. | Partial | Existing |
| help/commands | Topic sections and grouped commands. | Registry-based output. | Contract documented. | command registry | Internal registry objects hidden. | Partial | Existing |
| who/where | Visible players/location limits. | Who implemented, where placeholder. | Contract documented. | runtime/registry | Placeholder remains deferred. | Partial | Existing |
| mail/clan/auction/housing | Present in classic MUD families. | Not full systems in Smart MUD. | DEFERRED — GAMEPLAY SYSTEM NOT YET IMPLEMENTED. | N/A | Not fabricated. | Deferred | N/A |


## Phase 13C1 update

The current runtime migration checklist is maintained in `PHASE13C1_MIGRATION_CHECKLIST.md`. The canonical room path is `build_room_document` rendered through the existing `render_room` compatibility wrapper; normal categories default to white, mixed roles render per document element, and classic exit order is restored.
