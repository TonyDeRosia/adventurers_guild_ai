# Ability Dependency Graph

## Purpose

This graph orders future work by runtime prerequisites rather than by individual spell popularity. It intentionally contains no ability implementation.

```text
World/content definitions + learned ability projection
  └─ Canonical ability gateway (parse → known check → validate → cost → execute)
      ├─ Targeting / posture / room legality
      ├─ Resource, cooldown, wait-state authority
      ├─ Combat action and damage authority
      │   ├─ saving throws / resistance / immunity
      │   ├─ direct damage techniques and weapon skills
      │   └─ area damage / chained targets / attribution
      ├─ Healing and resource restoration authority
      ├─ Affect runtime (apply/remove/expire/tick/stack/exclusive)
      │   ├─ buffs, debuffs, cures, dispels, detection
      │   ├─ crowd control and movement flags
      │   ├─ auras / room effects
      │   └─ transformations / stances / passives
      ├─ Item activation and object creation/alteration
      ├─ Summon / follower / pet-control authority
      ├─ NPC AI ability selection and monster-special adapter
      ├─ Script/quest invocation with trigger claims and recursion bounds
      ├─ Builder validation/publish/loadout support
      └─ Persistence, death/logout cleanup, messages, observability, tests
```

## Ability-family edges

| Family | Direct prerequisites | Downstream blockers / notes |
|---|---|---|
| Utility and detection | gateway; targeting; resource/cooldown; room legality | item/room variants also need item runtime. |
| Healing and cures | gateway; healing; affect removal; death-state policy | Healing must not resurrect except an explicitly authored resurrection flow. |
| Buffs/debuffs/control | affect runtime; saving/resistance; duration/wear-off | Requires exclusive groups and action restrictions before full parity. |
| Direct damage / weapon skills | combat damage; save/resistance; wait; weapon/equipment validation | Depends on Phase 19 combat runtime already present, but formulas remain source-audit work. |
| Area damage | multi-target/room resolution; combat attribution; room safeguards | Must follow direct damage and canonical target fan-out. |
| Passives/reactives | trigger claims; combat events; recursion/depth bounds | Do not make passives direct command handlers. |
| Summons/pets/necromancy | summon ownership; expiry/death/logout; follower AI | Also needs corpse policy for corpse-consuming abilities. |
| Auras/forms/overlord | affect + room/aura membership + transformation projection | Needs explicit stacking, cleanup, and UI visibility. |
| Monster specials | NPC action selection; special adapter; combat/affect/item services | Source enumeration is blocked. |
| Builder/script/quest abilities | validation; canonical gateway; sandbox/trigger claims; persistence | Never execute arbitrary builder/script mutations outside the gateway. |
| Administrative abilities | authorization; live actor/world mutation policy; audit log | Separate from gameplay balancing. |

## Dependency acceptance gates

* **G1 — Source manifest:** pinned legacy SHA, concrete registration/command/special/trigger list, aliases, and custom modules. This is presently blocked by unavailable source access.
* **G2 — Canonical action:** costs, wait, target, position, equipment, messages, and test trace are observable for one action request.
* **G3 — Effect correctness:** durations, stack/exclusive rules, saves, cleanup on death/logout, and persistence recovery are tested.
* **G4 — Actor parity:** player, NPC, summon, script, and builder callers reach the same validated action path where applicable.
* **G5 — Content parity:** every concrete legacy row has migrated metadata and a status supported by automated tests.

## Phase 21B runtime boundary

`AbilityCommandRouter` (currently the command-engine ability route) constructs
`AbilityExecutionRequest` and calls `AbilityRuntimeService`; the runtime
delegates definition, target, cost, proficiency, cooldown, effect and
Damage/Death dependencies to `AbilityExecutionService`.  This is the required
edge for Phase 21C physical-skill migrations.
