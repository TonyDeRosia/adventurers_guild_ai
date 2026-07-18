from tests.test_phase15b38_1_medit_oedit_functional import engine_with_pack, text
from smart_mud.builder import MobileRecommendationService, MobileTemplate


def test_phase15c2a_stats_quickbuild_diff_apply_clear_and_preview(isolated_builder_world):
    engine, actor = engine_with_pack(isolated_builder_world)
    menu = text(engine, actor, "medit training_master_borik")
    assert "Stats Menu" in menu and "Runtime activation status" in menu
    stats = text(engine, actor, "stats")
    assert "MEDIT Stats Menu" in stats and "Authored override" in stats and "Recommended" in stats
    assert "Stats value updated" in text(engine, actor, "health 160")
    diff = text(engine, actor, "quickbuild 8 brute")
    assert "Quick Build recommendations (no mutation yet)" in diff and "resources.health" in diff
    applied = text(engine, actor, "applyquick all")
    assert "Quick Build applied as one undo checkpoint" in applied
    assert "Session undo applied" in text(engine, actor, "undo")
    assert "Session redo applied" in text(engine, actor, "redo")
    assert "Stats value updated" in text(engine, actor, "clear health")
    preview = text(engine, actor, "preview")
    assert "RESOLVED STATS" in preview and "COMBAT SNAPSHOT" in preview


def test_phase15c2a_recommendations_deterministic_and_validation_warnings():
    svc = MobileRecommendationService()
    a = svc.recommend(level=10, archetype="caster", resource_style="mana user")
    b = svc.recommend(level=10, archetype="caster", resource_style="mana user")
    assert a == b
    rec = {
        "id": "bad_boss", "name": "Bad Boss", "keywords": ["bad", "boss"],
        "room_description": "A boss is here.", "look_description": "Boss.",
        "level": 10, "archetype": "caster", "mobile_flags": ["boss"],
        "resources": {"health": {"maximum": 1, "starting": 1, "enabled": True}},
        "combat_profile": {"natural_weapons": [{"id": "hit", "family": "hit"}], "experience_reward": 99999},
    }
    issues = MobileTemplate.from_legacy(rec).validate()
    codes = {i["code"] for i in issues}
    assert "balance_low_health" in codes
    assert "balance_excessive_xp" in codes
    assert "caster_without_mana" in codes


def test_phase15c2a_runtime_projection_contains_core_authored_fields():
    rec = {
        "id": "proj_mob", "name": "Projection Mob", "keywords": "projection mob",
        "room_description": "Projection mob waits here.", "look_description": "A projected mob.",
        "level": 3, "default_position": "resting", "spawn_position": "standing",
        "mobile_flags": ["sentinel"], "affect_flags": ["darkvision"],
        "attributes": {"strength": 12},
        "resources": {"health": {"maximum": 44, "starting": 44, "enabled": True}},
        "combat_profile": {"attack_type": "bite", "natural_weapons": [{"id": "bite", "family": "bite"}]},
        "starting_inventory": [{"object_id": "ration", "quantity": 1}],
        "loot": {"entries": [{"object_id": "coin", "quantity": 1}], "corpse_enabled": True},
    }
    proj = MobileTemplate.from_legacy(rec).to_runtime_projection()
    assert proj["keywords"] == ["projection", "mob"]
    assert proj["default_position"] == "resting" and proj["spawn_position"] == "standing"
    assert proj["resources"]["max_health"] == 44
    assert proj["mobile_flags"] == ["sentinel"] and proj["permanent_affects"] == ["darkvision"]
    assert proj["starting_inventory"][0]["item_template_id"] == "ration"
