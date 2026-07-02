from pathlib import Path

from engine.mud_state_store import MUDStateStore


def test_mud_state_store_schema_and_round_trip(tmp_path: Path) -> None:
    store = MUDStateStore("camp", "world", db_path=tmp_path / "camp.sqlite")
    store.initialize()
    store.save_character({"character_id": "player_1", "name": "Aria", "level": 2, "xp": 5, "current_room_id": "room", "hp": 12, "gold": 3})
    assert store.load_character("player_1")["name"] == "Aria"
    store.save_character_stats("player_1", {"Strength": 7})
    assert store.load_character_stats("player_1") == {"Strength": 7}
    store.save_abilities("player_1", ["slash", {"id": "spark"}])
    assert store.load_abilities("player_1") == ["slash", "spark"]
    store.save_inventory("player_1", [{"item_id": "torch", "quantity": 2}])
    assert store.load_inventory("player_1")[0]["item_id"] == "torch"
    store.mark_room_visited("room"); store.mark_room_visited("room")
    assert store.load_room_runtime("room")["visited_count"] == 2
    assert store.load_relationship("jory", "player_1")["trust"] == 50
    rel = store.update_relationship("jory", "player_1", {"trust": -99, "hostility": 120})
    assert rel["trust"] == 0 and rel["hostility"] == 100
    store.add_npc_memory("jory", "player_1", "Player insulted Jory.", tags=["rude"])
    assert store.recall_npc_memories("jory", "player_1")[0]["summary"] == "Player insulted Jory."
    store.log_conversation(character_id="player_1", npc_id="jory", room_id="room", speaker="player", text="hello")
    assert store.load_recent_conversation("jory", "player_1")[0]["text"] == "hello"
    store.log_event(character_id="player_1", room_id="room", summary="Character entered world.")
    assert store.load_recent_events("camp")[0]["summary"] == "Character entered world."
    assert store.update_reputation("guild", "player_1", 15)["reputation"] == 15
