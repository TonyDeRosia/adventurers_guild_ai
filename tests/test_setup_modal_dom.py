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
    assert 'id="setup-image-ai"' not in html
    assert "Import, Set Up, and Start Image AI" in html
    assert "1. Download" in html
    assert "2. Select Sources" in html
    assert "3. Start" in html



def test_creator_mode_confirmation_and_badge_markup_exist() -> None:
    html = _index_html()
    assert 'id="creator-mode-toggle"' in html
    assert 'id="creator-mode-confirm-modal"' in html
    assert 'Creator Mode lets you edit character sheets, inventory, abilities, quests, NPCs, and other campaign data.' in html
    assert 'I understand that editing campaign data can change gameplay.' in html
    assert 'id="creator-mode-badge"' in html


def test_runtime_editors_are_creator_mode_only_by_default() -> None:
    html = _index_html()
    creator_only_ids = [
        'runtime-character-sheet-create-toggle',
        'inventory-editor-panel',
        'spellbook-editor-panel',
    ]
    for element_id in creator_only_ids:
        match = re.search(rf'id="{element_id}"[^>]*class="([^"]*)"|class="([^"]*)"[^>]*id="{element_id}"', html)
        assert match, f"{element_id} is missing"
        classes = ' '.join(group for group in match.groups() if group)
        assert 'creator-mode-only' in classes
