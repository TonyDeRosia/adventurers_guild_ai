# Corpse runtime

Corpses are canonical `entity_instances` of type `corpse`, are open containers,
and use normal item ownership (`owner_type=corpse`). Their room display is “The
corpse of `<name>` is lying here.” Existing decay processing spills contents
into the death room exactly once before destroying the corpse.

Phase 20A adapters create corpse metadata including source actor/template,
source level/life generation, typed shadow-extraction metadata (`attempts=3`),
and corpse policy flags (non-donatable, non-closeable, no ordinary storage).
Configured defaults are five object ticks for NPC corpses and ten for player
corpses. Player transfers exclude equipped items and drop truncation-toward-zero
of one tenth of carried gold; diamonds, Glory, bank gold, and bounty remain.
NPCs transfer carried and equipped instance identities before extraction.
