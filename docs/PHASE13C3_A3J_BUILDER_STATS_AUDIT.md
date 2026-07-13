# Phase 13C3-A3J Builder Stats Audit

Audited implementation on the checked-out repository branch. Primary runtime content lives under `worlds/shattered_realms`; Builder drafts live under the same world package's `builder` subtree and are authoritative until `builder publish stats` atomically publishes them.

## Document path matrix

| Family | Live path | Draft path | Adapter |
|---|---|---|---|
| attributes | `attributes/attributes.json` | `builder/attributes/attributes.json` | `AttributeDocumentAdapter` |
| stat formulas | `formulas/stat_formulas.json` | `builder/formulas/stat_formulas.json` | `FormulaDocumentAdapter` |
| derived stat definitions | `formulas/derived_stats.json` | `builder/formulas/derived_stats.json` | `StatDefinitionDocumentAdapter` |
| resistance definitions | `formulas/derived_stats.json#resistance_types` | `builder/formulas/derived_stats.json#resistance_types` | `ResistanceDocumentAdapter` |
| encumbrance thresholds | `formulas/derived_stats.json#encumbrance_thresholds` | `builder/formulas/derived_stats.json#encumbrance_thresholds` | `EncumbranceDocumentAdapter` |
| posture definitions | `combat/postures.json` | `builder/combat/postures.json` | `PostureDocumentAdapter` |
| range rules | `combat/range_rules.json` | `builder/combat/range_rules.json` | `RangeRulesDocumentAdapter` |
| combat messages | `combat/combat_messages.json` | `builder/combat/combat_messages.json` | `CombatMessageDocumentAdapter` |

## Pre-change audit findings

The previous implementation routed `attributeedit`, `formula`/`formulaedit`, `statdef`, `resistanceedit`, `encumbranceedit`, `postureedit`, `rangeedit`, and `combatmessage` through one generic handler. It performed simple JSON load/set/save operations through `BuilderContentEditor`, but schema knowledge was scattered in command dispatch, validation only checked duplicate IDs and missing show IDs, deletion did not consult a reference graph, responses were mostly raw JSON and could report success even when semantic requirements were not validated. `builder publish stats` parsed draft JSON and copied files in-place with a basic rollback attempt; it did not stage every file, persist manifests, provide hash-backed dirty status, expose preview/status, or distinguish runtime activation from file publication.

## Current command matrix

| Command family | Syntax | Handler | Mutation | Draft modified | Validation | Response | Tests |
|---|---|---|---|---|---|---|---|
| `attributeedit` | list/show/create/clone/name/short/description/default/minimum/maximum/creationmin/creationmax/order/group/role/visible/enable/tag/delete/validate/preview | `_cmd_attributeedit` -> `AttributeDocumentAdapter` | Real atomic draft mutation | `builder/attributes/attributes.json` | ID policy, ranges, order, tags, document IDs | Real record/validation preview | `tests/test_phase13c3_a3j_builder_stats.py` |
| `formula`, `formulaedit` | list/show/create/clone/expression/description/minimum/maximum/rounding/variable/test/validate/preview/delete | `_cmd_formulaedit` -> `FormulaDocumentAdapter` | Real atomic draft mutation | `builder/formulas/stat_formulas.json` | FormulaEngine parse/eval, unknown functions, unsafe syntax, undeclared variables, min/max, rounding, reference deletion | Real record/test diagnostics | focused tests |
| `statdef` | list/show/create/clone/name/short/description/formula/minimum/maximum/rounding/format/group/order/role/visible/enable/tag/delete/validate/preview | `_cmd_statdef` -> `StatDefinitionDocumentAdapter` | Real atomic draft mutation | `builder/formulas/derived_stats.json` | formula reference, min/max, format, order, tags | Real record/validation preview | focused tests |
| `resistanceedit` | list/show/create/clone/name/description/order/visible/enable/unit/minimum/maximum/delete/validate/preview | `_cmd_resistanceedit` -> `ResistanceDocumentAdapter` | Real atomic draft mutation | `builder/formulas/derived_stats.json` | unit, min/max, order, ID policy | Real record/validation preview | focused tests |
| `encumbranceedit` | list/show/set/rename/order/description/penalty/delete/validate/preview | `_cmd_encumbranceedit` -> `EncumbranceDocumentAdapter` | Real atomic draft mutation | `builder/formulas/derived_stats.json` | baseline zero, nonnegative thresholds, IDs | Real records/validation preview | focused tests |
| `postureedit` | list/show/create/clone/name/description/modifier/allow/automatic-hit-against/wake-on-damage/tag/enable/delete/validate/preview | `_cmd_postureedit` -> `PostureDocumentAdapter` | Real atomic draft mutation | `builder/combat/postures.json` | ID policy, tags, required posture delete protection, known modifier fields | Real record/validation preview | focused tests |
| `rangeedit` | show/set/reset/validate/preview | `_cmd_rangeedit` -> `RangeRulesDocumentAdapter` | Real atomic draft mutation | `builder/combat/range_rules.json` | unknown fields, min/max, formula reference | Real range document preview | focused tests |
| `combatmessage` | list/show/create/clone/field/condition/tag/delete/validate/preview | `_cmd_combatmessage` -> `CombatMessageDocumentAdapter` | Real atomic draft mutation | `builder/combat/combat_messages.json` | safe placeholders, no HTML, known condition fields | Real perspectives preview | focused tests |
| `builder status stats` | status | `_stats_status` | Read-only | none | cross-document status | hash-backed dirty/clean matrix | transaction tests |
| `builder validate stats` | validate | `_validate_stats` | Read-only | none | all-document validator | grouped errors and dependency graph | transaction tests |
| `builder preview stats` | preview | `_preview_stats` | Read-only | none | all-document validator | changed docs, hashes, warnings/errors, activation policy | transaction tests |
| `builder publish stats` | publish | `_publish_stats` -> `StatCombatPublisher` | Staged atomic publication | live canonical files only after staging | validation gate + staged parse | manifest, active_runtime/restart_required | transaction tests |

## Validation rules and dependency graph

`StatCombatPublishValidator` loads all draft documents as a prospective unit, builds a graph of `statdef -> formula` and `range_rules -> formula`, and exports attribute/formula/stat ID sets. It collects all adapter errors as structured issues with document, record ID, field, code, and message. Warnings are returned separately. Reference graph checks are used to reject deletion of formulas referenced by stat definitions or range rules. Runtime-required posture IDs are protected.

## Draft dirty state and audit records

Dirty state is hash-backed: `builder status stats` compares each draft hash to the current published hash. Edit audit records are appended to `builder/audit/stats_edits.jsonl` with actor, world, command, document, record ID, before/after hash, validation result, and timestamp. Publish manifests are appended to `builder/audit/stats_publish_manifests.jsonl` with publish ID, world, actor, timestamp, paths, old/new/staged hashes, validation result, warnings, activation plan, rollback status when applicable, and runtime activation outcome.

## Publish, rollback, and activation policy

Publication validates drafts, stages JSON into `builder/staging/<publish-id>`, reparses staged files, computes staged hashes, then atomically replaces targets. Prior bytes are captured for every target. Replacement failures restore prior bytes or remove newly created targets, retain dirty drafts, write a failed manifest, and emit no reload event. Reload failure policy is policy B: valid files remain published, `published=true`, `active_runtime=false`, and `restart_required=true`. `stat_definitions_reloaded` is emitted only when attached runtime services actually reload successfully.

## Remaining manual status

Windows manual acceptance was not performed in this Linux container. Exact commands are documented in the final response for a Windows operator to run.
