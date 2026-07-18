# Player Death and Respawn (Phase 20B)

Non-immortal player deaths calculate TNL as `max(0, next-level threshold - current XP)`. The percentage is 1% at level 1, follows the specified quadratic curve to 10% at the highest mortal level, and loss is `trunc((tnl * percentage + 99) / 100)`, capped by max loss. The XP service applies it once and never allows negative XP.

After Phase 20A corpse state and the penalty commit, the respawn adapter stops combat, moves the connected player to the configured temple, clears targets/wait state, makes HP at least 1, sets `RESTING`, and starts a new living generation. Equipment, remaining gold, diamonds, Glory, bank funds, class, skills, spells, and session are preserved; corpse-transferred inventory is not returned. Criminal-flag clearing is an adapter hook so the existing PvP state remains authoritative.
