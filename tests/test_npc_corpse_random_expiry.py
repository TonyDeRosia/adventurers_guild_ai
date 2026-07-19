from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from engine.mud_runtime import MudRuntime

class Random:
    def __init__(self, value): self.value = value
    def randint(self, low, high): assert (low, high) == (180, 300); return self.value

@pytest.mark.parametrize("seconds", [180, 240, 300])
def test_npc_corpse_records_inclusive_absolute_random_expiry(tmp_path, seconds):
    rt = MudRuntime(Path.cwd(), tmp_path); rt.load_world("shattered_realms")
    now = datetime(2030, 1, 1, tzinfo=timezone.utc); rt.corpse_clock = lambda: now; rt.corpse_decay_random_provider = Random(seconds)
    wolf = rt.spawn_entity("forest_wolf", room_id="emberwood_hunting_trail")
    corpse = rt.create_corpse(wolf["entity_id"], death_id=f"death-{seconds}"); st = corpse["state"]
    assert st["decay_seconds"] == seconds and st["decay_policy"] == "NPC_RANDOM_3_TO_5_MINUTES"
    assert datetime.fromisoformat(st["decay_at_utc"]) - datetime.fromisoformat(st["created_at_utc"]) == timedelta(seconds=seconds)
    rt.corpse_clock = lambda: now + timedelta(seconds=seconds - 1); assert rt.process_corpse_decay() == 0
    rt.corpse_clock = lambda: now + timedelta(seconds=seconds); assert rt.process_corpse_decay() == 1

def test_five_seconds_is_not_interpreted_as_tick_expiry(tmp_path):
    rt = MudRuntime(Path.cwd(), tmp_path); rt.load_world("shattered_realms"); now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    rt.corpse_clock=lambda: now; rt.corpse_decay_random_provider=Random(240); wolf=rt.spawn_entity("forest_wolf", room_id="emberwood_hunting_trail"); corpse=rt.create_corpse(wolf["entity_id"])
    for elapsed in (5, 30, 120): rt.corpse_clock=lambda elapsed=elapsed: now+timedelta(seconds=elapsed); assert rt.process_corpse_decay() == 0 and rt.find_entity(corpse["entity_id"])
