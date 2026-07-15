# Progression Projection Row Contract

## Phase 15B.13A hotfix

The SCORE/WORTH regression was caused by `ProgressionService._row()` assuming every SQLite row was mapping-compatible and calling `dict(row)` directly.  Windows production returned a positional SQLite tuple from the progression connection path, so `dict(row)` tried to interpret the first text column as an iterable `(key, value)` pair and raised `ValueError: dictionary update sequence element #0 has length 58; 2 is required`.

Progression reads now use an explicit column list for `actor_progression_state` and convert rows through `row_to_mapping(row, cursor_description)`.  Mapping rows, `sqlite3.Row`, named tuples, and positional tuple/list rows with cursor descriptions are supported.  Positional rows without cursor descriptions and scalar/string rows are rejected with typed errors instead of guessed column order.

The progression service sets `sqlite3.Row` only inside its own read boundary when it owns a plain sqlite connection whose `row_factory` is unset, but correctness does not depend on that global setting.  The cursor description remains the canonical source for tuple conversion, which keeps SQL tracing or test wrappers from changing result semantics.

JSON fields (`profession_ids_json`, `advancement_flags_json`, and `metadata_json`) continue to decode field-by-field with safe defaults for malformed optional JSON.  Required identity fields (`progression_state_id`, `world_id`, `actor_type`, and `actor_id`) are validated and are not fabricated.

Projection failures are not negatively cached by this change.  Once the row conversion succeeds, repeated SCORE/WORTH snapshots rebuild through the existing display snapshot cache key and do not require database reset, character recreation, world recreation, or manual cache deletion.
