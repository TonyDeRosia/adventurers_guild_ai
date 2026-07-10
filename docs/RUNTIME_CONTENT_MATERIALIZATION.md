# Runtime Content Materialization

World materialization is deterministic and idempotent. `once` declarations create instances only when no `content_materializations` record exists. Movement, look, restart, and repeated materialization do not recreate collected or destroyed items.

Normal startup loads world definitions, loads existing SQLite instances, runs idempotent materialization for committed live declarations, and renders from canonical room contents. Builder draft declarations are diagnostics/import data until explicitly materialized by runtime tooling.


## Legacy entity source normalization

Phase 5A makes legacy NPC declarations compatibility and diagnostic sources only. Legacy room NPC arrays and entity-template default rooms normalize into deterministic canonical spawn declarations, materialize into SQLite `entity_instances`, and then normal rendering, targeting, dialogue, look, scan, search, and movement-room rendering consume runtime instances only. Builder diagnostics may still show templates, spawns, legacy declarations, and materialization records separately.

Canonical spawns supersede equivalent legacy declarations by world, room, template, and compatible quantity. Display-name deduplication is not allowed because legitimate same-name runtime instances must remain visible. Upgraded databases adopt one matching existing runtime row into the materialization record and report ambiguous extras as duplicate candidates instead of deleting or hiding them.

## Phase 5B materialization

Materialization preserves stable entity instance identity and initializes living simulation records idempotently for materialized NPCs.
