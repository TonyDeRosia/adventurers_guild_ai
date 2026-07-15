# Phase 13C3-A3I Application Shell Audit

## Authoritative UI session states

The web shell now treats server/session state as authoritative and supports these client states: `logged_out`, `account_authenticated`, `world_select`, `character_select`, `character_entering`, `playing`, `disconnected`, and `error`.

The client may render gameplay prompt/input only when all of the following are true:

- the account session is authenticated;
- a world is selected;
- the server session is active;
- `session_state == "playing"`;
- `character_id` is present in the session;
- the server reports `character_entered == true`.

Stale prompt text, stale character IDs, and cached prompt HTML are not sufficient to infer playing state.

## Shell files and behavior

| File | Component/function | Previous assumption/behavior | Required behavior | Implementation status |
| --- | --- | --- | --- | --- |
| `app/static/index.html` | main shell markup | Large Smart MUD header lived at the top of the primary content panel; permanent status stack rendered `Ready.` / `Account ready.`; prompt and command row were always in the DOM without state semantics. | Primary panel begins with actual app content; account/application controls live in a compact external lower-left panel; no permanent bottom status bar; prompt/command row exists but is hidden outside active play. | Updated. Header/status stack removed from central content; `mud-account-panel` and transient `mud-notification` added. |
| `app/static/app.js` | `mudSessionState`, `isPlaying`, `updateGameplayChrome`, `renderPrompt` | Prompt rendered from any prompt payload and defaulted to save-state text in non-game screens. | Prompt renders only during authoritative playing state and is cleared immediately otherwise. | Updated. Prompt is hidden/cleared unless `isPlaying()` is true. |
| `app/static/app.js` | `sendInput` | Command input could submit while the client was on character select. | Gameplay commands are not submitted unless actively playing. | Updated. Client rejects local submission outside active play. |
| `app/static/app.js` | `renderWorldSelect`, `renderCharacterSelect`, `renderAccountFlow` | Transitions retained some active character UI state. | Leaving play clears active character, cached prompt, pending command UI, and history cursor. | Updated via `clearGameplayState`. |
| `app/static/app.js` | `enterCharacter`, `refreshPlayView` | UI could show play chrome before confirming server enter. | Character-enter transition hides play chrome; prompt/input appear only after successful enter/play-view confirms entry. | Updated. Enter button enters loading state and chrome activates only after successful response/play-view. |
| `app/static/app.js` | `updateAccountPanel` | Account/status information was duplicated in the main header/status strip. | Compact account/navigation panel displays account, world, character, Settings, Back, and Logout outside the transcript. | Updated. |
| `app/static/styles.css` | Smart MUD layout rules | Central content height was reduced by top header/status and bottom status stack; no lower-left account panel. | Lower-left account panel is visually separate and responsive; primary panel height is focused on content/transcript. | Updated with Phase 13C3-A3I overrides and narrow-width footer layout. |
| `app/web.py` | `account_session`, `play_view`, `_normalize_mud_view` | Session payload exposed only generic state and could return play prompt/output without proving entered character. | Payload includes explicit `session_state` and `character_entered`; play view returns empty prompt when not actively playing. | Updated. |
| `app/web.py` | `handle_input`, `/api/mud/input` | Rejection used generic session errors. | Gameplay commands outside active playing state return structured `not_playing_character`. | Updated. |
| `app/web.py` | account/world/character transitions | Account login jumped to character-select state before world selection; world changes did not explicitly clear active character. | World select and character select are explicit, and selecting a world clears active character state. | Updated. |
| Desktop wrapper (`app/main.py`, runtime launch path) | Static web shell host | Uses the same static app and FastAPI runtime. | Desktop inherits state-aware shell behavior because static assets and WebRuntime endpoints are shared. | No separate wrapper change required. |

## Implementation notes

- The permanent bottom status bar was removed, not merely hidden. Transient messages now use `#mud-notification`.
- The account panel is not part of the transcript and is outside `.smart-mud-main`.
- Prompt polling may still run, but `/api/mud/play-view` returns no prompt when no character is actively entered, and the client ignores prompt updates unless `isPlaying()` is true.
- Server-side command validation is the final authority and rejects bypassed gameplay input outside active play with `not_playing_character`.
