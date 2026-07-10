# Phase 5F Body, Equipment, Population, Lifecycle, and Respawn Foundation

Phase 5F makes physical actor existence Builder data. Combat, damage, loot, AI combat, skills, spells, crafting, and economy remain out of scope.

## Body profiles and equipment ownership

Actors reference `body_profile_id`; profiles define ordered slots, labels, visibility, allowed item categories, occupancy metadata, and future hit-location fields. Equipment slots are not engine constants. Removed gameplay concepts include Primary Weapon, Secondary Weapon, Shield, Quiver, Ranged, Ammo, and Both Hands.

Equipment belongs to the Actor. Slots belong to the Body Profile. Items declare `occupies_slots`; a two-handed weapon occupies `main_hand` and `off_hand`, while a shield is just an item occupying `off_hand`. Future ammunition is metadata via `requires_item_tag`, not a slot. `light` remains a canonical MUD slot.

Example profiles are provided for humanoid, wolf, dragon, spider, ghost, and elemental anatomies in `worlds/shattered_realms/body_profiles/body_profiles.json` and Builder templates.

## Dynamic score rendering

The score renderer resolves the Actor body profile and renders that profile's slots in Builder order. Humanoid, wolf, dragon, and future Builder profiles render without hard-coded score slot lists.

## Lifecycle

Canonical states are persisted as:

`not_spawned -> queued -> spawned -> alive -> unconscious -> dead -> corpse -> despawned -> respawn_queue -> spawned`.

The lifecycle manager owns death outcomes: corpse creation, despawn, respawn queueing, unique removal hooks, and future quest-state hooks. Combat will only report that an Actor reached zero health.

## Corpses

Corpses are separate runtime entities in `corpse_instances`. Future loot ownership belongs to the corpse, not the source Actor. Loot itself is intentionally not implemented.

## Population manager and spawn policies

`PopulationManager` deterministically handles world startup, unique NPC ownership, maintained populations, and restart-safe persistence. Builder policies include `once`, `persistent_unique`, `maintain_population`, `respawn_after_delay`, `scheduled`, `disabled`, `manual_only`, and `world_event`.

Respawn uses world time only. The `respawn_queue` table persists due world times so restarts do not lose scheduled respawns.

## Builder integration

Builder/Admin commands include `bodylist`, `bodyshow`, `slotlist`, `spawnlist`, `spawnshow`, `population`, `population reload`, `population validate`, `population diagnostics`, `lifecycle`, `corpse diagnostics`, `respawn queue`, and `respawn diagnostics`. Builder import/export data lives under the world package and builder template directories.

## Migration

Legacy item slot names are migrated to canonical body slots: primary weapon and ranged become `main_hand`; secondary weapon and shield become `off_hand`; two-handed items declare both hand slots; quiver/ammo are removed as slots and reserved for future metadata.
