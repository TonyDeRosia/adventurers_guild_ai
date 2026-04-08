from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from engine.campaign_engine import CampaignEngine
from engine.entities import CampaignState, LongTermMemoryEntry, SessionSummary
from engine.game_state_manager import GameStateManager
from prompts.renderer import PromptRenderer
from engine.save_manager import SaveManager
from memory.retrieval import MemoryRetrievalPipeline, RetrievalRequest
from models.base import NarrationModelAdapter, NullNarrationAdapter


def load_state() -> CampaignState:
    root = Path(__file__).resolve().parent.parent
    return CampaignState.from_dict(__import__("json").loads((root / "data" / "sample_campaign.json").read_text(encoding="utf-8")))


class StaticNarrationAdapter(NarrationModelAdapter):
    provider_name = "test"

    def __init__(self, narrative: str) -> None:
        self.narrative = narrative

    def generate(self, prompt: str, system_prompt: str = "", history: list[object] | None = None) -> str:
        return self.narrative


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


def test_new_ability_is_added_after_successful_use() -> None:
    state = load_state()
    state.settings.play_style.auto_update_character_sheet_from_actions = True
    state.settings.play_style.strict_sheet_enforcement = True
    engine = CampaignEngine(StaticNarrationAdapter("You cast rain spell and the storm answers immediately."), data_dir=Path("data"))

    engine.run_turn(state, "cast rain spell")

    names = [entry.get("name") for entry in state.structured_state.runtime.spellbook]
    assert "Rain Spell" in names


def test_ability_normalization_produces_clean_reusable_names() -> None:
    state = load_state()
    state.settings.play_style.auto_update_character_sheet_from_actions = True
    engine = CampaignEngine(StaticNarrationAdapter("You cast chain lightning and it succeeds."), data_dir=Path("data"))

    engine.run_turn(state, "cast chain lightning in the air")
    assert any(entry.get("name") == "Chain Lightning" for entry in state.structured_state.runtime.spellbook)


def test_summon_and_create_actions_normalize_to_named_abilities() -> None:
    state = load_state()
    state.settings.play_style.auto_update_character_sheet_from_actions = True
    engine = CampaignEngine(StaticNarrationAdapter("You channel primal power and it works."), data_dir=Path("data"))

    engine.run_turn(state, "i summon fire")
    engine.run_turn(state, "i create rain")

    names = [entry.get("name") for entry in state.structured_state.runtime.spellbook]
    assert "Fire Summoning" in names
    assert "Rain Calling" in names


def test_learned_ability_persists_across_turns_and_prompt_injection() -> None:
    state = load_state()
    state.settings.play_style.auto_update_character_sheet_from_actions = True
    engine = CampaignEngine(StaticNarrationAdapter("You cast rain spell and it succeeds."), data_dir=Path("data"))

    engine.run_turn(state, "cast rain spell")
    engine.run_turn(state, "look")

    gm_context = engine.state_orchestrator.build_gm_context(state)
    assert "Rain Spell" in gm_context
    assert any(entry.get("name") == "Rain Spell" for entry in state.structured_state.runtime.spellbook)


def test_duplicate_ability_entries_are_not_created() -> None:
    state = load_state()
    state.settings.play_style.auto_update_character_sheet_from_actions = True
    engine = CampaignEngine(StaticNarrationAdapter("You cast rain spell and it works."), data_dir=Path("data"))

    engine.run_turn(state, "cast rain spell")
    engine.run_turn(state, "cast rain spell")

    matches = [entry for entry in state.structured_state.runtime.spellbook if entry.get("name") == "Rain Spell"]
    assert len(matches) == 1


def test_duplicate_ability_entries_are_prevented_by_fuzzy_similarity() -> None:
    state = load_state()
    state.settings.play_style.auto_update_character_sheet_from_actions = True
    engine = CampaignEngine(StaticNarrationAdapter("You cast chain lightning and it works."), data_dir=Path("data"))

    engine.run_turn(state, "cast chain lightning in the air")
    engine.run_turn(state, "cast chain-lightning")

    matches = [entry for entry in state.structured_state.runtime.spellbook if entry.get("name") == "Chain Lightning"]
    assert len(matches) == 1


