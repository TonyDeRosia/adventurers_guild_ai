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


def test_smart_mud_layout_uses_terminal_prompt_and_compact_command_row() -> None:
    html = _index_html()
    assert 'class="smart-mud-mode"' in html
    assert 'id="dialogue-panel"' in html
    assert 'id="dialogue-feed" class="dialogue-feed mud-world-output"' in html
    assert 'id="mud-player-prompt"' in html
    assert 'class="input-bar compose-bar mud-command-row"' in html
    assert 'class="btn-primary mud-send-button"' in html
    assert 'id="mud-menu-settings"' in html
    for removed in ['mud-menu-character', 'mud-menu-inventory', 'mud-menu-equipment', 'mud-menu-spellbook', 'mud-menu-journal']:
        assert f'id="{removed}"' not in html
    assert 'id="mud-colors-settings"' in html
    assert 'id="mud-color-preset"' in html
    assert 'id="mud-color-roles"' in html
    assert 'legacy-sidebar' in html
    assert html.index('id="dialogue-feed"') < html.index('id="mud-player-prompt"') < html.index('id="chat-input"')
    assert 'Campaign Log' not in html
    assert 'Adventure Panel' not in html
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


def test_new_character_form_is_smart_mud_focused_by_default() -> None:
    html = _index_html()
    modal = html[html.index('id="new-campaign-modal"'):html.index('id="campaign-browser-modal"')]
    for step in [
        "Choose World",
        "Choose Race",
        "Choose Class",
        "Enter Character Name",
        "Describe Appearance",
        "Review and Enter World",
    ]:
        assert step in modal
    for legacy_text in ["Campaign Basics", "Play Style", "Rules Style", "story mode", "power level", "background", "goal"]:
        assert legacy_text.lower() not in modal.lower()
    assert 'id="form-player-name" type="text" required' in modal
    assert 'id="form-player-class" type="text" required' in modal
    assert 'id="form-species" type="text"' in modal
    assert 'id="form-player-concept"' in modal
    assert 'id="create-campaign-confirm" class="hidden"' in modal
    assert "ComfyUI" not in modal


def test_smart_mud_settings_are_player_facing_by_default() -> None:
    html = _index_html()
    modal = html[html.index('id="setup-modal"'):]
    default_view = modal[:modal.index('id="developer-tools-panel"')]
    for text in ["Font size", "Font family", "Terminal width", "Command echo", "Show timestamps", "MUD Colors", "Show Developer Tools"]:
        assert text in default_view
    assert 'class="panel-block developer-tool-section hidden"' in default_view
    assert 'id="developer-tools-panel" class="panel-block hidden"' in modal
    for player_facing in ["Campaign Mode", "Campaign Rules", "Story DM"]:
        assert player_facing in default_view
    for hidden in ["ComfyUI", "Image Addon", "Campaign Intelligence Library", "GM Orchestrator Inspector", "MUD Memory Inspector"]:
        assert hidden not in default_view


def test_wizard_option_groups_render_as_option_cards() -> None:
    html = _index_html()
    assert 'class="wizard-option-card"' in html
    assert html.count('class="wizard-option-card"') >= 8
    assert '<label><input name="form-play-style-choice"' not in html


def test_wizard_selected_options_have_card_styling() -> None:
    css = Path("app/static/styles.css").read_text(encoding="utf-8")
    html = _index_html()
    assert '.wizard-option-card:has(input:checked)' in css
    assert 'name="form-play-style-choice" type="radio" value="Storybook Mode" checked' in html
    assert 'name="form-rules-style-choice" type="radio" value="Hybrid" checked' in html
    assert 'name="form-power-level-choice"' not in html
    assert 'name="form-ability-mode"' not in html
    assert 'name="form-item-mode"' not in html


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


def test_journal_button_uses_separate_pending_badge() -> None:
    html = _index_html()
    assert '<button id="open-campaign-events" type="button">Journal <span id="campaign-events-pending-count" class="badge hidden">0</span></button>' in html
    assert 'Journal [' not in html


def test_spellbook_label_logic_exists_for_mage_and_non_mage_roles() -> None:
    script = Path("app/static/app.js").read_text(encoding="utf-8")
    assert "function updateAbilityToolLabel" in script
    assert "isSpellcastingRoleText(roleText) ? 'Spellbook' : 'Abilities'" in script
    assert "mage|wizard|sorcerer|warlock|cleric|druid|necromancer|spellblade" in script
