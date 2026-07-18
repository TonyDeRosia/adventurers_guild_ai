# Phase 19A acceptance

The deterministic tests in `tests/test_phase19a_physical_combat.py` cover
profile validation, canonical identity, HP-to-position boundaries, hit clamps,
weapon damage/HP mutation, misses, automatic sleeping-target hits, and armor.

Implemented limitations: no Phase 19B heartbeat changes, scheduled NPC
retaliation, spell damage, corpse/reward processing, or multi-target switching.
The result objects and injected persistence/event boundaries are intentionally
shared-service ready for those later additions.
