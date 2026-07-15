import sqlite3
from pathlib import Path

from engine.gathering import GatheringService
from engine.quests import ConversationService, QuestContent, QuestEventRouter, QuestService, QuestValidator
from engine.rewards import RewardService, init_reward_schema

WORLD = Path('worlds/shattered_realms')

class Store:
    world_id = 'shattered_realms'
    def __init__(self, db): self.db_path = db
    def create_item_instance(self, iid, template_id, current_owner='', flags=None, creator=''):
        with sqlite3.connect(self.db_path) as con:
            con.execute('CREATE TABLE IF NOT EXISTS item_instances(unique_id TEXT PRIMARY KEY, template_id TEXT, current_owner TEXT, flags_json TEXT)')
            con.execute('INSERT OR IGNORE INTO item_instances VALUES(?,?,?,?)',(iid,template_id,current_owner,','.join(flags or [])))
        return {'instance_id': iid}

def services(tmp_path):
    db=tmp_path/'starter.db'; init_reward_schema(db); store=Store(db)
    rewards=RewardService(store=store, db_path=db, world_id='shattered_realms')
    qs=QuestService(db, WORLD, reward_service=rewards)
    gs=GatheringService(db, WORLD)
    return db, qs, gs

def test_starter_content_validates_and_references_existing_resource():
    content=QuestContent(WORLD)
    result=QuestValidator(content).validate_all()
    assert result.ok, result
    q=content.get('quest_definitions','guildlands_emberleaf_errand')
    assert q['offer_sources'][0]['source_id']=='guild_registrar_maren'
    obj=content.get('quest_objectives','guildlands_emberleaf_gather_one')
    assert obj['objective_type']=='harvest_resource'
    assert obj['target_definition']['item_template_id']=='emberleaf'
    assert content.get('conversation_definitions','maren_emberleaf_errand')

def test_fresh_actor_accepts_gathers_eventbus_progress_persists_and_turns_in_once(tmp_path):
    db, qs, gs = services(tmp_path); actor='fresh_recruit'
    assert qs.evaluate_quest_availability(actor,'guildlands_next_steps')['available'] is False
    conv=ConversationService(qs)
    start=conv.start_conversation(actor,'maren_emberleaf_errand','guild_registrar_maren')
    assert 'first field errand' in start['node']['text']
    offer=conv.choose(start['conversation_session_id'],1)
    assert 'Bring me one emberleaf' in offer['node']['text']
    accepted=conv.choose(start['conversation_session_id'],1)
    assert 'Gather the emberleaf' in accepted['node']['text']
    inst=qs.get_actor_quests(actor)[0]
    assert inst['quest_id']=='guildlands_emberleaf_errand'
    qs2=QuestService(db, WORLD)
    assert qs2.get_actor_quests(actor)[0]['status']=='active'
    node=gs.materialize_node('emberleaf_patch_crossing','guildhall_crossing_square')
    result=gs.gather_mode('harvest', actor, 'guildhall_crossing_square', 'emberleaf', 'training_sword', world_time=5)
    assert result['ok'] and result['item_template_id']=='emberleaf'
    routed=QuestEventRouter(qs).handle_event({'event_type':'resource_gathered','event_id':'gather-event-1', **result})
    assert routed['matched']==1
    assert QuestEventRouter(qs).handle_event({'event_type':'resource_gathered','event_id':'gather-event-1', **result})['matched']==0
    ready=qs.get_actor_quests(actor)[0]
    assert ready['status']=='ready_to_turn_in'
    journal=qs.get_quest_journal(actor)[0]
    assert journal['ready_to_turn_in'] is True
    assert journal['objectives'][0]['progress_current']==result['quantity']
    turned=qs.turn_in_quest(actor, ready['quest_instance_id'], {'source_type':'test'})
    assert turned['status']=='completed'
    packet_count=lambda: sqlite3.connect(db).execute('select count(*) from reward_packets').fetchone()[0]
    assert packet_count()==1
    qs.turn_in_quest(actor, ready['quest_instance_id'], {'source_type':'test'})
    assert packet_count()==1
    assert qs.evaluate_quest_availability(actor,'guildlands_next_steps')['available'] is True
    assert QuestService(db, WORLD).get_actor_quests(actor, 'completed')[0]['quest_id']=='guildlands_emberleaf_errand'

def test_insufficient_turnin_rejected_and_decline_branch(tmp_path):
    _, qs, _ = services(tmp_path); actor='decliner'
    conv=ConversationService(qs); start=conv.start_conversation(actor,'maren_emberleaf_errand','guild_registrar_maren')
    conv.choose(start['conversation_session_id'],1)
    decline=conv.choose(start['conversation_session_id'],2)
    assert decline['node']['id']=='maren_emberleaf_decline'
    inst=qs.accept_quest(actor,'guildlands_emberleaf_errand')
    try:
        qs.turn_in_quest(actor, inst['quest_instance_id'])
    except ValueError as exc:
        assert 'not ready' in str(exc)
    else:
        raise AssertionError('turn-in should reject insufficient progress')


