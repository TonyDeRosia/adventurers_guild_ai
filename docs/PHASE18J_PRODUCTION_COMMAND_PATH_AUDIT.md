# Phase 18J Production Command Path Audit

## Production path before the fix

`POST /api/mud/input` is handled by `app.web.create_web_app.<locals>.mud_input`, which calls `WebRuntime.handle_input`.  The web runtime sends a `TransportMessage` through `smart_mud.transport.WebTransportAdapter`, whose shared base class `RuntimeTransportAdapter.handle_message` calls `MudRuntime.handle_input(character_id, text)`.  `MudRuntime.handle_input` loads the resident character, then calls `MudRuntime._handle_runtime_command`.  `_handle_runtime_command` parses the leading command through `MudRuntime._parse_interaction_command`; for `c ...`/`cast ...`, it delegates to `MudCommandEngine.handle_command`, which resolves `c` to `cast` with the canonical `CommandRegistry` and invokes `MudCommandEngine._cmd_use_ability`.

The production divergence was not a second web route: it was stale compatibility redispatch in `MudRuntime.handle_input`.  When display or ability output matched legacy fallback conditions, the runtime called `self.command_engine.handle_command(char, refresh_command)` a second time.  This made one input produce two deterministic routing log pairs and repeated display/projection loads.  The same compatibility area also made diagnosis misleading because Phase 18I spellup text could be present while production command results were re-entered through legacy refresh behavior.

## Production path after the fix

`POST /api/mud/input` -> `app.web.mud_input` -> `WebRuntime.handle_input` -> `WebTransportAdapter.handle_message` -> `MudRuntime.handle_input` -> `MudRuntime._handle_runtime_command` -> `MudCommandEngine.handle_command` -> `CommandRegistry.resolve`/`MudCommandEngine.resolve_alias` -> `MudCommandEngine._cmd_use_ability` -> `AbilityRuntimeGateway.resolve_spell_tokens` -> `AbilityRuntimeGateway.execute_by_id` -> `AbilityExecutionService.start_ability`.

There is no second `MudCommandEngine.handle_command` refresh pass after command execution.

## Cast implementations found

| File | Function/class | Production reachable | Test reachable | Registration point | Action |
|---|---|---:|---:|---|---|
| `engine/mud_commands.py` | `MudCommandEngine._cmd_use_ability` | Yes | Yes | `MudCommandEngine.command_handlers['cast']` | Retained as authoritative cast handler; uses `resolve_spell_tokens` and `execute_by_id`. |
| `engine/abilities.py` | `AbilityRuntimeGateway.execute` / `execute_result` | Yes for generic abilities; `execute_result` remains legacy/test API | Yes | Called by gateway clients | Retained; cast path now enters through `execute_by_id`, not whole-query execution. |
| `engine/abilities.py` | `AbilityRuntimeGateway.resolve_ability_prefix` | Yes for non-cast direct ability commands | Yes | `_cmd_use_ability` for non-cast verbs | Retained for `use`/direct ability behavior only. |
| `engine/mud_runtime.py` | compatibility redispatch in `MudRuntime.handle_input` | Was reachable | Was reachable | Post-command refresh branch | Removed/made unreachable. |

## Command registries and dispatchers

* `engine.command_registry.CommandRegistry` is the canonical registry.
* `engine.mud_commands.MudCommandEngine` owns deterministic gameplay handlers.
* `smart_mud.transport.WebTransportAdapter` and `TelnetTransportAdapter` are transport adapters only; both call `MudRuntime.handle_input` through `RuntimeTransportAdapter.handle_message`.
* `engine.mud_runtime.MudRuntime._handle_runtime_command` remains the runtime gameplay adapter for movement/items/builder pre-routing and delegates canonical ability/display commands to `MudCommandEngine`.

## Double routing explanation

The duplicate logs were caused by the post-command compatibility refresh branch in `MudRuntime.handle_input`, not by duplicate HTTP routes.  For stale empty display output and certain ability fallback messages, that branch called `self.command_engine.handle_command` again with the same command text, causing duplicate `Routing ...` and `Deterministic: ...` prints and extra persistence/projection work.  The branch was removed so the original resolution object/result is the only command response.

## Startup diagnostics

Startup now records structured debug diagnostics with:

* runtime root;
* git commit;
* imported `engine`, `engine.mud_commands`, and `engine.abilities` paths;
* module names;
* command registry object id;
* cast handler qualified name and source file.

The desktop production module paths from this Linux verification run are:

* `/workspace/smartmud/engine/__init__.py`
* `/workspace/smartmud/engine/mud_commands.py`
* `/workspace/smartmud/engine/abilities.py`

On Windows desktop, the same diagnostics will report the corresponding absolute paths under `C:\Users\antho\Desktop\Smart MUD\smartmud-main-v2\smartmud-main-v2` when launched from that tree.

## Remaining known issue

The smoke transcript still shows prompt/display response rendering can load the resident character during post-command view construction.  The eliminated compatibility redispatch stops duplicate command resolution; further projection-load reduction should move display services fully onto the resident actor/session projection.
