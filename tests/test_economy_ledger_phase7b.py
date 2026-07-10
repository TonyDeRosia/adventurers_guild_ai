from engine.economy import EconomyContent, EconomyService, init_economy_schema


def test_phase7b_currency_credit_debit_transfer_and_ledger(tmp_path):
    db=tmp_path/'mud.sqlite3'; svc=EconomyService(db, world_root='worlds/shattered_realms')
    assert svc.get_currency_balance('actor','a','gold') == 0
    svc.credit_currency('actor','a','gold',100, reason='test')
    svc.debit_currency('actor','a','gold',30, reason='test')
    svc.transfer_currency('actor','a','shop','blacksmith_shop','gold',20)
    assert svc.get_currency_balance('actor','a','gold') == 50
    assert svc.get_currency_balance('shop','blacksmith_shop','gold') == 20
    assert len(svc.trace_currency_balance('actor','a','gold')) >= 3


def test_phase7b_quotes_shop_stock_bank_and_conversion(tmp_path):
    db=tmp_path/'mud.sqlite3'; svc=EconomyService(db, world_root='worlds/shattered_realms')
    svc.credit_currency('actor','a','gold',100)
    stock=svc.initialize_shop_stock('blacksmith_shop')
    assert stock
    q=svc.quote_purchase('a','blacksmith_shop','iron_sword')
    assert q.total['gold'] == 25
    tx=svc.confirm_purchase('a', q.quote_id)
    assert tx['status'] == 'completed'
    svc.deposit('a', 10, 'gold')
    assert svc.bank_balance('a','gold') == 10
    svc.withdraw('a', 5, 'gold')
    assert svc.bank_balance('a','gold') == 5
    svc.credit_currency('actor','a','copper',100)
    res=svc.convert_currency('a',100,'copper','silver')
    assert res['received'] == 1


def test_phase7b_content_validation_and_formula_ids():
    content=EconomyContent('worlds/shattered_realms')
    assert {'gold','silver','copper'} <= set(content.data['currency_profiles'])
    assert content.validate()['errors'] == []
    from engine.formulas import FormulaRegistry
    reg=FormulaRegistry.default()
    for fid in ['shop_buy_price_v1','shop_sell_price_v1','service_price_v1','repair_price_v1','currency_conversion_v1']:
        assert reg.get(fid)
