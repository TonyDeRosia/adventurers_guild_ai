from __future__ import annotations

import json
from pathlib import Path

from engine.campaign_engine import CampaignEngine
from engine.entities import CampaignState
from memory.npc_personality import NPCPersonalitySystem
from models.base import NullNarrationAdapter


def load_state() -> CampaignState:
    root = Path(__file__).resolve().parent.parent
    return CampaignState.from_dict(json.loads((root / "data" / "sample_campaign.json").read_text(encoding="utf-8")))


def test_personality_state_change_and_threshold_unlock() -> None:
    state = load_state()
    engine = CampaignEngine(NullNarrationAdapter(), data_dir=Path("data"))
    personality = NPCPersonalitySystem(engine.content)

    for _ in range(3):
        personality.apply_event(state, "elder_thorne", "player_kindness", {"summary": "helped villagers"})

    npc = state.npcs["elder_thorne"]
    assert "shares_catacomb_secrets" in npc.unlocked_behaviors
    assert npc.dynamic_state.trust_toward_player >= 8


def test_memory_impact_and_trust_fear_thresholds() -> None:
    state = load_state()
    engine = CampaignEngine(NullNarrationAdapter(), data_dir=Path("data"))
    personality = NPCPersonalitySystem(engine.content)

    personality.apply_event(
        state,
        "elder_thorne",
        "player_betrayal",
        {
            "summary": "player threatened the chapel watch",
            "impact": {"trust_toward_player": -12, "fear_toward_player": 9, "anger": 6},
            "tags": ["threat"],
        },
    )

    npc = state.npcs["elder_thorne"]
    assert npc.dynamic_state.trust_toward_player <= -5
    assert npc.dynamic_state.fear_toward_player >= 9
    assert any(entry.event_type == "player_betrayal" for entry in npc.memory_log)


def test_personality_driven_dialogue_unlocks_response() -> None:
    state = load_state()
    engine = CampaignEngine(NullNarrationAdapter(), data_dir=Path("data"))

    for _ in range(3):
        engine.personality.apply_event(state, "elder_thorne", "player_kindness", {"summary": "act of kindness"})

    result = engine.run_turn(state, "talk elder_thorne")
    assert "shares_catacomb_secrets" in state.npcs["elder_thorne"].unlocked_behaviors
    assert any("Share the old catacomb side paths" in msg for msg in result.system_messages)


def test_legacy_save_defaults_dynamic_state() -> None:
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
            "inventory": [],
            "xp": 0,
        },
        "npcs": {
            "elder_thorne": {
                "id": "elder_thorne",
                "name": "Elder Thorne",
                "location_id": "moonfall_town",
                "disposition": 10,
                "relationship_tier": "neutral",
                "notes": [],
                "relationships": {},
            }
        },
        "locations": {"moonfall_town": {"id": "moonfall_town", "name": "Moonfall Town", "description": "desc", "connections": []}},
        "quests": {},
        "settings": {},
    }
    loaded = CampaignState.from_dict(legacy)
    assert loaded.npcs["elder_thorne"].dynamic_state.trust_toward_player == 0
    assert loaded.npcs["elder_thorne"].memory_log == []


def test_node_based_personality_guidance_is_available_for_prompting() -> None:
    state = load_state()
    engine = CampaignEngine(NullNarrationAdapter(), data_dir=Path("data"))

    guidance = engine.personality.build_prompt_guidance(state)

    assert guidance
    elder_line = next((line for line in guidance if line.startswith("Elder Thorne:")), "")
    assert "measured and tradition-minded" in elder_line or "stoic" in elder_line
    assert "likely voice=" in elder_line
    assert "stress=" in elder_line
    assert "current stance toward player=" in elder_line


def test_personality_profile_auto_generated_for_existing_npc_and_persists() -> None:
    state = load_state()
    engine = CampaignEngine(NullNarrationAdapter(), data_dir=Path("data"))
    npc = state.npcs["elder_thorne"]
    npc.personality_profile = None

    guidance_before = engine.personality.build_prompt_guidance(state)
    assert guidance_before
    assert npc.personality_profile is not None
    first_tone = npc.personality_profile.conversational_tone

    guidance_after = engine.personality.build_prompt_guidance(state)
    assert guidance_after
    assert npc.personality_profile is not None
    assert npc.personality_profile.conversational_tone == first_tone


def test_personality_profile_survives_serialization_roundtrip() -> None:
    state = load_state()
    engine = CampaignEngine(NullNarrationAdapter(), data_dir=Path("data"))
    engine.personality.build_prompt_guidance(state)

    reloaded = CampaignState.from_dict(state.to_dict())
    npc = reloaded.npcs["elder_thorne"]
    assert npc.personality_profile is not None
    assert npc.personality_profile.identity_label == "Elder Thorne"


def test_personality_profile_evolves_slightly_after_betrayal_pattern() -> None:
    state = load_state()
    engine = CampaignEngine(NullNarrationAdapter(), data_dir=Path("data"))
    engine.personality.build_prompt_guidance(state)

    engine.personality.apply_event(state, "elder_thorne", "player_betrayal", {"summary": "first betrayal"})
    engine.personality.apply_event(state, "elder_thorne", "player_betrayal", {"summary": "second betrayal"})
    profile = state.npcs["elder_thorne"].personality_profile
    assert profile is not None
    assert "suspicious" in profile.social_style or "guarded" in profile.social_style
    assert "deception" in profile.conflict_response or "contingencies" in profile.conflict_response
