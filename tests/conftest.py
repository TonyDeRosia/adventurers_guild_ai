from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import pytest

from engine.mud_runtime import MudRuntime
from smart_mud.builder import BuilderWorkspace
from smart_mud.world_registry import WorldRegistry


@dataclass
class IsolatedBuilderWorld:
    world_root: Path
    world_path: Path
    builder_path: Path
    workspace: BuilderWorkspace
    runtime: MudRuntime
    database_path: Path


@pytest.fixture
def isolated_builder_world(tmp_path: Path) -> IsolatedBuilderWorld:
    repo_root = Path(__file__).resolve().parents[1]
    world_root = tmp_path / "worlds"
    world_path = world_root / "shattered_realms"
    shutil.copytree(repo_root / "worlds" / "shattered_realms", world_path)

    db_root = tmp_path / "user_data"
    workspace = BuilderWorkspace(worlds_dir=world_root)
    runtime = MudRuntime(repo_root, db_root, world_registry=WorldRegistry(world_root))
    runtime.builder = BuilderWorkspace(worlds_dir=world_root, event_bus=runtime.event_bus)
    runtime.command_engine.builder = runtime.builder

    return IsolatedBuilderWorld(
        world_root=world_root,
        world_path=world_path,
        builder_path=world_path / "builder",
        workspace=workspace,
        runtime=runtime,
        database_path=runtime.state_store.db_path,
    )
