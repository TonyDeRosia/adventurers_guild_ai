from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from engine.mud_runtime import MudRuntime

@pytest.mark.parametrize("legacy, expected", [(5, 180), (179, 180), (999, 300)])
def test_legacy_npc_expiry_migrates_once_and_clamps_to_policy(tmp_path, legacy, expected):
    rt = MudRuntime(Path.cwd(), tmp_path); rt.load_world("shattered_realms"); now = datetime(2031, 1, 1, tzinfo=timezone.utc); rt.corpse_clock=lambda: now
    wolf = rt.spawn_entity("forest_wolf", room_id="emberwood_hunting_trail"); corpse = rt.create_corpse(wolf["entity_id"])
    st = {**corpse["state"], "decay_policy": "legacy_ticks", "decay_seconds": legacy, "created_at_utc": now.isoformat()}
    rt.update_entity_state(corpse["entity_id"], st); assert rt.process_corpse_decay() == 0
    migrated = rt.find_entity(corpse["entity_id"])["state"]
    assert migrated["decay_policy"] == "NPC_RANDOM_3_TO_5_MINUTES" and migrated["decay_seconds"] == expected
    expiry = migrated["decay_at_utc"]; assert rt.process_corpse_decay() == 0 and rt.find_entity(corpse["entity_id"])["state"]["decay_at_utc"] == expiry

def test_already_expired_absolute_corpse_is_not_revived(tmp_path):
    rt = MudRuntime(Path.cwd(), tmp_path); rt.load_world("shattered_realms"); now=datetime(2031,1,1,tzinfo=timezone.utc); rt.corpse_clock=lambda: now
    wolf=rt.spawn_entity("forest_wolf", room_id="emberwood_hunting_trail"); corpse=rt.create_corpse(wolf["entity_id"])
    rt.update_entity_state(corpse["entity_id"], {**corpse["state"], "decay_at_utc": (now-timedelta(seconds=1)).isoformat()})
    assert rt.process_corpse_decay() == 1 and rt.find_entity(corpse["entity_id"]) is None and rt.process_corpse_decay() == 0
