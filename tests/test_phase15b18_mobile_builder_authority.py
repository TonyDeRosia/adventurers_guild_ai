from pathlib import Path
from types import SimpleNamespace
import ast

from smart_mud.builder import BuilderService, BuilderWorkspace


def actor(name="Tony", role="builder", zones=None):
    return SimpleNamespace(id=name.lower(), name=name, account_id=f"acct-{name.lower()}", session_id=f"sess-{name.lower()}", role=role, world_id="test_world", room_id="start", current_zone_id="emberwood_edge", builder_zone_ids=zones or ["emberwood_edge"])


def test_medit_main_menu_has_phase15b18_sections(tmp_path):
    svc = BuilderService(BuilderWorkspace(tmp_path))
    a = actor(role="admin")
    assert svc.create_or_update_mobile(a, "forest_wolf", {"id":"forest_wolf", "name":"Forest Wolf", "zone_id":"emberwood_edge", "description":"A wolf."}).ok
    opened = svc.start_editor(a, "medit", "entities", "forest_wolf")
    assert opened.ok
    text = opened.message
    for label in ["MOBILE EDITOR: Forest Wolf", "1. Identity", "8. Body profile and Natural Weapons", "12. Equipment loadout", "18. Scripts and triggers", "20. Diagnostics and references", "S. Save"]:
        assert label in text


def test_zone_ownership_denies_unassigned_builder_and_admin_overrides(tmp_path):
    svc = BuilderService(BuilderWorkspace(tmp_path))
    admin = actor(role="admin")
    assert svc.create_or_update_mobile(admin, "forest_wolf", {"id":"forest_wolf", "name":"Forest Wolf", "zone_id":"emberwood_edge"}).ok
    denied = svc.start_editor(actor("Alice", zones=["rat_cellar"]), "medit", "entities", "forest_wolf")
    assert not denied.ok and "Zone ownership denied" in denied.message and "emberwood_edge" in denied.message
    assert svc.start_editor(actor("Owner", role="admin", zones=[]), "medit", "entities", "forest_wolf").ok


def test_direct_mobile_command_updates_active_session_scratch(tmp_path):
    svc = BuilderService(BuilderWorkspace(tmp_path))
    a = actor(role="admin")
    assert svc.create_or_update_mobile(a, "forest_wolf", {"id":"forest_wolf", "name":"Forest Wolf", "zone_id":"emberwood_edge"}).ok
    assert svc.start_editor(a, "medit", "entities", "forest_wolf").ok
    res = svc.create_or_update_mobile(a, "forest_wolf", {"name":"Scratch Wolf"}, "mset")
    assert res.ok and "active medit scratch" in res.message
    assert svc.workspace.load("test_world")["entities"]["forest_wolf"]["name"] == "Forest Wolf"
    assert "Scratch Wolf" in svc.preview(a, "entities", "forest_wolf").message
    assert svc.sessions.handle(a, "save").ok
    assert svc.workspace.load("test_world")["entities"]["forest_wolf"]["name"] == "Scratch Wolf"


def test_builder_python_no_deprecated_runtime_attack_authorities():
    text = Path("smart_mud/builder.py").read_text()
    assert "BODY_PROFILE_ATTACKS" not in text
    assert "TBA_ATTACK_FAMILIES" not in text


def test_mud_commands_entity_mutations_go_through_builder_service():
    tree = ast.parse(Path("engine/mud_commands.py").read_text())
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"create_or_update", "delete"}:
            if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == "entities":
                violations.append((node.lineno, node.func.attr))
    assert not violations
