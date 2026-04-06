from pathlib import Path

from engine.campaign_engine import CampaignEngine
from engine.game_state_manager import GameStateManager
from engine.save_manager import SaveManager
from models.registry import create_model_adapter


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _new_state():
    manager = GameStateManager(DATA_DIR)
    return manager.create_new_campaign("Tester", "Rogue", "classic_fantasy", False)


def _engine():
    return CampaignEngine(create_model_adapter("mock"), data_dir=DATA_DIR)


def test_dialogue_branching_sets_quest_relationship_and_flags() -> None:
    state = _new_state()
    engine = _engine()

    engine.run_turn(state, "talk elder_thorne")
    engine.run_turn(state, "choose 1")
    result = engine.run_turn(state, "choose 1")

    assert state.quests["q_catacomb_blight"].status == "active"
    assert state.npcs["elder_thorne"].relationships[state.player.id] > 10
    assert state.world_flags["moonfall.thorne_trusts_player"] is True
    assert "herbal_draught" in state.player.inventory_item_ids
    assert any("Added 'Herbal Draught'" in msg for msg in result.system_messages)


def test_inventory_use_and_equip_flow() -> None:
    state = _new_state()
    engine = _engine()

    state.player.hp = 10
    engine.run_turn(state, "take Herbal Draught")
    use_result = engine.run_turn(state, "use herbal_draught")
    assert state.player.hp == 18
    assert "recover 8 HP" in " ".join(use_result.system_messages)

    engine.run_turn(state, "take Grave-Iron Dagger")
    equip_result = engine.run_turn(state, "equip grave_iron_dagger")
    assert state.player.equipped_weapon_id == "grave_iron_dagger"
    assert "Equipped weapon" in " ".join(equip_result.system_messages)


def test_quest_progression_with_second_quest_and_turnin() -> None:
    state = _new_state()
    engine = _engine()

    engine.run_turn(state, "move brindlewatch_outpost")
    engine.run_turn(state, "talk captain_mirel")
    engine.run_turn(state, "choose 1")
    engine.run_turn(state, "choose 1")

    assert state.quests["q_supply_line"].status == "active"
    assert "sealed_supply_crate" in state.player.inventory_item_ids

    engine.run_turn(state, "talk captain_mirel")

    assert state.quests["q_supply_line"].status == "completed"
    assert state.world_flags["brindlewatch.supply_line_resolved"] is True


def test_save_load_backward_compatible_with_new_fields(tmp_path: Path) -> None:
    old_shape_payload = {
        "campaign_id": "legacy",
        "campaign_name": "Legacy",
        "turn_count": 2,
        "current_location_id": "moonfall_town",
        "player": {
            "id": "player_1",
            "name": "Legacy Hero",
            "char_class": "Fighter",
            "level": 1,
            "hp": 20,
            "max_hp": 20,
            "armor_class": 12,
            "attack_bonus": 3,
            "inventory": ["Torch"],
            "xp": 0,
        },
        "npcs": {},
        "locations": {
            "moonfall_town": {
                "id": "moonfall_town",
                "name": "Moonfall Town",
                "description": "Town",
                "connections": [],
            }
        },
        "quests": {},
        "world_flags": {},
        "active_enemy_id": None,
        "active_enemy_hp": None,
        "event_log": [],
        "settings": {"profile": "classic_fantasy", "mature_content_enabled": False, "narration_tone": "heroic"},
    }

    save_path = tmp_path / "saves"
    manager = SaveManager(save_path)
    from engine.entities import CampaignState

    legacy_state = CampaignState.from_dict(old_shape_payload)
    manager.save(legacy_state, "legacy")

    loaded = manager.load("legacy")
    upgraded = GameStateManager(DATA_DIR)._apply_additive_defaults(loaded.to_dict())

    assert "inventory_item_ids" in upgraded["player"]
    assert "equipped_weapon_id" in upgraded["player"]
    assert "q_supply_line" in upgraded["quests"]
    assert "brindlewatch_outpost" in upgraded["locations"]
