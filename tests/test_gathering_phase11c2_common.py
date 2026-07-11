from pathlib import Path
import sqlite3
from engine.gathering import GatheringService, init_gathering_schema

WORLD = Path('worlds/shattered_realms')

def service(tmp_path):
    return GatheringService(tmp_path/'gathering.db', WORLD)

def mat(gs, node_id):
    return gs.materialize_node(node_id,'guildhall_crossing_square',world_time=0)

def test_phase11c2_pilot_content_loads_and_validates(tmp_path):
    gs=service(tmp_path); v=gs.validate_content()
    assert v['ok'], v
    for rid in ['common_healing_herb','wild_mushroom','oak_wood','iron_ore','common_stone','river_fish','small_beast_hide','scrap_metal','clay_placeholder']:
        assert gs.get_resource_definition(rid)
    for nid in ['guildlands_herb_patch','guildlands_mushroom_cluster','guildlands_oak_tree','guildlands_iron_vein','guildlands_stone_outcrop','guildlands_fishing_spot','guildlands_scrap_pile','rat_corpse_skinning_node']:
        assert gs.get_node_definition(nid)


def test_phase11c2_gameplay_adapters_share_gathering_service(tmp_path):
    gs=service(tmp_path)
    cases=[('harvest','guildlands_herb_patch','herb patch','basic_sickle'),('forage','guildlands_mushroom_cluster','mushroom','basic_sickle'),('mine','guildlands_iron_vein','iron vein','basic_pickaxe'),('chop','guildlands_oak_tree','oak tree','basic_hatchet'),('fish','guildlands_fishing_spot','fishing','basic_fishing_rod'),('salvage','guildlands_scrap_pile','scrap','basic_salvage_tools'),('dig','guildlands_clay_site','clay','basic_shovel')]
    for method,nid,query,tool in cases:
        n=mat(gs,nid); before=n['capacity_current']
        out=getattr(gs,method)('actor_'+method,'guildhall_crossing_square',query,tool,world_time=10)
        assert out['ok'], (method,out)
        assert gs.get_node_instance(n['node_instance_id'])['capacity_current']==before-1
        assert out['reward_source']['source_type']=='gathering'


def test_phase11c2_wrong_tool_and_exact_tool_instance_rejection(tmp_path):
    gs=service(tmp_path); n=mat(gs,'guildlands_iron_vein')
    bad=gs.mine('miner','guildhall_crossing_square','iron vein','basic_hatchet')
    assert not bad['ok'] and 'wrong_tool' in str(bad)
    good=gs.mine('miner2','guildhall_crossing_square','iron vein','basic_pickaxe')
    assert good['ok']


def test_phase11c2_skinning_once_per_exact_corpse(tmp_path):
    gs=service(tmp_path); n=mat(gs,'rat_corpse_skinning_node')
    first=gs.skin_corpse('skinner','corpse_rat_1',n['node_instance_id'],'small_beast_hide','basic_skinning_knife',world_time=5)
    second=gs.skin_corpse('skinner','corpse_rat_1',n['node_instance_id'],'small_beast_hide','basic_skinning_knife',world_time=6)
    assert first['ok']
    assert not second['ok'] and second['reason']=='corpse_resource_already_extracted'
    assert gs.trace_corpse_extraction('corpse_rat_1')['extractions'][0]['status']=='extracted'


def test_phase11c2_concurrent_capacity_never_negative_and_idempotent(tmp_path):
    gs=service(tmp_path); n=mat(gs,'rat_corpse_skinning_node')
    s1=gs.start_gathering('a1',n['node_instance_id'],'small_beast_hide','basic_skinning_knife',world_time=1)
    s2=gs.start_gathering('a2',n['node_instance_id'],'small_beast_hide','basic_skinning_knife',world_time=1)
    assert s1['ok'] and s2['ok']
    r1=gs.complete_gathering(s1['gathering_session_id'],world_time=2)
    r2=gs.complete_gathering(s2['gathering_session_id'],world_time=2)
    assert r1['ok']
    assert not r2['ok'] and r2['reason'] in ('depleted','concurrent_capacity_conflict')
    assert gs.get_node_instance(n['node_instance_id'])['capacity_current'] == 0


def test_phase11c2_discovery_personal_state_score_and_traces(tmp_path):
    gs=service(tmp_path); n=mat(gs,'guildlands_scrap_pile')
    assert gs.discover_node('actor',n['node_instance_id'],'search')['ok']
    assert gs.survey_resources('actor','guildhall_crossing_square')
    assert 'deterministic' in str(gs.trace_yield('missing'))
    score=gs.score_section('actor','gathering')
    assert score['section']=='gathering' and 'internal' not in str(score).lower()
