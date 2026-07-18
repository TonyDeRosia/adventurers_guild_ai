# Phase 20B Acceptance Transcript

## Solo NPC
`death.reward.calculated` records table XP plus authored bonus; `death.rare_bonus.granted` records the frozen live-count bonus; `death.alignment.changed` records before/after; `death.glory.granted` records the deterministic roll. Phase 20A's direct gold, corpse, loot, and extraction events remain single-occurrence foundation work.

## Follower and group
Attribution follows the immediate follower to its player owner. The death ledger has one XP/glory award per recipient/type. Same-room members receive separately computed XP; same-zone remote members receive quest credit only; other-zone members receive neither.

## Player death and restart
The penalty event records TNL, percentage, and capped loss. Phase 20A has already dropped the 10% gold/corpse state. The respawn event records temple room; resulting player state is connected, HP at least one, RESTING, equipped, and no longer in old combat. Recalling `process_rewards` returns the stored completed ledger result: no XP, Glory, bounty, credit, automation, respawn, or corpse repeats.

## Limits
This phase intentionally does not implement combat commands, physical skills, spell damage, or resurrection. Phase 21 should implement flee, assist, rescue, kick, bash, backstab, bandage, whirlwind, and other physical abilities through Ability Runtime → Target Resolution → Resource/Wait Validation → DamageService → DeathRuntimeService.
