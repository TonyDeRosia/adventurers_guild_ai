from smart_mud.builder import MobileTemplate
from tests.test_phase15b38_1_medit_oedit_functional import engine_with_pack, text


def test_phase15c2b_advanced_sections_normalize_validate_and_project():
    rec = {
        "id": "advanced_mob", "name": "Advanced Mob", "keywords": "advanced mob",
        "room_description": "An advanced mob waits here.", "look_description": "Advanced.",
        "resources": {"health": {"maximum": 50, "starting": 50, "enabled": True}, "mana": {"maximum": 10, "starting": 10, "enabled": True}},
        "combat_profile": {"natural_weapons": [{"id": "claw", "family": "claw"}]},
        "combat_abilities": [{"ability_id": "power_strike", "trigger": "every_round", "target": "current_enemy", "chance": "50%", "cooldown": 2, "required_status": "enraged", "forbidden_status": "asleep"}],
        "event_reactions": [{"event": "spawn", "action": "say", "action_data": {"message": "Ready."}, "target": "room"}],
        "scripts": ["legacy_guard_script"],
    }
    canonical = MobileTemplate.from_legacy(rec).to_canonical_dict()
    assert canonical["combat_abilities"][0]["id"] == "power_strike"
    assert canonical["combat_abilities"][0]["chance"] == 50
    assert canonical["event_reactions"][0]["event_type"] == "spawn"
    assert canonical["script_attachments"][0]["script_id"] == "legacy_guard_script"
    projection = MobileTemplate.from_legacy(rec).to_runtime_projection()
    assert projection["combat_abilities"][0]["ability_id"] == "power_strike"
    assert projection["event_reactions"][0]["action_type"] == "say"
    assert projection["script_attachments"][0]["script_id"] == "legacy_guard_script"
    issues = MobileTemplate.from_legacy(rec).validate()
    assert not [i for i in issues if i["severity"] == "error"]


def test_phase15c2b_advanced_editor_copy_reorder_toggle_preview_and_validation(isolated_builder_world):
    engine, actor = engine_with_pack(isolated_builder_world)
    assert "Mobile Editor" in text(engine, actor, "medit training_master_borik")
    abilities = text(engine, actor, "combat abilities")
    assert "MEDIT Combat Abilities" in abilities
    assert "entry added" in text(engine, actor, "add power_strike")
    assert "entry updated" in text(engine, actor, "edit 1 cooldown 3")
    assert "entry copied" in text(engine, actor, "copy 1")
    assert "entry moved" in text(engine, actor, "move 2 1")
    assert "entry toggled" in text(engine, actor, "toggle 1")
    assert "Combat ability decision trace" in text(engine, actor, "preview")
    assert "Combat Abilities validation" in text(engine, actor, "validate")
    assert "Mobile Editor" in text(engine, actor, "back")

    reactions = text(engine, actor, "event reactions")
    assert "MEDIT Event Reactions" in reactions
    assert "entry added" in text(engine, actor, "add spawn")
    assert "entry updated" in text(engine, actor, "edit 1 action_type say")
    assert "Event reaction trace" in text(engine, actor, "preview")
    assert "Mobile Editor" in text(engine, actor, "back")

    scripts = text(engine, actor, "scripts")
    assert "MEDIT Script Attachments" in scripts
    assert "entry added" in text(engine, actor, "add guard_script")
    assert "Script attachment dry-run" in text(engine, actor, "preview")
    preview = text(engine, actor, "back")
    assert "Mobile Editor" in preview
    full = text(engine, actor, "preview")
    assert "ABILITY DECISION ORDER" in full and "EVENT REACTIONS" in full and "SCRIPT ATTACHMENTS" in full
