from types import SimpleNamespace
from smart_mud.event_bus import EventBus
from engine.schedules import ScheduleService

class Runtime:
    def __init__(self, db):
        self.active_world_id='test_world'; self.state_store=SimpleNamespace(db_path=db); self.event_bus=EventBus()
        self.active_world=SimpleNamespace(schedules=[{"id":"daily","entries":[
            {"id":"sleep","start_time":"22:00","end_time":"06:00","activity":"sleep","target_ref":"home","priority":1},
            {"id":"work","start_time":"06:00","end_time":"18:00","activity":"work","target_ref":"workplace","priority":1},
            {"id":"gate","start_time":"18:00","end_time":"22:00","activity":"stand guard","target_ref":"workplace","priority":2}],"location_refs":{"home":"home","workplace":"gate"},"fallback":{"id":"fb","activity":"idle"}}])
        self.entities={'npc':{'instance_id':'npc','room_id':'home','state':{'schedule_id':'daily'},'plugin_data':{}}}
        self.moves=[]
    def find_entity(self,eid): return self.entities.get(eid)
    def get_world_time(self, world_id): return {'world_id':world_id,'day':1,'hour':7,'minute':0}
    def find_room_path(self,start,target): return {'ok':True,'path':[start,'road',target]}
    def move_entity(self,eid,room_id,source_system='runtime',**ctx):
        self.moves.append((eid,room_id,source_system,ctx)); self.entities[eid]['room_id']=room_id; self.event_bus.publish('entity_moved', {'entity_id':eid,'room_id':room_id}, source_system=source_system); return self.entities[eid]

def test_schedule_loading_validation_and_selection(tmp_path):
    rt=Runtime(tmp_path/'s.sqlite'); svc=ScheduleService(rt)
    assert svc.validate_all()['ok'] is True
    sel=svc.select_activity('npc', {'world_id':'test_world','day':1,'hour':23,'minute':0})
    assert sel['entry_id']=='sleep'; assert sel['activity']=='sleep'; assert sel['target_room_id']=='home'; assert sel['dispatch_service']=='survival_needs'

def test_activity_transition_travel_eventbus_and_history(tmp_path):
    rt=Runtime(tmp_path/'s.sqlite'); svc=ScheduleService(rt)
    out=svc.apply('npc', {'world_id':'test_world','day':1,'hour':19,'minute':0})
    assert out['activity']=='stand_guard'; assert out['to_room_id']=='road'; assert rt.moves[0][2]=='schedule'
    names=[e.event_name for e in rt.event_bus.event_history()]
    assert 'entity_moved' in names and 'schedule_activity_selected' in names
    assert svc.history('npc')[0]['transition']=='transition'

def test_restart_persistence_interrupt_resume_and_world_time(tmp_path):
    db=tmp_path/'s.sqlite'; rt=Runtime(db); svc=ScheduleService(rt)
    svc.apply('npc', {'world_id':'test_world','day':3,'hour':7,'minute':30})
    restarted=ScheduleService(rt)
    state=restarted.runtime_state('npc')
    assert state['current_entry_id']=='work'; assert state['last_world_day']==3; assert state['last_world_minute']==450
    assert restarted.interrupt('npc','combat')['status']=='interrupted'
    assert restarted.resume('npc')['status']=='active'

def test_builder_style_validation_rejects_bad_activity(tmp_path):
    rt=Runtime(tmp_path/'s.sqlite'); rt.active_world.schedules=[{'id':'bad','entries':[{'id':'x','start_time':'25:00','end_time':'26:00','activity':'duplicate_ai'}]}]
    result=ScheduleService(rt).validate_all()
    assert result['ok'] is False
    assert any('unsupported activity' in e for e in result['errors'])
