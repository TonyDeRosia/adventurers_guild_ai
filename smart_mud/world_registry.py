"""World package discovery, validation, and loading for Smart MUD."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from engine.combat_equipment import CombatContentRegistry

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORLDS_DIR = PROJECT_ROOT / "worlds"

REQUIRED_RUNTIME_DIRS = (
    "rules", "areas", "rooms", "zones", "npcs", "items", "quests", "shops",
    "trainers", "classes", "races", "skills", "spells", "abilities", "factions",
    "lore", "dialogue", "intelligence", "colors", "schedules",
)
REQUIRED_BUILDER_DIRS = ("audit", "history", "snapshots", "imports", "exports", "templates", "examples")
REQUIRED_WORLD_DIRS = REQUIRED_RUNTIME_DIRS  # Backward-compatible alias for runtime-required content.
REQUIRED_MANIFEST_FIELDS = (
    "world_id", "display_name", "author", "description", "version",
    "engine_version_required", "minimum_engine_version", "maximum_engine_version",
    "dependencies", "required_plugins", "optional_plugins", "world_type",
    "default_starting_area", "default_starting_room", "supported_languages",
    "supported_character_slots", "builder", "load_priority", "package_guid",
)

class WorldRegistryError(ValueError):
    pass

class WorldValidationError(WorldRegistryError):
    def __init__(self, world_id: str, errors: list[str]) -> None:
        super().__init__(f"World {world_id} failed validation:\n- " + "\n- ".join(errors))
        self.world_id = world_id
        self.errors = errors

def _read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise WorldRegistryError(f"World file not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorldRegistryError(f"Invalid JSON in {path}: {exc}") from exc

def _records(root: Path, dirname: str) -> list[dict[str, Any]]:
    path = root / dirname
    out: list[dict[str, Any]] = []
    for json_path in sorted(path.glob("*.json")):
        data = _read_json(json_path, [])
        if isinstance(data, list):
            out.extend(x for x in data if isinstance(x, dict))
        elif isinstance(data, dict):
            values = data.get(dirname) or data.get("records")
            if isinstance(values, list):
                out.extend(x for x in values if isinstance(x, dict))
            else:
                out.append(data)
    return out

def by_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(r.get("id")): r for r in records if r.get("id")}

@dataclass(frozen=True)
class WorldPackage:
    root: Path
    manifest: dict[str, Any]
    rules: dict[str, Any]
    races: list[dict[str, Any]]
    classes: list[dict[str, Any]]
    abilities: list[dict[str, Any]]
    skills: list[dict[str, Any]]
    spells: list[dict[str, Any]]
    items: list[dict[str, Any]]
    item_placements: list[dict[str, Any]]
    areas: list[dict[str, Any]]
    rooms: list[dict[str, Any]]
    zones: list[dict[str, Any]]
    factions: list[dict[str, Any]]
    npcs: list[dict[str, Any]]
    spawns: list[dict[str, Any]]
    features: list[dict[str, Any]]
    quests: list[dict[str, Any]]
    shops: list[dict[str, Any]]
    trainers: list[dict[str, Any]]
    lore: list[dict[str, Any]]
    dialogue: list[dict[str, Any]]
    intelligence: dict[str, str]
    schedules: list[dict[str, Any]]
    relationship_seeds: list[dict[str, Any]]
    memory_seeds: list[dict[str, Any]]
    need_profiles: list[dict[str, Any]]
    goal_profiles: list[dict[str, Any]]
    body_profiles: list[dict[str, Any]] = None
    population_definitions: list[dict[str, Any]] = None
    lifecycle_profiles: list[dict[str, Any]] = None
    respawn_definitions: list[dict[str, Any]] = None
    equipment_slot_profiles: list[dict[str, Any]] = None
    effect_templates: list[dict[str, Any]] = None
    resource_profiles: list[dict[str, Any]] = None
    resistance_profiles: list[dict[str, Any]] = None
    combat_formulas: list[dict[str, Any]] = None
    modifier_types: list[dict[str, Any]] = None
    weapon_classes: list[dict[str, Any]] = None
    weapon_templates: list[dict[str, Any]] = None
    armor_classes: list[dict[str, Any]] = None
    armor_templates: list[dict[str, Any]] = None
    attack_profiles: list[dict[str, Any]] = None
    critical_profiles: list[dict[str, Any]] = None
    damage_profiles: list[dict[str, Any]] = None
    natural_weapon_profiles: list[dict[str, Any]] = None
    material_profiles: list[dict[str, Any]] = None
    equipment_sets: list[dict[str, Any]] = None
    ability_loadouts: list[dict[str, Any]] = None
    ability_schools: list[dict[str, Any]] = None
    ability_categories: list[dict[str, Any]] = None
    cooldown_groups: list[dict[str, Any]] = None
    targeting_profiles: list[dict[str, Any]] = None
    healing_profiles: list[dict[str, Any]] = None
    casting_profiles: list[dict[str, Any]] = None
    combat_behavior_profiles: list[dict[str, Any]] = None
    threat_profiles: list[dict[str, Any]] = None
    aggression_profiles: list[dict[str, Any]] = None
    assist_profiles: list[dict[str, Any]] = None
    flee_profiles: list[dict[str, Any]] = None
    surrender_profiles: list[dict[str, Any]] = None
    pursuit_profiles: list[dict[str, Any]] = None
    combat_groups: list[dict[str, Any]] = None
    combat_action_rules: list[dict[str, Any]] = None
    recipe_definitions: list[dict[str, Any]] = None
    workstation_profiles: list[dict[str, Any]] = None
    production_profiles: list[dict[str, Any]] = None
    item_quality_profiles: list[dict[str, Any]] = None
    crafting_quality_profiles: list[dict[str, Any]] = None
    ingredient_substitution_profiles: list[dict[str, Any]] = None
    crafting_message_profiles: list[dict[str, Any]] = None
    profession_experience_curves: list[dict[str, Any]] = None
    profession_growth_profiles: list[dict[str, Any]] = None
    organization_definitions: list[dict[str, Any]] = None
    organization_roles: list[dict[str, Any]] = None
    organization_membership_policies: list[dict[str, Any]] = None
    organization_invitation_policies: list[dict[str, Any]] = None
    organization_application_policies: list[dict[str, Any]] = None
    organization_leadership_policies: list[dict[str, Any]] = None
    organization_permission_profiles: list[dict[str, Any]] = None
    organization_communication_profiles: list[dict[str, Any]] = None
    organization_group_combat_profiles: list[dict[str, Any]] = None
    organization_shared_quest_profiles: list[dict[str, Any]] = None
    organization_reward_profiles: list[dict[str, Any]] = None
    organization_relationship_profiles: list[dict[str, Any]] = None
    organization_seeds: list[dict[str, Any]] = None
    organization_message_profiles: list[dict[str, Any]] = None

    faction_definitions: list[dict[str, Any]] = None
    faction_reputation_profiles: list[dict[str, Any]] = None
    faction_standing_tier_profiles: list[dict[str, Any]] = None
    faction_membership_reputation_policies: list[dict[str, Any]] = None
    faction_diplomacy_profiles: list[dict[str, Any]] = None
    faction_hostility_profiles: list[dict[str, Any]] = None
    faction_access_profiles: list[dict[str, Any]] = None
    faction_guard_response_profiles: list[dict[str, Any]] = None
    faction_economy_modifier_profiles: list[dict[str, Any]] = None
    faction_reward_profiles: list[dict[str, Any]] = None
    faction_reputation_decay_profiles: list[dict[str, Any]] = None
    faction_combat_reputation_profiles: list[dict[str, Any]] = None
    faction_title_profiles: list[dict[str, Any]] = None
    faction_message_profiles: list[dict[str, Any]] = None

    climate_profiles: list[dict[str, Any]] = None
    season_profiles: list[dict[str, Any]] = None
    daylight_profiles: list[dict[str, Any]] = None
    moonlight_profiles: list[dict[str, Any]] = None
    weather_type_definitions: list[dict[str, Any]] = None
    weather_transition_profiles: list[dict[str, Any]] = None
    room_environment_profiles: list[dict[str, Any]] = None
    light_source_profiles: list[dict[str, Any]] = None
    actor_vision_profiles: list[dict[str, Any]] = None
    environment_exposure_profiles: list[dict[str, Any]] = None
    environment_message_profiles: list[dict[str, Any]] = None
    environment_override_profiles: list[dict[str, Any]] = None
    environment_render_profiles: list[dict[str, Any]] = None
    environment_hazard_profiles: list[dict[str, Any]] = None

    actor_sense_profiles: list[dict[str, Any]] = None
    perception_profiles: list[dict[str, Any]] = None
    concealment_profiles: list[dict[str, Any]] = None
    concealment_source_profiles: list[dict[str, Any]] = None
    search_profiles: list[dict[str, Any]] = None
    tracking_profiles: list[dict[str, Any]] = None
    terrain_trace_profiles: list[dict[str, Any]] = None
    scent_profiles: list[dict[str, Any]] = None
    sound_profiles: list[dict[str, Any]] = None
    sound_propagation_profiles: list[dict[str, Any]] = None
    perception_message_profiles: list[dict[str, Any]] = None
    perception_knowledge_profiles: list[dict[str, Any]] = None
    secret_discovery_profiles: list[dict[str, Any]] = None
    sensory_retention_profiles: list[dict[str, Any]] = None

    resource_definitions: list[dict[str, Any]] = None
    resource_node_definitions: list[dict[str, Any]] = None
    resource_capacity_profiles: list[dict[str, Any]] = None
    resource_regeneration_profiles: list[dict[str, Any]] = None
    resource_availability_profiles: list[dict[str, Any]] = None
    resource_environment_profiles: list[dict[str, Any]] = None
    gathering_profiles: list[dict[str, Any]] = None
    gathering_tool_profiles: list[dict[str, Any]] = None
    resource_yield_profiles: list[dict[str, Any]] = None
    gathering_resource_cost_profiles: list[dict[str, Any]] = None
    gathering_interruption_profiles: list[dict[str, Any]] = None
    gathering_cooldown_profiles: list[dict[str, Any]] = None
    gathering_profession_xp_profiles: list[dict[str, Any]] = None
    gathering_message_profiles: list[dict[str, Any]] = None
    gathering_render_profiles: list[dict[str, Any]] = None
    gathering_access_profiles: list[dict[str, Any]] = None

    actor_need_definitions: list[dict[str, Any]] = None
    actor_needs_profiles: list[dict[str, Any]] = None
    needs_offline_policies: list[dict[str, Any]] = None
    need_threshold_profiles: list[dict[str, Any]] = None
    consumable_profiles: list[dict[str, Any]] = None
    consumable_portion_profiles: list[dict[str, Any]] = None
    food_freshness_profiles: list[dict[str, Any]] = None
    consumption_requirement_profiles: list[dict[str, Any]] = None
    consumption_interruption_profiles: list[dict[str, Any]] = None
    survival_message_profiles: list[dict[str, Any]] = None
    survival_render_profiles: list[dict[str, Any]] = None

    @property
    def id(self) -> str: return str(self.manifest["world_id"])
    @property
    def default_starting_room_id(self) -> str: return str(self.manifest.get("default_starting_room", ""))
    @property
    def default_starting_room(self) -> dict[str, Any]: return self.room(self.default_starting_room_id)
    def room(self, room_id: str) -> dict[str, Any]:
        for room in self.rooms:
            if room.get("id") == room_id:
                return room
        raise WorldRegistryError(f"Room not found in {self.id}: {room_id}")
    def world_intelligence_source_dir(self) -> Path | None:
        path = self.root / "intelligence"
        return path if path.exists() else None
    def campaign_intelligence_source_dir(self) -> Path | None:
        return None

class WorldRegistry:
    def __init__(self, worlds_dir: Path | None = None) -> None:
        self.worlds_dir = worlds_dir or WORLDS_DIR
        self.worlds_dir.mkdir(parents=True, exist_ok=True)

    def list_worlds(self) -> list[dict[str, Any]]:
        worlds = []
        seen: set[str] = set()
        for manifest_path in sorted(self.worlds_dir.glob("*/manifest.json")):
            manifest = _read_json(manifest_path)
            world_id = str(manifest.get("world_id") or manifest.get("id") or manifest_path.parent.name)
            if world_id in seen:
                raise WorldRegistryError(f"Duplicate world id: {world_id}")
            seen.add(world_id)
            worlds.append(self._public_manifest(manifest, world_id))
        return sorted(worlds, key=lambda m: (int(m.get("load_priority", 100)), str(m.get("id"))))

    def prepare_builder_workspace(self, world_id: str) -> list[Path]:
        """Create non-gameplay Builder workspace folders without affecting validation."""
        root = self.worlds_dir / world_id
        created: list[Path] = []
        for directory in (root / "builder", *(root / "builder" / dirname for dirname in REQUIRED_BUILDER_DIRS)):
            if not directory.exists():
                directory.mkdir(parents=True, exist_ok=True)
                created.append(directory)
        return created

    def validate_world(self, world_id: str) -> None:
        root = self.worlds_dir / world_id
        manifest = self._manifest(root)
        actual_id = str(manifest.get("world_id", world_id))
        errors: list[str] = []
        self.prepare_builder_workspace(world_id)
        for dirname in REQUIRED_RUNTIME_DIRS:
            if not (root / dirname).is_dir():
                errors.append(f"Missing required runtime folder: {dirname}/")
        for field in REQUIRED_MANIFEST_FIELDS:
            if field not in manifest:
                errors.append(f"Manifest missing required field: {field}")
        rooms = by_id(_records(root, "rooms")); npcs = by_id(_records(root, "npcs")); items = by_id(_records(root, "items"))
        quests = by_id(_records(root, "quests")); classes = by_id(_records(root, "classes")); abilities = by_id(_records(root, "abilities"))
        races = by_id(_records(root, "races")); spells = by_id(_records(root, "spells")); skills = by_id(_records(root, "skills"))
        for label, records in (("room", rooms), ("NPC", npcs), ("item", items), ("quest", quests), ("class", classes), ("race", races)):
            if "" in records:
                errors.append(f"A {label} record is missing an id")
        start_room = manifest.get("default_starting_room")
        if start_room and str(start_room) not in rooms:
            errors.append(f"Default starting room references missing room: {start_room}")
        for room in rooms.values():
            for exit_data in room.get("exits", []) or []:
                target = exit_data.get("to") or exit_data.get("room_id") or exit_data.get("target")
                if target and str(target) not in rooms:
                    errors.append(f"Room {room.get('id')} exit references missing room: {target}")
            for npc_id in room.get("npcs", []) or []:
                if str(npc_id) not in npcs:
                    errors.append(f"Room {room.get('id')} references missing NPC: {npc_id}")
        for npc in npcs.values():
            for room_id in npc.get("rooms", []) or ([npc.get("room_id")] if npc.get("room_id") else []):
                if str(room_id) not in rooms:
                    errors.append(f"NPC {npc.get('id')} references missing room: {room_id}")
        for item in items.values():
            template = item.get("template_id")
            if template and str(template) not in items:
                errors.append(f"Item {item.get('id')} references missing template: {template}")
        for quest in quests.values():
            for npc_id in quest.get("npc_ids", []) or ([] if not quest.get("npc_id") else [quest.get("npc_id")]):
                if str(npc_id) not in npcs:
                    errors.append(f"Quest {quest.get('id')} references missing NPC: {npc_id}")
        for trainer in _records(root, "trainers"):
            for class_id in trainer.get("class_ids", []) or ([] if not trainer.get("class_id") else [trainer.get("class_id")]):
                if str(class_id) not in classes:
                    errors.append(f"Trainer {trainer.get('id')} references missing class: {class_id}")
        schools = {str(s.get("id")) for s in _records(root / "rules", "spell_schools")} | {str(s.get("school")) for s in spells.values() if s.get("school")}
        for spell in spells.values():
            school = spell.get("school")
            if school and str(school) not in schools:
                errors.append(f"Spell {spell.get('id')} references missing school: {school}")
        for cls in classes.values():
            for ability_id in cls.get("ability_ids", []) or []:
                if str(ability_id) not in abilities and str(ability_id) not in skills and str(ability_id) not in spells:
                    errors.append(f"Class {cls.get('id')} references missing ability: {ability_id}")
        for race in races.values():
            if not isinstance(race, dict) or not race.get("id"):
                errors.append("Race record has invalid data")
        combat_content = CombatContentRegistry(records={name: _records(root, name) for name in ("weapon_classes", "weapon_templates", "armor_classes", "armor_templates", "attack_profiles", "critical_profiles", "damage_profiles", "natural_weapon_profiles", "material_profiles", "equipment_sets")})
        errors.extend(combat_content.validate())
        from engine.abilities import AbilityRegistry
        ability_content = AbilityRegistry(records={name: _records(root, name) for name in ("abilities", "ability_loadouts", "ability_schools", "ability_categories", "cooldown_groups", "targeting_profiles", "healing_profiles", "casting_profiles", "effect_templates", "resource_profiles", "damage_profiles", "combat_formulas")})
        errors.extend(ability_content.validate())
        from engine.combat_behavior import CombatBehaviorRegistry
        behavior_content = CombatBehaviorRegistry(records={name: _records(root, name) for name in ("combat_behavior_profiles", "combat_groups", "combat_action_rules")})
        errors.extend(behavior_content.validate())
        if errors:
            raise WorldValidationError(actual_id, errors)

    def load_world(self, world_id: str) -> WorldPackage:
        self.validate_world(world_id)
        root = self.worlds_dir / world_id
        manifest = self._manifest(root)
        rules = {p.stem: _read_json(p, {}) for p in sorted((root / "rules").glob("*.json"))}
        intelligence = {p.stem: p.read_text(encoding="utf-8") for p in sorted((root / "intelligence").glob("*.md"))}
        return WorldPackage(root, manifest, rules, _records(root,"races"), _records(root,"classes"), _records(root,"abilities"), _records(root,"skills"), _records(root,"spells"), _records(root,"items"), _records(root,"item_placements"), _records(root,"areas"), _records(root,"rooms"), _records(root,"zones"), _records(root,"factions"), _records(root,"npcs"), _records(root,"spawns"), _records(root,"features"), _records(root,"quests"), _records(root,"shops"), _records(root,"trainers"), _records(root,"lore"), _records(root,"dialogue"), intelligence, _records(root,"schedules"), _records(root,"relationship_seeds"), _records(root,"memory_seeds"), _records(root,"need_profiles"), _records(root,"goal_profiles"), _records(root,"body_profiles"), _records(root,"population_definitions"), _records(root,"lifecycle_profiles"), _records(root,"respawn_definitions"), _records(root,"equipment_slot_profiles"), _records(root,"effect_templates"), _records(root,"resource_profiles"), _records(root,"resistance_profiles"), _records(root,"combat_formulas"), _records(root,"modifier_types"), _records(root,"weapon_classes"), _records(root,"weapon_templates"), _records(root,"armor_classes"), _records(root,"armor_templates"), _records(root,"attack_profiles"), _records(root,"critical_profiles"), _records(root,"damage_profiles"), _records(root,"natural_weapon_profiles"), _records(root,"material_profiles"), _records(root,"equipment_sets"), _records(root,"ability_loadouts"), _records(root,"ability_schools"), _records(root,"ability_categories"), _records(root,"cooldown_groups"), _records(root,"targeting_profiles"), _records(root,"healing_profiles"), _records(root,"casting_profiles"), _records(root,"combat_behavior_profiles"), _records(root,"threat_profiles"), _records(root,"aggression_profiles"), _records(root,"assist_profiles"), _records(root,"flee_profiles"), _records(root,"surrender_profiles"), _records(root,"pursuit_profiles"), _records(root,"combat_groups"), _records(root,"combat_action_rules"), _records(root,"recipe_definitions"), _records(root,"workstation_profiles"), _records(root,"production_profiles"), _records(root,"item_quality_profiles"), _records(root,"crafting_quality_profiles"), _records(root,"ingredient_substitution_profiles"), _records(root,"crafting_message_profiles"), _records(root,"profession_experience_curves"), _records(root,"profession_growth_profiles"), _records(root,"organization_definitions"), _records(root,"organization_roles"), _records(root,"organization_membership_policies"), _records(root,"organization_invitation_policies"), _records(root,"organization_application_policies"), _records(root,"organization_leadership_policies"), _records(root,"organization_permission_profiles"), _records(root,"organization_communication_profiles"), _records(root,"organization_group_combat_profiles"), _records(root,"organization_shared_quest_profiles"), _records(root,"organization_reward_profiles"), _records(root,"organization_relationship_profiles"), _records(root,"organization_seeds"), _records(root,"organization_message_profiles"), _records(root,"faction_definitions"), _records(root,"faction_reputation_profiles"), _records(root,"faction_standing_tier_profiles"), _records(root,"faction_membership_reputation_policies"), _records(root,"faction_diplomacy_profiles"), _records(root,"faction_hostility_profiles"), _records(root,"faction_access_profiles"), _records(root,"faction_guard_response_profiles"), _records(root,"faction_economy_modifier_profiles"), _records(root,"faction_reward_profiles"), _records(root,"faction_reputation_decay_profiles"), _records(root,"faction_combat_reputation_profiles"), _records(root,"faction_title_profiles"), _records(root,"faction_message_profiles"), _records(root,"climate_profiles"), _records(root,"season_profiles"), _records(root,"daylight_profiles"), _records(root,"moonlight_profiles"), _records(root,"weather_type_definitions"), _records(root,"weather_transition_profiles"), _records(root,"room_environment_profiles"), _records(root,"light_source_profiles"), _records(root,"actor_vision_profiles"), _records(root,"environment_exposure_profiles"), _records(root,"environment_message_profiles"), _records(root,"environment_override_profiles"), _records(root,"environment_render_profiles"), _records(root,"environment_hazard_profiles"), _records(root,"actor_sense_profiles"), _records(root,"perception_profiles"), _records(root,"concealment_profiles"), _records(root,"concealment_source_profiles"), _records(root,"search_profiles"), _records(root,"tracking_profiles"), _records(root,"terrain_trace_profiles"), _records(root,"scent_profiles"), _records(root,"sound_profiles"), _records(root,"sound_propagation_profiles"), _records(root,"perception_message_profiles"), _records(root,"perception_knowledge_profiles"), _records(root,"secret_discovery_profiles"), _records(root,"sensory_retention_profiles"), _records(root,"resource_definitions"), _records(root,"resource_node_definitions"), _records(root,"resource_capacity_profiles"), _records(root,"resource_regeneration_profiles"), _records(root,"resource_availability_profiles"), _records(root,"resource_environment_profiles"), _records(root,"gathering_profiles"), _records(root,"gathering_tool_profiles"), _records(root,"resource_yield_profiles"), _records(root,"gathering_resource_cost_profiles"), _records(root,"gathering_interruption_profiles"), _records(root,"gathering_cooldown_profiles"), _records(root,"gathering_profession_xp_profiles"), _records(root,"gathering_message_profiles"), _records(root,"gathering_render_profiles"), _records(root,"gathering_access_profiles"), _records(root,"actor_need_definitions"), _records(root,"actor_needs_profiles"), _records(root,"needs_offline_policies"), _records(root,"need_threshold_profiles"), _records(root,"consumable_profiles"), _records(root,"consumable_portion_profiles"), _records(root,"food_freshness_profiles"), _records(root,"consumption_requirement_profiles"), _records(root,"consumption_interruption_profiles"), _records(root,"survival_message_profiles"), _records(root,"survival_render_profiles"))

    def reload_room(self, world: WorldPackage, room_id: str) -> dict[str, Any]:
        return self.load_world(world.id).room(room_id)
    def reload_npc(self, world: WorldPackage, npc_id: str) -> dict[str, Any]:
        return by_id(self.load_world(world.id).npcs)[npc_id]
    def reload_area(self, world: WorldPackage, area_id: str) -> dict[str, Any]:
        return by_id(self.load_world(world.id).areas)[area_id]
    def reload_quest(self, world: WorldPackage, quest_id: str) -> dict[str, Any]:
        return by_id(self.load_world(world.id).quests)[quest_id]
    def reload_item(self, world: WorldPackage, item_id: str) -> dict[str, Any]:
        return by_id(self.load_world(world.id).items)[item_id]

    def _manifest(self, root: Path) -> dict[str, Any]:
        return _read_json(root / "manifest.json")
    def _public_manifest(self, manifest: dict[str, Any], world_id: str) -> dict[str, Any]:
        return {
            "id": world_id,
            "world_id": world_id,
            "name": manifest.get("display_name") or manifest.get("name") or world_id,
            "display_name": manifest.get("display_name") or manifest.get("name") or world_id,
            "description": manifest.get("description", ""),
            "version": manifest.get("version", ""),
            "world_type": manifest.get("world_type") or manifest.get("genre", ""),
            "default_start_room": manifest.get("default_starting_room") or manifest.get("default_start_room", ""),
            "load_priority": manifest.get("load_priority", 100),
        }
