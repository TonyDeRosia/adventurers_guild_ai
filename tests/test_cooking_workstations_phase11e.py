from tests.test_cooking_phase11e_common import cook_fish_flow

def test_phase11e_canonical_cooking_flow(tmp_path):
    trace = cook_fish_flow(tmp_path)
    assert trace['recipe']['recipe_category'] == 'cooking'
