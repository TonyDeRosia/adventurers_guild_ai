from engine.organizations import OrganizationService

def test_phase8b_share_quest_offer_to_party(tmp_path):
    svc = OrganizationService(tmp_path / 'org.db')
    org = svc.create_party('leader')
    svc.add_member(org['organization_instance_id'], 'member')
    offers = svc.share_quest_offer(org['organization_instance_id'], 'leader', 'cellar_rat_problem')
    assert offers and offers[0]['recipient_actor_id'] == 'member'
