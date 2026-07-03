from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'app' / 'static' / 'index.html').read_text(encoding='utf-8')
JS = (ROOT / 'app' / 'static' / 'app.js').read_text(encoding='utf-8')
CSS = (ROOT / 'app' / 'static' / 'styles.css').read_text(encoding='utf-8')


def test_settings_are_smart_mud_only() -> None:
    assert 'id="mud-colors-settings"' in HTML
    assert 'id="mud-color-roles"' in HTML
    assert 'Developer Source Library' in HTML
    assert 'AI Context Inspector' in HTML
    for removed in ['ComfyUI', 'Image AI', 'Story DM', 'Narrator Rules', 'Campaign Intelligence Library', 'Campaign Prompt Inspector']:
        assert removed not in HTML


def test_normal_startup_uses_mud_worlds_first() -> None:
    assert "/api/mud/worlds" in JS
    assert "/api/campaign/play-view" not in JS
    assert "campaign_1" not in JS
    assert "refreshDependencyReadiness" not in JS


def test_color_editor_roles_and_live_preview_exist() -> None:
    for role in ['room_name','exit','prompt_hp','prompt_mana','prompt_gold','equipment_item','dialogue']:
        assert role in JS
    assert "type=\"color\"" in JS
    assert "applyColors" in JS


def test_single_scroll_layout_targets_world_output() -> None:
    assert 'body.smart-mud-mode' in CSS
    assert '#mud-world-output' in CSS
    assert 'overflow-y: auto' in CSS
    assert 'overflow: hidden' in CSS
