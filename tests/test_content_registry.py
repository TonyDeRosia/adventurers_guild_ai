from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.content_registry import ContentRegistry


def _seed_content_tree(base: Path) -> None:
    base.mkdir(parents=True, exist_ok=True)
    (base / "dialogues.json").write_text(
        json.dumps({"npc_1": {"start_node": "start", "nodes": {"start": {"text": "Hi", "options": []}}}}),
        encoding="utf-8",
    )
    (base / "enemies.json").write_text(
        json.dumps(
            {
                "goblin": {
                    "id": "goblin",
                    "name": "Goblin",
                    "max_hp": 8,
                    "attack": 2,
                    "armor": 0,
                    "description": "small",
                    "encounter_text": "A goblin appears",
                }
            }
        ),
        encoding="utf-8",
    )
    (base / "items.json").write_text(
        json.dumps(
            {
                "potion": {
                    "id": "potion",
                    "name": "Potion",
                    "type": "consumable",
                    "description": "heal",
                }
            }
        ),
        encoding="utf-8",
    )


def test_content_registry_reads_standard_json_files(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    _seed_content_tree(data_dir)

    registry = ContentRegistry(data_dir)

    assert registry.get_dialogue("npc_1") is not None
    assert registry.get_enemy("goblin") is not None
    assert registry.get_item("potion") is not None


def test_content_registry_supports_mispackaged_nested_json_file_layout(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    _seed_content_tree(data_dir)

    original = data_dir / "dialogues.json"
    original_text = original.read_text(encoding="utf-8")
    original.unlink()
    nested_dir = data_dir / "dialogues.json"
    nested_dir.mkdir(exist_ok=True)
    (nested_dir / "dialogues.json").write_text(original_text, encoding="utf-8")

    registry = ContentRegistry(data_dir)

    assert registry.get_dialogue("npc_1") is not None


def test_content_registry_raises_for_invalid_json_path(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    _seed_content_tree(data_dir)

    broken = data_dir / "dialogues.json"
    broken.unlink()
    broken.mkdir(exist_ok=True)

    with pytest.raises(FileNotFoundError):
        ContentRegistry(data_dir)
