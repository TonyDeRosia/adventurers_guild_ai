from engine.rewards import RewardContent


def test_phase7a_content_loads_and_validates():
    content = RewardContent("worlds/shattered_realms")
    assert content.list("reward_definitions")
    assert isinstance(content.validate(), dict)
