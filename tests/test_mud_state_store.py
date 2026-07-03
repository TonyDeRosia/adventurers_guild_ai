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


def test_smart_mud_v3_persistent_world_tables_and_round_trip(tmp_path: Path) -> None:
    store = MUDStateStore("camp", "world", db_path=tmp_path / "smart.sqlite")
    store.initialize()
    required = {
        "accounts", "account_settings", "account_preferences", "account_permissions", "account_logs",
        "characters", "character_stats", "character_inventory", "character_equipment", "character_skills",
        "character_spells", "character_abilities", "character_affects", "character_prompt", "character_aliases",
        "character_hotkeys", "character_languages", "character_titles", "character_conditions", "character_quests",
        "character_factions", "character_reputation", "character_bank", "character_storage", "character_cooldowns",
        "character_known_locations", "character_settings", "npc_templates", "npc_instances", "npc_current_room",
        "npc_health", "npc_inventory", "npc_equipment", "npc_relationships", "npc_memories", "npc_reputation",
        "npc_schedule", "npc_goals", "npc_personality_state", "npc_emotions", "npc_recent_events",
        "npc_dialog_history", "npc_known_players", "npc_current_activity", "npc_flags", "room_runtime",
        "room_items", "room_corpses", "room_doors", "room_weather", "room_lighting", "room_events",
        "room_players", "room_npcs", "room_objects", "room_flags", "room_variables", "room_reset_state",
        "item_instances", "mob_spawns", "mob_instances", "death_log", "world_state", "quests_runtime",
        "factions", "faction_reputation", "faction_alliances", "shops", "shop_inventories", "shop_transactions",
        "price_history", "merchant_ownership", "merchant_reputation", "restock_timers",
    }
    assert required.issubset(set(store.list_tables()))

    store.upsert_account("acct", "aria")
    store.save_character({"character_id": "player_1", "name": "Aria", "current_room_id": "square"})
    assert store.load_character("player_1")["current_room_id"] == "square"
    store.save_npc_template("guard", {"name": "Gate Guard"})
    assert store.load_npc_template("guard")["template"]["name"] == "Gate Guard"
    store.save_npc_instance("guard:1", "guard", "square", {"ai_state": {"alert": True}})
    assert store.load_npc_instance("guard:1")["current_room_id"] == "square"
    assert store.update_relationship("guard", "player_1", {"trust": 10, "suspicion": 5, "friendship": 3, "debt": 2, "favor": 1})["suspicion"] == 5
    store.add_npc_memory("guard", "player_1", "Player tipped NPC.", emotion="grateful", related_room="square", importance=7)
    memory = store.recall_npc_memories("guard", "player_1")[0]
    assert memory["importance"] == 7 and memory["emotion"] == "grateful"
    store.save_room_runtime("square", {"visited_count": 1, "lighting": "dawn"})
    assert store.load_room_runtime("square")["state"]["lighting"] == "dawn"
    store.create_item_instance("sword:1", "iron_sword", current_owner="player_1", durability=88, flags=["sharp"])
    assert store.load_item_instance("sword:1")["flags"] == ["sharp"]
    store.create_corpse("corpse:1", "square", owner="rat", gold=2, decay_seconds=60, items=["tail"])
    assert store.load_persistent_corpses("square")[0]["items"] == ["tail"]
    store.save_world_state("clock", {"day": 2, "hour": 9})
    store.save_world_state("weather", {"condition": "rain"})
    assert store.load_world_state("clock")["day"] == 2
    store.save_quest_state("player_1", "quest_1", "active", {"talked_to_guard": True})
    assert store.load_quest_state("player_1", "quest_1")["active_objectives"]["talked_to_guard"] is True
    assert store.update_reputation("guard_faction", "player_1", 12)["reputation"] == 12
    store.save_shop_inventory("shop", "bread", 4, 3, gold=25)
    assert store.load_shop_inventory("shop")[0]["item_id"] == "bread"

    restarted = MUDStateStore("camp", "world", db_path=tmp_path / "smart.sqlite")
    assert restarted.load_item_instance("sword:1")["durability"] == 88
    context = restarted.build_ai_context("player_1", "guard", "square")
    assert ["player", "character", "current_room", "nearby_players", "nearby_npcs", "npc_personality", "npc_relationships", "npc_memories", "current_conversation", "faction_reputation", "world_time", "weather", "active_quests", "recent_room_events", "relevant_world_lore"] == list(context.keys())
