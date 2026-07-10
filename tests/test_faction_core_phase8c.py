from engine.factions import FactionService, FactionValidator, FactionContent


def test_faction_definitions_validate_and_link_to_organizations():
    content = FactionContent('worlds/shattered_realms')
    result = FactionValidator(content).validate_all()
    assert result.ok, result
    service = FactionService()
    assert service.get_faction('guildlands_town')['organization_definition_id'] == 'guildlands_town_council'
    assert service.get_organization_faction('town_guard')['id'] == 'town_guard_faction'
    trace = service.trace_faction_linkage('guildlands_town')
    assert trace['authoritative_identity'] == 'OrganizationService'


def test_reputation_lifecycle_history_and_idempotency():
    service = FactionService()
    rep = service.initialize_actor_reputation('hero', 'guildlands_town')
    assert rep['standing_tier_id'] == 'neutral'
    first = service.modify_reputation('hero', 'guildlands_town', 600, 'quest', 'cellar_rat_problem', 'quest complete', event_id='quest-event-1')
    second = service.modify_reputation('hero', 'guildlands_town', 600, 'quest', 'cellar_rat_problem', 'quest complete', event_id='quest-event-1')
    assert first['applied'] is True
    assert second['idempotent'] is True
    standing = service.resolve_standing('hero', 'guildlands_town')
    assert standing['standing_tier_id'] == 'friendly'
    assert len(service.get_reputation_history('hero', 'guildlands_town')) == 1


def test_caps_floors_set_reset_and_access():
    service = FactionService()
    service.modify_reputation('hero', 'guildlands_town', 99999, 'admin', 'cap-test')
    assert service.get_actor_reputation('hero', 'guildlands_town')['reputation_value'].startswith('3000')
    service.modify_reputation('hero', 'guildlands_town', -99999, 'admin', 'floor-test')
    assert service.get_actor_reputation('hero', 'guildlands_town')['reputation_value'].startswith('-3000')
    access = service.evaluate_faction_access('hero', 'guildlands_town', 'room_entry', {'type':'room','id':'guildhall_crossing_square'})
    assert access['result'] in {'warn', 'allow'}
    service.reset_reputation('hero', 'guildlands_town')
    assert service.resolve_standing('hero', 'guildlands_town')['standing_tier_id'] == 'neutral'


def test_diplomacy_relationships_are_directional_reciprocal_and_traceable():
    service = FactionService()
    assert service.get_faction_relationship('guildlands_town', 'town_guard_faction')['state'] == 'allied'
    service.set_faction_relationship('blacksmiths_circle_faction', 'healers_order_faction', 'friendly', reciprocal=False)
    assert service.get_faction_relationship('blacksmiths_circle_faction', 'healers_order_faction')['state'] == 'friendly'
    assert service.get_faction_relationship('healers_order_faction', 'blacksmiths_circle_faction')['state'] == 'neutral'
    trace = service.trace_faction_relationship('blacksmiths_circle_faction', 'healers_order_faction')
    assert trace['relationship']['state'] == 'friendly'


def test_rewards_and_context_foundations():
    service = FactionService()
    service.modify_reputation('hero', 'guildlands_town', 600, 'quest', 'reward-check')
    rewards = service.evaluate_reward_eligibility('hero', 'guildlands_town')
    assert any(r['id'] == 'friendly_recognition' and r['available'] for r in rewards)
    claim = service.claim_faction_reward('hero', 'guildlands_town', 'friendly_recognition')
    assert claim['reward']['id'] == 'friendly_recognition'
    assert not [r for r in service.evaluate_reward_eligibility('hero', 'guildlands_town') if r['id'] == 'friendly_recognition'][0]['available']
    ctx = service.get_actor_faction_context('hero')
    assert 'reputations' in ctx and 'access_tags' in ctx
