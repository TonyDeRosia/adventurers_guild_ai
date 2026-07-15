# Phase 14A Adventurer's Lair Behavioral Ability Catalog

This catalog captures non-code behavior categories found in the Adventurer's Lair/tbaMUD magic model and maps them to Smart MUD representative Phase 14A definitions. Formula constants and implementation code are intentionally omitted.

| Name/family | Category | Target type | Hostile/helpful | Resource behavior | Cast/cooldown behavior | Damage/healing behavior | Saving throw | Affects/duration | Stacking/exclusivity | Materials | Messages/restrictions | Smart MUD representative |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Direct elemental bolt/blast | Damage spell | Single enemy | Hostile | Mana in AL; authored cost in Smart MUD | Cast command, optional cooldown | Typed magical damage through combat runtime | Magic save can reduce/negate when authored | Instant | N/A | Optional reagent | Hit/fail messages | `phase14a_fire_bolt` |
| Cure/Heal | Healing spell | Self/ally | Helpful | Mana/authored | Instant or cast | Restores HP; no normal resurrection | None | Instant | N/A | Optional holy reagent | Heal messages | `phase14a_lesser_heal` |
| Bless/stat buff | Buff | Self/ally/group | Helpful | Mana/authored | Instant/cast, cooldown | No direct damage | None | Timed stat/save modifier | Refresh/unique | Optional | Wear-off message | `phase14a_bless` |
| Blindness | Control debuff | Enemy | Hostile | Mana/authored | Cast/cooldown | No direct damage | Magic save negate | Blind/control condition | Unique by control tag | Optional | Sight returns on wear-off | `phase14a_blindness` |
| Poison | Debuff/DOT | Enemy | Hostile | Mana or natural attack | Instant/cast | Periodic poison damage, kill attribution through combat | Physical/magic save | Poison affect with ticks | Major poison exclusive | Optional venom/reagent | Poison fade message | `phase14a_poison` |
| Regeneration | HOT | Self/ally | Helpful | Mana/authored | Cast/cooldown | Periodic healing/resource restoration | None | Timed HOT | Refresh/unique | Optional | Regen fades | `phase14a_regeneration` |
| Cure poison/disease/blind | Cure | Self/ally | Helpful | Mana/authored | Instant/cast | Removes harmful categories | Optional | Removes effects by tag/category | Stack reduction/removal | Optional | Cure success/fail | `phase14a_cure_poison` |
| Dispel magic | Dispel | Actor/effect | Mixed | Mana/authored | Cast/cooldown | Removes dispellable effects | Magic save/resist when authored | Removes by tag/school/category | Selection policy | Optional | Dispel/protected messages | `phase14a_dispel_magic` |
| Sanctuary/protective ward | Defensive | Self/ally | Helpful | Mana/authored | Cast/cooldown | Grants resistance/protection | None | Timed protective effect | Exclusive protective ward group | Optional | Ward wear-off | `phase14a_stone_ward`, `phase14a_flame_ward` |
| Recall | Movement/utility | Self/location | Helpful | Mana/authored | Cannot use in restricted rooms/combat | Teleports to recall destination | None | Instant movement | N/A | Optional | Depart/arrival text | existing `recall` via `recall`/`teleport` op |
| Reagent spell | Any | Varies | Varies | Requires item instances | No cost on target failure | Varies | Varies | Varies | Varies | Atomic item consumption | Denial if missing reagent | `phase14a_ruby_flare` |
