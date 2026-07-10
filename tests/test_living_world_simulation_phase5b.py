from pathlib import Path
from engine.mud_runtime import MudRuntime

def test_simulation_tick_persists_state(tmp_path):
    rt=MudRuntime(Path('.'), tmp_path); rt.load_world('shattered_realms')
    eid=rt._fetch_entities('template_id=?',('training_master_borik',))[0]['instance_id']
    rt.set_world_time('shattered_realms',1,'18:10'); rt.simulate_world('shattered_realms',1)
    assert rt.find_entity(eid)['room_id'] in {'training_yard','guildhall_crossing_square'}
