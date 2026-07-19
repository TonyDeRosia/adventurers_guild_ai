from datetime import datetime, timedelta, timezone
from pathlib import Path
from engine.mud_runtime import MudRuntime

class Random:
    def randint(self, low, high): return 240

def test_persisted_corpse_keeps_absolute_expiry_across_runtime_reload(tmp_path):
    now = datetime(2032, 1, 1, tzinfo=timezone.utc)
    first = MudRuntime(Path.cwd(), tmp_path); first.load_world("shattered_realms"); first.corpse_clock=lambda: now; first.corpse_decay_random_provider=Random()
    wolf=first.spawn_entity("forest_wolf", room_id="emberwood_hunting_trail"); corpse=first.create_corpse(wolf["entity_id"], death_id="restart-death"); expiry=corpse["state"]["decay_at_utc"]
    # A normal new runtime uses the same SQLite state store; it must not reroll.
    second = MudRuntime(Path.cwd(), tmp_path); second.load_world("shattered_realms"); second.corpse_clock=lambda: now+timedelta(seconds=60)
    restored=second.find_entity(corpse["entity_id"]); assert restored and restored["state"]["decay_at_utc"] == expiry
    assert datetime.fromisoformat(expiry) - second.corpse_clock() == timedelta(seconds=180)
    second.corpse_clock=lambda: now+timedelta(seconds=240); assert second.process_corpse_decay() == 1 and second.find_entity(corpse["entity_id"]) is None
