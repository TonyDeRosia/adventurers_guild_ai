# Builder Resets

Status: **Partial implementation**.

Commands implemented: `resetlist`, `resetstat`, `resetcreate`, `resetclone`, `resetset`, `resetdelete`, `resetcommand`, `resetvalidate`, `resetpreview`, `resetrun`, `resethistory`, `resettrace`; aliases: `zreset`, `zresetstat`, `zresetpreview`, `zresetrun`.

Draft file: `worlds/<world_id>/builder/resets.json` through existing `BuilderWorkspace` paths.

## Examples
* `resetlist`
* `resetcreate new_training_reset training_grounds New Training Reset`
* `resetcommand new_training_reset add SPAWN_ENTITY entity_template_id=training_master_borik room_id=training_yard spawn_count=1 maximum_scope=room maximum_count=1 result_reference=guard`
* `resetvalidate new_training_reset`
* `resetpreview new_training_reset`
* `resetrun new_training_reset --dry-run`
* `resetrun new_training_reset`
* `resethistory`
* `resettrace <reset_run_id>`

## Windows manual verification steps
1. From `C:\Users\antho\Desktop\Smart MUD\smartmud-main-v2\smartmud-main-v2`, run `python run.py`.
2. Log in as `Kraevok` / `char_shattered_realms_kraevok`.
3. Run `whoami` and confirm builder/admin/owner.
4. Enter Builder Mode: `builder on`.
5. Select/inspect the existing zone: `zreset zone=training_grounds` or use existing zone navigation.
6. Inspect the test profile: `resetstat phase15a_training_grounds_test`.
7. Validate: `resetvalidate phase15a_training_grounds_test`.
8. Preview: `resetpreview phase15a_training_grounds_test`.
9. Run: `resetrun phase15a_training_grounds_test`.
10. Inspect affected rooms: `goto training_yard`, `look`, then `goto weapon_practice_ring`, `look`.
11. Run it a second time: `resetrun phase15a_training_grounds_test`.
12. Confirm count limits prevent duplicate training guards/swords.
13. Set or inspect a `when_empty` profile while Kraevok is inside `training_grounds`; preview/run should show occupancy skip for automatic mode.
14. Leave the zone, then confirm automatic eligibility with an admin pulse/tick hook when wired.
15. View history: `resethistory`.
16. View action trace: `resettrace <reset_run_id>`.

## Emberwood reset editing

The Emberwood Forest reset draft lives in `worlds/shattered_realms/builder/resets.json` as `emberwood_forest_population`. Validate with `resetvalidate emberwood_forest_population`, preview with `resetpreview emberwood_forest_population`, and populate missing wildlife with `resetrun emberwood_forest_population`.
