from engine.actors import Actor
from engine.mud_commands import MudCommandEngine
from engine.mud_runtime import MudCharacter
from engine.score_renderer import ActorScoreRenderer


def test_full_score_contains_new_part2_sections_and_plain_boxes():
    actor = Actor.create("char_full", "Full", "player")
    text = ActorScoreRenderer().render(actor)
    for title in ["Score Identity", "Resources", "Primary Attributes", "Derived Attributes", "Combat Profile", "Equipment", "Conditions", "Resistances", "Affects", "Spellup", "Progression", "Currencies", "Relationships", "Simulation"]:
        assert title in text
    assert "+----------------------------------------------------------------------------+" in text
    assert "BUILDER DIAGNOSTICS" not in text


def test_equipment_slots_affect_spellup_grouping_and_future_builder_values():
    actor = Actor.create("char_mod", "Mod", "player")
    actor.equipment_profile = {"equipped": {"head": {"name": "a plumed helm"}}}
    actor.effect_container = {
        "positive": [{"name": "Bless", "source": "temple", "duration": "medium", "remaining": "12m", "stacks": 1}],
        "negative": [{"name": "Chill", "source": "weather", "category": "negative"}],
        "spellup": {"long": [{"name": "Armor", "source": "self", "remaining": "1h"}]},
    }
    actor.attributes["honor"] = 15
    actor.resistance_profile["radiant"] = {"base": "future", "equipment": "future", "effects": "future", "total": "future"}
    actor.plugin_data["resources"] = {"resolve": "future"}
    actor.plugin_data["currencies"] = {"gold": 7, "favor": "future"}

    renderer = ActorScoreRenderer()
    assert "Head" in renderer.render(actor, "equipment") and "a plumed helm" in renderer.render(actor, "equipment")
    assert "Bless" in renderer.render(actor, "affects") and "Negative" in renderer.render(actor, "affects")
    assert "Armor" in renderer.render(actor, "spellup") and "Long" in renderer.render(actor, "spellup")
    assert "Honor" in renderer.render(actor, "attributes")
    assert "Radiant" in renderer.render(actor, "resistances")
    assert "Resolve" in renderer.render(actor, "resources")
    assert "Favor" in renderer.render(actor, "currencies")


def test_builder_diagnostics_formulas_raw_are_admin_only_and_same_renderer_path():
    actor = Actor.create("char_admin", "Admin", "player")
    renderer = ActorScoreRenderer()
    assert "restricted" in renderer.render(actor, "raw", admin=False)
    assert "Formula Debug" in renderer.render(actor, "formulas", admin=True)
    assert '"actor_id": "char_admin"' in renderer.render(actor, "raw", admin=True)
    assert renderer._renderers["relationships"] == renderer.render_relationships


def test_score_related_commands_use_score_renderer_sections():
    engine = MudCommandEngine()
    char = MudCharacter(id="char_cmd", name="Cmd", role="builder", gold=42)
    assert "CURRENCIES" in engine.handle_command(char, "worth").narrative
    assert "EQUIPMENT" in engine.handle_command(char, "equipment").narrative
    assert "AFFECTS" in engine.handle_command(char, "saff").narrative
    assert "SPELLUP" in engine.handle_command(char, "spellup").narrative
    assert "FORMULA DEBUG" in engine.handle_command(char, "score formulas").narrative
    assert "RAW ACTOR JSON" in engine.handle_command(char, "score raw").narrative
    assert "BUILDER DIAGNOSTICS" in engine.handle_command(char, "score diagnostics").narrative
