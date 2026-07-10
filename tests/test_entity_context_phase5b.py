from pathlib import Path
from engine.mud_runtime import MudRuntime

def test_context_no_ai_and_visible_only(tmp_path):
    rt=MudRuntime(Path('.'), tmp_path); rt.load_world('shattered_realms')
    eid=rt._fetch_entities('template_id=?',('blacksmith_harl',))[0]['instance_id']
    ctx=rt.get_entity_context(eid)
    assert 'profile' in ctx and 'private player inventory' in str(ctx['knowledge_boundaries']).lower()
    assert all(e['instance_id']!=eid for e in ctx['visible_entity_instances'])
