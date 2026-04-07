"""Core entity models for campaign state.

These dataclasses are intentionally provider-agnostic so game logic,
model providers, and persistence can evolve independently.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from engine.character_sheets import CharacterSheet, GuidanceStrength


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
    energy_or_mana: int = 10
    defense: int = 10
    speed: int = 10
    magic: int = 10
    willpower: int = 10
    presence: int = 10
    role: str = ""
    archetype: str = ""
    classic_attributes: dict[str, int | None] = field(default_factory=dict)
    inventory: list[str] = field(default_factory=list)
    xp: int = 0
    equipped_item_id: str | None = None


@dataclass
class NPC:
    """Represents a non-player character and relationship state."""

    @dataclass
    class PersonalityNodes:
        role: str = ""
        temperament: str = ""
        morals: str = ""
        social_style: str = ""
        fears: list[str] = field(default_factory=list)
        desires: list[str] = field(default_factory=list)
        loyalties: list[str] = field(default_factory=list)
        secrets: list[str] = field(default_factory=list)
        aggression: str = ""
        speech_style: str = ""
        decision_bias: str = ""
        faction_alignment: str = ""

    @dataclass
    class DynamicState:
        trust_toward_player: int = 0
        fear_toward_player: int = 0
        stress: int = 0
        hope: int = 0
        anger: int = 0
        loyalty: int = 0
        instability: int = 0
        suspicion: int = 0
        attraction: int = 0
        current_mood: str = "neutral"
        memory_tags: list[str] = field(default_factory=list)

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
    personality_archetype: str | None = None
    personality_nodes: PersonalityNodes | None = None
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
    image_generation_enabled: bool = True
    campaign_auto_visuals_enabled: bool = True
    suggested_moves_enabled: bool = False
    player_suggested_moves_override: bool | None = None
    content_settings: ContentSettings = field(default_factory=ContentSettings)

    def suggested_moves_active(self) -> bool:
        if self.player_suggested_moves_override is None:
            return self.suggested_moves_enabled
        return bool(self.player_suggested_moves_override)


@dataclass
class CampaignWorldMeta:
    """World-building metadata chosen during campaign creation."""

    world_name: str = "Untitled World"
    world_theme: str = "classic fantasy"
    starting_location_name: str = "Starting Area"
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
class CampaignCanonState:
    """Static or semi-static campaign canon facts."""

    campaign_premise: str = ""
    world_rules: list[str] = field(default_factory=list)
    custom_narrator_rules: list[dict[str, str]] = field(default_factory=list)
    lore: list[str] = field(default_factory=list)
    character_sheet_ids: list[str] = field(default_factory=list)
    faction_setup: dict[str, int] = field(default_factory=dict)
    item_definitions_version: str = "default"
    spell_definitions_version: str = "default"


@dataclass
class CampaignRuntimeState:
    """Dynamic campaign runtime state that must remain campaign-scoped."""

    player_core: dict[str, Any] = field(default_factory=dict)
    inventory: list[str] = field(default_factory=list)
    equipment: dict[str, str | None] = field(default_factory=dict)
    inventory_state: dict[str, Any] = field(default_factory=dict)
    spellbook: list[dict[str, Any]] = field(default_factory=list)
    abilities_learned: list[str] = field(default_factory=list)
    current_location_id: str = ""
    discovered_locations: list[str] = field(default_factory=list)
    quest_state: dict[str, str] = field(default_factory=dict)
    npc_relationships: dict[str, dict[str, Any]] = field(default_factory=dict)
    party_state: dict[str, Any] = field(default_factory=dict)
    status_effects: list[str] = field(default_factory=list)
    faction_changes: dict[str, int] = field(default_factory=dict)
    world_state: dict[str, Any] = field(default_factory=dict)
    scene_visual_state: dict[str, Any] = field(default_factory=dict)
    scene_state: dict[str, Any] = field(default_factory=dict)
    last_narration: str = ""


@dataclass
class CampaignRecentMemoryState:
    """Recent campaign turn memory and summaries."""

    last_major_actions: list[str] = field(default_factory=list)
    last_major_consequences: list[str] = field(default_factory=list)
    recent_dialogue: list[str] = field(default_factory=list)
    recent_discoveries: list[str] = field(default_factory=list)
    running_summary: str = ""


@dataclass
class CampaignSceneState:
    """Persistent immediate scene continuity for gameplay turns."""

    location_id: str | None = None
    location_name: str | None = None
    scene_summary: str = ""
    visible_entities: list[str] = field(default_factory=list)
    damaged_objects: list[str] = field(default_factory=list)
    altered_environment: list[str] = field(default_factory=list)
    active_effects: list[str] = field(default_factory=list)
    recent_consequences: list[str] = field(default_factory=list)
    last_player_action: str = ""
    last_immediate_result: str = ""


@dataclass
class CampaignStructuredState:
    """Campaign-scoped canonical + runtime + recent memory structures."""

    canon: CampaignCanonState = field(default_factory=CampaignCanonState)
    runtime: CampaignRuntimeState = field(default_factory=CampaignRuntimeState)
    recent_turn_memory: CampaignRecentMemoryState = field(default_factory=CampaignRecentMemoryState)


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
    character_sheets: list[CharacterSheet] = field(default_factory=list)
    character_sheet_guidance_strength: GuidanceStrength = "light"
    structured_state: CampaignStructuredState = field(default_factory=CampaignStructuredState)

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
            personality_nodes_raw = raw.get("personality_nodes")
            personality_nodes = (
                NPC.PersonalityNodes(
                    role=str(personality_nodes_raw.get("role", "")),
                    temperament=str(personality_nodes_raw.get("temperament", "")),
                    morals=str(personality_nodes_raw.get("morals", "")),
                    social_style=str(personality_nodes_raw.get("social_style", "")),
                    fears=[str(v) for v in personality_nodes_raw.get("fears", [])],
                    desires=[str(v) for v in personality_nodes_raw.get("desires", [])],
                    loyalties=[str(v) for v in personality_nodes_raw.get("loyalties", [])],
                    secrets=[str(v) for v in personality_nodes_raw.get("secrets", [])],
                    aggression=str(personality_nodes_raw.get("aggression", "")),
                    speech_style=str(personality_nodes_raw.get("speech_style", "")),
                    decision_bias=str(personality_nodes_raw.get("decision_bias", "")),
                    faction_alignment=str(personality_nodes_raw.get("faction_alignment", "")),
                )
                if isinstance(personality_nodes_raw, dict)
                else None
            )
            npc_payload = dict(raw)
            npc_payload["dynamic_state"] = dynamic_state
            npc_payload["memory_log"] = memory_log
            npc_payload["personality_nodes"] = personality_nodes
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
            character_sheets=[CharacterSheet.from_payload(entry) for entry in payload.get("character_sheets", []) if isinstance(entry, dict)],
            character_sheet_guidance_strength=cls._sheet_strength_from_payload(payload.get("character_sheet_guidance_strength", "light")),
            structured_state=cls._structured_state_from_payload(payload.get("structured_state"), payload),
        )

    @staticmethod
    def _sheet_strength_from_payload(raw_strength: Any) -> GuidanceStrength:
        strength = str(raw_strength or "light").strip().lower()
        if strength not in {"light", "strong"}:
            return "light"
        return strength  # type: ignore[return-value]

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
        settings["image_generation_enabled"] = bool(settings.get("image_generation_enabled", True))
        settings["campaign_auto_visuals_enabled"] = bool(settings.get("campaign_auto_visuals_enabled", True))
        settings["suggested_moves_enabled"] = bool(settings.get("suggested_moves_enabled", False))
        raw_override = settings.get("player_suggested_moves_override")
        settings["player_suggested_moves_override"] = None if raw_override is None else bool(raw_override)
        return CampaignSettings(**settings)

    @staticmethod
    def _world_meta_from_payload(raw_world_meta: dict[str, Any] | None, payload: dict[str, Any]) -> CampaignWorldMeta:
        """Deserialize world metadata while preserving backward compatibility."""

        current_location = payload.get("locations", {}).get(payload.get("current_location_id", ""), {})
        fallback_location_name = str(current_location.get("name", "Starting Area"))
        if raw_world_meta is None:
            return CampaignWorldMeta(
                world_name="Untitled World",
                world_theme=str(payload.get("settings", {}).get("profile", "classic_fantasy")).replace("_", " "),
                starting_location_name=fallback_location_name,
                tone=str(payload.get("settings", {}).get("narration_tone", "heroic")),
                premise="",
                player_concept="",
            )
        return CampaignWorldMeta(
            world_name=str(raw_world_meta.get("world_name", "Untitled World")),
            world_theme=str(raw_world_meta.get("world_theme", "classic fantasy")),
            starting_location_name=str(raw_world_meta.get("starting_location_name", fallback_location_name)),
            tone=str(raw_world_meta.get("tone", payload.get("settings", {}).get("narration_tone", "heroic"))),
            premise=str(raw_world_meta.get("premise", "")),
            player_concept=str(raw_world_meta.get("player_concept", "")),
        )

    @staticmethod
    def _structured_state_from_payload(raw_structured: dict[str, Any] | None, payload: dict[str, Any]) -> CampaignStructuredState:
        if not isinstance(raw_structured, dict):
            return CampaignState._build_structured_state_from_legacy_payload(payload)
        raw_canon = raw_structured.get("canon", {})
        raw_runtime = raw_structured.get("runtime", {})
        raw_recent = raw_structured.get("recent_turn_memory", {})
        return CampaignStructuredState(
            canon=CampaignCanonState(
                campaign_premise=str(raw_canon.get("campaign_premise", "")),
                world_rules=[str(v) for v in raw_canon.get("world_rules", [])],
                custom_narrator_rules=[
                    {
                        "id": str(entry.get("id", "")).strip() or f"rule_{index}",
                        "text": str(entry.get("text", "")).strip(),
                    }
                    for index, entry in enumerate(raw_canon.get("custom_narrator_rules", []))
                    if isinstance(entry, dict) and str(entry.get("text", "")).strip()
                ],
                lore=[str(v) for v in raw_canon.get("lore", [])],
                character_sheet_ids=[str(v) for v in raw_canon.get("character_sheet_ids", [])],
                faction_setup={str(k): int(v) for k, v in raw_canon.get("faction_setup", {}).items()},
                item_definitions_version=str(raw_canon.get("item_definitions_version", "default")),
                spell_definitions_version=str(raw_canon.get("spell_definitions_version", "default")),
            ),
            runtime=CampaignRuntimeState(
                player_core=dict(raw_runtime.get("player_core", {})),
                inventory=[str(v) for v in raw_runtime.get("inventory", [])],
                equipment={str(k): (None if v is None else str(v)) for k, v in raw_runtime.get("equipment", {}).items()},
                inventory_state=dict(raw_runtime.get("inventory_state", {})),
                spellbook=CampaignState._spellbook_from_payload(raw_runtime.get("spellbook", [])),
                abilities_learned=[str(v) for v in raw_runtime.get("abilities_learned", [])],
                current_location_id=str(raw_runtime.get("current_location_id", "")),
                discovered_locations=[str(v) for v in raw_runtime.get("discovered_locations", [])],
                quest_state={str(k): str(v) for k, v in raw_runtime.get("quest_state", {}).items()},
                npc_relationships={str(k): dict(v) for k, v in raw_runtime.get("npc_relationships", {}).items()},
                party_state=dict(raw_runtime.get("party_state", {})),
                status_effects=[str(v) for v in raw_runtime.get("status_effects", [])],
                faction_changes={str(k): int(v) for k, v in raw_runtime.get("faction_changes", {}).items()},
                world_state=dict(raw_runtime.get("world_state", {})),
                scene_visual_state=dict(raw_runtime.get("scene_visual_state", {})),
                scene_state=CampaignState._scene_state_from_payload(raw_runtime.get("scene_state", {}), payload),
                last_narration=str(raw_runtime.get("last_narration", "")),
            ),
            recent_turn_memory=CampaignRecentMemoryState(
                last_major_actions=[str(v) for v in raw_recent.get("last_major_actions", [])],
                last_major_consequences=[str(v) for v in raw_recent.get("last_major_consequences", [])],
                recent_dialogue=[str(v) for v in raw_recent.get("recent_dialogue", [])],
                recent_discoveries=[str(v) for v in raw_recent.get("recent_discoveries", [])],
                running_summary=str(raw_recent.get("running_summary", "")),
            ),
        )

    @staticmethod
    def _build_structured_state_from_legacy_payload(payload: dict[str, Any]) -> CampaignStructuredState:
        world_meta = payload.get("world_meta", {})
        character_sheets = payload.get("character_sheets", [])
        locations = payload.get("locations", {})
        discovered_locations = [str(key) for key in locations.keys()]
        return CampaignStructuredState(
            canon=CampaignCanonState(
                campaign_premise=str(world_meta.get("premise", "")),
                character_sheet_ids=[
                    str(sheet.get("id", ""))
                    for sheet in character_sheets
                    if isinstance(sheet, dict) and str(sheet.get("id", "")).strip()
                ],
                faction_setup={str(k): int(v) for k, v in payload.get("faction_reputation", {}).items()},
            ),
            runtime=CampaignRuntimeState(
                player_core=dict(payload.get("player", {})),
                inventory=[str(v) for v in payload.get("player", {}).get("inventory", [])],
                equipment={"equipped_item_id": payload.get("player", {}).get("equipped_item_id")},
                inventory_state={},
                current_location_id=str(payload.get("current_location_id", "")),
                discovered_locations=discovered_locations,
                quest_state={str(k): str(v.get("status", "active")) for k, v in payload.get("quests", {}).items()},
                npc_relationships={
                    str(k): {
                        "disposition": int(v.get("disposition", 0)),
                        "relationship_tier": str(v.get("relationship_tier", "neutral")),
                    }
                    for k, v in payload.get("npcs", {}).items()
                    if isinstance(v, dict)
                },
                faction_changes={str(k): int(v) for k, v in payload.get("faction_reputation", {}).items()},
                world_state={
                    "world_flags": dict(payload.get("world_flags", {})),
                    "world_events": [str(v) for v in payload.get("world_events", [])],
                },
                scene_state=CampaignState._scene_state_from_payload({}, payload),
                last_narration="",
            ),
            recent_turn_memory=CampaignRecentMemoryState(
                last_major_actions=[str(v) for v in payload.get("recent_memory", [])[-6:]],
                last_major_consequences=[str(v) for v in payload.get("event_log", [])[-6:]],
                running_summary=str(payload.get("session_summaries", [{}])[-1].get("summary", "")) if payload.get("session_summaries") else "",
            ),
        )

    @staticmethod
    def _spellbook_from_payload(raw_spellbook: Any) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for index, entry in enumerate(raw_spellbook if isinstance(raw_spellbook, list) else []):
            if isinstance(entry, dict):
                clean_name = str(entry.get("name", "")).strip()
                if not clean_name:
                    continue
                clean_type = str(entry.get("type", "ability")).strip().lower()
                if clean_type not in {"spell", "skill", "ability", "passive"}:
                    clean_type = "ability"
                entries.append(
                    {
                        "id": str(entry.get("id", "")).strip() or f"sb_{index}_{clean_name.lower().replace(' ', '_')}",
                        "name": clean_name,
                        "type": clean_type,
                        "description": str(entry.get("description", "")).strip(),
                        "cost_or_resource": str(entry.get("cost_or_resource", "")).strip(),
                        "cooldown": str(entry.get("cooldown", "")).strip(),
                        "tags": [str(tag).strip() for tag in entry.get("tags", []) if str(tag).strip()],
                        "notes": str(entry.get("notes", "")).strip(),
                    }
                )
                continue
            clean_name = str(entry).strip()
            if not clean_name:
                continue
            entries.append(
                {
                    "id": f"sb_{index}_{clean_name.lower().replace(' ', '_')}",
                    "name": clean_name,
                    "type": "ability",
                    "description": "",
                    "cost_or_resource": "",
                    "cooldown": "",
                    "tags": [],
                    "notes": "",
                }
            )
        return entries

    @staticmethod
    def _scene_state_from_payload(raw_scene_state: Any, payload: dict[str, Any]) -> dict[str, Any]:
        state = dict(raw_scene_state) if isinstance(raw_scene_state, dict) else {}
        current_location_id = str(payload.get("current_location_id", "")).strip()
        location_payload = payload.get("locations", {}).get(current_location_id, {}) if isinstance(payload.get("locations"), dict) else {}
        location_name = str(location_payload.get("name", "")).strip() or None
        world_meta = payload.get("world_meta", {}) if isinstance(payload.get("world_meta"), dict) else {}
        world_name = str(world_meta.get("world_name", "")).strip()
        world_theme = str(world_meta.get("world_theme", "")).strip()
        premise = str(world_meta.get("premise", "")).strip()
        visible_entities = [
            str(entry.get("name", "")).strip()
            for entry in (payload.get("npcs", {}).values() if isinstance(payload.get("npcs"), dict) else [])
            if isinstance(entry, dict) and str(entry.get("location_id", "")).strip() == current_location_id and str(entry.get("name", "")).strip()
        ]
        seeded_summary = str(state.get("scene_summary", "")).strip()
        if not seeded_summary:
            summary_parts = [f"You are at {location_name or 'the current area'}."]
            if world_name:
                summary_parts.append(f"World: {world_name}.")
            if world_theme:
                summary_parts.append(f"Theme: {world_theme}.")
            if premise:
                summary_parts.append(premise[:160])
            seeded_summary = " ".join(summary_parts)
        return asdict(
            CampaignSceneState(
                location_id=str(state.get("location_id", current_location_id)).strip() or None,
                location_name=str(state.get("location_name", location_name or "")).strip() or location_name,
                scene_summary=seeded_summary,
                visible_entities=[str(v) for v in state.get("visible_entities", visible_entities) if str(v).strip()],
                damaged_objects=[str(v) for v in state.get("damaged_objects", []) if str(v).strip()],
                altered_environment=[str(v) for v in state.get("altered_environment", []) if str(v).strip()],
                active_effects=[str(v) for v in state.get("active_effects", []) if str(v).strip()],
                recent_consequences=[str(v) for v in state.get("recent_consequences", []) if str(v).strip()],
                last_player_action=str(state.get("last_player_action", "")),
                last_immediate_result=str(state.get("last_immediate_result", "")),
            )
        )