def test_strict_mode_recognizes_learned_abilities_after_learning() -> None:
    state = load_state()
    state.settings.play_style.auto_update_character_sheet_from_actions = True
    state.settings.play_style.strict_sheet_enforcement = True
    engine = CampaignEngine(StaticNarrationAdapter("You cast rain spell and it succeeds."), data_dir=Path("data"))

    first = engine.run_turn(state, "cast rain spell")
    second = engine.run_turn(state, "cast rain spell")

    assert any("newly demonstrated" in msg.lower() for msg in first.system_messages)
    assert not any("newly demonstrated" in msg.lower() for msg in second.system_messages)


def test_main_character_sheet_is_auto_created_and_injected_when_missing() -> None:
    state = load_state()
    state.character_sheets = []
    engine = CampaignEngine(StaticNarrationAdapter("You look around carefully."), data_dir=Path("data"))

    engine.run_turn(state, "look")

    assert any(sheet.sheet_type == "main_character" for sheet in state.character_sheets)
    gm_context = engine.state_orchestrator.build_gm_context(state)
    assert "Player capabilities must respect the character sheet unless learning mode is enabled." in gm_context


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


def test_prompt_renderer_includes_narrative_quality_and_agency_guidance() -> None:
    state = load_state()
    system_prompt = PromptRenderer().build_system_prompt(state, requested_mode="play")
    assert "[Storytelling Quality]" in system_prompt
    assert "strong tabletop GM" in system_prompt
    assert "[Player Agency Guardrails]" in system_prompt
    assert "Never force player actions" in system_prompt
    assert "[Dialogue Quality]" in system_prompt


class SequencedNarrationAdapter(NarrationModelAdapter):
    provider_name = "test-sequenced"

    def __init__(self, outputs: list[str]) -> None:
        self.outputs = outputs
        self.calls = 0

    def generate(self, prompt: str, system_prompt: str = "", history=None) -> str:
        self.calls += 1
        if self.outputs:
            return self.outputs.pop(0)
        return "The action lands with visible impact."


def test_latest_action_priority_retries_when_stale_fire_overrides_ice() -> None:
    state = load_state()
    adapter = SequencedNarrationAdapter(
        [
            "Flames engulf him again while torches flicker and patrons lean in.",
            "Ice surges over him, locking his legs in place as frost hardens across the floor.",
        ]
    )
    engine = CampaignEngine(adapter, data_dir=Path("data"))

    state.structured_state.runtime.scene_state = {
        "location_id": state.current_location_id,
        "location_name": state.locations[state.current_location_id].name,
        "recent_consequences": ["fire scorched the pillar"],
        "last_player_action": "cast fireball at the thug",
    }
    result = engine.run_turn(state, "freeze him in ice")

    assert adapter.calls == 2
    assert "ice surges over him" in result.narrative.lower()
    assert result.metadata and result.metadata["retry_used"] is True
    assert result.metadata["retry_reason"] == "action_override"


def test_spell_action_requires_clear_effect_and_impact() -> None:
    state = load_state()
    adapter = SequencedNarrationAdapter(
        [
            "The room feels tense and uncertain as everyone waits.",
            "Your flamestrike crashes down in a white-hot column, blasting the target backward.",
        ]
    )
    engine = CampaignEngine(adapter, data_dir=Path("data"))
    turn = engine.run_turn(state, "cast flamestrike")

    assert "flamestrike" in turn.narrative.lower()
    assert ("crashes" in turn.narrative.lower() or "blasting" in turn.narrative.lower())
    assert turn.metadata and turn.metadata["retry_used"] is True


def test_prompt_renderer_includes_current_action_priority_block() -> None:
    state = load_state()
    prompt = PromptRenderer().build_turn_prompt(
        state,
        action="freeze him in ice",
        location_summary="Moonfall Tavern",
        memory=MemoryRetrievalPipeline().retrieve(
            state,
            RetrievalRequest(location_id=state.current_location_id, active_quest_ids=[], current_npc_id=None, recent_actions=[], important_world_state=[]),
        ),
    )
    assert "CURRENT PLAYER ACTION - HIGHEST PRIORITY" in prompt
    assert "Resolve this action first, then narrate consequences." in prompt


