from engine.progression import ProgressionContent

def test_phase6e_content_smoke():
    c=ProgressionContent('worlds/shattered_realms')
    assert 'species_profiles' in c.data
    assert c.validate()['errors'] == []
