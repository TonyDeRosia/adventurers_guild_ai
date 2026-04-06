"""Inventory and item management."""

from __future__ import annotations

from engine.entities import Character


class InventoryService:
    """Simple inventory mutations with validation."""

    def add_item(self, player: Character, item_name: str) -> str:
        item = item_name.strip()
        if not item:
            return "Item name cannot be empty."
        player.inventory.append(item)
        return f"Added '{item}' to inventory."

    def remove_item(self, player: Character, item_name: str) -> str:
        item = item_name.strip()
        if item in player.inventory:
            player.inventory.remove(item)
            return f"Removed '{item}' from inventory."
        return f"Item '{item}' not found."
