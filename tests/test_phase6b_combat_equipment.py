from engine.actors import Actor
from engine.combat import CombatEngine
from engine.combat_equipment import CombatContentRegistry
from engine.formulas import FormulaEngine, Modifier, ModifierRegistry
from smart_mud.world_registry import WorldRegistry


def test_phase6b_world_loads_and_validates_combat_content():
    world = WorldRegistry().load_world("shattered_realms")
    content = CombatContentRegistry(world)
    assert "sword" in content.weapon_classes
    assert "iron_sword" in content.weapon_templates
    assert "leather_armor" in content.armor_templates
    assert "slash" in content.attack_profiles
    assert "iron_sword" in content.damage_profiles
    assert "precise" in content.critical_profiles
    assert "wolf_bite" in content.natural_weapon_profiles
    assert content.validate() == []


def test_canonical_weapon_attack_and_armor_mitigation_are_data_driven():
    world = WorldRegistry().load_world("shattered_realms")
    content = CombatContentRegistry(world)
    mods = ModifierRegistry(); mods.register(Modifier.create("accuracy", "override", 100, id="acc")); mods.register(Modifier.create("critical_chance", "override", 0, id="crit"))
    attacker = Actor.create("a", "Guard")
    attacker.equipment_profile["equipped"] = {"main_hand": content.weapon_templates["iron_sword"]}
    defender = Actor.create("d", "Raider")
    defender.equipment_profile["equipped"] = {"body": content.armor_templates["leather_armor"], "off_hand": content.armor_templates["training_shield"]}
    result = CombatEngine(FormulaEngine(modifiers=mods), content=content).resolve_attack(attacker, defender)
    assert result.damage_event.base_damage == 7
    assert result.damage_event.mitigation == 4
    assert result.damage_event.final_damage == 3
    assert result.damage_event.attack_profile["metadata"]["damage_profile"]["id"] == "iron_sword"


def test_canonical_natural_weapon_originates_from_body_profile_builder_data():
    world = WorldRegistry().load_world("shattered_realms")
    content = CombatContentRegistry(world)
    mods = ModifierRegistry(); mods.register(Modifier.create("accuracy", "override", 100, id="acc"))
    wolf = Actor.create("w", "Wolf"); wolf.body_profile_id = "wolf"
    target = Actor.create("t", "Target")
    result = CombatEngine(FormulaEngine(modifiers=mods), content=content).resolve_attack(wolf, target)
    assert result.damage_event.attack_profile["source"] == "natural"
    assert result.damage_event.base_damage == 6
    assert result.damage_event.weapon["id"] == "wolf_bite"


def test_shield_occupancy_and_equipment_set_starter_examples():
    world = WorldRegistry().load_world("shattered_realms")
    content = CombatContentRegistry(world)
    shield = content.armor_templates["training_shield"]
    assert shield["equipment_type"] == "shield"
    assert shield["occupies_slots"] == ["off_hand"]
    assert content.equipment_sets["guard_equipment"]["items"] == ["iron_sword", "leather_armor", "training_shield"]
