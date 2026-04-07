from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from engine.campaign_engine import CampaignEngine
from engine.entities import CampaignState, LongTermMemoryEntry, SessionSummary
from engine.game_state_manager import GameStateManager
from prompts.renderer import PromptRenderer
from engine.save_manager import SaveManager
from memory.retrieval import MemoryRetrievalPipeline, RetrievalRequest
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
    assert state.player.agility == 4
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
    assert loaded.faction_reputation == {}
    assert loaded.quest_outcomes == {}
    assert loaded.world_events == []
    assert loaded.combat_effects == {}
    assert loaded.settings.content_settings.tone == "heroic"
    assert loaded.settings.content_settings.maturity_level == "standard"
    assert loaded.world_meta.world_name == "Untitled World"
    assert loaded.world_meta.starting_location_name == "Moonfall Town"


def test_stats_affect_combat_and_defend_action(monkeypatch) -> None:
    state = load_state()
    engine = CampaignEngine(NullNarrationAdapter(), data_dir=Path("data"))
    state.player.strength = 6
    state.player.vitality = 4
    state.active_enemy_id = "bone_warden"
    state.active_enemy_hp = 14

    rolls = iter([(14, 20), (18, 22)])
    monkeypatch.setattr("rules.combat.roll_d20", lambda bonus: next(rolls))
    monkeypatch.setattr("rules.combat.roll_die", lambda sides: 6)

    attack_turn = engine.run_turn(state, "attack")
    assert any("for 8 damage" in msg for msg in attack_turn.system_messages)

    state.player.hp = 20
    state.active_enemy_hp = 10
    defend_rolls = iter([(18, 22)])
    monkeypatch.setattr("rules.combat.roll_d20", lambda bonus: next(defend_rolls))
    monkeypatch.setattr("rules.combat.roll_die", lambda sides: 6)
    engine.run_turn(state, "defend")
    assert state.player.hp == 18


def test_branching_quest_outcomes_and_reputation_changes(monkeypatch) -> None:
    state = load_state()
    engine = CampaignEngine(NullNarrationAdapter(), data_dir=Path("data"))
    state.quests["q_catacomb_blight"].status = "active"
    state.player.inventory.append("moonsigil_relic")
    talk = engine.run_turn(state, "talk elder_thorne")
    assert state.quests["q_catacomb_blight"].status == "completed"
    assert state.quest_outcomes["q_catacomb_blight"] == "item"
    assert state.faction_reputation["guild"] >= 2
    assert any("seals the crypt entrance" in msg.lower() for msg in talk.system_messages)

    state = load_state()
    engine = CampaignEngine(NullNarrationAdapter(), data_dir=Path("data"))
    engine.run_turn(state, "talk elder_thorne")
    engine.run_turn(state, "choose 1")
    engine.run_turn(state, "move moonfall_catacombs")
    rolls = iter([(18, 21), (10, 13), (18, 21)])
    monkeypatch.setattr("rules.combat.roll_d20", lambda bonus: next(rolls))
    monkeypatch.setattr("rules.combat.roll_die", lambda sides: 8)
    engine.run_turn(state, "attack")
    engine.run_turn(state, "attack")
    assert state.quest_outcomes["q_catacomb_blight"] == "combat"


def test_relationship_tier_transitions_and_dialogue_gating() -> None:
    state = load_state()
    engine = CampaignEngine(NullNarrationAdapter(), data_dir=Path("data"))
    state.faction_reputation["town"] = 2
    state.npcs["elder_thorne"].disposition = 25
    state.npcs["elder_thorne"].relationship_tier = "friendly"
    state.npcs["elder_thorne"].dynamic_state.trust_toward_player = 8

    first = engine.run_turn(state, "talk elder_thorne")
    assert any("safer way than direct combat" in msg.lower() for msg in first.system_messages)

    state.npcs["elder_thorne"].disposition = -30
    state.npcs["elder_thorne"].relationship_tier = "hostile"
    hostile = engine.run_turn(state, "talk elder_thorne")
    assert not any("safer way than direct combat" in msg.lower() for msg in hostile.system_messages)


