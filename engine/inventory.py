"""Inventory and item management."""

from __future__ import annotations

from engine.content_repository import ContentRepository
from engine.entities import Character


class InventoryService:
    """Inventory mutations with support for stable IDs and display names."""

    def __init__(self, content: ContentRepository) -> None:
        self.content = content

    def ensure_compatibility(self, player: Character) -> None:
        if player.inventory_item_ids:
            self._sync_display_names(player)
            return

        for entry in list(player.inventory):
            item_id = self.content.resolve_item_id(entry)
            if item_id:
                player.inventory_item_ids.append(item_id)
            else:
                fallback_id = self._create_legacy_item_id(entry)
                player.inventory_item_ids.append(fallback_id)
                if fallback_id not in self.content.items_by_id:
                    self.content.items_by_id[fallback_id] = self._legacy_item(fallback_id, entry)
                    self.content.items_by_name[entry.lower()] = fallback_id
        self._sync_display_names(player)

    def add_item_by_id(self, player: Character, item_id: str) -> str:
        item = self.content.items_by_id.get(item_id)
        if not item:
            return f"Unknown item id '{item_id}'."
        player.inventory_item_ids.append(item_id)
        self._sync_display_names(player)
        return f"Added '{item.name}' to inventory."

    def add_item(self, player: Character, item_name: str) -> str:
        token = item_name.strip()
        if not token:
            return "Item name cannot be empty."
        item_id = self.content.resolve_item_id(token)
        if item_id:
            return self.add_item_by_id(player, item_id)

        fallback_id = self._create_legacy_item_id(token)
        if fallback_id not in self.content.items_by_id:
            self.content.items_by_id[fallback_id] = self._legacy_item(fallback_id, token)
            self.content.items_by_name[token.lower()] = fallback_id
        player.inventory_item_ids.append(fallback_id)
        self._sync_display_names(player)
        return f"Added '{token}' to inventory."

    def remove_item(self, player: Character, token: str) -> str:
        item_id = self._resolve_owned_item(player, token)
        if not item_id:
            return f"Item '{token.strip()}' not found."
        player.inventory_item_ids.remove(item_id)
        self._sync_display_names(player)
        removed_name = self.content.items_by_id[item_id].name
        return f"Removed '{removed_name}' from inventory."

    def use_item(self, player: Character, token: str) -> str:
        item_id = self._resolve_owned_item(player, token)
        if not item_id:
            return f"Item '{token.strip()}' not found."
        item = self.content.items_by_id[item_id]
        if item.kind != "consumable":
            return f"{item.name} cannot be used right now."
        healed = min(item.heal_amount, player.max_hp - player.hp)
        player.hp += healed
        player.inventory_item_ids.remove(item_id)
        self._sync_display_names(player)
        return f"You use {item.name} and recover {healed} HP."

    def equip_item(self, player: Character, token: str) -> str:
        item_id = self._resolve_owned_item(player, token)
        if not item_id:
            return f"Item '{token.strip()}' not found."
        item = self.content.items_by_id[item_id]
        if item.slot == "weapon":
            player.equipped_weapon_id = item_id
            return f"Equipped weapon: {item.name}."
        if item.slot == "trinket":
            player.equipped_trinket_id = item_id
            return f"Equipped trinket: {item.name}."
        return f"{item.name} cannot be equipped."

    def list_inventory(self, player: Character) -> str:
        self._sync_display_names(player)
        if not player.inventory_item_ids:
            return "Inventory is empty"
        entries = []
        for item_id in player.inventory_item_ids:
            item = self.content.items_by_id.get(item_id)
            if item:
                entries.append(f"{item.name} ({item.id})")
        weapon_name = self._equipped_name(player.equipped_weapon_id)
        trinket_name = self._equipped_name(player.equipped_trinket_id)
        return (
            "Inventory: "
            + ", ".join(entries)
            + f". Equipped weapon: {weapon_name}. Equipped trinket: {trinket_name}."
        )

    def has_item(self, player: Character, item_id: str) -> bool:
        return item_id in player.inventory_item_ids

    def get_attack_bonus_from_equipment(self, player: Character) -> int:
        if not player.equipped_weapon_id:
            return 0
        weapon = self.content.items_by_id.get(player.equipped_weapon_id)
        return weapon.attack_bonus if weapon else 0

    def _resolve_owned_item(self, player: Character, token: str) -> str | None:
        normalized = token.strip().lower()
        direct_id = self.content.resolve_item_id(normalized)
        if direct_id and direct_id in player.inventory_item_ids:
            return direct_id
        for item_id in player.inventory_item_ids:
            item = self.content.items_by_id.get(item_id)
            if item and item.name.lower() == normalized:
                return item_id
        return None

    def _sync_display_names(self, player: Character) -> None:
        player.inventory = [
            self.content.items_by_id[item_id].name
            for item_id in player.inventory_item_ids
            if item_id in self.content.items_by_id
        ]

    def _equipped_name(self, item_id: str | None) -> str:
        if not item_id:
            return "none"
        item = self.content.items_by_id.get(item_id)
        return item.name if item else "none"

    @staticmethod
    def _create_legacy_item_id(item_name: str) -> str:
        return f"legacy_{item_name.strip().lower().replace(' ', '_')}"

    def _legacy_item(self, item_id: str, item_name: str):
        from engine.content_repository import ItemDefinition

        return ItemDefinition(
            id=item_id,
            name=item_name,
            kind="utility",
            description="Legacy imported item.",
        )
