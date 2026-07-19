# Ability Implementation Roadmap

## Non-goal

This roadmap authorizes **inventory and prerequisite work only**. It does not authorize implementing Fireball, Bash, Backstab, Heal, Sanctuary, Meteor Swarm, summons, or Overlord abilities in this phase.

## Phase 0 — unblock the audit (required)

1. Obtain a pinned customized Adventurer’s Lair source checkout and capture its SHA.
2. Produce machine-checkable manifests for spell/skill registrations, command abilities, specials, custom modules, builder definitions, object activation, DG triggers, and quests.
3. Expand each dynamic family in the matrix to concrete rows and mark every unverified field `UNKNOWN` until traced.

**Exit gate:** G1 in the dependency graph. Without it, do not claim source-complete gameplay parity.

## Recommended implementation waves

| Wave | Scope | Dependency gate | Planned slices | Complexity risk |
|---|---|---|---|---|
| 1 | Metadata normalization, aliases, class/level/cost/wait/target contracts | G1, G2 | Utility metadata; all existing definitions | Small–Medium |
| 2 | Healing, cures, resource restoration, death-state legality | G2 | One heal/cure family per slice | Medium |
| 3 | Affect foundations: buff/debuff/detection/cleanse/dispel | G3 | One effect policy/family per slice | Medium–Large |
| 4 | Direct damage and weapon techniques | G2/G3 | One damage/save/weapon family per slice | Medium–Large |
| 5 | Area damage and group support | G2/G3 | Target fan-out then one spell family | Large |
| 6 | Movement, survival, crafting, object activation | G2 + item/room runtime | One interaction family per slice | Medium |
| 7 | Passives, stances, transformations, auras | G3/G4 | Trigger safety before individual passives | Large–Very Large |
| 8 | Summoning, pets, necromancy, corpse interaction | G3/G4 + death/corpse policy | Ownership/expiry then one summon family | Very Large |
| 9 | NPC-only attacks and monster specials | G4 | Adapter then one special family | Large–Very Large |
| 10 | Scripted, quest, builder-created, custom shadow/Overlord abilities | G4/G5 | Sandbox/validation then isolated capability | Very Large |
| 11 | Administrative abilities and final migration verification | G5 | Authorization/audit and row-by-row acceptance | Medium–Large |

## Highest-complexity currently known candidates

The following are planning candidates, not assertions about the complete hidden legacy catalog: Meteor Swarm (source discovery required), Fireball, Heal, Sanctuary, Raise Skeleton, pet control, summons, necromancy/corpse consumption, auras, transformations, Overlord abilities, shadow abilities, area/group spells, dispel magic, poison/DOT, charm/follower control, backstab, bash, monster specials, and DG/scripted quest invocation. The first five named spell/skill candidates remain explicitly unimplemented in this phase.

## Expected future phase count

After source manifest completion, plan **18–30 bounded implementation phases**: 1 audit-unblock phase, 10–18 family/runtime phases (split further when a family has distinct saves, targeting, persistence, or AI semantics), 4–6 monster/script/custom phases, and 3–5 row-by-row verification/remediation phases. Revise this estimate only after concrete legacy row count and complexity distribution are measured.

## Roadmap update policy

* Add a concrete matrix row before implementing any ability.
* Link every implementation PR to its row(s), prerequisite gate, tests, and status transition.
* A status transition to `IMPLEMENTED` requires a player path plus applicable NPC/script/builder/persistence/death tests.
* Preserve intentional architectural differences; do not port C globals, tables, bitvectors, formats, or special-procedure implementation patterns.

## Phase 21B — Canonical Ability Runtime

Phase 21B adds the typed `AbilityRuntimeService` request/result boundary and
routes command ability execution through it.  The next bounded implementation
phase is **Phase 21C — Core Physical Combat Commands** (flee, assist, rescue,
kick, bash), using this runtime rather than a new combat-skill pipeline.

### Phase 21B completion update

Common request orchestration is now explicit in `AbilityRuntimeService`; no
Phase 21C physical-command work is included in this update.

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

### Phase 21B12 verification

Completed focused verification for compact SKILLS presentation, canonical generic
NPC target resolution (including Forest Wolf and stable ordinals), targetability
catalog validation, safe missing targets, idempotent corpse creation, absolute
random 180--300 second NPC expiry, legacy migration, and SQLite restart expiry
persistence.  No Phase 21C work is included.  Browser/Telnet semantic parity is
covered by the existing production transport acceptance tests; manual server
observation remains a documented limitation.
