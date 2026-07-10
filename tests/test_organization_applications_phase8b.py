from engine.organizations import OrganizationService

def test_phase8b_application_approve(tmp_path):
    svc = OrganizationService(tmp_path / 'org.db')
    org = svc.create_organization('adventurers_guild_placeholder', 'leader')
    app = svc.apply_to_organization('applicant', org['organization_instance_id'], 'hello')
    svc.approve_application('leader', app['application_id'])
    assert any(m['actor_id'] == 'applicant' for m in svc.get_members(org['organization_instance_id'], 'active'))
