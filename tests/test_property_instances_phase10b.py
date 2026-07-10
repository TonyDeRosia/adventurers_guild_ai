from engine.property import PropertyService

def test_property_instance_restart_persistence(tmp_path):
    db=tmp_path/'p.db'; svc=PropertyService(db, world_root='worlds/shattered_realms')
    inst=svc.materialize_property('wayfarers_mug_room_1')
    assert inst['status']=='available'
    assert PropertyService(db, world_root='worlds/shattered_realms').get_property_instance(inst['property_instance_id'])['name']=='Wayfarers Mug Room 1'
