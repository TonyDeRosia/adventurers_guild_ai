from types import SimpleNamespace
from smart_mud.builder import BuilderWorkspace, DRAFT_FILES


def actor(): return SimpleNamespace(id='builder',account_id='acct',role='builder',world_id='shattered_realms')

def test_builder_has_gathering_collections_and_round_trip(tmp_path):
    bw=BuilderWorkspace(worlds_dir=tmp_path); root=bw.ensure('shattered_realms')
    assert 'resource_definitions' in DRAFT_FILES and (root/DRAFT_FILES['resource_definitions']).exists()
    drafts=bw.load('shattered_realms')
    drafts['resource_definitions']['test_resource']={'id':'test_resource','name':'Test Resource','resource_type':'custom','rarity':0,'enabled':True}
    bw.save_drafts('shattered_realms', drafts)
    result=bw.export(actor())
    assert result.ok
