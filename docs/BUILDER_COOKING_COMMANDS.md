# Builder Cooking Commands

Phase 11E implements canonical cooking as a CraftingService specialization. Recipes remain `recipe_definitions`; ingredient reservations remain exact `crafting_input_reservations`; outputs are canonical item instances. SurvivalNeedsService remains authoritative for eating, drinking, portions, serving depletion, need changes, and freshness interpretation.

Starter content includes roasted river fish, cooked small meat, wild mushroom stew, simple herbal tea, and dried fish; data-driven profiles cover ingredients, substitutions, serving yields, consumable outputs, nutrition metadata, preservation, heat, failures, messages, and rendering. Campfire cooking uses SurvivalNeedsService campfire instances as workstation context without moving campfire ownership into crafting.

Manual acceptance: `cook list`, `recipe roasted river fish`, gather or create a `river_fish` instance, `light campfire`, `add fuel`, `cook roasted river fish at campfire`, `food inspect cooked river fish`, `eat cooked river fish`, `preserve <item>`.
