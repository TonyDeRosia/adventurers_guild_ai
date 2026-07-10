import shutil
from pathlib import Path
from types import SimpleNamespace

from engine.mud_runtime import MudRuntime
from engine.mud_commands import MudCommandEngine
from smart_mud.builder import BuilderWorkspace


REPO_ROOT = Path(__file__).resolve().parents[1]


def actor(role="builder"):
    return SimpleNamespace(role=role, account_role=role, world_id="shattered_realms", id="c1", account_id="a1", room_id="guildhall_crossing_square", edit_room_id="guildhall_crossing_square", name="Tester")


def workspace(isolated_builder_world):
    return isolated_builder_world.workspace, isolated_builder_world.world_root


def test_builder_workspace_creates_import_template_example_folders(isolated_builder_world):
    bw, root = workspace(isolated_builder_world)
    shutil.rmtree(root / "shattered_realms/builder")
    bw.ensure("shattered_realms")
    for dirname in ("imports", "templates", "examples"):
        assert (root / "shattered_realms/builder" / dirname).is_dir()


def test_template_files_exist_and_commands_copy_without_overwrite(isolated_builder_world):
    bw, root = workspace(isolated_builder_world)
    bw.ensure("shattered_realms")
    required = {"empty_bundle_template.json", "area_zone_room_template.json", "bad_duplicate_vnum_test.json", "future_keys_test.json", "feature_library_template.json"}
    assert required <= {p.name for p in (root / "shattered_realms/builder/templates").glob("*.json")}
    engine = MudCommandEngine(); engine.builder = bw
    listed = engine.handle_command(actor(), "builder template list")
    assert listed.ok and "area_zone_room_template.json" in listed.narrative
    copied = engine.handle_command(actor(), "builder template copy area_zone_room_template.json my_area.json")
    assert copied.ok
    assert (root / "shattered_realms/builder/imports/my_area.json").exists()
    refused = engine.handle_command(actor(), "builder template copy area_zone_room_template.json my_area.json")
    assert not refused.ok and "--force" in refused.narrative
    forced = engine.handle_command(actor(), "builder template copy area_zone_room_template.json my_area.json --force")
    assert forced.ok


def test_import_list_guidance_and_template_validation_results(isolated_builder_world):
    bw, root = workspace(isolated_builder_world)
    bw.ensure("shattered_realms")
    msg = bw.import_list(actor()).message
    assert "No import files found." in msg
    assert "builder template copy area_zone_room_template.json my_area.json" in msg
    assert "worlds/shattered_realms/builder/imports/" in msg
    bw.template_copy(actor(), "area_zone_room_template.json", "area.json")
    assert bw.import_validate(actor(), "area.json").ok
    bw.template_copy(actor(), "bad_duplicate_vnum_test.json", "bad.json")
    bad = bw.import_validate(actor(), "bad.json")
    assert not bad.ok and "duplicate vnum" in bad.message
    bw.template_copy(actor(), "future_keys_test.json", "future.json")
    future = bw.import_validate(actor(), "future.json")
    assert future.ok and "Future top-level collection locations" in future.message


def test_builder_starter_room_dedupes_draft_features_against_live_scenery(isolated_builder_world):
    rt = isolated_builder_world.runtime
    acct = rt.create_account("Builder", role="builder")
    rt.load_world("shattered_realms")
    cid = rt.create_character(world_id="shattered_realms", name="Builder", account_id=acct["account_id"])["character_id"]
    rt.enter_world(cid)
    rt.handle_input(cid, "builder on")
    output = rt.handle_input(cid, "look")["output"]
    assert output.count("Old Gate") == 1
    assert output.count("Fountain") == 1


def test_portable_runtime_items_are_not_hidden_by_feature_dedupe(isolated_builder_world):
    rt = isolated_builder_world.runtime
    acct = rt.create_account("Builder", role="builder")
    rt.load_world("shattered_realms")
    rt.item_templates["rusty_sword"] = {**dict(rt.item_templates["rusty_sword"]), "name": "Fountain", "portable": True}
    cid = rt.create_character(world_id="shattered_realms", name="Builder", account_id=acct["account_id"])["character_id"]
    rt.enter_world(cid)
    rt.spawn_item("rusty_sword", owner_type="room", room_id="guildhall_crossing_square")
    rt.handle_input(cid, "builder on")
    output = rt.handle_input(cid, "look")["output"]
    assert output.count("Fountain") == 2