def test_writing_instructions_discourage_summary_style_and_prefer_scene_flow() -> None:
    state = load_state()
    prompt = PromptRenderer().build_turn_prompt(
        state,
        action="look around",
        location_summary="Moonfall Tavern",
        memory=MemoryRetrievalPipeline().retrieve(
            state,
            RetrievalRequest(location_id=state.current_location_id, active_quest_ids=[], current_npc_id=None, recent_actions=[], important_world_state=[]),
        ),
    )
    assert "Write like a scene, not a report" in prompt
    assert "avoid wrappers such as 'Turn X' or 'Outcome summary'" in prompt


def test_writing_instructions_prefer_direct_dialogue_and_readable_spacing() -> None:
    state = load_state()
    prompt = PromptRenderer().build_turn_prompt(
        state,
        action="talk to elder thorne",
        location_summary="Moonfall Tavern",
        memory=MemoryRetrievalPipeline().retrieve(
            state,
            RetrievalRequest(location_id=state.current_location_id, active_quest_ids=[], current_npc_id=None, recent_actions=[], important_world_state=[]),
        ),
    )
    assert "Present speech directly as dialogue" in prompt
    assert "avoid summary phrasing like 'you say' or 'the player says'" in prompt
    assert "Use spacing and paragraph breaks generously" in prompt
    assert "Separate setting, action/reaction, and dialogue into readable blocks" in prompt
    assert "Do not print visible scaffold labels such as [Scene], [Dialogue], [Turn Snapshot], [NPC Reactions], [Enemy/Threat Reactions], or [Immediate Result]" in prompt


def test_model_history_does_not_prefix_narrator_entries_with_outcome_summary_wrapper() -> None:
    state = load_state()
    state.conversation_turns = [
        __import__("engine.entities", fromlist=["ConversationTurn"]).ConversationTurn(
            turn=1,
            player_input="I inspect the sigil.",
            narrator_response="The sigil glows faintly as old runes wake along the stone.",
            system_messages=[],
        )
    ]
    engine = CampaignEngine(NullNarrationAdapter(), data_dir=Path("data"))
    history = engine._build_model_history(state)

    assert len(history) == 2
    assert history[1].role == "assistant"
    assert not history[1].content.lower().startswith("outcome summary:")


def test_system_message_sanitizer_blocks_log_style_wrappers() -> None:
    engine = CampaignEngine(NullNarrationAdapter(), data_dir=Path("data"))
    cleaned = engine._sanitize_system_messages(
        [
            "Turn 3: the lantern flickers.",
            "Outcome summary: corridor is clear.",
            "You say: hello there.",
            "The corridor air smells like wet stone.",
        ]
    )

    assert cleaned == ["The corridor air smells like wet stone."]


def test_finish_turn_filters_banned_system_message_phrases() -> None:
    state = load_state()
    engine = CampaignEngine(NullNarrationAdapter(), data_dir=Path("data"))
    result = engine._finish_turn(
        state,
        action="check log filter",
        system_messages=[
            "Turn 8: movement confirmed.",
            "Outcome summary: doorway opened.",
            "You say: we proceed.",
            "A cold draft spills from the opened doorway.",
        ],
        skip_narrator=True,
    )

    texts = [message["text"] for message in result.messages]
    assert texts == ["A cold draft spills from the opened doorway."]
    assert not any("turn" in text.lower() for text in texts)
    assert not any("outcome summary" in text.lower() for text in texts)
    assert not any("you say" in text.lower() for text in texts)


def test_coherent_output_does_not_trigger_quality_fallback() -> None:
    state = load_state()
    adapter = SequencedNarrationAdapter(
        [
            "You hesitate for a heartbeat, then the room answers your move: chairs scrape back and Elder Thorne watches for what you do next.",
        ]
    )
    engine = CampaignEngine(adapter, data_dir=Path("data"))
    result = engine.run_turn(state, "look")

    assert result.metadata is not None
    assert result.metadata["quality_fallback_used"] is False
    assert "elder thorne" in result.narrative.lower()


