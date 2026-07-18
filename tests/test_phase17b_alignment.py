from types import SimpleNamespace

from engine.mud_displays import CharacterDisplaySnapshot, build_score_document, render_display_plain
from smart_mud.builder import BuilderService, BuilderWorkspace, MobileTemplate


def _score_snapshot(alignment=896):
    return CharacterDisplaySnapshot(
        character_id="hero",
        identity={"display_name": "Aster", "title": "the Bold", "alignment": alignment},
        race={"name": "Human", "availability": "available"},
        character_class={"name": "Warrior", "availability": "available"},
        level=7,
        alignment=alignment,
        age={"display": "22 years old"},
        resources={"hp": 5000, "max_hp": 5000, "mana": 6325, "max_mana": 6325, "movement": 5177, "max_movement": 5733},
        progression={"xp": 12345, "xp_to_next_level": 55},
        attributes={"strength": {"value": 14}, "intelligence": {"value": 11}, "wisdom": {"value": 10}, "dexterity": {"value": 13}, "constitution": {"value": 12}, "charisma": {"value": 8}},
        offense={"hit_bonus": {"value": 4}, "damage_bonus": {"value": 3}, "accuracy": {"value": 82}},
        defense={"armor": {"value": 12}, "evasion": {"value": 7}},
        saves={"magic": {"value": 10}},
        criticals={"critical_melee": {"value": 5}, "critical_spell": {"value": 2}, "critical_heal": {"value": 1}},
        carrying={"current_weight": 42, "carry_capacity": 100, "encumbrance_text": "Moderate"},
        currency={"gold": 99, "diamonds": 0, "glory": 0, "bank": 4},
        time={"play_time": "1 day, 2 hours"},
        survival={"hunger": "Satisfied", "thirst": "Quenched"},
    )


def test_score_resource_row_includes_alignment_and_border_safe():
    text = render_display_plain(build_score_document(snapshot=_score_snapshot()))
    assert "HP: 5000/5000  Mana: 6325/6325  Move: 5177/5733  Alignment: 896" in text
    for line in text.splitlines():
        assert len(line) == 81


def test_score_alignment_numeric_edges():
    for value in (0, 1000, -1000):
        text = render_display_plain(build_score_document(snapshot=_score_snapshot(value)))
        assert f"Alignment: {value}" in text
        assert all(len(line) == 81 for line in text.splitlines())


def actor(name="Tony", role="admin"):
    return SimpleNamespace(id=name.lower(), name=name, account_id="acct", role=role, world_id="test_world", room_id="start")


def test_medit_alignment_edit_validation_undo_redo_save_reopen(tmp_path):
    s = BuilderService(BuilderWorkspace(worlds_dir=tmp_path)); a = actor()
    assert s.acquire_lock(a, "entities", "phase17b_mob").ok
    assert s.mutate(a, "entities", "phase17b_mob", {"name": "Phase Mob", "description": "A test mob.", "room_description": "A test mob waits here.", "look_description": "A test mob.", "resources": {"health": {"maximum": 10, "starting": 10}}, "alignment": 0}).ok
    s.release_lock(a, "entities", "phase17b_mob")
    assert "Mob ID" in s.start_editor(a, "medit", "entities", "phase17b_mob").message
    stats = s.sessions.handle(a, "stats").message
    assert "Alignment" in stats
    assert "Current alignment: 0" in s.sessions.handle(a, "D").message
    assert "numeric" in s.sessions.handle(a, "abc").message
    assert "outside" in s.sessions.handle(a, "2500").message
    cancelled = s.sessions.handle(a, "Q").message
    assert "Mob ID" in cancelled and s.sessions.active[s.sessions.actor_key(a)].working_record["alignment"] == 0
    s.sessions.handle(a, "stats")
    s.sessions.handle(a, "D")
    changed = s.sessions.handle(a, "-350").message
    assert "Alignment" in changed and "-350" in changed
    assert s.sessions.active[s.sessions.actor_key(a)].working_record["alignment"] == -350
    assert "Session undo applied" in s.sessions.handle(a, "undo").message
    assert s.sessions.active[s.sessions.actor_key(a)].working_record["alignment"] == 0
    assert "Session redo applied" in s.sessions.handle(a, "redo").message
    assert s.sessions.active[s.sessions.actor_key(a)].working_record["alignment"] == -350
    assert s.sessions.handle(a, "save").ok
    assert s.sessions.handle(a, "quit").ok
    reopened = s.start_editor(a, "medit", "entities", "phase17b_mob").message
    assert "Mob ID" in reopened
    assert "-350" in s.sessions.handle(a, "stats").message


def test_mobile_runtime_projection_preserves_positive_neutral_negative_alignment():
    for value in (750, 0, -750):
        rec = {"id": f"mob_{value}", "name": "Mob", "keywords": ["mob"], "room_description": "Mob is here.", "look_description": "Mob.", "resources": {"health": {"maximum": 10, "starting": 10}}, "alignment": value}
        assert MobileTemplate.from_legacy(rec).to_runtime_projection()["alignment"] == value
