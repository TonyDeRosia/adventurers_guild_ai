from engine.property import PropertyService

def test_process_time_expires_lease_and_key_grants_once(tmp_path):
    svc=PropertyService(tmp_path/'p.db', world_root='worlds/shattered_realms')
    p=svc.materialize_property('wayfarers_mug_room_1')['property_instance_id']
    svc.grant_access('a',p,'a',['enter'],grant_type='tenant')
    import sqlite3
    with sqlite3.connect(tmp_path/'p.db') as con:
        con.execute("INSERT INTO property_leases VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",('l1','shattered_realms',p,'actor','a','system','property','active',0,5,5,5,'','',0,'n','n','{}'))
    assert svc.process_property_time('shattered_realms',6)==['l1']
    assert svc.process_property_time('shattered_realms',7)==[]
    assert not svc.evaluate_property_access('a',p,'enter',world_time=7)['allowed']
