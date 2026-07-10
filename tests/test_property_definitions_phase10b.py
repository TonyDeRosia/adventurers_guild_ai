from engine.property import PropertyContent

def test_property_definitions_and_profiles_validate():
    c=PropertyContent('worlds/shattered_realms')
    assert c.get('property_definitions','wayfarers_mug_room_1')['property_type']=='inn_room'
    result=c.validate()
    assert result['errors']==[]
    assert 'standard_property_access' in c.data['property_access_profiles']
