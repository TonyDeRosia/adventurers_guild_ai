from pathlib import Path
from engine.mud_runtime import MudRuntime

def test_goal_selection_stable(tmp_path):
    rt=MudRuntime(Path('.'), tmp_path); rt.load_world('shattered_realms')
    eid=rt._fetch_entities('template_id=?',('blacksmith_harl',))[0]['instance_id']
    rt.create_entity_goal(eid,'idle','Idle','builder',priority=1)
    rt.create_entity_goal(eid,'work','Work','builder',priority=90)
    assert rt.select_deterministic_goal(eid)['goal_type']=='work'
