from types import SimpleNamespace

from smart_mud.builder import BuilderService, BuilderWorkspace
from engine.mud_commands import MudCommandEngine


def actor(role="owner"):
    return SimpleNamespace(
        id="builder", name="Builder", account_id="acct", session_id="sess",
        role=role, account_role=role, world_id="shattered_realms", room_id="start",
        builder_zone_ids=["guildhall_crossing"], current_area_id="starter_guildlands",
        current_zone_id="guildhall_crossing",
    )


def test_normalization_plan_is_deterministic_and_audit_reports_real_counts(tmp_path):
    ws = BuilderWorkspace(worlds_dir=tmp_path / "worlds")
    svc = BuilderService(ws)
    a = actor()
    drafts = ws.load("shattered_realms")
    drafts.setdefault("areas", {})["starter_guildlands"] = {"id": "starter_guildlands", "name": "Starter Guildlands", "vnum_start": 1000, "vnum_end": 1999, "room_vnum_start": 1000, "room_vnum_end": 1299}
    drafts.setdefault("zones", {})["guildhall_crossing"] = {"id": "guildhall_crossing", "name": "Guildhall Crossing", "area_id": "starter_guildlands", "vnum_start": 1000, "vnum_end": 1029}
    drafts.setdefault("rooms", {})["guildhall_crossing_square"] = {"id": "guildhall_crossing_square", "name": "Crossing", "vnum": 1000, "area_id": "starter_guildlands", "zone_id": "guildhall_crossing"}
    drafts.setdefault("entities", {})["training_rat"] = {"id": "training_rat", "name": "Training Rat", "default_room_id": "guildhall_crossing_square"}
    drafts.setdefault("items", {})["practice_sword"] = {"id": "practice_sword", "name": "Practice Sword"}
    ws.save_drafts("shattered_realms", drafts)

    first = svc.normalization_plan(a)
    second = svc.normalization_plan(a)
    assert first == second
    assert any(p["id"] == "training_rat" and p["new_vnum"] == 1500 and p["new_zone"] == "guildhall_crossing" for p in first)
    assert "Missing VNUMs: 2" in svc.normalize_command(a, ["audit"]).message
    assert "training_rat" in svc.normalize_command(a, ["plan"]).message


def test_normalization_apply_verify_and_rollback(tmp_path):
    ws = BuilderWorkspace(worlds_dir=tmp_path / "worlds")
    svc = BuilderService(ws)
    a = actor()
    drafts = ws.load("shattered_realms")
    drafts.setdefault("areas", {})["starter_guildlands"] = {"id": "starter_guildlands", "name": "Starter Guildlands", "vnum_start": 1000, "vnum_end": 1999, "room_vnum_start": 1000, "room_vnum_end": 1299}
    drafts.setdefault("zones", {})["guildhall_crossing"] = {"id": "guildhall_crossing", "name": "Guildhall Crossing", "area_id": "starter_guildlands", "vnum_start": 1000, "vnum_end": 1029}
    drafts.setdefault("rooms", {})["guildhall_crossing_square"] = {"id": "guildhall_crossing_square", "name": "Crossing", "vnum": 1000, "area_id": "starter_guildlands", "zone_id": "guildhall_crossing"}
    drafts.setdefault("entities", {})["training_rat"] = {"id": "training_rat", "name": "Training Rat", "default_room_id": "guildhall_crossing_square"}
    ws.save_drafts("shattered_realms", drafts)

    assert svc.normalize_command(a, ["apply"]).ok
    applied = ws.load("shattered_realms")["entities"]["training_rat"]
    assert applied["vnum"] == 1500
    assert applied["area_id"] == "starter_guildlands"
    assert applied["zone_id"] == "guildhall_crossing"
    assert svc.normalize_command(a, ["verify"]).ok
    assert svc.normalize_command(a, ["rollback"]).ok
    rolled = ws.load("shattered_realms")["entities"]["training_rat"]
    assert "vnum" not in rolled


def test_picker_continuation_opens_stable_numbered_choice(tmp_path):
    ws = BuilderWorkspace(worlds_dir=tmp_path / "worlds")
    svc = BuilderService(ws)
    a = actor()
    drafts = ws.load("shattered_realms")
    drafts.setdefault("entities", {})["alpha_wolf"] = {"id": "alpha_wolf", "name": "Alpha Wolf", "vnum": 1500, "area_id": "starter_guildlands", "zone_id": "guildhall_crossing"}
    drafts.setdefault("entities", {})["beta_wolf"] = {"id": "beta_wolf", "name": "Beta Wolf", "vnum": 1501, "area_id": "starter_guildlands", "zone_id": "guildhall_crossing"}
    ws.save_drafts("shattered_realms", drafts)

    choices = svc.discover_editor_target(a, "medit", ["wolf"])
    assert not choices.ok and "Enter number" in choices.message
    opened = svc.continue_picker(a, "1")
    assert opened is not None and opened.ok
    assert "Mobile Editor" in opened.message


def test_bnorm_routes_through_command_engine(tmp_path):
    ws = BuilderWorkspace(worlds_dir=tmp_path / "worlds")
    engine = MudCommandEngine()
    engine.builder = ws
    engine.builder_service = BuilderService(ws)
    res = engine.command_handlers["bnorm"](actor(), ["audit"], "bnorm audit")
    assert "Builder normalization audit" in res.narrative
