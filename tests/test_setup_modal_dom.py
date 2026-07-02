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



def test_advanced_campaign_image_generation_checkbox_defaults_off() -> None:
    html = _index_html()
    match = re.search(r'<input id="image-enabled"[^>]*>', html)
    assert match, "Campaign image generation checkbox is missing."
    assert "checked" not in match.group(0)


def test_settings_shortcuts_close_settings_before_opening_target_modals() -> None:
    script = Path("app/static/app.js").read_text(encoding="utf-8")
    narrator_handler = re.search(
        r"document\.getElementById\('open-narrator-rules'\)\.onclick = async \(\) => \{(?P<body>.*?)\n\};",
        script,
        flags=re.DOTALL,
    )
    world_handler = re.search(
        r"document\.getElementById\('open-world-building'\)\.onclick = async \(\) => \{(?P<body>.*?)\n\};",
        script,
        flags=re.DOTALL,
    )
    assert narrator_handler, "Narrator Rules handler is missing."
    assert world_handler, "World Building handler is missing."
    assert "openPrimaryModal('narrator-rules-modal');" in narrator_handler.group("body")
    assert "openPrimaryModal('world-building-modal');" in world_handler.group("body")


def test_creator_mode_confirmation_handler_still_opens_confirmation_modal() -> None:
    script = Path("app/static/app.js").read_text(encoding="utf-8")
    assert "openCreatorModeConfirmation();" in script
    assert "openDialog('creator-mode-confirm-modal');" in script


def test_new_campaign_form_is_campaign_focused_by_default() -> None:
    html = _index_html()
    modal = html[html.index('id="new-campaign-modal"'):html.index('id="campaign-browser-modal"')]
    assert 'id="form-campaign-name"' in modal
    assert 'id="form-world-theme"' in modal
    assert 'id="form-tone"' in modal
    assert 'id="form-premise"' in modal
    assert 'Advanced Campaign Rules' in modal
    assert 'class="character-sheets-entry"' not in modal
    assert '<h4>Character Sheets Manager</h4>' in modal
    assert 'id="character-sheets-manager" class="character-sheets-manager hidden"' in modal
    for step in [
        "Campaign Basics",
        "Play Style",
        "Rules Style",
        "Character Identity",
        "Character Description",
        "Power Level",
        "Starting Abilities",
        "Starting Items",
        "Review",
    ]:
        assert step in modal
    assert 'id="form-player-name" type="text" required' in modal
    assert 'id="form-player-class" type="text" required' in modal
    assert 'id="create-campaign-confirm" class="hidden"' in modal
    assert "ComfyUI" not in modal
    assert 'advanced-campaign-rules' in modal


def test_wizard_option_groups_render_as_option_cards() -> None:
    html = _index_html()
    assert 'class="wizard-option-card"' in html
    assert html.count('class="wizard-option-card"') >= 18
    assert '<label><input name="form-play-style-choice"' not in html


def test_wizard_selected_options_have_card_styling() -> None:
    css = Path("app/static/styles.css").read_text(encoding="utf-8")
    html = _index_html()
    assert '.wizard-option-card:has(input:checked)' in css
    assert 'name="form-play-style-choice" type="radio" value="Storybook Mode" checked' in html
    assert 'name="form-rules-style-choice" type="radio" value="Hybrid" checked' in html
    assert 'name="form-power-level-choice" type="radio" value="Capable Adventurer" checked' in html
    assert 'name="form-ability-mode" type="radio" value="suggest" checked' in html
    assert 'name="form-item-mode" type="radio" value="suggest" checked' in html


def test_campaign_intelligence_uses_file_picker_not_source_path_field() -> None:
    html = _index_html()
    script = Path("app/static/app.js").read_text(encoding="utf-8")
    styles = Path("app/static/styles.css").read_text(encoding="utf-8")

    assert 'id="intelligence-source-path"' not in html
    assert 'id="add-intelligence-source-file" class="hidden" type="file" accept=".txt,.md,.json"' in html
    assert 'id="replace-intelligence-source-file" class="hidden" type="file" accept=".txt,.md,.json"' in html
    assert "addIntelligenceSourceButton?.addEventListener('click', openAddIntelligenceFilePicker);" in script
    assert "FormData" in script
    assert "Choose a .txt, .md, or .json file." in script
    assert "Import failed: unsupported file type." in script
    assert "Replace failed: select a source first." in script
    assert "intelligence-source-card${selectedClass}" in script
    assert ".intelligence-source-card.selected" in styles
