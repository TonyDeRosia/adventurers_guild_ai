# Ability Implementation Status

## Snapshot

This is a status ledger for the `73` currently authored Smart MUD definitions, not a claim that the inaccessible customized legacy source has no additional abilities.

| Status | Count | Meaning in this audit |
|---|---:|---|
| IMPLEMENTED | 1 | Canonical runtime path exists (source-specific legacy values still need audit). |
| PARTIALLY_IMPLEMENTED | 67 | Metadata/foundation exists; full gameplay semantics or legacy evidence is incomplete. |
| NOT_STARTED | 5 | Definition/passive catalog entry exists without an executable passive runtime. |
| INTENTIONALLY_REMOVED | 0 | No removal is asserted without a legacy source decision. |
| BLOCKED_BY_DEPENDENCY | 5 | Dynamic family rows in the parity matrix await a prerequisite. |
| UNKNOWN | 2 | Dynamic/custom legacy family source details are unavailable. |

## Definition-type counts

| Type | Count |
|---|---:|
| defensive | 1 |
| heal | 1 |
| natural | 2 |
| passive | 5 |
| skill | 15 |
| spell | 46 |
| technique | 2 |
| utility | 1 |

## Status evidence and rules

* A listed ability is **not** upgraded to `IMPLEMENTED` merely because a JSON definition, command name, or generic operation exists.
* The only currently marked `IMPLEMENTED` row is `basic_attack`; it is bounded to its current Smart MUD path. Formula and customized-Adventurer’s-Lair parity remains unverified.
* Current spells, skills, techniques, natural attacks, and prototypes are `PARTIALLY_IMPLEMENTED` unless the runtime and tests prove their complete behavior. This deliberately avoids claiming Fireball, Bash, Backstab, Heal, Sanctuary, summons, Meteor Swarm, or Overlord abilities are complete.
* Passive definitions are `NOT_STARTED` until event subscription, claim/depth safety, execution, cleanup, and tests are all present.
* The legacy-only/dynamic rows in `ABILITY_PARITY_MATRIX.md` have exactly one status each. They must be split into concrete abilities on a pinned source audit; no estimate may silently convert them into parity.

## Comparison checklist for each concrete legacy row

When G1 source access is restored, record each item below as **already exists**, **needs metadata only**, **needs effect implementation**, **needs runtime support**, **needs UI support**, **needs Builder support**, **needs persistence**, **needs AI support**, **needs scripting support**, and/or **needs testing**:

1. Registration/name/aliases/internal constant and class/level/practice metadata.
2. Costs (HP/mana/move/material), cooldown/wait, targets, position/equipment/weapon/combat/room/zone/world restrictions.
3. Success, damage/heal, save/resist, effects/duration/stacks/exclusivity, created objects/summons, death/corpse behavior, and messages.
4. Player, NPC, pet, monster-special, builder, administrative, and script/quest callers.
5. Durable state, expiry/restart/death/logout cleanup, display/UI, audit events, and automated coverage.

## Final audit report

| Measure | Count | Interpretation |
|---|---:|---|
| Current authored definitions | 73 | Measured JSON rows; this is the only complete count available in this checkout. |
| Spells | 46 | Current authored definitions whose type is `spell`. |
| Skills | 15 | Current authored definitions whose type is `skill`. |
| Passive abilities | 5 | Current authored definitions whose type is `passive`. |
| Commands functioning as abilities | 1 dynamic family | Concrete legacy command count is `UNKNOWN` pending source command-table extraction. |
| Monster specials | 2 authored natural/monster definitions + 1 dynamic family | Concrete customized special count is `UNKNOWN`. |
| Custom/Overlord/shadow/quest/script ability families | 5 dynamic families | Concrete customized ability count is `UNKNOWN`. |
| Implemented | 1 | Current authored definitions only. |
| Partial | 67 | Current authored definitions only. |
| Missing/not started | 5 | Current passive definitions only. |
| Legacy total | UNKNOWN | Cannot be measured honestly without the requested source. |

### Top twenty highest-complexity candidates

| Rank | Ability/family | Complexity | Why |
|---:|---|---|---|
| 1 | Meteor Swarm | Very Large | Source discovery, area targeting, damage attribution, saves, room safety. |
| 2 | Fireball | Large | Area/direct damage semantics and saving throws. |
| 3 | Heal | Large | Healing, caps, death-state legality, class metadata. |
| 4 | Sanctuary | Large | Protective stacking, damage mitigation, wear-off. |
| 5 | Raise Skeleton | Very Large | Corpse interaction, summon ownership, expiry, death cleanup. |
| 6 | Pet control | Very Large | Follower commands, permissions, AI, persistence. |
| 7 | Summons | Very Large | Actor lifecycle, attribution, expiry/logout/death cleanup. |
| 8 | Necromancy/corpse consumption | Very Large | Corpse ownership, object mutations, death policy. |
| 9 | Auras | Large | Membership reconciliation, stacking, room movement, cleanup. |
| 10 | Transformations | Large | Body/equipment projection and restoration. |
| 11 | Overlord abilities | Very Large | Customized source discovery and multi-runtime effects. |
| 12 | Shadow abilities | Very Large | Customized source discovery and stealth/effect interactions. |
| 13 | Area/group spells | Large | Fan-out, friendly-fire, attribution, saves. |
| 14 | Dispel Magic | Large | Effect selection, protection/resistance, stack policy. |
| 15 | Poison/DOT | Large | Tick claims, cure/dispel, death attribution. |
| 16 | Charm/follower control | Very Large | Control authority, AI, logout/death behavior. |
| 17 | Backstab | Large | Weapon/position/stealth opening-combat rules. |
| 18 | Bash | Large | Weapon/position, knockdown/control, wait state. |
| 19 | Monster specials | Very Large | Custom special registry and NPC execution adapter. |
| 20 | DG/scripted quest invocation | Very Large | Sandbox, trigger recursion, persistence, authorization. |

## Phase 21B status

The runtime foundation is production-wired for existing authored ability
execution.  Magic Missile, Armor, Detect Magic, Strength, Build Campfire and
Set Camp retain their existing production handlers through the shared registry
and execution service.  This does **not** claim implementation of the remaining
authored definitions or complete customized legacy parity.

### Phase 21B orchestration status

The six shipped abilities are **PRODUCTION_WIRED** through the request runtime.
The former instant executor is **PARTIALLY_WIRED** solely as a compatibility
adapter for older direct callers.

> **Phase 21B.3 status (2026-07-18):** Magic Missile structured damage receipts now preserve
> request/source/target/HP linkage and durable duplicate references.  Terminal death linkage is
> injectable but is not wired through normal `MudRuntime`; transport terminal acceptance remains
> unproven, so Phase 21C is not unblocked.

### Phase 21B.6 replay acceptance update

Transport-neutral request identity now reaches the canonical ability request
through both production adapters.  Durable duplicate receipts retain original
damage/death references, and prompt projections refresh canonical paid
resources before rendering.  See `ABILITY_PHASE_21B_FINAL_ACCEPTANCE.md`.


## Phase 21B closure update

Phase 21B remains **IN PROGRESS** and Phase 21C remains **NOT UNBLOCKED** until the required focused and full-suite terminal results are captured.  The current evidence matrix and scope limitation are recorded in [ABILITY_PHASE_21B_CLOSURE.md](ABILITY_PHASE_21B_CLOSURE.md).
