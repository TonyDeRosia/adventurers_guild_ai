"""Deterministic Phase 21B.2 acceptance of the request runtime boundary."""
from engine.abilities import AbilityExecutionRequest, AbilityExecutionService, AbilityInvocationType
from engine.actors import Actor
from smart_mud.world_registry import WorldRegistry

class SequenceRandom:
    def __init__(self, values): self.values = list(values); self.calls = 0
    def roll_percent(self): self.calls += 1; return self.values.pop(0)
    def randint(self, minimum, maximum): self.calls += 1; return self.values.pop(0)

def setup(tmp_path):
    db = tmp_path / "world.db"
    service = AbilityExecutionService(db, WorldRegistry().load_world("shattered_realms"), world_id="shattered_realms", allow_isolated_combat_engine=True)
    hero = Actor.create("hero", "Hero", "player"); hero.identity.current_location = "room1"
    service.register_actor(hero); service.grant_ability("hero", "armor", "test")
    return service, hero

def request():
    return AbilityExecutionRequest(request_id="request-1", world_id="shattered_realms", actor_id="hero", ability_id="armor", invocation_type=AbilityInvocationType.CAST_COMMAND, raw_argument_text="self", idempotency_key="browser-submit-1")

def test_preview_and_duplicate_do_not_consume_runtime_rolls(tmp_path):
    service, _ = setup(tmp_path); rng = SequenceRandom([37])
    runtime = service.ability_runtime(); runtime.random_provider = rng
    preview = runtime.execute(AbilityExecutionRequest(**{**request().__dict__, "preview": True}))
    assert preview.ok and rng.calls == 0
    first = runtime.execute(request())
    assert first.ok and first.success_policy == "ALWAYS_SUCCEEDS" and first.success_roll is None
    duplicate = runtime.execute(request())
    assert duplicate.status == "DUPLICATE_IGNORED" and rng.calls == 0

def test_committed_idempotency_survives_runtime_recreation(tmp_path):
    service, _ = setup(tmp_path)
    assert service.ability_runtime().execute(request()).ok
    # A fresh service/runtime represents a process restart using the same DB.
    restarted, _ = setup_existing(tmp_path)
    duplicate = restarted.ability_runtime().execute(request())
    assert duplicate.status == "DUPLICATE_IGNORED"

def setup_existing(tmp_path):
    db = tmp_path / "world.db"
    service = AbilityExecutionService(db, WorldRegistry().load_world("shattered_realms"), world_id="shattered_realms", allow_isolated_combat_engine=True)
    hero = Actor.create("hero", "Hero", "player"); hero.identity.current_location = "room1"
    service.register_actor(hero); service.grant_ability("hero", "armor", "test")
    return service, hero
