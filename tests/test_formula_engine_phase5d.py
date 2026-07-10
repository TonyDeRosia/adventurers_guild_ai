from types import SimpleNamespace

from engine.actors import Actor
from engine.formulas import FormulaDefinition, FormulaEngine, FormulaRegistry, Modifier, ModifierRegistry
from engine.mud_commands import MudCommandEngine
from smart_mud.builder import BuilderWorkspace


def char(role="builder"):
    return SimpleNamespace(id="c1", account_id="a1", name="Tester", role=role, account_role=role, world_id="shattered_realms", room_id="start", level=1, hp=10, max_hp=10, mana=5, max_mana=5, stamina=5, max_stamina=5, xp=0, gold=0, equipment={}, affects={})


def test_formula_registry_creation_lookup_replacement_and_metadata():
    registry = FormulaRegistry.default()
    assert registry.get("attack_rating") is not None
    registry.replace(FormulaDefinition(id="attack_rating", display_name="World Attack", version="2.0.0", outputs=["attack_rating"], builder_owner="builder"))
    assert registry.get("attack_rating").version == "2.0.0"
    assert any(m["id"] == "attack_rating" for m in registry.metadata())


def test_formula_validation_circular_and_missing_dependencies():
    registry = FormulaRegistry()
    registry.register(FormulaDefinition(id="a", dependencies=["b"]))
    registry.register(FormulaDefinition(id="b", dependencies=["a", "missing"]))
    result = registry.validate()
    assert not result.ok
    assert any("circular" in e for e in result.errors)
    assert any("missing dependency missing" in e for e in result.errors)


def test_modifier_registration_stacking_policies_unknown_warning():
    mods = ModifierRegistry()
    mods.register(Modifier.create("movement_speed", "add", 1, id="low", source="boots", category="equipment", stacking_rule="highest_only"))
    mods.register(Modifier.create("movement_speed", "add", 3, id="high", source="boots", category="equipment", stacking_rule="highest_only"))
    mods.register(Modifier.create("builder_stat", "add", 5, id="future"))
    assert [m.id for m in mods.stacked_for_stat("movement_speed")] == ["high"]
    assert any("unknown target stat builder_stat" in w for w in mods.validate().warnings)


def test_formula_tracing_and_actor_integration():
    mods = ModifierRegistry()
    mods.register(Modifier.create("attack_rating", "add", 2, id="blessing", source="buff"))
    engine = FormulaEngine(modifiers=mods)
    actor = Actor.create("a1", "A")
    result = actor.get_derived_value("attack_rating", engine, base_value=10)
    assert result.final_value == 12
    assert result.formula_name == "attack_rating"
    assert result.modifier_list[0]["id"] == "blessing"
    assert any(step["step"] == "modifier" for step in result.calculation_trace)


def test_builder_diagnostics_commands_are_read_only():
    eng = MudCommandEngine()
    c = char()
    assert "attack_rating" in eng.handle_command(c, "formula list").narrative
    assert "Formula validation" in eng.handle_command(c, "formula validate").narrative
    assert "Modifier Registry" in eng.handle_command(c, "modifier list").narrative
    assert "Actor formulas" in eng.handle_command(c, "actor formulas").narrative


def test_builder_import_export_recognizes_formula_collections(tmp_path):
    workspace = BuilderWorkspace(worlds_dir=tmp_path)
    c = char(); c.world_id = "test_world"
    root = workspace.ensure("test_world")
    assert (root / "formulas.json").exists()
    assert (root / "modifier_types.json").exists()
    bundle = root / "imports" / "formula_bundle.json"
    bundle.write_text('{"formulas":{"custom_formula":{"id":"custom_formula","outputs":["builder_stat"]}},"modifier_types":{"mystery":{"operation":"mystery"}},"future_formula_templates":{}}')
    validation = workspace.import_validate(c, "formula_bundle.json")
    assert validation.ok
    assert "unknown modifier type mystery" in validation.message
    applied = workspace.import_apply(c, "formula_bundle.json")
    assert applied.ok
    exported = workspace.export(c)
    assert exported.ok


def test_future_plugin_formula_and_builder_defined_stat():
    registry = FormulaRegistry()
    registry.register(FormulaDefinition(id="plugin_speed", plugin_owner="weather_plugin", outputs=["storm_speed"], world_overrides={"world": "custom"}))
    mods = ModifierRegistry()
    mods.register(Modifier.create("storm_speed", "custom", {"script": "builder"}, id="builder_custom", stacking_rule="builder_custom"))
    assert registry.validate().ok
    assert mods.stacked_for_stat("storm_speed")[0].id == "builder_custom"
