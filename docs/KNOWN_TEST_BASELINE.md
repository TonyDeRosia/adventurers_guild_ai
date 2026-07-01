# Known Test Baseline

Last checked while hardening the V2 DM Reasoning Pipeline.

## Command

```bash
python -m pytest tests/test_web_runtime.py tests/test_campaign_extensions.py tests/test_setup_modal_dom.py
```

## Current failures observed

`tests/test_campaign_extensions.py` and `tests/test_setup_modal_dom.py` passed during the combined run. The combined suite currently reports legacy/environment failures in `tests/test_web_runtime.py` that are outside the pipeline-owned `/api/campaign/input` acceptance path:

- ComfyUI/image setup validation and orchestration failures in this container, including incomplete portable folder messaging, missing `pyvenv.cfg`, managed ComfyUI root inference, preferred-checkpoint setup, missing python runtime, and launch-target validation.
- Legacy direct `runtime.handle_player_input(...)` expectations around lightweight NPC persistence, prompt feed retention, narrator output, recalibration learning-mode ability creation, and NPC dialogue splitting.
- Legacy guided-start tests that still call `runtime.handle_player_input(...)` directly and expect sparse/broad intros to open immediately or remain in the previous `character_creation` follow-up state. The V2 route acceptance path is now covered through `engine.dm_pipeline.process_player_input(...)` and `/api/campaign/input`; weak intros intentionally stay in bootstrap and broad ability claims move to `ability_setup_followup` until abilities are clarified.

Use the targeted V2 pipeline tests and live route tests for this change's acceptance behavior.
