from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import time
from types import SimpleNamespace

import pytest

from app.web import WebRuntime, create_web_app
from engine.character_sheets import CharacterSheet, CharacterSheetAbilityEntry
from engine.campaign_engine import TurnResult
from engine.entities import CampaignState, ConversationTurn, NPC
from images.base import ImageGenerationResult
from models.base import NarrationModelAdapter, ProviderUnavailableError


def _runtime(tmp_path: Path, monkeypatch) -> WebRuntime:
    monkeypatch.setenv("ADVENTURER_GUILD_AI_USER_DATA_DIR", str(tmp_path / "user_data"))
    return WebRuntime(Path.cwd())


def test_campaign_management_create_save_switch_rename_delete(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)

    created = runtime.create_campaign({"player_name": "Mira", "char_class": "Mage", "slot": "slot_mira"})
    assert created["slot"] == "slot_mira"

    runtime.handle_player_input("look")
    runtime.save_active_campaign("slot_mira")
    runtime.create_campaign({"player_name": "Aric", "char_class": "Rogue", "slot": "slot_aric"})
    runtime.save_active_campaign("slot_aric")

    switched = runtime.switch_campaign("slot_mira")
    assert switched["state"]["player"]["name"] == "Mira"
    assert any("look" in msg["text"].lower() for msg in runtime.session.message_history)

    renamed = runtime.rename_campaign("slot_mira", "Mira Renamed")
    assert renamed["campaign_name"] == "Mira Renamed"

    deleted = runtime.delete_campaign("slot_aric")
    assert deleted["deleted"] == "slot_aric"


def test_create_campaign_persists_world_metadata(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    created = runtime.create_campaign(
        {
            "player_name": "Aria",
            "char_class": "Ranger",
            "slot": "slot_world",
            "campaign_name": "Aria in the Ashen Realm",
            "world_name": "Vel Astren",
            "world_theme": "dark fantasy",
            "starting_location_name": "Black Harbor",
            "campaign_tone": "grim heroic",
            "premise": "the old gods vanished and the sea is haunted",
            "player_concept": "exiled ranger searching for her brother",
        }
    )
    assert created["state"]["campaign_name"] == "Aria in the Ashen Realm"
    assert created["state"]["world_meta"]["world_name"] == "Vel Astren"
    assert created["state"]["world_meta"]["starting_location_name"] == "Black Harbor"

    runtime.switch_campaign("slot_world")
    assert runtime.session.state.world_meta.world_theme == "dark fantasy"
    assert runtime.session.state.locations[runtime.session.state.current_location_id].name == "Black Harbor"


def test_create_campaign_stores_campaign_play_style_settings(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    created = runtime.create_campaign(
        {
            "player_name": "StyleCreate",
            "slot": "slot_style_create",
            "play_style": {
                "allow_freeform_powers": False,
                "auto_update_character_sheet_from_actions": False,
                "strict_sheet_enforcement": True,
                "auto_sync_player_declared_identity": False,
                "auto_generate_npc_personalities": False,
                "auto_evolve_npc_personalities": False,
                "reactive_world_persistence": False,
                "narration_format_mode": "compact",
                "scene_visual_mode": "manual",
            },
        }
    )
    play_style = created["state"]["settings"]["play_style"]
    assert play_style["allow_freeform_powers"] is False
    assert play_style["strict_sheet_enforcement"] is True
    assert play_style["narration_format_mode"] == "compact"
    assert play_style["scene_visual_mode"] == "manual"


def test_new_campaign_uses_preferred_visual_and_suggested_move_defaults(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    created = runtime.create_campaign({"player_name": "DefaultCheck", "slot": "slot_defaults"})

    assert "campaign_auto_visuals_enabled" not in created["state"]["settings"]
    assert created["state"]["settings"]["play_style"]["scene_visual_mode"] == "after_narration"
    assert created["state"]["settings"]["suggested_moves_enabled"] is False
    assert created["state"]["settings"]["effective_suggested_moves_enabled"] is False
    assert created["state"]["settings"]["display_mode"] == "story"

    global_settings = runtime.get_global_settings()
    assert global_settings["image"]["manual_image_generation_enabled"] is True
    assert global_settings["image"]["campaign_auto_visual_timing"] == "after_narration"


def test_existing_campaign_settings_are_preserved_on_load(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"player_name": "KeepMe", "slot": "slot_keep"})
    runtime.set_campaign_settings(
        {
            "suggested_moves_enabled": True,
            "player_suggested_moves_override": True,
            "play_style": {"scene_visual_mode": "manual"},
        }
    )
    runtime.save_active_campaign("slot_keep")

    reloaded = _runtime(tmp_path, monkeypatch)
    reloaded.switch_campaign("slot_keep")
    settings = reloaded.serialize_state()["settings"]
    assert settings["play_style"]["scene_visual_mode"] == "manual"
    assert "campaign_auto_visuals_enabled" not in settings
    assert settings["suggested_moves_enabled"] is True
    assert settings["effective_suggested_moves_enabled"] is True


def test_campaign_play_style_settings_persist_across_save_and_load(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"player_name": "PersistStyle", "slot": "slot_style_persist"})
    runtime.set_campaign_settings(
        {
            "play_style": {
                "allow_freeform_powers": False,
                "auto_update_character_sheet_from_actions": False,
                "strict_sheet_enforcement": True,
                "auto_sync_player_declared_identity": False,
                "auto_generate_npc_personalities": False,
                "auto_evolve_npc_personalities": True,
                "reactive_world_persistence": False,
                "narration_format_mode": "dialogue_focused",
                "scene_visual_mode": "before_narration",
            }
        }
    )
    runtime.save_active_campaign("slot_style_persist")

    reloaded = _runtime(tmp_path, monkeypatch)
    loaded = reloaded.switch_campaign("slot_style_persist")
    play_style = loaded["state"]["settings"]["play_style"]
    assert play_style["allow_freeform_powers"] is False
    assert play_style["strict_sheet_enforcement"] is True
    assert play_style["narration_format_mode"] == "dialogue_focused"
    assert play_style["scene_visual_mode"] == "before_narration"


def test_campaign_play_style_is_isolated_per_campaign(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"player_name": "StyleA", "slot": "slot_style_a"})
    runtime.set_campaign_settings({"play_style": {"narration_format_mode": "compact", "scene_visual_mode": "manual"}})
    runtime.save_active_campaign("slot_style_a")
    runtime.create_campaign({"player_name": "StyleB", "slot": "slot_style_b"})
    runtime.set_campaign_settings({"play_style": {"narration_format_mode": "book", "scene_visual_mode": "after_narration"}})
    runtime.save_active_campaign("slot_style_b")

    first = runtime.switch_campaign("slot_style_a")
    assert first["state"]["settings"]["play_style"]["narration_format_mode"] == "compact"
    assert first["state"]["settings"]["play_style"]["scene_visual_mode"] == "manual"
    second = runtime.switch_campaign("slot_style_b")
    assert second["state"]["settings"]["play_style"]["narration_format_mode"] == "book"
    assert second["state"]["settings"]["play_style"]["scene_visual_mode"] == "after_narration"


def test_display_mode_persists_after_save_load_and_switch(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    first = runtime.create_campaign({"player_name": "ModeOne", "slot": "slot_story"})
    assert first["state"]["settings"]["display_mode"] == "story"
    runtime.save_active_campaign("slot_story")

    runtime.create_campaign({"player_name": "ModeTwo", "slot": "slot_mud", "display_mode": "mud"})
    runtime.save_active_campaign("slot_mud")
    assert runtime.serialize_state()["settings"]["display_mode"] == "mud"

    switched = runtime.switch_campaign("slot_story")
    assert switched["state"]["settings"]["display_mode"] == "story"
    switched_back = runtime.switch_campaign("slot_mud")
    assert switched_back["state"]["settings"]["display_mode"] == "mud"

    reloaded = _runtime(tmp_path, monkeypatch)
    loaded = reloaded.switch_campaign("slot_mud")
    assert loaded["state"]["settings"]["display_mode"] == "mud"


def test_display_mode_can_be_changed_from_campaign_settings_and_persists(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"player_name": "ModeSwap", "slot": "slot_mode_swap", "display_mode": "story"})
    updated = runtime.set_campaign_settings({"display_mode": "rpg"})
    assert updated["display_mode"] == "rpg"
    runtime.save_active_campaign("slot_mode_swap")

    reloaded = _runtime(tmp_path, monkeypatch)
    switched = reloaded.switch_campaign("slot_mode_swap")
    assert switched["state"]["settings"]["display_mode"] == "rpg"


def test_campaign_listing_includes_display_mode_for_selected_campaign_summary(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"player_name": "ListStory", "slot": "slot_story_list", "display_mode": "story"})
    runtime.save_active_campaign("slot_story_list")
    runtime.create_campaign({"player_name": "ListMud", "slot": "slot_mud_list", "display_mode": "mud"})
    runtime.save_active_campaign("slot_mud_list")

    campaigns = runtime.list_campaigns()
    by_slot = {entry["slot"]: entry for entry in campaigns}
    assert by_slot["slot_story_list"]["display_mode"] == "story"
    assert by_slot["slot_mud_list"]["display_mode"] == "mud"


def test_campaign_listing_surfaces_all_save_files_even_unreadable_json_shapes(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"player_name": "ListAll", "slot": "slot_valid"})
    runtime.save_active_campaign("slot_valid")
    invalid_shape_path = runtime.paths.saves / "slot_invalid_shape.json"
    invalid_shape_path.write_text(json.dumps(["not", "a", "campaign", "object"]), encoding="utf-8")

    campaigns = runtime.list_campaigns()
    by_slot = {entry["slot"]: entry for entry in campaigns}
    assert "slot_valid" in by_slot
    assert "slot_invalid_shape" in by_slot
    assert by_slot["slot_invalid_shape"]["loadable"] is False


@pytest.mark.parametrize("display_mode", ["mud", "rpg"])
def test_campaign_creation_accepts_non_story_display_modes(tmp_path: Path, monkeypatch, display_mode: str) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    created = runtime.create_campaign({"player_name": "ModeCheck", "slot": f"slot_{display_mode}", "display_mode": display_mode})
    assert created["state"]["settings"]["display_mode"] == display_mode


def test_campaign_creation_with_character_sheet_loadout_and_display_mode_submits(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    created = runtime.create_campaign(
        {
            "player_name": "LoadoutCheck",
            "slot": "slot_loadout_layout",
            "display_mode": "rpg",
            "character_sheets": [
                {
                    "id": "sheet_loadout",
                    "name": "Loadout Hero",
                    "sheet_type": "main_character",
                    "role": "Spellblade",
                    "guaranteed_abilities": [
                        {"name": "Spark Slash", "type": "ability", "cost_or_resource": "2 energy", "cooldown": "1 turn", "tags": ["starter"]},
                        {"name": "Ward", "type": "spell", "cost_or_resource": "4 mana", "cooldown": "2 turns"},
                    ],
                }
            ],
        }
    )
    assert created["state"]["settings"]["display_mode"] == "rpg"
    assert len(created["state"]["spellbook"]) >= 2


def test_campaign_state_api_includes_display_mode(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"player_name": "ApiMode", "slot": "slot_api_mode", "display_mode": "mud"})
    state = runtime.serialize_state()
    assert state["settings"]["display_mode"] == "mud"


def test_legacy_campaign_without_play_style_loads_safe_defaults() -> None:
    legacy = {
        "campaign_id": "legacy",
        "campaign_name": "Legacy",
        "turn_count": 0,
        "current_location_id": "start",
        "player": {"id": "p1", "name": "Legacy", "char_class": "Ranger"},
        "npcs": {},
        "locations": {"start": {"id": "start", "name": "Start", "description": "start", "connections": []}},
        "quests": {},
        "settings": {},
    }
    loaded = CampaignState.from_dict(legacy)
    play_style = loaded.settings.play_style
    assert play_style.allow_freeform_powers is True
    assert play_style.narration_format_mode == "book"
    assert play_style.scene_visual_mode == "after_narration"


def test_character_sheet_can_be_created_after_campaign_start_and_serialized(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"player_name": "SheetMaker", "slot": "slot_runtime_sheet"})

    created = runtime.upsert_character_sheet(
        {
            "action": "create",
            "name": "Iris",
            "sheet_type": "party_member",
            "role": "companion",
            "archetype": "Scout",
            "description": "Fast moving ally",
        }
    )
    assert created["created_id"]
    assert len(created["character_sheets"]) == 1
    assert created["character_sheets"][0]["name"] == "Iris"
    assert runtime.serialize_state()["character_sheets"][0]["role"] == "companion"


def test_character_sheet_creation_persists_and_remains_campaign_scoped(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"player_name": "ScopeA", "slot": "slot_scope_a"})
    first = runtime.upsert_character_sheet({"action": "create", "name": "Echo", "role": "npc_ally"})
    second = runtime.upsert_character_sheet({"action": "create", "name": "Echo", "role": "npc_ally"})
    assert first["created_id"] != second["created_id"]
    runtime.save_active_campaign("slot_scope_a")

    runtime.create_campaign({"player_name": "ScopeB", "slot": "slot_scope_b"})
    assert runtime.serialize_state()["character_sheets"] == []
    runtime.save_active_campaign("slot_scope_b")

    runtime.switch_campaign("slot_scope_a")
    assert len(runtime.serialize_state()["character_sheets"]) == 2

    reloaded = _runtime(tmp_path, monkeypatch)
    reloaded.switch_campaign("slot_scope_a")
    assert len(reloaded.serialize_state()["character_sheets"]) == 2
    reloaded.switch_campaign("slot_scope_b")
    assert reloaded.serialize_state()["character_sheets"] == []


def test_runtime_character_sheet_creation_supports_full_payload_and_created_id_selection(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"player_name": "FullSheet", "slot": "slot_full_sheet"})

    created = runtime.upsert_character_sheet(
        {
            "action": "create",
            "name": "Kestrel",
            "sheet_type": "party_member",
            "role": "companion",
            "archetype": "Blade Dancer",
            "description": "Fast striker",
            "traits": ["quick", "curious"],
            "guaranteed_abilities": [
                {"name": "Arc Flash", "type": "spell", "cost_or_resource": "2 mana", "notes": "starter"},
            ],
            "notes": "Always scouting ahead",
            "state": {"current_condition": "Ready"},
        }
    )
    created_id = created["created_id"]
    assert created_id
    assert any(sheet["id"] == created_id for sheet in created["character_sheets"])
    saved_sheet = next(sheet for sheet in created["character_sheets"] if sheet["id"] == created_id)
    assert saved_sheet["guaranteed_abilities"][0]["name"] == "Arc Flash"
    assert saved_sheet["notes"] == "Always scouting ahead"


def test_runtime_character_sheet_browser_uses_dedicated_create_modal_markup() -> None:
    index_html = Path("app/static/index.html").read_text(encoding="utf-8")
    app_js = Path("app/static/app.js").read_text(encoding="utf-8")
    assert 'id="runtime-character-sheet-create-toggle"' in index_html
    assert 'id="runtime-character-sheet-create-modal"' in index_html
    assert 'id="runtime-character-sheet-create-panel"' not in index_html
    assert "No character sheets attached yet." in app_js


def test_campaign_log_renders_npc_dialogue_inline_without_faceplate_markup() -> None:
    app_js = Path("app/static/app.js").read_text(encoding="utf-8")
    styles_css = Path("app/static/styles.css").read_text(encoding="utf-8")
    assert "msg-npc-inline" in app_js
    assert "npc-card-avatar" not in app_js
    assert ".msg-npc-inline" in styles_css
    assert ".msg-npc-card" not in styles_css


def test_campaign_panel_removes_quick_load_autosave_and_hides_display_mode_controls() -> None:
    index_html = Path("app/static/index.html").read_text(encoding="utf-8")
    app_js = Path("app/static/app.js").read_text(encoding="utf-8")
    assert "Quick load autosave" not in index_html
    assert 'id="open-display-mode-modal"' not in index_html
    assert 'id="display-mode-modal"' not in index_html
    assert 'id="selected-campaign-summary"' in index_html
    assert "display_mode: 'story'" in app_js
    assert "renderSelectedCampaignSummary" in app_js
    assert "display_mode_change_requested" not in app_js
    assert "display_mode_change_applied" not in app_js


def test_input_mode_toggle_markup_and_frontend_mode_switching_present() -> None:
    index_html = Path("app/static/index.html").read_text(encoding="utf-8")
    app_js = Path("app/static/app.js").read_text(encoding="utf-8")
    styles_css = Path("app/static/styles.css").read_text(encoding="utf-8")
    assert 'id="input-mode-toggle"' in index_html
    assert "let currentInputMode = 'ic';" in app_js
    assert "function toggleInputMode()" in app_js
    assert "body: JSON.stringify({ text, mode: currentInputMode })" in app_js
    assert ".msg-ooc_player" in styles_css
    assert ".msg-ooc_gm" in styles_css


