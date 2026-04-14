"""Campaign-scoped structured state orchestration for GM context and persistence."""

from __future__ import annotations

from dataclasses import asdict

from engine.character_sheets import CharacterSheet, CharacterSheetClassicAttributes, CharacterSheetStats
from engine.entities import CampaignSceneState, CampaignState
from engine.spellbook import normalize_abilities_collection


class CampaignStateOrchestrator:
    """Maintains structured campaign canon/runtime/memory and assembles GM context."""

    def __init__(self, recent_limit: int = 8) -> None:
        self.recent_limit = recent_limit

    def ensure_initialized(self, state: CampaignState) -> None:
        structured = state.structured_state
        self._ensure_main_character_sheet(state)
        if not structured.canon.campaign_premise:
            structured.canon.campaign_premise = state.world_meta.premise
        if not structured.canon.character_sheet_ids and state.character_sheets:
            structured.canon.character_sheet_ids = [sheet.id for sheet in state.character_sheets if sheet.id]
        if not structured.runtime.current_location_id:
            structured.runtime.current_location_id = state.current_location_id
        if not isinstance(structured.runtime.scene_state, dict):
            structured.runtime.scene_state = asdict(CampaignSceneState())
        scene_state = structured.runtime.scene_state
        structured.runtime.abilities = self._normalize_spellbook(getattr(structured.runtime, "abilities", structured.runtime.spellbook))
        structured.runtime.spellbook = list(structured.runtime.abilities)
        scene_state.setdefault("location_id", state.current_location_id or None)
        location = state.locations.get(state.current_location_id)
        scene_state.setdefault("location_name", location.name if location else None)
        scene_state.setdefault("scene_summary", "")
        scene_state.setdefault("visible_entities", [])
        scene_state.setdefault("damaged_objects", [])
        scene_state.setdefault("altered_environment", [])
        scene_state.setdefault("active_effects", [])
        scene_state.setdefault("recent_consequences", [])
        scene_state.setdefault("last_player_action", "")
        scene_state.setdefault("last_immediate_result", "")
        scene_state.setdefault("scene_actors", [])
        scene_state.setdefault("lightweight_npcs", [])
        scene_state.setdefault("last_target_actor_id", "")
        scene_state.setdefault("npc_conditions", {})
        scene_state.setdefault("enemy_conditions", {})
        scene_state.setdefault("environment_consequences", [])

    def update_runtime_state(self, state: CampaignState, *, action: str, system_messages: list[str], narrative: str) -> dict[str, bool]:
        self.ensure_initialized(state)
        runtime = state.structured_state.runtime
        runtime.player_core = {
            "name": state.player.name,
            "class": state.player.char_class,
            "level": state.player.level,
            "hp": state.player.hp,
            "max_hp": state.player.max_hp,
            "xp": state.player.xp,
            "attack_bonus": state.player.attack_bonus,
            "energy_or_mana": state.player.energy_or_mana,
        }
        # Ownership rule: inventory is player-managed reference data by default.
        # Runtime/system reads remain available, but we avoid rewriting player-authored
        # inventory_state during normal gameplay turns.
        runtime.inventory = self._flatten_inventory_names(runtime.inventory_state) or list(state.player.inventory)
        runtime.equipment = {"equipped_item_id": state.player.equipped_item_id}
        if not runtime.inventory_state:
            runtime.inventory_state = self._build_inventory_state(state)
        runtime.abilities = self._normalize_spellbook(getattr(runtime, "abilities", runtime.spellbook))
        runtime.spellbook = list(runtime.abilities)
        runtime.abilities_learned = sorted(set(runtime.abilities_learned + self._infer_abilities_from_messages(system_messages)))
        runtime.current_location_id = state.current_location_id
        runtime.discovered_locations = sorted(set(runtime.discovered_locations + list(state.locations.keys()) + [state.current_location_id]))
        runtime.quest_state = {quest_id: quest.status for quest_id, quest in state.quests.items()}
        runtime.npc_relationships = {
            npc_id: {
                "name": npc.name,
                "disposition": npc.disposition,
                "relationship_tier": npc.relationship_tier,
                "trust": npc.dynamic_state.trust_toward_player,
                "fear": npc.dynamic_state.fear_toward_player,
                "suspicion": npc.dynamic_state.suspicion,
                "loyalty": npc.dynamic_state.loyalty,
                "location_id": npc.location_id,
            }
            for npc_id, npc in state.npcs.items()
        }
        runtime.party_state = {
            "active_enemy_id": state.active_enemy_id,
            "active_enemy_hp": state.active_enemy_hp,
            "minions": runtime.party_state.get("minions", []),
        }
        runtime.status_effects = sorted([key for key, enabled in state.combat_effects.items() if bool(enabled)])
        runtime.faction_changes = dict(state.faction_reputation)
        runtime.world_state = {
            "world_flags": dict(state.world_flags),
            "quest_outcomes": dict(state.quest_outcomes),
            "world_events": list(state.world_events[-24:]),
        }

        recent = state.structured_state.recent_turn_memory
        recent.last_major_actions = self._append_bounded(recent.last_major_actions, f"T{state.turn_count} action: {action.strip()}")
        for message in system_messages[-3:]:
            recent.last_major_consequences = self._append_bounded(recent.last_major_consequences, message)
            if "discover" in message.lower() or "find" in message.lower():
                recent.recent_discoveries = self._append_bounded(recent.recent_discoveries, message)
        if state.active_dialogue_npc_id:
            recent.recent_dialogue = self._append_bounded(recent.recent_dialogue, f"{state.active_dialogue_npc_id}: {narrative[:120]}")
        if state.session_summaries:
            recent.running_summary = state.session_summaries[-1].summary

        updates = {
            "inventory": True,
            "spellbook": True,
            "quests": True,
            "npc_states": True,
            "world_state": True,
            "recent_memory": True,
        }
        print(
            "[campaign-memory] state_updated "
            f"inventory={str(updates['inventory']).lower()} "
            f"spellbook={str(updates['spellbook']).lower()} "
            f"quests={str(updates['quests']).lower()}"
        )
        print(f"[spellbook] current_entry_count={len(runtime.spellbook)}")
        return updates

    def set_scene_visual_state(self, state: CampaignState, payload: dict[str, object] | None) -> None:
        state.structured_state.runtime.scene_visual_state = dict(payload or {})

    def build_gm_context(self, state: CampaignState) -> str:
        self.ensure_initialized(state)
        structured = state.structured_state
        main_sheet = next((sheet for sheet in state.character_sheets if sheet.sheet_type == "main_character"), None)
        nearby_npcs = [
            entry
            for entry in structured.runtime.npc_relationships.values()
            if str(entry.get("location_id", "")) == state.current_location_id
        ]
        scene_actor_npcs = [
            actor
            for actor in structured.runtime.scene_state.get("scene_actors", [])
            if isinstance(actor, dict)
            and bool(actor.get("visible", True))
            and str(actor.get("location_id", state.current_location_id)) == state.current_location_id
        ]
        nearby_npc_count = len(nearby_npcs) + len(scene_actor_npcs)
        active_quests = [qid for qid, status in structured.runtime.quest_state.items() if status == "active"]
        print(f"[gm-context-audit] campaign={state.campaign_id}")
        print(f"[gm-context-audit] world_name={state.world_meta.world_name}")
        print(f"[gm-context-audit] premise_present={str(bool(structured.canon.campaign_premise.strip())).lower()}")
        print(f"[gm-context-audit] location={structured.runtime.current_location_id}")
        print(f"[gm-context-audit] player_core_present={str(bool(structured.runtime.player_core)).lower()}")
        print(f"[gm-context-audit] main_sheet_present={str(main_sheet is not None).lower()}")
        print(f"[gm-context-audit] inventory_items={len(structured.runtime.inventory)}")
        print(f"[gm-context-audit] inventory_state_items={len(structured.runtime.inventory_state.get('items', []))}")
        print(f"[gm-context-audit] spellbook_entries={len(structured.runtime.spellbook)}")
        print(f"[gm-context-audit] active_quests={len(active_quests)}")
        print(f"[gm-context-audit] npc_count={nearby_npc_count}")
        print(f"[gm-context-audit] minion_count={len(structured.runtime.party_state.get('minions', []))}")
        print(f"[gm-context-audit] recent_turn_actions={len(structured.recent_turn_memory.last_major_actions)}")
        print(f"[gm-context-audit] custom_narrator_rules={len(structured.canon.custom_narrator_rules)}")
        return (
            "[Authoritative Campaign State]\n"
            "Treat the structured campaign state below as source-of-truth over stylistic improvisation.\n"
            "Player capabilities must respect the character sheet unless learning mode is enabled.\n"
            "Do not treat player self-claims about stats/rank as canon unless validated by this state.\n"
            f"Canon: {asdict(structured.canon)}\n"
            f"Runtime: {{'player_core': {structured.runtime.player_core}, 'inventory': {structured.runtime.inventory}, "
            f"'inventory_state': {structured.runtime.inventory_state}, 'equipment': {structured.runtime.equipment}, 'spellbook': {structured.runtime.spellbook}, "
            f"'abilities_learned': {structured.runtime.abilities_learned}, 'current_location_id': '{structured.runtime.current_location_id}', "
            f"'active_quests': {active_quests}, 'nearby_npcs': {nearby_npcs}, 'scene_actors': {scene_actor_npcs}, "
            f"'party_state': {structured.runtime.party_state}, 'status_effects': {structured.runtime.status_effects}, "
            f"'faction_changes': {structured.runtime.faction_changes}, 'world_state': {structured.runtime.world_state}, "
            f"'scene_visual_state': {structured.runtime.scene_visual_state}}}\n"
            f"Recent Turn Memory: {asdict(structured.recent_turn_memory)}"
        )

    def _append_bounded(self, entries: list[str], value: str) -> list[str]:
        clean = value.strip()
        if not clean:
            return entries
        updated = entries + [clean]
        return updated[-self.recent_limit :]

    def _infer_abilities_from_messages(self, system_messages: list[str]) -> list[str]:
        abilities: list[str] = []
        for message in system_messages:
            lowered = message.lower()
            if "focused ability" in lowered:
                abilities.append("focused_ability")
            if "ranger's charm" in lowered:
                abilities.append("rangers_charm_attunement")
        return abilities

    def _build_inventory_state(self, state: CampaignState) -> dict[str, object]:
        categories: dict[str, list[str]] = {
            "items": [],
            "weapons": [],
            "armor": [],
            "consumables": [],
            "key_items": [],
        }
        for item_id in state.player.inventory:
            label = str(item_id)
            lowered = label.lower()
            if any(token in lowered for token in ["sword", "blade", "bow", "axe", "staff"]):
                categories["weapons"].append(label)
            elif any(token in lowered for token in ["armor", "shield", "helm", "mail"]):
                categories["armor"].append(label)
            elif any(token in lowered for token in ["draught", "potion", "elixir"]):
                categories["consumables"].append(label)
            elif any(token in lowered for token in ["key", "sigil", "relic", "lantern"]):
                categories["key_items"].append(label)
            else:
                categories["items"].append(label)
        state_payload = {
            **categories,
            "entries": [
                {"id": f"inv_{index}", "name": item_id, "category": self._category_for_item(item_id), "quantity": 1, "notes": ""}
                for index, item_id in enumerate(state.player.inventory)
            ],
            "currency": {"gold": 0, "silver": 0, "copper": 0},
            "equipped": {"equipped_item_id": state.player.equipped_item_id},
        }
        return state_payload

    def _category_for_item(self, item_id: str) -> str:
        lowered = str(item_id or "").lower()
        if any(token in lowered for token in ["sword", "blade", "bow", "axe", "staff"]):
            return "weapons"
        if any(token in lowered for token in ["armor", "shield", "helm", "mail"]):
            return "armor"
        if any(token in lowered for token in ["draught", "potion", "elixir"]):
            return "consumables"
        if any(token in lowered for token in ["key", "sigil", "relic", "lantern"]):
            return "key_items"
        return "items"

    def _flatten_inventory_names(self, inventory_state: dict[str, object] | None) -> list[str]:
        if not isinstance(inventory_state, dict):
            return []
        names: list[str] = []
        for entry in inventory_state.get("entries", []):
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name", "")).strip()
            if name:
                names.append(name)
        if names:
            return names
        legacy: list[str] = []
        for key in ("items", "weapons", "armor", "consumables", "key_items"):
            values = inventory_state.get(key, [])
            if isinstance(values, list):
                legacy.extend(str(v).strip() for v in values if str(v).strip())
        return legacy

    def _ensure_main_character_sheet(self, state: CampaignState) -> None:
        main_sheet = next((sheet for sheet in state.character_sheets if sheet.sheet_type == "main_character"), None)
        if main_sheet is not None:
            return
        auto_sheet = CharacterSheet(
            id=f"sheet_auto_{state.player.id}",
            name=state.player.name or "Player",
            sheet_type="main_character",
            role=state.player.char_class,
            level_or_rank=str(state.player.level),
            description="Auto-generated from runtime player state.",
            stats=CharacterSheetStats(
                health=state.player.max_hp or state.player.hp,
                energy_or_mana=state.player.energy_or_mana,
                attack=state.player.attack_bonus,
                defense=state.player.defense,
                speed=state.player.speed,
                magic=state.player.magic,
                willpower=state.player.willpower,
                presence=state.player.presence,
            ),
            classic_attributes=CharacterSheetClassicAttributes(
                strength=state.player.strength,
                dexterity=state.player.agility,
                constitution=state.player.vitality,
                intelligence=state.player.intellect,
                wisdom=state.player.willpower,
                charisma=state.player.presence,
            ),
            abilities=[str(entry.get("name", "")).strip() for entry in state.structured_state.runtime.spellbook if isinstance(entry, dict)],
            equipment=list(state.player.inventory),
            notes="Created automatically because no main character sheet was provided.",
        )
        auto_sheet.abilities = [name for name in auto_sheet.abilities if name]
        state.character_sheets.append(auto_sheet)
        print(f"[character-sheets] auto_created_main_sheet=true id={auto_sheet.id}")

    def _normalize_spellbook(self, raw_entries: list[dict[str, object]] | list[object]) -> list[dict[str, object]]:
        return normalize_abilities_collection(raw_entries)
