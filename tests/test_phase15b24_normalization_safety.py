from types import SimpleNamespace

from smart_mud.builder import BuilderService, BuilderWorkspace


def actor(role="owner"):
    return SimpleNamespace(id="builder", name="Builder", account_id="acct", session_id="sess", role=role, account_role=role, world_id="shattered_realms", room_id="room")


def seed(ws):
    drafts=ws.load("shattered_realms")
    drafts.setdefault("areas", {})["starter_guildlands"]={"id":"starter_guildlands","name":"Starter Guildlands"}
    drafts.setdefault("zones", {})["guildhall_crossing"]={"id":"guildhall_crossing","name":"Guildhall Crossing","area_id":"starter_guildlands","vnum_start":1000,"vnum_end":1029}
    drafts.setdefault("rooms", {})["room"]={"id":"room","name":"Room","vnum":1000,"area_id":"starter_guildlands","zone_id":"guildhall_crossing"}
    ws.save_drafts("shattered_realms", drafts)
    return drafts


def test_manual_review_blocks_apply_and_weak_name_hint_never_applies(tmp_path):
    ws=BuilderWorkspace(worlds_dir=tmp_path/"worlds"); svc=BuilderService(ws); drafts=seed(ws)
    drafts.setdefault("entities", {})["guildhall_rat"]={"id":"guildhall_rat","name":"Guildhall Rat"}
    ws.save_drafts("shattered_realms", drafts)
    plan=svc.normalization_plan(actor())
    rec=next(p for p in plan if p["id"]=="guildhall_rat")
    assert rec["confidence"] == "MANUAL_REVIEW"
    out=svc.normalize_command(actor(), ["apply"])
    assert not out.ok
    assert "Normalization cannot be applied because 1 records require manual review and 0 records are blocked." in out.message
    assert "builder normalize plan verbose" in out.message


def test_confirmed_reference_requires_confirmation_then_creates_versioned_snapshot(tmp_path):
    ws=BuilderWorkspace(worlds_dir=tmp_path/"worlds"); svc=BuilderService(ws); drafts=seed(ws)
    drafts.setdefault("entities", {})["training_rat"]={"id":"training_rat","name":"Training Rat","default_room_id":"room"}
    ws.save_drafts("shattered_realms", drafts)
    a=actor("admin")
    first=svc.normalize_command(a, ["apply"])
    assert not first.ok and "CONFIRM NORMALIZE 1" in first.message
    wrong=svc.normalize_command(a, ["confirm", "2"])
    assert not wrong.ok and "count does not match" in wrong.message
    ok=svc.normalize_command(a, ["confirm", "1"])
    assert ok.ok
    applied=ws.load("shattered_realms")["entities"]["training_rat"]
    assert applied["vnum"] == 1500
    snaps=svc.normalize_command(a, ["snapshots"])
    assert "normalize_" in snaps.message


def test_builder_denied_but_admin_and_owner_can_prepare_apply(tmp_path):
    ws=BuilderWorkspace(worlds_dir=tmp_path/"worlds"); svc=BuilderService(ws); drafts=seed(ws)
    drafts.setdefault("entities", {})["training_rat"]={"id":"training_rat","name":"Training Rat","default_room_id":"room"}
    ws.save_drafts("shattered_realms", drafts)
    assert svc.normalize_command(actor("builder"), ["audit"]).ok
    assert not svc.normalize_command(actor("builder"), ["apply"]).ok
    assert "You do not have permission" in svc.normalize_command(actor("builder"), ["apply"]).message
    assert "CONFIRM NORMALIZE" in svc.normalize_command(actor("admin"), ["apply"]).message
    assert "CONFIRM NORMALIZE" in svc.normalize_command(actor("owner"), ["apply"]).message


def test_shared_spawn_reset_namespace_prevents_collision(tmp_path):
    ws=BuilderWorkspace(worlds_dir=tmp_path/"worlds"); svc=BuilderService(ws); drafts=seed(ws)
    drafts.setdefault("spawns", {})["spawn_a"]={"id":"spawn_a","name":"Spawn A","room_id":"room"}
    drafts.setdefault("resets", {})["reset_a"]={"id":"reset_a","name":"Reset A","room_id":"room"}
    ws.save_drafts("shattered_realms", drafts)
    plan=svc.normalization_plan(actor())
    vals={p["id"]:p["new_vnum"] for p in plan}
    assert vals["spawn_a"] == 1700
    assert vals["reset_a"] == 1701


def test_verify_catches_out_of_range_and_broken_reference(tmp_path):
    ws=BuilderWorkspace(worlds_dir=tmp_path/"worlds"); svc=BuilderService(ws); drafts=seed(ws)
    drafts.setdefault("entities", {})["bad"]={"id":"bad","name":"Bad","vnum":9999,"area_id":"starter_guildlands","zone_id":"guildhall_crossing"}
    drafts.setdefault("spawns", {})["broken_spawn"]={"id":"broken_spawn","vnum":1700,"area_id":"starter_guildlands","zone_id":"guildhall_crossing","room_id":"missing_room","mobile_id":"bad"}
    ws.save_drafts("shattered_realms", drafts)
    out=svc.normalize_command(actor(), ["verify"])
    assert not out.ok
    assert "OUT_OF_RANGE_VNUM" in out.message
    assert "BROKEN_REFERENCE" in out.message
