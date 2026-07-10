from pathlib import Path
from smart_mud.builder import BuilderWorkspace, DRAFT_FILES

def test_builder_collections_include_living_files(tmp_path):
    b=BuilderWorkspace(worlds_dir=tmp_path); root=b.ensure('shattered_realms')
    assert 'schedules' in DRAFT_FILES and (root/'schedules.json').exists()
