"""Canonical Smart MUD equipment slot registry shared by players and NPCs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class EquipmentSlot:
    id: str
    label: str


EQUIPMENT_SLOTS: tuple[EquipmentSlot, ...] = (
    EquipmentSlot("head", "Head"),
    EquipmentSlot("face", "Face"),
    EquipmentSlot("neck", "Neck"),
    EquipmentSlot("shoulders", "Shoulders"),
    EquipmentSlot("back", "Back"),
    EquipmentSlot("chest", "Chest"),
    EquipmentSlot("arms", "Arms"),
    EquipmentSlot("wrists", "Wrists"),
    EquipmentSlot("hands", "Hands"),
    EquipmentSlot("finger_left", "Finger left"),
    EquipmentSlot("finger_right", "Finger right"),
    EquipmentSlot("waist", "Waist"),
    EquipmentSlot("legs", "Legs"),
    EquipmentSlot("feet", "Feet"),
    EquipmentSlot("main_hand", "Main hand"),
    EquipmentSlot("off_hand", "Off hand"),
    EquipmentSlot("accessory_1", "Accessory 1"),
    EquipmentSlot("accessory_2", "Accessory 2"),
    EquipmentSlot("light", "Light"),
)

CANONICAL_EQUIPMENT_SLOT_IDS: tuple[str, ...] = tuple(slot.id for slot in EQUIPMENT_SLOTS)
EQUIPMENT_SLOT_LABELS: dict[str, str] = {slot.id: slot.label for slot in EQUIPMENT_SLOTS}

EQUIPMENT_SLOT_ALIASES: dict[str, str] = {
    "mainhand": "main_hand",
    "main hand": "main_hand",
    "main-hand": "main_hand",
    "wield": "main_hand",
    "primary_weapon": "main_hand",
    "primary weapon": "main_hand",
    "primary-weapon": "main_hand",
    "offhand": "off_hand",
    "off hand": "off_hand",
    "off-hand": "off_hand",
    "held": "off_hand",
    "shield": "off_hand",
    "secondary_weapon": "off_hand",
    "secondary weapon": "off_hand",
    "secondary-weapon": "off_hand",
    "wrist": "wrists",
    "body": "chest",
    "torso": "chest",
    "finger left": "finger_left",
    "finger-left": "finger_left",
    "finger right": "finger_right",
    "finger-right": "finger_right",
}


def normalize_equipment_slot(slot: object) -> str:
    raw = str(slot or "").strip()
    key = raw.lower().replace("__", "_")
    spaced = key.replace("_", " ")
    canonical = EQUIPMENT_SLOT_ALIASES.get(key) or EQUIPMENT_SLOT_ALIASES.get(spaced) or key
    return canonical if canonical in EQUIPMENT_SLOT_LABELS else key


def is_canonical_equipment_slot(slot: object) -> bool:
    return normalize_equipment_slot(slot) in EQUIPMENT_SLOT_LABELS and str(slot or "").strip().lower().replace(" ", "_").replace("-", "_") == normalize_equipment_slot(slot)


def equipment_slot_label(slot: object) -> str:
    canonical = normalize_equipment_slot(slot)
    return EQUIPMENT_SLOT_LABELS.get(canonical, str(slot or "").replace("_", " ").capitalize())


def canonicalize_slot_list(slots: Iterable[object]) -> list[str]:
    out: list[str] = []
    for slot in slots:
        normalized = normalize_equipment_slot(slot)
        if normalized in EQUIPMENT_SLOT_LABELS and normalized not in out:
            out.append(normalized)
    return out
