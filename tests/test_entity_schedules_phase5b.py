from pathlib import Path
from engine.mud_runtime import MudRuntime

def test_schedule_eval_and_path(tmp_path):
    rt=MudRuntime(Path('.'), tmp_path); rt.load_world('shattered_realms')
    eid=rt._fetch_entities('template_id=?',('blacksmith_harl',))[0]['instance_id']
    rt.set_world_time('shattered_realms',1,'07:00')
    ev=rt.evaluate_entity_schedule(eid)
    assert ev['activity']=='working' and ev['target_room_id']=='blacksmith_stall'
    assert rt.find_room_path('tavern_common_room','blacksmith_stall')['path']==['tavern_common_room','market_lane','blacksmith_stall']
