from pathlib import Path
from engine.mud_runtime import MudRuntime

def test_needs_decay_and_goal(tmp_path):
    rt=MudRuntime(Path('.'), tmp_path); rt.load_world('shattered_realms')
    eid=rt._fetch_entities('template_id=?',('blacksmith_harl',))[0]['instance_id']
    rt.living_world.advance_needs(eid,7000)
    assert any(n['current_value'] <= n['threshold_low'] for n in rt.living_world.list_needs(eid) if n['need_type']=='energy')
    assert any(g['goal_type']=='rest' for g in rt.list_entity_goals(eid))
