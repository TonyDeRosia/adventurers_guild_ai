# Phase 5C Part 1 Actor Architecture

Phase 5C establishes Smart MUD's permanent `Actor` data model before combat exists. The goal is architectural: players, NPCs, mobs, bosses, pets, merchants, guards, summons, and peaceful civilians all share one extensible data shape. Behavior will later decide whether an Actor fights, flees, trades, follows, or talks; separate combat-capable entity systems must not be introduced.

## Adventurer's Lair usability baseline

The existing Smart MUD command/display audit and command parity documents identify classic MUD display expectations for `score`, `worth`, `affects`, equipment, identify/examination, Builder diagnostics, and administrative inspection. Phase 5C preserves that usability by making the score sheet a readable, sectioned, classic MUD block with clear labels, separators, resources, attributes, combat placeholders, equipment, affects, resistances, currencies, and diagnostics. The implementation is new Python architecture rather than copied C data structures.

## Actor ownership

`engine/actors.py` defines the core ownership model. Every Actor permanently owns:

- Identity
- Resources
- Primary attributes, including Builder-defined extras
- Combat profile
- Equipment profile
- Resistance profile
- Condition profile
- Relationship profile
- Need, goal, memory, and simulation profiles
- Progression profile
- Effect container
- Derived statistics cache
- Builder metadata
- Plugin data

The default peaceful profile is still combat-capable data: aggression `never`, attack `none`, flee `immediate`, and combat profile `Civilian`. This keeps future combat from needing a separate NPC/player/mob schema.

## Derived statistics and formulas

Derived combat values are represented only as placeholders in `DerivedStatistic` records. The cache stores the key, display label, future formula name, optional value, and placeholder status. It does not calculate attack rating, defense rating, armor, critical chance, healing power, carry capacity, initiative, or any other derived value.

`FormulaRegistry` is a named registry framework for future Builder-overridable formulas. It can register names such as `attack_rating`, `armor`, `mana_regeneration`, `movement_regeneration`, and custom Builder formulas without embedding combat math in Python. Phase 5C intentionally stops at registration metadata.

## Score renderer

`engine/score_renderer.py` contains the single modular `ActorScoreRenderer`. Every section is independently renderable through `render_section`, and the full `score` command is composed from those same section renderers. This prevents duplicate render paths.

Implemented sections are:

- Identity
- Resources
- Primary Attributes
- Derived Attributes
- Combat
- Equipment
- Conditions
- Affects
- Resistances
- Progression
- Currencies
- Relationships
- Simulation
- Builder Diagnostics
- AI Diagnostics

Builder and AI diagnostics are admin/Builder-only sections. Normal players receive a restricted-section message.

## Runtime bridge and persistence

`MudCharacter` now has an `actor_data` JSON dictionary so SQLite character persistence can store the permanent Actor model without replacing existing runtime fields in one risky migration. `actor_from_runtime_character` bridges legacy runtime character values into an Actor view for score rendering and keeps HP, mana, stamina, XP, gold, role metadata, equipment, and affects visible through the new architecture.

## Builder diagnostics

Builder diagnostics expose architecture, not editing workflows. The diagnostic section shows Actor id/type, base values, derived placeholder keys, formula registration status, metadata, and validation warnings such as missing base attributes. Full field editing remains future work.

## Why this exists before combat

Combat, AI, skills, spells, equipment bonuses, classes, races, factions, quests, and behavior trees will all depend on the same living-entity foundation. Building the Actor model first prevents later systems from hardcoding player-only stats, NPC-only combat data, or derived values that cannot be overridden by Builders.


## Phase 6E Progression Integration

Canonical progression is now represented by `engine.progression.ProgressionService`, SQLite `actor_progression_state`, XP/currency/grant history tables, and world package collections for species, races, classes, tracks, professions, curves, progression profiles, and growth profiles. Quest, loot, trainer, crafting, faction, and final balance systems remain separate and must award progression only through canonical APIs.

## Phase 7B Economy Integration

Phase 7B adds the canonical `engine.economy.EconomyService` for SQLite-authoritative carried balances, immutable ledger entries, price quotes, transactions, shop stock, buyback records, identify/repair service payments, bank accounts, and currency conversion. Economy world data is authored in the dedicated currency, shop, stock, policy, pricing, service, repair, bank, restock, message, and eligibility collections. Reward, item, progression, Actor, command, package, Builder, and roadmap systems integrate by calling EconomyService APIs rather than directly mutating money, stock, item ownership, bank records, or service state. Crafting, trainers, quests, auctions, player trading, and autonomous AI economics remain explicitly deferred.

## Phase 8B Organization Integration

Phase 8B adds the canonical `OrganizationService` for parties, guilds, clans, NPC organizations, roles, permissions, invitations, applications, shared quest context, group combat attribution, and organization audit history. These systems provide context only and call existing canonical services for combat, quests, rewards, economy, progression, crafting, and world state.
