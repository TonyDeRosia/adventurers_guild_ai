# Entity Spawn Runtime Bridge

Entity templates remain definitions. Spawn declarations and legacy default-room declarations materialize SQLite `entity_instances` once and record instance IDs in `content_materializations`. Entity `plugin_data.ai_profile` is preserved as deterministic future-AI metadata; no AI behavior or generation is performed.
