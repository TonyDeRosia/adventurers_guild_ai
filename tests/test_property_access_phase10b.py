from engine.property import PropertyService

def test_access_owner_guest_revoked(tmp_path):
    svc=PropertyService(tmp_path/'p.db', world_root='worlds/shattered_realms')
    p=svc.materialize_property('wayfarers_mug_room_1')['property_instance_id']
    assert not svc.evaluate_property_access('a',p,'enter')['allowed']
    svc.grant_access('owner',p,'guest',['enter'])
    assert svc.evaluate_property_access('guest',p,'enter')['allowed']
    svc.revoke_access('owner',p,'guest')
    assert not svc.evaluate_property_access('guest',p,'enter')['allowed']
