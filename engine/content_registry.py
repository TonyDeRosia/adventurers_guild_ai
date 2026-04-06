"""Load data-driven campaign content assets."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class DialogueOption:
    id: str
    text: str
    next_node: str | None = None
    effects: dict[str, Any] = field(default_factory=dict)


@dataclass
class DialogueNode:
    text: str
    options: list[DialogueOption] = field(default_factory=list)


@dataclass
class DialogueTree:
    start_node: str
    nodes: dict[str, DialogueNode]


@dataclass
class EnemyReward:
    xp: int = 0
    items: list[str] = field(default_factory=list)


@dataclass
class EnemyDefinition:
    id: str
    name: str
    max_hp: int
    attack: int
    armor: int
    description: str
    encounter_text: str
    damage_die: int = 6
    reward: EnemyReward = field(default_factory=EnemyReward)


@dataclass
class ItemDefinition:
    id: str
    name: str
    type: str
    description: str
    heal_amount: int = 0
    attack_bonus: int = 0


class ContentRegistry:
    """Provides typed lookups over JSON-authored content files."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self._dialogues = self._load_dialogues()
        self._enemies = self._load_enemies()
        self._items = self._load_items()

    def _read_json(self, filename: str) -> dict[str, Any]:
        return json.loads((self.data_dir / filename).read_text(encoding="utf-8"))

    def _load_dialogues(self) -> dict[str, DialogueTree]:
        payload = self._read_json("dialogues.json")
        trees: dict[str, DialogueTree] = {}
        for npc_id, raw_tree in payload.items():
            nodes: dict[str, DialogueNode] = {}
            for node_id, raw_node in raw_tree["nodes"].items():
                options = [
                    DialogueOption(
                        id=o["id"],
                        text=o["text"],
                        next_node=o.get("next_node"),
                        effects=o.get("effects", {}),
                    )
                    for o in raw_node.get("options", [])
                ]
                nodes[node_id] = DialogueNode(text=raw_node["text"], options=options)
            trees[npc_id] = DialogueTree(start_node=raw_tree["start_node"], nodes=nodes)
        return trees

    def _load_enemies(self) -> dict[str, EnemyDefinition]:
        payload = self._read_json("enemies.json")
        enemies: dict[str, EnemyDefinition] = {}
        for enemy_id, raw in payload.items():
            reward_raw = raw.get("reward", {})
            reward = EnemyReward(xp=reward_raw.get("xp", 0), items=reward_raw.get("items", []))
            enemies[enemy_id] = EnemyDefinition(
                id=raw["id"],
                name=raw["name"],
                max_hp=raw["max_hp"],
                attack=raw["attack"],
                armor=raw["armor"],
                damage_die=raw.get("damage_die", 6),
                description=raw["description"],
                encounter_text=raw["encounter_text"],
                reward=reward,
            )
        return enemies

    def _load_items(self) -> dict[str, ItemDefinition]:
        payload = self._read_json("items.json")
        items: dict[str, ItemDefinition] = {}
        for item_id, raw in payload.items():
            items[item_id] = ItemDefinition(
                id=raw["id"],
                name=raw["name"],
                type=raw["type"],
                description=raw["description"],
                heal_amount=raw.get("heal_amount", 0),
                attack_bonus=raw.get("attack_bonus", 0),
            )
        return items

    def get_dialogue(self, npc_id: str) -> DialogueTree | None:
        return self._dialogues.get(npc_id)

    def get_enemy(self, enemy_id: str) -> EnemyDefinition | None:
        return self._enemies.get(enemy_id)

    def get_item(self, item_id: str) -> ItemDefinition | None:
        return self._items.get(item_id)

    def all_items(self) -> dict[str, ItemDefinition]:
        return self._items
