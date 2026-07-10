# Runtime Content Materialization

World materialization is deterministic and idempotent. `once` declarations create instances only when no `content_materializations` record exists. Movement, look, restart, and repeated materialization do not recreate collected or destroyed items.

Normal startup loads world definitions, loads existing SQLite instances, runs idempotent materialization for committed live declarations, and renders from canonical room contents. Builder draft declarations are diagnostics/import data until explicitly materialized by runtime tooling.
