from engine.organizations import OrganizationService
import pytest

def test_phase8b_invite_accept_decline_duplicate(tmp_path):
    svc = OrganizationService(tmp_path / 'org.db')
    org = svc.create_party('leader')
    inv = svc.invite_actor(org['organization_instance_id'], 'leader', 'member')
    with pytest.raises(Exception):
        svc.invite_actor(org['organization_instance_id'], 'leader', 'member')
    svc.accept_invitation('member', inv['invitation_id'])
    assert any(m['actor_id'] == 'member' for m in svc.get_members(org['organization_instance_id'], 'active'))
