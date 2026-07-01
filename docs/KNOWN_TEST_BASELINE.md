# Known Test Baseline

Last checked while cleaning player-facing Adventure Mode output and Basic DM fallbacks.

## Command

```bash
python -m pytest tests/test_web_runtime.py tests/test_campaign_extensions.py tests/test_setup_modal_dom.py
```

## Current result

- `tests/test_campaign_extensions.py`: passed in the combined run.
- `tests/test_setup_modal_dom.py`: passed in the combined run.
- Combined suite result: **339 passed, 11 failed, 12 skipped**.

## Current failures observed

The remaining failures are in `tests/test_web_runtime.py` and are unrelated to the Adventure Mode player-output filter, diagnostic routing, Basic DM fallback, ability-use quarantine, or bootstrap role parsing changes in this branch:

- ComfyUI/image setup validation and orchestration baseline failures:
  - incomplete portable folder messaging still expects `python_embeded or .venv`
  - missing `pyvenv.cfg` validation is not marked broken
  - managed ComfyUI root inference is not considered valid in the test fixture
  - preferred-checkpoint setup monkeypatch does not accept `setup_lock_owned`
  - missing python runtime and launch-target validation do not report expected missing-file sentinels
- Legacy direct runtime expectations unrelated to this output-filter change:
  - lightweight NPC persistence still observes an auto-created main character sheet
  - prompt-feed retention expectations differ from current runtime behavior
  - gameplay narrator-output counting still sees retry generation
  - recalibration no longer auto-adds missing abilities directly when player-owned ability proposals are required
  - NPC dialogue split assertion expects the pre-routed message list shape

Use the focused DM/output tests and the passing `tests/test_campaign_extensions.py`/`tests/test_setup_modal_dom.py` results for this change's acceptance behavior.
