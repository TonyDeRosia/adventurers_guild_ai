from types import SimpleNamespace

import pytest

from engine.mud_displays import (
    CharacterDisplaySnapshot,
    build_score_document,
    render_display_html,
    render_display_plain,
)
from engine.mud_commands import MudCommandEngine


def frozen_snapshot():
    return CharacterDisplaySnapshot(
        character_id="c1",
        identity={"character_id": "c1", "display_name": "Aster", "title": "the Bold"},
        race={"availability": "unavailable"},
        character_class={"availability": "unsupported"},
        level=7,
        alignment="Good",
        age={"display": "22 years old"},
        time={"play_time": "1 day, 2 hours"},
        progression={"xp": {"label": "Experience", "value": 12345, "display_format": "thousands", "display_order": 10}, "xp_to_next_level": {"label": "TNL", "value": 55, "display_order": 20}, "practice_points": 3, "training_points": 2},
        resources={"hp": 5, "max_hp": 10, "mana": 7, "max_mana": 8, "stamina": 9, "max_stamina": 12},
        attributes={"might": {"label": "Might", "value": 14, "display_order": 20}, "grace": {"label": "Grace", "value": 13, "display_order": 10}},
        offense={"accuracy": {"label": "Accuracy", "value": 71, "unit": "percentage", "display_order": 10}, "hit_bonus": {"label": "Hit Bonus", "value": 4}},
        defense={"armor": {"label": "Armor", "value": 12}, "parry": {"label": "Parry", "value": 0, "active": False, "inactive_reason": "Not consumed by combat yet."}},
        criticals={"critical_melee": {"label": "Melee Critical", "value": 5, "unit": "percentage"}},
        saves={"physical": {"label": "Physical Save", "value": 8}, "mental": {"label": "Mental Save", "value": 9}, "magic": {"label": "Magic Save", "value": 10}},
        resistances={"custom_void": {"label": "Void", "value": -5, "unit": "percentage"}},
        weapon_profile={"weapon_name": "Iron Longsword", "minimum_damage": 8, "maximum_damage": 13, "damage_type": "slashing", "attack_speed": 2},
        unarmed_profile={"minimum_damage": 1, "maximum_damage": 2, "damage_type": "blunt"},
        speed={"initiative": {"label": "Initiative", "value": 3}, "movement_speed": {"label": "Movement Speed", "value": 100, "unit": "percentage"}},
        carrying={"current_weight": {"label": "Current Carry Weight", "value": 42, "unit": "lb"}, "carry_capacity": {"label": "Carry Capacity", "value": 100, "unit": "lb"}},
        encumbrance={"encumbrance_percent": {"label": "Encumbrance", "value": 42, "unit": "percentage"}, "encumbrance_state": {"label": "State", "value": "Unburdened"}},
        survival={"posture": "standing", "hunger": {"label": "Hunger", "value": "Satisfied"}},
        effects=({"name": "Blessing <script>", "classification": "beneficial", "remaining": "5 minutes", "stacks": 2}, {"name": "Poison", "classification": "harmful"}),
        location={"world": {"label": "World", "value": "Shattered Realms"}, "room_name": {"label": "Room", "value": "Old Gate"}},
        currency={"gold": {"label": "Gold", "value": 99}},
        mechanics={"pk_status": {"label": "PK Status", "value": "Protected"}},
        source_versions={"snapshot": "phase13c3-b.snapshot.v1", "combat": "combat-v1"},
    )


def test_score_renders_adventurers_lair_sheet_without_modern_sections():
    text = render_display_plain(build_score_document(snapshot=frozen_snapshot(), mode="full"))
    assert "RESOURCES" not in text
    assert "HP:" not in text and "Mana:" not in text and "Stamina:" not in text
    assert "PRIMARY STATISTICS" not in text
    assert "SECONDARY COMBAT STATISTICS" not in text
    assert "Name: Aster" in text and "Title: the Bold" in text
    assert "Race: Unavailable" in text
    assert "Class: Not implemented" in text
    assert "Exp:" in text and "TNL:" in text
    assert "Carry Capacity:" in text
    assert "Base Stats:" in text and "Armor:" in text and "Hitroll" in text
    assert "Resistances" not in text and "Speed" not in text and "ACTIVE EFFECTS" not in text


def test_score_compact_keeps_same_adventurers_lair_layout_and_html_escapes():
    doc = build_score_document(snapshot=frozen_snapshot(), mode="compact")
    text = render_display_plain(doc)
    assert "ACTIVE EFFECTS" not in text
    html = render_display_html(build_score_document(snapshot=frozen_snapshot(), mode="full"))
    assert '&lt;script&gt;' not in html  # effects are not part of normal AL score
    assert '<script>' not in html


def test_score_requires_v1_snapshot_and_detailed_permission():
    bad = CharacterDisplaySnapshot(schema_version="old", snapshot_version="old")
    with pytest.raises(ValueError):
        build_score_document(snapshot=bad)
    with pytest.raises(PermissionError):
        build_score_document(snapshot=frozen_snapshot(), mode="detailed", detailed_allowed=False)
    assert "IMMORTAL INFORMATION" in render_display_plain(build_score_document(snapshot=frozen_snapshot(), mode="detailed", detailed_allowed=True))


def test_score_command_uses_snapshot_service_once_and_routes_sc():
    class Service:
        def __init__(self): self.calls = 0
        def build_snapshot(self, character):
            self.calls += 1
            return frozen_snapshot()
    svc = Service()
    engine = MudCommandEngine()
    engine.character_display_snapshots = svc
    character = SimpleNamespace(name="Aster", role="admin")
    result = engine._cmd_score(character, ["full"], "score full")
    assert result.ok
    assert svc.calls == 1
    assert result.state_updates["snapshot_version"] == "phase13c3-b.snapshot.v1"
    result = engine._cmd_score(character, [], "sc")
    assert result.ok
    assert svc.calls == 2


def test_combatstats_modes_use_canonical_snapshot():
    engine = MudCommandEngine()
    character = SimpleNamespace(id="hero", name="Hero", level=1, hp=50, mana=20, stamina=20, attributes={"strength": 12, "dexterity": 11, "constitution": 10, "intelligence": 9, "wisdom": 8, "charisma": 7})
    assert "OFFENSE" in engine._cmd_combatstats(character, ["offense"], "combatstats offense").narrative
    assert "DEFENSE" in engine._cmd_combatstats(character, ["defense"], "combatstats defense").narrative
    assert "SAVES" in engine._cmd_combatstats(character, ["saves"], "combatstats saves").narrative
    assert "RESISTANCES" in engine._cmd_combatstats(character, ["resistances"], "combatstats resistances").narrative
    assert "DAMAGE" in engine._cmd_combatstats(character, ["damage"], "combatstats damage").narrative
    assert "COMBAT STAT BREAKDOWN" in engine._cmd_combatstats(character, ["breakdown", "accuracy"], "combatstats breakdown accuracy").narrative
