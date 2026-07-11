from pathlib import Path
from engine.environment import EnvironmentService


def svc(tmp_path):
    return EnvironmentService(tmp_path / "env.db", Path("worlds/shattered_realms"), "shattered_realms")


def test_phase11a_profile_validation_and_required_content(tmp_path):
    s = svc(tmp_path)
    result = s.validate_content()
    assert result["errors"] == []
    assert {"guildlands_temperate", "guildlands_underground", "guildlands_indoor"} <= set(s.records["climate_profiles"])
    assert {"clear", "cloudy", "rain", "heavy_rain", "fog", "light_snow", "storm"} <= set(s.records["weather_type_definitions"])


def test_phase11a_daylight_seasons_and_dark_room_resolution(tmp_path):
    s = svc(tmp_path)
    assert s.resolve_season({"day": 1, "hour": 0, "minute": 0})["id"] == "spring"
    assert s.resolve_day_period({"day": 1, "hour": 5, "minute": 30})["period"] == "dawn"
    env = s.resolve_room_environment({"id": "cave", "terrain": "underground"}, world_time=0)
    assert env["profile_id"] == "underground_dark"
    assert env["light"]["light_class"] == "pitch_black"
    assert env["sheltered"] is True


def test_phase11a_weather_is_deterministic_persistent_and_forecast_read_only(tmp_path):
    s = svc(tmp_path)
    first = s.get_weather()
    before = dict(first)
    forecast = s.get_forecast()
    after_forecast = s.get_weather()
    assert forecast["current_conditions"] == before["current_weather_type"]
    assert after_forecast == before
    changes = s.process_environment_time("shattered_realms", 500)
    assert len(changes) <= 4
    persisted = EnvironmentService(tmp_path / "env.db", Path("worlds/shattered_realms"), "shattered_realms").get_weather()
    assert persisted["weather_state_id"] == first["weather_state_id"]
    assert persisted["next_transition_world_time"] >= before["next_transition_world_time"]


def test_phase11a_light_sources_visibility_and_exposure(tmp_path):
    s = svc(tmp_path)
    room = {"id": "cave", "terrain": "underground"}
    assert s.evaluate_visibility("actor", "room", "cave", room)["result"] == "not_visible"
    light = s.activate_light_source("item", "torch-1", "torch_light", room_id="cave")
    assert light["status"] == "active"
    assert s.resolve_room_environment(room, world_time=0)["light"]["light_class"] in {"normal", "bright"}
    assert s.evaluate_visibility("actor", "room", "cave", room)["visible"] is True
    assert s.extinguish_light_source("item", "torch-1") is True
    assert s.resolve_room_environment(room, world_time=0)["light"]["light_class"] == "pitch_black"
    outside = {"id": "road", "terrain": "outdoor"}
    e1 = s.accumulate_exposure("actor", outside, 100)
    e2 = s.accumulate_exposure("actor", outside, 100)
    assert e1 == e2


def test_phase11a_context_hooks(tmp_path):
    s = svc(tmp_path)
    room = {"id": "road", "terrain": "outdoor"}
    assert "movement_modifier" in s.movement_context(room)
    assert "visibility_modifier" in s.combat_context(room)
    assert s.living_world_context(room)["weather"] in s.records["weather_type_definitions"]
    assert {"current_weather", "season", "day_period", "light_class", "sheltered"} <= set(s.quest_condition_context(room))
