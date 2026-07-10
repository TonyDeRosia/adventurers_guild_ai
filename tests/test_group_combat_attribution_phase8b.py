from engine.organizations import OrganizationService

def test_phase8b_group_combat_contribution_accumulates(tmp_path):
    svc = OrganizationService(tmp_path / 'org.db')
    org = svc.create_party('leader')
    svc.record_group_combat_participation(org['organization_instance_id'], 'combat1', 'leader', 'rat', damage=3)
    rows = svc.record_group_combat_participation(org['organization_instance_id'], 'combat1', 'leader', 'rat', damage=2, healing=1)
    row = rows[0]
    assert row['damage_contribution'] == 5
    assert row['healing_contribution'] == 1