def test_repetition_detection_allows_progression_on_same_subject() -> None:
    engine = CampaignEngine(NullNarrationAdapter(), data_dir=Path("data"))
    prior = "The Bone Warden advances with shield high and the crypt dust shakes under its steps."
    current = "The Bone Warden still advances, but now it staggers after your hit and its shield arm drops."
    assessment = engine._assess_repetition_pattern(current, prior)
    assert assessment["is_progression"] is True
    assert assessment["is_dead_loop"] is False


def test_repetition_detection_allows_same_location_with_new_consequence() -> None:
    engine = CampaignEngine(NullNarrationAdapter(), data_dir=Path("data"))
    prior = "You remain in the crypt hall while the same iron door rattles in its frame."
    current = "You remain in the crypt hall, but now the iron door cracks and torch smoke spills through."
    assessment = engine._assess_repetition_pattern(current, prior)
    assert assessment["is_progression"] is True
    assert assessment["is_dead_loop"] is False


def test_validator_preserves_coherent_non_refusal_output_even_if_indirect() -> None:
    state = load_state()
    engine = CampaignEngine(NullNarrationAdapter(), data_dir=Path("data"))
    scene_state = engine._ensure_scene_state(state)
    assessment = engine._validate_narration_output(
        "attack the statue",
        "Moonlight reflects across still water while distant bells ring.",
        state,
        scene_state,
    )
    assert assessment["valid"] is True
    assert assessment["reason"] == "ok"


def test_prompt_renderer_player_facts_relevance_filtering() -> None:
    state = load_state()
    retrieval = MemoryRetrievalPipeline().retrieve(
        state,
        RetrievalRequest(location_id=state.current_location_id, active_quest_ids=[], current_npc_id=None, recent_actions=[], important_world_state=[]),
    )
    renderer = PromptRenderer()
    cast_prompt = renderer.build_turn_prompt(state, action="cast flamestrike", location_summary="Moonfall Tavern", memory=retrieval)
    item_prompt = renderer.build_turn_prompt(state, action="use field_draught", location_summary="Moonfall Tavern", memory=retrieval)
    dialogue_prompt = renderer.build_turn_prompt(state, action="talk elder_thorne", location_summary="Moonfall Tavern", memory=retrieval)

    assert "Focus for this turn: magic" in cast_prompt
    assert "Spellbook highlights:" in cast_prompt
    assert "Focus for this turn: item_use" in item_prompt
    assert "Inventory highlights:" in item_prompt
    assert "Focus for this turn: dialogue" in dialogue_prompt
    assert "Attack bonus:" not in dialogue_prompt


def test_prompt_renderer_npc_and_enemy_blocks_are_compact_and_behavioral() -> None:
    state = load_state()
    state.active_enemy_id = "bone_warden"
    state.active_enemy_hp = 9
    engine = CampaignEngine(NullNarrationAdapter(), data_dir=Path("data"))
    scene_state = engine._ensure_scene_state(state)
    context = engine._build_structured_turn_context(state, "attack", scene_state)
    prompt = PromptRenderer().build_turn_prompt(
        state,
        action="attack",
        location_summary="Moonfall Catacombs",
        memory=MemoryRetrievalPipeline().retrieve(
            state,
            RetrievalRequest(location_id=state.current_location_id, active_quest_ids=[], current_npc_id=None, recent_actions=[], important_world_state=[]),
        ),
        turn_context=context,
    )

    assert "likely intent" in prompt
    assert "tactical posture" in prompt


def test_structured_turn_context_npc_summary_includes_name_role_and_traits() -> None:
    state = load_state()
    engine = CampaignEngine(NullNarrationAdapter(), data_dir=Path("data"))
    scene_state = engine._ensure_scene_state(state)
    context = engine._build_structured_turn_context(state, "talk elder_thorne", scene_state)
    assert context.npc_states
    first = context.npc_states[0]
    assert ":" in first
    assert "role " in first
    assert "personality " in first


