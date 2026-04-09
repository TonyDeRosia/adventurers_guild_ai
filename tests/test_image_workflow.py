from pathlib import Path

from images.base import ImageGenerationRequest
from images.prompt_builder import TurnImagePromptBuilder
from images.workflow_manager import WorkflowManager
from engine.game_state_manager import GameStateManager
from app.pathing import initialize_user_data_paths


def test_scene_workflow_builds_valid_comfy_graph() -> None:
    manager = WorkflowManager(Path('data/workflows'))
    request = ImageGenerationRequest(
        workflow_id='scene_image',
        prompt='ruined temple at dawn',
        negative_prompt='blurry',
        parameters={
            'seed': 123,
            'steps': 20,
            'cfg': 6.5,
            'width': 640,
            'height': 384,
            'checkpoint': 'dreamshaper.safetensors',
        },
    )

    workflow = manager.build_workflow(request)
    manager.validate_workflow(workflow)
    bindings = manager.inspect_bindings(workflow)

    assert bindings.checkpoint_node_ids
    assert bindings.positive_prompt_node_ids
    assert bindings.save_image_node_ids
    assert any(workflow[node]['inputs'].get('ckpt_name') == 'dreamshaper.safetensors' for node in bindings.checkpoint_node_ids)
    assert any(workflow[node]['inputs'].get('text') == 'ruined temple at dawn' for node in bindings.positive_prompt_node_ids)
    assert any(
        isinstance(node, dict)
        and isinstance(node.get('inputs'), dict)
        and node['inputs'].get('seed') == 123
        and node['inputs'].get('steps') == 20
        for node in workflow.values()
    )
    assert any(
        isinstance(node, dict)
        and isinstance(node.get('inputs'), dict)
        and node['inputs'].get('width') == 640
        for node in workflow.values()
    )


def test_scene_workflow_without_output_node_fails() -> None:
    manager = WorkflowManager(Path('data/workflows'))
    try:
        manager.validate_workflow({'1': {'class_type': 'KSampler', 'inputs': {'steps': 10}}})
    except ValueError as exc:
        assert 'output node' in str(exc).lower()
    else:
        raise AssertionError('Expected ValueError for incomplete workflow')


