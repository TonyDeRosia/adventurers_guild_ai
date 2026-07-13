import sqlite3
from pathlib import Path
from engine.mud_runtime import MudRuntime


def make_rt(tmp_path):
    rt=MudRuntime(root=Path('.'), user_data_dir=tmp_path)
    rt.load_world('shattered_realms')
    cid=rt.create_character(world_id='shattered_realms', name='Phase Twelve Bee')['character_id']
    rt.enter_world(cid)
    return rt,cid

def text(rt,cid,cmd):
    return rt.handle_input(cid,cmd)["semantic_output"]


def test_starter_abilities_points_and_no_duplicates(tmp_path):
    rt,cid=make_rt(tmp_path)
    assert 'Set Camp' in text(rt,cid,'skills')
    assert 'Build Campfire' in text(rt,cid,'skills')
    assert 'Recall' in text(rt,cid,'spells')
    assert 'Attribute points' in text(rt,cid,'train')
    with sqlite3.connect(rt.state_store.db_path) as con:
        rows=con.execute('select ability_id,count(*) from actor_ability_progression where actor_id=? group by ability_id',(cid,)).fetchall()
        assert dict(rows)['set_camp']==1
        assert con.execute('select attribute_points from actor_progression_state where actor_id=?',(cid,)).fetchone()[0] >= 30
    rt.enter_world(cid)
    with sqlite3.connect(rt.state_store.db_path) as con:
        assert con.execute('select count(*) from actor_ability_progression where actor_id=? and ability_id="recall"',(cid,)).fetchone()[0] == 1


def test_recall_camp_and_campfire_runtime_persist(tmp_path):
    rt,cid=make_rt(tmp_path)
    out=text(rt,cid,'cast recall')
    assert 'silver light' in out.lower()
    assert 'You establish a modest campsite here.' in text(rt,cid,'set camp')
    assert 'You build a small campfire.' in text(rt,cid,'build campfire')
    assert 'campfire' in text(rt,cid,'look').lower()
    assert 'Kindling' in text(rt,cid,'look campfire')
    assert 'Kindling' in text(rt,cid,'examine campfire')
    assert 'You light the campfire.' in text(rt,cid,'light campfire')
    db=rt.state_store.db_path
    rt2=MudRuntime(root=Path('.'), user_data_dir=tmp_path); rt2.load_world('shattered_realms')
    assert 'lit campfire' in text(rt2,cid,'look').lower()
    with sqlite3.connect(db) as con:
        assert con.execute('select count(*) from campfire_instances').fetchone()[0] >= 1
