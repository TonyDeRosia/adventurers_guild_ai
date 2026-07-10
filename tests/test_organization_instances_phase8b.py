from engine.organizations import OrganizationService

def test_phase8b_create_persistent_instance_once(tmp_path):
    db = tmp_path / 'org.db'
    svc = OrganizationService(db)
    first = svc.create_organization('town_guard', 'guard_captain')
    second = OrganizationService(db).create_organization('town_guard', 'guard_captain')
    assert first['organization_instance_id'] == second['organization_instance_id']
    assert second['status'] == 'active'

def test_phase8b_disband_retains_history(tmp_path):
    svc = OrganizationService(tmp_path / 'org.db')
    org = svc.create_party('leader')
    svc.disband_organization('leader', org['organization_instance_id'])
    trace = svc.trace_organization(org['organization_instance_id'])
    assert trace['organization']['status'] == 'disbanded'
    assert any(a['operation'] == 'organization_disbanded' for a in trace['audit'])
