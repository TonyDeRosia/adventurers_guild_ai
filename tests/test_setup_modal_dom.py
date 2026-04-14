from __future__ import annotations

from collections import Counter
from pathlib import Path
import re


def _index_html() -> str:
    return Path("app/static/index.html").read_text(encoding="utf-8")


def test_setup_modal_has_no_duplicate_dom_ids() -> None:
    html = _index_html()
    ids = re.findall(r'id="([^"]+)"', html)
    duplicates = sorted([dom_id for dom_id, count in Counter(ids).items() if count > 1])
    assert not duplicates, f"Duplicate DOM ids found: {duplicates}"


def test_comfyui_path_controls_live_only_in_advanced_image_settings() -> None:
    html = _index_html()
    details_match = re.search(
        r'<details class="advanced-image-settings">(?P<section>.*?)</details>',
        html,
        flags=re.DOTALL,
    )
    assert details_match, "Advanced image settings disclosure is missing."
    advanced_section = details_match.group("section")

    advanced_only_ids = [
        "comfyui-path-input",
        "pick-comfyui-folder",
        "comfyui-workflow-path-input",
        "pick-comfyui-workflow-file",
        "comfyui-output-dir-input",
        "pick-comfyui-output-folder",
    ]

    for element_id in advanced_only_ids:
        assert advanced_section.count(f'id="{element_id}"') == 1
        assert html.count(f'id="{element_id}"') == 1

    assert 'id="checkpoint-folder-input"' in html
    assert 'id="pick-checkpoint-folder"' in html
    assert 'id="open-checkpoint-page"' not in html


def test_play_layout_uses_single_campaign_log_without_npc_sidebar() -> None:
    html = _index_html()
    assert 'id="dialogue-panel"' in html
    assert 'id="dialogue-feed"' in html
    assert 'id="npc-panel"' not in html
    assert 'id="npc-panel-list"' not in html


def test_guided_image_import_controls_are_present() -> None:
    html = _index_html()
    required_ids = [
        "open-comfyui-download-page",
        "open-model-download-page",
        "image-import-comfy-source",
        "pick-image-import-comfy-file",
        "pick-image-import-comfy-folder",
        "image-import-model-source",
        "pick-image-import-model-file",
        "pick-image-import-model-folder",
        "import-image-ai",
    ]
    for element_id in required_ids:
        assert f'id="{element_id}"' in html
