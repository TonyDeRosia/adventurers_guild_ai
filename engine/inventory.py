"""Inventory and item management."""

from __future__ import annotations

from engine.content_registry import ContentRegistry
from engine.entities import Character


class InventoryService:
    """Simple inventory mutations with item-aware use and equip methods."""

    def __init__(self, content: ContentRegistry) -> None:
        self.content = content

    def add_item(self, player: Character, item_id: str) -> str:
        normalized = self._normalize_item_id(item_id)
        if not normalized:
            return "Item name cannot be empty."
        player.inventory.append(normalized)
        label = self._label(normalized)
        return f"Added '{label}' to inventory."

    def remove_item(self, player: Character, item_id: str) -> str:
        normalized = self._normalize_item_id(item_id)
        if normalized in player.inventory:
            player.inventory.remove(normalized)
            return f"Removed '{self._label(normalized)}' from inventory."
        return f"Item '{item_id.strip()}' not found."

    def describe_inventory(self, player: Character) -> str:
        if not player.inventory:
            return "Inventory: empty"
        readable = [self._label(item_id) for item_id in player.inventory]
        equipped = self._label(player.equipped_item_id) if player.equipped_item_id else "none"
        return f"Inventory: {', '.join(readable)} | Equipped: {equipped}"

    def use_item(self, player: Character, item_id: str) -> str:
        normalized = self._normalize_item_id(item_id)
        if normalized not in player.inventory:
            return "You do not have that item."

        definition = self.content.get_item(normalized)
        if definition is None:
            return f"{self._label(normalized)} has no usable effect."

        if definition.type == "healing":
            if player.hp >= player.max_hp:
                return "You are already at full health."
            healed = min(definition.heal_amount, player.max_hp - player.hp)
            player.hp += healed
            player.inventory.remove(normalized)
            return f"You use {definition.name} and recover {healed} HP."

        return f"{definition.name} cannot be used right now."

    def equip_item(self, player: Character, item_id: str) -> str:
        normalized = self._normalize_item_id(item_id)
        if normalized not in player.inventory:
            return "You do not have that item."

        definition = self.content.get_item(normalized)
        if definition is None or definition.type not in {"trinket", "weapon"}:
            return f"{self._label(normalized)} cannot be equipped."

        current = player.equipped_item_id
        if current == normalized:
            return f"{definition.name} is already equipped."

        if current:
            current_def = self.content.get_item(current)
            if current_def and current_def.attack_bonus:
                player.attack_bonus -= current_def.attack_bonus

        player.equipped_item_id = normalized
        if definition.attack_bonus:
            player.attack_bonus += definition.attack_bonus
        return f"You equip {definition.name}."

    def _normalize_item_id(self, item_input: str | None) -> str:
        token = (item_input or "").strip().lower().replace(" ", "_")
        return token

    def _label(self, item_id: str | None) -> str:
        if not item_id:
            return "none"
        definition = self.content.get_item(item_id)
        if definition:
            return definition.name
        return item_id.replace("_", " ").title()