def test_turn_prompt_builder_uses_visual_focus_from_narration(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ADVENTURER_GUILD_AI_USER_DATA_DIR", str(tmp_path / "user_data"))
    paths = initialize_user_data_paths()
    state = GameStateManager(paths.content_data, paths.saves, paths.user_data).create_new_campaign(
        player_name="Aria",
        char_class="Ranger",
        profile="classic_fantasy",
        mature_content_enabled=False,
        content_settings_enabled=True,
    )
    builder = TurnImagePromptBuilder()

    packet = builder.build_packet(
        state,
        player_action="draw bow",
        narrator_response="A pale moonbeam cuts through the fog while shadows gather around the ruined gate.",
        stage="after_narration",
    )

    assert "Aria draw bow" in packet.prompt
    assert "moonbeam cuts through the fog" in packet.prompt
    assert "in Starting Area" in packet.prompt
    assert "wrong character count" in packet.negative_prompt


def test_before_narration_prompt_uses_structured_scene_state_not_generic_only(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ADVENTURER_GUILD_AI_USER_DATA_DIR", str(tmp_path / "user_data"))
    paths = initialize_user_data_paths()
    state = GameStateManager(paths.content_data, paths.saves, paths.user_data).create_new_campaign(
        player_name="Aria",
        char_class="Ranger",
        profile="classic_fantasy",
        mature_content_enabled=False,
        content_settings_enabled=True,
    )
    state.structured_state.runtime.scene_state = {
        "location_name": "Shattered Chapel",
        "scene_summary": "Moonlight spills through broken stained glass into a ruined altar hall.",
        "damaged_objects": ["broken stained glass", "collapsed pews"],
        "altered_environment": ["drifting dust motes"],
    }
    builder = TurnImagePromptBuilder()
    packet = builder.build_packet(state, player_action="raise shield", narrator_response="", stage="before_narration")

    assert "Shattered Chapel" in packet.prompt
    assert "broken stained glass" in packet.prompt
    assert "pre-outcome framing from current scene state" in packet.prompt


def test_combat_prompt_includes_attacker_defender_and_outcome_details(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ADVENTURER_GUILD_AI_USER_DATA_DIR", str(tmp_path / "user_data"))
    paths = initialize_user_data_paths()
    state = GameStateManager(paths.content_data, paths.saves, paths.user_data).create_new_campaign(
        player_name="Aria",
        char_class="Ranger",
        profile="classic_fantasy",
        mature_content_enabled=False,
        content_settings_enabled=True,
    )
    state.active_enemy_id = "temple_guard"
    state.active_enemy_hp = 9
    state.structured_state.runtime.scene_state = {
        "recent_consequences": ["The guard staggers backward, clutching a bleeding shoulder."],
        "enemy_conditions": {"temple_guard": {"hp": 9}},
        "active_effects": ["violet lightning arcs around Aria's gauntlet"],
    }
    builder = TurnImagePromptBuilder()
    packet = builder.build_packet(
        state,
        player_action="slash at temple guard with short sword",
        narrator_response="Aria drives forward and the guard reels from the impact.",
        stage="after_narration",
    )

    assert "temple guard" in packet.prompt
    assert "1 total, critical" in packet.prompt
    assert "staggers backward" in packet.prompt
    assert "combat" in packet.prompt


def test_dialogue_prompt_does_not_collapse_into_combat_framing(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ADVENTURER_GUILD_AI_USER_DATA_DIR", str(tmp_path / "user_data"))
    paths = initialize_user_data_paths()
    state = GameStateManager(paths.content_data, paths.saves, paths.user_data).create_new_campaign(
        player_name="Aria",
        char_class="Ranger",
        profile="classic_fantasy",
        mature_content_enabled=False,
        content_settings_enabled=True,
    )
    state.active_enemy_id = None
    builder = TurnImagePromptBuilder()
    packet = builder.build_packet(
        state,
        player_action="ask Captain Mirel about the sealed vault",
        narrator_response="Captain Mirel leans over the map table and replies in a low, careful tone.",
        stage="after_narration",
    )

    assert "dialogue scene" in packet.prompt
    assert "battle pose" in packet.negative_prompt
    assert "idle portrait only" not in packet.negative_prompt


def test_visual_continuity_persists_when_current_turn_omits_detail(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ADVENTURER_GUILD_AI_USER_DATA_DIR", str(tmp_path / "user_data"))
    paths = initialize_user_data_paths()
    state = GameStateManager(paths.content_data, paths.saves, paths.user_data).create_new_campaign(
        player_name="Aria",
        char_class="Ranger",
        profile="classic_fantasy",
        mature_content_enabled=False,
        content_settings_enabled=True,
    )
    state.structured_state.runtime.scene_state = {
        "visual_continuity": {
            "armor_clothing": "black and silver armor",
            "primary_weapon": "obsidian spear",
            "weather": "fog",
            "lighting": "moonlight",
        },
        "location_name": "Glass Docks",
        "scene_summary": "Wet stone walkways line the harbor.",
    }
    builder = TurnImagePromptBuilder()
    packet = builder.build_packet(
        state,
        player_action="step forward",
        narrator_response="Aria advances carefully.",
        stage="after_narration",
    )
    continuity = packet.continuity_state

    assert continuity["armor_clothing"] == "black and silver armor"
    assert continuity["primary_weapon"] == "obsidian spear"
    assert continuity["weather"] == "fog"
    assert continuity["lighting"] == "moonlight"


def test_quest_titles_do_not_dominate_immediate_action_scene(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ADVENTURER_GUILD_AI_USER_DATA_DIR", str(tmp_path / "user_data"))
    paths = initialize_user_data_paths()
    state = GameStateManager(paths.content_data, paths.saves, paths.user_data).create_new_campaign(
        player_name="Aria",
        char_class="Ranger",
        profile="classic_fantasy",
        mature_content_enabled=False,
        content_settings_enabled=True,
    )
    for quest in state.quests.values():
        quest.status = "active"
        quest.title = "Recover the Seven Sigils"
    builder = TurnImagePromptBuilder()
    packet = builder.build_packet(
        state,
        player_action="parry the raider strike",
        narrator_response="Steel rings out as Aria knocks the blade aside.",
        stage="after_narration",
    )
    assert "Recover the Seven Sigils" not in packet.prompt
    assert "parry the raider strike" in packet.prompt


def test_negative_prompt_additions_are_applied_deterministically(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ADVENTURER_GUILD_AI_USER_DATA_DIR", str(tmp_path / "user_data"))
    paths = initialize_user_data_paths()
    state = GameStateManager(paths.content_data, paths.saves, paths.user_data).create_new_campaign(
        player_name="Aria",
        char_class="Ranger",
        profile="classic_fantasy",
        mature_content_enabled=False,
        content_settings_enabled=True,
    )
    builder = TurnImagePromptBuilder()
    packet = builder.build_packet(
        state,
        player_action="look around",
        narrator_response="A cold wind stirs the banners.",
        stage="after_narration",
        negative_prompt_additions=["lens flare", "random hooded stranger", "lens flare"],
    )

    assert "lens flare" in packet.negative_prompt
    assert packet.negative_prompt.count("lens flare") == 1
