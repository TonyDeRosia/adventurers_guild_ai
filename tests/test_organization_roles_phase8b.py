from engine.organizations import OrganizationContent, OrganizationValidator

def test_phase8b_roles_permissions_and_inheritance():
    c = OrganizationContent('worlds/shattered_realms')
    leader = c.get('organization_roles', 'party_leader')
    assert 'invite' in leader['permissions']
    assert 'party_member' in leader['inherits_from_role_ids']
    assert OrganizationValidator(c).validate_role('party_leader').ok
