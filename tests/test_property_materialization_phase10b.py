from engine.property import PropertyService

def test_materialize_once_no_duplicate(tmp_path):
    svc=PropertyService(tmp_path/'p.db', world_root='worlds/shattered_realms')
    a=svc.materialize_property('wayfarers_mug_room_1'); b=svc.materialize_property('wayfarers_mug_room_1')
    assert a['property_instance_id']==b['property_instance_id']
    assert len(svc.list_available_properties())==1
