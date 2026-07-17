# Phase 15C.0 Builder OEDIT Specification

This specification is the canonical Smart MUD implementation roadmap for Object Builder parity with Anthony's customized Adventurer's Lair Builder. Adventurer's Lair is a behavioral reference only. Smart MUD must preserve builder-facing outcomes through typed commands, Builder sessions, drafts, validation, preview, publish, activation, and rollback without porting TBA code, bitvectors, global object arrays, object file formats, or Oasis menu architecture.

## Audit Scope and Evidence

Direct checkout of `TonyDeRosia/tbamud_adventurers_lair` was attempted during this phase, but the environment returned `CONNECT tunnel failed, response 403`. This document is therefore a conservative permanent parity contract based on the requested OEDIT feature surface, established TBA/Circle Oasis OEDIT behavior, and existing Smart MUD Builder/publish architecture. Later local source review may append precise Adventurer's Lair labels and custom flags, but Smart MUD must continue to use the architecture specified here.

## OEDIT Primary Workflow

`oedit <id|vnum>`, `ocreate <vnum> <name>`, `ostat <id|vnum>`, `odelete <id|vnum>`, and future object subcommands must resolve Smart MUD IDs first and VNUMs second. Creation requires current or explicit area ownership and an object VNUM inside that area's object range. Draft object IDs should follow `<area_id>_obj_<vnum>` unless an existing stable ID is being preserved.

OEDIT sessions use scratch working records, savepoints, locks, dirty tracking, validation, diff, preview, save, discard, and dirty quit prompts. Save writes only Builder drafts. Publish updates immutable world-package generations; runtime item instances keep their existing template projection according to Smart MUD runtime policy unless a later migration explicitly changes them.

## General Object Fields

| Field | Parity behavior | Smart MUD requirement | Validation |
|---|---|---|---|
| Keywords | Command lookup nouns. | Ordered keyword list. | Required, safe, non-empty. |
| Short description | Inventory/equipment display. | `short_description`/display name. | Required. |
| Long description | Room ground line. | `long_description`. | Required for world-spawnable objects. |
| Action description | Text shown when used/read/activated for some types. | `action_description` or type-specific message profile. | Required for readable/usable types when no message profile exists. |
| Type | Object category drives values editor. | `object_type` enum. | Required; values must match type. |
| Extra flags | Special object properties. | Named flag list. | Must be known or custom namespaced. |
| Wear flags | Legal wear/carry positions. | Named wear-location list. | Must be compatible with body slots and item type. |
| Weight | Encumbrance. | Numeric weight and unit. | Non-negative; container contents rules apply. |
| Cost | Shop/base value. | Economy price field/profile. | Non-negative; currency profile valid. |
| Timer | Decay/expiration duration. | Decay/timer profile or minutes. | Negative invalid; zero means no timer if configured. |
| Values | Type-specific data. | Structured per-type subdocument. | Validated by specialized editor. |
| Applies | Stat modifiers. | Ordered apply records. | Known apply type, legal amount, stacking policy. |
| Extra descriptions | Look/examine keyed descriptions. | Shared extra-description model with rooms. | Unique keywords; description required. |
| Minimum level | Usage/equip requirement. | Requirement profile or `minimum_level`. | Must be non-negative and policy-compatible. |
| Permanent affects | Effects granted while worn/held/used. | Effect references or named permanent affects. | Must resolve and define stacking/removal behavior. |
| Scripts | Triggered behavior. | Future unified script references. | Registry/dependency validation. |

## Extra Flags Catalog

Logical groups must be shown in the Builder rather than one flat bit list.

| Group | Flags/concepts | Purpose | Validation |
|---|---|---|---|
| Visibility | glow, hum, invisible, hidden, dark, no_locate | Presentation, magical detection, searchability. | Requires visibility/perception support for runtime effect. |
| Durability | magic, blessed, anti_good, anti_evil, anti_neutral, no_drop, no_remove, no_disarm, indestructible | Handling, alignment, removal, destruction policy. | Restriction flags require requirement/equipment policy. |
| Economy | no_sell, no_rent, no_donate, unique, account_bound, character_bound | Shop/rent/transfer rules. | Must integrate with EconomyService and item ownership. |
| Interaction | container_lockable, readable, activatable, usable, takeable, lootable, harvestable | Command affordances. | Must match object type and command service. |
| Runtime | decay, persistent, corpse_item, quest_item, prototype, admin_only | Persistence and special lifecycle. | Staff-only fields require admin/owner; quest items require quest refs. |
| Custom | namespaced custom tags | Adventurer's Lair custom behavior mapped into Smart MUD profiles. | Warn until consumed by service/script/event reaction. |

