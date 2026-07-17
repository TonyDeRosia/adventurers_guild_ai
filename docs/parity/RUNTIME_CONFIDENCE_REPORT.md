# Runtime Confidence Report — Phase 16A.1

## Scoring model

Confidence is the audit confidence that Smart MUD's current runtime behavior has been traced to production code, tests, persistence, Builder/data exposure, and Adventurer's Lair evidence. It is not a feature-completeness score.

| Runtime domain | Confidence | Why |
| --- | ---: | --- |
| Character identity, stats, score, resources | 75% | Strong Smart MUD code/test evidence exists in character, stat, score, and resource services; exact customized Adventurer's Lair source verification remains blocked. |
| Movement, rooms, exits, occupancy | 50% | Runtime movement and room occupancy exist, but persistent door/lock/key state remains partial and is the next foundation. |
| Commands and parser | 50% | Command registry and MudRuntime dispatch exist, but many individual commands are partial, missing, or unverified. |
| Combat and death lifecycle | 75% | Live combat, resources, critical profiles, death/corpse documentation, and focused tests exist; some advanced behaviors remain partial. |
| Inventory, equipment, object use | 50% | Inventory/equipment paths exist; containers, consumables, lights, and object magic need implementation phases. |
| NPC/mobile behavior | 50% | Combat behavior and profiles exist, but Adventurer's Lair AI actor brains/aggression/scavenging parity is not fully proven. |
| Quests, triggers, scripts | 25% | Quest services exist; DG script/trigger runtime parity is structurally absent and needs a later foundation. |
| Economy, shops, banks, rent/storage | 50% | Economy and shop data/services exist; full AL shop/rent/storage behavior is incomplete. |
| Builder/content registry | 75% | Strong Builder/content registry and schema evidence exists; runtime parity must remain owner-specific and avoid Builder-only assumptions. |
| Persistence/world-state | 50% | MudStateStore and runtime stores exist; persistent doors, containers, corpse state, and reset histories need a shared state contract. |
| Rendering/player output/help | 75% | Display, score, help, rendering, and output services have focused evidence; exact AL output strings still require source/manual verification. |
| Custom Adventurer's Lair features | 50% | Criticals and class tracks have Smart MUD evidence; AI brains, accounts, ASCII maps, and DG scripts remain source-verification dependent. |

## Phase-order verdict

Phase 16B should proceed unchanged as the next implementation phase. Persistent exit/door state is still the lowest-risk foundational dependency because containers, object use, resets, mobile behavior, scripts, and Builder validation all need reliable room/exit state before they can be implemented without architectural guessing.

## Remaining NEEDS-VERIFICATION

The JSON inventory still contains 278 NEEDS-VERIFICATION entries. Phase 16A.1 adds a required reason to each remaining entry rather than pretending unsupported parity has been proven without access to the customized Adventurer's Lair source tree.
