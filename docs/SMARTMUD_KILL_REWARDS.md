# SmartMUD Kill Rewards (Phase 20B)

`DeathRuntimeService.process_rewards` extends, rather than repeats, the claimed Phase 20A foundation transaction. It freezes the supplied group and rare-live snapshots, credits quests, calculates rewards, applies them through `CharacterXPService`, performs disposition, then marks the ledger `REWARDS_COMPLETED`.

## Experience

NPC base XP by `victim level - recipient level` is: `<=-15: 1`, `-14..-10: 3`, `-9..-8: 5`, `-7..-5: 15`, `-4..-3: 40`, `-2: 60`, `-1: 90`, `0: 120`, `1: 150`, `2: 180`, `3: 220`, `4: 260`, `5: 300`, and `>=6: 350`. Authored bonus XP is additive and the result is clamped to the configured positive cap.

Group NPC XP is **same-room only**, is not divided, and is separately computed from every recipient's level. Player-victim XP is same-room only: total is `trunc(victim_exp / 3) + members - 1`, capped at `trunc(max_exp_loss * 2 / 3)`, with every member receiving `max(1, trunc(total / members))`.

For NPCs, a frozen live-definition count from 1 through 10 adds `max(1, trunc(normal_xp / 4))`; 11+ adds none. The XP service applies the global multiplier exactly once, owns persistence/caps/level advancement, and prevents XP below zero.

## Alignment, Glory, and bounty

Every XP recipient gets `alignment + trunc((-victim_alignment - alignment) / 16)`. Only the credited player killer gets primary Glory. PvE rolls 15–25 and, beyond a three-level difference, uses `trunc(base * max(0, 8-difference) / 5)`. PvP rolls 800–1200 and uses `trunc(base * max(0, 10-difference) / 7)`. PvP Glory is zero for the same stable victim ID within 600 seconds.

A player bounty is atomically cleared and paid to a distinct, non-immortal credited player killer only. It cannot pay an NPC, self-kill, immortal, corpse, or retry.
