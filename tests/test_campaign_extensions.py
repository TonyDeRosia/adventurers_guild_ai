from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from engine.campaign_engine import CampaignEngine
from engine.entities import CampaignState
from engine.save_manager import SaveManager
from models.base import NullNarrationAdapter


def load_state() -> CampaignState:
    root = Path(__file__).resolve().parent.parent
    return CampaignState.from_dict(__import__("json").loads((root / "data" / "sample_campaign.json").read_text(encoding="utf-8")))


def test_dialogue_branching_updates_quest_and_flags() -> None:
    state = load_state()
    engine = CampaignEngine(NullNarrationAdapter(), data_dir=Path("data"))

    first = engine.run_turn(state, "talk elder_thorne")
    assert any("Type 'choose <number>'" in msg for msg in first.system_messages)

    second = engine.run_turn(state, "choose 1")
    assert state.quests["q_catacomb_blight"].status == "active"
    assert state.world_flags["thorne_trusts_player"] is True
    assert any("lantern sigil" in msg.lower() for msg in second.system_messages)


def test_inventory_use_and_equip_flow() -> None:
    state = load_state()
    engine = CampaignEngine(NullNarrationAdapter(), data_dir=Path("data"))

    state.player.hp = 9
    used = engine.run_turn(state, "use field_draught")
    assert state.player.hp == 17
    assert "field_draught" not in state.player.inventory
    assert any("recover 8 HP" in msg for msg in used.system_messages)

    add = engine.run_turn(state, "take rangers_charm")
    assert any("Ranger's Charm" in msg for msg in add.system_messages)
    equip = engine.run_turn(state, "equip rangers_charm")
    assert state.player.equipped_item_id == "rangers_charm"
    assert state.player.attack_bonus == 4
    assert any("equip Ranger's Charm" in msg for msg in equip.system_messages)


def test_quest_progression_and_branch_consequence(monkeypatch) -> None:
    state = load_state()
    engine = CampaignEngine(NullNarrationAdapter(), data_dir=Path("data"))

    engine.run_turn(state, "talk elder_thorne")
    engine.run_turn(state, "choose 1")
    engine.run_turn(state, "move moonfall_catacombs")

    rolls = iter([(18, 21), (10, 13), (18, 21), (9, 12)])
    monkeypatch.setattr("rules.combat.roll_d20", lambda bonus: next(rolls))
    monkeypatch.setattr("rules.combat.roll_die", lambda sides: 8)

    engine.run_turn(state, "attack")
    finish = engine.run_turn(state, "attack")
    assert state.quests["q_catacomb_blight"].status == "completed"
    assert state.world_flags["catacombs_cleared_violently"] is True
    assert any("defeated" in msg.lower() for msg in finish.system_messages)

    state.quests["q_moonlantern_oath"].status = "active"
    state.player.inventory.append("moonlantern")
    engine.run_turn(state, "move whispering_woods")
    turn = engine.run_turn(state, "talk warden_elira")
    assert state.quests["q_moonlantern_oath"].status == "completed"
    assert state.world_flags["moonlantern_returned"] is True
    assert any("Ranger's Charm" in msg for msg in turn.system_messages)


def test_save_load_with_additive_fields(tmp_path: Path) -> None:
    state = load_state()
    state.player.equipped_item_id = "rangers_charm"
    state.active_dialogue_npc_id = "elder_thorne"
    state.active_dialogue_node_id = "greeting"
    state.world_flags["moonlantern_returned"] = True

    manager = SaveManager(tmp_path)
    manager.save(state, "slotx")
    loaded = manager.load("slotx")

    assert loaded.player.equipped_item_id == "rangers_charm"
    assert loaded.active_dialogue_npc_id == "elder_thorne"
    assert loaded.active_dialogue_node_id == "greeting"
    assert loaded.world_flags["moonlantern_returned"] is True


def test_backward_compatible_load_defaults() -> None:
    legacy = {
        "campaign_id": "legacy",
        "campaign_name": "Legacy Save",
        "turn_count": 1,
        "current_location_id": "moonfall_town",
        "player": {
            "id": "p1",
            "name": "Legacy",
            "char_class": "Fighter",
            "level": 1,
            "hp": 20,
            "max_hp": 20,
            "armor_class": 12,
            "attack_bonus": 3,
            "inventory": ["torch"],
            "xp": 0
        },
        "npcs": {},
        "locations": {
            "moonfall_town": {
                "id": "moonfall_town",
                "name": "Moonfall Town",
                "description": "desc",
                "connections": []
            }
        },
        "quests": {},
        "settings": {}
    }
    loaded = CampaignState.from_dict(deepcopy(legacy))
    assert loaded.player.equipped_item_id is None
    assert loaded.active_dialogue_npc_id is None
    assert loaded.world_flags == {}
