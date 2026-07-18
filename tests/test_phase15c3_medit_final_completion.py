from engine.mud_runtime import MudRuntime
from smart_mud.builder import BuilderService, MobileTemplate
from tests.test_phase15b38_1_medit_oedit_functional import engine_with_pack, text


def complete_mobile_record():
    return {
        "id": "phase15c3_guard", "name": "Phase Guard", "keywords": ["phase", "guard"],
        "entity_type": "npc", "area_id": "starter_guildlands", "zone_id": "guildhall_crossing", "room_description": "A phase guard watches here.", "look_description": "The guard is alert.",
        "level": 8, "default_position": "standing", "spawn_position": "resting",
        "mobile_flags": ["sentinel", "helper"], "affect_flags": ["darkvision"],
        "attributes": {"strength": 14, "dexterity": 12, "constitution": 13, "intelligence": 10, "wisdom": 10, "charisma": 8},
        "resources": {"health": {"maximum": 120, "starting": 100, "enabled": True}, "mana": {"maximum": 20, "starting": 10, "enabled": True}},
        "combat_profile": {"attack_type": "slash", "natural_weapons": [{"id": "sword_arm", "family": "slash", "damage_dice": "2d6", "selection_weight": 10}]},
        "equipment_loadout": {"equipped": {"mainhand": {"item_template_id": "iron_sword", "quantity": 1, "chance": 100}}, "carried": [{"item_template_id": "ration", "quantity": 2, "chance": 100}]},
        "starting_inventory": [{"item_template_id": "ration", "quantity": 1}],
        "loot": {"corpse_enabled": True, "profile_id": "guard_loot", "entries": [{"item_template_id": "iron_sword", "quantity": 1, "chance": 25}]},
        "combat_abilities": [{"id": "guard_bash", "ability_id": "power_strike", "trigger": "every_round", "target_selector": "current_enemy", "chance": 60, "cooldown": 2, "uses_per_combat": 3}],
        "event_reactions": [{"id": "guard_spawn", "event_type": "spawn", "action_type": "say", "target_selector": "room", "action_data": {"message": "On duty."}}],
        "script_attachments": [{"id": "guard_script", "script_id": "guard_patrol", "trigger": "spawn"}],
        "faction_id": "town_guard",
    }


def test_phase15c3_validation_preview_and_projection_are_single_source():
    tmpl = MobileTemplate.from_legacy(complete_mobile_record())
    issues = tmpl.validate()
    assert not [i for i in issues if i["severity"] == "error"]
    warnings = {i["code"] for i in issues if i["severity"] == "warning"}
    assert "script_runtime_host_deferred" in warnings
    projection = tmpl.to_runtime_projection()
    assert projection["combat_abilities"][0]["runtime_supported"] is True
    assert projection["event_reactions"][0]["runtime_supported"] is True
    assert projection["script_attachments"][0]["runtime_supported"] is False
    assert "script host" in projection["script_attachments"][0]["runtime_decision_reason"]


def test_phase15c3_builder_publish_validation_uses_advanced_mobile_template(isolated_builder_world):
    engine, actor = engine_with_pack(isolated_builder_world)
    actor.role = actor.account_role = "admin"
    svc: BuilderService = engine.builder_service
    rec = complete_mobile_record(); rec["combat_abilities"][0]["chance"] = 140
    assert svc.create_or_update_mobile(actor, rec["id"], rec).ok
    result = svc.validate_object(actor, "entities", rec["id"])
    assert not result.ok
    assert "Chance must be 0-100" in result.message


def test_phase15c3_runtime_spawn_materializes_builder_projection(monkeypatch):
    rt = MudRuntime.__new__(MudRuntime)
    rt.entity_templates = {"phase15c3_guard": MobileTemplate.from_legacy(complete_mobile_record()).to_canonical_dict()}
    rt.ENTITY_TYPES = {"npc", "mob", "object", "corpse"}
    rt.active_world_id = "test"
    rt._template_presentation_hash = lambda _tmpl: "hash"
    captured = {}
    class Store: db_path = ":memory:"
    rt.state_store = Store()
    monkeypatch.setattr("sqlite3.connect", lambda _path: type("C", (), {"__enter__": lambda s: s, "__exit__": lambda *a: None, "execute": lambda s, _sql, payload: captured.setdefault("payload", payload)})())
    rt.find_entity = lambda eid: {"entity_id": eid, "is_alive": False}
    rt._publish_entity_event = lambda *a, **k: None
    ent = rt.spawn_entity("phase15c3_guard", room_id="room1")
    assert ent["entity_id"].startswith("ent_")
    state = __import__("json").loads(captured["payload"][13])
    plugin = __import__("json").loads(captured["payload"][17])
    assert state["current_state"] == "resting"
    assert state["current_health"] == 100
    assert plugin["builder_runtime_projection"]["combat_abilities"][0]["ability_id"] == "power_strike"
    assert plugin["builder_runtime_projection"]["event_reactions"][0]["action_type"] == "say"