## Wear Flags and Wear Locations

Wear flags define where an item may be equipped, not where it is currently equipped. Smart MUD must store named slots such as take/carry, finger, neck, body, head, legs, feet, hands, arms, shield/offhand, about body, waist, wrist, wield/main hand, held, light, ears, eyes, back, face, ankle, and any body-profile-specific slot. Validation must compare the item against the actor body profile and equipment service, reject nonsensical exclusive slots where possible, and warn when a legacy slot has no Smart MUD runtime consumer.

## Type-Specific Values Audit

Each object type must use a specialized editor with named fields, validation, preview, and dependency checks. Smart MUD must not expose raw `value[0..3]` authoring as the primary UI.

| Type | Supported values | Validation and special behavior |
|---|---|---|
| Light | duration, brightness, fuel profile, extinguish behavior. | Timer/fuel non-negative; preview light output. |
| Scroll | spell/ability list, level, charges/consume policy. | Abilities must exist and be castable from item. |
| Wand | ability, level, max/current charges, target policy. | Current charges cannot exceed max; ability target legal. |
| Staff | ability, level, charges, area/room target policy. | Area effects require safe targeting profile. |
| Weapon | weapon family, damage dice, damage type, attack verb, speed, handedness, proficiency tags. | Dice valid; wear slots include wield/held; combat preview required. |
| Fire weapon/projectile | ammo type, range, damage, consume policy. | Ammo dependency valid. |
| Missile/ammo | ammo family, damage modifier, quantity stack. | Compatible launcher profile. |
| Armor | armor value, slot coverage, mitigation types, durability. | Wear slots/body coverage legal. |
| Potion | abilities/effects, level, doses, consume messages. | Effects valid; dose count positive. |
| Food | nutrition, servings, spoilage, freshness, poison flag/effect. | Uses SurvivalNeedsService profiles. |
| Drink container | capacity, current amount, liquid type, poison/effect. | Current <= capacity; liquid exists. |
| Fountain | liquid type, refill policy, capacity, room fixture flag. | Usually not takeable; liquid profile exists. |
| Container | capacity, weight reduction, closeable, lock/key, pick difficulty, corpse flag. | Key object exists; contents limit valid. |
| Note/letter/book/scroll-readable | document profile, text reference, language, pages. | Uses WrittenContentService; text/version valid. |
| Key | key code/lock profile, consumed-on-use flag. | Referenced locks validated. |
| Money/treasure | currency profile, amount, denomination, treasure group. | Currency exists; amount non-negative. |
| Boat/vehicle | allowed terrain, capacity, movement profile. | Movement service dependency. |
| Portal | destination room/id, charges, cooldown, restrictions. | Destination exists; access requirements valid. |
| Furniture | capacity, posture support, healing/rest modifiers. | Posture interactions valid. |
| Trash/junk | no special values beyond decay/value. | Should usually have low/no cost. |
| Instrument/tool/crafting resource | tool profile, profession tags, durability, material. | Crafting/gathering profile exists. |
| Quest/token | quest refs, bind policy, visibility, hand-in behavior. | Quest dependency required. |

## Applies Audit

Applies are ordered stat modifier records. Supported apply types include attributes, HP, mana, move/stamina, armor, hitroll/accuracy, damroll/damage, saving throws, resistances, regeneration, speed, skill/ability bonuses, encumbrance, light, perception, stealth, spell power, healing power, and profession modifiers. Each apply has type, amount, operation, condition, active slot state, stacking group, source label, and optional duration.

Stacking must be explicit: additive by default for plain stat amounts, max/min or exclusive for special named groups, and blocked for duplicate unique effects. Validation must reject unknown apply types, impossible amounts, applies on non-equippable items unless intentionally usable/held, and duplicate exclusive stacking groups. Copy preserves order and source labels while changing object ID provenance.

