from engine.organizations import OrganizationContent, OrganizationValidator

def test_phase8b_starter_organization_definitions_validate():
    content = OrganizationContent('worlds/shattered_realms')
    assert content.get('organization_definitions', 'starter_party')['organization_type'] == 'party'
    assert content.get('organization_definitions', 'town_guard')['persistent'] is True
    result = OrganizationValidator(content).validate_all()
    assert result.ok, result
