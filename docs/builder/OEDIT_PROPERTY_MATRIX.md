# OEDIT Property Matrix — Phase 15B.38

Network access to clone the customized TBA reference was blocked in this environment (`CONNECT tunnel failed, response 403`), so the TBA column is audited from established Circle/TBA OLC behavior and marked as behavioral reference, not copied source.

| Property | Runtime | TBA | Future | Builder Status | Validation | Example | Notes |
|---|---|---|---|---|---|---|---|
| id | canonical item template key | vnum | stable package id | exposed | required | `iron_sword` | canonical ID, not numeric-only |
| name | supported | aliases/name list | required | exposed | required | `Iron Sword` | display label |
| keywords | supported in commands/search | namelist | required | exposed | duplicate warning | `iron,sword` | comma list |
| short_description | partial | short desc | required | exposed | optional fallback | `an iron sword` | inventory line |
| long_description | supported | room desc | required | exposed | fallback | `An iron sword lies here.` | ground display |
| look_description | partial | action desc/extra desc | required | exposed | fallback | `The blade is nicked.` | examine text |
| extra_descriptions | new canonical list | extra desc menu | required | exposed | list | `blade:...` | structured future UI |
| item_type | supported | item type | required | exposed | required | `weapon` | drives warnings |
| subtype | new canonical text | type-specific values | planned | exposed | text | `longsword` | no separate schema |
| category | partial | n/a | planned | exposed | text | `equipment` | grouping/filtering |
| material | partial | material extension | crafting | exposed | text | `iron` | used by crafting/repair |
| quality | partial via crafting docs | n/a | equipment progression | exposed | text | `standard` | quality profile id later |
| rarity | display colors exist | custom flags | loot/economy | exposed | text | `common` | stable enum later |
| ownership | instance owner exists | take flags | housing/banks/mail | exposed | text | `player` | template policy |
| binding | new policy | n/a | soulbound/accountbound | exposed | text | `none` | policy only |
| weight | runtime inventory/carry | weight | required | exposed | non-negative | `5` | integer units |
| cost | economy/shop | cost | required | exposed | non-negative | `25` | base coin value |
| stack_size | instance stack_count | n/a | stacking | exposed | non-negative | `20` | max template stack |
| destroy_timer | corpses/decay related | timer | decay | exposed | non-negative | `60` | seconds/minutes per system |
| wear_flags | equipment slots | wear flags | equipment | exposed | list | `wield,held` | slot policy |
| extra_flags | custom flags | extra flags | scripts/visibility | exposed | list | `glow,magic` | no bitvectors |
| slot_restrictions | new | wear flags/body | equipment progression | exposed | list | `mainhand` | complements wear flags |
| weapon_type | combat profile | weapon value | combat | exposed | text | `sword` | profile id later |
| attack_type | attack messages | attack type | combat | exposed | text | `slash` | maps to damage family |
| damage_dice | combat natural/profile | value dice | combat | exposed | weapon warning | `1d8` | warning if missing |
| speed | combat planned | value | combat | exposed | non-negative | `3` | initiative/cooldown hook |
| range | combat planned | value | ranged combat | exposed | non-negative | `1` | tiles/rooms policy later |
| armor_values | partial score/equipment | armor value | defense | exposed | text/json | `ac:2` | future structured map |
| resistances | display supports | affects | defense | exposed | list | `fire:5` | future structured map |
| capacity | container planned | container val | inventory | exposed | non-negative, warning | `10` | container warning if zero |
| weight_capacity | new | container val | inventory | exposed | non-negative | `100` | carry capacity |
| container_flags | new | container flags | inventory | exposed | list | `closeable,locked` | no bitvectors |
| open/closed/locked | new | container state | housing/banks | exposed | boolean | `true` | template default state |
| lock_difficulty | new | pickproof/lock | security | exposed | non-negative | `12` | skill DC |
| key_id | new | key vnum | doors/containers | exposed | locked warning | `brass_key` | dependency checked in future |
| transparent | new | container flag | display | exposed | boolean | `false` | see contents |
| spell_storage | abilities integration | scroll/wand values | magic | exposed | list | `heal` | ability ids |
| charges | abilities runtime | wand/staff value | magic | exposed | non-negative | `3` | instance can override |
| recharge | new | n/a | magic | exposed | non-negative | `60` | runtime hook |
| passive_effects | effects runtime | affects | magic/equipment | exposed | list | `warmth` | effect refs |
| affects | display/effects | affect slots | stats | exposed | list | `str:+1` | future structured map |
| scripts | ability/scripts refs | DG scripts | AI/quests | exposed | list/search | `on_use_unlock` | dependency analysis scans |
| fuel/burn_time/brightness | light docs | light values | survival/vision | exposed | non-negative | `120` | light subsystem hook |
| nutrition | survival docs | food value | hunger | exposed | non-negative | `10` | consumable integration |
| poison | survival/combat planned | poison flag | food/drink | exposed | boolean | `false` | immediate validation |
| decay | food preservation docs | timer | survival | exposed | non-negative | `1440` | freshness hook |
| liquid_type | survival/drink planned | drink type | thirst | exposed | text | `water` | profile id later |
| servings | portions docs | drink amount | thirst/cooking | exposed | non-negative | `4` | instance can decrement |
| ingredients | crafting docs | n/a | crafting | exposed | list | `iron_ingot` | recipe refs |
| resource_tags | gathering docs | n/a | harvesting | exposed | list | `metal` | search field |
| recipes | crafting docs | n/a | crafting | exposed | list | `forge_sword` | dependency scan |
| gathering | gathering docs | n/a | resource tools | exposed | list | `mining_tool` | tool profile refs |
| builder_notes | builder metadata | n/a | workflow | exposed/search | text | `Needs balance` | never player-facing |
| validation | service output | n/a | publishing | exposed | generated | warnings/errors | not persisted as authority |
| preview | service output | n/a | UX | exposed | generated | look/inv/shop | not persisted |
| dependencies | scan output | n/a | publication safety | exposed | generated | rooms/resets | not persisted |

## Runtime audit summary
Smart MUD had canonical draft collections, item instances, item templates, inventory/equipment display, gathering, crafting, survival, rewards, zone resets, and ability item operations. Before this phase, object editing was a generic `ocreate/oset/odesc` path with no complete capability contract, no grouped menu, minimal validation, and no object-specific preview/dependency workflow.

## Customized TBA audit summary
The behavioral reference exposes identity strings, item type, extra/wear flags, type-specific values for weapons, armor, containers, drink containers, fountains, food, light, keys, portals, affects, extra descriptions, scripts, cost, rent/timer, and weight. Smart MUD now models these as named canonical fields instead of TBA bitvectors/value slots.

## Future Smart MUD capability summary
Future systems require stable template fields for crafting, gathering, ownership, binding, rarity, quality, durability/condition hooks, stack policy, housing/banks/mail transfer policy, auction/shop presentation, pets/AI scripted use, quest references, equipment progression, survival consumables, light/vision, and publication dependency safety.

## Intentionally unsupported
TBA numeric bitvectors and raw value slots are intentionally unsupported as persistence authority. They are represented as named lists or named canonical fields so world packages remain readable and extensible.
