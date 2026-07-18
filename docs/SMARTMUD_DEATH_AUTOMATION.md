# Death Automation (Phase 20B)

The reward stage calls canonical adapters in strict order: `auto_split`, `auto_gold`, `auto_loot`, then `auto_sacrifice`. Each completion is ledger-keyed by death and corpse. Split consumes only corpse currency (never direct NPC gold), gold takes remaining corpse currency, loot uses canonical carrying/ownership validation and leaves failures in place, and sacrifice is for NPC corpses only after currency and loot processing.

Quest, autoquest, and campaign adapters receive the death ID and full kill context. Credit eligibility is same room **or same zone** from the frozen group snapshot, deliberately wider than XP. Post-kill hooks are adapter/EventBus extension points for objectives, passives, AI, achievements, and analytics.
