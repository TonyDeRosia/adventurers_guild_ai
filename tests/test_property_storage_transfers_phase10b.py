import sqlite3, json
from engine.property import PropertyService

def seed_item(db, iid, owner='actor', actor='a', equipped=''):
    with sqlite3.connect(db) as con:
        con.execute("CREATE TABLE IF NOT EXISTS item_instances(instance_id TEXT PRIMARY KEY,world_id TEXT,template_id TEXT,owner_type TEXT,owner_id TEXT,room_id TEXT,equipped_slot TEXT,stack_count INTEGER,condition TEXT,durability INTEGER,created_at TEXT,updated_at TEXT,custom_flags TEXT,plugin_data TEXT,destroyed_at TEXT,destroy_reason TEXT)")
        con.execute("INSERT INTO item_instances VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(iid,'shattered_realms','torch',owner,actor,'',equipped,1,'normal',100,'now','now',json.dumps({}),json.dumps({}),None,''))

def test_storage_transfer_capacity_and_no_duplication(tmp_path):
    db=tmp_path/'p.db'; svc=PropertyService(db, world_root='worlds/shattered_realms')
    p=svc.materialize_property('adventurers_guild_locker')['property_instance_id']; svc.grant_access('a',p,'a',['store','retrieve'])
    c=svc.get_storage_containers('a',p)[0]['storage_container_id']; seed_item(db,'item1')
    assert svc.store_item('a',c,'item1') is True
    with sqlite3.connect(db) as con: assert con.execute("SELECT owner_type,owner_id FROM item_instances WHERE instance_id='item1'").fetchone()==('property_storage',c)
    assert svc.retrieve_item('a',c,'item1') is True
    with sqlite3.connect(db) as con: assert con.execute("SELECT COUNT(*) FROM item_instances WHERE instance_id='item1'").fetchone()[0]==1

def test_equipped_item_rejected(tmp_path):
    db=tmp_path/'p.db'; svc=PropertyService(db, world_root='worlds/shattered_realms')
    p=svc.materialize_property('adventurers_guild_locker')['property_instance_id']; svc.grant_access('a',p,'a',['store'])
    c=svc.get_storage_containers('a',p)[0]['storage_container_id']; seed_item(db,'item2',equipped='wield')
    try: svc.store_item('a',c,'item2')
    except ValueError as e: assert 'equipped' in str(e)
    else: assert False
