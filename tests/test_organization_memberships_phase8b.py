from engine.organizations import OrganizationService
import pytest

def test_phase8b_membership_history_and_one_party_limit(tmp_path):
    svc = OrganizationService(tmp_path / 'org.db')
    party = svc.create_party('leader')
    svc.add_member(party['organization_instance_id'], 'member')
    with pytest.raises(ValueError):
        svc.create_party('member')
    svc.leave_organization('member', party['organization_instance_id'])
    rows = svc.get_members(party['organization_instance_id'])
    assert any(r['actor_id'] == 'member' and r['status'] == 'left' for r in rows)
