from types import SimpleNamespace
import json
from smart_mud.builder import BuilderWorkspace


def actor(): return SimpleNamespace(id='builder',account_id='acct',role='builder',world_id='shattered_realms')

def test_gathering_import_preview_apply_export(tmp_path):
    bw=BuilderWorkspace(worlds_dir=tmp_path); root=bw.ensure('shattered_realms')
    bundle={'resource_definitions':{'imported_resource':{'id':'imported_resource','name':'Imported Resource','resource_type':'custom','rarity':0,'enabled':True}}}
    (root/'imports'/'gathering.json').write_text(json.dumps(bundle),encoding='utf-8')
    assert bw.import_validate(actor(),'gathering.json').ok
    assert 'Resource definitions to add/update' in bw.import_preview(actor(),'gathering.json').message
    assert bw.import_apply(actor(),'gathering.json').ok
    assert bw.export(actor()).ok
