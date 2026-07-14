# Smart MUD Web Runtime Performance Audit

## Scope
Audited `app/static/app.js`, `app/web.py`, `engine/mud_runtime.py`, `smart_mud/transport.py`, runtime sessions, character persistence, play-view/prompt/room rendering, display snapshots, command history, EventBus, and the runtime pulse.

## Baseline findings
Before this change the browser created an unconditional `setInterval(pollPlayView, 1200)` at shell initialization. `pollPlayView()` called `GET /api/mud/play-view` regardless of login/play state. `refreshPlayView()` also called the same endpoint for initial view loads and full-screen replacement.

### `/api/mud/play-view` callers
* Old permanent timer: `pollPlayView()` every 1.2 seconds.
* Old explicit refresh: `refreshPlayView()` when called without an already supplied view.
* Character entry: entered a character, then requested play-view.
* No command path required play-view directly, but command normalization consumed the runtime view returned by `POST /api/mud/input`.

### Timers and recursive refresh
* Old frontend: one fixed 1.2 second timer that could continue outside play.
* Backend: one managed one-second runtime pulse for world time, combat, controllers, needs, and scheduled systems.
* No browser timer is required to drive the server pulse.

### Baseline measured counters
Measured by reading the actual frontend timer/caller graph and runtime counters introduced in this phase; timer-derived HTTP counts are exact for the 1.2 second interval over 10 seconds.

| Scenario | HTTP requests | play-view count | character load count | character save count | world load count | snapshot build count | render count |
|---|---:|---:|---:|---:|---:|---:|---:|
| Account screen idle 10s | 8 | 8 | 0 | 0 | 0 | 0 | 0 |
| Character select idle 10s | 8 | 8 | 0 | 0 | 0 | 0 | 0 |
| Playing idle 10s | 8 | 8 | 16 | 0 | 8 | 0 | 16 |
| One `look` | 1 command + timer race | 1 command view + possible timer | 2+ | 1 | 1 | command-specific | 2 |
| One `score` | 1 command + timer race | command prompt view + possible timer | 2+ | 1 | 1 | 1+ | 1+ |
| One movement | 1 command + timer race | command room view + possible timer | 2+ | 1+ | 1 | command-specific | 2 |
| Quit then idle 10s | 8 | 8 | 0 in guarded backend, timer still sent | 0 | 0 | 0 | 0 |

The important baseline problem was not just count volume; each active play-view reloaded the character in `MudRuntime.play_view` and then `_normalize_mud_view` loaded the same character again for name/HP. `_normalize_mud_view` also loaded the active world for response naming.

## Implemented behavior

### Frontend refresh architecture
The unconditional full-view interval was removed. `mudRefreshController` owns async refresh and enforces one timer, one in-flight request, `AbortController` cancellation, and cleanup on state changes, logout, quit, and page unload. It starts only after successful character entry and calls `/api/mud/async-messages`, not `/api/mud/play-view`.

### Async message architecture
Added `GET /api/mud/async-messages?after=<cursor>`. The runtime exposes message envelopes with `message_id`, `session_id`, `character_id`, `world_id`, `event_type`, `output_text`, `output_html`, invalidation flags, `session_state`, and `created_at`. Messages are retained per active character and delivered only when their sequence is newer than the client cursor.

### Resident-character design and session cache
`MudRuntime` now tracks active characters and session associations with these mappings:
* `session_active_character`: session id to active character id.
* `active_characters`: active character id to resident `MudCharacter`.
* `actor_registry`: active character actor projection.
* `character_session_ids`: character id to web/telnet session id.
* counters and dirty/save state hooks for active objects.

Character entry loads from SQLite once, registers the actor, stores the resident object, and subsequent play-view/command/prompt paths use the resident object.

### Play-view, prompt, and rendering changes
`MudRuntime.play_view()` resolves the resident character once, renders room and prompt once, and never performs its own SQLite load when the active object exists. `_normalize_mud_view()` uses the already resident character and active world package instead of reloading SQLite/world package data.

`prompt_snapshot()` provides lightweight prompt-only projection for commands and async updates that do not need full room rendering.

### Save/autosave policy
Read-only commands (`look`, `score`, `inventory`, `equipment` and aliases) do not perform the command-completion character save. Mutating commands continue to save. Quit/session transition performs a final coalesced save and removes active-session residency. Server runtime pulse remains the owner of timed systems; frontend polling is not used for autosave.

### Request/render deduplication and scrollback ownership
Backend play-view tracks overlapping identical active requests and returns a lightweight not-modified response while incrementing `overlapping_requests_prevented`. Frontend tracks play-view sequence numbers and ignores stale responses. Active scrollback is browser-owned after initial character entry; commands and async messages append output instead of replacing scrollback.

### Session transitions
Leaving playing stops the async controller, aborts in-flight requests, clears active prompt/chrome, clears active character frontend state, and avoids play-view. Backend play-view outside active play returns lightweight session state and does not load character/world/room.

### Runtime pulse behavior
The one-second FastAPI-owned runtime pulse remains. Pulse systems may enqueue visible combat/effect/NPC/room messages; the browser receives those through the async channel. The browser does not drive world time.

### Logging and counters
Routine resident object access does not log `Loaded character ...`; that remains a persistence operation log only. Developer diagnostics include performance counters: play-view requests, async requests, SQL loads/saves, world package loads, room/prompt renders, display snapshots, commands, delivered messages, and overlapping request prevention.

## Adventurer's Lair behavioral parity findings
Smart MUD does not copy Adventurer's Lair C structures, descriptors, sockets, macros, or file formats. It now reproduces the performance characteristics: player state is loaded on entry, retained while playing, commands operate on resident state, pulse/timed systems are centralized, output is delivered when generated, persistence occurs at lifecycle/mutation points, restart recovers from SQLite, and display refresh does not reload the player file/database row every cycle.

## Windows manual acceptance procedure
Not performed in Linux. On Windows desktop, start the app, enter a character, idle 30 seconds, run `look`, run `score`, move north, idle 30 seconds, `quit`, idle at Character Select for 30 seconds, re-enter, then logout. Expected logs: no endless `GET /api/mud/play-view`, no repeated idle character loads, no play-view calls at Character Select or after logout, command requests occur once, async messages appear only when generated, character save counts are bounded, and desktop remains responsive.
