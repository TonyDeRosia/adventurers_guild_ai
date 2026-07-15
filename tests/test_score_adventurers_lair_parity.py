from engine.display_services import CarryingDisplaySource
from engine.mud_displays import CharacterDisplaySnapshot, build_score_document, render_display_plain


def _snapshot():
    return CharacterDisplaySnapshot(
        character_id="hero",
        identity={"display_name": "Aster", "title": "the Bold"},
        race={"name": "Human", "availability": "available"},
        character_class={"name": "Warrior", "availability": "available"},
        level=7,
        age={"display": "22 years old", "birthday": "You were born on the Day of Thunder."},
        alignment="Good",
        progression={"xp": 12345, "xp_to_next_level": 55, "practice_points": 3, "training_points": 2, "quest_points": 9, "remorts": 1},
        attributes={"strength": {"value": 14}, "intelligence": {"value": 11}, "wisdom": {"value": 10}, "dexterity": {"value": 13}, "constitution": {"value": 12}, "charisma": {"value": 8}},
        offense={"hit_bonus": {"value": 4}, "damage_bonus": {"value": 3}, "accuracy": {"value": 82}},
        defense={"armor": {"value": 12}, "evasion": {"value": 7}},
        saves={"magic": {"value": 10}},
        criticals={"critical_melee": {"value": 5, "unit": "percentage"}, "critical_spell": {"value": 2}, "critical_heal": {"value": 1}},
        carrying={"current_weight": 42, "carry_capacity": 100, "item_count": 6, "max_item_count": 30, "encumbrance_text": "Moderate"},
        currency={"gold": 99, "diamonds": 0, "glory": 0, "bank": 4},
        time={"play_time": "1 day, 2 hours"},
        survival={"hunger": "Satisfied", "thirst": "Quenched"},
        conditions=[{"name": "You are standing."}],
        source_versions={"combat": "combat-v1"},
    )


def test_score_matches_adventurers_lair_line_order_and_removes_modern_sections():
    text = render_display_plain(build_score_document(snapshot=_snapshot()))
    lines = text.splitlines()
    assert lines[0].startswith("╔") and len(lines[0]) == 81
    joined = "\n".join(lines)
    ordered = ["CHARACTER STATUS", "Name: Aster", "Title: the Bold", "Race: Human", "Age: 22 years old", "Exp:", "Carry Capacity:", "Base Stats:", "Armor:", "Gold:", "Quests completed:", "Play time:", "Hunger:"]
    positions = [joined.index(token) for token in ordered]
    assert positions == sorted(positions)
    for forbidden in ["PRIMARY STATISTICS", "SECONDARY COMBAT", "Damage", "Resistances", "Speed", "Mechanics", "Location", "ACTIVE EFFECTS", "HP:", "Mana:", "Movement:"]:
        assert forbidden not in joined


def test_score_detailed_is_immortal_only_diagnostics():
    normal = render_display_plain(build_score_document(snapshot=_snapshot()))
    snap = _snapshot()
    snap = CharacterDisplaySnapshot(**{**snap.__dict__, "identity": {**snap.identity, "immortal": True, "builder_zone": "old_gate"}})
    immortal = render_display_plain(build_score_document(snapshot=snap, mode="detailed", detailed_allowed=True))
    assert "IMMORTAL INFORMATION" not in normal
    assert "IMMORTAL INFORMATION" not in immortal
    assert "POOFIN: Aster appears with an ear-splitting bang." in immortal
    assert "Your current zone: old_gate" in immortal


def test_carrying_source_does_not_sum_inventory_in_display_layer():
    c = {"inventory": [{"weight": 10}, {"weight": 5}], "max_item_count": 30}
    snap = CarryingDisplaySource().snapshot(c)
    assert "current_weight" not in snap
    assert "item_count" not in snap
