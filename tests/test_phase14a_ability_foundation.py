import sqlite3
from types import SimpleNamespace

from engine.abilities import AbilityExecutionService, AbilityRegistry, init_ability_schema, AbilityEffectOperationRegistry
from engine.actors import Actor


def pkg():
    return SimpleNamespace(
        id="test_world",
        abilities=[
            {"id":"venom","name":"Venom","ability_type":"spell","targeting":{"mode":"single_actor"},"plugin_data":{"canonical_effects":[{"effect_id":"venom_dot","operation":"damage_over_time","base_value":3,"damage_type":"poison","duration":{"domain":"world_minutes","amount":3},"tick_interval":1,"tags":["poison"],"messages":{"target_wear_off":"The poison fades from {target}."}}]}},
            {"id":"cure_poison","name":"Cure Poison","ability_type":"spell","targeting":{"mode":"single_actor"},"plugin_data":{"canonical_effects":[{"effect_id":"cure","operation":"cleanse","tags":["poison"]}]}},
            {"id":"ember","name":"Ember","ability_type":"spell","targeting":{"mode":"single_actor"},"plugin_data":{"canonical_effects":[{"effect_id":"burn","operation":"deal_damage","base_value":4,"damage_type":"fire"}]}},
            {"id":"regen","name":"Regeneration","ability_type":"spell","targeting":{"mode":"single_actor"},"plugin_data":{"canonical_effects":[{"effect_id":"regen_hot","operation":"healing_over_time","resource":"health","base_value":2,"duration":{"domain":"world_minutes","amount":2},"tick_interval":1,"tags":["regeneration"]}]}},
            {"id":"reagent_spell","name":"Reagent Spell","ability_type":"spell","targeting":{"mode":"self"},"plugin_data":{"materials":[{"template_id":"ruby_dust","quantity":2,"consume_timing":"start"}],"canonical_effects":[{"effect_id":"msg","operation":"send_message","messages":{"actor_success":"Dust flares."}}]}},
        ],
        ability_loadouts=[], ability_schools=[], ability_categories=[], cooldown_groups=[], effect_templates=[], resource_profiles=[], damage_profiles=[], combat_formulas=[]
    )


def service(tmp_path):
    db=tmp_path/"mud.db"; init_ability_schema(db)
    svc=AbilityExecutionService(db, pkg(), world_id="test_world")
    hero=Actor.create("hero","Hero","player"); rat=Actor.create("rat","Rat","mob")
    svc.register_actor(hero); svc.register_actor(rat)
    for aid in svc.registry.abilities: svc.grant_ability("hero", aid, "test", aid)
    return svc, hero, rat, db


def test_phase14a_registry_rejects_unknown_operations():
    reg=AbilityEffectOperationRegistry()
    reg.validate("deal_damage")
    try:
        reg.validate("python_eval")
    except ValueError as exc:
        assert "Unknown" in str(exc)
    else:
        raise AssertionError("unsafe operation accepted")


def test_phase14a_dot_ticks_once_and_cleanse_removes(tmp_path):
    svc, hero, rat, db=service(tmp_path)
    rat.resources.health=20
    res=svc.execute_instant_ability("hero","venom","rat")
    assert res["ok"]
    first=svc.process_effect_ticks(1)
    assert first
    after=rat.resources.health
    assert after < 20
    assert svc.process_effect_ticks(1) == []
    cure=svc.execute_instant_ability("hero","cure_poison","rat")
    assert cure["ok"]
    assert svc.process_effect_ticks(2) == []


def test_phase14a_hot_and_materials_are_canonical(tmp_path):
    svc, hero, rat, db=service(tmp_path)
    hero.resources.health=10; hero.resources.maximum_health=20
    assert svc.execute_instant_ability("hero","regen","self")["ok"]
    svc.process_effect_ticks(1)
    assert hero.resources.health == 12
    with sqlite3.connect(db) as c:
        c.execute("CREATE TABLE IF NOT EXISTS item_instances(instance_id TEXT PRIMARY KEY,world_id TEXT,template_id TEXT,owner_type TEXT,owner_id TEXT,room_id TEXT,equipped_slot TEXT,stack_count INTEGER,condition TEXT,durability INTEGER,created_at TEXT,updated_at TEXT,custom_flags TEXT,plugin_data TEXT,destroyed_at TEXT,destroy_reason TEXT)")
        c.execute("INSERT INTO item_instances(instance_id,world_id,template_id,owner_type,owner_id,stack_count) VALUES('i1','test_world','ruby_dust','actor','hero',2)")
    out=svc.execute_instant_ability("hero","reagent_spell","self")
    assert out["ok"] and out["material_results"][0]["consumed"] == 2
    with sqlite3.connect(db) as c:
        row=c.execute("SELECT destroy_reason FROM item_instances WHERE instance_id='i1'").fetchone()
    assert row[0] == "ability_material"


def test_phase14a_npc_availability_uses_template_not_player_rows(tmp_path):
    svc, hero, rat, db=service(tmp_path)
    rat.plugin_data.setdefault("npc_ability_ids", []).append("ember")
    rows=svc.availability.resolve_actor_abilities("rat")
    assert any(r["ability"]["id"] == "ember" and r["source_type"] == "NPC template" for r in rows)
