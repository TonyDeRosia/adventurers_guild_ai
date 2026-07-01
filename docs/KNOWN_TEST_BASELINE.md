# Known Test Baseline

Last checked while implementing the V2 DM Reasoning Pipeline.

## Command

```bash
python -m pytest tests/test_web_runtime.py tests/test_campaign_extensions.py tests/test_setup_modal_dom.py
```

## Current failures observed

`tests/test_campaign_extensions.py` and `tests/test_setup_modal_dom.py` passed in the targeted run. `tests/test_web_runtime.py` currently reports pre-existing/image-environment and legacy-expectation failures when run as a whole in this container, including ComfyUI validation/orchestration cases and older guided-start tests that expected sparse intros to begin immediately. The V2 pipeline intentionally changes guided-start behavior so weak or incomplete intros stay in bootstrap instead of opening the scene.

The new acceptance flows should be validated against the live `/api/campaign/input` route because that route now invokes `engine.dm_pipeline.process_player_input()`.
