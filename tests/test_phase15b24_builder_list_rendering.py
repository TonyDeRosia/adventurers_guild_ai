from types import SimpleNamespace
from smart_mud.builder import BuilderService, BuilderWorkspace


def actor():
    return SimpleNamespace(id="b", account_id="a", session_id="s", role="builder", account_role="builder", world_id="shattered_realms", room_id="room", current_area_id="starter_guildlands", current_zone_id="guildhall_crossing")


def test_builder_brief_list_has_single_view_and_missing_vnum_marker(tmp_path):
    ws=BuilderWorkspace(worlds_dir=tmp_path/"worlds"); svc=BuilderService(ws); d=ws.load("shattered_realms")
    d.setdefault("entities", {})["bear"]={"id":"bear","name":"Ashback Bear","level":2,"area_id":"starter_guildlands","zone_id":"guildhall_crossing"}
    ws.save_drafts("shattered_realms", d)
    out=svc.list_content(actor(), "mob", ["all"])
    assert out.ok
    assert "----" in out.message
    assert "Legacy pipe view" not in out.message
    assert "Mob List" in out.message
