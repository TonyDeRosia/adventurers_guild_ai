from engine.character_stats import CharacterAttributeService, CombatStatService, CombatStatSnapshot, ActorStatInput, PrimaryStatValue, CombatStatValue, ResistanceStatValue, NaturalWeaponProfile

class C:
    id='hero'; level=2; hp=999; mana=10; stamina=10; inventory=[]; attributes={'strength':12,'dexterity':12,'constitution':12,'intelligence':12,'wisdom':12,'charisma':12}

def service():
    return CombatStatService(CharacterAttributeService())

def test_snapshot_is_structured_actor_generic_and_read_only():
    c=C(); s=service(); snap=s.get_combat_snapshot(c, {'runtime':None})
    assert isinstance(snap, CombatStatSnapshot)
    assert snap.schema_version == 'phase13c3-b3.combat-snapshot.v1'
    assert snap.actor_id == 'hero'
    assert isinstance(next(iter(snap.primary_stats.values())), PrimaryStatValue)
    assert isinstance(snap.offense['accuracy'], CombatStatValue)
    assert isinstance(snap.resistances['physical'], ResistanceStatValue)
    assert c.hp == 999
    assert snap.resource_maxima['health'].value == 999
    events=s.refresh_actor_maxima(c,'test')
    assert c.hp == snap.resource_maxima['max_health'].value
    assert events

def test_actor_stat_input_and_template_natural_weapon_projection():
    s=service()
    tmpl={'id':'wolf','level':3,'combat_role':'skirmisher','natural_weapons':[{'id':'bite','name':'Wolf Bite','min_damage':2,'max_damage':6,'damage_type':'pierce'}], 'resistances':{'cold':10}}
    asi=s.build_actor_stat_input(tmpl,{})
    assert isinstance(asi, ActorStatInput)
    assert asi.actor_type == 'npc'
    assert len(set(asi.primary_attribute_bases.values())) > 1
    assert isinstance(asi.natural_weapon_profiles[0], NaturalWeaponProfile)
    assert asi.natural_weapon_profiles[0].name == 'Wolf Bite'

def test_semantic_roles_drive_formula_variables_and_speed_inactive():
    s=service(); c=C(); bd=s.get_breakdown(c,'attack_power')
    assert 'physical_power' in bd['inputs']
    snap=s.get_combat_snapshot(c,{})
    assert snap.criticals['critical_damage'].unit == 'multiplier'
    assert snap.speed['initiative'].active is False
    assert 'do not currently use initiative' in snap.speed['initiative'].inactive_reason
    assert snap.mechanics['presence']['combat_consumed'] is False

def test_player_npc_equivalent_attributes_have_equivalent_stats():
    s=service(); p=C()
    class N(C):
        id='npc'; actor_type='mob'; template={'id':'npc_template','attributes':C.attributes,'level':2}; template_id='npc_template'
    ps=s.get_combat_snapshot(p,{})
    ns=s.get_combat_snapshot(N(),{})
    assert ps.primary_stats['strength'].final_value == ns.primary_stats['strength'].final_value
    assert ps.offense['attack_power'].value == ns.offense['attack_power'].value
    assert ps.defense['evasion'].value == ns.defense['evasion'].value
