"""Load structured campaign content from JSON files under data/."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EnemyReward:
    xp: int = 0
    item_ids: list[str] = field(default_factory=list)
    set_flags: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EnemyDefinition:
    id: str
    name: str
    max_hp: int
    attack: int
    armor: int
    damage_die: int
    description: str
    encounter_text: str
    reward: EnemyReward


@dataclass(frozen=True)
class ItemDefinition:
    id: str
    name: str
    kind: str
    description: str
    heal_amount: int = 0
    slot: str | None = None
    attack_bonus: int = 0


@dataclass(frozen=True)
class DialogueChoice:
    id: str
    text: str
    next_node: str | None = None
    effects: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DialogueNode:
    npc_text: str
    choices: list[DialogueChoice]


@dataclass(frozen=True)
class DialogueTree:
    start_node: str
    nodes: dict[str, DialogueNode]


@dataclass(frozen=True)
class TurnInRule:
    quest_id: str
    required_item_id: str
    completion_flag: str


class ContentRepository:
    """Central registry for data-driven content definitions."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.items_by_id: dict[str, ItemDefinition] = {}
        self.items_by_name: dict[str, str] = {}
        self.enemies: dict[str, EnemyDefinition] = {}
        self.location_encounters: dict[str, str] = {}
        self.dialogues: dict[str, DialogueTree] = {}
        self.location_items: dict[str, list[str]] = {}
        self.npc_turnins: dict[str, TurnInRule] = {}
        self.reload()

    def reload(self) -> None:
        self._load_items()
        self._load_enemies()
        self._load_dialogues()
        self._load_world_content()

    def _read_json(self, filename: str) -> dict[str, Any]:
        path = self.data_dir / filename
        return json.loads(path.read_text(encoding="utf-8"))

    def _load_items(self) -> None:
        payload = self._read_json("items.json")
        items: dict[str, ItemDefinition] = {}
        names: dict[str, str] = {}
        for item_data in payload.get("items", []):
            item = ItemDefinition(
                id=item_data["id"],
                name=item_data["name"],
                kind=item_data["kind"],
                description=item_data["description"],
                heal_amount=item_data.get("heal_amount", 0),
                slot=item_data.get("slot"),
                attack_bonus=item_data.get("attack_bonus", 0),
            )
            items[item.id] = item
            names[item.name.lower()] = item.id
        self.items_by_id = items
        self.items_by_name = names

    def _load_enemies(self) -> None:
        payload = self._read_json("enemies.json")
        enemies: dict[str, EnemyDefinition] = {}
        for enemy_data in payload.get("enemies", []):
            reward_data = enemy_data.get("reward", {})
            enemy = EnemyDefinition(
                id=enemy_data["id"],
                name=enemy_data["name"],
                max_hp=enemy_data["max_hp"],
                attack=enemy_data["attack"],
                armor=enemy_data["armor"],
                damage_die=enemy_data.get("damage_die", 6),
                description=enemy_data.get("description", ""),
                encounter_text=enemy_data.get("encounter_text", ""),
                reward=EnemyReward(
                    xp=reward_data.get("xp", 0),
                    item_ids=list(reward_data.get("item_ids", [])),
                    set_flags=dict(reward_data.get("set_flags", {})),
                ),
            )
            enemies[enemy.id] = enemy
        self.enemies = enemies
        self.location_encounters = dict(payload.get("location_encounters", {}))

    def _load_dialogues(self) -> None:
        payload = self._read_json("dialogues.json")
        dialogues: dict[str, DialogueTree] = {}
        for npc_id, tree_data in payload.get("dialogues", {}).items():
            nodes: dict[str, DialogueNode] = {}
            for node_id, node_data in tree_data.get("nodes", {}).items():
                choices = [
                    DialogueChoice(
                        id=choice_data["id"],
                        text=choice_data["text"],
                        next_node=choice_data.get("next_node"),
                        effects=choice_data.get("effects", {}),
                    )
                    for choice_data in node_data.get("choices", [])
                ]
                nodes[node_id] = DialogueNode(npc_text=node_data["npc_text"], choices=choices)
            dialogues[npc_id] = DialogueTree(start_node=tree_data["start_node"], nodes=nodes)
        self.dialogues = dialogues

    def _load_world_content(self) -> None:
        payload = self._read_json("world_content.json")
        self.location_items = {
            location_id: list(item_ids)
            for location_id, item_ids in payload.get("location_items", {}).items()
        }
        self.npc_turnins = {
            npc_id: TurnInRule(
                quest_id=rule["quest_id"],
                required_item_id=rule["required_item_id"],
                completion_flag=rule["completion_flag"],
            )
            for npc_id, rule in payload.get("npc_quest_turnins", {}).items()
        }

    def resolve_item_id(self, token: str) -> str | None:
        lowered = token.lower().strip()
        if lowered in self.items_by_id:
            return lowered
        return self.items_by_name.get(lowered)
