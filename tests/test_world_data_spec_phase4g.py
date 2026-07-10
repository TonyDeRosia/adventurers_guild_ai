import json
import shutil
from pathlib import Path
from types import SimpleNamespace

from smart_mud.builder import BuilderWorkspace


def actor(role="builder"):
    return SimpleNamespace(role=role, account_role=role, world_id="shattered_realms", id="c1", account_id="a1", room_id="guildhall_crossing_square", edit_room_id="guildhall_crossing_square")


def workspace(tmp_path):
    root = tmp_path / "worlds"
    shutil.copytree(Path("worlds/shattered_realms"), root / "shattered_realms", ignore=shutil.ignore_patterns("builder"))
    return BuilderWorkspace(worlds_dir=root), root


def spec_text():
    return Path("docs/WORLD_DATA_SPECIFICATION.md").read_text(encoding="utf-8")


def test_world_data_spec_phase4g_exists_and_documents_bundle_keys():
    text = spec_text()
    assert "World Data Specification v1.0" in text
    for key in ['"areas"', '"zones"', '"rooms"', '"features"', '"items"', '"entities"', '"spawns"']:
        assert key in text


def test_world_data_spec_documents_optional_location_hierarchy_without_room_duplication():
    text = spec_text()
    assert "locations.json" in text
    assert "optional v1 future-supported data" in text
    assert "room -> zone -> area -> location hierarchy" in text
    assert "Rooms must not duplicate hardcoded `continent`, `kingdom`, or `region` fields" in text
    assert "planet" in text and "star_system" in text and "custom" in text


def test_world_data_spec_documents_required_area_zone_room_fields():
    text = spec_text()
    for field in ["room_vnum_start", "object_vnum_end", "mob_vnum_start", "spawn_vnum_end", "zone_ids", "created_at", "updated_at"]:
        assert f"`{field}`" in text
    for field in ["area_id", "vnum_start", "vnum_end", "room_ids"]:
        assert f"`{field}`" in text
    for field in ["zone_id", "vnum", "exits", "features", "plugin_data"]:
        assert f"`{field}`" in text


def test_world_data_spec_documents_feature_plugin_inheritance_and_tba_parity():
    text = spec_text()
    for phrase in [
        "Feature Library Model",
        "Current rooms may embed local features under `room.features`",
        "`plugin_data` is a JSON object preserved",
        "Resolution order is",
        "tbaMUD Design Parity",
        "zone modularity",
        "JSON instead of `.wld/.zon/.mob/.obj/.shp/.trg`",
    ]:
        assert phrase in text


def test_world_data_spec_roadmap_and_related_docs_reference_phase4g():
    for doc in [
        "docs/SMART_MUD_MASTER_ROADMAP.md",
        "docs/SMART_MUD_ARCHITECTURE.md",
        "docs/WORLD_PACKAGE_SPEC.md",
        "docs/AREA_ZONE_VNUM_SYSTEM.md",
        "docs/BUILDER_IMPORT_PIPELINE.md",
        "docs/BUILDER_MODE.md",
    ]:
        text = Path(doc).read_text(encoding="utf-8")
        assert "Phase 4G" in text
        assert "WORLD_DATA_SPECIFICATION.md" in text
    parity = Path("docs/TBAMUD_WORLD_DESIGN_PARITY.md").read_text(encoding="utf-8")
    assert "Builder drafts replace direct live file editing" in parity


def test_import_validation_preserves_plugin_data_and_local_features(tmp_path):
    bw, root = workspace(tmp_path)
    bw.ensure("shattered_realms")
    bundle = {
        "areas": {"plugin_area": {"id":"plugin_area", "name":"Plugin Area", "description":"Area", "world_id":"shattered_realms", "vnum_start":3000, "vnum_end":3099, "room_vnum_start":3000, "room_vnum_end":3099, "plugin_data":{"world_context":{"biome":"test"}}}},
        "zones": {"plugin_zone": {"id":"plugin_zone", "name":"Plugin Zone", "description":"Zone", "world_id":"shattered_realms", "area_id":"plugin_area", "vnum_start":3000, "vnum_end":3099, "plugin_data":{"danger_level":"low"}}},
        "rooms": {"plugin_room": {"id":"plugin_room", "name":"Plugin Room", "description":"Room", "world_id":"shattered_realms", "area_id":"plugin_area", "zone_id":"plugin_zone", "vnum":3000, "exits":{}, "features":{"mural":{"name":"Mural", "plugin_data":{"lore":"kept"}}}, "flags":[], "tags":[], "plugin_data":{"ambient_override":{"music":"quiet"}}}},
        "features": {"shared_feature": {"id":"shared_feature", "name":"Shared Feature", "plugin_data":{"kept": True}}},
        "items": {}, "entities": {}, "spawns": {},
    }
    (root / "shattered_realms/builder/imports/plugin_bundle.json").write_text(json.dumps(bundle), encoding="utf-8")
    res = bw.import_validate(actor(), "plugin_bundle.json")
    assert res.ok, res.message
    assert bw.import_apply(actor(), "plugin_bundle.json").ok
    drafts = bw.load("shattered_realms")
    assert drafts["areas"]["plugin_area"]["plugin_data"]["world_context"]["biome"] == "test"
    assert drafts["zones"]["plugin_zone"]["plugin_data"]["danger_level"] == "low"
    assert drafts["rooms"]["plugin_room"]["plugin_data"]["ambient_override"]["music"] == "quiet"
    assert drafts["rooms"]["plugin_room"]["features"]["mural"]["plugin_data"]["lore"] == "kept"
    assert drafts["features"]["shared_feature"]["plugin_data"]["kept"] is True


def test_import_validation_warns_for_unknown_future_top_level_keys(tmp_path):
    bw, root = workspace(tmp_path)
    bw.ensure("shattered_realms")
    bundle = {"areas": {}, "zones": {}, "rooms": {}, "features": {}, "items": {}, "entities": {}, "spawns": {}, "locations": {"future_city": {}}, "quest_templates": {}}
    (root / "shattered_realms/builder/imports/future_bundle.json").write_text(json.dumps(bundle), encoding="utf-8")
    res = bw.import_validate(actor(), "future_bundle.json")
    assert res.ok
    assert "Future top-level collection locations is not applied by this version." in res.message
    assert "Future top-level collection quest_templates is not applied by this version." in res.message
    assert bw.import_apply(actor(), "future_bundle.json").ok
    drafts = bw.load("shattered_realms")
    assert "locations" not in drafts
    assert "quest_templates" not in drafts
