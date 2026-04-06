from pathlib import Path

from engine.entities import CampaignState
from engine.save_manager import SaveManager
from rules.combat import CombatEngine


SAMPLE_STATE = {
    "campaign_id": "t",
    "campaign_name": "Test",
    "turn_count": 0,
    "current_location_id": "l1",
    "player": {
        "id": "p1",
        "name": "Hero",
        "char_class": "Fighter",
        "level": 1,
        "hp": 20,
        "max_hp": 20,
        "armor_class": 12,
        "attack_bonus": 3,
        "inventory": [],
        "xp": 0,
    },
    "npcs": {},
    "locations": {
        "l1": {
            "id": "l1",
            "name": "Camp",
            "description": "test",
            "connections": [],
        }
    },
    "quests": {},
    "active_enemy_id": "bone_warden",
    "active_enemy_hp": 7,
    "settings": {
        "profile": "dark_fantasy",
        "mature_content_enabled": True,
        "narration_tone": "grim",
        "image_generation_enabled": False,
    },
}


def test_combat_result_shape() -> None:
    engine = CombatEngine()
    result = engine.resolve_attack("Hero", 3, "Bandit", 12, 10)
    assert result.attacker == "Hero"
    assert 1 <= result.raw_roll <= 20
    assert 0 <= result.damage <= 8


def test_combat_math_hit_and_damage(monkeypatch) -> None:
    monkeypatch.setattr("rules.combat.roll_d20", lambda bonus: (17, 17 + bonus))
    monkeypatch.setattr("rules.combat.roll_die", lambda sides: 6)
    engine = CombatEngine()
    result = engine.resolve_attack("Hero", 3, "Bandit", 12, 10, damage_die=8)
    assert result.hit is True
    assert result.total_roll == 20
    assert result.damage == 6
    assert result.remaining_hp == 4


def test_combat_math_miss(monkeypatch) -> None:
    monkeypatch.setattr("rules.combat.roll_d20", lambda bonus: (2, 2 + bonus))
    engine = CombatEngine()
    result = engine.resolve_attack("Hero", 1, "Bandit", 12, 10, damage_die=8)
    assert result.hit is False
    assert result.damage == 0
    assert result.remaining_hp == 10


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    state = CampaignState.from_dict(SAMPLE_STATE)
    manager = SaveManager(tmp_path)
    manager.save(state, "slot1")
    loaded = manager.load("slot1")
    assert loaded.campaign_id == "t"
    assert loaded.player.name == "Hero"
    assert loaded.active_enemy_id == "bone_warden"
    assert loaded.active_enemy_hp == 7
    assert loaded.settings.profile == "dark_fantasy"
