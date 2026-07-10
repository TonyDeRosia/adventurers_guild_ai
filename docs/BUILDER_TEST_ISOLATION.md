# Builder Test Isolation

Builder tests that create, edit, import, apply, save, reload, snapshot, export, or otherwise mutate Builder state must never write to the committed `worlds/shattered_realms/builder/` drafts. Those drafts are starter content and are shared fixtures for fresh installs, documentation checks, and read-only consistency tests.

The shared pytest `isolated_builder_world` fixture copies the full Shattered Realms package into pytest's per-test `tmp_path`, creates a `BuilderWorkspace` pointed at that temporary `worlds/` root, and creates a `MudRuntime` with a temporary SQLite database and a `WorldRegistry` pointed at the same copy. Mutating tests should use the fixture's `world_root`, `world_path`, `builder_path`, `workspace`, `runtime`, and `database_path` instead of repository paths.

Repository integrity tests hash the committed Builder draft files and verify representative mutations only affect the temporary copy. Test-generated `imports/`, `exports/`, `history/`, `audit/`, and `snapshots/` content must remain under the isolated copy.
