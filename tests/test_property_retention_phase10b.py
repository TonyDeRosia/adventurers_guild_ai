from engine.property import PropertyContent, PropertyService

def test_phase10b_foundation_smoke(tmp_path):
    content=PropertyContent('worlds/shattered_realms')
    assert content.validate()['errors']==[]
    svc=PropertyService(tmp_path/'p.db', world_root='worlds/shattered_realms')
    inst=svc.materialize_property('wayfarers_mug_room_1')
    assert svc.trace_property(inst['property_instance_id'])['definition']['id']=='wayfarers_mug_room_1'