def test_scene_state_tracks_and_persists_npc_conditions() -> None:
    state = load_state()
    engine = CampaignEngine(NullNarrationAdapter(), data_dir=Path("data"))
    scene_state = engine._ensure_scene_state(state)

    npc = next(iter([entry for entry in state.npcs.values() if entry.location_id == state.current_location_id]))
    engine._update_scene_state_from_turn(
        state,
        action=f"i freeze {npc.name}",
        narrative=f"{npc.name} is frozen in place and weakened.",
        system_messages=[],
        is_gameplay=True,
    )
    persisted = scene_state.get("npc_conditions", {}).get(npc.id, [])
    assert "frozen" in persisted
    assert "weakened" in persisted

    engine._update_scene_state_from_turn(
        state,
        action="i look around",
        narrative="Frost still cages the target.",
        system_messages=[],
        is_gameplay=True,
    )
    follow_up = scene_state.get("npc_conditions", {}).get(npc.id, [])
    assert "frozen" in follow_up


def test_scene_state_tracks_enemy_condition_behavior_and_pressure() -> None:
    state = load_state()
    state.active_enemy_id = "bone_warden"
    state.active_enemy_hp = 6
    engine = CampaignEngine(NullNarrationAdapter(), data_dir=Path("data"))

    engine._update_scene_state_from_turn(
        state,
        action="attack the bone warden",
        narrative="The Bone Warden is badly injured but still advancing with intense pressure.",
        system_messages=[],
        is_gameplay=True,
    )
    enemy_state = engine._ensure_scene_state(state).get("enemy_conditions", {}).get("bone_warden", {})
    assert "critical" in enemy_state.get("conditions", []) or "injured" in enemy_state.get("conditions", [])
    assert enemy_state.get("behavior") == "advancing"
    assert enemy_state.get("pressure") == "high"


def test_scene_state_environment_persistence_and_condition_evolution() -> None:
    state = load_state()
    engine = CampaignEngine(NullNarrationAdapter(), data_dir=Path("data"))
    scene_state = engine._ensure_scene_state(state)

    npc = next(iter([entry for entry in state.npcs.values() if entry.location_id == state.current_location_id]))
    engine._update_scene_state_from_turn(
        state,
        action=f"i freeze {npc.name} and scorch the floor",
        narrative=f"{npc.name} is frozen while fire starts spreading across nearby cover.",
        system_messages=[],
        is_gameplay=True,
    )
    engine._update_scene_state_from_turn(
        state,
        action=f"i shatter {npc.name}",
        narrative=f"{npc.name} is shattered into icy fragments.",
        system_messages=[],
        is_gameplay=True,
    )

    npc_conditions = scene_state.get("npc_conditions", {}).get(npc.id, [])
    assert "shattered" in npc_conditions
    assert "frozen" not in npc_conditions
    persistent_environment = [item.lower() for item in scene_state.get("environment_consequences", [])]
    assert any("fire is spreading" in item for item in persistent_environment)


def test_prompt_includes_persistent_condition_summaries() -> None:
    state = load_state()
    state.active_enemy_id = "bone_warden"
    state.active_enemy_hp = 8
    engine = CampaignEngine(NullNarrationAdapter(), data_dir=Path("data"))
    scene_state = engine._ensure_scene_state(state)
    npc = next(iter([entry for entry in state.npcs.values() if entry.location_id == state.current_location_id]))
    scene_state["npc_conditions"][npc.id] = ["frozen", "weakened"]
    scene_state["enemy_conditions"]["bone_warden"] = {
        "conditions": ["injured"],
        "behavior": "advancing",
        "pressure": "high",
    }
    scene_state["environment_consequences"] = ["frost spreading across the tavern floor"]
    context = engine._build_structured_turn_context(state, "attack", scene_state)
    prompt = PromptRenderer().build_turn_prompt(
        state,
        action="attack",
        location_summary="Moonfall Catacombs",
        memory=MemoryRetrievalPipeline().retrieve(
            state,
            RetrievalRequest(location_id=state.current_location_id, active_quest_ids=[], current_npc_id=None, recent_actions=[], important_world_state=[]),
        ),
        scene_state_summary=engine._summarize_scene_state_for_prompt(scene_state),
        turn_context=context,
    )

    assert "frozen, weakened" in prompt
    assert "injured, advancing, pressure high" in prompt
