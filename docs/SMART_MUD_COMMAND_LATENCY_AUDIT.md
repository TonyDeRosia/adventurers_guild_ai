# Smart MUD Command Latency Audit

## Scope

This audit records the command path for `look`, `score`, `worth`, `equipment`, `north`, and `quit` on the current `main-v2` repository. Adventurer's Lair was used only as a behavioral reference: command input produces immediate player output, while asynchronous game-loop output remains independent.

## Root cause

The desktop client posted commands to `POST /api/mud/input`, but visible command output could be delayed until the next `/api/mud/async-messages` poll. The async controller schedules normal polls at 5000 ms, so any command output not rendered from the direct POST response was visibly delayed by that fixed interval.

## Correlation and monotonic timing

Each command response now carries a `request_id`/`action_id` and a `trace` object populated with monotonic timestamps for:

- input key accepted / request started;
- command routing started;
- command execution completed;
- response serialization completed.

The frontend adds debug-only (`window.SMART_MUD_DEBUG`) timing for:

- command network ms;
- DOM append ms;
- total keypress-to-display ms.

## Command response normalization

`MudRuntime.handle_input()` returns a canonical `command_response` envelope with command text, semantic/plain output, room render, prompt snapshot, state updates, session transition, mutation state, async events, and delivery policy. `WebRuntime.handle_input()` maps this into the authoritative HTTP response fields expected by the browser:

- `ok`;
- `request_id` / `action_id`;
- `command_echo_html` / `command_echo_text`;
- `command_result_html` / `command_result_text`;
- `room_output_html` / `room_output_text`;
- `prompt_html` / `prompt_text`;
- `session_state` / `session_transition`;
- `save_status`.

## Delivery policy

Ordinary command output uses `direct_response`. Independent room/combat/world events remain `async_only`. Observer messages are queued for other recipients and exclude the acting character, preventing duplication for the command issuer.

## Save policy and dirty tracking

Commands are classified into one mutation category. Read-only commands (`look`, `score`, `worth`, `equipment`, `inventory`, `abilities`, `help`, `who`, `history`, `combatstats`, `attributes`, etc.) do not dirty or save the character. Mutating commands mark dirty reasons (`movement`, `equipment`, `inventory`, `resource`, `world`, `builder`, or `session metadata`) and pass through a single save coordinator. Clean characters skip saves; dirty characters save once and clear dirty state only after a successful commit. Quit uses one final coalesced save owner.

## Async cursor and prompt behavior

The async endpoint returns the latest cursor even when no messages are delivered. The frontend preserves the cursor across command responses and only resets it when changing sessions/characters. Async responses update the prompt only when `prompt_invalidated == true` and prompt HTML exists.

## Windows manual acceptance steps

These steps must be performed manually on Windows; they were not performed automatically here.

1. Enter `Kraevok`.
2. Run `score`.
3. Run `equipment`.
4. Run `worth`.
5. Run `look`.
6. Move `north`.
7. Run `score` again.
8. Run `quit`.

Expected results:

- each command result appears immediately from `POST /api/mud/input`;
- no fixed five-second delay;
- `score`, equipment display, and `worth` perform zero character saves;
- successful movement performs one bounded save;
- quit performs one final character save;
- no duplicate command output;
- async polling remains lightweight;
- no async request continues after quit.
