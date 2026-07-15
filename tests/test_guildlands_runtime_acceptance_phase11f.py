from pathlib import Path

from engine.command_registry import CommandRegistry
from smart_mud.world_registry import WorldRegistry, _records


def test_world_registry_loads_nested_builder_item_templates() -> None:
    records = _records(Path.cwd() / "worlds" / "shattered_realms", "item_templates")
    ids = {record["id"] for record in records}
    assert "training_sword" in ids
    assert "clean_water_flask" in ids


def test_guildlands_player_commands_are_registered_as_canonical_commands() -> None:
    registry = CommandRegistry()
    required = {
        "look", "north", "south", "inventory", "equipment", "score", "quests", "journal",
        "talk", "greet", "accept", "turnin", "progress", "gather", "loot", "skin",
        "butcher", "harvest", "cook", "eat", "drink", "shop", "sell", "rent", "sleep",
        "wake", "home", "property", "storage", "save",
    }
    missing = sorted(command for command in required if command not in registry.commands)
    assert missing == []
    assert all(registry.commands[command].implemented for command in required)


def test_shattered_realms_runtime_package_exposes_guildlands_acceptance_content() -> None:
    world = WorldRegistry(Path.cwd() / "worlds").load_world("shattered_realms")
    assert world.default_starting_room_id == "guildhall_crossing_square"
    names = "\n".join(str(x.get("name", "")) for x in world.npcs + world.spawns + world.features + world.shops)
    rooms = {room.get("id") for room in world.rooms}
    assert "Guild Registrar Maren" in names
    assert "guildhall_crossing_square" in rooms
    assert any("hunting" in str(room.get("name", "")).lower() or "trail" in str(room.get("name", "")).lower() for room in world.rooms)
