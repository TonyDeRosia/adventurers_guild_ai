from engine.organizations import OrganizationService

def test_phase8b_permission_default_deny_and_leader_grant(tmp_path):
    svc = OrganizationService(tmp_path / 'org.db')
    org = svc.create_party('leader')
    assert svc.has_permission('leader', org['organization_instance_id'], 'invite')
    assert not svc.has_permission('outsider', org['organization_instance_id'], 'invite')
