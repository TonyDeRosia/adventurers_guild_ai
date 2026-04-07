"""Core entity models for campaign state.

These dataclasses are intentionally provider-agnostic so game logic,
model providers, and persistence can evolve independently.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Character:
    """Represents a player-controlled character."""

    id: str
    name: str
    char_class: str
    level: int = 1
    hp: int = 20
    max_hp: int = 20
    armor_class: int = 12
    attack_bonus: int = 3
    strength: int = 2
    agility: int = 2
    intellect: int = 2
    vitality: int = 2
    inventory: list[str] = field(default_factory=list)
    xp: int = 0
    equipped_item_id: str | None = None


@dataclass
class NPC:
    """Represents a non-player character and relationship state."""

    @dataclass
    class DynamicState:
        trust_toward_player: int = 0
        fear_toward_player: int = 0
        stress: int = 0
        hope: int = 0
        anger: int = 0
        loyalty: int = 0
        instability: int = 0

    @dataclass
    class MemoryEntry:
        event_type: str
        summary: str
        turn: int
        world_event_id: str | None = None
        player_action: str | None = None
        impact: dict[str, int] = field(default_factory=dict)
        tags: list[str] = field(default_factory=list)

    id: str
    name: str
    location_id: str
    disposition: int = 0
    relationship_tier: str = "neutral"
    notes: list[str] = field(default_factory=list)
    relationships: dict[str, int] = field(default_factory=dict)
    profile_id: str | None = None
    dynamic_state: DynamicState = field(default_factory=DynamicState)
    memory_log: list[MemoryEntry] = field(default_factory=list)
    unlocked_behaviors: list[str] = field(default_factory=list)
    applied_evolution_rules: list[str] = field(default_factory=list)


@dataclass
class Location:
    """Represents a world location."""

    id: str
    name: str
    description: str
    connections: list[str] = field(default_factory=list)


@dataclass
class Quest:
    """Represents a quest and completion state."""

    id: str
    title: str
    description: str
    status: str = "active"
    objectives: list[str] = field(default_factory=list)
    availability: dict[str, Any] = field(default_factory=dict)


@dataclass
class CampaignSettings:
    """Configurable campaign behavior toggles."""

    @dataclass
    class ContentSettings:
        """Narration-layer content controls configured per campaign."""

        tone: str = "heroic"
        maturity_level: str = "standard"
        thematic_flags: list[str] = field(default_factory=lambda: ["adventure", "mystery"])

    profile: str = "classic_fantasy"
    mature_content_enabled: bool = False
    narration_tone: str = "heroic"
    image_generation_enabled: bool = False
    content_settings: ContentSettings = field(default_factory=ContentSettings)


@dataclass
class CampaignWorldMeta:
    """World-building metadata chosen during campaign creation."""

    world_name: str = "Moonfall"
    world_theme: str = "classic fantasy"
    starting_location_name: str = "Moonfall Town"
    tone: str = "heroic"
    premise: str = ""
    player_concept: str = ""


@dataclass
class SessionSummary:
    """Compact reusable summary for a campaign milestone."""

    turn: int
    trigger: str
    summary: str
    location_id: str
    quest_ids: list[str] = field(default_factory=list)
    npc_ids: list[str] = field(default_factory=list)
    world_flags: list[str] = field(default_factory=list)


@dataclass
class LongTermMemoryEntry:
    """Structured long-term memory item used during retrieval."""

    id: str
    category: str
    text: str
    location_id: str | None = None
    quest_id: str | None = None
    npc_id: str | None = None
    turn: int = 0
    weight: int = 1


@dataclass
class ConversationTurn:
    """Persisted chat-style conversation turn for local sessions."""

    turn: int
    player_input: str
    system_messages: list[str] = field(default_factory=list)
    narrator_response: str = ""
    requested_mode: str = "play"
    location_id: str = ""


@dataclass
class CampaignState:
    """Top-level persistent campaign state."""

    campaign_id: str
    campaign_name: str
    turn_count: int
    current_location_id: str
    player: Character
    npcs: dict[str, NPC]
    locations: dict[str, Location]
    quests: dict[str, Quest]
    world_flags: dict[str, bool] = field(default_factory=dict)
    faction_reputation: dict[str, int] = field(default_factory=dict)
    quest_outcomes: dict[str, str] = field(default_factory=dict)
    world_events: list[str] = field(default_factory=list)
    combat_effects: dict[str, Any] = field(default_factory=dict)
    active_enemy_id: str | None = None
    active_enemy_hp: int | None = None
    active_dialogue_npc_id: str | None = None
    active_dialogue_node_id: str | None = None
    event_log: list[str] = field(default_factory=list)
    recent_memory: list[str] = field(default_factory=list)
    long_term_memory: list[LongTermMemoryEntry] = field(default_factory=list)
    session_summaries: list[SessionSummary] = field(default_factory=list)
    unresolved_plot_threads: list[str] = field(default_factory=list)
    important_world_facts: list[str] = field(default_factory=list)
    conversation_turns: list[ConversationTurn] = field(default_factory=list)
    settings: CampaignSettings = field(default_factory=CampaignSettings)
    world_meta: CampaignWorldMeta = field(default_factory=CampaignWorldMeta)

    def to_dict(self) -> dict[str, Any]:
        """Serialize campaign state to a dictionary for JSON storage."""

        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CampaignState":
        """Deserialize from JSON payload.

        Assumes payload shape generated by `to_dict`.
        """

        npcs: dict[str, NPC] = {}
        for key, raw in payload["npcs"].items():
            dynamic_state = NPC.DynamicState(**raw.get("dynamic_state", {}))
            memory_log = [NPC.MemoryEntry(**entry) for entry in raw.get("memory_log", [])]
            npc_payload = dict(raw)
            npc_payload["dynamic_state"] = dynamic_state
            npc_payload["memory_log"] = memory_log
            npcs[key] = NPC(**npc_payload)
        for npc in npcs.values():
            if not npc.relationship_tier:
                if npc.disposition >= 60:
                    npc.relationship_tier = "loyal"
                elif npc.disposition >= 20:
                    npc.relationship_tier = "friendly"
                elif npc.disposition <= -20:
                    npc.relationship_tier = "hostile"
                else:
                    npc.relationship_tier = "neutral"

        return cls(
            campaign_id=payload["campaign_id"],
            campaign_name=payload["campaign_name"],
            turn_count=payload["turn_count"],
            current_location_id=payload["current_location_id"],
            player=Character(**payload["player"]),
            npcs=npcs,
            locations={k: Location(**v) for k, v in payload["locations"].items()},
            quests={k: Quest(**v) for k, v in payload["quests"].items()},
            world_flags={k: bool(v) for k, v in payload.get("world_flags", {}).items()},
            faction_reputation={k: int(v) for k, v in payload.get("faction_reputation", {}).items()},
            quest_outcomes={k: str(v) for k, v in payload.get("quest_outcomes", {}).items()},
            world_events=[str(v) for v in payload.get("world_events", [])],
            combat_effects=dict(payload.get("combat_effects", {})),
            active_enemy_id=payload.get("active_enemy_id"),
            active_enemy_hp=payload.get("active_enemy_hp"),
            active_dialogue_npc_id=payload.get("active_dialogue_npc_id"),
            active_dialogue_node_id=payload.get("active_dialogue_node_id"),
            event_log=payload.get("event_log", []),
            recent_memory=[str(v) for v in payload.get("recent_memory", [])],
            long_term_memory=[LongTermMemoryEntry(**v) for v in payload.get("long_term_memory", [])],
            session_summaries=[SessionSummary(**v) for v in payload.get("session_summaries", [])],
            unresolved_plot_threads=[str(v) for v in payload.get("unresolved_plot_threads", [])],
            important_world_facts=[str(v) for v in payload.get("important_world_facts", [])],
            conversation_turns=[ConversationTurn(**v) for v in payload.get("conversation_turns", [])],
            settings=cls._settings_from_payload(payload.get("settings", {})),
            world_meta=cls._world_meta_from_payload(payload.get("world_meta"), payload),
        )

    @staticmethod
    def _settings_from_payload(raw_settings: dict[str, Any]) -> CampaignSettings:
        """Deserialize settings while preserving backward compatibility."""

        settings = dict(raw_settings)
        raw_content = settings.pop("content_settings", None)
        content_settings: CampaignSettings.ContentSettings

        if raw_content is None:
            content_settings = CampaignSettings.ContentSettings(
                tone=settings.get("narration_tone", "heroic"),
                maturity_level="mature" if settings.get("mature_content_enabled") else "standard",
            )
        else:
            content_settings = CampaignSettings.ContentSettings(
                tone=raw_content.get("tone", settings.get("narration_tone", "heroic")),
                maturity_level=raw_content.get(
                    "maturity_level", "mature" if settings.get("mature_content_enabled") else "standard"
                ),
                thematic_flags=list(raw_content.get("thematic_flags", ["adventure", "mystery"])),
            )

        settings["content_settings"] = content_settings
        return CampaignSettings(**settings)

    @staticmethod
    def _world_meta_from_payload(raw_world_meta: dict[str, Any] | None, payload: dict[str, Any]) -> CampaignWorldMeta:
        """Deserialize world metadata while preserving backward compatibility."""

        current_location = payload.get("locations", {}).get(payload.get("current_location_id", ""), {})
        fallback_location_name = str(current_location.get("name", "Moonfall Town"))
        if raw_world_meta is None:
            return CampaignWorldMeta(
                world_name="Moonfall",
                world_theme=str(payload.get("settings", {}).get("profile", "classic_fantasy")).replace("_", " "),
                starting_location_name=fallback_location_name,
                tone=str(payload.get("settings", {}).get("narration_tone", "heroic")),
                premise="",
                player_concept="",
            )
        return CampaignWorldMeta(
            world_name=str(raw_world_meta.get("world_name", "Moonfall")),
            world_theme=str(raw_world_meta.get("world_theme", "classic fantasy")),
            starting_location_name=str(raw_world_meta.get("starting_location_name", fallback_location_name)),
            tone=str(raw_world_meta.get("tone", payload.get("settings", {}).get("narration_tone", "heroic"))),
            premise=str(raw_world_meta.get("premise", "")),
            player_concept=str(raw_world_meta.get("player_concept", "")),
        )
