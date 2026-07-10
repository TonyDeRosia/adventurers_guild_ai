from engine.property import PropertyService

def test_home_set_clear(tmp_path):
    svc=PropertyService(tmp_path/'p.db', world_root='worlds/shattered_realms')
    p=svc.materialize_property('wayfarers_mug_room_1')['property_instance_id']; svc.grant_access('a',p,'a',['enter'])
    hid=svc.set_home('a',p)
    assert hid.startswith('home_')
    svc.clear_home('a')
