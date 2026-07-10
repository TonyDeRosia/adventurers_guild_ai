from engine.actors import Actor
from engine.combat import CombatEngine, CombatState, apply_damage
from engine.formulas import FormulaEngine, Modifier, ModifierRegistry
from engine.phase5f import ActorLifecycleManager


def actor(aid, name, hp=30):
    a = Actor.create(aid, name, "npc")
    a.resources.health = a.resources.maximum_health = hp
    return a


def test_weapon_attack_hit_critical_mitigation_and_trace():
    mods = ModifierRegistry()
    mods.register(Modifier.create("accuracy", "override", 100, id="acc"))
    mods.register(Modifier.create("attack_power", "override", 5, id="pow"))
    mods.register(Modifier.create("critical_chance", "override", 100, id="crit"))
    mods.register(Modifier.create("armor", "override", 3, id="armor"))
    engine = CombatEngine(FormulaEngine(modifiers=mods), seed="same")
    p = actor("p1", "Player")
    gob = actor("g1", "Goblin")
    p.equipment_profile["main_hand"] = {"id":"sword", "name":"Builder Sword", "attack_profile":{"id":"slash", "damage_type":"slash", "base_damage":7, "speed":2}}
    result = engine.resolve_attack(p, gob)
    assert result.hit is True
    assert result.damage_event.critical is True
    assert result.damage_event.final_damage == 21  # (7+5)*2 - 3
    assert gob.resources.health == 9
    assert [t["step"] for t in result.trace][:3] == ["resolve_attacker_actor", "resolve_defender_actor", "resolve_attack_profile"]


def test_miss_is_deterministic_and_same_seed_matches():
    mods = ModifierRegistry(); mods.register(Modifier.create("accuracy", "override", 0, id="acc")); mods.register(Modifier.create("defense_rating", "override", 95, id="def"))
    one = CombatEngine(FormulaEngine(modifiers=mods), seed="fixed")
    two = CombatEngine(FormulaEngine(modifiers=mods), seed="fixed")
    assert one.resolve_attack(actor("a", "A"), actor("b", "B")).hit == two.resolve_attack(actor("a", "A"), actor("b", "B")).hit


def test_natural_attack_body_profile_and_resistance():
    mods = ModifierRegistry(); mods.register(Modifier.create("accuracy", "override", 100, id="acc"))
    wolf = actor("w", "Wolf"); wolf.body_profile_id = "wolf"; wolf.combat_profile["natural_weapons"] = [{"id":"bite", "slot":"head", "damage_type":"pierce", "base_damage":6}]
    player = actor("p", "Player"); player.resistance_profile["pierce"] = 2
    result = CombatEngine(FormulaEngine(modifiers=mods)).resolve_attack(wolf, player)
    assert result.damage_event.attack_profile["source"] == "natural"
    assert result.damage_event.final_damage == 4


def test_damage_api_death_handoff_corpse_and_respawn_queue(tmp_path):
    life = ActorLifecycleManager(tmp_path / "life.db", "world")
    mods = ModifierRegistry(); mods.register(Modifier.create("accuracy", "override", 100, id="acc")); mods.register(Modifier.create("attack_power", "override", 99, id="pow"))
    attacker = actor("killer", "Killer"); victim = actor("victim", "Victim", hp=5)
    victim.lifecycle_profile = {"respawn_delay": 10, "spawn_definition_id": "spawn_victim"}
    result = CombatEngine(FormulaEngine(modifiers=mods), lifecycle=life).resolve_attack(attacker, victim, room_id="room", world_time=7)
    assert victim.combat_profile["combat_state"] == CombatState.DEAD.value
    assert result.death_handoff["actor_id"] == "victim"
    assert life.get("victim")["state"] == "corpse"
    assert life.respawn_due(17)[0]["actor_id"] == "victim"


def test_consider_and_resource_api():
    weak = actor("weak", "Weak", hp=5); strong = actor("strong", "Strong", hp=100)
    assert CombatEngine().consider(strong, weak) == "weak"
    assert apply_damage(strong, 10)["after"] == 90
    assert strong.apply_healing(5)["after"] == 95
