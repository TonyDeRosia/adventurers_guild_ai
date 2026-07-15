# Classic MUD Inspection Parity Matrix

Smart MUD now routes player inspection through `MudRuntime.inspect_target(viewer, resolved_target, inspection_mode)`. Target resolution is shared across LOOK, EXAMINE, IDENTIFY, READ, LOOK_INSIDE, and LOOK_DIRECTION; command parsing no longer owns category-specific rendering.

Fallback precedence for authored descriptions is:

1. `examine_description` / `examine_text` for EXAMINE and INSPECT.
2. `look_description` for targeted LOOK.
3. `description` or `long_description` for compatibility with older content.
4. `short_description`, `name`, and natural state-aware fallback text.

Builder-editable content may provide `name`, `keywords`, `room_description`, `short_description`, `look_description`, `examine_description`, `identify_description`, `readable_text`, `state_descriptions`, `interaction_hints`, portability flags, and interaction capability/default-interaction data. MUD color markup is preserved in stored text; keyword matching uses normalized lower-case tokens from names and keywords rather than rendered room prose.

| Command | Adventurer's Lair behavior | Previous Smart MUD behavior | Repaired Smart MUD behavior | Canonical Smart MUD service | Intentional difference |
|---|---|---|---|---|---|
| `look` | Renders room title, description, contents, and exits. | Rendered the room. | Continues to render room only for bare LOOK/L. | Room renderer via command engine/runtime. | HTML/semantic roles are Smart MUD-specific. |
| `look target` | Uses target-specific display functions, not room display. | Could fall through to item/entity preview or room-like fallback; descriptions often reused technical/default text. | Resolves target once and renders target heading, authored look text, visible state, and condition. | `inspect_target(..., LOOK)`. | State text is generated from Smart MUD state dictionaries. |
| `look at target` | Filler word is ignored and target is inspected. | Inconsistent parser behavior across target categories. | `at` is normalized away and the same target dispatcher is used. | `_parse_interaction_command` plus `inspect_target`. | None. |
| `examine` / `inspect` | Shows richer object/character detail where visible. | Mostly identical to LOOK for many objects/features. | Uses `examine_description`, visible state, condition, equipment, and authored hints. | `inspect_target(..., EXAMINE)`. | Does not reveal hidden mechanics. |
| `identify` | Separate stat/appraisal command. | Could serve as the only useful item detail. | Mechanical output remains separate from physical LOOK/EXAMINE. | `inspect_target(..., IDENTIFY)`. | Permission formulas remain future work. |
| `read` | Shows written/readable text. | Placeholder for many targets. | Reads `readable_text`/writing fields or gives natural no-writing response. | `inspect_target(..., READ)`. | None. |
| `look direction` | Uses exit/direction look. | Could be treated as a feature or fall through. | Resolves exit/direction and renders exit description/state without room IDs. | `inspect_target(..., LOOK_DIRECTION)` through the shared resolver. | Destination glimpses are only shown when authored. |
| `look in container` | Shows container contents, not ordinary target description. | Corpse/container routing existed but was separate and brittle. | Uses shared target resolution, then container renderer only. | `inspect_target(..., LOOK_INSIDE)` / `_look_in_container`. | Closed/empty state messages are Smart MUD wording. |
| `look actor` | Shows character/mob description, condition, visible equipment. | Actor LOOK often used generic template description. | Shows authored physical description, condition, posture/status, combat target, and visible equipment placeholder. | `inspect_target(..., LOOK/EXAMINE)`. | Exact HP and AI metadata are intentionally hidden. |
| `look object` | Shows object action/description tier. | Often used `long_description` or identify-like data. | Uses `look_description`, state such as flask fullness, then fallback. | Shared item target in `inspect_target`. | Consumable state is derived from Smart MUD item flags. |
| `look feature` | Fixed scenery can be inspected by keyword. | Fountain/gate had generic starter text and could be confused with room rendering in live testing. | Feature text is distinct; Fountain/Gate/Board/Stall have authored tiers. | Feature target in shared resolver and dispatcher. | Interaction hints are authored prose, not capability IDs. |
| `look corpse` | Corpse description separate from contents. | Corpses existed but contents/state could blur. | Ordinary LOOK shows physical corpse/freshness; EXAMINE shows wounds/processing/open state; LOOK IN shows contents. | Corpse target in `inspect_target`. | Corpse decay policy remains existing Smart MUD policy. |
| `look runtime object` | Dynamic room objects have display/action text. | Camps/campfires had special command text but not unified inspection. | Campsite/campfire runtime objects resolve like other targets and derive lit/extinguished state. | Runtime object resolver plus `inspect_target`. | Runtime object state keys are never printed raw. |

## Mob Reset / Respawn Equivalence

Adventurer's Lair/TBA-style reset behavior is represented by Smart MUD's persisted respawn queue instead of Diku reset commands. On death, the old living entity is retired, a corpse is created once, and a respawn record stores source spawn/template, old lifecycle, due real time, and state. When due, Smart MUD creates one new living entity with a new lifecycle ID and full resources; the corpse remains independent. Restart reconciliation is conservative: due records are read from SQLite and processed once, while existing alive instances prevent duplicates.
