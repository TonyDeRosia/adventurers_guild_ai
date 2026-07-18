from pathlib import Path

from engine.mud_runtime import MudRuntime


def test_normal_runtime_injects_one_canonical_death_runtime_into_abilities(tmp_path):
    runtime = MudRuntime(Path.cwd(), tmp_path)
    runtime.load_world("shattered_realms")

    assert runtime.death_runtime is not None
    assert runtime.abilities is not None
    assert runtime.abilities.death_runtime is runtime.death_runtime
    assert runtime.abilities.require_death_runtime is True

