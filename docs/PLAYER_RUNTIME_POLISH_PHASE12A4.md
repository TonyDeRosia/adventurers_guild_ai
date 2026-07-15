# Player Runtime Polish (Phase 12A.4)

This pass extends existing runtime systems only. The SQLite runtime remains the authority, commands continue through the CommandRegistry and EventBus path, and service-backed gameplay objects are rendered from runtime state rather than being baked into room prose.

## Inspection System

`look <target>`, `look at <target>`, `examine <target>`, and `inspect <target>` share the runtime interaction target resolver. The resolver checks visible equipment and inventory, room items, players, NPCs, mobs, exits, authored room features, and service-backed world objects. Target output uses authored descriptions already present on Builder/world data or service profile-derived descriptions.

## Visible World Objects and Room Rendering

Room rendering is still performed by the canonical room renderer. Runtime room assembly now includes persisted service-backed objects such as campsites and campfires alongside players, NPCs, mobs, corpses, item instances, and room features. This keeps visible content tied to current runtime state.

## Campfire Lifecycle

Campfires continue to use `SurvivalNeedsService` persistence. The player flow is:

1. `set camp` establishes a campsite.
2. `build campfire` creates a persisted campfire instance.
3. `look` shows `a small campfire`.
4. `light campfire` changes the persisted campfire state to lit and `look` shows `a lit campfire`.
5. `extinguish campfire` changes the persisted state to extinguished and `look` shows `an extinguished campfire`.

Because the objects are read from SQLite, the visible state survives runtime restart.

## Starter Demonstration Skills and Spell

The default demonstration world continues to treat starter capabilities as real authored Ability/Skill/Spell entries. Player-facing skill and spell lists read from the existing ability registry and actor grants rather than hidden command aliases.

## Training Flow

Training remains owned by `TrainingService`. Player output should present lessons in natural language with costs, requirements, benefits, and available balances. Attribute allocation must update canonical character stats, trigger formula recalculation through the existing formula/stat path, and persist through SQLite.

## Social System

Deterministic socials now cover common classic MUD emotes such as wave, bow, nod, salute, point, laugh, smile, cry, cheer, applaud, hug, highfive, dance, spit, sit, stand, rest, yawn, and stretch. Socials publish EventBus events and render emote text rather than speech.

## Player Runtime Polish

Player-facing output should avoid implementation terminology and internal identifiers during ordinary play. Diagnostics remain available to authorized Builder/admin workflows, while normal commands render gameplay prose.
