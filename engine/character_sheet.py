"""Player character sheet utilities."""

from __future__ import annotations

from engine.entities import Character


class CharacterSheetService:
    """Read/update methods for character progression."""

    def summary(self, player: Character) -> str:
        bag = ", ".join(item.replace("_", " ").title() for item in player.inventory) if player.inventory else "Empty"
        equipped = player.equipped_item_id.replace("_", " ").title() if player.equipped_item_id else "None"
        return (
            f"{player.name} the {player.char_class} | Level {player.level} | "
            f"HP {player.hp}/{player.max_hp} | AC {player.armor_class} | "
            f"Attack +{player.attack_bonus} | "
            f"STR {player.strength} AGI {player.agility} INT {player.intellect} VIT {player.vitality} | "
            f"XP {player.xp} | Equipped: {equipped} | Inventory: {bag}"
        )

    def grant_xp(self, player: Character, amount: int) -> str:
        player.xp += amount
        leveled = False
        while player.xp >= player.level * 100:
            player.xp -= player.level * 100
            player.level += 1
            player.max_hp += 4
            player.hp = player.max_hp
            player.attack_bonus += 1
            leveled = True
        return "Level up achieved!" if leveled else "XP granted."
