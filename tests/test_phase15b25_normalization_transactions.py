from types import SimpleNamespace
from smart_mud.builder import BuilderService, BuilderWorkspace


def actor():
    return SimpleNamespace(id="builder", name="Builder", account_id="acct", session_id="sess", role="admin", account_role="admin", world_id="shattered_realms", room_id="room")


def seed(ws):
    d = ws.load("shattered_realms")
    d["areas"]["starter_guildlands"] = {"id":"starter_guildlands","name":"Starter Guildlands"}
    d["zones"]["guildhall_crossing"] = {"id":"guildhall_crossing","name":"Guildhall Crossing","area_id":"starter_guildlands","vnum_start":1000,"vnum_end":1029}
    d["rooms"]["room"] = {"id":"room","name":"Room","vnum":1000,"area_id":"starter_guildlands","zone_id":"guildhall_crossing"}
    d["entities"]["training_rat"] = {"id":"training_rat","name":"Training Rat","default_room_id":"room"}
    ws.save_drafts("shattered_realms", d)


def test_snapshot_root_is_not_nested_builder(tmp_path):
    svc = BuilderService(BuilderWorkspace(worlds_dir=tmp_path / "worlds"))
    root = svc._normalization_snapshot_root("shattered_realms")
    assert root.parent.name == "builder"
    assert root.name == "normalization_snapshots"
    assert "builder/builder/normalization_snapshots" not in root.as_posix()


def test_confirm_apply_creates_transaction_and_exact_restore(tmp_path):
    ws = BuilderWorkspace(worlds_dir=tmp_path / "worlds"); svc = BuilderService(ws); a = actor(); seed(ws)
    before = svc._draft_file_hashes("shattered_realms")
    ready = svc.normalize_command(a, ["apply"])
    assert not ready.ok and "CONFIRM NORMALIZE 1" in ready.message
    applied = svc.normalize_command(a, ["confirm", "1"])
    assert applied.ok, applied.message
    assert "transaction_id" in (applied.data or {})
    tx = svc.normalize_command(a, ["transactions"])
    assert (applied.data or {})["transaction_id"] in tx.message
    restored = svc._restore_normalization_snapshot_internal("shattered_realms", (applied.data or {})["snapshot_id"], reason="test", actor=a)
    assert restored.ok, restored.errors
    after = svc._draft_file_hashes("shattered_realms")
    for name, h in before.items():
        assert after.get(name) == h


def test_plan_populates_reference_evidence(tmp_path):
    ws = BuilderWorkspace(worlds_dir=tmp_path / "worlds"); svc = BuilderService(ws); a = actor(); seed(ws)
    plan = svc.normalization_plan(a)
    row = next(p for p in plan if p["id"] == "training_rat")
    assert row["outgoing_references"]
    assert any(r["target_collection"] == "rooms" for r in row["outgoing_references"])


def test_builder_list_semantic_markup_and_html_ansi_render(tmp_path):
    from engine.mud_displays import semantic_html, render_display_ansi
    ws = BuilderWorkspace(worlds_dir=tmp_path / "worlds"); svc = BuilderService(ws); a = actor(); seed(ws)
    out = svc.list_content(a, "mob", ["all"])
    assert out.ok
    assert "{builder_title}" in out.message
    assert "{builder_vnum}" in out.message
    html = semantic_html(out.message)
    assert 'role="builder_title"' in html
    assert 'role="builder_vnum"' in html
    ansi = render_display_ansi(type("Doc", (), {"title":"", "subtitle":"", "paragraphs":[], "lines":[out.message], "sections":[], "footer":"", "semantic_role":"builder_row", "title_role":"builder_title"})())
    assert "\x1b[" in ansi
