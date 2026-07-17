# MEDIT/OEDIT Completion Matrix — Phase 15B.39

This audit covers all visible Smart MUD MEDIT and OEDIT menu entries after Phase 15B.39. The reference workflow is the TBA-style OLC draft editor model: numbered menus, temporary drafts, explicit validation, preview, undo/redo, cancel/back, and save. Runtime systems that do not have canonical executable support are not exposed as fake editors; where a canonical data field is retained for compatibility it is marked limited/read-only in the workflow notes.

## Completion rules

| Rule | Status |
|---|---|
| No visible raw bitvector editing | Complete: flag fields open toggle editors. |
| No visible serialized/dictionary prompts | Complete: structured field/list/reference/flag managers are rendered instead. |
| No raw field-value shell advertised in MEDIT/OEDIT menus | Complete: menus direct builders to numbered field managers. |
| Draft safety | Complete: session savepoint, dirty state, undo, redo, cancel/back, and explicit save are present. |
| Preview and validation | Complete: parent sessions and focused managers expose preview/validate actions. |

## MEDIT matrix

| Editor | Menu | Submenu | Option | Current implementation | Runtime subsystem | Current workflow | Classification | Builder usability | Required work | Final status |
|---|---|---|---|---|---|---|---|---|---|---|
| MEDIT | Main | Identity | Display name, id, VNUM, entity type | Numbered field descriptors | Entity/mobile templates | Select option, enter validated value, undo/redo/save | Functional | No JSON or SQL | None | Complete |
| MEDIT | Main | Keywords | Keyword list | List editor | Entity aliases/search | Add/remove/move/clear with duplicate guard | Functional | Structured list editing | None | Complete |
| MEDIT | Main | Descriptions | Room/look/short text | Multiline editor | Look/rendering | `.save`, `.cancel`, `.show`, `.clear` | Functional | No raw serialized text | None | Complete |
| MEDIT | Main | Race/Class/Traits | species, race, gender, size, alignment | Numbered validated fields | Mobile identity | Select field and edit draft | Functional | Guided values/help | None | Complete |
| MEDIT | Main | Level/Stats | level and attributes | Numbered integer descriptors | Combat/stat runtime | Range checked prompts | Functional | Immediate validation | None | Complete |
| MEDIT | Main | HP/Mana/Move | resources map | Numbered resource descriptor | Resource runtime | Structured field display; canonical map retained | Functional limited | No dictionary prompt displayed | Formula-specific UI deferred until formula subsystem exposes per-resource schema | Complete |
| MEDIT | Main | Combat | armor/behavior/threat/ability profile refs | Numbered descriptors | Combat services | Field managers and validation | Functional limited | Canonical profile IDs visible with search elsewhere | Dedicated profile editors outside MEDIT are not duplicated | Complete |
| MEDIT | Main | Body/Natural Weapons | body profile and natural weapons | Reference/body workflow and manager | Body/combat runtime | Choose body, manage attacks, preview/validate | Functional | No bitvectors | None | Complete |
| MEDIT | Main | Positions | default/spawn position | Numbered fields | Mobile posture | Validated draft edit | Functional | Guided menu | None | Complete |
| MEDIT | Main | Action Flags | mobile flags | Toggle flag editor | Mobile flags | Number toggles/all/none/help | Functional | No raw bitvectors | None | Complete |
| MEDIT | Main | Affect Flags | affect flags | Toggle flag editor | Affect/status flags | Number toggles/all/none/help | Functional | No raw bitvectors | None | Complete |
| MEDIT | Main | Equipment | equipped/carried loadout | Structured loadout manager | Equipment/items | Assign/carry/edit/remove/clear/search/preview/validate | Functional | No serialized loadouts | None | Complete |
| MEDIT | Main | Inventory | starting inventory | List editor | Inventory runtime | Add/remove/move/clear | Functional | Structured list | None | Complete |
| MEDIT | Main | Loot/Shops | loot and corpse refs | Numbered canonical fields | Loot/corpse/shop data | Draft fields plus validation | Functional limited | Exposes supported refs only | Shop-specific runtime editor absent; not faked | Complete |
| MEDIT | Main | Abilities | ability loadout/granted abilities | Field/list descriptors | Ability runtime | Structured list/reference style | Functional limited | No Python structures | Full spell editor not part of MEDIT | Complete |
| MEDIT | Main | Behavior | behavior/personality/schedule refs | Field descriptors | AI/behavior runtime | Draft refs with preview | Functional limited | No shell menu advertised | Dedicated AI profile editing deferred | Complete |
| MEDIT | Main | Faction | faction and relationships | Field/list descriptors | Faction/org runtime | Draft refs/list | Functional limited | Search available through Builder discovery | Dedicated faction editor deferred | Complete |
| MEDIT | Main | Scripts | script IDs | List descriptor; menu hidden only if no runtime records | Script/trigger runtime | Attach IDs where canonical records exist | Unsupported/limited | No fake script language | Runtime scripting is not fully canonical in this repo | Complete |
| MEDIT | Main | Spawns | spawn/reset references | Structured spawn manager | Spawn/reset runtime | Add/edit/remove/search/trace/preview/validate | Functional | No reset syntax required | None | Complete |
| MEDIT | Main | Diagnostics | validation/references/preview | Read-only diagnostics | Validation/runtime | Preview/validate/testspawn | Read only | Intentional read-only | None | Complete |

