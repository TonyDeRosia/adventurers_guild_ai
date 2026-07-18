from engine.physical_combat import CombatActor, Position, position_for_hp, normalize_actor_id, AttackResolutionService, PhysicalFormulaProfile

class Rolls:
    def __init__(self, values): self.values=iter(values)
    def randint(self, lo, hi):
        value=next(self.values); assert lo <= value <= hi; return value

def actor(actor_id, **kw):
    return CombatActor(actor_id, kw.pop('kind','player'), 'world', 'room', 'actor', hp=100, max_hp=100, position=kw.pop('position', Position.FIGHTING), **kw)

def test_identity_and_positions_are_canonical():
    assert normalize_actor_id('player:one') == normalize_actor_id('character:one') == 'character:one'
    assert [position_for_hp(h) for h in (1,0,-3,-6,-11)] == [Position.STANDING,Position.STUNNED,Position.INCAPACITATED,Position.MORTALLY_WOUNDED,Position.DEAD]

def test_profile_and_hit_bounds():
    assert not PhysicalFormulaProfile.load().validate()
    svc=AttackResolutionService(rng=Rolls([1]))
    low=svc.attack_roll(actor('character:a', level=1, hitroll=-100),actor('entity:b',level=100,dexterity=100))
    assert low.hit_chance == 5
    svc=AttackResolutionService(rng=Rolls([96]))
    high=svc.attack_roll(actor('character:a',level=100,hitroll=100),actor('entity:b',level=1,dexterity=1))
    assert high.hit_chance == 95 and not high.hit

def test_hit_damage_uses_one_hp_source_and_miss_does_not_mutate():
    target=actor('entity:fox',kind='npc', armor=-10, dexterity=1)
    attacker=actor('character:hero', strength=10, dexterity=10, weapon={'item_instance_id':'sword-1','damage_dice_count':1,'damage_die_size':4,'damage_type':'slash'})
    # hit roll, weapon die, no-crit trigger
    roll,result=AttackResolutionService(rng=Rolls([1,4,1])).resolve(attacker,target,'enc-1')
    assert roll.hit and result and target.hp == 100-result.final_damage and result.attack_source_id == 'sword-1'
    before=target.hp
    roll,result=AttackResolutionService(rng=Rolls([100])).resolve(attacker,target,'enc-1')
    assert not roll.hit and result is None and target.hp == before

def test_sleeping_auto_hit_and_armor_mitigates_only_damage():
    a=actor('character:a',weapon={'damage_dice_count':1,'damage_die_size':2}, strength=10)
    d=actor('entity:d',kind='npc',position=Position.SLEEPING,armor=1000)
    roll,result=AttackResolutionService(rng=Rolls([2,1])).resolve(a,d)
    assert roll.automatic_hit_reason == 'TARGET_NOT_AWAKE' and result.final_damage == 1
