from pathlib import Path
from engine.mud_runtime import MudRuntime

def test_world_clock_manual_and_persistent(tmp_path):
    rt=MudRuntime(Path('.'), tmp_path); rt.load_world('shattered_realms')
    assert rt.get_world_time('shattered_realms')['hour']==6
    rt.set_world_time('shattered_realms',2,'07:50')
    assert rt.advance_world_time('shattered_realms',20)['hour']==8
    rt.pause_world_time('shattered_realms'); assert rt.get_world_time('shattered_realms')['paused'] is True
    rt2=MudRuntime(Path('.'), tmp_path); rt2.load_world('shattered_realms')
    assert rt2.get_world_time('shattered_realms')['day']==2