## OEDIT matrix

| Editor | Menu | Submenu | Option | Current implementation | Runtime subsystem | Current workflow | Classification | Builder usability | Required work | Final status |
|---|---|---|---|---|---|---|---|---|---|---|
| OEDIT | Main | Identity | name/id/descriptions | Object editor fields | Item templates | Numbered draft fields and save | Functional | No JSON/SQL | None | Complete |
| OEDIT | Main | Keywords | keywords | List editor | Search/look parser | Add/remove/move/clear | Functional | Duplicate validation | None | Complete |
| OEDIT | Main | Extra descriptions | extra descriptions | Structured list field/preview | Look/examine | Manage list in draft | Functional limited | No raw encoded prompt displayed | Rich reorder manager uses list editor | Complete |
| OEDIT | Main | Item Type/Subtype | type/category/material | Enum/field descriptors | Item runtime | Select type; type-specific sections show/hide | Functional | Unsupported sections hidden | None | Complete |
| OEDIT | Main | Weight/Cost | numeric economics | Validated object mutation/editor fields | Economy/inventory | Non-negative validation | Functional | Clear error messages | None | Complete |
| OEDIT | Main | Wear Flags | wear flags | Toggle flag editor | Equipment runtime | Number toggles/all/none | Functional | No bitvectors | None | Complete |
| OEDIT | Main | Extra Flags | extra flags | Toggle flag editor | Item flags | Number toggles/all/none | Functional | No bitvectors | None | Complete |
| OEDIT | Main | Weapon | damage/combat fields | Visible only for weapons/armor | Combat item runtime | Validated draft fields and combat preview | Functional | Hidden for unrelated types | None | Complete |
| OEDIT | Main | Armor | armor/resistance fields | Visible only for armor/weapon support | Armor runtime | Validated draft fields | Functional | Hidden for unrelated types | None | Complete |
| OEDIT | Main | Container | capacity/lock/key | Visible only for containers | Container runtime | Validated draft fields and container preview | Functional | Hidden otherwise | None | Complete |
| OEDIT | Main | Food/Drink | nutrition/liquid/servings | Visible only for consumables/drinks | Consumable runtime | Validated draft fields | Functional | Hidden otherwise | None | Complete |
| OEDIT | Main | Light | light data | Visible only for light type | Light runtime | Validated draft fields | Functional | Hidden otherwise | None | Complete |
| OEDIT | Main | Magic/Affects | spell/affect data | Canonical fields only | Ability/affect runtime | Structured list/field drafts | Functional limited | No Python structures | Runtime spell scripting not duplicated | Complete |
| OEDIT | Main | Scripts | script IDs | Exposed only as canonical IDs where present | Script runtime | Attach/list validation | Unsupported/limited | No fake editor | Runtime scripting incomplete | Complete |
| OEDIT | Main | Crafting Metadata | recipe/crafting refs | Read-only/field refs | Crafting runtime | Preview/dependency lookup | Read only/limited | No hidden syntax | Dedicated crafting editor deferred | Complete |
| OEDIT | Main | Validation | object validation | Validator | Item runtime | Field-specific errors | Functional | Explains field and reason | None | Complete |
| OEDIT | Main | Preview | look/inventory/equipment/shop | Preview renderer | Item rendering/shop | Ground, inventory, equipment, examine, shop text | Functional | Builder can inspect results | None | Complete |

## Hidden or intentionally limited runtime features

* REDIT, AEDIT, ZEDIT, metadata registry, visual desktop builder, and AI builder are outside this phase.
* Script menus do not invent a DG-script-compatible language when canonical runtime script records are unavailable.
* Shop-specific mobile merchant authoring remains limited to existing canonical references because the repository does not provide a full shop editor in MEDIT.
* Formula/resource profile authoring remains limited to canonical draft fields; the formula registry is a separate subsystem.

## Manual acceptance walkthrough

1. `medit training_master_borik`; open each numbered section from 1 through 20.
2. In Identity, Level/attributes, Positions, Combat, Behavior, Faction, and Loot, select a numbered field, enter a valid value, undo, redo, preview, validate, and back out.
3. In Keywords, Inventory, Abilities, and Scripts, add a list item, reject a duplicate where applicable, move/remove it, undo, redo, and back out.
4. In Descriptions, open a multiline field, enter two lines, `.show`, `.cancel`, repeat, `.save`, preview, undo, redo.
5. In Mobile Flags and Affect Flags, toggle by number, use `all`, `none`, undo, redo, validate.
6. In Equipment, search for `training`, assign `training_sword` to `mainhand`, carry `field_ration`, preview, validate, undo, redo, remove.
7. In Spawns, add `guildhall_crossing_square`, edit max/chance, preview, trace, validate, undo, redo, remove.
8. Save, quit, reopen the mobile, and confirm saved draft values.
9. `oedit training_sword`; confirm type-specific grouped sections and hidden unsupported container/light/food/drink sections.
10. Open object fields, edit name/type/keywords/descriptions/wear flags/extra flags, preview, validate, undo, redo, save, quit, and reopen.
