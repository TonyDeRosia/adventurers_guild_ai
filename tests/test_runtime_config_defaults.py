import json
from pathlib import Path

from app.runtime_config import RuntimeConfigStore


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    output: dict[str, object] = {}
    for key, value in pairs:
        if key in output:
            raise ValueError(f"Duplicate key in JSON payload: {key}")
        output[key] = value
    return output


def test_default_app_config_is_valid_json_without_duplicate_keys() -> None:
    config_path = Path("data/defaults/app_config.json")
    payload = json.loads(config_path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys)

    assert isinstance(payload, dict)
    assert "model" in payload
    assert "image" in payload


def test_default_app_config_round_trips_through_runtime_store(tmp_path: Path) -> None:
    source = Path("data/defaults/app_config.json")
    target = tmp_path / "app_config.json"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    loaded = RuntimeConfigStore(target).load()

    assert loaded.model.provider == "null"
    assert loaded.model.model_name == "llama3"
    assert loaded.image.provider == "local"
    assert loaded.image.campaign_auto_visual_timing == "after_narration"
    assert loaded.image.managed_service_enabled is True
    assert loaded.image.managed_install_path == ""