## Object Permanent Affects

Object permanent affects are effects granted while worn, held, wielded, carried, or used depending on activation policy. They should cover the same canonical affect taxonomy as mobile permanent affects: visibility, perception, protection, haste/slow, movement, conditions, attribute modifiers, resistances, immunities, vulnerabilities, and skill/ability modifiers. Validation must prove the effect exists, has a removal policy, declares stacking, and does not conflict with item type or wear location.

## Extra Descriptions Compared to Rooms

Object extra descriptions should share the completed room extra-description behavior: ordered keyed entries, one or more keywords per entry, rich description text, add/edit/delete/reorder/copy, preview, search, and validation. Missing parity to implement for objects is object-specific lookup through inventory, equipment, room contents, containers, and corpses. Required parity: examining `keyword item` should prefer the object's matching extra description before falling back to the general description, with ambiguity handled by normal parser rules.

## Scripts Audit

OEDIT scripts attach to object templates as script references with trigger type, event bindings, parameters, enabled state, priority, local variables, and dependency metadata. Supported trigger concepts include get, drop, wear, remove, use, consume, read, open, close, lock, unlock, timer, decay, enter container, leave container, give, receive, damage, break, and reset. Smart MUD scripts must integrate with the future unified scripting architecture and may only invoke canonical services.

## Copy, Delete, Search, and Dependencies

Copy duplicates the draft object template, nested values, applies, effects, extra descriptions, scripts, and flags into a new ID/VNUM without duplicating runtime item instances. Delete is staged and dependency-aware. Publish must block deletion while rooms, resets, mobiles, loadouts, loot tables, rewards, shops, quests, scripts, or containers still reference the object unless the builder also stages safe replacements.

Search must support ID, VNUM, keyword, alias, type, flag, wear slot, apply, affect, area, zone, missing dependency, and text in descriptions.

## OEDIT Gap Analysis

| Feature | Adventurer's Lair | Smart MUD today | Gap | Phase | Priority |
|---|---|---|---|---|---|
| OEDIT session workflow | Yes | Partial command placeholders/foundation | Full object session editor | 15D.1 | Critical |
| General fields | Yes | Partial item templates | Canonical object schema | 15D.1 | Critical |
| Extra/wear flags | Yes | Partial | Named catalogs and validation | 15D.1/15D.3 | High |
| Type values | Yes | Missing specialized parity | Per-type editors | 15D.2 | Critical |
| Applies | Yes | Partial stat/effect services | Ordered apply editor | 15D.3 | High |
| Permanent affects | Yes | Partial effect services | Object effect authoring | 15D.4 | High |
| Extra descriptions | Yes | Rooms implemented | Object integration with parser | 15D.5 | High |
| Scripts | Yes | Future | Script refs/dry validation | 15D.6 | Medium |
| Copy/delete/deps | Yes | Partial | Dependency graph and staged delete | 15D.7 | High |
| Publish/runtime item behavior | Limited legacy save | Smart MUD generation pipeline exists | Include all object fields in generation | 15D.7 | Critical |

## Recommended OEDIT Implementation Phases

- 15D.1: OEDIT Core: schema, commands, lookup, ownership, sessions, general fields, flags shell.
- 15D.2: Type Values: specialized editors for every object type with preview and validation.
- 15D.3: Applies and wear validation: stat modifier authoring and stacking policy.
- 15D.4: Permanent Affects: object effect references, activation/removal policy.
- 15D.5: Object Extra Descriptions: shared editor, parser/runtime integration, search.
- 15D.6: Scripts: unified script references and trigger validation.
- 15D.7: Copy/Delete/Validation/Publish hardening: dependency graph, deletion workflow, object publish and runtime projection tests.

## Future Smart MUD Extensions After Parity

After parity, add item archetype templates, equipment sets, material/quality profiles, random affix packages, crafting blueprints, loot profiles, visual skins, attunement rules, bind-on-policy profiles, repair/enchantment profiles, provenance histories, collection sets, and smart container profiles. These enhancements belong after 15D.7 and should be profile-driven rather than duplicated on individual item templates.