def test_custom_campaign_starts_without_sample_npcs_or_quests(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    created = runtime.create_campaign(
        {
            "mode": "custom",
            "player_name": "Nova",
            "char_class": "Mage",
            "slot": "slot_clean",
            "world_name": "Starreach",
            "starting_location_name": "Glass Docks",
        }
    )
    assert created["state"]["world_meta"]["world_name"] == "Starreach"
    assert runtime.session.state.npcs == {}
    assert runtime.session.state.quests == {}


def test_premade_campaign_mode_explicitly_loads_sample(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    created = runtime.create_campaign({"mode": "premade", "slot": "slot_premade"})
    assert created["state"]["world_meta"]["world_name"] == "Moonfall"
    assert "elder_thorne" in runtime.session.state.npcs


def test_campaign_rename_and_delete_require_selection(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    try:
        runtime.rename_campaign("", "Nope")
        assert False, "Expected ValueError for empty rename slot"
    except ValueError as exc:
        assert "No save selected" in str(exc)

    try:
        runtime.delete_campaign(" ")
        assert False, "Expected ValueError for empty delete slot"
    except ValueError as exc:
        assert "No save selected" in str(exc)


def test_settings_persistence_and_runtime_effects(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)

    runtime.set_global_settings(
        {
            "model": {"provider": "null", "model_name": "llama3.2"},
            "image": {"provider": "null", "enabled": False},
        }
    )
    runtime.set_campaign_settings(
        {
            "narration_tone": "grim",
            "mature_content_enabled": True,
            "image_generation_enabled": False,
            "suggested_moves_enabled": False,
            "player_suggested_moves_override": False,
            "content_settings": {"tone": "noir", "maturity_level": "mature", "thematic_flags": ["horror"]},
        }
    )

    config_path = runtime.paths.config / "app_config.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert payload["model"]["model_name"] == "llama3.2"
    assert payload["image"]["enabled"] is False
    assert payload["image"]["comfyui_workflow_path"].endswith("scene_image.json")
    assert payload["image"]["comfyui_output_dir"] == ""
    assert runtime.session.state.settings.content_settings.tone == "noir"
    assert runtime.session.state.settings.suggested_moves_active() is False


def test_missing_comfyui_paths_report_setup_needed(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.set_global_settings({"image": {"provider": "comfyui", "comfyui_path": "", "comfyui_workflow_path": ""}})
    status = runtime.get_image_status()
    assert status["status_code"] == "setup_required"
    assert "ComfyUI runtime is not available" in status["user_message"]


def test_valid_external_workflow_path_enables_comfyui_generation_path(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    comfy_root = tmp_path / "ComfyUI"
    comfy_root.mkdir(parents=True, exist_ok=True)
    (comfy_root / "main.py").write_text("print('ok')", encoding="utf-8")
    (comfy_root / "custom_nodes").mkdir(exist_ok=True)
    (comfy_root / "models").mkdir(exist_ok=True)
    (comfy_root / "run_cpu.bat").write_text("@echo off", encoding="utf-8")
    workflow_file = tmp_path / "custom_scene.json"
    workflow_file.write_text("{}", encoding="utf-8")
    runtime.set_global_settings(
        {"image": {"provider": "comfyui", "comfyui_path": str(comfy_root), "comfyui_workflow_path": str(workflow_file), "enabled": True}}
    )
    monkeypatch.setattr(runtime, "get_image_status", lambda: {"ready": True})
    monkeypatch.setattr(runtime.image_adapter, "generate", lambda request, _manager: ImageGenerationResult(success=True, workflow_id=request.workflow_id))
    result = runtime.generate_image({"workflow_id": "scene_image", "prompt": "ok"})
    assert result.success is True
    assert result.workflow_id == "custom_scene"


def test_invalid_external_workflow_path_disables_image_feature_cleanly(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.set_campaign_settings({"image_generation_enabled": True})
    runtime.set_global_settings(
        {"image": {"provider": "comfyui", "comfyui_path": str(tmp_path / "missing"), "comfyui_workflow_path": str(tmp_path / "missing.json"), "enabled": True}}
    )
    result = runtime.generate_image({"workflow_id": "scene_image", "prompt": "Moonlit ruins"})
    assert result.success is False
    assert "path" in (result.error or "").lower()


def test_visual_pipeline_apply_rejects_invalid_workflow_path(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    comfy_root = tmp_path / "ComfyUI"
    comfy_root.mkdir(parents=True, exist_ok=True)
    (comfy_root / "main.py").write_text("print('ok')", encoding="utf-8")
    (comfy_root / "custom_nodes").mkdir(exist_ok=True)
    (comfy_root / "models").mkdir(exist_ok=True)
    (comfy_root / "run_cpu.bat").write_text("@echo off", encoding="utf-8")
    checkpoints = comfy_root / "models" / "checkpoints"
    checkpoints.mkdir(parents=True, exist_ok=True)

    original_workflow = runtime.app_config.image.comfyui_workflow_path
    result = runtime.apply_visual_pipeline_settings(
        {
            "comfyui_path": str(comfy_root),
            "comfyui_workflow_path": str(tmp_path / "missing.txt"),
            "comfyui_output_dir": "",
            "checkpoint_folder": str(checkpoints),
        }
    )
    assert result["ok"] is False
    assert result["error_field"] == "comfyui_workflow_path"
    assert runtime.app_config.image.comfyui_workflow_path == original_workflow


def test_visual_pipeline_apply_saves_and_reloads_runtime(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    comfy_root = tmp_path / "ComfyUI"
    comfy_root.mkdir(parents=True, exist_ok=True)
    (comfy_root / "main.py").write_text("print('ok')", encoding="utf-8")
    (comfy_root / "custom_nodes").mkdir(exist_ok=True)
    (comfy_root / "models").mkdir(exist_ok=True)
    (comfy_root / "run_cpu.bat").write_text("@echo off", encoding="utf-8")
    workflow = tmp_path / "scene.json"
    workflow.write_text("{}", encoding="utf-8")
    checkpoints = comfy_root / "models" / "checkpoints"
    checkpoints.mkdir(parents=True, exist_ok=True)

    result = runtime.apply_visual_pipeline_settings(
        {
            "comfyui_path": str(comfy_root),
            "comfyui_workflow_path": str(workflow),
            "comfyui_output_dir": "",
            "checkpoint_folder": str(checkpoints),
        }
    )
    assert result["ok"] is True
    assert runtime.app_config.image.comfyui_workflow_path == str(workflow)
    assert result["path_config"]["image"]["pipeline_ready"] is True

    reloaded = _runtime(tmp_path, monkeypatch)
    assert reloaded.app_config.image.comfyui_workflow_path == str(workflow)


def test_empty_workflow_path_uses_bundled_default(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.image.comfyui_workflow_path = ""
    status = runtime.get_path_configuration_status()["image"]["workflow_path"]
    assert status["configured"] is False
    assert status["valid"] is True
    assert str(status.get("resolved_path", "")).endswith("scene_image.json")


def test_visual_pipeline_validation_uses_auto_detected_comfyui_for_checkpoint_inference(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    comfy_root = tmp_path / "ComfyUI"
    comfy_root.mkdir(parents=True, exist_ok=True)
    (comfy_root / "main.py").write_text("print('ok')", encoding="utf-8")
    (comfy_root / "custom_nodes").mkdir(exist_ok=True)
    checkpoints = comfy_root / "models" / "checkpoints"
    checkpoints.mkdir(parents=True, exist_ok=True)
    (comfy_root / "run_cpu.bat").write_text("@echo off", encoding="utf-8")
    workflow = tmp_path / "scene.json"
    workflow.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(runtime, "_find_comfyui_root", lambda: comfy_root)

    status = runtime.validate_visual_pipeline_config(
        {
            "comfyui_path": "",
            "comfyui_workflow_path": str(workflow),
            "comfyui_output_dir": "",
            "checkpoint_folder": "",
        }
    )["image"]

    assert status["comfyui_root"]["valid"] is True
    assert status["checkpoint_dir"]["valid"] is True
    assert status["pipeline_ready"] is True


def test_save_checkpoint_folder_validates_and_persists_selection(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    checkpoint_dir = tmp_path / "models" / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    result = runtime.save_checkpoint_folder(str(checkpoint_dir))

    assert result["ok"] is True
    assert runtime.app_config.image.checkpoint_folder == str(checkpoint_dir)
    assert result["path_config"]["image"]["checkpoint_dir"]["valid"] is True


def test_skip_images_for_now_switches_to_text_only_mode(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.image.provider = "comfyui"
    runtime.app_config.image.enabled = True

    result = runtime.skip_images_for_now()

    assert result["ok"] is True
    assert runtime.app_config.image.provider == "null"
    assert runtime.app_config.image.enabled is False
    assert result["snapshot"]["text_only_mode_active"] is True


def test_turn_flow_persists_memory_and_messages(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)

    out = runtime.handle_player_input("summarize")
    assert out["messages"]
    assert runtime.session.state.conversation_turns
    assert runtime.session.state.recent_memory

    runtime.save_active_campaign("slot_memory")
    runtime.switch_campaign("slot_memory")
    assert runtime.session.state.conversation_turns[-1].player_input == "summarize"


def test_ooc_input_returns_contextual_reply_without_mutating_campaign_state(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.handle_player_input("look around")
    original_turn_count = runtime.session.state.turn_count
    original_conversation_turns = len(runtime.session.state.conversation_turns)
    original_spellbook = list(runtime.session.state.structured_state.runtime.spellbook)
    original_npc_ids = sorted(runtime.session.state.npcs.keys())

    monkeypatch.setattr(runtime.engine.model, "generate", lambda *args, **kwargs: "OOC: You're in the starting area right now.")
    output = runtime.handle_ooc_input("What scene are we in?")

    assert output["metadata"]["mode"] == "ooc"
    assert output["messages"][0]["type"] == "ooc_gm"
    assert "starting area" in output["messages"][0]["text"].lower()
    assert runtime.session.state.turn_count == original_turn_count
    assert len(runtime.session.state.conversation_turns) == original_conversation_turns
    assert runtime.session.state.structured_state.runtime.spellbook == original_spellbook
    assert sorted(runtime.session.state.npcs.keys()) == original_npc_ids
    assert runtime.session.message_history[-2]["type"] == "ooc_player"
    assert runtime.session.message_history[-1]["type"] == "ooc_gm"


def test_ooc_input_does_not_trigger_turn_pipeline_side_effects(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)

    monkeypatch.setattr(runtime.engine, "run_turn", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("run_turn should not execute")))
    monkeypatch.setattr(
        runtime,
        "_run_turn_visual_generation",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("visual generation should not execute")),
    )
    monkeypatch.setattr(
        runtime,
        "_maybe_queue_auto_turn_visual",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("auto visual queue should not execute")),
    )
    monkeypatch.setattr(runtime.engine.model, "generate", lambda *args, **kwargs: "OOC: Clarification only.")

    output = runtime.handle_ooc_input("Did narration skip a beat?")
    assert output["messages"][0]["text"].startswith("OOC:")


def test_ooc_structured_spell_generation_updates_spellbook_and_sheet(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_ooc_structured_spells"})
    state = runtime.session.state
    state.structured_state.runtime.spellbook = []
    state.character_sheets = [CharacterSheet.from_payload({"id": "sheet_main", "name": "Aria", "sheet_type": "main_character"})]
    main_sheet = state.character_sheets[0]

    monkeypatch.setattr(
        runtime.engine.model,
        "generate",
        lambda *args, **kwargs: (
            "Here are two ranger spells.\n"
            "[STRUCTURED_SYNC_PAYLOAD]"
            '{"spellbook_entries":[{"name":"Ember Lance","type":"spell","description":"A piercing line of fire."},{"name":"Mist Ward","type":"spell","description":"A defensive veil."}]}'
            "[/STRUCTURED_SYNC_PAYLOAD]"
        ),
    )
    output = runtime.handle_ooc_input("Generate two spells for my spellbook.")

    assert output["metadata"]["ooc_mode"] == "structured_authoring"
    names = [entry.get("name", "") for entry in state.structured_state.runtime.spellbook]
    assert "Ember Lance" in names
    assert "Mist Ward" in names
    assert any(name == "Ember Lance" for name in main_sheet.abilities)
    assert output["metadata"]["ooc_sync"]["spellbook_entries_added"] >= 2


def test_ooc_structured_spell_generation_rejects_conversational_spell_lines(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_ooc_structured_spells_reject"})
    state = runtime.session.state
    state.structured_state.runtime.spellbook = []

    monkeypatch.setattr(
        runtime.engine.model,
        "generate",
        lambda *args, **kwargs: (
            "I can help you choose spells.\n"
            "[STRUCTURED_SYNC_PAYLOAD]"
            "{\"spellbook_entries\":[{\"name\":\"Do you have a preferred level for these new spells?\"},{\"name\":\"Now that we've got your data up to date, what would you like to do next?\"}]}"
            "[/STRUCTURED_SYNC_PAYLOAD]"
        ),
    )

    output = runtime.handle_ooc_input("Generate spells for my spellbook.")
    assert output["metadata"]["ooc_mode"] == "structured_authoring"
    assert output["metadata"]["ooc_sync"]["spellbook_entries_added"] == 0
    assert state.structured_state.runtime.spellbook == []


def test_ooc_structured_character_sheet_update_applies_requested_title(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_ooc_structured_sheet"})
    state = runtime.session.state
    state.character_sheets = [CharacterSheet.from_payload({"id": "sheet_main", "name": "Aria", "sheet_type": "main_character"})]
    main_sheet = state.character_sheets[0]
    main_sheet.level_or_rank = ""
    monkeypatch.setattr(
        runtime.engine.model,
        "generate",
        lambda *args, **kwargs: "Done. Title updated to Kokudar the Ash Lord.",
    )

    output = runtime.handle_ooc_input("Make my title Kokudar the Ash Lord.")

    assert output["metadata"]["ooc_mode"] == "structured_authoring"
    assert main_sheet.level_or_rank == "Kokudar the Ash Lord"
    assert output["metadata"]["ooc_sync"]["character_sheet_updated"] is True


def test_ooc_behavior_rule_detected_and_persisted_as_narrator_rule(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    output = runtime.handle_ooc_input("OOC stop using mysterious hooded figures all the time")

    assert output["metadata"]["ooc_mode"] == "behavior_rule"
    assert "I’ll apply this narrator rule" in output["messages"][0]["text"]
    rules = runtime.get_narrator_rules()
    assert len(rules) == 1
    assert "generic mysterious hooded figures" in rules[0].get("text", "").lower()
    assert rules[0].get("source") == "ooc_behavior_rule"


def test_ooc_behavior_rule_normalizes_investigation_request(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    output = runtime.handle_ooc_input("OOC do not skip over things I explicitly investigate")

    assert output["metadata"]["ooc_mode"] == "behavior_rule"
    rules = runtime.get_narrator_rules()
    assert any("explicitly investigates a target" in entry.get("text", "") for entry in rules)


def test_ooc_behavior_rule_dedupes_repeat_requests(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.handle_ooc_input("OOC keep NPC dialogue shorter")
    runtime.handle_ooc_input("OOC keep npc dialogue short")
    rules = runtime.get_narrator_rules()
    assert len(rules) == 1


def test_ooc_behavior_rule_injected_into_future_prompt_generation(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    capture = _PromptCaptureProvider()
    runtime.engine.model = capture
    runtime.handle_ooc_input("OOC stop making every stranger guarded by default")

    runtime.handle_player_input("I greet the gate guard.")
    assert "Narrator Rules - Hard" in capture.last_system_prompt
    assert "Do not make strangers guarded by default" in capture.last_system_prompt


def test_ooc_behavior_rule_does_not_mutate_structured_or_world_data(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    state = runtime.session.state
    before_spellbook = list(state.structured_state.runtime.spellbook)
    before_world_lore = list(state.structured_state.canon.lore)
    main_sheet = runtime._find_main_character_sheet(state)
    before_title = main_sheet.level_or_rank if main_sheet is not None else ""

    output = runtime.handle_ooc_input("OOC prioritize resolving my direct investigation before introducing distractions")

    assert output["metadata"]["ooc_mode"] == "behavior_rule"
    assert state.structured_state.runtime.spellbook == before_spellbook
    assert state.structured_state.canon.lore == before_world_lore
    if main_sheet is not None:
        assert main_sheet.level_or_rank == before_title


def test_ooc_behavior_rule_campaign_switching_isolated(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"player_name": "Mira", "slot": "slot_behavior_a"})
    runtime.handle_ooc_input("OOC keep NPC dialogue shorter")
    runtime.save_active_campaign("slot_behavior_a")

    runtime.create_campaign({"player_name": "Aric", "slot": "slot_behavior_b"})
    runtime.save_active_campaign("slot_behavior_b")

    runtime.switch_campaign("slot_behavior_a")
    rules_a = runtime.get_narrator_rules()
    runtime.switch_campaign("slot_behavior_b")
    rules_b = runtime.get_narrator_rules()

    assert any("dialogue concise" in entry.get("text", "").lower() for entry in rules_a)
    assert all("dialogue concise" not in entry.get("text", "").lower() for entry in rules_b)


def test_history_and_scene_visual_are_campaign_namespaced(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"player_name": "Mira", "slot": "slot_iso"})
    runtime.handle_player_input("look")
    runtime._set_scene_visual(
        slot="slot_iso",
        image_url="/generated/a.png",
        prompt="scene a",
        source="test",
        stage="after_narration",
        turn=1,
    )
    first_key = runtime._campaign_namespace("slot_iso")
    assert first_key in runtime.history_store
    assert first_key in runtime.scene_visual_store

    runtime.create_campaign({"player_name": "Aric", "slot": "slot_iso"})
    runtime.handle_player_input("status")
    second_key = runtime._campaign_namespace("slot_iso")
    assert second_key in runtime.history_store
    assert second_key != first_key


def test_runtime_does_not_add_session_boilerplate_messages(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    texts = [message["text"] for message in runtime.session.message_history]
    assert "Web session initialized. GUI mode is active." not in texts


class _FailingProvider(NarrationModelAdapter):
    provider_name = "ollama"

    def generate(self, prompt: str, system_prompt: str = "", history=None) -> str:
        raise ProviderUnavailableError("simulated connection failure")


class _ScaffoldLeakProvider(NarrationModelAdapter):
    provider_name = "ollama"

    def generate(self, prompt: str, system_prompt: str = "", history=None) -> str:
        return """[Requested Mode]
play
[Conversation Context]
Recent chat turns: You: look || Narrator: none
[Memory Context]
Recent memory: none
[Scene Context]
Location: Moonfall
[Player State Summary]
HP: 20/20
The lantern-light flickers across the gate as unseen footsteps circle your flank."""


class _SanitizedButGroundedProvider(NarrationModelAdapter):
    provider_name = "ollama"

    def generate(self, prompt: str, system_prompt: str = "", history=None) -> str:
        return """Recent memory: none
Moonfall Keep remains in view. The cracked wall still sheds dust near the torchlit arch."""


class _ScaffoldLabelLeakProvider(NarrationModelAdapter):
    provider_name = "ollama"

    def generate(self, prompt: str, system_prompt: str = "", history=None) -> str:
        return """[Scene]
Rain beads on the broken archway.

[Dialogue]
"Keep low," the scout whispers.

[Immediate Result]
Bootsteps scrape nearby stone."""


class _SuggestedMoveProvider(NarrationModelAdapter):
    provider_name = "ollama"

    def generate(self, prompt: str, system_prompt: str = "", history=None) -> str:
        return "Fog hugs the road as distant bells ring. Suggested next move: question the nearest guard."


class _AdvisoryPhraseProvider(NarrationModelAdapter):
    provider_name = "ollama"

    def generate(self, prompt: str, system_prompt: str = "", history=None) -> str:
        return "Rain glitters on the cobblestones. You could follow the footprints into the alley."


class _PromptCaptureProvider(NarrationModelAdapter):
    provider_name = "ollama"

    def __init__(self) -> None:
        self.last_prompt = ""
        self.last_system_prompt = ""

    def generate(self, prompt: str, system_prompt: str = "", history=None) -> str:
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt
        return "The hall is silent as your minions await your command."


class _ForcedAgencyProvider(NarrationModelAdapter):
    provider_name = "ollama"

    def generate(self, prompt: str, system_prompt: str = "", history=None) -> str:
        return "You decide to kneel before the altar. Dark light spills across the chamber."


class _CountingProvider(NarrationModelAdapter):
    provider_name = "ollama"

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, prompt: str, system_prompt: str = "", history=None) -> str:
        self.calls += 1
        return "A cold wind curls through the archway."


class _RefusalProvider(NarrationModelAdapter):
    provider_name = "ollama"

    def generate(self, prompt: str, system_prompt: str = "", history=None) -> str:
        return "I cannot create that scene."


class _LoopingFillerProvider(NarrationModelAdapter):
    provider_name = "ollama"

    def generate(self, prompt: str, system_prompt: str = "", history=None) -> str:
        return "The throne room trembles and the darkness surrounding you deepens as your minions close in."


class _UngroundedProvider(NarrationModelAdapter):
    provider_name = "ollama"

    def generate(self, prompt: str, system_prompt: str = "", history=None) -> str:
        return "Moonlight reflects across still water while distant bells ring."


class _ShortDialogueProvider(NarrationModelAdapter):
    provider_name = "ollama"

    def generate(self, prompt: str, system_prompt: str = "", history=None) -> str:
        return '"I hear you."'


class _AdvisoryOnlyProvider(NarrationModelAdapter):
    provider_name = "ollama"

    def generate(self, prompt: str, system_prompt: str = "", history=None) -> str:
        return "You should step forward now."


class _WallProgressionProvider(NarrationModelAdapter):
    provider_name = "ollama"

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, prompt: str, system_prompt: str = "", history=None) -> str:
        self.calls += 1
        if self.calls == 1:
            return "Your fireball slams into the wall and leaves cracked, scorched stone."
        return "Your fireball strikes the already-cracked wall, widening the fracture line."


class _RichGroundedProvider(NarrationModelAdapter):
    provider_name = "ollama"

    def generate(self, prompt: str, system_prompt: str = "", history=None) -> str:
        return (
            "Your offer lands hard enough to still the nearby table chatter. "
            "The paladin's jaw tightens, gauntlet creaking on the pommel, while two squires trade a wary glance. "
            "He does not move for his blade, but his next words come measured: “Name your terms.”"
        )


class _FigureIntroProvider(NarrationModelAdapter):
    provider_name = "ollama"

    def generate(self, prompt: str, system_prompt: str = "", history=None) -> str:
        return "A hooded figure lingers beside the broken arch and watches you."


class _MixedSocialNarrationProvider(NarrationModelAdapter):
    provider_name = "ollama"

    def generate(self, prompt: str, system_prompt: str = "", history=None) -> str:
        return (
            "You close the distance by two careful steps, and the man who has been staring straight through you "
            "shifts his weight with a visible hitch in his shoulders. A few nearby patrons go quiet, sensing the "
            "tension between you. When you offer a calm hello, he exhales through his nose and answers low: "
            "“...Hello. Keep your voice down.” His eyes stay on you, waiting to see what you do next."
        )


class _NamedIntroProvider(NarrationModelAdapter):
    provider_name = "ollama"

    def generate(self, prompt: str, system_prompt: str = "", history=None) -> str:
        return 'The woman meets your gaze and says, "My name is Eira."'


class _GuardThenNamedProvider(NarrationModelAdapter):
    provider_name = "ollama"

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, prompt: str, system_prompt: str = "", history=None) -> str:
        self.calls += 1
        if self.calls == 1:
            return "A guard blocks the path and studies you in silence."
        if self.calls == 2:
            return 'The guard lifts his chin. "I am Gravell."'
        return "The guard stays measured, watching for your intent before speaking again."


class _LeakyMerchantLabelProvider(NarrationModelAdapter):
    provider_name = "ollama"

    def generate(self, prompt: str, system_prompt: str = "", history=None) -> str:
        return "Merchant Starting Location watches you quietly from behind the stall."


class _LeakyFigureLabelProvider(NarrationModelAdapter):
    provider_name = "ollama"

    def generate(self, prompt: str, system_prompt: str = "", history=None) -> str:
        return "Figure Starting Location lingers beside the arch and says nothing."


def test_turn_fallback_is_clean_when_provider_fails(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _FailingProvider()
    out = runtime.handle_player_input("look")
    assert out["metadata"]["fallback_used"] is True
    assert out["metadata"]["fallback_reason"] == "simulated connection failure"
    assert "[Local template narrator]" not in out["narrative"]
    assert "[Requested Mode]" not in out["narrative"]


def test_refusal_output_uses_grounded_engine_fallback(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _RefusalProvider()
    out = runtime.handle_player_input("i cast fireball at the wall")
    assert "i cannot" not in out["narrative"].lower()
    assert "fireball" in out["narrative"].lower()
    assert out["metadata"]["quality_fallback_used"] is True
    assert out["metadata"]["quality_invalid_output"] is True


def test_filler_loop_output_is_preserved_when_structurally_valid(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _LoopingFillerProvider()
    out = runtime.handle_player_input("i cast fireball")
    lowered = out["narrative"].lower()
    assert "throne room" in lowered
    assert "your minions" in lowered
    assert out["metadata"]["quality_fallback_used"] is False


def test_ungrounded_output_is_preserved_when_not_structurally_broken(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _UngroundedProvider()
    out = runtime.handle_player_input("i attack the statue")
    lowered = out["narrative"].lower()
    assert "attack" not in lowered or "statue" not in lowered
    assert out["metadata"]["quality_fallback_used"] is False


def test_valid_short_dialogue_is_preserved_without_quality_fallback(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _ShortDialogueProvider()
    out = runtime.handle_player_input('i say "hello there"')
    assert "i hear you" in out["narrative"].lower()
    assert out["metadata"]["quality_fallback_used"] is False
    assert out["metadata"]["quality_invalid_output"] is False


def test_richer_grounded_narration_is_preserved_without_fallback(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _RichGroundedProvider()
    out = runtime.handle_player_input("I offer the paladin a deal.")
    lowered = out["narrative"].lower()
    assert "paladin" in lowered
    assert "squires" in lowered
    assert "name your terms" in lowered
    assert out["metadata"]["quality_fallback_used"] is False


def test_recommendation_only_output_is_not_replaced_with_engine_template(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _AdvisoryOnlyProvider()
    runtime.set_campaign_settings({"player_suggested_moves_override": False})
    out = runtime.handle_player_input("look")
    assert "world holds its breath for a heartbeat" not in out["narrative"].lower()
    assert out["metadata"]["quality_fallback_used"] is False


def test_legacy_payload_loads_with_default_scene_state(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    payload = runtime.session.state.to_dict()
    runtime_payload = payload["structured_state"]["runtime"]
    runtime_payload.pop("scene_state", None)
    loaded = CampaignState.from_dict(payload)
    scene_state = loaded.structured_state.runtime.scene_state
    assert scene_state["damaged_objects"] == []
    assert scene_state["recent_consequences"] == []
    assert "location_id" in scene_state


def test_scene_state_persists_and_progresses_across_turns(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _WallProgressionProvider()
    first = runtime.handle_player_input("i cast fireball at the wall")
    second = runtime.handle_player_input("i cast fireball at the wall again")

    scene_state = runtime.session.state.structured_state.runtime.scene_state
    assert "cracked wall" in " ".join(scene_state["damaged_objects"]).lower()
    assert any("wall" in consequence.lower() for consequence in scene_state["recent_consequences"])
    assert "already-cracked wall" in second["narrative"].lower()
    assert first["narrative"] != second["narrative"]


def test_scene_aware_fallback_reuses_existing_damage_state(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _RefusalProvider()
    first = runtime.handle_player_input("i cast fireball at the wall")
    second = runtime.handle_player_input("i cast fireball at the wall again")
    assert "fireball" in first["narrative"].lower()
    assert "already-cracked wall" in second["narrative"].lower()


def test_perception_fallback_describes_scene_without_boilerplate(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _RefusalProvider()
    out = runtime.handle_player_input("i look around")
    lowered = out["narrative"].lower()
    assert "action resolves immediately" not in lowered
    assert "specific surface features and changes become immediately visible" not in lowered
    assert "look around" not in lowered.split(".")[0]
    assert "moonfall" in lowered or "scene" in lowered or "view" in lowered


def test_what_is_all_around_me_is_classified_as_perception(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _RefusalProvider()
    out = runtime.handle_player_input("what is all around me")
    lowered = out["narrative"].lower()
    assert "you shift position" not in lowered
    assert "remains" in lowered or "in view" in lowered


def test_movement_fallback_describes_changed_viewpoint(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _RefusalProvider()
    out = runtime.handle_player_input("i walk around")
    lowered = out["narrative"].lower()
    assert "you shift position" in lowered or "new viewpoint" in lowered or "changing your angle" in lowered
    assert "your movement changes position right away" not in lowered


def test_attack_spell_fallback_references_existing_damage(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _RefusalProvider()
    runtime.handle_player_input("i cast fireball at the wall")
    out = runtime.handle_player_input("i cast fireball at the wall again")
    lowered = out["narrative"].lower()
    assert "prior damage" in lowered or "already visible" in lowered or "again" in lowered
    assert "point of impact" not in lowered


def test_dialogue_fallback_does_not_invent_npc_reply(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _RefusalProvider()
    out = runtime.handle_player_input('i say "show yourself"')
    lowered = out["narrative"].lower()
    assert "show yourself" in lowered
    assert "no immediate spoken reply" in lowered or "voice carries" in lowered


def test_narrated_figure_registers_scene_actor_and_visible_count(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _FigureIntroProvider()
    runtime.handle_player_input("look")
    scene_state = runtime.session.state.structured_state.runtime.scene_state
    assert any("hooded figure" in actor.get("short_label", "") for actor in scene_state["scene_actors"])
    assert len(scene_state["visible_entities"]) >= 1
    assert any("hooded figure" in item.lower() for item in scene_state["visible_entities"])


def test_dialogue_pronoun_targets_registered_actor_without_direct_reply_shortcut(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _FigureIntroProvider()
    runtime.handle_player_input("look")
    runtime.engine.model = _ShortDialogueProvider()
    out = runtime.handle_player_input("i say 'what do you want?' to them")
    lowered = out["narrative"].lower()
    scene_state = runtime.session.state.structured_state.runtime.scene_state
    assert "i hear you" in lowered
    assert scene_state["last_target_actor_id"]


def test_wait_for_reply_with_visible_actor_stays_on_main_narration_path(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _FigureIntroProvider()
    runtime.handle_player_input("look")
    runtime.engine.model = _ShortDialogueProvider()
    out = runtime.handle_player_input("I wait for their reply")
    lowered = out["narrative"].lower()
    assert "i hear you" in lowered


def test_mixed_social_turn_is_not_collapsed_to_short_npc_reply(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _MixedSocialNarrationProvider()
    runtime.handle_player_input("look")
    out = runtime.handle_player_input("i walk up to the man staring at me and say hello")
    lowered = out["narrative"].lower()
    assert "you close the distance" in lowered
    assert "staring" in lowered
    assert "tension" in lowered
    assert "hello" in lowered
    assert "turns toward you, posture" not in lowered


def test_mixed_social_turn_preserves_full_scene_shape_with_target_context(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _FigureIntroProvider()
    runtime.handle_player_input("look")
    runtime.engine.model = _MixedSocialNarrationProvider()
    out = runtime.handle_player_input("i approach her and ask her name")
    lowered = out["narrative"].lower()
    scene_state = runtime.session.state.structured_state.runtime.scene_state
    assert len(scene_state.get("scene_actors", [])) >= 1
    assert "keep your voice down" in lowered


def test_targeted_dialogue_uses_model_output_instead_of_direct_reply_shortcut(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _FigureIntroProvider()
    runtime.handle_player_input("look")
    counting = _CountingProvider()
    runtime.engine.model = counting
    out = runtime.handle_player_input("i say hello to them")
    assert counting.calls == 1
    assert "cold wind curls through the archway" in out["narrative"].lower()
    assert runtime.session.state.structured_state.runtime.scene_state["last_target_actor_id"]


def test_mixed_social_change_keeps_structured_and_dialogue_paths_intact(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _ShortDialogueProvider()
    runtime.handle_player_input("look")
    pure_dialogue = runtime.handle_player_input('i say "hello there"')
    assert "i hear you" in pure_dialogue["narrative"].lower()
    structured = runtime.handle_player_input("what are my stats")
    assert structured["metadata"]["requested_mode"] == "structured_lookup"


def test_lightweight_npc_scene_state_persists_and_stays_campaign_scoped(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _FigureIntroProvider()
    runtime.create_campaign({"slot": "slot_npc_scope_a"})
    runtime.handle_player_input("look")
    runtime.handle_player_input("i say 'hello' to them")
    runtime.save_active_campaign("slot_npc_scope_a")

    runtime.create_campaign({"slot": "slot_npc_scope_b"})
    scene_b = runtime.session.state.structured_state.runtime.scene_state
    assert scene_b.get("lightweight_npcs", []) == []
    runtime.save_active_campaign("slot_npc_scope_b")

    reloaded = _runtime(tmp_path, monkeypatch)
    reloaded.switch_campaign("slot_npc_scope_a")
    scene_a = reloaded.session.state.structured_state.runtime.scene_state
    assert len(scene_a.get("lightweight_npcs", [])) >= 1
    assert isinstance(scene_a["lightweight_npcs"][0].get("personality_profile"), dict)
    assert reloaded.serialize_state()["character_sheets"] == []


def test_lightweight_npc_gets_generated_personality_profile_on_materialization(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _FigureIntroProvider()
    runtime.handle_player_input("look")
    runtime.handle_player_input("i say hello to them")
    scene_state = runtime.session.state.structured_state.runtime.scene_state
    assert scene_state.get("lightweight_npcs")
    profile = scene_state["lightweight_npcs"][0].get("personality_profile", {})
    assert profile.get("baseline_temperament")
    assert profile.get("conversational_tone")
    assert profile.get("stress_response")


def test_narration_name_intro_registers_real_npc_profile_and_world_building_entry(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _NamedIntroProvider()
    runtime.handle_player_input('i say "who are you?"')
    state = runtime.session.state
    eira = next((npc for npc in state.npcs.values() if npc.name == "Eira"), None)
    assert eira is not None
    assert eira.personality_profile is not None
    payload = runtime.get_world_building_view()
    assert any(entry.get("name") == "Eira" for entry in payload["npc_personalities"])


def test_named_npc_intro_does_not_duplicate_entity_on_repeat_mentions(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _NamedIntroProvider()
    runtime.handle_player_input('i say "who are you?"')
    first_ids = {npc.id for npc in runtime.session.state.npcs.values() if npc.name == "Eira"}
    runtime.handle_player_input("i nod and listen")
    second_ids = {npc.id for npc in runtime.session.state.npcs.values() if npc.name == "Eira"}
    assert len(first_ids) == 1
    assert first_ids == second_ids


def test_named_npc_intro_persists_across_turns_and_save_reload(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _NamedIntroProvider()
    runtime.create_campaign({"slot": "slot_eira"})
    runtime.handle_player_input('i say "who are you?"')
    runtime.handle_player_input("look")
    assert any(npc.name == "Eira" for npc in runtime.session.state.npcs.values())
    runtime.save_active_campaign("slot_eira")

    reloaded = _runtime(tmp_path, monkeypatch)
    reloaded.switch_campaign("slot_eira")
    reloaded_eira = next((npc for npc in reloaded.session.state.npcs.values() if npc.name == "Eira"), None)
    assert reloaded_eira is not None
    assert reloaded_eira.personality_profile is not None


def test_alias_resolution_maps_guard_label_back_to_named_npc(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _GuardThenNamedProvider()
    runtime.handle_player_input("look")
    runtime.handle_player_input('i say "who are you?"')
    runtime.handle_player_input('i say "guard, answer me."')

    state = runtime.session.state
    gravell_entries = [npc for npc in state.npcs.values() if npc.name == "Gravell"]
    assert len(gravell_entries) == 1
    assert not any(npc.name.lower() == "guard" for npc in state.npcs.values())
    scene_state = state.structured_state.runtime.scene_state
    guard_actor = next(
        (
            actor
            for actor in scene_state.get("scene_actors", [])
            if isinstance(actor, dict) and str(actor.get("short_label", "")).strip().lower() == "guard"
        ),
        None,
    )
    assert guard_actor is not None
    assert str(guard_actor.get("linked_npc_id", "")).strip() == gravell_entries[0].id


def test_unnamed_actor_name_reveal_updates_same_entity_instead_of_duplicate(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _GuardThenNamedProvider()
    runtime.handle_player_input("look")
    scene_state = runtime.session.state.structured_state.runtime.scene_state
    assert any(str(actor.get("short_label", "")).strip().lower() == "guard" for actor in scene_state.get("scene_actors", []))

    runtime.handle_player_input('i say "state your name."')
    names = sorted(npc.name for npc in runtime.session.state.npcs.values())
    assert names.count("Gravell") == 1
    assert "Guard" not in names


def test_sanitized_grounded_output_is_kept_without_quality_fallback(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _SanitizedButGroundedProvider()
    out = runtime.handle_player_input("look")
    lowered = out["narrative"].lower()
    assert out["metadata"]["sanitized_output"] is True
    assert out["metadata"]["quality_fallback_used"] is False
    assert "cracked wall" in lowered


def test_fallback_regression_blocks_abstract_placeholder_phrases(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _RefusalProvider()
    outputs = [
        runtime.handle_player_input("i look around")["narrative"].lower(),
        runtime.handle_player_input("i cast fireball at the wall")["narrative"].lower(),
        runtime.handle_player_input("i walk around")["narrative"].lower(),
    ]
    merged = " ".join(outputs)
    assert "the action resolves immediately" not in merged
    assert "the immediate outcome is visible at the point of impact" not in merged
    assert "your movement changes position right away" not in merged
    assert "specific surface features and changes become immediately visible" not in merged


def test_scene_state_summary_is_injected_into_prompt(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    capture = _PromptCaptureProvider()
    runtime.engine.model = capture
    runtime.handle_player_input("i cast fireball at the wall")
    runtime.handle_player_input("i cast fireball at the wall again")
    assert "Current Scene State:" in capture.last_prompt
    assert "Damaged objects:" in capture.last_prompt


def test_turn_prompt_uses_separated_gm_brief_sections(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    capture = _PromptCaptureProvider()
    runtime.engine.model = capture
    runtime.handle_player_input("i cast fireball at the wall")
    prompt = capture.last_prompt
    assert "[CURRENT PLAYER ACTION]" in prompt
    assert "[SCENE / SETTING]" in prompt
    assert "[NPCS IN SCENE]" in prompt
    assert "[ENEMIES / THREATS]" in prompt
    assert "[PLAYER FACTS]" in prompt
    assert "[RECENT CONSEQUENCES]" in prompt
    assert "[NARRATOR RULES]" in prompt
    assert "[WRITING INSTRUCTIONS]" in prompt


def test_turn_prompt_includes_identity_continuity_guidance_for_npcs(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    capture = _PromptCaptureProvider()
    runtime.engine.model = _NamedIntroProvider()
    runtime.handle_player_input('i say "who are you?"')
    runtime.engine.model = capture
    runtime.handle_player_input('i say "the stranger should answer."')
    prompt = capture.last_prompt
    assert "reuse established NPC names once introduced" in prompt
    assert "Do not rename existing NPCs" in prompt
    assert "Generic references" in prompt


def test_turn_prompt_keeps_npcs_and_enemies_in_separate_sections(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    capture = _PromptCaptureProvider()
    runtime.engine.model = capture
    runtime.session.state.active_enemy_id = "goblin_raider"
    runtime.session.state.active_enemy_hp = 12
    runtime.handle_player_input("look")
    prompt = capture.last_prompt
    npc_idx = prompt.find("[NPCS IN SCENE]")
    enemy_idx = prompt.find("[ENEMIES / THREATS]")
    assert npc_idx >= 0
    assert enemy_idx > npc_idx
    assert "Hostile threat active: goblin_raider (HP 12)." in prompt


def test_turn_prompt_retains_player_system_feeds(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    capture = _PromptCaptureProvider()
    runtime.engine.model = capture
    runtime.session.state.player.inventory = ["torch", "field_draught"]
    runtime.session.state.structured_state.runtime.spellbook = [{"name": "Arc Bolt", "type": "spell"}]
    runtime.upsert_narrator_rule({"action": "upsert", "text": "Keep the moonlight imagery grounded in the current location."})
    runtime.handle_player_input("look")
    prompt = capture.last_prompt
    assert "[PLAYER FACTS]" in prompt
    assert "Inventory highlights: torch, field_draught" in prompt
    assert "Spellbook highlights: Arc Bolt" in prompt
    assert "[NARRATOR RULES]" in prompt
    assert "Keep the moonlight imagery grounded in the current location." in prompt


def test_expressive_indirect_resolution_is_not_invalidated(tmp_path: Path, monkeypatch) -> None:
    class _IndirectResolutionProvider(NarrationModelAdapter):
        provider_name = "ollama"

        def generate(self, prompt: str, system_prompt: str = "", history=None) -> str:
            return (
                "Heat blooms across the stone as your casting gesture lands; dust peels from the seam and a jagged line "
                "threads outward through the wall while nearby voices choke off into silence."
            )

    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _IndirectResolutionProvider()
    out = runtime.handle_player_input("i cast fireball at the wall")
    assert out["metadata"]["quality_invalid_output"] is False
    assert out["metadata"]["quality_fallback_used"] is False
    assert "jagged line" in out["narrative"].lower()


def test_scene_state_lists_are_capped_and_deduped(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _RefusalProvider()
    for _ in range(8):
        runtime.handle_player_input("i cast fireball at the wall")
    scene_state = runtime.session.state.structured_state.runtime.scene_state
    assert len(scene_state["recent_consequences"]) <= 5
    assert len(scene_state["damaged_objects"]) <= 8
    assert scene_state["damaged_objects"].count("cracked wall") == 1


def test_system_and_structured_turns_do_not_mutate_scene_state(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _RefusalProvider()
    runtime.handle_player_input("i cast fireball at the wall")
    before = dict(runtime.session.state.structured_state.runtime.scene_state)
    runtime.handle_player_input("what are your narrator rules")
    runtime.handle_player_input("what are my stats")
    after = runtime.session.state.structured_state.runtime.scene_state
    assert after["damaged_objects"] == before["damaged_objects"]
    assert after["recent_consequences"] == before["recent_consequences"]


def test_repetitive_output_uses_fallback_on_second_turn(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _CountingProvider()
    first = runtime.handle_player_input("look")
    second = runtime.handle_player_input("look around")
    third = runtime.handle_player_input("inspect the chamber")
    fourth = runtime.handle_player_input("inspect again")
    assert first["narrative"] != ""
    assert second["metadata"]["quality_repetitive_output"] is False
    assert second["metadata"]["quality_fallback_used"] is False
    assert third["metadata"]["quality_repetitive_output"] is False
    assert third["metadata"]["quality_fallback_used"] is False
    assert fourth["metadata"]["quality_repetitive_output"] is True
    assert fourth["metadata"]["quality_fallback_used"] is True


def test_turn_sanitizer_removes_prompt_scaffold_leaks(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _ScaffoldLeakProvider()
    out = runtime.handle_player_input("look")
    assert "Recent chat turns:" not in out["narrative"]
    assert "Recent memory:" not in out["narrative"]
    assert "[Requested Mode]" not in out["narrative"]
    assert out["metadata"]["quality_fallback_used"] is False


def test_turn_sanitizer_removes_internal_scaffold_labels_but_preserves_readability(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _ScaffoldLabelLeakProvider()
    out = runtime.handle_player_input("look")
    assert "[Scene]" not in out["narrative"]
    assert "[Dialogue]" not in out["narrative"]
    assert "[Immediate Result]" not in out["narrative"]
    assert '"Keep low," the scout whispers.' in out["narrative"]
    assert "\n\n" in out["narrative"]


def test_turn_sanitizer_keeps_normal_prose_unchanged(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _PromptCaptureProvider()
    out = runtime.handle_player_input("look")
    assert out["narrative"] == "The hall is silent as your minions await your command."
    assert out["metadata"]["sanitized_output"] is False


def test_recommendations_are_not_engine_suppressed_when_not_broken(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _SuggestedMoveProvider()

    runtime.set_campaign_settings({"player_suggested_moves_override": True})
    normal_turn = runtime.handle_player_input("look")
    assert "Suggested next move:" in normal_turn["narrative"]

    guidance_turn = runtime.handle_player_input("what should I do next?")
    assert "Suggested next move:" in guidance_turn["narrative"]


def test_recommendations_are_hard_removed_when_campaign_setting_is_disabled(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _SuggestedMoveProvider()
    runtime.set_campaign_settings({"player_suggested_moves_override": False})

    guidance_turn = runtime.handle_player_input("what should I do next?")
    assert "Suggested next move:" in guidance_turn["narrative"]
    assert guidance_turn["metadata"]["recommendation_cleanup_applied"] is False


def test_regression_valid_advisory_narration_is_no_longer_rewritten(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _AdvisoryPhraseProvider()
    runtime.set_campaign_settings({"player_suggested_moves_override": False})

    out = runtime.handle_player_input("look")
    assert "You could" in out["narrative"]
    assert out["metadata"]["recommendation_cleanup_applied"] is False


def test_custom_narrator_rules_persist_and_remain_campaign_scoped(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"player_name": "Mira", "slot": "slot_rule_a"})
    runtime.upsert_narrator_rule({"action": "upsert", "text": "Use darker gothic tone"})
    runtime.save_active_campaign("slot_rule_a")

    runtime.create_campaign({"player_name": "Aric", "slot": "slot_rule_b"})
    runtime.upsert_narrator_rule({"action": "upsert", "text": "Keep combat responses short and brutal"})
    runtime.save_active_campaign("slot_rule_b")

    runtime.switch_campaign("slot_rule_a")
    rules_a = runtime.get_narrator_rules()
    runtime.switch_campaign("slot_rule_b")
    rules_b = runtime.get_narrator_rules()

    assert any("darker gothic tone" in entry.get("text", "").lower() for entry in rules_a)
    assert all("darker gothic tone" not in entry.get("text", "").lower() for entry in rules_b)


def test_custom_narrator_rules_are_injected_into_prompt(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    capture = _PromptCaptureProvider()
    runtime.engine.model = capture
    runtime.upsert_narrator_rule({"action": "upsert", "text": "Never describe my emotions unless I state them"})
    runtime.handle_player_input("look around")
    assert "Narrator Rules - Hard" in capture.last_system_prompt
    assert "Never describe my emotions unless I state them" in capture.last_system_prompt


def test_narrator_rules_request_returns_system_only_without_narrator_or_model_call(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    counting = _CountingProvider()
    runtime.engine.model = counting
    runtime.upsert_narrator_rule({"action": "upsert", "text": "Keep consequences concrete"})

    out = runtime.handle_player_input("what are your narrator rules")

    assert counting.calls == 0
    assert out["narrative"] == ""
    assert out["metadata"]["requested_mode"] == "system"
    assert any(message["text"] == "Narrator rules:" for message in out["messages"])
    assert any("1. Keep consequences concrete" == message["text"] for message in out["messages"])
    assert all(message["type"] != "narrator" for message in out["messages"])


def test_stats_request_returns_structured_only_without_narrator_or_model_call(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    counting = _CountingProvider()
    runtime.engine.model = counting

    out = runtime.handle_player_input("what are my stats")

    assert counting.calls == 0
    assert out["narrative"] == ""
    assert out["metadata"]["requested_mode"] == "structured_lookup"
    assert any("HP" in message["text"] for message in out["messages"])
    assert all(message["type"] != "narrator" for message in out["messages"])


def test_gameplay_turn_still_generates_narrator_output(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    counting = _CountingProvider()
    runtime.engine.model = counting

    out = runtime.handle_player_input("i cast holy nova")

    assert counting.calls == 1
    assert out["narrative"] != ""
    assert any(message["type"] == "narrator" for message in out["messages"])


def test_internal_thought_turn_is_treated_as_gameplay(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    counting = _CountingProvider()
    runtime.engine.model = counting

    out = runtime.handle_player_input("i think to myself")

    assert out["metadata"]["requested_mode"] == "play"
    assert out["narrative"] != ""
    assert any(message["type"] == "narrator" for message in out["messages"])


def test_internal_stats_wording_does_not_route_to_structured(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    counting = _CountingProvider()
    runtime.engine.model = counting

    out = runtime.handle_player_input("i wonder what my stats are")

    assert out["metadata"]["requested_mode"] == "play"
    assert out["narrative"] != ""
    assert counting.calls == 1
    assert any(message["type"] == "narrator" for message in out["messages"])


def test_internal_thought_narration_is_not_engine_rewritten(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _PromptCaptureProvider()

    out = runtime.handle_player_input("i consider my next move")
    narrative = out["narrative"].lower()

    assert narrative != ""


def test_narration_sanitizes_merchant_starting_location_label(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _LeakyMerchantLabelProvider()
    out = runtime.handle_player_input("i approach the stall")
    lowered = out["narrative"].lower()
    assert "starting location" not in lowered
    assert "_starting_location" not in lowered
    assert "_start" not in lowered
    assert "merchant starting location" not in lowered
    assert "the merchant" in lowered


def test_narration_sanitizes_figure_starting_location_label(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _LeakyFigureLabelProvider()
    out = runtime.handle_player_input("i wait")
    lowered = out["narrative"].lower()
    assert "starting location" not in lowered
    assert "_starting_location" not in lowered
    assert "_start" not in lowered
    assert "figure starting location" not in lowered
    assert ("the shadowed figure" in lowered) or ("the figure" in lowered)


def test_build_structured_messages_skips_blank_narrator_payload(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    payload = runtime.engine._build_structured_messages(["Status delivered."], "   ")
    assert payload == [{"type": "system", "text": "Status delivered."}]


def test_custom_never_make_decisions_rule_is_prompt_driven_without_engine_cleanup(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _ForcedAgencyProvider()
    runtime.upsert_narrator_rule({"action": "upsert", "text": "Never make decisions for me"})
    out = runtime.handle_player_input("wait")
    assert "You decide to" in out["narrative"]
    assert out["metadata"]["custom_rule_cleanup_applied"] is False


def test_system_prompt_contains_narrative_quality_examples_and_handoff_guidance(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    capture = _PromptCaptureProvider()
    runtime.engine.model = capture
    runtime.handle_player_input("I enter the guild.")
    system_prompt = capture.last_system_prompt
    assert "[Narrative Examples]" in system_prompt
    assert "I offer the paladin a deal." in system_prompt
    assert "End on a clean handoff point" in system_prompt


def test_settings_include_ollama_unavailable_status(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)

    monkeypatch.setattr(
        "models.ollama_adapter.OllamaAdapter.check_readiness",
        lambda self: {
            "provider": "ollama",
            "model": self.model,
            "base_url": self.base_url,
            "reachable": False,
            "model_exists": False,
            "ready": False,
            "user_message": "Ollama is not running. Start Ollama to use this model provider.",
            "fallback_reason": "offline",
        },
    )
    settings = runtime.set_global_settings({"model": {"provider": "ollama", "model_name": "llama3"}})
    assert settings["model_status"]["ready"] is False
    assert settings["model_status"]["user_message"] == "Ollama is not running. Start Ollama to use this model provider."


def test_turn_metadata_surfaces_model_status(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.engine.model = _FailingProvider()
    runtime.app_config.model.provider = "ollama"
    runtime.app_config.model.model_name = "llama3"
    monkeypatch.setattr(
        "models.ollama_adapter.OllamaAdapter.check_readiness",
        lambda self: {
            "provider": "ollama",
            "model": self.model,
            "base_url": self.base_url,
            "reachable": False,
            "model_exists": False,
            "ready": False,
            "user_message": "Ollama is not running. Start Ollama to use this model provider.",
            "fallback_reason": "offline",
        },
    )
    out = runtime.handle_player_input("look")
    assert out["metadata"]["model_status"]["ready"] is False
    assert out["metadata"]["model_status"]["provider"] == "ollama"


def test_image_generation_requires_comfyui_readiness(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.set_campaign_settings({"image_generation_enabled": True})
    runtime.set_global_settings({"image": {"provider": "comfyui", "base_url": "http://127.0.0.1:9", "enabled": True}})

    result = runtime.generate_image({"workflow_id": "scene_image", "prompt": "Moonlit ruins"})
    assert result.success is False
    assert "comfyui" in (result.error or "").lower()
    assert result.metadata.get("provider") == "comfyui"


def test_auto_after_visual_updates_scene_panel_without_image_chat_message(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.set_global_settings({"image": {"provider": "comfyui", "campaign_auto_visual_timing": "after_narration"}})
    runtime.set_campaign_settings({"image_generation_enabled": True, "play_style": {"scene_visual_mode": "after_narration"}})
    monkeypatch.setattr(runtime, "get_image_status", lambda: {"ready": True})
    output_file = runtime.generated_image_dir / "turn_visual.png"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_bytes(b"fake")
    monkeypatch.setattr(
        runtime,
        "generate_image",
        lambda payload: ImageGenerationResult(
            success=True,
            workflow_id="scene_image",
            result_path=str(output_file),
            metadata={"image": {"filename": "turn_visual.png", "type": "output"}},
        ),
    )

    runtime._run_turn_visual_generation(
        player_action="inspect the rune",
        narrator_response="Blue sparks arc across the old stone and illuminate hidden glyphs.",
        stage="after_narration",
    )

    assert not any(message.get("type") == "image" for message in runtime.session.message_history)
    scene_visual = runtime._scene_visual_for_slot()
    assert scene_visual is not None
    assert scene_visual["image_url"].endswith("/generated/turn_visual.png")
    assert scene_visual["source"] == "automatic"
    assert scene_visual["caption"] == "Scene visual reflects the current area."


def test_campaign_auto_visual_timing_aliases_normalize_to_supported_values(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    settings = runtime.set_global_settings({"image": {"campaign_auto_visual_timing": "auto_after"}})
    assert settings["image"]["campaign_auto_visual_timing"] == "after_narration"


def test_auto_after_turn_visual_only_queues_for_meaningful_narration(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    queued: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        runtime,
        "_run_turn_visual_generation_async",
        lambda player_action, narrator_response, stage, source: queued.append((player_action, narrator_response, stage, source)) or True,
    )

    not_queued = runtime._maybe_queue_auto_turn_visual(
        auto_enabled=True,
        auto_timing="after_narration",
        player_action="look around",
        narrator_response="...",
        stage="after_narration",
    )
    assert not_queued is False
    assert queued == []

    queued_ok = runtime._maybe_queue_auto_turn_visual(
        auto_enabled=True,
        auto_timing="after_narration",
        player_action="look around",
        narrator_response="The torchlight reveals wet stone arches and a narrow bridge over dark water.",
        stage="after_narration",
    )
    assert queued_ok is True
    assert len(queued) == 1


@pytest.mark.parametrize(
    ("mode", "expected_auto_enabled", "expected_timing"),
    [
        ("off", False, "off"),
        ("manual", False, "off"),
        ("before_narration", True, "before_narration"),
        ("after_narration", True, "after_narration"),
    ],
)
def test_scene_visual_mode_is_single_source_for_auto_behavior(
    tmp_path: Path, monkeypatch, mode: str, expected_auto_enabled: bool, expected_timing: str
) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.set_campaign_settings(
        {
            "image_generation_enabled": True,
            "play_style": {"scene_visual_mode": mode},
            "campaign_auto_visuals_enabled": not expected_auto_enabled,
        }
    )
    runtime.set_global_settings({"image": {"provider": "comfyui", "campaign_auto_visual_timing": "off"}})
    monkeypatch.setattr(runtime, "get_image_status", lambda: {"ready": False})
    captured: list[tuple[bool, str, str]] = []
    monkeypatch.setattr(
        runtime,
        "_maybe_queue_auto_turn_visual",
        lambda auto_enabled, auto_timing, player_action, narrator_response, stage: captured.append(
            (auto_enabled, auto_timing, stage)
        )
        or False,
    )

    runtime.handle_player_input("look around")
    assert captured
    assert captured[0][0] is expected_auto_enabled
    assert captured[0][1] == expected_timing


def test_manual_visual_generation_works_when_scene_visual_mode_is_off(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.set_campaign_settings({"play_style": {"scene_visual_mode": "off"}})
    monkeypatch.setattr(runtime, "get_image_status", lambda: {"ready": True})
    output_file = runtime.generated_image_dir / "manual_scene.png"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_bytes(b"fake")
    monkeypatch.setattr(
        runtime,
        "generate_image",
        lambda payload: ImageGenerationResult(
            success=True,
            workflow_id="scene_image",
            result_path=str(output_file),
            metadata={"image": {"filename": "manual_scene.png", "type": "output"}},
        ),
    )

    runtime._run_turn_visual_generation(
        player_action="raise lantern",
        narrator_response="Dark stone glitters in the rain.",
        stage="manual",
        source="manual",
    )
    scene_visual = runtime._scene_visual_for_slot()
    assert scene_visual is not None
    assert scene_visual["source"] == "manual"


def test_manual_prompt_override_is_forwarded_unchanged(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.set_campaign_settings({"play_style": {"scene_visual_mode": "off"}})
    monkeypatch.setattr(runtime, "get_image_status", lambda: {"ready": True})
    output_file = runtime.generated_image_dir / "manual_override.png"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_bytes(b"fake")
    captured_payload: dict[str, Any] = {}

    def _fake_generate(payload: dict[str, Any]) -> ImageGenerationResult:
        captured_payload.update(payload)
        return ImageGenerationResult(
            success=True,
            workflow_id="scene_image",
            result_path=str(output_file),
            metadata={"image": {"filename": "manual_override.png", "type": "output"}},
        )

    monkeypatch.setattr(runtime, "generate_image", _fake_generate)
    runtime._request_scene_visual_generation(
        source="manual",
        stage="manual",
        player_action="",
        narrator_response="",
        prompt_override="manual custom prompt with exact wording",
    )
    assert captured_payload["prompt"] == "manual custom prompt with exact wording"
    assert captured_payload.get("negative_prompt", "") == ""


def test_after_narration_prompt_uses_full_scene_not_only_first_sentence(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.set_global_settings({"image": {"provider": "comfyui"}})
    runtime.set_campaign_settings({"image_generation_enabled": True, "play_style": {"scene_visual_mode": "after_narration"}})
    monkeypatch.setattr(runtime, "get_image_status", lambda: {"ready": True})
    output_file = runtime.generated_image_dir / "full_scene.png"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_bytes(b"fake")
    captured_payload: dict[str, Any] = {}

    def _fake_generate(payload: dict[str, Any]) -> ImageGenerationResult:
        captured_payload.update(payload)
        return ImageGenerationResult(
            success=True,
            workflow_id="scene_image",
            result_path=str(output_file),
            metadata={"image": {"filename": "full_scene.png", "type": "output"}},
        )

    monkeypatch.setattr(runtime, "generate_image", _fake_generate)
    runtime._run_turn_visual_generation(
        player_action="cast arc bolt at the raider",
        narrator_response=(
            "Aria hurls a crackling bolt across the hall. "
            "The raider slams into a broken pillar as blue sparks scatter over the floor."
        ),
        stage="after_narration",
    )

    assert "broken pillar" in captured_payload["prompt"]
    assert "blue sparks scatter" in captured_payload["prompt"]


def test_auto_visual_continuity_state_is_persisted_in_scene_state(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.set_global_settings({"image": {"provider": "comfyui"}})
    runtime.set_campaign_settings({"image_generation_enabled": True})
    monkeypatch.setattr(runtime, "get_image_status", lambda: {"ready": True})
    output_file = runtime.generated_image_dir / "continuity.png"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_bytes(b"fake")
    monkeypatch.setattr(
        runtime,
        "generate_image",
        lambda payload: ImageGenerationResult(
            success=True,
            workflow_id="scene_image",
            result_path=str(output_file),
            metadata={"image": {"filename": "continuity.png", "type": "output"}},
        ),
    )
    runtime.session.state.structured_state.runtime.scene_state = {
        "location_name": "Old Chapel",
        "scene_summary": "Moonlight and dust in a broken nave.",
        "active_effects": ["violet aura around gauntlet"],
    }
    runtime._run_turn_visual_generation(
        player_action="raise warding hand",
        narrator_response="The ward flares and casts sharp shadows across cracked stone.",
        stage="after_narration",
    )
    continuity = runtime.session.state.structured_state.runtime.scene_state.get("visual_continuity", {})
    assert isinstance(continuity, dict)
    assert continuity.get("lighting") in {"moonlight", "sharp shadows", ""}
    assert "persistent_magic_effects" in continuity

def test_auto_turn_visual_async_dedupes_same_slot_turn_and_stage(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.set_global_settings({"image": {"provider": "comfyui", "campaign_auto_visual_timing": "after_narration"}})
    runtime.set_campaign_settings({"image_generation_enabled": True, "play_style": {"scene_visual_mode": "after_narration"}})
    monkeypatch.setattr(runtime, "_run_turn_visual_generation", lambda *args, **kwargs: time.sleep(0.1))

    first = runtime._run_turn_visual_generation_async("inspect", "A vivid chamber blooms with blue witchlight.", "after_narration", "auto_after")
    second = runtime._run_turn_visual_generation_async("inspect", "A vivid chamber blooms with blue witchlight.", "after_narration", "auto_after")

    assert first is True
    assert second is False


def test_dependency_readiness_ollama_offline(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.model.provider = "ollama"
    runtime.app_config.model.model_name = "llama3"
    monkeypatch.setattr("shutil.which", lambda name: "C:/Ollama/ollama.exe")
    monkeypatch.setattr(
        "models.ollama_adapter.OllamaAdapter.check_readiness",
        lambda self: {
            "provider": "ollama",
            "model": self.model,
            "base_url": self.base_url,
            "reachable": False,
            "model_exists": False,
            "ready": False,
            "user_message": "Ollama is not running. Start Ollama to use this model provider.",
            "fallback_reason": "offline",
        },
    )
    readiness = runtime.get_dependency_readiness()
    model_provider = readiness["items"][0]
    assert model_provider["provider_type"] == "model_provider"
    assert model_provider["reachable"] is False
    assert "ollama serve" in model_provider["next_action"]


def test_dependency_readiness_ollama_online_model_missing(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.model.provider = "ollama"
    runtime.app_config.model.model_name = "llama3"
    monkeypatch.setattr(
        "models.ollama_adapter.OllamaAdapter.check_readiness",
        lambda self: {
            "provider": "ollama",
            "model": self.model,
            "base_url": self.base_url,
            "reachable": True,
            "model_exists": False,
            "ready": False,
            "user_message": "Model llama3 is not installed in Ollama. Run: ollama pull llama3",
            "fallback_reason": "missing model",
        },
    )
    readiness = runtime.get_dependency_readiness()
    model_item = readiness["items"][1]
    assert model_item["provider_type"] == "selected_model"
    assert model_item["model_exists"] is False
    assert "ollama pull llama3" in model_item["next_action"]


def test_dependency_readiness_ollama_online_model_present(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.model.provider = "ollama"
    monkeypatch.setattr(
        "models.ollama_adapter.OllamaAdapter.check_readiness",
        lambda self: {
            "provider": "ollama",
            "model": self.model,
            "base_url": self.base_url,
            "reachable": True,
            "model_exists": True,
            "ready": True,
            "user_message": "Ollama is ready with model llama3.",
            "fallback_reason": "",
        },
    )
    readiness = runtime.get_dependency_readiness()
    assert readiness["items"][0]["status_level"] == "ready"
    assert readiness["items"][1]["status_level"] == "ready"


def test_dependency_readiness_comfyui_offline(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.image.provider = "comfyui"
    comfy_dir = tmp_path / "ComfyUI"
    comfy_dir.mkdir(parents=True, exist_ok=True)
    (comfy_dir / "main.py").write_text("print('ok')", encoding="utf-8")
    (comfy_dir / "custom_nodes").mkdir(exist_ok=True)
    (comfy_dir / "models" / "checkpoints").mkdir(parents=True, exist_ok=True)
    (comfy_dir / "run_cpu.bat").write_text("@echo off", encoding="utf-8")
    workflow = tmp_path / "scene.json"
    workflow.write_text("{}", encoding="utf-8")
    runtime.app_config.image.comfyui_path = str(comfy_dir)
    runtime.app_config.image.comfyui_workflow_path = str(workflow)
    runtime.app_config.image.checkpoint_folder = str(comfy_dir / "models" / "checkpoints")
    monkeypatch.setattr(runtime, "_find_comfyui_root", lambda: comfy_dir)
    monkeypatch.setattr(
        "images.comfyui_adapter.ComfyUIAdapter.check_readiness",
        lambda self: {
            "provider": "comfyui",
            "base_url": self.base_url,
            "reachable": False,
            "ready": False,
            "status_level": "error",
            "user_message": "ComfyUI is not reachable at the configured address.",
            "next_action": "Start ComfyUI, then click Recheck.",
            "error": "connection refused",
        },
    )
    readiness = runtime.get_dependency_readiness()
    image_item = readiness["items"][2]
    assert image_item["provider_type"] == "image_provider"
    assert image_item["reachable"] is False
    assert image_item["status_code"] == "not_running"
    assert image_item["actions"][0]["id"] == "start_image_engine"


def test_dependency_readiness_does_not_pollute_story_messages(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    _ = runtime.get_dependency_readiness()
    messages_before = len(runtime.session.message_history)
    runtime.handle_player_input("look")
    messages_after = [message["text"] for message in runtime.session.message_history]
    assert len(messages_after) > messages_before


def test_start_ollama_logs_setup_action(tmp_path: Path, monkeypatch, capsys) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.model.provider = "ollama"
    monkeypatch.setattr("shutil.which", lambda _: "C:/Ollama/ollama.exe")
    monkeypatch.setattr(
        runtime,
        "get_model_status",
        lambda: {"provider": "ollama", "reachable": True, "model_exists": True, "ready": True},
    )

    result = runtime.start_ollama_service()
    captured = capsys.readouterr()
    assert result["ok"] is True
    assert "[setup-action] start-ollama requested" in captured.out
    assert "[setup-action] start-ollama success" in captured.out


def test_install_model_logs_setup_action(tmp_path: Path, monkeypatch, capsys) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    monkeypatch.setattr("shutil.which", lambda _: "C:/Ollama/ollama.exe")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args=args[0], returncode=0, stdout="already exists", stderr=""),
    )

    result = runtime.install_story_model("llama3")
    captured = capsys.readouterr()
    assert result["ok"] is True
    assert "[setup-action] install-model requested model=llama3" in captured.out
    assert "[setup-action] install-model success model=llama3" in captured.out
    assert result["message"] == "Story model installed. Text generation is ready."


def test_setup_endpoints_invoke_backend_actions(tmp_path: Path, monkeypatch, capsys) -> None:
    try:
        from fastapi.testclient import TestClient
    except RuntimeError as exc:
        pytest.skip(str(exc))
    runtime = _runtime(tmp_path, monkeypatch)
    app = create_web_app(runtime, runtime.root / "app" / "static")
    client = TestClient(app)

    monkeypatch.setattr(runtime, "start_ollama_service", lambda: {"ok": True, "message": "started"})
    monkeypatch.setattr(runtime, "install_ollama", lambda: {"ok": True, "message": "installed ollama"})
    monkeypatch.setattr(runtime, "install_story_model", lambda model_name=None: {"ok": True, "message": f"installed {model_name}"})
    monkeypatch.setattr(runtime, "install_image_engine", lambda: {"ok": True, "message": "installed comfyui"})
    monkeypatch.setattr(runtime, "start_image_engine", lambda: {"ok": True, "message": "started comfyui"})
    monkeypatch.setattr(runtime, "orchestrate_setup_text_ai", lambda model_name=None: {"ok": True, "message": f"orchestrated text {model_name}"})
    monkeypatch.setattr(runtime, "orchestrate_setup_image_ai", lambda: {"ok": True, "message": "orchestrated image"})
    monkeypatch.setattr(runtime, "orchestrate_setup_everything", lambda model_name=None: {"ok": True, "message": f"orchestrated all {model_name}"})

    start_response = client.post("/api/setup/start-ollama", json={})
    install_ollama_response = client.post("/api/setup/install-ollama", json={})
    install_response = client.post("/api/setup/install-model", json={"model": "llama3"})
    install_image_response = client.post("/api/setup/install-image-engine", json={})
    start_image_response = client.post("/api/setup/start-image-engine", json={})
    orchestrate_text_response = client.post("/api/setup/orchestrate-text", json={"model": "llama3"})
    orchestrate_image_response = client.post("/api/setup/orchestrate-image", json={})
    orchestrate_everything_response = client.post("/api/setup/orchestrate-everything", json={"model": "llama3"})
    captured = capsys.readouterr()

    assert start_response.status_code == 200
    assert install_ollama_response.status_code == 200
    assert install_response.status_code == 200
    assert start_response.json()["ok"] is True
    assert install_ollama_response.json()["ok"] is True
    assert install_response.json()["ok"] is True
    assert install_image_response.json()["ok"] is True
    assert start_image_response.json()["ok"] is True
    assert orchestrate_text_response.json()["ok"] is True
    assert orchestrate_image_response.json()["ok"] is True
    assert orchestrate_everything_response.json()["ok"] is True
    assert "[setup-action] route invoked endpoint=/api/setup/start-ollama" in captured.out
    assert "[setup-action] route invoked endpoint=/api/setup/install-ollama" in captured.out
    assert "[setup-action] route invoked endpoint=/api/setup/install-model model=llama3" in captured.out
    assert "[setup-action] route invoked endpoint=/api/setup/install-image-engine" in captured.out
    assert "[setup-action] route invoked endpoint=/api/setup/start-image-engine" in captured.out
    assert "[setup-action] route invoked endpoint=/api/setup/orchestrate-text model=llama3" in captured.out
    assert "[setup-action] route invoked endpoint=/api/setup/orchestrate-image" in captured.out
    assert "[setup-action] route invoked endpoint=/api/setup/orchestrate-everything model=llama3" in captured.out


def test_visual_pipeline_endpoints_apply_and_validate(tmp_path: Path, monkeypatch) -> None:
    try:
        from fastapi.testclient import TestClient
    except RuntimeError as exc:
        pytest.skip(str(exc))
    runtime = _runtime(tmp_path, monkeypatch)
    app = create_web_app(runtime, runtime.root / "app" / "static")
    client = TestClient(app)

    comfy_root = tmp_path / "ComfyUI"
    comfy_root.mkdir(parents=True, exist_ok=True)
    (comfy_root / "main.py").write_text("print('ok')", encoding="utf-8")
    (comfy_root / "custom_nodes").mkdir(exist_ok=True)
    (comfy_root / "models").mkdir(exist_ok=True)
    (comfy_root / "run_cpu.bat").write_text("@echo off", encoding="utf-8")
    workflow = tmp_path / "scene.json"
    workflow.write_text("{}", encoding="utf-8")
    checkpoints = comfy_root / "models" / "checkpoints"
    checkpoints.mkdir(parents=True, exist_ok=True)
    payload = {
        "comfyui_path": str(comfy_root),
        "comfyui_workflow_path": str(workflow),
        "comfyui_output_dir": "",
        "checkpoint_folder": str(checkpoints),
    }

    validate_response = client.post("/api/settings/visual-pipeline/validate", json=payload)
    apply_response = client.post("/api/settings/visual-pipeline", json=payload)

    assert validate_response.status_code == 200
    assert validate_response.json()["path_config"]["image"]["pipeline_ready"] is True
    assert apply_response.status_code == 200
    assert apply_response.json()["ok"] is True


def test_pick_file_endpoint_returns_selected_path(tmp_path: Path, monkeypatch) -> None:
    try:
        from fastapi.testclient import TestClient
    except RuntimeError as exc:
        pytest.skip(str(exc))
    runtime = _runtime(tmp_path, monkeypatch)
    app = create_web_app(runtime, runtime.root / "app" / "static")
    client = TestClient(app)
    monkeypatch.setattr(runtime, "pick_file", lambda title, initial_path="", filters=None: {"ok": True, "path": "/tmp/workflow.json"})

    response = client.post("/api/setup/pick-file", json={"title": "Select workflow", "filters": [".json"]})
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["path"].endswith("workflow.json")


def test_guided_image_setup_endpoints_proxy_runtime_methods(tmp_path: Path, monkeypatch) -> None:
    try:
        from fastapi.testclient import TestClient
    except RuntimeError as exc:
        pytest.skip(str(exc))
    runtime = _runtime(tmp_path, monkeypatch)
    app = create_web_app(runtime, runtime.root / "app" / "static")
    client = TestClient(app)

    monkeypatch.setattr(runtime, "get_image_setup_snapshot", lambda: {"ready": False, "message": "snapshot"})
    monkeypatch.setattr(runtime, "use_bundled_image_engine", lambda: {"ok": True, "message": "bundled"})
    monkeypatch.setattr(runtime, "save_checkpoint_folder", lambda path: {"ok": True, "path": path})
    monkeypatch.setattr(runtime, "skip_images_for_now", lambda: {"ok": True, "message": "skipped"})

    snapshot_response = client.get("/api/setup/image-readiness-card")
    bundled_response = client.post("/api/setup/use-bundled-image-engine", json={})
    checkpoint_response = client.post("/api/setup/save-checkpoint-folder", json={"path": "/tmp/checkpoints"})
    skip_response = client.post("/api/setup/skip-images", json={})

    assert snapshot_response.status_code == 200
    assert snapshot_response.json()["message"] == "snapshot"
    assert bundled_response.status_code == 200
    assert bundled_response.json()["message"] == "bundled"
    assert checkpoint_response.status_code == 200
    assert checkpoint_response.json()["path"] == "/tmp/checkpoints"
    assert skip_response.status_code == 200
    assert skip_response.json()["message"] == "skipped"


def test_desktop_setup_endpoints_proxy_runtime_methods(tmp_path: Path, monkeypatch) -> None:
    try:
        from fastapi.testclient import TestClient
    except RuntimeError as exc:
        pytest.skip(str(exc))
    runtime = _runtime(tmp_path, monkeypatch)
    app = create_web_app(runtime, runtime.root / "app" / "static")
    client = TestClient(app)

    monkeypatch.setattr(runtime, "get_desktop_capabilities", lambda: {"ok": True, "desktop": {"mode": "desktop_packaged"}})
    monkeypatch.setattr(runtime, "open_external_url", lambda url: {"ok": True, "url": url, "method": "os.startfile"})
    monkeypatch.setattr(runtime, "stop_image_engine", lambda: {"ok": True, "message": "stopped"})

    capabilities_response = client.get("/api/desktop/capabilities")
    open_url_response = client.post("/api/setup/open-external-url", json={"url": "https://example.com"})
    stop_image_response = client.post("/api/setup/stop-image-engine", json={})

    assert capabilities_response.status_code == 200
    assert capabilities_response.json()["desktop"]["mode"] == "desktop_packaged"
    assert open_url_response.status_code == 200
    assert open_url_response.json()["url"] == "https://example.com"
    assert stop_image_response.status_code == 200
    assert stop_image_response.json()["message"] == "stopped"


def test_first_run_status_exposes_packaging_and_setup_states(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    monkeypatch.setattr(
        runtime,
        "get_model_status",
        lambda: {"provider": "ollama", "ready": False, "reachable": False, "model_exists": False, "user_message": "Ollama missing."},
    )
    monkeypatch.setattr(
        runtime,
        "get_image_status",
        lambda: {"provider": "comfyui", "ready": False, "reachable": False, "user_message": "ComfyUI not running."},
    )
    monkeypatch.setattr(
        runtime,
        "get_path_configuration_status",
        lambda: {"image": {"checkpoint_dir": {"valid": False, "message": "Checkpoint folder is required.", "path": ""}}},
    )
    monkeypatch.setattr(
        runtime,
        "get_installer_layout_status",
        lambda: {
            "state": "invalid",
            "valid": False,
            "summary": "Installer layout is invalid.",
            "missing_required": ["bundled_image_runtime", "workflow_scene_image"],
            "packaged_app_files_present": False,
            "bundled_image_runtime_present": False,
            "bundled_workflows_present": False,
            "embedded_python_present": False,
            "checks": {
                "runtime_bundle": {"message": "Missing required packaged folder: runtime_bundle."},
                "bundled_image_runtime": {"path": str(tmp_path / "missing_bundle"), "present": False},
            },
        },
    )

    status = runtime.get_first_run_status()

    assert status["app_installed"]["state"] in {"ready", "not_packaged"}
    assert status["text_ai"]["state"] == "not_ready"
    assert status["image_engine_bundle"]["state"] == "missing"
    assert status["bundled_workflows"]["state"] == "missing"
    assert status["embedded_python"]["state"] == "missing"
    assert status["installer_layout"]["state"] == "invalid"
    assert status["packaged_app_files"]["state"] == "missing"
    assert status["model_folder"]["state"] == "missing"
    assert status["text_only_mode"]["state"] in {"active", "inactive"}


def test_image_setup_snapshot_includes_installer_layout_payload(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    monkeypatch.setattr(runtime, "get_first_run_status", lambda: {"app_installed": {"state": "ready"}})
    monkeypatch.setattr(
        runtime,
        "get_installer_layout_status",
        lambda: {
            "state": "invalid",
            "valid": False,
            "checks": {"bundled_image_runtime": {"present": False, "path": ""}},
            "missing_required": ["bundled_image_runtime"],
        },
    )
    snapshot = runtime.get_image_setup_snapshot()
    assert snapshot["installer_layout"]["state"] == "invalid"
    assert snapshot["bundled_comfyui_available"] is False


def test_campaign_recalibrate_endpoint_invokes_runtime_recalibration(tmp_path: Path, monkeypatch) -> None:
    try:
        from fastapi.testclient import TestClient
    except RuntimeError as exc:
        pytest.skip(str(exc))
    runtime = _runtime(tmp_path, monkeypatch)
    app = create_web_app(runtime, runtime.root / "app" / "static")
    client = TestClient(app)
    monkeypatch.setattr(runtime, "recalibrate_campaign_state", lambda state: {"ok": True, "abilities_synced": 1})

    response = client.post("/api/campaign/recalibrate", json={})

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_campaign_input_endpoint_routes_ic_and_ooc_modes(tmp_path: Path, monkeypatch) -> None:
    try:
        from fastapi.testclient import TestClient
    except RuntimeError as exc:
        pytest.skip(str(exc))
    runtime = _runtime(tmp_path, monkeypatch)
    app = create_web_app(runtime, runtime.root / "app" / "static")
    client = TestClient(app)

    monkeypatch.setattr(
        runtime,
        "handle_player_input",
        lambda text: {"messages": [{"type": "narrator", "text": f"IC:{text}"}], "metadata": {"mode": "ic"}, "state": runtime.serialize_state()},
    )
    monkeypatch.setattr(
        runtime,
        "handle_ooc_input",
        lambda text: {"messages": [{"type": "ooc_gm", "text": f"OOC:{text}"}], "metadata": {"mode": "ooc"}, "state": runtime.serialize_state()},
    )

    ic_response = client.post("/api/campaign/input", json={"text": "look", "mode": "ic"})
    ooc_response = client.post("/api/campaign/input", json={"text": "what happened?", "mode": "ooc"})
    bad_mode = client.post("/api/campaign/input", json={"text": "hello", "mode": "meta"})

    assert ic_response.status_code == 200
    assert ic_response.json()["metadata"]["mode"] == "ic"
    assert ooc_response.status_code == 200
    assert ooc_response.json()["metadata"]["mode"] == "ooc"
    assert bad_mode.status_code == 400


def test_dependency_readiness_comfyui_not_installed(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.image.provider = "comfyui"
    monkeypatch.setattr(runtime, "_find_comfyui_root", lambda: None)
    monkeypatch.setattr(
        "images.comfyui_adapter.ComfyUIAdapter.check_readiness",
        lambda self: {"provider": "comfyui", "base_url": self.base_url, "reachable": False, "ready": False, "status_level": "error", "user_message": "offline", "next_action": "n/a", "error": "connection refused"},
    )
    readiness = runtime.get_dependency_readiness()
    image_item = readiness["items"][2]
    assert image_item["status_code"] in {"not_installed", "setup_required"}
    assert image_item["actions"][0]["id"] in {"install_image_engine", "recheck"}


def test_campaign_list_includes_unreadable_save_files(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    bad_save = runtime.paths.saves / "broken_slot.json"
    bad_save.write_text("{not_json", encoding="utf-8")
    campaigns = runtime.list_campaigns()
    match = next(item for item in campaigns if item["slot"] == "broken_slot")
    assert match["loadable"] is False


def test_validate_comfyui_install_reports_missing_launcher(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    comfy_dir = tmp_path / "user_data" / "tools" / "ComfyUI"
    comfy_dir.mkdir(parents=True, exist_ok=True)
    (comfy_dir / "main.py").write_text("print('ok')", encoding="utf-8")
    (comfy_dir / "custom_nodes").mkdir(exist_ok=True)
    (comfy_dir / "models").mkdir(exist_ok=True)

    validation = runtime.validate_comfyui_install(comfy_dir)
    assert validation["ok"] is False
    assert "run_cpu.bat|run_nvidia_gpu.bat" in validation["missing_files"]


def test_install_image_engine_repairs_missing_launcher(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.image.provider = "comfyui"
    monkeypatch.setattr(runtime, "_is_windows", lambda: True)
    monkeypatch.setattr("webbrowser.open", lambda *_args, **_kwargs: True)

    def _fake_download(target_dir: Path) -> tuple[bool, str]:
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "main.py").write_text("print('ok')", encoding="utf-8")
        (target_dir / "custom_nodes").mkdir(exist_ok=True)
        (target_dir / "models").mkdir(exist_ok=True)
        return True, "ok"

    monkeypatch.setattr(runtime, "_download_and_extract_comfyui", _fake_download)
    result = runtime.install_image_engine()
    assert result["ok"] is True
    comfy_dir = Path(runtime.app_config.image.comfyui_path)
    assert (comfy_dir / "run_cpu.bat").exists()


def test_start_image_engine_repairs_launcher_before_failing(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.image.provider = "comfyui"
    comfy_dir = tmp_path / "user_data" / "tools" / "ComfyUI"
    comfy_dir.mkdir(parents=True, exist_ok=True)
    (comfy_dir / "main.py").write_text("print('ok')", encoding="utf-8")
    (comfy_dir / "custom_nodes").mkdir(exist_ok=True)
    (comfy_dir / "models").mkdir(exist_ok=True)
    runtime.app_config.image.comfyui_path = str(comfy_dir)
    workflow = tmp_path / "scene.json"
    workflow.write_text("{}", encoding="utf-8")
    checkpoint_dir = comfy_dir / "models" / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    runtime.app_config.image.comfyui_workflow_path = str(workflow)
    runtime.app_config.image.checkpoint_folder = str(checkpoint_dir)

    monkeypatch.setattr(runtime, "_find_comfyui_root", lambda: comfy_dir)
    monkeypatch.setattr(runtime, "get_image_status", lambda: {"reachable": False})
    monkeypatch.setattr("shutil.which", lambda _name: "python")

    launch_calls = {"count": 0}

    def _fake_popen(*_args, **_kwargs):
        launch_calls["count"] += 1
        raise OSError("simulated launch failure")

    monkeypatch.setattr("subprocess.Popen", _fake_popen)
    result = runtime.start_image_engine()
    assert (comfy_dir / "run_cpu.bat").exists()
    assert launch_calls["count"] == 1
    assert result["ok"] is False
    assert result["failure_stage"] == "launch-engine"


def test_start_image_engine_detects_early_exit_and_exposes_startup_log(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.image.provider = "comfyui"
    comfy_dir = tmp_path / "user_data" / "tools" / "ComfyUI"
    comfy_dir.mkdir(parents=True, exist_ok=True)
    (comfy_dir / "main.py").write_text("print('ok')", encoding="utf-8")
    (comfy_dir / "run_cpu.bat").write_text("@echo off\r\npython main.py\r\n", encoding="utf-8")
    (comfy_dir / "custom_nodes").mkdir(exist_ok=True)
    (comfy_dir / "models" / "checkpoints").mkdir(parents=True, exist_ok=True)
    workflow = tmp_path / "scene.json"
    workflow.write_text("{}", encoding="utf-8")
    runtime.app_config.image.comfyui_path = str(comfy_dir)
    runtime.app_config.image.comfyui_workflow_path = str(workflow)
    runtime.app_config.image.checkpoint_folder = str(comfy_dir / "models" / "checkpoints")

    monkeypatch.setattr(runtime, "_find_comfyui_root", lambda: comfy_dir)
    monkeypatch.setattr(runtime, "get_image_status", lambda: {"reachable": False})
    monkeypatch.setattr("time.sleep", lambda _seconds: None)

    class _Proc:
        stdout = True

        def poll(self):
            return 1

        def communicate(self, timeout=0.0):
            return ("Traceback (most recent call last):\nModuleNotFoundError: x\n", "")

    monkeypatch.setattr("subprocess.Popen", lambda *_args, **_kwargs: _Proc())
    result = runtime.start_image_engine()
    assert result["ok"] is False
    assert result["failure_stage_message"] == "ComfyUI exited during startup"
    assert result["startup_status"]["reason"] == "process-exited-immediately"
    assert "modulenotfounderror" in result["startup_status"]["runtime_error_hint"]


def test_start_image_engine_validates_bundled_layout_before_launch_in_packaged_mode(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.image.provider = "comfyui"
    bundled_comfy = tmp_path / "runtime_bundle" / "comfyui"
    bundled_comfy.mkdir(parents=True, exist_ok=True)
    (bundled_comfy / "main.py").write_text("print('ok')", encoding="utf-8")
    (bundled_comfy / "run_cpu.bat").write_text("@echo off\r\npython main.py\r\n", encoding="utf-8")
    (bundled_comfy / "custom_nodes").mkdir(exist_ok=True)
    (bundled_comfy / "models" / "checkpoints").mkdir(parents=True, exist_ok=True)
    workflow = tmp_path / "scene.json"
    workflow.write_text("{}", encoding="utf-8")
    runtime.app_config.image.comfyui_path = str(bundled_comfy)
    runtime.app_config.image.comfyui_workflow_path = str(workflow)
    runtime.app_config.image.checkpoint_folder = str(bundled_comfy / "models" / "checkpoints")

    monkeypatch.setattr(runtime.desktop, "_capabilities", runtime.desktop.capabilities.__class__(**{
        **runtime.desktop.capabilities.to_dict(),
        "mode": "desktop_packaged",
    }))
    monkeypatch.setattr("app.web.bundled_comfyui_dir", lambda: bundled_comfy)
    monkeypatch.setattr(runtime, "get_image_status", lambda: {"reachable": False})
    monkeypatch.setattr(
        runtime,
        "get_installer_layout_status",
        lambda: {"valid": False, "state": "invalid", "missing_required": ["workflow_scene_image"], "summary": "invalid"},
    )

    result = runtime.start_image_engine()
    assert result["ok"] is False
    assert result["failure_stage"] == "layout-validation"
    assert "workflow_scene_image" in result["missing_required"]


def test_dependency_readiness_includes_image_startup_status(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.image_startup_status = {"reason": "runtime-error-in-launcher-output", "summary": "runtime error", "log_text": "error line"}
    readiness = runtime.get_dependency_readiness()
    image_item = readiness["items"][2]
    assert image_item["startup_status"]["reason"] == "runtime-error-in-launcher-output"
    assert "runtime error" in image_item["startup_status"]["summary"]


def test_dependency_readiness_reports_missing_ollama_install(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.model.provider = "ollama"
    monkeypatch.setattr("shutil.which", lambda name: None)
    monkeypatch.setattr(
        "models.ollama_adapter.OllamaAdapter.check_readiness",
        lambda self: {
            "provider": "ollama",
            "model": self.model,
            "base_url": self.base_url,
            "reachable": False,
            "model_exists": False,
            "ready": False,
            "user_message": "Ollama is not running.",
            "fallback_reason": "offline",
            "error": "connection refused",
        },
    )
    readiness = runtime.get_dependency_readiness()
    provider_item = readiness["items"][0]
    assert "not installed" in provider_item["user_message"].lower()
    assert provider_item["actions"][0]["id"] == "install_ollama"


def test_start_ollama_reports_missing_cli(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.model.provider = "ollama"
    monkeypatch.setattr("shutil.which", lambda name: None)
    result = runtime.start_ollama_service()
    assert result["ok"] is False
    assert "not installed" in result["message"].lower()


def test_install_story_model_runs_pull_and_returns_success(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    monkeypatch.setattr("shutil.which", lambda name: "/bin/ollama")

    monkeypatch.setattr(runtime, "get_model_status", lambda: {"reachable": True})

    def _fake_run(*args, **kwargs):
        assert kwargs["encoding"] == "utf-8"
        assert kwargs["errors"] == "replace"
        return subprocess.CompletedProcess(args=["ollama", "pull", "llama3"], returncode=0, stdout="pulled", stderr="")

    monkeypatch.setattr("subprocess.run", _fake_run)
    result = runtime.install_story_model("llama3")
    assert result["ok"] is True
    assert "installed" in result["message"].lower()


def test_orchestrate_text_ai_from_missing_model_to_ready(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.model.provider = "ollama"
    states = iter(
        [
            {"reachable": False, "model_exists": False},
            {"reachable": True, "model_exists": False},
            {"reachable": True, "model_exists": True},
        ]
    )
    monkeypatch.setattr(runtime, "get_model_status", lambda: next(states))
    monkeypatch.setattr(runtime, "_find_ollama_cli", lambda: "C:/Ollama/ollama.exe")
    monkeypatch.setattr(runtime, "start_ollama_service", lambda: {"ok": True, "message": "started"})
    monkeypatch.setattr(runtime, "install_story_model", lambda model_name=None: {"ok": True, "message": "installed model"})
    monkeypatch.setattr(runtime, "_refresh_readiness_snapshot", lambda: {"items": []})
    result = runtime.orchestrate_setup_text_ai("llama3")
    assert result["ok"] is True
    assert result["summary"] == "Text AI ready."


def test_orchestrate_everything_combines_text_and_image_results(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    monkeypatch.setattr(runtime, "orchestrate_setup_text_ai", lambda model_name=None: {"ok": True, "message": "text ok"})
    monkeypatch.setattr(runtime, "orchestrate_setup_image_ai", lambda: {"ok": True, "message": "image ok"})
    monkeypatch.setattr(runtime, "_refresh_readiness_snapshot", lambda: {"items": []})
    result = runtime.orchestrate_setup_everything("llama3")
    assert result["ok"] is True
    assert "Text AI ready. Image AI ready." in result["summary"]


def test_install_story_model_requires_running_ollama(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    monkeypatch.setattr("shutil.which", lambda name: "/bin/ollama")
    monkeypatch.setattr(runtime, "get_model_status", lambda: {"reachable": False})
    result = runtime.install_story_model("llama3")
    assert result["ok"] is False
    assert "not running" in result["message"].lower()


def test_install_ollama_windows_flow_logs(tmp_path: Path, monkeypatch, capsys) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.app_config.model.provider = "ollama"
    monkeypatch.setattr(runtime, "_is_windows", lambda: True)
    states = iter([None, "C:/Ollama/ollama.exe"])
    monkeypatch.setattr(runtime, "_find_ollama_cli", lambda: next(states))
    monkeypatch.setattr(runtime, "_resolve_ollama_windows_installer_url", lambda: "https://ollama.com/download/OllamaSetup.exe")

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"fake-exe"

    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: _Resp())
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: SimpleNamespace(wait=lambda timeout=None: 0))
    monkeypatch.setattr(runtime, "start_ollama_service", lambda: {"ok": True, "message": "started"})

    result = runtime.install_ollama()
    captured = capsys.readouterr()
    assert result["ok"] is True
    assert "[setup-action] install-ollama requested" in captured.out
    assert "[setup-action] downloading installer url=https://ollama.com/download/OllamaSetup.exe" in captured.out
    assert "[setup-action] installer launched" in captured.out
    assert "[setup-action] install-ollama success" in captured.out

def test_create_campaign_with_character_sheets_persists_and_restores(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    payload = {
        "player_name": "Kael",
        "char_class": "Summoner",
        "slot": "slot_sheets",
        "character_sheet_guidance_strength": "strong",
        "character_sheets": [
            {
                "id": "mc_1",
                "name": "Kael",
                "sheet_type": "main_character",
                "role": "leader",
                "archetype": "stormbound tactician",
                "level_or_rank": "5",
                "faction": "Guild",
                "description": "Carries a living rune blade.",
                "stats": {"health": 14, "energy_or_mana": 20, "attack": 11, "defense": 9, "speed": 10, "magic": 15, "willpower": 13, "presence": 12},
                "traits": ["curious", "focused"],
                "abilities": ["storm sigil", "binding chain"],
                "equipment": ["rune blade"],
                "weaknesses": ["pride"],
                "temperament": "measured",
                "loyalty": "guild",
                "social_style": "direct",
                "speech_style": "precise",
                "state": {"morale": 8, "bond_to_player": 10, "current_condition": "steady"},
            }
        ],
    }
    created = runtime.create_campaign(payload)
    assert created["state"]["character_sheet_guidance_strength"] == "strong"
    assert len(created["state"]["character_sheets"]) == 1
    assert created["state"]["character_sheets"][0]["sheet_type"] == "main_character"
    assert created["state"]["player"]["hp"] == 14
    assert created["state"]["player"]["max_hp"] == 14
    assert created["state"]["player"]["attack"] == 11
    assert created["state"]["player"]["defense"] == 9
    assert created["state"]["player"]["magic"] == 15
    assert created["state"]["player"]["class"] == "leader"

    runtime.switch_campaign("slot_sheets")
    assert runtime.session.state.character_sheet_guidance_strength == "strong"
    assert runtime.session.state.character_sheets[0].name == "Kael"
    assert runtime.session.state.player.hp == 14
    assert runtime.session.state.player.max_hp == 14


def test_create_campaign_without_character_sheets_keeps_defaults(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    created = runtime.create_campaign({"player_name": "Aria", "char_class": "Ranger", "slot": "slot_default"})
    assert created["state"]["player"]["hp"] == 20
    assert created["state"]["player"]["max_hp"] == 20
    assert created["state"]["player"]["class"] == "Ranger"

def test_image_pipeline_test_action_succeeds_when_configured(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    comfy_root = tmp_path / "ComfyUI"
    comfy_root.mkdir(parents=True, exist_ok=True)
    (comfy_root / "main.py").write_text("print('ok')", encoding="utf-8")
    (comfy_root / "custom_nodes").mkdir(exist_ok=True)
    (comfy_root / "models" / "checkpoints").mkdir(parents=True, exist_ok=True)
    (comfy_root / "run_cpu.bat").write_text("@echo off", encoding="utf-8")
    workflow = tmp_path / "scene.json"
    workflow.write_text("{}", encoding="utf-8")

    runtime.set_global_settings(
        {
            "image": {
                "provider": "comfyui",
                "enabled": True,
                "comfyui_path": str(comfy_root),
                "comfyui_workflow_path": str(workflow),
                "checkpoint_folder": str(comfy_root / "models" / "checkpoints"),
                "preferred_checkpoint": "",
            }
        }
    )
    monkeypatch.setattr("images.comfyui_adapter.ComfyUIAdapter.check_readiness", lambda self: {"ready": True, "user_message": "ready"})
    monkeypatch.setattr("images.comfyui_adapter.ComfyUIAdapter._list_checkpoints", lambda self: ["dreamshaper.safetensors"])
    monkeypatch.setattr(
        "images.comfyui_adapter.ComfyUIAdapter.generate",
        lambda self, request, _manager: ImageGenerationResult(success=True, workflow_id=request.workflow_id, prompt_id="pid", result_path="/tmp/out.png"),
    )

    result = runtime.test_image_pipeline()
    assert result["success"] is True
    assert result["failing_step"] == ""


def test_image_pipeline_test_action_fails_when_workflow_path_missing(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    comfy_root = tmp_path / "ComfyUI"
    comfy_root.mkdir(parents=True, exist_ok=True)
    (comfy_root / "main.py").write_text("print('ok')", encoding="utf-8")
    (comfy_root / "custom_nodes").mkdir(exist_ok=True)
    (comfy_root / "models" / "checkpoints").mkdir(parents=True, exist_ok=True)
    (comfy_root / "run_cpu.bat").write_text("@echo off", encoding="utf-8")

    runtime.set_global_settings(
        {
            "image": {
                "provider": "comfyui",
                "enabled": True,
                "comfyui_path": str(comfy_root),
                "comfyui_workflow_path": str(tmp_path / "missing.json"),
                "checkpoint_folder": str(comfy_root / "models" / "checkpoints"),
                "preferred_checkpoint": "",
            }
        }
    )

    result = runtime.test_image_pipeline()
    assert result["success"] is False
    assert result["failing_step"] == "workflow_path"


def test_new_campaign_seeds_scene_state(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    created = runtime.create_campaign(
        {
            "slot": "slot_seed",
            "world_name": "Vel Astren",
            "world_theme": "dark fantasy",
            "starting_location_name": "Black Harbor",
            "premise": "The sea is haunted.",
        }
    )
    scene_state = runtime.session.state.structured_state.runtime.scene_state
    assert scene_state["location_name"] == "Black Harbor"
    assert "Vel Astren" in scene_state["scene_summary"]
    assert scene_state["altered_environment"] == []
    assert scene_state["damaged_objects"] == []


def test_scene_state_survives_save_and_load(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_scene_persist", "starting_location_name": "Glass Docks"})
    before = dict(runtime.session.state.structured_state.runtime.scene_state)
    runtime.save_active_campaign("slot_scene_persist")

    reloaded = _runtime(tmp_path, monkeypatch)
    reloaded.switch_campaign("slot_scene_persist")
    after = reloaded.session.state.structured_state.runtime.scene_state
    assert after["location_name"] == before["location_name"]
    assert after["scene_summary"] == before["scene_summary"]


def test_narrator_rules_persist_after_restart_and_switch_isolated(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"player_name": "Mira", "slot": "slot_rules_a"})
    runtime.upsert_narrator_rule({"action": "upsert", "text": "Rule A tone"})
    runtime.save_active_campaign("slot_rules_a")

    runtime.create_campaign({"player_name": "Aric", "slot": "slot_rules_b"})
    runtime.save_active_campaign("slot_rules_b")

    reloaded = _runtime(tmp_path, monkeypatch)
    capture = _PromptCaptureProvider()
    reloaded.engine.model = capture

    reloaded.switch_campaign("slot_rules_a")
    reloaded.handle_player_input("look")
    assert "Rule A tone" in capture.last_system_prompt

    reloaded.switch_campaign("slot_rules_b")
    reloaded.handle_player_input("look")
    assert "Rule A tone" not in capture.last_system_prompt


def test_world_building_button_and_modal_markup_present_in_left_controls() -> None:
    index_html = Path("app/static/index.html").read_text(encoding="utf-8")
    app_js = Path("app/static/app.js").read_text(encoding="utf-8")
    narrator_idx = index_html.index('id="open-narrator-rules"')
    world_idx = index_html.index('id="open-world-building"')
    assert narrator_idx < world_idx
    assert ">World Building</button>" in index_html
    assert 'id="world-building-modal"' in index_html
    assert "NPC Personalities" in index_html
    assert "World Design" in index_html
    assert "Reactive World Changes" in index_html
    assert 'id="recalibrate-world-building"' in index_html
    assert ">Recalibrate</button>" in index_html
    assert "No NPC personalities generated yet." in index_html
    assert "No world design entries available yet." in index_html
    assert "No reactive world changes recorded yet." in index_html
    assert "open-world-building" in app_js
    assert "/api/campaign/world-building" in app_js
    assert "/api/campaign/recalibrate" in app_js


def test_world_building_modal_places_recalibrate_left_of_close_on_same_row() -> None:
    index_html = Path("app/static/index.html").read_text(encoding="utf-8")
    styles_css = Path("app/static/styles.css").read_text(encoding="utf-8")
    action_row_match = re.search(
        r'<div class="button-row world-building-actions-row">\s*<button id="recalibrate-world-building"[^>]*>Recalibrate</button>\s*<button id="close-world-building"[^>]*>Close</button>',
        index_html,
        flags=re.S,
    )
    assert action_row_match is not None
    assert ".world-building-actions-row {" in styles_css
    assert "display: flex;" in styles_css


def test_world_building_view_returns_empty_collections_when_no_data(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_world_empty"})
    runtime.session.state.npcs = {}
    runtime.session.state.important_world_facts = []
    runtime.session.state.structured_state.canon.lore = []
    runtime.session.state.structured_state.runtime.discovered_locations = []
    runtime.session.state.world_events = []
    runtime.session.state.structured_state.runtime.scene_state = {}
    payload = runtime.get_world_building_view()
    assert payload["npc_personalities"] == []
    assert payload["world_design"] == []
    assert payload["reactive_world_changes"] == []


def test_world_building_view_surfaces_real_npc_world_and_reactive_data(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_world_rich", "starting_location_name": "Black Harbor"})
    state = runtime.session.state
    if state.npcs:
        npc = next(iter(state.npcs.values()))
    else:
        npc = NPC(id="npc_captain_myra", name="Captain Myra", location_id=state.current_location_id)
        state.npcs[npc.id] = npc
    npc.name = "Captain Myra"
    if npc.personality_profile is None:
        npc.personality_profile = NPC.PersonalityProfile()
    npc.personality_profile.archetype = "Veteran Captain"
    npc.personality_profile.baseline_temperament = "Disciplined but compassionate"
    npc.personality_profile.social_style = "Direct leadership"
    npc.personality_profile.motivations = "Protect the harbor and crew"
    npc.personality_profile.conversational_tone = "Measured and practical"
    npc.personality_profile.conflict_response = "Prefers strategic de-escalation"
    npc.dynamic_state.current_mood = "Wary respect"
    npc.applied_evolution_rules = ["Became more trusting after the dock rescue"]
    state.structured_state.runtime.scene_state = {
        "npc_conditions": {npc.id: ["Recovering from storm injuries"]},
        "altered_environment": ["Collapsed pier blocks eastern docking lane"],
        "recent_consequences": ["Harbor watch doubled night patrols after sabotage"],
        "active_effects": ["Smuggler network laying low but still active"],
    }
    state.important_world_facts = ["The moon-tide determines safe passage through the reefs."]
    state.structured_state.canon.lore = ["The Black Beacon was built by exiled star-mages."]
    state.structured_state.runtime.discovered_locations = [state.current_location_id]
    state.faction_reputation = {"Harbor Watch": 15}
    state.unresolved_plot_threads = ["Who funded the dock saboteurs?"]
    state.recent_memory = ["Captain Myra asked the party for a discreet investigation."]
    state.world_events = ["Emergency council called in Black Harbor."]
    state.structured_state.recent_turn_memory.recent_discoveries = ["Recovered coded ledger from smuggler cache."]

    payload = runtime.get_world_building_view()
    assert payload["npc_personalities"]
    assert payload["npc_personalities"][0]["name"] == "Captain Myra"
    assert payload["npc_personalities"][0]["current_persistent_conditions"] == ["Recovering from storm injuries"]
    world_design_labels = {entry["label"] for entry in payload["world_design"]}
    reactive_labels = {entry["label"] for entry in payload["reactive_world_changes"]}
    assert "World Facts" in world_design_labels
    assert "Discovered Lore" in world_design_labels
    assert "Persistent Environment Changes" in reactive_labels
    assert "Major Scene Consequences" in reactive_labels


def test_world_design_excludes_raw_narration_logs_and_keeps_structured_entries(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_world_design_cleanup"})
    state = runtime.session.state
    state.important_world_facts = ["The citadel gate closes at moonrise."]
    state.recent_memory = ["Narrator: Full paragraph narration that should not be listed in world design."]
    state.world_flags = {"citadel_alert": True}
    payload = runtime.get_world_building_view()
    labels = {entry["label"] for entry in payload["world_design"]}
    merged_entries = " ".join(item for group in payload["world_design"] for item in group.get("entries", []))
    assert "Persistent State" in labels
    assert "Narrative Threads" not in labels
    assert "full paragraph narration" not in merged_entries.lower()


def test_recalibration_creates_missing_npc_from_recent_narration(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_recal_npc"})
    state = runtime.session.state
    state.conversation_turns = [
        ConversationTurn(
            turn=1,
            player_input="I ask the guard for directions.",
            narrator_response='The guard nods. "My name is Eira."',
            system_messages=[],
        )
    ]
    state.npcs = {}

    result = runtime.recalibrate_campaign_state(state)

    assert result["ok"] is True
    assert any(npc.name == "Eira" for npc in state.npcs.values())


def test_recalibration_adds_missing_ability_when_learning_mode_enabled(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_recal_ability"})
    state = runtime.session.state
    state.settings.play_style.auto_update_character_sheet_from_actions = True
    state.character_sheets = [
        CharacterSheet.from_payload({"id": "sheet_main", "name": state.player.name, "sheet_type": "main_character"})
    ]
    state.structured_state.runtime.spellbook = []
    state.conversation_turns = [
        ConversationTurn(turn=1, player_input="I cast ember lance at the ice wall.", narrator_response="The wall cracks.", system_messages=[]),
    ]

    result = runtime.recalibrate_campaign_state(state)

    assert result["abilities_synced"] >= 1
    names = [entry["name"] for entry in state.structured_state.runtime.spellbook]
    assert any("ember" in name.lower() and "lance" in name.lower() for name in names)


def test_recalibration_backfills_structured_ooc_spells_from_message_history(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_recal_ooc_backfill"})
    state = runtime.session.state
    state.structured_state.runtime.spellbook = []
    runtime.session.message_history = [
        {"type": "ooc_player", "text": "Generate ranger spells for my spellbook."},
        {
            "type": "ooc_gm",
            "text": "- Storm Arrow: Wind-guided shot.\n- Root Snare: Entangling vines.",
            "structured_sync_payload": {
                "spellbook_entries": [
                    {"name": "Storm Arrow", "type": "spell", "description": "Wind-guided shot."},
                    {"name": "Root Snare", "type": "spell", "description": "Entangling vines."},
                ]
            },
        },
    ]

    result = runtime.recalibrate_campaign_state(state)

    names = [entry["name"] for entry in state.structured_state.runtime.spellbook]
    assert "Storm Arrow" in names
    assert "Root Snare" in names
    assert result["ooc_backfill_spellbook_entries"] >= 2


def test_recalibration_skips_unstructured_ooc_gm_text(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_recal_ooc_unstructured"})
    state = runtime.session.state
    state.structured_state.runtime.spellbook = []
    runtime.session.message_history = [
        {"type": "ooc_player", "text": "Generate ranger spells for my spellbook."},
        {"type": "ooc_gm", "text": "- Storm Arrow: Wind-guided shot.\n- Root Snare: Entangling vines."},
    ]

    result = runtime.recalibrate_campaign_state(state)
    assert result["ooc_backfill_spellbook_entries"] == 0
    assert state.structured_state.runtime.spellbook == []


def test_recalibration_cleanup_removes_invalid_spell_entries_and_keeps_valid(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_recal_cleanup"})
    state = runtime.session.state
    state.character_sheets = [CharacterSheet.from_payload({"id": "sheet_main", "name": "Aria", "sheet_type": "main_character"})]
    main_sheet = state.character_sheets[0]
    state.structured_state.runtime.spellbook = [
        {"name": "Bark Shield", "type": "spell"},
        {"name": "Do you have a preferred level for these new spells?", "type": "spell"},
    ]
    main_sheet.abilities = ["Bark Shield", "Now that we've got your data up to date, what would you like to do next?"]
    main_sheet.guaranteed_abilities = [
        CharacterSheetAbilityEntry.from_payload({"name": "Moonlit Tracker", "type": "ability"}),
        CharacterSheetAbilityEntry.from_payload({"name": "Please provide your spell preference", "type": "spell"}),
    ]

    result = runtime.recalibrate_campaign_state(state)
    names = [entry["name"] for entry in state.structured_state.runtime.spellbook]
    guaranteed = [entry.name for entry in main_sheet.guaranteed_abilities]
    assert "Bark Shield" in names
    assert "Do you have a preferred level for these new spells?" not in names
    assert "Bark Shield" in main_sheet.abilities
    assert all("what would you like" not in value.lower() for value in main_sheet.abilities)
    assert "Moonlit Tracker" in guaranteed
    assert all("please provide" not in value.lower() for value in guaranteed)
    assert result["cleaned_invalid_spell_entries"] >= 2


def test_recalibration_merges_duplicate_npcs_by_name(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_recal_dedupe"})
    state = runtime.session.state
    state.npcs = {
        "npc_eira": NPC(id="npc_eira", name="Eira", location_id=state.current_location_id),
        "npc_eira_2": NPC(id="npc_eira_2", name="Eira", location_id=state.current_location_id),
    }
    state.structured_state.runtime.scene_state = {
        "scene_actors": [{"actor_id": "a1", "linked_npc_id": "npc_eira_2", "display_name": "Eira"}],
        "npc_conditions": {"npc_eira_2": ["injured"]},
    }
    state.conversation_turns = [
        ConversationTurn(turn=1, player_input="I check on Eira.", narrator_response="Eira steadies her breath.", system_messages=[]),
    ]

    result = runtime.recalibrate_campaign_state(state)

    assert result["npc_merged"] >= 1
    assert len(state.npcs) == 1


def test_recalibration_extracts_world_effects_from_recent_narration(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_recal_world"})
    state = runtime.session.state
    state.structured_state.runtime.scene_state = {}
    state.conversation_turns = [
        ConversationTurn(
            turn=1,
            player_input="I unleash fire at the floor.",
            narrator_response="Frost races over the floor while fire spreads and a storm howls through the hall.",
            system_messages=[],
        ),
    ]

    result = runtime.recalibrate_campaign_state(state)
    scene_state = state.structured_state.runtime.scene_state

    assert result["world_updates"] >= 1
    assert any("frost" in entry.lower() for entry in scene_state.get("altered_environment", []))
    assert state.world_flags.get("env_storm_active") is True


def test_recalibration_does_not_overwrite_existing_personality_profile(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_recal_safe"})
    state = runtime.session.state
    npc = NPC(id="npc_known", name="Eira", location_id=state.current_location_id)
    npc.personality_profile = NPC.PersonalityProfile(archetype="Watch Captain", baseline_temperament="steady")
    state.npcs = {npc.id: npc}
    state.conversation_turns = [
        ConversationTurn(turn=1, player_input="I greet Eira.", narrator_response="Eira watches carefully.", system_messages=[]),
    ]

    runtime.recalibrate_campaign_state(state)

    assert state.npcs["npc_known"].personality_profile is not None
    assert state.npcs["npc_known"].personality_profile.archetype == "Watch Captain"


def test_npc_identity_registry_reuses_record_for_repeat_npc(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_npc_registry"})
    state = runtime.session.state
    state.npcs["npc_watch"] = NPC(id="npc_watch", name="Captain Vey", location_id=state.current_location_id)

    registry = runtime._sync_npc_identities()
    first = dict(registry.records["npc_watch"])
    registry_again = runtime._sync_npc_identities()
    second = registry_again.records["npc_watch"]

    assert second["npc_id"] == "npc_watch"
    assert second["first_seen_turn"] == first["first_seen_turn"]


def test_npc_portrait_generation_failure_is_non_blocking(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_npc_portrait_fail"})
    state = runtime.session.state
    npc = NPC(id="npc_companion", name="Seren", location_id=state.current_location_id, disposition=35, relationship_tier="friendly")
    state.npcs[npc.id] = npc
    registry = runtime._sync_npc_identities()

    monkeypatch.setattr(
        runtime,
        "generate_image",
        lambda payload: ImageGenerationResult(success=False, workflow_id="character_portrait", error="backend unavailable"),
    )
    runtime._generate_npc_portrait(npc_id=npc.id)

    record = registry.records[npc.id]
    assert record["portrait_status"] == "failed"
    assert record.get("portrait_path", "") == ""


def test_npc_portrait_generation_binds_to_npc_id(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_npc_portrait_bind"})
    state = runtime.session.state
    npc = NPC(id="npc_companion", name="Seren", location_id=state.current_location_id, disposition=35, relationship_tier="friendly")
    state.npcs[npc.id] = npc
    registry = runtime._sync_npc_identities()

    monkeypatch.setattr(
        runtime,
        "generate_image",
        lambda payload: ImageGenerationResult(success=True, workflow_id="character_portrait", result_path=str(runtime.generated_image_dir / "npc.png")),
    )
    monkeypatch.setattr(runtime, "public_image_path", lambda result_path: "/generated/npc.png")
    runtime._generate_npc_portrait(npc_id=npc.id)

    record = registry.records[npc.id]
    assert record["portrait_status"] == "ready"
    assert record["portrait_path"] == "/generated/npc.png"
    assert record["visual_locked"] is True


def test_handle_player_input_routes_npc_dialogue_cards_and_preserves_narrator(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_npc_message_routing"})
    state = runtime.session.state
    npc = NPC(id="npc_keeper", name="Keeper Thane", location_id=state.current_location_id)
    state.npcs[npc.id] = npc
    state.active_dialogue_npc_id = npc.id

    monkeypatch.setattr(
        runtime.engine,
        "run_turn",
        lambda *_args, **_kwargs: TurnResult(
            narrative="Rain gathers over the square.",
            system_messages=[],
            messages=[
                {"type": "npc", "text": "[calm/measured] Welcome back, traveler."},
                {"type": "narrator", "text": "Rain gathers over the square."},
            ],
        ),
    )

    payload = runtime.handle_player_input("talk npc_keeper")
    npc_message = payload["messages"][0]
    narrator_message = payload["messages"][1]

    assert npc_message["type"] == "npc"
    assert npc_message["speaker_npc_id"] == "npc_keeper"
    assert npc_message["speaker_name"] == "Keeper Thane"
    assert narrator_message["type"] == "narrator"


def test_narrator_only_turn_stays_narrator_only_without_resolved_speaker(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_npc_split_narrator_only"})
    runtime.session.state.active_dialogue_npc_id = None

    monkeypatch.setattr(
        runtime.engine,
        "run_turn",
        lambda *_args, **_kwargs: TurnResult(
            narrative='The market rustles as someone says, "Fresh bread!"',
            system_messages=[],
            messages=[{"type": "narrator", "text": 'The market rustles as someone says, "Fresh bread!"'}],
        ),
    )

    payload = runtime.handle_player_input("look around")
    assert [message["type"] for message in payload["messages"]] == ["narrator"]
    assert '"Fresh bread!"' in payload["messages"][0]["text"]


def test_narration_plus_resolved_npc_line_splits_to_narrator_and_npc_and_reuses_identity(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_npc_split_resolved"})
    state = runtime.session.state
    npc = NPC(id="npc_merchant", name="Vera", location_id=state.current_location_id)
    state.npcs[npc.id] = npc
    state.active_dialogue_npc_id = npc.id

    outputs = iter(
        [
            TurnResult(
                narrative='The awning snaps in the wind as the merchant says, "Care to trade?"',
                system_messages=[],
                messages=[{"type": "narrator", "text": 'The awning snaps in the wind as the merchant says, "Care to trade?"'}],
            ),
            TurnResult(
                narrative='"I can lower the price a little."',
                system_messages=[],
                messages=[{"type": "narrator", "text": '"I can lower the price a little."'}],
            ),
        ]
    )
    monkeypatch.setattr(runtime.engine, "run_turn", lambda *_args, **_kwargs: next(outputs))

    first = runtime.handle_player_input("I ask the merchant about prices.")
    second = runtime.handle_player_input("I wait.")
    first_types = [message["type"] for message in first["messages"]]
    assert first_types == ["narrator", "npc"]
    assert first["messages"][1]["speaker_name"] == "Vera"
    assert first["messages"][1]["speaker_npc_id"] == "npc_merchant"
    assert second["messages"][0]["type"] == "npc"
    assert second["messages"][0]["speaker_npc_id"] == "npc_merchant"
    assert len(runtime.session.state.structured_state.runtime.npc_identity_registry) == 1


def test_mixed_narration_quote_and_trailing_narration_splits_into_three_messages(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_npc_split_mixed"})
    state = runtime.session.state
    npc = NPC(id="npc_gorvoth", name="Gorvoth", location_id=state.current_location_id)
    state.npcs[npc.id] = npc
    state.active_dialogue_npc_id = npc.id

    monkeypatch.setattr(
        runtime.engine,
        "run_turn",
        lambda *_args, **_kwargs: TurnResult(
            narrative=(
                'As you approach Gorvoth, he studies you carefully. '
                '"You seek my history?" he asks. '
                "His posture remains measured and guarded."
            ),
            system_messages=[],
            messages=[
                {
                    "type": "narrator",
                    "text": (
                        'As you approach Gorvoth, he studies you carefully. '
                        '"You seek my history?" he asks. '
                        "His posture remains measured and guarded."
                    ),
                }
            ],
        ),
    )

    payload = runtime.handle_player_input("I ask Gorvoth what happened here.")
    assert [message["type"] for message in payload["messages"]] == ["narrator", "npc", "narrator"]
    assert payload["messages"][1]["speaker_name"] == "Gorvoth"
    assert "You seek my history?" in payload["messages"][1]["text"]


def test_npc_message_attaches_portrait_metadata_when_available(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_npc_split_portrait"})
    state = runtime.session.state
    npc = NPC(id="npc_artist", name="Iria", location_id=state.current_location_id)
    state.npcs[npc.id] = npc
    state.active_dialogue_npc_id = npc.id
    registry = runtime._sync_npc_identities()
    registry.bind_portrait_success(npc.id, portrait_path="/generated/iria.png", prompt="portrait")

    monkeypatch.setattr(
        runtime.engine,
        "run_turn",
        lambda *_args, **_kwargs: TurnResult(
            narrative='"Welcome to my gallery."',
            system_messages=[],
            messages=[{"type": "narrator", "text": '"Welcome to my gallery."'}],
        ),
    )
    payload = runtime.handle_player_input("I greet Iria.")
    npc_message = payload["messages"][0]
    assert npc_message["type"] == "npc"
    assert npc_message["speaker_name"] == "Iria"
    assert npc_message["portrait_url"] == "/generated/iria.png"


def test_npc_message_without_portrait_still_emits_card_fields(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_npc_split_no_portrait"})
    state = runtime.session.state
    npc = NPC(id="npc_scout", name="Deren", location_id=state.current_location_id)
    state.npcs[npc.id] = npc
    state.active_dialogue_npc_id = npc.id

    monkeypatch.setattr(
        runtime.engine,
        "run_turn",
        lambda *_args, **_kwargs: TurnResult(
            narrative='"The road is clear ahead."',
            system_messages=[],
            messages=[{"type": "narrator", "text": '"The road is clear ahead."'}],
        ),
    )
    payload = runtime.handle_player_input("Any scouts ahead?")
    npc_message = payload["messages"][0]
    assert npc_message["type"] == "npc"
    assert npc_message["speaker_name"] == "Deren"
    assert npc_message["portrait_url"] == ""


def test_unresolved_quoted_speech_stays_on_narrator_path(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_npc_split_unresolved"})
    runtime.session.state.active_dialogue_npc_id = None

    monkeypatch.setattr(
        runtime.engine,
        "run_turn",
        lambda *_args, **_kwargs: TurnResult(
            narrative='A distant voice whispers, "Leave now."',
            system_messages=[],
            messages=[{"type": "narrator", "text": 'A distant voice whispers, "Leave now."'}],
        ),
    )
    payload = runtime.handle_player_input("I listen.")
    assert len(payload["messages"]) == 1
    assert payload["messages"][0]["type"] == "narrator"
    assert "Leave now" in payload["messages"][0]["text"]


def test_single_quoted_npc_speech_splits_when_speaker_resolved(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_npc_split_single_quotes"})
    state = runtime.session.state
    npc = NPC(id="npc_archivist", name="Archivist Nera", location_id=state.current_location_id)
    state.npcs[npc.id] = npc
    state.active_dialogue_npc_id = npc.id

    monkeypatch.setattr(
        runtime.engine,
        "run_turn",
        lambda *_args, **_kwargs: TurnResult(
            narrative="Nera steadies the scroll. 'The vault remembers every oath,' she says.",
            system_messages=[],
            messages=[{"type": "narrator", "text": "Nera steadies the scroll. 'The vault remembers every oath,' she says."}],
        ),
    )
    payload = runtime.handle_player_input("I ask Nera about the vault.")
    assert [message["type"] for message in payload["messages"]] == ["narrator", "npc", "narrator"]
    assert payload["messages"][1]["speaker_name"] == "Archivist Nera"
    assert payload["messages"][1]["text"] == "The vault remembers every oath,"


def test_explicit_speaker_npc_id_metadata_is_used_for_narrator_split(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_npc_split_explicit_speaker"})
    state = runtime.session.state
    state.npcs["npc_guard"] = NPC(id="npc_guard", name="Captain Rovan", location_id=state.current_location_id)
    state.npcs["npc_merchant"] = NPC(id="npc_merchant", name="Vera", location_id=state.current_location_id)
    state.active_dialogue_npc_id = "npc_merchant"

    monkeypatch.setattr(
        runtime.engine,
        "run_turn",
        lambda *_args, **_kwargs: TurnResult(
            narrative='The captain folds his arms and says, "No one enters after dusk."',
            system_messages=[],
            messages=[
                {
                    "type": "narrator",
                    "text": 'The captain folds his arms and says, "No one enters after dusk."',
                    "speaker_npc_id": "npc_guard",
                }
            ],
        ),
    )
    payload = runtime.handle_player_input("I ask who can enter.")
    assert payload["messages"][1]["type"] == "npc"
    assert payload["messages"][1]["speaker_npc_id"] == "npc_guard"
    assert payload["messages"][1]["speaker_name"] == "Captain Rovan"


def test_multiple_explicit_npc_speakers_preserve_dialogue_order(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_npc_split_multiple_speakers"})
    state = runtime.session.state
    state.npcs["npc_guard"] = NPC(id="npc_guard", name="Captain Rovan", location_id=state.current_location_id)
    state.npcs["npc_mage"] = NPC(id="npc_mage", name="Iria", location_id=state.current_location_id)

    monkeypatch.setattr(
        runtime.engine,
        "run_turn",
        lambda *_args, **_kwargs: TurnResult(
            narrative='The guard steps forward and says, "Hold there." The mage raises a hand and says, "Let them pass."',
            system_messages=[],
            messages=[
                {"type": "narrator", "text": 'The guard steps forward and says, "Hold there."', "speaker_npc_id": "npc_guard"},
                {"type": "narrator", "text": 'The mage raises a hand and says, "Let them pass."', "speaker_npc_id": "npc_mage"},
            ],
        ),
    )
    payload = runtime.handle_player_input("I approach the gate.")
    dialogue_lines = [m for m in payload["messages"] if m["type"] == "npc"]
    assert [m["speaker_name"] for m in dialogue_lines] == ["Captain Rovan", "Iria"]
    assert [m["text"] for m in dialogue_lines] == ["Hold there.", "Let them pass."]


def test_npc_identity_registry_persists_through_save_reload(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_npc_persist"})
    state = runtime.session.state
    state.npcs["npc_persist"] = NPC(id="npc_persist", name="Iria", location_id=state.current_location_id, disposition=30, relationship_tier="friendly")
    registry = runtime._sync_npc_identities()
    registry.bind_portrait_success("npc_persist", portrait_path="/generated/iria.png", prompt="portrait prompt")
    runtime.save_active_campaign("slot_npc_persist")

    reloaded = _runtime(tmp_path, monkeypatch)
    reloaded.switch_campaign("slot_npc_persist")
    restored = reloaded.session.state.structured_state.runtime.npc_identity_registry
    assert restored["npc_persist"]["portrait_path"] == "/generated/iria.png"
    assert restored["npc_persist"]["display_name"] == "Iria"


def test_history_replay_prefers_structured_turn_messages_for_npc_cards(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_npc_replay_structured"})
    state = runtime.session.state
    state.conversation_turns = [
        ConversationTurn(
            turn=1,
            player_input="I greet Vera.",
            system_messages=[],
            narrator_response='The trader smiles. "Welcome back."',
            display_messages=[
                {"type": "narrator", "text": "The trader smiles."},
                {"type": "npc", "text": "Welcome back.", "speaker_npc_id": "npc_merchant", "speaker_name": "Vera"},
            ],
        )
    ]
    runtime.history_store = {}
    replayed = runtime._history_for_slot(runtime.session.active_slot)
    assert [message["type"] for message in replayed] == ["player", "narrator", "npc"]
    assert replayed[2]["speaker_name"] == "Vera"


def test_display_messages_survive_save_load_and_replay(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_npc_replay_save_load"})
    runtime.session.state.conversation_turns = [
        ConversationTurn(
            turn=1,
            player_input="I listen.",
            system_messages=[],
            narrator_response='The old scout says, "Keep low."',
            display_messages=[
                {"type": "narrator", "text": "The old scout studies the ridge."},
                {"type": "npc", "text": "Keep low.", "speaker_npc_id": "npc_scout", "speaker_name": "Deren"},
                {"type": "narrator", "text": "He points toward the pass."},
            ],
        )
    ]
    runtime.save_active_campaign("slot_npc_replay_save_load")

    reloaded = _runtime(tmp_path, monkeypatch)
    reloaded.switch_campaign("slot_npc_replay_save_load")
    replayed = reloaded._history_for_slot("slot_npc_replay_save_load")
    assert [message["type"] for message in replayed] == ["player", "narrator", "npc", "narrator"]
    assert replayed[2]["speaker_name"] == "Deren"
    assert replayed[2]["text"] == "Keep low."


def test_play_view_separates_scene_from_dialogue(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_play_view_scene"})
    state = runtime.session.state
    npc = NPC(id="npc_scene", name="Warden Ilra", location_id=state.current_location_id)
    state.npcs[npc.id] = npc
    state.active_dialogue_npc_id = npc.id

    monkeypatch.setattr(
        runtime.engine,
        "run_turn",
        lambda *_args, **_kwargs: TurnResult(
            narrative='Fog gathers around the gate as Ilra says, "Stay close."',
            system_messages=[],
            messages=[{"type": "narrator", "text": 'Fog gathers around the gate as Ilra says, "Stay close."'}],
        ),
    )
    runtime.handle_player_input("I approach the gate.")
    view = runtime.get_play_view()

    assert "Fog gathers" in view["scene_state"]["narration"]
    assert any(entry["type"] == "npc" and entry.get("speaker_name") == "Warden Ilra" for entry in view["dialogue_entries"])


def test_play_view_visible_npc_includes_portrait_or_placeholder(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_play_view_npc"})
    state = runtime.session.state
    npc = NPC(id="npc_portrait", name="Seren Vale", location_id=state.current_location_id)
    state.npcs[npc.id] = npc
    registry = runtime._sync_npc_identities()

    without_portrait = runtime.get_play_view()
    npc_entry = next(item for item in without_portrait["visible_npcs"] if item["npc_id"] == npc.id)
    assert npc_entry["display_name"] == "Seren Vale"
    assert npc_entry["portrait_url"] == ""
    assert npc_entry["avatar_fallback"] == "SV"

    registry.bind_portrait_success(npc.id, portrait_path="/generated/seren.png", prompt="portrait")
    with_portrait = runtime.get_play_view()
    npc_entry_with_portrait = next(item for item in with_portrait["visible_npcs"] if item["npc_id"] == npc.id)
    assert npc_entry_with_portrait["portrait_url"] == "/generated/seren.png"


def test_play_view_remains_valid_with_narration_only_and_survives_reload(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_play_view_reload"})

    monkeypatch.setattr(
        runtime.engine,
        "run_turn",
        lambda *_args, **_kwargs: TurnResult(
            narrative="The chapel stands quiet under moonlight.",
            system_messages=[],
            messages=[{"type": "narrator", "text": "The chapel stands quiet under moonlight."}],
        ),
    )
    runtime.handle_player_input("look")
    runtime.save_active_campaign("slot_play_view_reload")

    reloaded = _runtime(tmp_path, monkeypatch)
    reloaded.switch_campaign("slot_play_view_reload")
    view = reloaded.get_play_view()

    assert view["visible_npcs"] == []
    assert any(entry["type"] == "narrator" for entry in view["dialogue_entries"])
    assert "chapel" in view["scene_state"]["narration"].lower()
