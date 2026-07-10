from pathlib import Path
from engine.mud_runtime import MudRuntime

def test_starter_pilots_exist_once_with_profiles(tmp_path):
    rt=MudRuntime(Path('.'), tmp_path); rt.load_world('shattered_realms')
    for tid in ['blacksmith_harl','training_master_borik','apprentice_mage_lina','healer_sella','tavern_keeper_jory']:
        ents=rt._fetch_entities('template_id=?',(tid,)); assert len(ents)==1
        prof=rt.get_entity_profile(ents[0]['instance_id']); assert prof['identity']['personal_name']
        assert rt.evaluate_entity_schedule(ents[0]['instance_id'])['schedule_id']=='starter_day_worker'
