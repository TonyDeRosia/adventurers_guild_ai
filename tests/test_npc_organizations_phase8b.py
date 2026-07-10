from engine.organizations import OrganizationService

def test_phase8b_foundation_smoke(tmp_path):
    svc = OrganizationService(tmp_path / 'org.db')
    org = svc.create_party('leader')
    assert svc.trace_organization(org['organization_instance_id'])['restart_state'] == 'sqlite-authoritative'
