from pathlib import Path
from engine.environment import EnvironmentService


def test_phase11a_environment_foundation_smoke(tmp_path):
    svc = EnvironmentService(tmp_path / "env.db", Path("worlds/shattered_realms"), "shattered_realms")
    assert svc.validate_content()["errors"] == []
    weather = svc.get_weather()
    assert weather["weather_state_id"]
    assert svc.get_forecast()["current_conditions"] == weather["current_weather_type"]
    room = {"id": "phase11a_room", "terrain": "underground"}
    assert svc.resolve_room_environment(room, world_time=0)["light"]["light_class"] == "pitch_black"
    svc.activate_light_source("item", "phase11a_torch", "torch_light", room_id="phase11a_room")
    assert svc.evaluate_visibility("actor", "room", "phase11a_room", room)["visible"] is True
    assert "movement_modifier" in svc.movement_context(room)
    assert "visibility_modifier" in svc.combat_context(room)
