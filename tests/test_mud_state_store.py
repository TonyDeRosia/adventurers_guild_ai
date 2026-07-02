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


def test_mud_death_respawn_and_permanent_story_npc(tmp_path: Path) -> None:
    store = MUDStateStore("camp", "world", db_path=tmp_path / "camp.sqlite")
    rat_spawn = {
        "spawn_id": "rat_spawn",
        "npc_id": "cellar_rat",
        "room_id": "cellar",
        "max_alive": 1,
        "respawn_enabled": True,
        "respawn_delay_seconds": 0,
        "respawn_mode": "normal",
        "corpse_decay_seconds": 60,
    }
    story_spawn = {
        "spawn_id": "maren_spawn",
        "npc_id": "guild_registrar_maren",
        "room_id": "office",
        "max_alive": 1,
        "respawn_enabled": False,
        "respawn_delay_seconds": 0,
        "respawn_mode": "story_permanent",
    }

    rat = store.spawn_mobs_for_room("cellar", [rat_spawn])[0]
    assert store.load_alive_mobs("cellar")[0]["npc_id"] == "cellar_rat"
    dead_rat = store.mark_mob_dead(rat["instance_id"], "player_1", "combat", "Player killed a cellar rat.")
    assert dead_rat["status"] == "dead"
    assert store.load_alive_mobs("cellar") == []
    assert store.load_corpses("cellar")[0]["npc_id"] == "cellar_rat"
    assert store.recall_kill_history("cellar_rat", "player_1")[0]["summary"] == "Player killed a cellar rat."
    assert store.load_respawn_timers("cellar")[0]["spawn_id"] == "rat_spawn"
    assert store.process_due_respawns("9999-01-01T00:00:00+00:00")[0]["npc_id"] == "cellar_rat"
    assert store.load_alive_mobs("cellar")[0]["npc_id"] == "cellar_rat"

    story = store.spawn_mobs_for_room("office", [story_spawn])[0]
    store.mark_mob_dead(story["instance_id"], "player_1", "combat", "Maren died permanently.")
    assert store.load_alive_mobs("office") == []
    assert store.load_respawn_timers("office") == []
    assert store.process_due_respawns("9999-01-01T00:00:00+00:00") == []
