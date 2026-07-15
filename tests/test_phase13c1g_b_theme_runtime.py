from types import SimpleNamespace

from engine.display_themes import validate_display_theme, preview_display_theme, resolve_effective_display_theme
from engine.mud_displays import build_score_document, render_display_plain, build_inventory_document, build_equipment_document


def _char(**prefs):
    return SimpleNamespace(
        id="hero", name="Hero", title="Tester", race="Human", character_class="Warrior", level=3,
        hp=10, max_hp=20, mana=5, max_mana=8, stamina=7, max_stamina=9, xp=100,
        xp_to_next_level=50, gold=2, silver=1, attributes={"strength": {"final": 12}},
        calculated_stats={"armor": 4}, inventory=[], equipment={}, preferences=prefs,
    )


def test_theme_frame_width_alignment_labels_borders_preview_runtime():
    raw = {
        "theme_id": "test", "name": "Test", "frame_style": "classic_single", "width": 44,
        "title_alignment": "left", "labels": {"score.title": "ADVENTURER RECORD"},
        "border_characters": {"top_left": "+", "top": "-", "top_right": "+", "side": "|", "bottom_left": "+", "bottom": "-", "bottom_right": "+"},
    }
    assert validate_display_theme(raw) == []
    preview = preview_display_theme(raw, "score")
    assert preview["ok"] == "true"
    assert "+" in preview["plain"] and "ADVENTURER RECORD" in preview["plain"]
    theme = resolve_effective_display_theme(_char(display_theme="minimal_modern"), family="score")
    doc = build_score_document(_char(), theme=theme)
    assert "STATUS" in render_display_plain(doc)


def test_security_rejects_unsafe_theme_fields():
    bad = {
        "theme_id": "bad", "name": "Bad", "frame_style": "huge", "width": 20,
        "title_alignment": "middle", "border_characters": {"top": "<script>"},
        "semantic_roles": {"character_frame": "not_a_role"},
        "section_order": {"score": ["identity", "sql"]},
        "templates": {"score": {"line": "{player.__dict__}"}},
    }
    errors = "\n".join(validate_display_theme(bad))
    assert "unsupported frame_style" in errors
    assert "width" in errors
    assert "unsupported semantic role" in errors
    assert "unsupported section" in errors
    assert "one safe visible character" in errors
    assert "arbitrary expressions" in errors


def test_inventory_and_equipment_are_themed():
    theme = resolve_effective_display_theme(_char(display_theme="classic_adventurer"), family="inventory")
    inv = render_display_plain(build_inventory_document([{"name": "&Ylantern&n", "stack_count": 2}], theme=theme))
    eq = render_display_plain(build_equipment_document([{"equipped_slot": "main_hand", "name": "sword"}], ["main_hand", "off_hand"], theme=theme))
    assert "INVENTORY" in inv and "2x" in inv
    assert "EQUIPMENT" in eq and "sword" in eq
