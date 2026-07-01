# Known Test Baseline

This baseline was captured while stabilizing tests around the productized V1 app defaults. The app now defaults to Adventure Mode, hides creator controls until explicitly enabled, and keeps image generation disabled unless a user opts into the image/developer setup flow.

## Baseline command

- `node --check app/static/app.js` passes.
- After updating stale default-mode tests, `python -m pytest` reports 28 failures, 447 passes, and 9 skips.

## Intentionally unfixed failures

The following failures remain documented rather than fixed in this stabilization pass because they appear to cover behavior outside the requested scope or potentially real product regressions that should be triaged before changing gameplay/runtime code:

- Ability auto-learning and recalibration expectations in `tests/test_campaign_extensions.py` and `tests/test_web_runtime.py` now conflict with the current player-managed spellbook behavior (`[ability-learn] added_to_spellbook=false reason=player_managed_spellbook`). These should be reviewed as gameplay behavior before changing either code or tests.
- Several ComfyUI/image backend setup diagnostics tests still assert detailed managed-runtime launch behavior. Image generation remains disabled by default, so these developer-tool tests need a separate targeted review to distinguish stale setup assumptions from real setup regressions.
- A few runtime prompt/scene-state tests fail because the runtime now auto-creates a main character sheet and may retry narrator prompts during validation. These are preserved as baseline failures pending gameplay/runtime triage.

## Tests updated in this pass

- Settings shortcut DOM tests now assert the current modal manager flow (`openPrimaryModal`) rather than older direct class toggles.
- Creator Mode confirmation tests now assert the current dialog helper (`openDialog`) rather than older direct class toggles.
- Settings persistence tests now expect image workflow paths to remain blank when the image provider is `null`/disabled by default.
- Image setup orchestration monkeypatches now accept the current `setup_lock_owned` keyword used by the runtime setup flow.
