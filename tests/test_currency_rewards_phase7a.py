from engine.rewards import CurrencyService


def test_currency_award_idempotent_and_nonnegative(tmp_path):
    c = CurrencyService(tmp_path/"r.db")
    src = {"reward_packet_id":"p","reward_entry_id":"e"}
    c.award_currency("actor","copper",3,src)
    c.award_currency("actor","copper",3,src)
    assert c.get_currency_balance("actor","copper") == 3
    try:
        c.award_currency("actor","copper",-1,{})
    except ValueError:
        pass
    else:
        raise AssertionError("negative currency accepted")