def test_recommendation_cleanup_removes_alternate_recommendation_labels() -> None:
    engine = CampaignEngine(NullNarrationAdapter(), data_dir=Path("data"))

    narrative = (
        "The torchlight flickers over the crypt door.\n"
        "Your first course of action: inspect the runes before opening it.\n"
        "Next move: keep your hand near your blade."
    )
    cleaned = engine._strip_recommendation_segments(narrative)

    assert "first course of action:" not in cleaned.lower()
    assert "next move:" not in cleaned.lower()
    assert "torchlight flickers" in cleaned.lower()


def test_guidance_request_detection_matches_common_advice_phrases() -> None:
    engine = CampaignEngine(NullNarrationAdapter(), data_dir=Path("data"))
    assert engine._player_requested_guidance("What should I do next?") is True
    assert engine._player_requested_guidance("Any suggestions?") is True
    assert engine._player_requested_guidance("Recommend a next move.") is True
    assert engine._player_requested_guidance("What are my options here?") is True
    assert engine._player_requested_guidance("I attack the ghoul.") is False


def test_prompt_renderer_includes_content_settings_layer() -> None:
    state = load_state()
    state.settings.profile = "dark_fantasy"
    state.settings.narration_tone = "grim"
    state.settings.content_settings.tone = "noir"
    state.settings.content_settings.maturity_level = "mature"
    state.settings.content_settings.thematic_flags = ["political_intrigue", "horror", "romance"]
    state.world_meta.world_name = "Vel Astren"
    state.world_meta.world_theme = "dark fantasy"
    state.world_meta.starting_location_name = "Black Harbor"
    state.world_meta.premise = "The old gods vanished."
    state.world_meta.player_concept = "Exiled ranger."

    prompt = PromptRenderer().build_system_prompt(state)

    assert "[System Tone]" in prompt
    assert "[Campaign Tone]" in prompt
    assert "[Content Settings]" in prompt
    assert "tone=noir" in prompt
    assert "maturity_level=mature" in prompt
    assert "political_intrigue, horror, romance" in prompt
    assert "must never alter combat math" in prompt
    assert "[World Setup]" in prompt
    assert "Vel Astren" in prompt
    assert "Black Harbor" in prompt


def test_campaign_creation_can_disable_content_settings() -> None:
    manager = GameStateManager(Path("data"), Path("data") / "saves")
    state = manager.create_new_campaign(
        player_name="Mira",
        char_class="Mage",
        profile="classic_fantasy",
        mature_content_enabled=True,
        content_settings_enabled=False,
        campaign_tone="heroic",
        maturity_level="mature",
        thematic_flags=["romance", "gore"],
    )

    assert state.settings.content_settings.tone == "heroic"
    assert state.settings.content_settings.maturity_level == "standard"
    assert state.settings.content_settings.thematic_flags == []


def test_main_character_guaranteed_loadout_initializes_runtime_spellbook() -> None:
    manager = GameStateManager(Path("data"), Path("data") / "saves")
    state = manager.create_new_campaign(
        player_name="Mira",
        char_class="Mage",
        profile="classic_fantasy",
        mature_content_enabled=False,
        character_sheets=[
            {
                "id": "sheet_mira",
                "name": "Mira",
                "sheet_type": "main_character",
                "role": "Mage",
                "guaranteed_abilities": [
                    {
                        "name": "Arc Bolt",
                        "type": "spell",
                        "description": "A focused arcane strike.",
                        "cost_or_resource": "5 mana",
                        "cooldown": "1 turn",
                        "tags": ["arcane", "starter"],
                        "notes": "Core opener",
                    }
                ],
            }
        ],
    )
    assert len(state.structured_state.runtime.spellbook) == 1
    assert state.structured_state.runtime.spellbook[0]["name"] == "Arc Bolt"
    assert state.structured_state.runtime.spellbook[0]["type"] == "spell"