def test_starter_combat_content_builder_owned_and_world_loaded():
    content=QuestContent(WORLD)
    result=QuestValidator(content).validate_all()
    assert result.ok, result
    q=content.get('quest_definitions','guildlands_wolf_pelts')
    assert q['availability_profile_id']=='after_emberleaf_errand'
    assert q['reward_definition_id']=='guildlands_wolf_pelts_reward'
    kill=content.get('quest_objectives','guildlands_wolf_pelts_kill_one')
    pelt=content.get('quest_objectives','guildlands_wolf_pelts_obtain_pelt')
    assert kill['objective_type']=='kill_template'
    assert kill['target_definition']['actor_template_id']=='forest_wolf'
    assert pelt['target_definition']['item_template_id']=='wolf_pelt'
    npcs=json_load(WORLD/'npcs/npcs.json')
    wolf=[n for n in npcs if n['id']=='forest_wolf'][0]
    assert wolf['combat_behavior_profile_id']=='wolf_pack'
    assert wolf['ability_loadout_id']=='wolf_basic'
    assert wolf['death_loot_profile_id']=='starter_wolf_death_loot'
    rooms=json_load(WORLD/'rooms/rooms.json')
    trail=[r for r in rooms if r['id']=='emberwood_hunting_trail'][0]
    assert 'forest_wolf' in trail['npcs']
    assert trail['exits'][0]['destination_room_id']=='old_gate_road'


def test_combat_eventbus_kill_pelt_progress_duplicate_protection_and_restart(tmp_path):
    db, qs, _ = services(tmp_path); actor='wolf_recruit'
    # prerequisite completed through canonical quest state, not custom flags
    ember=qs.accept_quest(actor,'guildlands_emberleaf_errand')
    qs.process_quest_event({'event_type':'resource_gathered','event_id':'ember-1','actor_id':actor,'item_template_id':'emberleaf','quantity':1})
    qs.turn_in_quest(actor, ember['quest_instance_id'])
    inst=qs.accept_quest(actor,'guildlands_wolf_pelts')
    router=QuestEventRouter(qs)
    kill={'event_type':'enemy_killed','event_id':'wolf-kill-1','actor_id':actor,'target_actor_id':'forest_wolf_spawn_1','target_actor_template_id':'forest_wolf','target_actor_tags':['wolf','starter'], 'world_time':10}
    assert router.handle_event(kill)['matched']==1
    assert router.handle_event(kill)['matched']==0
    pelt={'event_type':'quest_item_obtained','event_id':'wolf-pelt-1','actor_id':actor,'item_template_id':'wolf_pelt','item_instance_id':'pelt-instance-1','quantity':1,'corpse_id':'corpse_wolf_1','world_time':11}
    assert router.handle_event(pelt)['matched']==1
    ready=[q for q in QuestService(db, WORLD).get_actor_quests(actor) if q['quest_id']=='guildlands_wolf_pelts'][0]
    assert ready['quest_id']=='guildlands_wolf_pelts'
    assert ready['status']=='ready_to_turn_in'
    trace=QuestService(db, WORLD).trace_quest(inst['quest_instance_id'])
    assert len(trace['consumed_events'])==2


def test_starter_wolf_loot_rewardservice_and_corpse_persistence(tmp_path):
    from engine.mud_state_store import MUDStateStore
    rewards=RewardService(db_path=tmp_path/'loot.db')
    packet=rewards.resolve_loot_table('wolf_common_loot', {'source_type':'corpse','source_id':'forest_wolf','source_instance_id':'spawn_emberwood_forest_wolf'}, {'recipient_type':'corpse','recipient_id':'corpse_wolf_1'}, seed='starter-wolf')
    entries={e['definition_id'] for e in packet['resolved_entries']}
    assert {'wolf_pelt','torn_hide','copper'} <= entries
    store=MUDStateStore('camp','shattered_realms', db_path=tmp_path/'state.db')
    store.create_corpse('corpse_wolf_1','emberwood_hunting_trail',owner='forest_wolf',gold=2,decay_seconds=1800,items=['wolf_pelt'])
    reloaded=MUDStateStore('camp','shattered_realms', db_path=tmp_path/'state.db')
    corpses=reloaded.load_persistent_corpses('emberwood_hunting_trail')
    assert corpses[0]['corpse_id']=='corpse_wolf_1'
    assert corpses[0]['items']==['wolf_pelt']


def test_eventbus_aliases_for_corpse_looted_and_item_collected(tmp_path):
    db, qs, _ = services(tmp_path); actor='alias_recruit'
    ember=qs.accept_quest(actor,'guildlands_emberleaf_errand')
    qs.process_quest_event({'event_type':'resource_gathered','event_id':'ember-alias','actor_id':actor,'item_template_id':'emberleaf','quantity':1})
    qs.turn_in_quest(actor, ember['quest_instance_id'])
    qs.accept_quest(actor,'guildlands_wolf_pelts')
    assert QuestEventRouter(qs).handle_event({'event_type':'item_collected','event_id':'item-1','actor_id':actor,'item_template_id':'wolf_pelt','quantity':1})['matched']==1
    # corpse_looted routes through the same collect-item objective family and remains idempotent per event id.
    assert QuestEventRouter(qs).handle_event({'event_type':'corpse_looted','event_id':'corpse-loot-1','actor_id':actor,'item_template_id':'wolf_pelt','quantity':1,'corpse_id':'corpse_wolf_1'})['matched']==1


def json_load(path):
    import json
    return json.loads(Path(path).read_text())
