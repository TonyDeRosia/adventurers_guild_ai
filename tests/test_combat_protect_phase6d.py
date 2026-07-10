from engine.actors import Actor
from engine.combat_behavior import CombatBehaviorRegistry, CombatBehaviorService, ThreatService, init_combat_behavior_schema


def make_service():
    svc=CombatBehaviorService(world_id='test')
    npc=Actor.create('npc_1','Rat','npc'); pc=Actor.create('pc_1','Hero','player')
    npc.identity.current_location=pc.identity.current_location='room_1'
    npc.combat_profile['combat_behavior_profile_id']='rat_aggressive'
    svc.register_actor(npc); svc.register_actor(pc)
    return svc,npc,pc


def test_phase6d_profile_loading_and_validation():
    reg=CombatBehaviorRegistry()
    assert 'civilian_safe' in reg.profiles
    assert reg.validate()==[]


def test_phase6d_hostility_and_trace():
    svc,npc,pc=make_service()
    result=svc.hostility.evaluate_hostility(npc.actor_id, pc.actor_id)
    assert result['result']=='hostile'
    assert result['trace']


def test_phase6d_threat_highest_and_deterministic_tie():
    svc,npc,pc=make_service()
    svc.threat.add_threat(npc.actor_id, pc.actor_id, 5, 'damage')
    svc.threat.add_threat(npc.actor_id, 'pc_2', 5, 'damage')
    assert svc.threat.get_highest_threat_target(npc.actor_id)=='pc_1'
    assert len([r for r in svc.threat.get_actor_threat_table(npc.actor_id) if r['target_actor_id']=='pc_1'])==1


def test_phase6d_awareness_candidates_and_selection_are_deterministic():
    svc,npc,pc=make_service()
    assert svc.scan_actor_combat_awareness(npc.actor_id)['aware']
    a=svc.trace_combat_decision(npc.actor_id)
    b=svc.trace_combat_decision(npc.actor_id)
    assert a['selected_action']==b['selected_action']
    assert a['selected_action']['action_type']=='basic_attack'


def test_phase6d_civilian_safe_does_not_initiate():
    svc=CombatBehaviorService(world_id='test')
    civ=Actor.create('civ','Civilian','npc'); pc=Actor.create('pc','Hero','player')
    civ.identity.current_location=pc.identity.current_location='room_1'
    civ.combat_profile['combat_behavior_profile_id']='civilian_safe'
    svc.register_actor(civ); svc.register_actor(pc)
    assert svc.hostility.evaluate_hostility('civ','pc')['result']=='neutral'
    assert svc.select_combat_action('civ').action_type=='wait'


def test_phase6d_schema_initializes(tmp_path):
    db=tmp_path/'phase6d.sqlite'
    init_combat_behavior_schema(db)
    threat=ThreatService(db,'test')
    threat.add_threat('a','b',3,'damage')
    threat.add_threat('a','b',2,'healing')
    rows=threat.get_actor_threat_table('a')
    assert len(rows)==1 and rows[0]['threat_value']==5
