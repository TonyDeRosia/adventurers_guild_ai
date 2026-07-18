import sqlite3

from engine.command_registry import CommandRegistry
from engine.mud_commands import MudCommandEngine
from engine.abilities import AbilityExecutionService, init_ability_schema
from engine.actors import Actor
from smart_mud.world_registry import WorldRegistry


class Bus:
    def __init__(self): self.events=[]
    def subscribe(self,*a,**k): pass
    def publish(self, name, payload, **kwargs): self.events.append((name,payload,kwargs))


def service(tmp_path):
    bus=Bus(); db=tmp_path/'mud.db'; init_ability_schema(db)
    svc=AbilityExecutionService(db, WorldRegistry().load_world('shattered_realms'), event_bus=bus, world_id='shattered_realms', allow_isolated_combat_engine=True)
    hero=Actor.create('hero','Hero','player'); hero.name='Hero'; hero.id='hero'; gob=Actor.create('goblin','Goblin','mob'); ally=Actor.create('ally','Anthor Ally','player')
    for a in (hero,gob,ally): a.identity.current_location='room1'; svc.register_actor(a)
    for aid in ['kick','bash','bandage','magic_missile','armor','bless','strength']:
        svc.grant_ability('hero', aid, 'test')
    return svc, hero, gob, ally, bus


def test_phase18g_command_minimum_abbreviations_are_stable():
    r=CommandRegistry()
    assert r.resolve('cast') == ('cast','exact')
    assert r.resolve('c')[0] == 'cast'
    assert r.resolve('ki')[0] == 'kick'
    assert r.resolve('bas')[0] == 'bash'
    assert r.resolve('band')[0] == 'bandage'
    assert r.resolve('k')[1] == 'unknown'
    assert r.resolve('l')[0] == 'look'
    # Does not pick by insertion order.
    r.register(r.commands['cast'].__class__(command='campaign', min_abbrev='ca', category='system'))
    assert r.resolve('ca')[1].startswith('ambiguous')


def test_phase18g_spell_token_resolver_quotes_case_and_target_boundary(tmp_path):
    svc, hero, gob, ally, bus = service(tmp_path); gw=svc.gateway()
    for text in ['magic missile goblin', "'magic missile' goblin", '"magic missile" goblin', 'magic goblin', 'mag mis gob', 'MAGIC MISSILE GOBLIN']:
        res=gw.resolve_spell_tokens('hero', text)
        assert res['status'] == 'RESOLVED', text
        assert res['ability_id'] == 'magic_missile'
        assert res['target_text'].startswith('gob')
    assert gw.resolve_spell_tokens('hero', 'kick goblin')['status'] == 'UNKNOWN_ABILITY'


def test_phase18g_direct_and_cast_commands_reach_gateway_with_target_prefix(tmp_path):
    svc, hero, gob, ally, bus = service(tmp_path)
    eng=MudCommandEngine(event_bus=bus); eng.ability_service=svc
    before_mana=hero.resources.mana; before_hp=gob.resources.health
    out=eng.handle_command(hero, 'c magic gob')
    assert out.ok and 'Magic Missile' in out.narrative
    assert hero.resources.mana < before_mana and gob.resources.health < before_hp
    svc._world_time = svc.world_time() + 5
    before_stam=hero.resources.stamina; before_hp=gob.resources.health
    out=eng.handle_command(hero, 'ki gob')
    assert out.ok and 'kick' in out.narrative.lower()
    assert hero.resources.stamina < before_stam and gob.resources.health < before_hp
    svc._world_time = svc.world_time() + 5
    assert eng.handle_command(hero, 'bas gob').ok
    svc._world_time = svc.world_time() + 5
    hero.resources.health=40
    out=eng.handle_command(hero, 'band ally')
    assert out.ok or 'self' not in out.narrative.lower()


def test_phase18g_ambiguous_target_spends_no_mana(tmp_path):
    svc, hero, gob, ally, bus = service(tmp_path)
    goblin2=Actor.create('goblin_guard','Goblin Guard','mob'); goblin2.identity.current_location='room1'; svc.register_actor(goblin2)
    before=hero.resources.mana
    res=svc.gateway().execute_result('hero', 'magic missile', 'gob', {'command':'c magic gob'})
    assert res.status == 'INVALID_TARGET'
    assert hero.resources.mana == before


def test_phase18k_magic_missile_no_target_uses_current_opponent_not_self(tmp_path):
    svc, hero, gob, ally, bus = service(tmp_path)
    hero.plugin_data['current_combat_target'] = 'goblin'
    before_hero = hero.resources.health
    before_gob = gob.resources.health
    out = svc.execute_instant_ability('hero', 'magic_missile')
    assert out['ok']
    assert gob.resources.health < before_gob
    assert hero.resources.health == before_hero
    hero.plugin_data.pop('current_combat_target')
    res = svc.validate_ability_use('hero', 'magic_missile')
    assert not res['ok']
    assert res['message'] == 'No current opponent.'
