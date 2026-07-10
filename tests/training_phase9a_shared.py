from pathlib import Path
from engine.training import TrainingContent, TrainingService
from engine.mud_state_store import MUDStateStore as StateStore


def test_phase9a_training_content_loads_and_validates():
    content = TrainingContent('worlds/shattered_realms')
    assert content.get('trainer_definitions', 'training_master_borik')
    assert content.get('training_offer_definitions', 'learn_basic_attack_improvement')
    result = content.validate()
    assert result['errors'] == []


def test_phase9a_quote_immutable_and_duplicate_confirmation_safe(tmp_path):
    store = StateStore('phase9a', world_id='shattered_realms', db_path=tmp_path/'mud.db')
    service = TrainingService(store, world_root='worlds/shattered_realms')
    service.progression.initialize_actor_progression('hero', defaults={'practice_sessions': 2, 'training_sessions': 2, 'attribute_points': 2})
    quote = service.create_training_quote('hero', 'training_master_borik', 'learn_basic_attack_improvement')
    assert quote['costs']['practice_sessions'] == 1
    done = service.confirm_training('hero', quote['quote_id'])
    again = service.confirm_training('hero', quote['quote_id'])
    assert done['status'] == 'completed'
    assert again['idempotent'] is True
    assert service.progression.get_ability_rank('hero', 'basic_attack') == 1
    assert service.progression.get_actor_progression('hero')['practice_sessions'] == 1


def test_phase9a_attribute_profession_and_trace(tmp_path):
    store = StateStore('phase9a', world_id='shattered_realms', db_path=tmp_path/'mud.db')
    service = TrainingService(store, world_root='worlds/shattered_realms')
    service.progression.initialize_actor_progression('hero', defaults={'attribute_points': 1})
    q = service.create_training_quote('hero', 'training_master_borik', 'train_strength_once')
    tx = service.confirm_training('hero', q['quote_id'])
    trace = service.trace_training_transaction(tx['transaction_id'])
    assert trace['transaction']['status'] == 'completed'
    assert any(r['result_type'] == 'attribute_trained' for r in trace['results'])
    q2 = service.create_training_quote('hero', 'blacksmith_harl_profession_trainer', 'learn_blacksmith_profession')
    service.confirm_training('hero', q2['quote_id'])
    assert 'blacksmith' in service.progression.get_actor_progression('hero')['profession_ids']


def test_phase9a_conversion_cycle_rejected(tmp_path):
    root = tmp_path/'world'; (root/'advancement_conversion_profiles').mkdir(parents=True)
    (root/'advancement_conversion_profiles'/'advancement_conversion_profiles.json').write_text('{"advancement_conversion_profiles":{"a_to_b":{"id":"a_to_b","input_currency_id":"a","input_amount":1,"output_currency_id":"b","output_amount":1},"b_to_a":{"id":"b_to_a","input_currency_id":"b","input_amount":1,"output_currency_id":"a","output_amount":1}}}')
    content = TrainingContent(root)
    assert content.validate()['errors']
