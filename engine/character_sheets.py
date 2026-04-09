"""Optional character sheet schema and prompt formatting helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

SheetType = Literal["main_character", "npc_or_mob", "party_member", "minion_or_summon"]
GuidanceStrength = Literal["light", "strong"]
AbilityType = Literal["spell", "skill", "ability", "passive", "technique", "trait", "item_power"]


@dataclass
class CharacterSheetStats:
    health: int = 10
    energy_or_mana: int = 10
    attack: int = 10
    defense: int = 10
    speed: int = 10
    magic: int = 10
    willpower: int = 10
    presence: int = 10


@dataclass
class CharacterSheetClassicAttributes:
    strength: int | None = None
    dexterity: int | None = None
    constitution: int | None = None
    intelligence: int | None = None
    wisdom: int | None = None
    charisma: int | None = None


@dataclass
class CharacterSheetState:
    trust: int | None = None
    suspicion: int | None = None
    anger: int | None = None
    fear_state: int | None = None
    morale: int | None = None
    bond_to_player: int | None = None
    current_condition: str = ""


@dataclass
class CharacterSheetAbilityEntry:
    name: str
    type: AbilityType = "ability"
    description: str = ""
    cost_or_resource: str = ""
    cooldown: str = ""
    tags: list[str] = field(default_factory=list)
    notes: str = ""

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "CharacterSheetAbilityEntry":
        raw_type = str(payload.get("type", "ability")).strip().lower()
        ability_type: AbilityType = (
            raw_type if raw_type in {"spell", "skill", "ability", "passive", "technique", "trait", "item_power"} else "ability"
        )
        return cls(
            name=str(payload.get("name", "")).strip() or "Unnamed Ability",
            type=ability_type,
            description=str(payload.get("description", "")).strip(),
            cost_or_resource=str(payload.get("cost_or_resource", "")).strip(),
            cooldown=str(payload.get("cooldown", "")).strip(),
            tags=[str(tag).strip() for tag in payload.get("tags", []) if str(tag).strip()],
            notes=str(payload.get("notes", "")).strip(),
        )


@dataclass
class CharacterSheet:
    # Layer 1: identity and role
    id: str
    name: str
    sheet_type: SheetType
    role: str = ""
    archetype: str = ""
    level_or_rank: str = ""
    faction: str = ""
    description: str = ""

    # Layer 2: core gameplay stats
    stats: CharacterSheetStats = field(default_factory=CharacterSheetStats)
    classic_attributes: CharacterSheetClassicAttributes = field(default_factory=CharacterSheetClassicAttributes)

    # Layer 3: narrative and behavior anchors
    traits: list[str] = field(default_factory=list)
    abilities: list[str] = field(default_factory=list)
    guaranteed_abilities: list[CharacterSheetAbilityEntry] = field(default_factory=list)
    equipment: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    temperament: str = ""
    loyalty: str = ""
    fear: str = ""
    desire: str = ""
    social_style: str = ""
    speech_style: str = ""
    notes: str = ""

    state: CharacterSheetState = field(default_factory=CharacterSheetState)
    guidance_strength: GuidanceStrength = "light"

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "CharacterSheet":
        stats = CharacterSheetStats(**dict(payload.get("stats", {})))
        classic = CharacterSheetClassicAttributes(**dict(payload.get("classic_attributes", {})))
        state = CharacterSheetState(**dict(payload.get("state", {})))
        raw_type = str(payload.get("sheet_type", "npc_or_mob"))
        sheet_type: SheetType = raw_type if raw_type in {"main_character", "npc_or_mob", "party_member", "minion_or_summon"} else "npc_or_mob"
        raw_strength = str(payload.get("guidance_strength", "light"))
        guidance_strength: GuidanceStrength = raw_strength if raw_strength in {"light", "strong"} else "light"
        return cls(
            id=str(payload.get("id", "")).strip() or "sheet",
            name=str(payload.get("name", "")).strip() or "Unnamed",
            sheet_type=sheet_type,
            role=str(payload.get("role", "")),
            archetype=str(payload.get("archetype", "")),
            level_or_rank=str(payload.get("level_or_rank", "")),
            faction=str(payload.get("faction", "")),
            description=str(payload.get("description", "")),
            stats=stats,
            classic_attributes=classic,
            traits=[str(v) for v in payload.get("traits", []) if str(v).strip()],
            abilities=[str(v) for v in payload.get("abilities", []) if str(v).strip()],
            guaranteed_abilities=[
                CharacterSheetAbilityEntry.from_payload(entry)
                for entry in payload.get("guaranteed_abilities", [])
                if isinstance(entry, dict)
            ],
            equipment=[str(v) for v in payload.get("equipment", []) if str(v).strip()],
            weaknesses=[str(v) for v in payload.get("weaknesses", []) if str(v).strip()],
            temperament=str(payload.get("temperament", "")),
            loyalty=str(payload.get("loyalty", "")),
            fear=str(payload.get("fear", "")),
            desire=str(payload.get("desire", "")),
            social_style=str(payload.get("social_style", "")),
            speech_style=str(payload.get("speech_style", "")),
            notes=str(payload.get("notes", "")),
            state=state,
            guidance_strength=guidance_strength,
        )


class CharacterSheetPromptFormatter:
    """Converts optional sheets into concise prompt anchors."""

    def build_guidance_blocks(self, sheets: list[CharacterSheet], campaign_strength: GuidanceStrength = "light") -> list[str]:
        blocks: list[str] = []
        for sheet in sheets:
            anchors = [
                f"role={sheet.role or 'unspecified'}",
                f"archetype={sheet.archetype or 'unspecified'}",
                f"rank={sheet.level_or_rank or 'unspecified'}",
                f"temperament={sheet.temperament or 'unspecified'}",
                f"loyalty={sheet.loyalty or 'unspecified'}",
                f"social_style={sheet.social_style or 'unspecified'}",
                f"speech_style={sheet.speech_style or 'unspecified'}",
            ]
            if sheet.abilities:
                anchors.append(f"abilities={', '.join(sheet.abilities[:4])}")
            if sheet.guaranteed_abilities:
                anchors.append(
                    "guaranteed_loadout="
                    + ", ".join(f"{entry.type}:{entry.name}" for entry in sheet.guaranteed_abilities[:6])
                )
            if sheet.weaknesses:
                anchors.append(f"weaknesses={', '.join(sheet.weaknesses[:3])}")
            if sheet.state.current_condition:
                anchors.append(f"condition={sheet.state.current_condition}")
            if sheet.state.morale is not None:
                anchors.append(f"morale={sheet.state.morale}")
            if sheet.state.bond_to_player is not None:
                anchors.append(f"bond_to_player={sheet.state.bond_to_player}")
            intensity = sheet.guidance_strength if sheet.guidance_strength in {"light", "strong"} else campaign_strength
            label = {
                "main_character": "Main Character Guidance",
                "npc_or_mob": "NPC/Mob Guidance",
                "party_member": "Party Member Guidance",
                "minion_or_summon": "Minion/Summon Guidance",
            }[sheet.sheet_type]
            blocks.append(f"[{label}] {sheet.name}: strength={intensity}; " + "; ".join(anchors))
        return blocks
