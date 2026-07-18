from engine.death_runtime import DeathRequest, DeathRuntimeService, DeathState


def request(death_id="d1", source="character:hero"):
    return DeathRequest(death_id, "world", "room", "entity:wolf", source, terminal_damage_event_id="terminal-1", source_metadata={"life_generation":"spawn-1"})


def test_death_is_claimed_once_and_stores_side_effects(tmp_path):
    calls=[]
    def op(name):
        def f(*_args, **_kwargs):
            calls.append(name)
            return {"entity_id":"corpse-1"} if name == "create_corpse" else {"item_ids":["sword"]} if name == "transfer_belongings" else {"rolls":[{"roll":25}]} if name == "roll_loot" else {}
        return f
    service=DeathRuntimeService(tmp_path / "state.sqlite", operations={n:op(n) for n in ("cleanup_combat","create_corpse","transfer_belongings","resolve_gold","roll_loot","extract_npc")})
    first=service.process_death(request()); second=service.process_death(request())
    assert first.status == DeathState.REMOVED and second.corpse_instance_id == "corpse-1"
    assert calls.count("create_corpse") == calls.count("roll_loot") == calls.count("transfer_belongings") == 1


def test_owner_attribution_stops_cycles(tmp_path):
    actors={"entity:pet":{"master_id":"entity:pet2"},"entity:pet2":{"master_id":"character:hero"},"character:hero":{"kind":"player"},"entity:cycle":{"master_id":"entity:cycle"}}
    service=DeathRuntimeService(tmp_path / "state.sqlite", actor_lookup=actors.get)
    assert service.resolve_credited_killer("entity:pet") == "character:hero"
    assert service.resolve_credited_killer("entity:cycle") == "entity:cycle"


def test_gold_and_loot_rules_are_inclusive_and_clamped():
    class Fixed:
        def randint(self, lo, hi): return hi if (lo, hi) == (0, 2) else 25
    assert DeathRuntimeService.resolve_npc_gold(-5, 2, 9, rng=Fixed())["amount"] == 2
    rolls, warnings=DeathRuntimeService.roll_npc_loot([{"item_id":"pelt","chance":25},{"item_id":"none","chance":0}], rng=Fixed(), item_exists=lambda x: x == "pelt")
    assert not warnings and rolls[0]["dropped"] and not rolls[1]["dropped"]
