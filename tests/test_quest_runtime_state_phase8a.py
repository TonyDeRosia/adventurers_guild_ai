from engine.quests import QuestService

def test_offer_accept_progress_idempotent_complete(tmp_path):
    svc=QuestService(tmp_path/'q.db', 'worlds/shattered_realms')
    actor='actor1'
    assert svc.offer_quest(actor,'cellar_rat_problem')['status']=='offered'
    inst=svc.accept_quest(actor,'cellar_rat_problem')
    iid=inst['quest_instance_id']
    svc.process_quest_event({'event_type':'conversation_completed','event_id':'e1','actor_id':actor,'custom_target_id':'jory_rat_problem'})
    assert svc.get_quest_instance(iid)['current_stage_id']=='cellar_rat_problem_kill'
    ev={'event_type':'actor_killed','event_id':'rat1','actor_id':actor,'target_actor_id':'rat-inst-1','target_actor_tags':['cellar_rat']}
    assert svc.process_quest_event(ev)['matched']==1
    assert svc.process_quest_event(ev)['matched']==0
    svc.process_quest_event({'event_type':'actor_killed','event_id':'rat2','actor_id':actor,'target_actor_id':'rat-inst-2','target_actor_tags':['cellar_rat']})
    svc.process_quest_event({'event_type':'actor_killed','event_id':'rat3','actor_id':actor,'target_actor_id':'rat-inst-3','target_actor_tags':['cellar_rat']})
    assert svc.get_quest_instance(iid)['current_stage_id']=='cellar_rat_problem_return'
    assert svc.trace_quest(iid)['consumed_events']
