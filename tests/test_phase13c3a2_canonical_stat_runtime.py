from types import SimpleNamespace
from engine.character_stats import CharacterAttributeService, CombatStatService, StatModifier
from engine.mud_state_store import MUDStateStore

class RuntimeStub:
    active_world_id='shattered_realms'; world_time=1
    def __init__(self): self.equipped=[]; self.inventory=[]; self.state_store=None; self.active_world=SimpleNamespace(effect_templates=[])
    def find_equipped_items(self, cid): return list(self.equipped)
    def find_inventory_items(self, cid): return list(self.inventory)


def char(): return SimpleNamespace(id='hero', level=1, hp=999, mana=5, stamina=5, max_health=60, max_mana=30, max_stamina=50, inventory=[])

def services(tmp_path, rt):
    store=MUDStateStore(str(tmp_path/'state.db')); store.initialize(); rt.state_store=store
    attr=CharacterAttributeService(store); attr.runtime=rt
    return attr, CombatStatService(attr)


def test_equipped_weapon_armor_and_affect_change_and_revert(tmp_path):
    rt=RuntimeStub(); attr, combat=services(tmp_path, rt); c=char()
    base=combat.get_combat_snapshot(c, {'runtime':rt})
    assert base.weapon_profile is None
    assert base.defense['armor'] == 0

    rt.equipped=[{'instance_id':'w1','template_id':'iron_sword','owner_type':'equipment','owner_id':'hero','equipped_slot':'main_hand','stack_count':1,'template':{'id':'iron_sword','name':'Iron Sword','type':'weapon','base_damage':7,'damage_types':['slash'],'attack_speed':2,'reach':1,'range':0,'weight':4,'modifiers':[{'id':'sword_str','target_domain':'attribute','target_key':'strength','operation':'add','value':2}]}}]
    with_weapon=combat.get_combat_snapshot(c, {'runtime':rt})
    assert with_weapon.weapon_profile.source == 'Iron Sword'
    assert with_weapon.weapon_profile.maximum_damage > 0
    assert attr.get_attribute(c,'strength', {'runtime':rt}).equipment_modifier == 2

    rt.equipped.append({'instance_id':'a1','template_id':'leather_armor','owner_type':'equipment','owner_id':'hero','equipped_slot':'body','stack_count':1,'template':{'id':'leather_armor','name':'Leather Armor','armor_value':3,'weight':8,'resistances':{},'modifiers':[{'id':'armor_evasion','target_domain':'derived_stat','target_key':'evasion','operation':'subtract','value':1}]}})
    armored=combat.get_combat_snapshot(c, {'runtime':rt})
    assert armored.defense['armor'] == 3
    assert armored.carrying['current_carry_weight'] == 12
    assert armored.defense['evasion'] == with_weapon.defense['evasion'] - 1

    affected=combat.get_combat_snapshot(c, {'runtime':rt,'modifiers':[StatModifier('test_bless','affect','effect1','strength','add',2), StatModifier('fire','affect','effect1','resistance.fire','add',5)]})
    assert affected.attributes['strength'].affect_modifier == 2
    assert affected.resistances['fire'] == 5

    rt.equipped=[]
    reverted=combat.get_combat_snapshot(c, {'runtime':rt})
    assert reverted.weapon_profile is None
    assert reverted.defense['armor'] == 0
    assert reverted.carrying['current_carry_weight'] == 0
    assert reverted.attributes['strength'].equipment_modifier == 0


def test_resource_clamp_no_refill_and_source_version_changes(tmp_path):
    rt=RuntimeStub(); _, combat=services(tmp_path, rt); c=char()
    snap=combat.get_combat_snapshot(c, {'runtime':rt})
    assert snap.resources['health'] == snap.resources['max_health']
    assert c.hp == snap.resources['max_health']
    before=snap.source_version
    rt.equipped=[{'instance_id':'cap','template_id':'belt','owner_type':'equipment','owner_id':'hero','equipped_slot':'waist','stack_count':1,'template':{'id':'belt','name':'Belt','weight':1,'modifiers':[{'id':'carry','target_domain':'derived_stat','target_key':'carry_capacity','operation':'add','value':10}]}}]
    assert combat.get_combat_snapshot(c, {'runtime':rt}).source_version != before
