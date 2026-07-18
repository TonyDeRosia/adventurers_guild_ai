from engine.command_registry import CommandMeta, CommandRegistry
from engine.mud_commands import MudCommandEngine
from smart_mud.transport import RuntimeTransportAdapter, TransportMessage


class RuntimeSpy:
    def __init__(self):
        self.calls = []
        self.event_bus = None

    def handle_input(self, character_id, text):
        self.calls.append((character_id, text))
        return {"output": "ok", "view": {"prompt": ">"}}


def test_phase18j_cast_handler_is_authoritative_phase18_parser():
    engine = MudCommandEngine()
    assert engine.command_handlers["cast"] == engine._cmd_use_ability
    assert engine.resolve_alias("c") == "cast"


def test_phase18j_duplicate_command_registration_rejected():
    registry = CommandRegistry()
    try:
        registry.register(CommandMeta(command="look"))
    except ValueError as exc:
        assert "Duplicate command registration" in str(exc)
    else:
        raise AssertionError("duplicate command registration was accepted")


def test_phase18j_web_and_telnet_base_adapter_dispatch_once():
    runtime = RuntimeSpy()
    adapter = RuntimeTransportAdapter(runtime)
    session = adapter.create_session(character_id="char_1")
    adapter.handle_message(TransportMessage(session=session, text="spells"))
    assert runtime.calls == [("char_1", "spells")]
