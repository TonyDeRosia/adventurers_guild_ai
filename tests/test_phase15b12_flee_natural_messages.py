from engine.combat_runtime import CombatRuntimeService
from engine.actors import Actor, ActorIdentity
from engine.combat import CombatEngine
from engine.combat_equipment import CombatContentRegistry
from smart_mud.world_registry import WorldRegistry


class DummyRuntime:
    active_world_id = "shattered_realms"
    active_world = None
    event_bus = None
    performance_counters = {}
    _current_command_trace = object()
    def __init__(self):
        class Store: db_path = ":memory:"
        self.state_store = Store()


def actor(aid, name, dex=10, level=1, room="r"):
    a = Actor.create(aid, name, "npc" if aid.startswith("entity:") else "player")
    a.identity = ActorIdentity(name=name, current_location=room, current_world="shattered_realms")
    a.attributes["dexterity"] = dex
    a.progression_profile["level"] = level
    return a


def svc():
    rt = DummyRuntime()
    s = object.__new__(CombatRuntimeService)
    s.runtime = rt; s.FLEE_BASE_CHANCE=50.0; s.FLEE_DEX_WEIGHT=4.0; s.FLEE_LEVEL_WEIGHT=1.5; s.FLEE_MIN_CHANCE=5.0; s.FLEE_MAX_CHANCE=95.0
    return s


def test_flee_formula_threshold_weights_and_clamps():
    s = svc(); hero=actor("character:h", "Hero", 10, 5); foe=actor("entity:f", "Foe", 10, 5)
    assert s.calculate_flee_chance(hero, [foe])["chance"] == 50
    assert s.calculate_flee_chance(actor("character:h", "Hero", 15, 5), [foe])["chance"] == 70
    assert s.calculate_flee_chance(actor("character:h", "Hero", 5, 5), [foe])["chance"] == 30
    assert s.calculate_flee_chance(actor("character:h", "Hero", 10, 15), [foe])["chance"] == 65
    assert s.calculate_flee_chance(actor("character:h", "Hero", 10, -5), [foe])["chance"] == 35
    assert s.calculate_flee_chance(actor("character:h", "Hero", 30, 50), [foe])["chance"] == 95
    assert s.calculate_flee_chance(actor("character:h", "Hero", 1, -50), [foe])["chance"] == 5


def test_multiple_opponents_use_lowest_chance():
    s = svc(); hero=actor("character:h", "Hero", 10, 10)
    weak=actor("entity:w", "Weak", 5, 1); strong=actor("entity:s", "Strong", 18, 20)
    calc=s.calculate_flee_chance(hero, [weak, strong])
    assert calc["selected_opponent"] == "entity:s"
    assert calc["chance"] < 50


def test_nonhumanoid_natural_attack_and_message_grammar():
    world = WorldRegistry().load_world("shattered_realms")
    engine = CombatEngine(content=CombatContentRegistry(world))
    bear=actor("entity:b", "Ashback Bear"); bear.body_profile_id="bear"
    target=actor("character:t", "Kraevok")
    ap=engine.attack_profile(bear)
    assert ap.source == "natural"
    assert ap.name.lower() != "fist"
    msg=engine._messages(bear, target, "hit", type("E", (), {"attack_profile":{"name":"claws"}, "weapon":{}, "final_damage":10, "critical":False})())
    assert "punches hard you" not in msg["victim"]
    assert " you " in msg["victim"]