def test_memory_retrieval_pipeline_prefers_contextual_entries() -> None:
    state = load_state()
    state.turn_count = 10
    state.current_location_id = "moonfall_town"
    state.quests["q_catacomb_blight"].status = "active"
    state.long_term_memory = [
        LongTermMemoryEntry(
            id="m1",
            category="quest",
            text="q_catacomb_blight advanced in moonfall_town",
            location_id="moonfall_town",
            quest_id="q_catacomb_blight",
            turn=9,
            weight=3,
        ),
        LongTermMemoryEntry(
            id="m2",
            category="npc",
            text="warden_elira distrusts delays",
            location_id="whispering_woods",
            npc_id="warden_elira",
            turn=2,
            weight=1,
        ),
    ]
    state.recent_memory = ["Player action: talk elder_thorne", "Quest q_catacomb_blight set to active."]
    state.session_summaries = [
        SessionSummary(
            turn=8,
            trigger="talk elder_thorne",
            summary="Thorne shared catacomb warning.",
            location_id="moonfall_town",
            quest_ids=["q_catacomb_blight"],
        )
    ]

    pipeline = MemoryRetrievalPipeline()
    result = pipeline.retrieve(
        state,
        RetrievalRequest(
            location_id="moonfall_town",
            active_quest_ids=["q_catacomb_blight"],
            current_npc_id="elder_thorne",
            recent_actions=["talk", "quest"],
            important_world_state=[],
        ),
    )

    assert result.long_term_memory[0].startswith("q_catacomb_blight advanced")
    assert result.session_summaries == ["Thorne shared catacomb warning."]
    assert any("talk elder_thorne" in item for item in result.recent_memory)


def test_analysis_mode_answers_core_questions() -> None:
    state = load_state()
    engine = CampaignEngine(NullNarrationAdapter(), data_dir=Path("data"))
    state.npcs["elder_thorne"].disposition = 30
    state.npcs["elder_thorne"].relationship_tier = "friendly"

    quest_answer = engine.run_turn(state, "analyze what quests are active")
    npc_answer = engine.run_turn(state, "analyze what does this npc think of me")
    recent_answer = engine.run_turn(state, "analyze what happened recently")

    assert any("Active quests:" in msg for msg in quest_answer.system_messages)
    assert any("tier=friendly" in msg for msg in npc_answer.system_messages)
    assert any("Recent actions:" in msg for msg in recent_answer.system_messages)


def test_summary_persistence_and_save_load_compatibility_for_memory(tmp_path: Path) -> None:
    state = load_state()
    engine = CampaignEngine(NullNarrationAdapter(), data_dir=Path("data"))
    engine.run_turn(state, "summarize")
    assert state.session_summaries
    assert state.recent_memory

    manager = SaveManager(tmp_path)
    manager.save(state, "slot_memory")
    loaded = manager.load("slot_memory")

    assert loaded.session_summaries
    assert loaded.recent_memory
    assert isinstance(loaded.long_term_memory, list)

def test_prompt_renderer_includes_character_sheet_guidance_blocks() -> None:
    state = load_state()
    state.character_sheet_guidance_strength = "strong"
    state.character_sheets = [
        __import__('engine.character_sheets', fromlist=['CharacterSheet']).CharacterSheet.from_payload(
            {
                "id": "npc_1",
                "name": "Captain Vey",
                "sheet_type": "npc_or_mob",
                "role": "city watch captain",
                "archetype": "stern protector",
                "level_or_rank": "elite",
                "temperament": "controlled",
                "loyalty": "city council",
                "social_style": "formal",
                "speech_style": "clipped",
                "abilities": ["shield wall"],
                "weaknesses": ["rigid protocol"],
            }
        )
    ]

    prompt = PromptRenderer().build_turn_prompt(
        state,
        action="talk captain",
        location_summary="Moonfall gate",
        memory=MemoryRetrievalPipeline().retrieve(state, RetrievalRequest(location_id=state.current_location_id, active_quest_ids=[], current_npc_id=None, recent_actions=[], important_world_state=[])),
        character_sheet_guidance=["[NPC/Mob Guidance] Captain Vey: strength=strong; role=city watch captain"],
    )
    assert "[Character Sheet Guidance]" in prompt
    assert "Captain Vey" in prompt
