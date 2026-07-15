from types import SimpleNamespace

from engine.command_registry import CommandRegistry
from engine.mud_commands import MudCommandEngine


def char(role="player"):
    return SimpleNamespace(id="c1", name="Tester", role=role, level=1, hp=10, max_hp=10, mana=5, max_mana=5, stamina=8, max_stamina=8, xp=0, gold=0, inventory=[], equipment={}, abilities=[], affects={}, preferences={})


def test_registry_contains_metadata_and_aliases():
    registry = CommandRegistry()
    meta = registry.commands["score"]
    assert meta.command == "score"
    assert meta.aliases == ("sc",)
    assert meta.category == "informational"
    assert meta.status == "implemented"
    assert meta.transport_safe is True
    assert registry.resolve("id") == ("identify", "alias")


def test_commands_group_and_hide_admin_builder():
    engine = MudCommandEngine()
    text = engine.handle_command(char(), "commands").narrative
    assert "Movement:" in text
    assert "Information:" in text
    assert "score" in text
    assert "redit" not in text
    assert "goto" not in text


def test_commands_all_exposes_planned_safely():
    engine = MudCommandEngine()
    text = engine.handle_command(char(), "commands all").narrative
    assert "Combat:" in text
    assert "kill" in text


def test_help_uses_registry_metadata():
    engine = MudCommandEngine()
    score = engine.handle_command(char(), "help score").narrative
    get = engine.handle_command(char(), "help get").narrative
    assert "Command: score" in score and "Aliases: sc" in score
    assert "Command: get" in get and "Pick up an item" in get


def test_placeholders_and_toggles_are_clean():
    engine = MudCommandEngine()
    c = char()
    assert "Weather:" in engine.handle_command(c, "weather").narrative
    assert "mount" in engine.handle_command(c, "mount").narrative.lower()
    assert "brief is now ON" in engine.handle_command(c, "brief").narrative
    assert "Prompt preset:" in engine.handle_command(c, "prompt").narrative


def test_ambiguous_abbreviation_does_not_guess():
    engine = MudCommandEngine()
    result = engine.handle_command(char(), "s")
    # exact alias south wins; a truly ambiguous abbreviation asks.
    result = engine.handle_command(char(), "a")
    assert result.ok is False
    assert "Which command did you mean?" in result.narrative



def test_registry_help_list_and_placeholder_events_fire():
    from smart_mud.event_bus import EventBus
    bus = EventBus()
    seen = []
    for name in ["command_registered", "command_alias_registered", "command_help_requested", "command_list_requested", "command_placeholder_used"]:
        bus.subscribe(name, lambda event: seen.append(event.event_name), source=f"test_{name}")
    engine = MudCommandEngine(event_bus=bus)
    c = char()
    engine.handle_command(c, "help score")
    engine.handle_command(c, "commands")
    engine.handle_command(c, "mount")
    assert "command_registered" in seen
    assert "command_alias_registered" in seen
    assert "command_help_requested" in seen
    assert "command_list_requested" in seen
    assert "command_placeholder_used" in seen
