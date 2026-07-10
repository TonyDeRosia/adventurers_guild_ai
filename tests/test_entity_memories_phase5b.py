from pathlib import Path
from engine.mud_runtime import MudRuntime

def test_memory_duplicate_prevention_and_query(tmp_path):
    rt=MudRuntime(Path('.'), tmp_path); rt.load_world('shattered_realms')
    eid=rt._fetch_entities('template_id=?',('blacksmith_harl',))[0]['instance_id']
    rt.record_entity_memory(eid,'interaction','A player greeted Harl.',subject_type='character',subject_id='char_a',source_event_type='entity_dialogue',source_event_id='evt1')
    rt.record_entity_memory(eid,'interaction','Duplicate.',subject_type='character',subject_id='char_a',source_event_type='entity_dialogue',source_event_id='evt1')
    assert len(rt.get_memories_about(eid,'character','char_a'))==1
