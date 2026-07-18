"""Safe in-game Builder workspace services for Smart MUD."""
from __future__ import annotations

import json, shutil, re, os, hashlib, sqlite3, time
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from smart_mud.world_registry import WORLDS_DIR, _records
from smart_mud.builder_rendering import medit as medit_render
from engine.equipment_slots import CANONICAL_EQUIPMENT_SLOT_IDS, EQUIPMENT_SLOT_LABELS, EQUIPMENT_SLOT_ALIASES, normalize_equipment_slot, equipment_slot_label, canonicalize_slot_list

BUILDER_ROLES = {"builder", "admin", "owner"}
VALID_WEAR_SLOTS = set(CANONICAL_EQUIPMENT_SLOT_IDS)
VALID_ENTITY_TYPES = {"npc", "mob", "merchant", "trainer", "banker", "healer", "critter", "object"}
MEDIT_SEX_VALUES = ("neutral","male","female","nonbinary","unknown","custom")
MEDIT_SIZE_VALUES = ("tiny","small","medium","large","huge","gargantuan","custom")
MEDIT_POSITIONS = ("sleeping","resting","sitting","standing","fighting","stunned","incapacitated","mortally_wounded","dead")
MEDIT_ATTACK_TYPES = ("hit","sting","whip","slash","bite","bludgeon","crush","pound","claw","maul","thrash","pierce","blast","punch","stab","gore","kick","tail","breath","slam")
MEDIT_MOBILE_FLAGS = ("sentinel","stay_zone","wander","no_wander","aggressive","wimpy","memory","helper","no_kill","elite","boss","scavenger","mountable","pet","purchasable","companion","no_charm","shopkeeper","trainer","guildmaster","questmaster","banker","healer","ai_actor","scripted_only","behavior_profile_controlled","immortal","protected","unique","no_purge","debug_only")
MEDIT_AFFECT_FLAGS = ("detect_invisible","darkvision","detect_magic","awareness","invisible","hidden","camouflage","sanctuary","protection","shield","flying","water_breathing","swimming","pass_door","haste","slow","poison","disease","blindness","silence","fear","charm","rooted","stunned","sleeping")

MEDIT_QUICK_BUILD_VERSION = "smartmud-medit-quick-build/v1"
MEDIT_ARCHETYPES = ("harmless civilian","civilian","weak creature","standard creature","skirmisher","brute","soldier","guardian","rogue","caster","healer/support","elite","boss","custom")
MEDIT_DURABILITY = ("fragile","low","standard","durable","very durable","boss")
MEDIT_OFFENSE = ("very low","low","standard","high","extreme")
MEDIT_DEFENSE = ("very low","low","standard","high","extreme")
MEDIT_RESOURCE_STYLES = ("health only","martial","mana user","stamina user","hybrid","custom")
MEDIT_REWARD_STYLES = ("none","low","standard","generous","elite","boss","custom")
MEDIT_DIFFICULTY_RANKS = ("trivial","normal","veteran","elite","miniboss","boss","raid/world boss")

MEDIT_ADVANCED_ABILITY_TYPES = ("ability", "skill", "spell", "special")
MEDIT_ADVANCED_TARGETS = ("self", "current_enemy", "random_enemy", "weakest_enemy", "strongest_enemy", "nearest_enemy", "ally", "weakest_ally", "strongest_ally", "leader", "owner", "master", "room", "custom")
MEDIT_ADVANCED_ABILITY_TRIGGERS = ("combat_start", "opening_move", "every_round", "random_round", "self_hp_threshold", "enemy_hp_threshold", "ally_hp_threshold", "enemy_casting", "ally_condition", "required_status_present", "required_status_absent", "cooldown_ready", "near_death", "target_death")
MEDIT_ADVANCED_EVENT_TYPES = ("player_enters", "player_leaves", "mobile_enters", "mobile_leaves", "sees_target", "loses_sight", "speech_heard", "keyword_spoken", "tell_received", "emote_observed", "receives_item", "is_given_item", "item_shown", "examined", "used", "trade_attempted", "pet_purchase_attempted", "combat_starts", "attacked", "ally_attacked", "enemy_defeated", "ally_defeated", "self_hp_threshold", "ally_hp_threshold", "enemy_hp_threshold", "combat_ends", "self_flees", "target_flees", "reset", "repop", "time_of_day", "weather_change", "world_event", "quest_state_change", "faction_standing_change", "area_state_change", "zone_state_change", "spawn", "death", "corpse_created", "despawn")
MEDIT_ADVANCED_ACTION_TYPES = ("say", "tell", "emote", "social", "move", "flee", "attack", "assist", "use_ability", "cast", "give_item", "take_item", "drop_item", "equip_item", "summon_mobile", "spawn_object", "call_guards", "change_faction_standing", "start_dialogue", "offer_quest", "advance_quest", "set_state", "set_tag", "trigger_script", "publish_event", "wait", "noop")
MEDIT_ADVANCED_SCRIPT_TRIGGERS = ("spawn", "death", "combat_start", "combat_round", "speech_heard", "keyword_spoken", "item_given", "examined", "used", "reset", "despawn", "event")
MEDIT_RUNTIME_SUPPORTED_ABILITY_TRIGGERS = {"combat_start", "opening_move", "every_round", "random_round", "self_hp_threshold", "enemy_hp_threshold", "cooldown_ready", "near_death"}
MEDIT_RUNTIME_SUPPORTED_REACTION_ACTIONS = {"say", "emote", "social", "attack", "assist", "flee", "use_ability", "cast", "publish_event", "wait", "noop"}
MEDIT_RUNTIME_SUPPORTED_REACTION_EVENTS = {"spawn", "death", "combat_starts", "attacked", "speech_heard", "keyword_spoken", "player_enters", "reset", "despawn"}

def _stable_nested_id(parent_id: str, kind: str, index: int, seed: str = "") -> str:
    base = re.sub(r"[^a-z0-9_:-]+", "_", str(seed or f"{parent_id}_{kind}_{index}").lower()).strip("_")
    return base or f"{parent_id}_{kind}_{index}"

def _chance_int(value: Any, default: int = 100) -> int:
    if isinstance(value, str) and value.strip().endswith("%"):
        value = value.strip()[:-1]
    try: return int(float(value))
    except Exception: return default

def _canonical_advanced_entry(raw: dict[str, Any], parent_id: str, kind: str, index: int) -> dict[str, Any]:
    rec = deepcopy(raw or {})
    rec["id"] = _stable_nested_id(parent_id, kind, index, rec.get("id") or rec.get("entry_id") or rec.get("reaction_id") or rec.get("attachment_id") or rec.get("ability_id") or rec.get("script_id"))
    rec.setdefault("enabled", True); rec["priority"] = int(rec.get("priority") if rec.get("priority") is not None else rec.get("order", index))
    rec.setdefault("builder_label", rec.get("label") or rec.get("name") or "")
    rec["chance"] = _chance_int(rec.get("chance", 100))
    for fld in ("cooldown", "initial_cooldown", "minimum_round", "maximum_round", "resource_cost", "uses_per_combat", "uses_per_life", "uses_per_reset"):
        if fld in rec and rec.get(fld) not in (None, ""):
            try: rec[fld] = int(rec.get(fld))
            except Exception: pass
    for fld in ("required_status", "forbidden_status", "required_target_status", "forbidden_target_status", "required_tags", "forbidden_tags", "required_conditions", "forbidden_conditions"):
        val = rec.get(fld)
        if isinstance(val, str): rec[fld] = [x.strip() for x in val.split(",") if x.strip()]
        elif val is None: rec[fld] = []
    if kind == "combat_ability":
        rec["ability_type"] = str(rec.get("ability_type") or rec.get("type") or "ability").lower()
        rec["ability_id"] = str(rec.get("ability_id") or rec.get("ability") or rec.get("skill_id") or rec.get("spell_id") or "")
        rec["target_selector"] = str(rec.get("target_selector") or rec.get("target") or "current_enemy").lower().replace(" ", "_")
        rec["trigger"] = str(rec.get("trigger") or rec.get("trigger_mode") or "every_round").lower().replace(" ", "_")
        rec.setdefault("classification_flags", list(rec.get("flags") or []))
    elif kind == "event_reaction":
        rec["event_type"] = str(rec.get("event_type") or rec.get("event") or "spawn").lower().replace(" ", "_")
        rec["action_type"] = str(rec.get("action_type") or rec.get("action") or "noop").lower().replace(" ", "_")
        rec["target_selector"] = str(rec.get("target_selector") or rec.get("target") or "self").lower().replace(" ", "_")
        rec.setdefault("event_filters", rec.get("filters") or {})
        rec.setdefault("action_data", rec.get("parameters") or rec.get("data") or {})
        rec.setdefault("stop_processing", bool(rec.get("stop_processing", False)))
    else:
        rec["script_id"] = str(rec.get("script_id") or rec.get("trigger_id") or rec.get("id") or "")
        rec["trigger"] = str(rec.get("trigger") or rec.get("event_binding") or "event").lower().replace(" ", "_")
        rec.setdefault("parameters", rec.get("params") or {})
        rec.setdefault("conditions", rec.get("conditions") or [])
        rec.setdefault("execution_policy", rec.get("execution_policy") or "canonical_service_host")
    return rec

def _normalize_advanced_mobile_sections(rec: dict[str, Any], oid: str) -> dict[str, Any]:
    rec["combat_abilities"] = [_canonical_advanced_entry(x, oid, "combat_ability", i + 1) for i, x in enumerate(rec.get("combat_abilities") or rec.get("abilities") or rec.get("explicit_abilities") or []) if isinstance(x, dict)]
    rec["event_reactions"] = [_canonical_advanced_entry(x, oid, "event_reaction", i + 1) for i, x in enumerate(rec.get("event_reactions") or rec.get("reactions") or []) if isinstance(x, dict)]
    raw_scripts = rec.get("script_attachments") or rec.get("scripts") or rec.get("script_ids") or rec.get("triggers") or []
    normalized_scripts=[]
    for i, x in enumerate(raw_scripts):
        normalized_scripts.append(_canonical_advanced_entry(x if isinstance(x, dict) else {"script_id": x}, oid, "script_attachment", i + 1))
    rec["script_attachments"] = normalized_scripts
    return rec

class MobileRecommendationService:
    """Deterministic, versioned MEDIT recommendation helper kept separate from routing/runtime."""
    version = MEDIT_QUICK_BUILD_VERSION
    _mul = {"very low":0.55,"low":0.75,"standard":1.0,"high":1.3,"extreme":1.65,"fragile":0.55,"durable":1.25,"very durable":1.55,"boss":2.4,"none":0.0,"generous":1.45,"elite":1.8,"trivial":0.7,"normal":1.0,"veteran":1.2,"miniboss":1.7,"raid/world boss":3.0}
    _arch = {"harmless civilian":0.35,"civilian":0.55,"weak creature":0.75,"standard creature":1.0,"skirmisher":1.05,"brute":1.25,"soldier":1.15,"guardian":1.2,"rogue":1.05,"caster":0.9,"healer/support":0.85,"elite":1.5,"boss":2.2,"custom":1.0}
    def recommend(self, level:int=1, archetype:str="standard creature", durability:str="standard", offense:str="standard", defense:str="standard", resource_style:str="health only", attack_style:str="hit", reward_style:str="standard", difficulty_rank:str="normal") -> dict[str, Any]:
        lvl=max(1,min(100,int(level or 1))); am=self._arch.get(archetype,1.0); dm=self._mul.get(durability,1.0)*self._mul.get(difficulty_rank,1.0); om=self._mul.get(offense,1.0)*am; defm=self._mul.get(defense,1.0)
        attr_base=max(3,min(100,10+lvl//3)); attrs={k:attr_base for k in ("strength","dexterity","constitution","intelligence","wisdom","charisma")}
        if "brute" in archetype or archetype in {"soldier","guardian","boss"}: attrs["strength"]+=3; attrs["constitution"]+=2
        if archetype in {"rogue","skirmisher"}: attrs["dexterity"]+=3
        if archetype in {"caster","healer/support"}: attrs["intelligence"]+=3; attrs["wisdom"]+=3
        hp=int((18+lvl*14)*dm*am); mana=0; stamina=int(20+lvl*6)
        if resource_style in {"mana user","hybrid"} or archetype in {"caster","healer/support"}: mana=int(12+lvl*9)
        if resource_style == "health only": stamina=0
        sides=max(2,min(12,2+lvl//4)); dice_count=max(1,min(6,1+lvl//10)); reward=self._mul.get(reward_style,1.0)
        return {"version":self.version,"inputs":{"level":lvl,"archetype":archetype,"durability":durability,"offense":offense,"defense":defense,"resource_style":resource_style,"attack_style":attack_style,"reward_style":reward_style,"difficulty_rank":difficulty_rank},"values":{"level":lvl,"archetype":archetype,"attributes":attrs,"resources":{"health":{"maximum":hp,"starting":hp,"enabled":True},"mana":{"maximum":mana,"starting":mana,"enabled":mana>0},"stamina":{"maximum":stamina,"starting":stamina,"enabled":stamina>0}},"combat_profile":{"armor":int(lvl*defm*1.4),"defense":int(lvl*defm),"accuracy":int(lvl*om/2),"damage_bonus":int(lvl*om/3),"damage_dice":f"{dice_count}d{sides}","attack_type":attack_style if attack_style in MEDIT_ATTACK_TYPES else "hit","attacks_per_round":1+(1 if om>1.4 and lvl>=8 else 0)+(1 if om>2.0 and lvl>=20 else 0),"experience_reward":int(lvl*25*reward*am),"gold_reward":int(lvl*4*reward)}}}
    def diff(self, record:dict[str,Any], recs:dict[str,Any]) -> dict[str,Any]:
        values=recs.get("values",{}); out={}
        for k,v in values.items():
            if k in {"attributes","resources","combat_profile"}:
                cur=record.get(k) or {}
                for nk,nv in v.items():
                    before=(cur or {}).get(nk); out[f"{k}.{nk}"]={"before":before,"after":nv,"would_overwrite":before not in (None,"",{},[])}
            else: out[k]={"before":record.get(k),"after":v,"would_overwrite":record.get(k) not in (None,"")}
        return out


DRAFT_FILES = {
    "world": "world.json", "display_themes": "display_themes.json",
    "areas": "areas.json", "zones": "zones.json", "rooms": "rooms.json",
    "features": "features.json", "items": "item_templates.json", "attack_family_definitions": "attack_family_definitions.json", "body_profiles": "body_profiles.json", "natural_weapon_profiles": "natural_weapon_profiles.json", "item_placements": "item_placements.json", "entities": "entity_templates.json", "spawns": "spawns.json", "resets": "resets.json", "schedules": "schedules.json", "relationship_seeds": "relationship_seeds.json", "memory_seeds": "memory_seeds.json", "need_profiles": "need_profiles.json", "goal_profiles": "goal_profiles.json", "formulas": "formulas.json", "modifier_types": "modifier_types.json", "future_formula_templates": "future_formula_templates.json", "abilities": "abilities.json", "ability_loadouts": "ability_loadouts.json", "ability_schools": "ability_schools.json", "ability_categories": "ability_categories.json", "cooldown_groups": "cooldown_groups.json", "targeting_profiles": "targeting_profiles.json", "healing_profiles": "healing_profiles.json", "casting_profiles": "casting_profiles.json", "combat_behavior_profiles": "combat_behavior_profiles.json", "threat_profiles": "threat_profiles.json", "aggression_profiles": "aggression_profiles.json", "assist_profiles": "assist_profiles.json", "flee_profiles": "flee_profiles.json", "surrender_profiles": "surrender_profiles.json", "pursuit_profiles": "pursuit_profiles.json", "combat_groups": "combat_groups.json", "combat_action_rules": "combat_action_rules.json", "recipe_definitions": "recipe_definitions.json", "workstation_profiles": "workstation_profiles.json", "production_profiles": "production_profiles.json", "item_quality_profiles": "item_quality_profiles.json", "crafting_quality_profiles": "crafting_quality_profiles.json", "ingredient_substitution_profiles": "ingredient_substitution_profiles.json", "crafting_message_profiles": "crafting_message_profiles.json", "profession_experience_curves": "profession_experience_curves.json", "profession_growth_profiles": "profession_growth_profiles.json", "quest_definitions": "quest_definitions.json", "quest_series": "quest_series.json", "quest_chapters": "quest_chapters.json", "quest_stages": "quest_stages.json", "quest_objectives": "quest_objectives.json", "quest_availability_profiles": "quest_availability_profiles.json", "quest_acceptance_profiles": "quest_acceptance_profiles.json", "quest_repeat_policies": "quest_repeat_policies.json", "quest_failure_profiles": "quest_failure_profiles.json", "quest_abandon_profiles": "quest_abandon_profiles.json", "quest_sharing_profiles": "quest_sharing_profiles.json", "quest_action_definitions": "quest_action_definitions.json", "conversation_definitions": "conversation_definitions.json", "conversation_nodes": "conversation_nodes.json", "conversation_choices": "conversation_choices.json", "conversation_conditions": "conversation_conditions.json", "conversation_actions": "conversation_actions.json", "quest_message_profiles": "quest_message_profiles.json", "quest_time_limit_profiles": "quest_time_limit_profiles.json", "world_state_definitions": "world_state_definitions.json", "organization_definitions": "organization_definitions.json", "organization_roles": "organization_roles.json", "organization_membership_policies": "organization_membership_policies.json", "organization_invitation_policies": "organization_invitation_policies.json", "organization_application_policies": "organization_application_policies.json", "organization_leadership_policies": "organization_leadership_policies.json", "organization_permission_profiles": "organization_permission_profiles.json", "organization_communication_profiles": "organization_communication_profiles.json", "organization_group_combat_profiles": "organization_group_combat_profiles.json", "organization_shared_quest_profiles": "organization_shared_quest_profiles.json", "organization_reward_profiles": "organization_reward_profiles.json", "organization_relationship_profiles": "organization_relationship_profiles.json", "organization_seeds": "organization_seeds.json", "organization_message_profiles": "organization_message_profiles.json", "faction_definitions": "faction_definitions.json", "faction_reputation_profiles": "faction_reputation_profiles.json", "faction_standing_tier_profiles": "faction_standing_tier_profiles.json", "faction_membership_reputation_policies": "faction_membership_reputation_policies.json", "faction_diplomacy_profiles": "faction_diplomacy_profiles.json", "faction_hostility_profiles": "faction_hostility_profiles.json", "faction_access_profiles": "faction_access_profiles.json", "faction_guard_response_profiles": "faction_guard_response_profiles.json", "faction_economy_modifier_profiles": "faction_economy_modifier_profiles.json", "faction_reward_profiles": "faction_reward_profiles.json", "faction_reputation_decay_profiles": "faction_reputation_decay_profiles.json", "faction_combat_reputation_profiles": "faction_combat_reputation_profiles.json", "faction_title_profiles": "faction_title_profiles.json", "faction_message_profiles": "faction_message_profiles.json", "trainer_definitions": "trainer_definitions.json", "training_offer_definitions": "training_offer_definitions.json", "training_requirement_profiles": "training_requirement_profiles.json", "training_cost_profiles": "training_cost_profiles.json", "training_result_profiles": "training_result_profiles.json", "trainer_availability_profiles": "trainer_availability_profiles.json", "class_track_training_profiles": "class_track_training_profiles.json", "advancement_conversion_profiles": "advancement_conversion_profiles.json", "respec_profiles": "respec_profiles.json", "training_refund_profiles": "training_refund_profiles.json", "training_cooldown_profiles": "training_cooldown_profiles.json", "training_message_profiles": "training_message_profiles.json", "written_document_definitions": "written_document_definitions.json", "written_content_profiles": "written_content_profiles.json", "written_content_pages": "written_content_pages.json", "written_access_profiles": "written_access_profiles.json", "written_retention_profiles": "written_retention_profiles.json", "written_render_profiles": "written_render_profiles.json", "written_sanitization_profiles": "written_sanitization_profiles.json", "mail_service_profiles": "mail_service_profiles.json", "bulletin_board_definitions": "bulletin_board_definitions.json", "bulletin_posting_profiles": "bulletin_posting_profiles.json", "written_moderation_profiles": "written_moderation_profiles.json", "written_message_profiles": "written_message_profiles.json", "readable_item_profiles": "readable_item_profiles.json", "journal_profiles": "journal_profiles.json", "book_profiles": "book_profiles.json"
}

COOKING_COLLECTION_FILES = {
    "cooking_ingredient_profiles": "cooking_ingredient_profiles.json",
    "cooking_substitution_profiles": "cooking_substitution_profiles.json",
    "ingredient_preparation_profiles": "ingredient_preparation_profiles.json",
    "cooking_serving_yield_profiles": "cooking_serving_yield_profiles.json",
    "cooking_consumable_output_profiles": "cooking_consumable_output_profiles.json",
    "food_nutrition_profiles": "food_nutrition_profiles.json",
    "food_preservation_profiles": "food_preservation_profiles.json",
    "cooking_heat_profiles": "cooking_heat_profiles.json",
    "cooking_failure_profiles": "cooking_failure_profiles.json",
    "cooking_message_profiles": "cooking_message_profiles.json",
    "cooking_render_profiles": "cooking_render_profiles.json",
}
DRAFT_FILES.update(COOKING_COLLECTION_FILES)

# Phase 11D1 canonical survival needs Builder collections.
for _survival_key in (
    "actor_need_definitions", "actor_needs_profiles", "needs_offline_policies",
    "need_threshold_profiles", "consumable_profiles", "consumable_portion_profiles",
    "food_freshness_profiles", "consumption_requirement_profiles",
    "consumption_interruption_profiles", "survival_message_profiles", "survival_render_profiles",
):
    DRAFT_FILES.setdefault(_survival_key, f"{_survival_key}.json")

# Phase 11C1 canonical gathering Builder collections.
for _gathering_key in (
    "resource_definitions", "resource_node_definitions", "resource_capacity_profiles",
    "resource_regeneration_profiles", "resource_availability_profiles", "resource_environment_profiles",
    "gathering_profiles", "gathering_tool_profiles", "resource_yield_profiles",
    "gathering_resource_cost_profiles", "gathering_interruption_profiles", "gathering_cooldown_profiles",
    "gathering_profession_xp_profiles", "gathering_message_profiles", "gathering_render_profiles", "gathering_access_profiles",
):
    DRAFT_FILES.setdefault(_gathering_key, f"{_gathering_key}.json")


# Phase 15B.38 canonical Object Builder capability contract.
OBJECT_BUILDER_SECTIONS = {
    "identity": ("name", "keywords", "short_description", "long_description", "look_description", "extra_descriptions"),
    "classification": ("item_type", "subtype", "category", "material", "quality", "rarity", "ownership", "binding"),
    "economy": ("weight", "cost", "stack_size", "destroy_timer"),
    "wear": ("wear_flags", "extra_flags", "slot_restrictions"),
    "combat": ("weapon_type", "attack_type", "damage_dice", "speed", "range", "armor_values", "resistances"),
    "container": ("capacity", "weight_capacity", "container_flags", "open", "closed", "locked", "lock_difficulty", "key_id", "transparent"),
    "magic": ("spell_storage", "charges", "recharge", "passive_effects", "affects", "scripts"),
    "light": ("fuel", "burn_time", "brightness"),
    "food": ("nutrition", "poison", "decay"),
    "drink": ("liquid_type", "servings", "poison"),
    "crafting": ("ingredients", "resource_tags", "recipes", "gathering"),
    "builder": ("builder_notes", "validation", "preview", "dependencies"),
}

TBA_OEDIT_EXTRA_FLAGS = ("glow", "hum", "dark", "lock", "evil", "invisible", "magic", "nodrop", "bless", "anti_good", "anti_evil", "anti_neutral", "noremove", "inventory", "unique")
TBA_OEDIT_WEAR_FLAGS = ("take", "finger", "neck", "body", "head", "legs", "feet", "hands", "arms", "shield", "about", "waist", "wrist", "wield", "hold", "float", "light", "mainhand", "offhand")
TBA_OEDIT_PERM_AFFECTS = ("blind", "invisible", "detect_invisible", "detect_magic", "sense_life", "waterwalk", "sanctuary", "group", "curse", "infravision", "poison", "protect_evil", "protect_good", "sleep", "notrack", "flying")
TBA_ITEM_TYPES = ("light", "scroll", "wand", "staff", "potion", "weapon", "armor", "container", "drink_container", "fountain", "food", "money", "furniture", "note", "other", "worn", "treasure", "trash", "key", "pen", "boat", "misc")
REDIT_DIRECTIONS = ("north", "east", "south", "west", "up", "down")
REDIT_REVERSE_DIRECTIONS = {"north": "south", "south": "north", "east": "west", "west": "east", "up": "down", "down": "up"}
REDIT_DOOR_TYPES = ("open_passage", "door", "closed_door", "locked_door")
REDIT_EXIT_FLAGS = ("hidden", "blocked", "pickproof", "climb", "swim", "fly", "crawl", "one_way", "no_mob", "no_player", "scripted")
REDIT_ROOM_FLAGS = ("dark", "death", "indoors", "peaceful", "soundproof", "nomob", "private")
REDIT_SECTORS = ("inside", "city", "field", "forest", "hills", "mountain", "water", "air")
TBA_APPLY_TYPES = ("strength", "dexterity", "intelligence", "wisdom", "constitution", "charisma", "class", "level", "age", "weight", "height", "mana", "hit", "move", "gold", "experience", "armor", "hitroll", "damroll", "saving_para", "saving_rod", "saving_petri", "saving_breath", "saving_spell")

def normalize_extra_keywords(value: Any) -> list[str]:
    raw = value if isinstance(value, list) else str(value or "").split()
    out: list[str] = []
    seen: set[str] = set()
    for part in raw:
        word = re.sub(r"\s+", " ", str(part or "").strip()).lower()
        word = re.sub(r"^[^a-z0-9_']+|[^a-z0-9_']+$", "", word)
        if not word or word in seen:
            continue
        seen.add(word); out.append(word)
    return out

def normalize_room_extra_descriptions(value: Any, room_id: str = "room") -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, Any]] = []
    used: set[str] = set()
    for i, raw in enumerate(value):
        rec = deepcopy(raw) if isinstance(raw, dict) else {"description": str(raw or "")}
        keywords = normalize_extra_keywords(rec.get("keywords") or rec.get("keyword") or rec.get("key") or rec.get("name") or "")
        desc = str(rec.get("description") or rec.get("text") or rec.get("long_description") or "").rstrip()
        eid = str(rec.get("id") or "").strip()
        if not eid:
            seed = "|".join([room_id, str(i), " ".join(keywords), desc[:40]])
            eid = "rextra_" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:10]
        base = re.sub(r"[^a-zA-Z0-9_:-]+", "_", eid).strip("_") or f"rextra_{i+1}"
        eid = base; n = 2
        while eid in used:
            eid = f"{base}_{n}"; n += 1
        used.add(eid)
        rec["id"] = eid; rec["keywords"] = keywords; rec["description"] = desc
        rec["sort_order"] = i
        if "enabled" in rec:
            rec["enabled"] = bool(rec.get("enabled"))
        normalized.append(rec)
    return normalized

def validate_room_extra_descriptions(rec: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    raw = rec.get("extra_descriptions", [])
    if raw in (None, ""):
        return issues
    if not isinstance(raw, list):
        return ["error: extra_descriptions must be a list"]
    ids: set[str] = set(); keyword_owner: dict[str, str] = {}
    for i, entry in enumerate(raw, 1):
        if not isinstance(entry, dict):
            issues.append(f"error: extra_descriptions[{i}] must be an object"); continue
        eid = str(entry.get("id") or "").strip()
        if not eid: issues.append(f"error: extra_descriptions[{i}] missing stable id")
        elif eid in ids: issues.append(f"error: extra_descriptions[{i}] duplicate id {eid}")
        ids.add(eid)
        keywords = normalize_extra_keywords(entry.get("keywords"))
        if not keywords: issues.append(f"error: extra_descriptions[{i}] requires at least one keyword")
        if len(keywords) != len(entry.get("keywords") or []): issues.append(f"warning: extra_descriptions[{i}] has duplicate or non-normal keywords")
        for kw in keywords:
            if kw in keyword_owner and keyword_owner[kw] != eid:
                issues.append(f"warning: extra description keyword '{kw}' also appears on {keyword_owner[kw]}; runtime uses first ordered match")
            keyword_owner.setdefault(kw, eid)
        if not str(entry.get("description") or "").strip():
            issues.append(f"error: extra_descriptions[{i}] description is empty")
        so = entry.get("sort_order", i-1)
        if not isinstance(so, int) or so < 0:
            issues.append(f"warning: extra_descriptions[{i}] sort_order should be a non-negative integer")
    return issues

OBJECT_NUMERIC_FIELDS = {"weight", "cost", "stack_size", "destroy_timer", "speed", "range", "capacity", "weight_capacity", "lock_difficulty", "charges", "recharge", "fuel", "burn_time", "brightness", "nutrition", "decay", "servings"}
OBJECT_LIST_FIELDS = {"keywords", "extra_descriptions", "wear_flags", "extra_flags", "slot_restrictions", "resistances", "container_flags", "spell_storage", "passive_effects", "affects", "scripts", "ingredients", "resource_tags", "recipes", "gathering"}
OBJECT_BOOL_FIELDS = {"open", "closed", "locked", "transparent", "poison"}
OBJECT_TEXT_FIELDS = set().union(*OBJECT_BUILDER_SECTIONS.values()) - OBJECT_NUMERIC_FIELDS - OBJECT_LIST_FIELDS - OBJECT_BOOL_FIELDS

def normalize_object_template(object_id: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    rec = deepcopy(data or {})
    rec.setdefault("id", object_id)
    rec.setdefault("name", object_id.replace("_", " ").title())
    rec.setdefault("keywords", object_id.replace("_", " ").split())
    rec.setdefault("short_description", rec.get("name"))
    rec.setdefault("long_description", f"{rec.get('name')} is here.")
    rec.setdefault("look_description", rec.get("long_description", ""))
    rec.setdefault("item_type", rec.get("type", "misc"))
    rec.setdefault("category", "object")
    rec.setdefault("weight", 0)
    rec.setdefault("cost", 0)
    rec.setdefault("stack_size", 1)
    rec.setdefault("wear_flags", [])
    rec.setdefault("extra_flags", [])
    rec.setdefault("builder_notes", "")
    return rec

def coerce_object_field(field: str, raw: Any) -> Any:
    if field in OBJECT_NUMERIC_FIELDS:
        try:
            val = int(raw)
        except Exception as exc:
            raise ValueError(f"{field} must be a number") from exc
        if val < 0:
            raise ValueError(f"{field} cannot be negative")
        return val
    if field in OBJECT_BOOL_FIELDS:
        if isinstance(raw, bool): return raw
        text = str(raw).strip().lower()
        if text in {"yes", "true", "on", "1"}: return True
        if text in {"no", "false", "off", "0"}: return False
        raise ValueError(f"{field} must be true/false")
    if field in OBJECT_LIST_FIELDS:
        if isinstance(raw, list): return raw
        return [x.strip() for x in str(raw).replace(";", ",").split(",") if x.strip()]
    return str(raw)

def validate_object_template(rec: dict[str, Any]) -> list[dict[str, Any]]:
    issues=[]; oid=str(rec.get("id") or "")
    for fld in ("id", "name", "item_type"):
        if not str(rec.get(fld) or "").strip(): issues.append({"severity":"error","field_path":fld,"message":f"{fld} is required.","object_id":oid})
    for fld in OBJECT_NUMERIC_FIELDS:
        if fld in rec:
            try: val=int(rec.get(fld) or 0)
            except Exception: issues.append({"severity":"error","field_path":fld,"message":f"{fld} must be numeric.","object_id":oid}); continue
            if val < 0: issues.append({"severity":"error","field_path":fld,"message":f"{fld} cannot be negative.","object_id":oid})
    kws=[str(x).lower() for x in rec.get("keywords") or []]
    if len(kws) != len(set(kws)): issues.append({"severity":"warning","field_path":"keywords","message":"Duplicate keywords.","object_id":oid})
    typ=str(rec.get("item_type") or "").lower()
    if typ == "weapon" and not rec.get("damage_dice"): issues.append({"severity":"warning","field_path":"damage_dice","message":"Weapon has no damage dice.","object_id":oid})
    if typ == "container" and not int(rec.get("capacity") or 0): issues.append({"severity":"warning","field_path":"capacity","message":"Container has no capacity.","object_id":oid})
    if rec.get("locked") and not rec.get("key_id"): issues.append({"severity":"warning","field_path":"key_id","message":"Locked object has no key reference.","object_id":oid})
    return issues

@dataclass
class BuilderResult:
    ok: bool
    message: str
    data: dict[str, Any] | None = None

class BuilderWorkspace:
    """Persists draft Builder edits under worlds/<world_id>/builder without touching live files."""
    def __init__(self, worlds_dir: Path | None = None, event_bus: Any | None = None) -> None:
        self.worlds_dir = Path(worlds_dir or WORLDS_DIR)
        self.event_bus = event_bus


    STARTER_AREA = {
        "id": "starter_guildlands", "name": "Starter Guildlands", "description": "The organized starter region for Shattered Realms, covering the guildhall crossing, civic halls, training spaces, market, tavern, roads, farms, forest edge, watchpost, and rat cellar used by new characters.",
        "vnum_start": 1000, "vnum_end": 1999, "room_vnum_start": 1000, "room_vnum_end": 1299,
        "object_vnum_start": 1300, "object_vnum_end": 1499, "mob_vnum_start": 1500, "mob_vnum_end": 1699,
        "spawn_vnum_start": 1700, "spawn_vnum_end": 1799,
        "flags": [], "tags": ["starter"], "plugin_data": {},
    }
    STARTER_ZONES = [
        ("guildhall_crossing", "Guildhall Crossing", 1000, 1029), ("registrar_hall", "Registrar Hall", 1030, 1049),
        ("training_grounds", "Training Grounds", 1050, 1079), ("market_lane", "Market Lane", 1080, 1119),
        ("wayfarers_mug", "Wayfarer's Mug", 1120, 1149), ("old_gate_road", "Old Gate Road", 1150, 1179),
        ("east_farmland", "East Farmland", 1180, 1209), ("emberwood_edge", "Emberwood Edge", 1210, 1239),
        ("abandoned_watchpost", "Abandoned Watchpost", 1240, 1269), ("rat_cellar", "Rat Cellar", 1270, 1299),
    ]
    ROOM_HINTS = {
        "guildhall_registrar_office": "registrar_hall", "registrar": "registrar_hall", "training": "training_grounds",
        "market": "market_lane", "tavern": "wayfarers_mug", "mug": "wayfarers_mug", "old_gate": "old_gate_road",
        "farmland": "east_farmland", "farm": "east_farmland", "emberwood": "emberwood_edge", "watchpost": "abandoned_watchpost",
        "rat_cellar": "rat_cellar", "cellar": "rat_cellar", "guildhall": "guildhall_crossing",
    }

    def migrate_starter(self, actor: Any) -> BuilderResult:
        if not self.can_build(actor):
            return BuilderResult(False, "You do not have permission for that command.")
        world_id = self.world_id(actor); root = self.ensure(world_id)
        self.snapshot(actor)
        drafts = self.load(world_id)
        before_live = {name: (self.worlds_dir/world_id/sub/name).read_text(encoding='utf-8') if (self.worlds_dir/world_id/sub/name).exists() else None for sub,name in [('areas','areas.json'),('zones','zones.json'),('rooms','rooms.json'),('items','items.json')]}
        areas = drafts.setdefault('areas', {}); zones = drafts.setdefault('zones', {}); rooms = drafts.setdefault('rooms', {})
        ac = 0; zc = 0; rm = 0; assigned = 0
        area = dict(self.STARTER_AREA, world_id=world_id, zone_ids=[z[0] for z in self.STARTER_ZONES])
        if 'starter_guildlands' not in areas: ac += 1
        areas['starter_guildlands'] = {**areas.get('starter_guildlands', {}), **area}
        zone_starts = {}
        for zid,name,start,end in self.STARTER_ZONES:
            zone_starts[zid]=start
            if zid not in zones: zc += 1
            zones[zid] = {**zones.get(zid, {}), 'id':zid, 'name':name, 'description':f'{name} starter zone.', 'world_id':world_id, 'area_id':'starter_guildlands', 'vnum_start':start, 'vnum_end':end, 'room_ids': zones.get(zid,{}).get('room_ids', []), 'flags':[], 'tags':['starter'], 'plugin_data':{}}
        counters = {zid:start for zid,_,start,_ in self.STARTER_ZONES}
        live_rooms = _records(self.worlds_dir/world_id, 'rooms')
        for lr in live_rooms:
            rid = str(lr.get('id') or '')
            if not rid: continue
            zid = self._starter_zone_for_room(lr)
            if rid == 'guildhall_crossing_square': vnum = 1000
            elif rid == 'guildhall_archway': vnum = 1001
            elif rid == 'guildhall_registrar_office': vnum = 1030
            elif rid == 'training_yard': vnum = 1050
            elif rid == 'market_lane': vnum = 1080
            elif rid == 'tavern_common_room': vnum = 1120
            elif rid == 'old_gate_road': vnum = 1150
            else:
                vnum = counters[zid]
                while any(r.get('area_id')=='starter_guildlands' and r.get('vnum')==vnum for r in rooms.values()): vnum += 1
            counters[zid] = max(counters[zid], vnum+1)
            ex = {}
            for e in lr.get('exits') or []:
                if isinstance(e, dict) and e.get('direction'):
                    ex[e['direction']] = {k:v for k,v in {'direction':e.get('direction'), 'target_room_id':e.get('target_room_id') or e.get('destination_room_id') or e.get('room_id'), 'description':e.get('description','')}.items() if v is not None}
            feats = {}
            for oid in lr.get('objects') or []:
                feats[str(oid)] = {'id': str(oid), 'name': str(oid).replace('_',' ').title(), 'portable': False, 'source': 'live room object'}
            rec = {'id':rid, 'name':lr.get('name') or lr.get('title') or rid.replace('_',' ').title(), 'description':lr.get('long_description') or lr.get('description') or lr.get('short_description') or '', 'world_id':world_id, 'area_id':'starter_guildlands', 'zone_id':zid, 'vnum':vnum, 'exits':ex, 'features':feats, 'flags':lr.get('flags') or [], 'tags':lr.get('tags') or [], 'plugin_data': {'migration_source':'live_starter'}}
            if rid not in rooms: rm += 1
            if not rooms.get(rid,{}).get('area_id') or not rooms.get(rid,{}).get('zone_id') or rooms.get(rid,{}).get('vnum') is None: assigned += 1
            rooms[rid] = rec
            zones[zid].setdefault('room_ids', [])
            if rid not in zones[zid]['room_ids']: zones[zid]['room_ids'].append(rid)
        self.save_drafts(world_id, drafts)
        changed_live = any(((self.worlds_dir/world_id/sub/name).read_text(encoding='utf-8') if (self.worlds_dir/world_id/sub/name).exists() else None) != txt for (sub,name),txt in zip([('areas','areas.json'),('zones','zones.json'),('rooms','rooms.json'),('items','items.json')], before_live.values()))
        self.audit(actor, world_id, 'builder migrate starter', 'world', world_id, None, {'rooms': rm, 'assigned': assigned})
        lines = ['Starter migration complete.', '', f'Areas created:\n{ac}', '', f'Zones created:\n{zc}', '', f'Rooms migrated:\n{len(live_rooms)}', '', f'Legacy rooms assigned:\n{assigned}', '', f'Live files changed:\n{"yes" if changed_live else "no"}', '', 'Builder drafts changed:\nyes', '', 'Next:', 'builder validate', 'rooms unassigned', 'builder save', 'builder export']
        return BuilderResult(True, '\n'.join(lines))

    def _starter_zone_for_room(self, room: dict[str, Any]) -> str:
        rid = str(room.get('id','')); aid = str(room.get('area_id',''))
        ids = {z[0] for z in self.STARTER_ZONES}
        if aid in ids: return aid
        text = f"{rid} {aid} {' '.join(room.get('tags') or [])}".lower()
        for key,zid in self.ROOM_HINTS.items():
            if key in text: return zid
        return 'guildhall_crossing'

    def import_list(self, actor: Any) -> BuilderResult:
        if not self.can_build(actor):
            return BuilderResult(False, "You do not have permission for that command.")
        world_id = self.world_id(actor)
        root = self.ensure(world_id)/'imports'; files = sorted(p.name for p in root.glob('*.json'))
        if not files:
            return BuilderResult(True, f'No import files found.\n\nCreate one by copying a template:\nbuilder template list\nbuilder template copy area_zone_room_template.json my_area.json\n\nImport folder:\nworlds/{world_id}/builder/imports/')
        return BuilderResult(True, 'Builder import files:\n' + '\n'.join(files))


    def template_list(self, actor: Any) -> BuilderResult:
        if not self.can_build(actor):
            return BuilderResult(False, "You do not have permission for that command.")
        root = self.ensure(self.world_id(actor)) / "templates"
        files = sorted(p.name for p in root.glob("*.json"))
        return BuilderResult(True, "Builder import templates:\n" + ("\n".join(files) if files else "- none"))

    def template_show(self, actor: Any, template_name: str) -> BuilderResult:
        if not self.can_build(actor):
            return BuilderResult(False, "You do not have permission for that command.")
        world_id = self.world_id(actor); path = self.ensure(world_id) / "templates" / Path(template_name).name
        if not path.exists():
            return BuilderResult(False, f"Template not found: {template_name}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            keys = [k for k, v in data.items() if isinstance(v, dict) and v]
        except Exception:
            keys = []
        summary = ", ".join(keys) if keys else "empty/current-key bundle"
        return BuilderResult(True, f"Template: {path.name}\nPath: worlds/{world_id}/builder/templates/{path.name}\nSummary: {summary}")

    def template_copy(self, actor: Any, template_name: str, new_filename: str, force: bool = False) -> BuilderResult:
        if not self.can_build(actor):
            return BuilderResult(False, "You do not have permission for that command.")
        world_id = self.world_id(actor); root = self.ensure(world_id)
        src = root / "templates" / Path(template_name).name
        dest = root / "imports" / Path(new_filename).name
        if not src.exists():
            return BuilderResult(False, f"Template not found: {template_name}")
        if dest.exists() and not force:
            return BuilderResult(False, f"Import file already exists: {dest.name} (use --force to overwrite)")
        shutil.copyfile(src, dest)
        return BuilderResult(True, f"Copied template {src.name} to worlds/{world_id}/builder/imports/{dest.name}")

    def _load_import_bundle(self, world_id: str, filename: str) -> tuple[dict[str, Any] | None, str, list[str]]:
        path = self.ensure(world_id) / "imports" / Path(filename).name
        if not path.exists():
            return None, f"Import file not found: {filename}", []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            return None, f"Invalid JSON: {e}", []
        future_keys = [str(k) for k in data.keys() if k not in DRAFT_FILES]
        if any(k in data for k in DRAFT_FILES):
            return {k: data.get(k, {}) for k in DRAFT_FILES}, "", future_keys
        return None, "Import bundle must contain Builder collections such as areas, zones, rooms, recipes, workstations, production profiles, quality profiles, features, items, entities, spawns, schedules, relationship seeds, memory seeds, need profiles, or goal profiles.", future_keys

    def import_validate(self, actor: Any, filename: str) -> BuilderResult:
        if not self.can_build(actor):
            return BuilderResult(False, "You do not have permission for that command.")
        bundle, err, future_keys = self._load_import_bundle(self.world_id(actor), filename)
        if err: return BuilderResult(False, 'Import validation failed.\n\nErrors:\n- '+err+'\n\nWarnings:\n- none')
        merged = self.load(self.world_id(actor));
        for k,v in bundle.items():
            if not isinstance(merged.get(k), dict): merged[k] = {}
            merged.setdefault(k, {}).update(v if isinstance(v,dict) else {})
        errors=[]; warnings=[f"Future top-level collection {key} is not applied by this version." for key in future_keys]; self._validate_bundle_refs(merged, errors, warnings)
        baseline_errors: list[str] = []
        baseline_warnings: list[str] = []
        self._validate_bundle_refs(self.load(self.world_id(actor)), baseline_errors, baseline_warnings)
        baseline = set(baseline_errors)
        errors = [e for e in errors if e not in baseline]
        ok=not errors
        return BuilderResult(ok, ('Import validation passed.' if ok else 'Import validation failed.')+'\n\nErrors:\n'+('\n'.join('- '+e for e in errors) if errors else '- none')+'\n\nWarnings:\n'+('\n'.join('- '+w for w in warnings) if warnings else '- none'))

    def import_preview(self, actor: Any, filename: str) -> BuilderResult:
        if not self.can_build(actor):
            return BuilderResult(False, "You do not have permission for that command.")
        bundle, err, future_keys = self._load_import_bundle(self.world_id(actor), filename)
        if err: return BuilderResult(False, err)
        drafts=self.load(self.world_id(actor)); names=[('areas','Areas'),('zones','Zones'),('rooms','Rooms'),('features','Features'),('items','Items'),('item_placements','Item placements'),('entities','Entities'),('spawns','Spawns'),('schedules','Schedules'),('relationship_seeds','Relationship seeds'),('memory_seeds','Memory seeds'),('need_profiles','Need profiles'),('goal_profiles','Goal profiles'),('formulas','Formulas'),('modifier_types','Modifier types'),('future_formula_templates','Future formula templates'),('abilities','Abilities'),('ability_loadouts','Ability loadouts'),('ability_schools','Ability schools'),('ability_categories','Ability categories'),('cooldown_groups','Cooldown groups'),('targeting_profiles','Targeting profiles'),('healing_profiles','Healing profiles'),('casting_profiles','Casting profiles'),('recipe_definitions','Recipes'),('workstation_profiles','Workstations'),('production_profiles','Production profiles'),('item_quality_profiles','Item quality profiles'),('crafting_quality_profiles','Crafting quality profiles'),('ingredient_substitution_profiles','Ingredient substitution profiles'),('crafting_message_profiles','Crafting message profiles'),('profession_experience_curves','Profession experience curves'),('profession_growth_profiles','Profession growth profiles'),('resource_definitions','Resource definitions'),('resource_node_definitions','Resource node definitions'),('resource_capacity_profiles','Resource capacity profiles'),('resource_regeneration_profiles','Resource regeneration profiles'),('resource_availability_profiles','Resource availability profiles'),('resource_environment_profiles','Resource environment profiles'),('gathering_profiles','Gathering profiles'),('gathering_tool_profiles','Gathering tool profiles'),('resource_yield_profiles','Resource yield profiles'),('gathering_resource_cost_profiles','Gathering resource cost profiles'),('gathering_interruption_profiles','Gathering interruption profiles'),('gathering_cooldown_profiles','Gathering cooldown profiles'),('gathering_profession_xp_profiles','Gathering profession XP profiles'),('gathering_message_profiles','Gathering message profiles'),('gathering_render_profiles','Gathering render profiles'),('gathering_access_profiles','Gathering access profiles')]
        lines=[]
        for k,label in names:
            b=bundle.get(k,{}) if isinstance(bundle.get(k,{}),dict) else {}; add=sum(1 for x in b if x not in drafts.get(k,{})); upd=len(b)-add; lines.append(f'{label} to add/update: {add}/{upd}')
        errors=[]; warnings=[f"Future top-level collection {key} is not applied by this version." for key in future_keys]; merged=deepcopy(drafts)
        for k,v in bundle.items():
            if not isinstance(merged.get(k), dict): merged[k] = {}
            merged.setdefault(k,{}).update(v if isinstance(v,dict) else {})
        self._validate_bundle_refs(merged,errors,warnings)
        baseline_errors: list[str] = []
        baseline_warnings: list[str] = []
        self._validate_bundle_refs(drafts, baseline_errors, baseline_warnings)
        baseline = set(baseline_errors)
        errors = [e for e in errors if e not in baseline]
        lines += ['', 'Conflicts:', '- none', 'Legacy/unassigned warnings:', *(('- '+w for w in warnings if 'legacy' in w.lower()) or ['- none']), 'Broken references:', *(('- '+e for e in errors) or ['- none']), '', 'No files changed.']
        return BuilderResult(True, '\n'.join(lines))

    def import_apply(self, actor: Any, filename: str, replace: bool=False) -> BuilderResult:
        if not self.can_build(actor):
            return BuilderResult(False, "You do not have permission for that command.")
        bundle, err, future_keys = self._load_import_bundle(self.world_id(actor), filename)
        if err: return BuilderResult(False, err)
        if replace: self.snapshot(actor); drafts={k:{} for k in DRAFT_FILES}
        else: drafts=self.load(self.world_id(actor))
        for k,v in bundle.items():
            if not isinstance(drafts.get(k), dict): drafts[k] = {}
            drafts.setdefault(k,{}).update(v if isinstance(v,dict) else {})
        self.save_drafts(self.world_id(actor), drafts); self.audit(actor,self.world_id(actor),'builder import apply','import',filename,None,{'replace':replace})
        return BuilderResult(True, f'Builder import applied: {filename}\nMode: {"replace-drafts" if replace else "merge"}')

    def _validate_bundle_refs(self, drafts: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
        safe=re.compile(r'^[a-z0-9]+(?:_[a-z0-9]+)*$'); areas=drafts.get('areas',{}); zones=drafts.get('zones',{}); rooms=drafts.get('rooms',{}); live_items={str(r.get('id')) for r in _records(self.worlds_dir / 'shattered_realms', 'items') if r.get('id')}
        for kind,bucket in [('area',areas),('zone',zones),('room',rooms)]:
            for oid in bucket:
                if not safe.fullmatch(str(oid)): errors.append(f'{kind} ID unsafe: {oid}')
        for zid,z in zones.items():
            if z.get('area_id') not in areas: errors.append(f'zone {zid} references missing area {z.get("area_id")}')
        seen={}
        for rid,r in rooms.items():
            if not r.get('name'): errors.append(f'room {rid} missing name')
            if not r.get('description'): warnings.append(f'room {rid} missing description')
            aid,zid=r.get('area_id'),r.get('zone_id')
            if not aid or not zid: warnings.append(f'Legacy room {rid} has no area or zone.')
            elif aid not in areas: errors.append(f'room {rid} references missing area {aid}')
            elif zid not in zones: errors.append(f'room {rid} references missing zone {zid}')
            elif zones[zid].get('area_id') != aid: errors.append(f'room {rid} zone {zid} does not belong to area {aid}')
            v=r.get('vnum')
            if aid and v is not None:
                seen.setdefault((aid,v),[]).append(rid)
                a=areas.get(aid,{}); z=zones.get(zid,{})
                if a and not int(a.get('room_vnum_start') or a.get('vnum_start') or v) <= int(v) <= int(a.get('room_vnum_end') or a.get('vnum_end') or v): errors.append(f'room {rid} vnum outside area range')
                if z and not int(z.get('vnum_start') or v) <= int(v) <= int(z.get('vnum_end') or v): errors.append(f'room {rid} vnum outside zone range')
            for d,e in (r.get('exits') or {}).items():
                t=e.get('target_room_id') or e.get('destination_room_id') or e.get('room_id')
                if t and t not in rooms: errors.append(f'room {rid} exit {d} references missing room {t}')
        for (aid,v),ids in seen.items():
            if len(ids)>1: errors.append(f'duplicate vnum {v} inside area {aid}: {", ".join(ids)}')
        for pid, pl in drafts.get('item_placements', {}).items():
            if not safe.fullmatch(str(pid)): errors.append(f'item placement ID unsafe: {pid}')
            if pl.get('item_template_id') not in drafts.get('items', {}) and pl.get('item_template_id') not in live_items: errors.append(f'item placement {pid} references missing item template {pl.get("item_template_id")}')
            if pl.get('room_id') not in rooms: errors.append(f'item placement {pid} references missing room {pl.get("room_id")}')
        from engine.formulas import FormulaDefinition, FormulaRegistry, ModifierRegistry
        freg = FormulaRegistry()
        for fid, raw in drafts.get("formulas", {}).items():
            if not isinstance(raw, dict): errors.append(f"formula {fid} must be an object"); continue
            try:
                freg.register(FormulaDefinition(id=str(raw.get("id") or fid), display_name=str(raw.get("display_name") or ""), description=str(raw.get("description") or ""), version=str(raw.get("version") or "1.0.0"), dependencies=list(raw.get("dependencies") or []), inputs=list(raw.get("inputs") or []), outputs=list(raw.get("outputs") or []), validation=dict(raw.get("validation") or {}), plugin_owner=raw.get("plugin_owner"), builder_owner=raw.get("builder_owner"), world_overrides=dict(raw.get("world_overrides") or {}), plugin_data=dict(raw.get("plugin_data") or {})))
            except ValueError as exc: errors.append(str(exc))
        fv = freg.validate(); errors.extend(fv.errors); warnings.extend(fv.warnings)
        known = ModifierRegistry().modifier_types
        for mid, raw in drafts.get("modifier_types", {}).items():
            if not isinstance(raw, dict): warnings.append(f"unknown modifier type {mid} must be an object"); continue
            op = str(raw.get("operation") or raw.get("id") or mid)
            if op not in known: warnings.append(f"unknown modifier type {mid}")

    def can_build(self, actor: Any) -> bool:
        roles = {str(getattr(actor, "role", "player")).lower(), str(getattr(actor, "account_role", "player")).lower()}
        return bool(roles & BUILDER_ROLES)

    def ensure(self, world_id: str) -> Path:
        root = self.worlds_dir / world_id / "builder"
        for name in ("audit", "history", "snapshots", "exports", "imports", "templates", "examples"):
            (root / name).mkdir(parents=True, exist_ok=True)
        starters = {
            "attack_family_definitions": {fam: {"id": fam, "display_name": fam.replace("_", " ").title()} for fam in SEED_ATTACK_FAMILIES},
            "body_profiles": {"wolf": {"id":"wolf", "capabilities":["fangs","claws"], "suggested_natural_weapon_ids":["wolf_fangs","wolf_claws"]}, "bear": {"id":"bear", "capabilities":["teeth","claws","paws"], "suggested_natural_weapon_ids":["bear_claw","bear_bite","bear_maul"]}, "humanoid": {"id":"humanoid", "capabilities":["fists"], "suggested_natural_weapon_ids":["humanoid_fist"]}},
            "natural_weapon_profiles": {"wolf_fangs": _canonical_weapon({"id":"wolf_fangs","family":"bite","noun":"fangs","verb":"bites","damage_type":"piercing","damage_dice":"1d6","weight":100}, "wolf"), "wolf_claws": _canonical_weapon({"id":"wolf_claws","family":"claw","noun":"claws","verb":"rakes","damage_type":"slashing","damage_dice":"1d4","weight":30}, "wolf"), "bear_claw": _canonical_weapon({"id":"bear_claw","family":"claw","noun":"claws","verb":"claws","damage_type":"slashing","damage_dice":"1d8","weight":50}, "bear"), "bear_bite": _canonical_weapon({"id":"bear_bite","family":"bite","noun":"teeth","verb":"bites","damage_type":"piercing","damage_dice":"1d8","weight":25}, "bear"), "bear_maul": _canonical_weapon({"id":"bear_maul","family":"maul","noun":"paws","verb":"mauls","damage_type":"bludgeoning","damage_dice":"2d6","weight":25}, "bear")},
            "formulas": {"attack_rating": {"id": "attack_rating", "display_name": "Attack Rating", "description": "Starter placeholder; Builders may replace this formula later.", "version": "1.0.0", "dependencies": [], "inputs": [], "outputs": ["attack_rating"], "validation": {"placeholder": True}, "plugin_owner": None, "builder_owner": None, "world_overrides": {}, "plugin_data": {}}},
            "modifier_types": {"add": {"id": "add", "operation": "add", "description": "Adds a contributed value without defining gameplay math."}, "custom": {"id": "custom", "operation": "custom", "description": "Reserved for future plugin or Builder-defined modifier handling."}},
            "future_formula_templates": {"derived_stat_template": {"id": "builder_defined_stat", "display_name": "Builder Defined Stat", "description": "Copy this shape when authoring a future formula.", "version": "1.0.0", "dependencies": [], "inputs": ["future_variable"], "outputs": ["builder_defined_stat"], "validation": {}, "plugin_owner": None, "builder_owner": "builder", "world_overrides": {}, "plugin_data": {}}},
        }
        for key, filename in DRAFT_FILES.items():
            path = root / filename
            if not path.exists():
                path.write_text(json.dumps(starters.get(key, {}), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return root

    def _coerce_draft_collection(self, key: str, filename: str, raw: Any) -> dict[str, Any]:
        if not isinstance(raw, dict):
            return {}
        wrapper_keys = {key, filename[:-5] if filename.endswith(".json") else filename}
        if key == "items":
            wrapper_keys.add("item_templates")
        for wrapper in wrapper_keys:
            nested = raw.get(wrapper)
            if isinstance(nested, dict):
                return nested
            if isinstance(nested, list):
                return {str(x.get("id")): x for x in nested if isinstance(x, dict) and x.get("id")}
        if raw.get("id"):
            return {str(raw["id"]): raw}
        return raw

    def load(self, world_id: str) -> dict[str, Any]:
        root = self.ensure(world_id)
        drafts = {key: self._coerce_draft_collection(key, filename, self._read(root / filename, {})) for key, filename in DRAFT_FILES.items()}
        changed = self.normalize_drafts(world_id, drafts)
        if changed:
            self.save_drafts(world_id, drafts)
        return drafts


    def normalize_area(self, world_id: str, area_id: str, area: Any) -> tuple[dict[str, Any], bool]:
        original = deepcopy(area) if isinstance(area, dict) else area
        record = deepcopy(area) if isinstance(area, dict) else {}
        now = self.stamp()
        record.setdefault("id", area_id); record.setdefault("name", area_id.replace("_", " ").title())
        record.setdefault("description", ""); record.setdefault("world_id", world_id)
        for k in ("vnum_start","vnum_end","room_vnum_start","room_vnum_end","object_vnum_start","object_vnum_end","mob_vnum_start","mob_vnum_end","spawn_vnum_start","spawn_vnum_end"):
            record.setdefault(k, None)
        record.setdefault("zone_ids", []); record.setdefault("flags", []); record.setdefault("tags", []); record.setdefault("plugin_data", {})
        record.setdefault("created_at", now); record.setdefault("updated_at", record.get("created_at") or now)
        ordered = {k: record.get(k) for k in ("id","name","description","world_id","vnum_start","vnum_end","room_vnum_start","room_vnum_end","object_vnum_start","object_vnum_end","mob_vnum_start","mob_vnum_end","spawn_vnum_start","spawn_vnum_end","zone_ids","flags","tags","plugin_data","created_at","updated_at")}
        for k, v in record.items():
            if k not in ordered: ordered[k] = v
        return ordered, ordered != original

    def normalize_zone(self, world_id: str, zone_id: str, zone: Any) -> tuple[dict[str, Any], bool]:
        original = deepcopy(zone) if isinstance(zone, dict) else zone
        record = deepcopy(zone) if isinstance(zone, dict) else {}
        now = self.stamp()
        record.setdefault("id", zone_id); record.setdefault("name", zone_id.replace("_", " ").title())
        record.setdefault("description", ""); record.setdefault("world_id", world_id); record.setdefault("area_id", "")
        record.setdefault("vnum_start", None); record.setdefault("vnum_end", None); record.setdefault("room_ids", [])
        record.setdefault("flags", []); record.setdefault("tags", []); record.setdefault("plugin_data", {})
        record.setdefault("created_at", now); record.setdefault("updated_at", record.get("created_at") or now)
        ordered = {k: record.get(k) for k in ("id","name","description","world_id","area_id","vnum_start","vnum_end","room_ids","flags","tags","plugin_data","created_at","updated_at")}
        for k, v in record.items():
            if k not in ordered: ordered[k] = v
        return ordered, ordered != original

    def normalize_room(self, world_id: str, room_id: str, room: Any) -> tuple[dict[str, Any], bool]:
        original = deepcopy(room) if isinstance(room, dict) else room
        record = deepcopy(room) if isinstance(room, dict) else {}
        record.setdefault("id", room_id)
        record.setdefault("name", "")
        record.setdefault("description", "")
        record.setdefault("world_id", world_id)
        record.setdefault("area_id", "")
        record.setdefault("zone_id", "")
        record.setdefault("vnum", None)
        if not isinstance(record.get("exits"), dict): record["exits"] = {}
        if not isinstance(record.get("features"), dict): record["features"] = {}
        if not isinstance(record.get("flags"), list): record["flags"] = []
        if not isinstance(record.get("tags"), list): record["tags"] = []
        if not isinstance(record.get("plugin_data"), dict): record["plugin_data"] = {}
        record["extra_descriptions"] = normalize_room_extra_descriptions(record.get("extra_descriptions"), room_id)
        ordered = {k: record.get(k) for k in ("id","name","description","world_id","area_id","zone_id","vnum","exits","features","extra_descriptions","flags","tags","plugin_data")}
        for k, v in record.items():
            if k not in ordered: ordered[k] = v
        return ordered, ordered != original

    def normalize_drafts(self, world_id: str, drafts: dict[str, Any], actor: Any | None = None) -> bool:
        changed = False
        drafts.setdefault("world", {})
        areas = drafts.setdefault("areas", {})
        for area_id in list(areas.keys()):
            normalized, did = self.normalize_area(world_id, str(area_id), areas[area_id])
            areas[area_id] = normalized
            changed = changed or did
        zones = drafts.setdefault("zones", {})
        for zone_id in list(zones.keys()):
            normalized, did = self.normalize_zone(world_id, str(zone_id), zones[zone_id])
            zones[zone_id] = normalized
            changed = changed or did
        rooms = drafts.setdefault("rooms", {})
        for room_id in list(rooms.keys()):
            normalized, did = self.normalize_room(world_id, str(room_id), rooms[room_id])
            rooms[room_id] = normalized
            if did:
                changed = True
                if actor is not None:
                    self.audit(actor, world_id, "draft normalization", "room", str(room_id), None, normalized)
                    self.publish("builder_draft_room_normalized", actor, world_id, "room", str(room_id), command="draft normalization")
        entities = drafts.setdefault("entities", {})
        for entity_id, rec in list(entities.items()):
            if isinstance(rec, dict) and rec.get("natural_attacks") is not None:
                before = deepcopy(rec); attacks = rec.pop("natural_attacks") or []
                cp = dict(rec.get("combat_profile") or {})
                cp["natural_weapons"] = [_canonical_weapon(x, str(entity_id)) for x in attacks if isinstance(x, dict)]
                rec["combat_profile"] = cp; rec.setdefault("migration_log", []).append({"schema":"natural_attacks_to_combat_profile.natural_weapons","timestamp":self.stamp()})
                entities[entity_id] = rec; changed = True
                if actor is not None: self.audit(actor, world_id, "schema migration", "entities", str(entity_id), before, rec)
        return changed

    def save_drafts(self, world_id: str, drafts: dict[str, Any]) -> None:
        self.normalize_drafts(world_id, drafts)
        root = self.ensure(world_id)
        for key, filename in DRAFT_FILES.items():
            (root / filename).write_text(json.dumps(drafts.get(key, {}), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _atomic_json_write(self, path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(path)

    def publish_drafts(self, actor: Any) -> BuilderResult:
        """Transactionally publish Builder display drafts to canonical package files."""
        world_id = self.world_id(actor)
        drafts = self.load(world_id)
        world_root = self.worlds_dir / world_id
        from engine.display_themes import SUPPORTED_FAMILIES, validate_display_theme
        from engine.mud_displays import PROMPT_PRESETS

        errors: list[str] = []
        theme_drafts = drafts.get("display_themes") or {}
        if not isinstance(theme_drafts, dict):
            errors.append("display_themes draft must be an object keyed by theme id")
            theme_drafts = {}
        candidate_themes: list[dict[str, Any]] = []
        theme_ids: set[str] = set()
        for key, raw in sorted(theme_drafts.items()):
            if not isinstance(raw, dict):
                errors.append(f"display theme {key} must be an object")
                continue
            rec = deepcopy(raw)
            tid = str(rec.get("theme_id") or rec.get("id") or key or "").strip()
            if not tid:
                errors.append(f"display theme {key} is missing theme_id")
                continue
            rec["theme_id"] = tid
            rec.setdefault("name", tid.replace("_", " ").title())
            theme_ids.add(tid)
            for err in validate_display_theme(rec):
                errors.append(f"display theme {tid}: {err}")
            candidate_themes.append(rec)

        def _check_assignment(scope: str, object_id: str, record: dict[str, Any]) -> None:
            one = str(record.get("display_theme_id") or "")
            if one and one not in theme_ids:
                errors.append(f"{scope} {object_id} display_theme_id references missing theme {one}")
            fams = record.get("display_theme_ids") or {}
            if fams and not isinstance(fams, dict):
                errors.append(f"{scope} {object_id} display_theme_ids must be an object")
                return
            for family, theme_id in fams.items():
                if str(family) not in SUPPORTED_FAMILIES:
                    errors.append(f"{scope} {object_id} has unsupported display family {family}")
                if str(theme_id) not in theme_ids:
                    errors.append(f"{scope} {object_id} display_theme_ids.{family} references missing theme {theme_id}")

        world_meta_by_id = drafts.get("world") if isinstance(drafts.get("world"), dict) else {}
        world_meta = deepcopy(world_meta_by_id.get(world_id) if isinstance(world_meta_by_id.get(world_id), dict) else world_meta_by_id)
        default_theme = str(world_meta.get("default_display_theme_id") or "")
        if default_theme and default_theme not in theme_ids:
            errors.append(f"world default_display_theme_id references missing theme {default_theme}")
        prompt_preset = str(world_meta.get("default_prompt_preset") or "")
        if prompt_preset and prompt_preset not in PROMPT_PRESETS and not any(prompt_preset in (t.get("prompt_presets") or {}) for t in candidate_themes):
            errors.append(f"world default_prompt_preset references missing prompt preset {prompt_preset}")
        _check_assignment("world", world_id, world_meta)
        for area_id, area in (drafts.get("areas") or {}).items():
            if isinstance(area, dict): _check_assignment("area", str(area_id), area)
        for zone_id, zone in (drafts.get("zones") or {}).items():
            if isinstance(zone, dict): _check_assignment("zone", str(zone_id), zone)

        if errors:
            return BuilderResult(False, "Builder publish failed.\n" + "\n".join(f"- {e}" for e in errors), {"errors": errors})

        writes = [
            (world_root / "display_themes" / "display_themes.json", {"display_themes": candidate_themes}),
            (world_root / "world" / "world.json", world_meta),
            (world_root / "areas" / "areas.json", list((drafts.get("areas") or {}).values())),
            (world_root / "zones" / "zones.json", list((drafts.get("zones") or {}).values())),
        ]
        for path, data in writes:
            self._atomic_json_write(path, data)
        self.audit(actor, world_id, "builder publish", "display_theme", world_id, None, {"themes": sorted(theme_ids)})
        self.publish("builder_publish_completed", actor, world_id, "display_theme", world_id, command="builder publish")
        return BuilderResult(True, "Display theme changes were published. Reload the world or restart Smart MUD to apply them.")

    def current_room_id(self, actor: Any) -> str:
        return str(getattr(actor, "edit_room_id", "") or getattr(actor, "last_edited_target", "") or getattr(actor, "room_id", "") or getattr(actor, "current_room_id", "") or "start")

    def world_id(self, actor: Any) -> str:
        return str(getattr(actor, "world_id", "") or "shattered_realms")

    def set_builder_mode(self, actor: Any, enabled: bool) -> BuilderResult:
        if not self.can_build(actor):
            self.publish("builder_permission_denied", actor, self.world_id(actor), "builder", "mode", command="builder")
            return BuilderResult(False, "You do not have permission for that command.")
        setattr(actor, "builder_mode", enabled)
        setattr(actor, "builder_enabled", enabled)
        self.publish("builder_mode_enabled" if enabled else "builder_mode_disabled", actor, self.world_id(actor), "builder", "mode", command="builder")
        return BuilderResult(True, f"Builder mode is now {'ON' if enabled else 'OFF'}.")

    def create_or_update(self, actor: Any, collection: str, object_id: str, updates: dict[str, Any], action: str, target_type: str) -> BuilderResult:
        world_id = self.world_id(actor); drafts = self.load(world_id)
        bucket = drafts.setdefault(collection, {})
        before = deepcopy(bucket.get(object_id))
        record = deepcopy(before) if isinstance(before, dict) else {"id": object_id}
        record.update(updates)
        bucket[object_id] = record
        self.save_drafts(world_id, drafts)
        self.audit(actor, world_id, action, target_type, object_id, before, record)
        event = f"builder_{target_type}_created" if before is None and action.endswith("create") else f"builder_{target_type}_updated"
        self.publish(event, actor, world_id, target_type, object_id, command=action)
        return BuilderResult(True, f"Draft {target_type} {object_id} {('created' if before is None else 'updated')}.", record)

    def delete(self, actor: Any, collection: str, object_id: str, target_type: str) -> BuilderResult:
        world_id = self.world_id(actor); drafts = self.load(world_id); before = drafts.get(collection, {}).pop(object_id, None)
        self.save_drafts(world_id, drafts); self.audit(actor, world_id, "delete", target_type, object_id, before, None)
        return BuilderResult(True, f"Draft {target_type} {object_id} deleted." if before else f"Draft {target_type} {object_id} was not present.")

    def set_exit(self, actor: Any, direction: str, updates: dict[str, Any], create: bool = False) -> BuilderResult:
        room_id = self.current_room_id(actor); world_id = self.world_id(actor); drafts = self.load(world_id)
        room = drafts.setdefault("rooms", {}).setdefault(room_id, {"id": room_id, "exits": {}})
        exits = room.setdefault("exits", {})
        before = deepcopy(exits.get(direction))
        ex = deepcopy(before) if isinstance(before, dict) else {"direction": direction}
        ex.update(updates); exits[direction] = ex
        self.save_drafts(world_id, drafts); self.audit(actor, world_id, "excreate" if create else "exset", "exit", f"{room_id}:{direction}", before, ex)
        self.publish("builder_exit_created" if create and before is None else "builder_exit_updated", actor, world_id, "exit", f"{room_id}:{direction}", command="excreate" if create else "exset")
        return BuilderResult(True, f"Draft exit {direction} {'created' if create and before is None else 'updated'}.", ex)

    def validate(self, actor: Any) -> BuilderResult:
        world_id = self.world_id(actor); root = self.ensure(world_id); raw_rooms = self._read(root / DRAFT_FILES["rooms"], {})
        drafts = self.load(world_id); errors=[]; warnings=[]; info=[]
        required = {"id": str, "name": str, "description": str, "world_id": str, "area_id": str, "zone_id": str, "exits": dict, "features": dict, "flags": list, "tags": list, "plugin_data": dict}
        for rid, raw in raw_rooms.items():
            if not isinstance(raw, dict) or any(k not in raw for k in required):
                warnings.append(f"room {rid} was partial and has been normalized")
            elif any(not isinstance(raw.get(k), typ) for k, typ in required.items()):
                warnings.append(f"room {rid} had invalid draft field types and has been normalized")
        safe_re = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
        areas = drafts.get("areas", {}); zones = drafts.get("zones", {})
        for aid, area in areas.items():
            if not safe_re.fullmatch(str(aid)): errors.append(f"area {aid} has unsafe id")
        area_items = list(areas.items())
        for i, (a1, one) in enumerate(area_items):
            for a2, two in area_items[i+1:]:
                if None not in (one.get("vnum_start"), one.get("vnum_end"), two.get("vnum_start"), two.get("vnum_end")) and int(one["vnum_start"]) <= int(two["vnum_end"]) and int(two["vnum_start"]) <= int(one["vnum_end"]):
                    errors.append(f"area vnum ranges overlap: {a1} and {a2}")
        theme_ids = {str((r or {}).get("theme_id") or (r or {}).get("id")) for r in _records(self.worlds_dir / world_id, "display_themes") if isinstance(r, dict)} | {"classic_adventurer", "minimal_modern"}
        families = {"score","worth","inventory","equipment","affects","skills","spells","abilities","cooldowns","prompt","quest_log","shop","board","trainer","help"}
        wmeta = (drafts.get("world") or {}).get(world_id, {}) if isinstance(drafts.get("world"), dict) else {}
        if wmeta.get("default_display_theme_id") and str(wmeta.get("default_display_theme_id")) not in theme_ids: errors.append(f"world default_display_theme_id references missing theme {wmeta.get('default_display_theme_id')}")
        for aid, area in areas.items():
            if area.get("display_theme_id") and str(area.get("display_theme_id")) not in theme_ids: errors.append(f"area {aid} references missing display theme {area.get('display_theme_id')}")
            for fam, tid in (area.get("display_theme_ids") or {}).items():
                if fam not in families: errors.append(f"area {aid} invalid display family {fam}")
                if str(tid) not in theme_ids: errors.append(f"area {aid} family {fam} references missing display theme {tid}")
        for zid, zone in zones.items():
            if zone.get("display_theme_id") and str(zone.get("display_theme_id")) not in theme_ids: errors.append(f"zone {zid} references missing display theme {zone.get('display_theme_id')}")
            for fam, tid in (zone.get("display_theme_ids") or {}).items():
                if fam not in families: errors.append(f"zone {zid} invalid display family {fam}")
                if str(tid) not in theme_ids: errors.append(f"zone {zid} family {fam} references missing display theme {tid}")
        for zid, zone in zones.items():
            if not safe_re.fullmatch(str(zid)): errors.append(f"zone {zid} has unsafe id")
            aid = zone.get("area_id")
            if aid not in areas: errors.append(f"zone {zid} assigned to missing area {aid}")
            else:
                area = areas[aid]
                if int(zone.get("vnum_start") or 0) < int(area.get("vnum_start") or 0) or int(zone.get("vnum_end") or 0) > int(area.get("vnum_end") or 0): errors.append(f"zone {zid} range outside area {aid} range")
            for room_id in zone.get("room_ids") or []:
                if str(room_id) not in drafts.get("rooms", {}):
                    errors.append(f"zone {zid} room_ids references missing room {room_id}")
        by_area = {}
        for zid, z in zones.items(): by_area.setdefault(z.get("area_id"), []).append((zid,z))
        for aid, zs in by_area.items():
            for i, (z1, one) in enumerate(zs):
                for z2, two in zs[i+1:]:
                    if int(one.get("vnum_start") or 0) <= int(two.get("vnum_end") or 0) and int(two.get("vnum_start") or 0) <= int(one.get("vnum_end") or 0): errors.append(f"zone vnum ranges overlap in area {aid}: {z1} and {z2}")

        live_rooms = {str(r.get("id")) for r in _records(self.worlds_dir / world_id, "rooms") if r.get("id")}
        live_items = {str(r.get("id")) for r in _records(self.worlds_dir / world_id, "items") if r.get("id")}
        draft_rooms = set(drafts["rooms"].keys()); all_rooms = live_rooms | draft_rooms
        reverse = {"north":"south","south":"north","east":"west","west":"east","up":"down","down":"up","in":"out","out":"in"}
        seen_names = {}
        for rid, room in drafts["rooms"].items():
            nm = str((room or {}).get("name") or "").strip().lower()
            if nm:
                seen_names.setdefault(nm, []).append(str(rid))
        for nm, ids in seen_names.items():
            if len(ids) > 1:
                warnings.append(f"duplicate room display name {nm}: {', '.join(ids)}")
        area_vnums = {}
        for rid, room in drafts["rooms"].items():
            key=(room.get("area_id"), room.get("vnum"))
            if key[0] and key[1] is not None:
                area_vnums.setdefault(key, []).append(str(rid))
        for (aid,v), ids in area_vnums.items():
            if len(ids)>1: errors.append(f"duplicate vnum {v} within area {aid}: {', '.join(ids)}")
        for rid, room in drafts["rooms"].items():
            if not str(rid).strip() or any(ch.isspace() for ch in str(rid)) or not re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", str(rid)): errors.append(f"room {rid} has unsafe id")
            if rid in live_rooms: warnings.append(f"room {rid} shadows live room")
            if "world_id" not in room: errors.append(f"room {rid} missing world_id")
            if "area_id" not in room: warnings.append(f"room {rid} missing area_id field")
            if "zone_id" not in room: warnings.append(f"room {rid} missing zone_id field")
            if not room.get("area_id") or not room.get("zone_id"):
                warnings.append(f"legacy loose room {rid}; use rassign <room_id> area current zone current vnum <number>")
            elif room.get("area_id") not in areas: errors.append(f"room {rid} assigned to missing area {room.get('area_id')}")
            elif room.get("zone_id") not in zones: errors.append(f"room {rid} assigned to missing zone {room.get('zone_id')}")
            if room.get("vnum") is not None and room.get("area_id") in areas:
                v = int(room.get("vnum")); area = areas[room.get("area_id")]; expected = f"{room.get('area_id')}_{v}"
                if str(rid) != expected: warnings.append(f"assigned room ID does not match generated convention: room {rid} canonical {expected}")
                if v < int(area.get("room_vnum_start") or area.get("vnum_start") or v) or v > int(area.get("room_vnum_end") or area.get("vnum_end") or v): errors.append(f"room {rid} vnum outside area room range")
                z = zones.get(room.get("zone_id"))
                if z and (v < int(z.get("vnum_start") or v) or v > int(z.get("vnum_end") or v)): errors.append(f"room {rid} vnum outside zone range")
            if not isinstance(room.get("exits"), dict): errors.append(f"room {rid} missing exits dictionary")
            if not isinstance(room.get("features"), dict): warnings.append(f"room {rid} missing features dictionary")
            if not isinstance(room.get("flags"), list): warnings.append(f"room {rid} missing flags list")
            if not isinstance(room.get("tags"), list): warnings.append(f"room {rid} missing tags list")
            if not isinstance(room.get("plugin_data"), dict): warnings.append(f"room {rid} missing plugin_data dictionary")
            if not room.get("name"): warnings.append(f"room {rid} missing name")
            if self._looks_like_id(room.get("name", "")): warnings.append(f"room {rid} name looks like a room ID")
            suggested = str(rid).replace("_", " ").title()
            name_text = str(room.get("name") or "").strip()
            if name_text and name_text.lower() != suggested.lower() and name_text.lower().replace(" ", "_") in str(rid).lower():
                warnings.append(f"Room {rid} has a confusing display name: {name_text}. Suggested name: {suggested}.")
            if not room.get("description"): warnings.append(f"room {rid} missing description")
            for issue in validate_room_extra_descriptions(room):
                (errors if issue.startswith("error:") else warnings).append(f"room {rid} {issue.split(': ',1)[1] if ': ' in issue else issue}")
            for d, ex in (room.get("exits") or {}).items():
                target = ex.get("target_room_id") or ex.get("to") or ex.get("room_id")
                if not target: errors.append(f"room {rid} exit {d} missing target_room_id")
                elif str(target) not in all_rooms: errors.append(f"room {rid} exit {d} references missing room {target}")
                elif str(target) == str(rid): warnings.append(f"room {rid} exit {d} is a self-loop")
                rev = reverse.get(str(d).lower())
                if target and rev and str(target) in drafts["rooms"]:
                    rex = (drafts["rooms"].get(str(target), {}).get("exits") or {}).get(rev) or {}
                    rtarget = rex.get("target_room_id") or rex.get("to") or rex.get("room_id")
                    if not rtarget: warnings.append(f"room {rid} exit {d} missing reverse exit {rev}")
                    elif str(rtarget) != str(rid): errors.append(f"room {rid} exit {d} reverse {rev} points to wrong room {rtarget}")
            for fid, feat in (room.get("features") or {}).items():
                if not feat.get("name"): errors.append(f"feature {fid} missing name")
        try:
            from engine.schedules import ScheduleService
            validator = ScheduleService(db_path=":memory:", world_id=world_id)
            for sid, schedule in drafts.get("schedules", {}).items():
                schedule_data = dict(schedule or {})
                schedule_data.setdefault("id", str(sid))
                for err in validator.validate_schedule(schedule_data):
                    errors.append(f"schedule {sid}: {err}")
        except Exception as exc:
            warnings.append(f"schedule validation unavailable: {exc}")

        for iid, item in drafts["items"].items():
            if not item.get("name"): errors.append(f"item {iid} missing name")
            for slot in item.get("wear_slots", []) if isinstance(item.get("wear_slots", []), list) else []:
                if normalize_equipment_slot(slot) not in VALID_WEAR_SLOTS: errors.append(f"item {iid} invalid wear slot {slot}")
            if isinstance(item.get("plugin_data"), str):
                try: json.loads(item["plugin_data"])
                except json.JSONDecodeError: errors.append(f"item {iid} invalid plugin_data JSON")
        for eid, ent in drafts["entities"].items():
            if not ent.get("name"): errors.append(f"entity {eid} missing name")
            if ent.get("entity_type") and ent.get("entity_type") not in VALID_ENTITY_TYPES: errors.append(f"entity {eid} invalid entity_type {ent.get('entity_type')}")
        for pid, pl in drafts.get("item_placements", {}).items():
            if not safe_re.fullmatch(str(pid)): errors.append(f"item placement {pid} has unsafe id")
            if pl.get("item_template_id") not in drafts["items"] and pl.get("item_template_id") not in live_items: errors.append(f"item placement {pid} references missing item template {pl.get('item_template_id')}")
            if pl.get("room_id") not in all_rooms: errors.append(f"item placement {pid} references missing room {pl.get('room_id')}")
            try:
                if int(pl.get("quantity") or 0) <= 0: errors.append(f"item placement {pid} quantity must be positive")
            except Exception: errors.append(f"item placement {pid} quantity must be numeric")
            if pl.get("seed_policy", "once") not in {"once", "ensure_initial", "disabled"}: errors.append(f"item placement {pid} invalid seed_policy {pl.get('seed_policy')}")
        for sid, sp in drafts["spawns"].items():
            if sp.get("entity_template_id") not in drafts["entities"]: errors.append(f"spawn {sid} references missing entity template {sp.get('entity_template_id')}")
            if sp.get("room_id") and sp.get("room_id") not in all_rooms: errors.append(f"spawn {sid} references missing room {sp.get('room_id')}")
        # Formula/modifier diagnostics collections are accepted now and validated conservatively.
        from engine.formulas import FormulaDefinition, FormulaRegistry, Modifier, ModifierRegistry
        freg = FormulaRegistry()
        for fid, raw in drafts.get("formulas", {}).items():
            if not isinstance(raw, dict): errors.append(f"formula {fid} must be an object"); continue
            try: freg.register(FormulaDefinition(id=str(raw.get("id") or fid), display_name=str(raw.get("display_name") or ""), description=str(raw.get("description") or ""), version=str(raw.get("version") or "1.0.0"), dependencies=list(raw.get("dependencies") or []), inputs=list(raw.get("inputs") or []), outputs=list(raw.get("outputs") or []), validation=dict(raw.get("validation") or {}), plugin_owner=raw.get("plugin_owner"), builder_owner=raw.get("builder_owner"), world_overrides=dict(raw.get("world_overrides") or {}), plugin_data=dict(raw.get("plugin_data") or {})))
            except ValueError as exc: errors.append(str(exc))
        fv = freg.validate(); errors.extend(fv.errors); warnings.extend(fv.warnings)
        mreg = ModifierRegistry()
        for mid, raw in drafts.get("modifier_types", {}).items():
            if not isinstance(raw, dict): warnings.append(f"unknown modifier type {mid} must be an object"); continue
            op = str(raw.get("operation") or raw.get("id") or mid)
            if op not in mreg.modifier_types: warnings.append(f"unknown modifier type {mid}")

        # Phase 11C1 gathering foundation validation is delegated to the canonical service.
        try:
            from engine.gathering import GatheringService
            gs = GatheringService(Path(":memory:"), self.worlds_dir / world_id)
            gs.records.update({k: {str((v or {}).get("id") or dk): v for dk, v in (drafts.get(k, {}) or {}).items() if isinstance(v, dict)} for k in getattr(__import__("engine.gathering", fromlist=["GATHERING_COLLECTIONS"]), "GATHERING_COLLECTIONS")})
            gv = gs.validate_content(); errors.extend(gv.get("errors", [])); warnings.extend(gv.get("warnings", []))
        except Exception as exc:
            warnings.append(f"gathering validation unavailable: {exc}")
        current = str(getattr(actor, "edit_room_id", "") or getattr(actor, "last_edited_target", ""))
        if current and current not in all_rooms: errors.append(f"builder current target missing: {current}")
        if current: info.append(f"builder current target: {current}")
        for msg in errors: self.publish("builder_validation_error", actor, world_id, "validation", msg, command="builder validate")
        for msg in warnings: self.publish("builder_validation_warning", actor, world_id, "validation", msg, command="builder validate")
        self.publish("builder_validation_run", actor, world_id, "builder", "validate", command="builder validate")
        lines = ["Builder validation passed." if not errors else "Builder validation failed.", "", "Errors"]
        lines += [f"- {e}" for e in errors] or ["- none"]
        lines += ["", "Warnings"] + ([f"- {w}" for w in warnings] or ["- none"])
        lines += ["", "Info"] + ([f"- {i}" for i in info] or ["- none"])
        return BuilderResult(not errors, "\n".join(lines), {"errors": errors, "warnings": warnings, "info": info})

    def export(self, actor: Any) -> BuilderResult:
        world_id=self.world_id(actor); root=self.ensure(world_id); stamp=self.stamp(); out=root/"exports"/f"builder_export_{stamp}.json"
        drafts = self.load(world_id); self.normalize_drafts(world_id, drafts, actor); self.save_drafts(world_id, drafts)
        out.write_text(json.dumps(drafts, indent=2, sort_keys=True)+"\n", encoding="utf-8")
        self.audit(actor, world_id, "builder save", "export", out.name, None, {"path": str(out)})
        self.publish("builder_save_requested", actor, world_id, "export", out.name, command="builder save")
        return BuilderResult(True, f"Builder drafts exported safely to {out}.")

    def snapshot(self, actor: Any) -> BuilderResult:
        world_id=self.world_id(actor); root=self.ensure(world_id); stamp=self.stamp(); dest=root/"snapshots"/stamp; dest.mkdir(parents=True, exist_ok=True)
        for filename in DRAFT_FILES.values(): shutil.copy2(root/filename, dest/filename)
        self.audit(actor, world_id, "builder snapshot", "snapshot", stamp, None, {"path": str(dest)})
        self.publish("builder_snapshot_created", actor, world_id, "snapshot", stamp, command="builder snapshot")
        return BuilderResult(True, f"Builder snapshot created: {dest}.")

    def history(self, actor: Any, limit: int = 10) -> BuilderResult:
        root=self.ensure(self.world_id(actor)); rows=[]
        for p in sorted((root/"audit").glob("*.jsonl")):
            rows.extend(p.read_text(encoding="utf-8").splitlines())
        return BuilderResult(True, "Recent builder history:\n" + "\n".join(rows[-limit:]) if rows else "No builder history yet.")

    def audit(self, actor: Any, world_id: str, action: str, target_type: str, target_id: str, before: Any, after: Any, reason: str = "") -> None:
        root=self.ensure(world_id); rec={"timestamp": self.stamp(), "account_id": str(getattr(actor,"account_id", "")), "character_id": str(getattr(actor,"id", "")), "world_id": world_id, "action": action, "target_type": target_type, "target_id": target_id, "before": before, "after": after, "reason": reason}
        line=json.dumps(rec, sort_keys=True)
        for sub in ("audit", "history"):
            with (root/sub/f"{datetime.now(timezone.utc).date().isoformat()}.jsonl").open("a", encoding="utf-8") as fh: fh.write(line+"\n")

    def publish(self, name: str, actor: Any, world_id: str, target_type: str, target_id: str, command: str = "") -> None:
        if self.event_bus:
            payload={"account_id": str(getattr(actor,"account_id", "")), "character_id": str(getattr(actor,"id", "")), "world_id": world_id, "target_type": target_type, "target_id": target_id, "command": command, "timestamp": self.stamp()}
            self.event_bus.publish(name, payload, source_system="builder", account_id=payload["account_id"], character_id=payload["character_id"], world_id=world_id, command=command)

    def _looks_like_id(self, text: str) -> bool:
        return bool(re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)+", str(text or "")))

    def _read(self, path: Path, default: Any) -> Any:
        try: return json.loads(path.read_text(encoding="utf-8")) if path.exists() else deepcopy(default)
        except json.JSONDecodeError: return deepcopy(default)

    def stamp(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")


SEED_BODY_NATURAL_WEAPON_SUGGESTIONS = {
    "wolf": [{"family":"bite","verb":"bites","noun":"fangs","weight":70,"damage_type":"piercing","damage_dice":"1d6"},{"family":"claw","verb":"rakes","noun":"claws","weight":30,"damage_type":"slashing","damage_dice":"1d4"}],
    "bear": [{"family":"claw","verb":"claws","noun":"claws","weight":50,"damage_type":"slashing","damage_dice":"1d8"},{"family":"maul","verb":"mauls","noun":"paws","weight":25,"damage_type":"bludgeoning","damage_dice":"2d6"},{"family":"bite","verb":"bites","noun":"teeth","weight":25,"damage_type":"piercing","damage_dice":"1d8"}],
    "spider": [{"family":"bite","verb":"bites","noun":"mandibles","weight":70,"damage_type":"piercing","damage_dice":"1d4"}],
    "dragon": [{"family":"bite","verb":"bites","noun":"jaws","weight":35,"damage_type":"piercing","damage_dice":"2d8"},{"family":"claw","verb":"slashes","noun":"talons","weight":35,"damage_type":"slashing","damage_dice":"2d6"},{"family":"breath","verb":"breathes","noun":"breath","weight":30,"damage_type":"elemental","damage_dice":"3d6"}],
    "snake": [{"family":"bite","verb":"strikes","noun":"fangs","weight":100,"damage_type":"piercing","damage_dice":"1d6"}],
    "humanoid": [{"family":"punch","verb":"punches","noun":"fist","weight":100,"damage_type":"bludgeoning","damage_dice":"1d3"}],
    "elemental": [{"family":"slam","verb":"slams","noun":"body","weight":100,"damage_type":"elemental","damage_dice":"1d8"}],
    "construct": [{"family":"slam","verb":"slams","noun":"frame","weight":100,"damage_type":"bludgeoning","damage_dice":"1d8"}],
}


SEED_ATTACK_FAMILIES = ("fist", "sting", "whip", "slash", "bite", "bludgeon", "crush", "pound", "claw", "maul", "thrash", "pierce", "blast", "punch", "stab", "gore", "kick", "tail", "breath", "slam")

def _canonical_weapon(raw: dict[str, Any], fallback_id: str = "natural_weapon") -> dict[str, Any]:
    family = str(raw.get("mechanical_family") or raw.get("family") or raw.get("attack_type") or fallback_id).lower()
    noun_plural = str(raw.get("noun_plural") or raw.get("noun") or raw.get("name") or family)
    verb_third = str(raw.get("verb_third_person") or raw.get("verb") or (family + "s"))
    wid = str(raw.get("id") or f"{fallback_id}_{family}").lower().replace(" ", "_")
    return {
        "id": wid, "mechanical_family": family, "name": str(raw.get("name") or noun_plural),
        "noun_singular": str(raw.get("noun_singular") or noun_plural.rstrip("s") or noun_plural),
        "noun_plural": noun_plural, "verb_base": str(raw.get("verb_base") or family), "verb_third_person": verb_third,
        "attacker_template": str(raw.get("attacker_template") or "You {verb_base} {victim} with your {noun_plural}."),
        "victim_template": str(raw.get("victim_template") or "{attacker} {verb_third_person} you with {noun_plural}."),
        "observer_template": str(raw.get("observer_template") or "{attacker} {verb_third_person} {victim} with {noun_plural}."),
        "damage_type": str(raw.get("damage_type") or "physical"), "damage_dice": str(raw.get("damage_dice") or raw.get("dice") or "1d3"),
        "minimum_damage": int(raw.get("minimum_damage") or raw.get("min_damage") or 1),
        "maximum_damage": int(raw.get("maximum_damage") or raw.get("max_damage") or raw.get("base_damage") or 3),
        "accuracy_modifier": int(raw.get("accuracy_modifier") or 0), "critical_modifier": int(raw.get("critical_modifier") or 0),
        "selection_weight": int(raw.get("selection_weight") or raw.get("weight") or 100), "cooldown_pulses": int(raw.get("cooldown_pulses") or 0),
        "required_body_capability": str(raw.get("required_body_capability") or raw.get("capability") or family),
        "enabled": bool(raw.get("enabled", True)), "metadata": dict(raw.get("metadata") or {}),
    }

def _canonical_keywords(values: Any, fallback: str = "") -> list[str]:
    raw = values if isinstance(values, list) else str(values or "").replace(",", " ").split()
    out: list[str] = []
    for value in raw:
        keyword = re.sub(r"\s+", " ", str(value or "").strip().lower())
        if keyword and keyword not in out:
            out.append(keyword)
    if not out and fallback:
        out = [x for x in re.findall(r"[a-z0-9_']+", fallback.lower()) if x]
    return out

def _canonical_mobile_entry(raw: dict[str, Any], prefix: str, index: int, object_id: str) -> dict[str, Any]:
    seed = str(raw.get("id") or raw.get("entry_id") or raw.get("item_template_id") or raw.get("object_id") or f"{object_id}_{prefix}_{index}")
    entry = dict(raw)
    entry["id"] = re.sub(r"[^a-z0-9_:-]+", "_", seed.lower()).strip("_") or f"{object_id}_{prefix}_{index}"
    if entry.get("object_id") and not entry.get("item_template_id"):
        entry["item_template_id"] = entry.pop("object_id")
    if "chance" in entry:
        try: entry["chance"] = int(entry.get("chance"))
        except Exception: entry["chance"] = 100
    else:
        entry["chance"] = 100
    if "quantity" in entry:
        try: entry["quantity"] = int(entry.get("quantity"))
        except Exception: entry["quantity"] = 1
    entry.setdefault("enabled", True)
    entry.setdefault("order", index)
    return entry


class MobileTemplate:
    """Canonical mobile adapter shared by Builder preview, testspawn and generation activation."""
    def __init__(self, record: dict[str, Any], source: str = "draft") -> None:
        self.source = source
        self.record = self.from_legacy(record).to_canonical_dict() if source == "legacy-proxy" else deepcopy(record or {})

    @classmethod
    def from_draft(cls, record: dict[str, Any]) -> "MobileTemplate":
        return cls(record, "draft")

    @classmethod
    def from_generation(cls, record: dict[str, Any]) -> "MobileTemplate":
        return cls(record, "generation")

    @classmethod
    def from_legacy(cls, record: dict[str, Any]) -> "MobileTemplate":
        rec = deepcopy(record or {})
        raw = rec.pop("natural_attacks", None)
        if raw is not None:
            cp = dict(rec.get("combat_profile") or {})
            cp["natural_weapons"] = [_canonical_weapon(x, str(rec.get("id") or "mobile")) for x in raw if isinstance(x, dict)]
            rec["combat_profile"] = cp
        raw_top = rec.pop("natural_weapons", None)
        if raw_top is not None:
            cp = dict(rec.get("combat_profile") or {})
            cp["natural_weapons"] = [_canonical_weapon(x, str(rec.get("id") or "mobile")) for x in raw_top if isinstance(x, dict)]
            rec["combat_profile"] = cp
        cp = dict(rec.get("combat_profile") or {})
        cp["natural_weapons"] = [_canonical_weapon(x, str(rec.get("id") or "mobile")) for x in (cp.get("natural_weapons") or []) if isinstance(x, dict)]
        rec["combat_profile"] = cp
        return cls(rec, "legacy")

    def validate(self) -> list[dict[str, Any]]:
        rec = self.to_canonical_dict(); oid = str(rec.get("id") or "")
        issues: list[dict[str, Any]] = []
        def issue(sev, code, path, msg, hint=""):
            issues.append({"severity":sev,"code":code,"collection":"entities","object_id":oid,"field_path":path,"message":msg,"fix_hint":hint,"reference_target":"","blocking":sev=="error"})
        for fld in ("id","name"):
            if not rec.get(fld): issue("error","required_field",fld,f"{fld} is required.",f"Set {fld}.")
        kws = _canonical_keywords(rec.get("keywords"), "")
        if not kws: issue("error","empty_keywords","keywords","At least one keyword is required.","Add target-resolution keywords.")
        if not (rec.get("short_description") or rec.get("name")): issue("error","missing_short_description","short_description","Short description is required.","Set a short description.")
        if not (rec.get("room_description") or rec.get("description") or rec.get("long_description")): issue("error","missing_room_description","room_description","Long room description is required.","Set the room-visible description.")
        if not (rec.get("look_description") or rec.get("examine_description")): issue("warning","missing_detail_description","look_description","Detailed examine description is empty.","Add look/examine text.")
        try:
            level = int(rec.get("level", 1) or 1)
            if not 1 <= level <= 100: issue("error","level_range","level","Level must be 1-100.")
        except Exception: issue("error","level_number","level","Level must be a whole number.")
        for pos_field in ("default_position", "spawn_position"):
            pos = str(rec.get(pos_field) or "standing")
            if pos not in MEDIT_POSITIONS: issue("warning","unknown_position",pos_field,f"{pos_field} '{pos}' is not a canonical named position.")
            if pos == "dead": issue("warning","spawn_dead",pos_field,"Templates should not spawn dead unless intentionally staged.")
        if "natural_attacks" in rec: issue("error","deprecated_field","natural_attacks","natural_attacks is deprecated; use combat_profile.natural_weapons.","Save through BuilderService migration.")
        attrs = rec.get("attributes") or {}
        for fld in ("strength","dexterity","constitution","intelligence","wisdom","charisma"):
            if fld in attrs and not (1 <= int(attrs.get(fld) or 0) <= 100): issue("error","attribute_range",f"attributes.{fld}","Attribute must be 1-100.")
        resources = rec.get("resources") or {}
        if not (resources.get("health") or rec.get("max_health")): issue("warning","missing_health","resources.health","A health resource is required before publish/runtime activation.","Add health with a positive maximum.")
        for rname, rvalue in resources.items() if isinstance(resources, dict) else []:
            data = rvalue if isinstance(rvalue, dict) else {"maximum": rvalue, "starting": rvalue}
            try:
                maximum = int(data.get("maximum") if data.get("maximum") is not None else data.get("max"))
                starting = int(data.get("starting") if data.get("starting") is not None else maximum)
                if maximum < 0: issue("error","resource_range",f"resources.{rname}.maximum","Resource maximum cannot be negative.")
                if starting > maximum: issue("error","resource_start",f"resources.{rname}.starting","Starting resource cannot exceed maximum.")
            except Exception: issue("error","resource_number",f"resources.{rname}","Resource maximum/starting values must be whole numbers.")
        weapons=(rec.get("combat_profile") or {}).get("natural_weapons") or []
        if not weapons: issue("warning","no_natural_weapons","combat_profile.natural_weapons","Mob has no natural weapons.","Add an authored natural weapon.")
        for i,w in enumerate(weapons):
            for fld in ("id","mechanical_family","noun_plural","verb_third_person","damage_type","damage_dice","selection_weight"):
                if not w.get(fld): issue("error","natural_weapon_required",f"combat_profile.natural_weapons[{i}].{fld}",f"Natural weapon {fld} is required.")
            if int(w.get("selection_weight") or 0) <= 0: issue("error","natural_weapon_weight",f"combat_profile.natural_weapons[{i}].selection_weight","Weight must be positive.")
        flags = set(rec.get("mobile_flags") or rec.get("flags") or [])
        affects = set(rec.get("affect_flags") or [])
        if "wander" in flags and "no_wander" in flags: issue("warning","contradictory_flags","mobile_flags","wander and no_wander are both authored.")
        if "pet" not in flags and (rec.get("pet_price") or (rec.get("economy") or {}).get("purchase_price")): issue("warning","pet_price_without_pet","pet_price","Pet price is set but pet flag is not enabled.")
        if "haste" in affects and "slow" in affects: issue("warning","contradictory_affects","affect_flags","haste and slow are both permanent affects.")
        recs = MobileRecommendationService().recommend(level=rec.get("level", 1), archetype=str(rec.get("archetype") or "standard creature"))
        vals = recs["values"]; hp = ((rec.get("resources") or {}).get("health") or {}).get("maximum")
        try:
            hp_int = int(hp)
            exp_hp = int(vals["resources"]["health"]["maximum"]);
            if hp_int < exp_hp * 0.5: issue("warning","balance_low_health","resources.health.maximum",f"Health {hp_int} is below expected range {exp_hp//2}-{exp_hp*2} from {MobileRecommendationService.version}; publish allowed.")
            if hp_int > exp_hp * 2: issue("warning","balance_high_health","resources.health.maximum",f"Health {hp_int} is above expected range {exp_hp//2}-{exp_hp*2} from {MobileRecommendationService.version}; publish allowed.")
        except Exception: pass
        cp = rec.get("combat_profile") or {}; xp = cp.get("experience_reward") or rec.get("experience_reward")
        try:
            xp_int=int(xp); exp_xp=int(vals["combat_profile"]["experience_reward"])
            if xp_int > exp_xp*3: issue("warning","balance_excessive_xp","combat_profile.experience_reward",f"XP {xp_int} exceeds expected range 0-{exp_xp*3} from {MobileRecommendationService.version}; publish allowed.")
            if xp_int and xp_int < max(1, exp_xp//4): issue("warning","balance_insufficient_xp","combat_profile.experience_reward",f"XP {xp_int} is below expected range {max(1, exp_xp//4)}-{exp_xp*3} from {MobileRecommendationService.version}; publish allowed.")
        except Exception: pass
        if (rec.get("archetype") == "caster" or rec.get("archetype") == "healer/support") and not (((rec.get("resources") or {}).get("mana") or {}).get("maximum")): issue("warning","caster_without_mana","resources.mana.maximum","Caster/support archetype has no mana or equivalent resource; publish allowed.")
        abilities_catalog = set((rec.get("_ability_catalog") or []))
        def overlap(a, b): return sorted(set(a or []) & set(b or []))
        for section, id_field in (("combat_abilities", "ability_id"), ("event_reactions", "id"), ("script_attachments", "script_id")):
            entries = rec.get(section) or []; seen_ids=set(); seen_priorities=set()
            for i, ent in enumerate(entries):
                eid = str(ent.get("id") or ent.get(id_field) or "")
                if not eid: issue("error", "missing_nested_id", f"{section}[{i}].id", "Nested entry stable ID is required.", "Copy/recreate the entry to generate a stable ID.")
                if eid in seen_ids: issue("error", "duplicate_nested_id", f"{section}[{i}].id", f"Duplicate nested ID {eid}.", "Rename or copy the entry so each nested ID is unique.")
                seen_ids.add(eid)
                pr = ent.get("priority")
                if pr in seen_priorities: issue("warning", "duplicate_priority", f"{section}[{i}].priority", f"Priority {pr} is duplicated; deterministic list order will break ties.", "Use unique priorities when decision order matters.")
                seen_priorities.add(pr)
                ch = _chance_int(ent.get("chance", 100));
                if ch < 0 or ch > 100: issue("error", "invalid_chance", f"{section}[{i}].chance", "Chance must be 0-100.", "Set chance to a whole percentage.")
                for fld in ("cooldown", "initial_cooldown", "uses_per_combat", "uses_per_life", "uses_per_reset"):
                    if ent.get(fld) not in (None, ""):
                        try:
                            if int(ent.get(fld)) < 0: issue("error", "negative_limit", f"{section}[{i}].{fld}", f"{fld} cannot be negative.", "Use zero or a positive whole number.")
                        except Exception: issue("error", "invalid_number", f"{section}[{i}].{fld}", f"{fld} must be a whole number.", "Use a numeric value.")
                if overlap(ent.get("required_status"), ent.get("forbidden_status")): issue("error", "contradictory_status", f"{section}[{i}].required_status", "Required and forbidden statuses overlap.", "Remove the status from one side.")
                if overlap(ent.get("required_tags"), ent.get("forbidden_tags")): issue("error", "contradictory_tags", f"{section}[{i}].required_tags", "Required and forbidden tags overlap.", "Remove the tag from one side.")
        for i, ent in enumerate(rec.get("combat_abilities") or []):
            if ent.get("ability_type") not in MEDIT_ADVANCED_ABILITY_TYPES: issue("error", "unknown_ability_type", f"combat_abilities[{i}].ability_type", "Unknown ability type.", "Use ability, skill, spell, or special.")
            if not ent.get("ability_id"): issue("error", "missing_ability", f"combat_abilities[{i}].ability_id", "Combat ability is missing an ability reference.", "Choose an ability/skill/spell ID.")
            if ent.get("target_selector") not in MEDIT_ADVANCED_TARGETS: issue("error", "invalid_target", f"combat_abilities[{i}].target_selector", "Invalid target selector.", "Choose a canonical MEDIT target selector.")
            if ent.get("trigger") not in MEDIT_ADVANCED_ABILITY_TRIGGERS: issue("error", "invalid_trigger", f"combat_abilities[{i}].trigger", "Invalid ability trigger.", "Choose a canonical combat trigger.")
            if ent.get("trigger") not in MEDIT_RUNTIME_SUPPORTED_ABILITY_TRIGGERS: issue("warning", "ability_runtime_deferred", f"combat_abilities[{i}].trigger", "Ability editor data is canonical, but this trigger is runtime-deferred.", "Publish only if deferred runtime behavior is acceptable.")
            if abilities_catalog and ent.get("ability_id") not in abilities_catalog: issue("error", "missing_ability_reference", f"combat_abilities[{i}].ability_id", "Referenced ability is not present in the ability registry.", "Create or select an existing ability.")
            if ent.get("minimum_round") and ent.get("maximum_round") and int(ent.get("minimum_round")) > int(ent.get("maximum_round")): issue("error", "round_range", f"combat_abilities[{i}].minimum_round", "Minimum round cannot be after maximum round.", "Adjust timing bounds.")
        for i, ent in enumerate(rec.get("event_reactions") or []):
            if ent.get("event_type") not in MEDIT_ADVANCED_EVENT_TYPES: issue("error", "unknown_event", f"event_reactions[{i}].event_type", "Unknown EventBus event mapping.", "Choose a canonical event type.")
            if ent.get("action_type") not in MEDIT_ADVANCED_ACTION_TYPES: issue("error", "unsupported_action", f"event_reactions[{i}].action_type", "Unsupported reaction action.", "Choose a canonical action type.")
            if ent.get("target_selector") not in MEDIT_ADVANCED_TARGETS: issue("error", "invalid_target", f"event_reactions[{i}].target_selector", "Invalid target selector.", "Choose a canonical target selector.")
            if ent.get("event_type") not in MEDIT_RUNTIME_SUPPORTED_REACTION_EVENTS or ent.get("action_type") not in MEDIT_RUNTIME_SUPPORTED_REACTION_ACTIONS: issue("warning", "reaction_runtime_deferred", f"event_reactions[{i}].runtime", "Reaction is editor-complete but runtime-deferred for this event/action mapping.", "Use supported mappings or accept a runtime limitation.")
            if ent.get("action_type") == "publish_event" and (ent.get("action_data") or {}).get("event_type") == ent.get("event_type"): issue("warning", "reaction_loop_risk", f"event_reactions[{i}].action_data", "Reaction may publish the same event and loop; runtime depth protection will stop recursion.", "Add cooldown/conditions or publish a different event.")
        for i, ent in enumerate(rec.get("script_attachments") or []):
            if not ent.get("script_id"): issue("error", "missing_script", f"script_attachments[{i}].script_id", "Script attachment is missing a script reference.", "Choose an approved script/trigger ID.")
            if ent.get("trigger") not in MEDIT_ADVANCED_SCRIPT_TRIGGERS: issue("error", "unsupported_script_trigger", f"script_attachments[{i}].trigger", "Unsupported script trigger binding.", "Choose a canonical script trigger.")
            issue("warning", "script_runtime_host_deferred", f"script_attachments[{i}].runtime", "Script attachment management is complete, but source execution depends on the canonical script host.", "Validate the script host before activation.")
        return issues

    def to_canonical_dict(self) -> dict[str, Any]:
        rec = deepcopy(self.record)
        oid = str(rec.get("id") or "mobile")
        rec["id"] = oid
        if rec.get("aliases") and not rec.get("keywords"):
            rec["keywords"] = rec.get("aliases")
        rec["keywords"] = _canonical_keywords(rec.get("keywords"), str(rec.get("name") or oid))
        rec["aliases"] = list(dict.fromkeys([str(x).strip() for x in (rec.get("aliases") or []) if str(x).strip()]))
        if rec.get("gender") and not rec.get("sex"):
            rec["sex"] = rec.get("gender")
        rec.setdefault("sex", "neutral")
        rec.setdefault("enabled", True)
        rec.setdefault("default_position", rec.get("spawn_position") or "standing")
        rec.setdefault("spawn_position", rec.get("default_position") or "standing")
        resources = dict(rec.get("resources") or {})
        legacy_health = rec.get("max_health") if rec.get("max_health") is not None else (rec.get("stats") or {}).get("max_health") if isinstance(rec.get("stats"), dict) else None
        if legacy_health is not None and "health" not in resources:
            resources["health"] = {"maximum": legacy_health, "starting": legacy_health, "enabled": True}
        if resources and all(not isinstance(v, dict) for v in resources.values()):
            resources = {str(k): {"maximum": v, "starting": v, "enabled": True} for k, v in resources.items()}
        rec["resources"] = resources
        rec["attributes"] = dict(rec.get("attributes") or {})
        rec["mobile_flags"] = list(dict.fromkeys([str(x).lower() for x in (rec.get("mobile_flags") or rec.get("flags") or [])]))
        rec["affect_flags"] = list(dict.fromkeys([str(x).lower() for x in (rec.get("affect_flags") or rec.get("permanent_affects") or [])]))
        rec["starting_inventory"] = [_canonical_mobile_entry(x, "inventory", i + 1, oid) for i, x in enumerate(rec.get("starting_inventory") or rec.get("inventory") or []) if isinstance(x, dict)]
        loot = dict(rec.get("loot") or {})
        entries = loot.get("entries") if isinstance(loot.get("entries"), list) else rec.get("loot_entries") or []
        loot["entries"] = [_canonical_mobile_entry(x, "loot", i + 1, oid) for i, x in enumerate(entries) if isinstance(x, dict)]
        loot.setdefault("profile_id", rec.get("loot_table_id") or rec.get("loot_profile_id"))
        loot.setdefault("corpse_enabled", True)
        rec["loot"] = loot
        rec.pop("natural_attacks", None); rec.pop("natural_weapons", None)
        cp = dict(rec.get("combat_profile") or {})
        cp["natural_weapons"] = [_canonical_weapon(x, str(rec.get("id") or "mobile")) for x in cp.get("natural_weapons") or []]
        if rec.get("attack_type") and not cp.get("attack_type"):
            cp["attack_type"] = rec.get("attack_type")
        rec["combat_profile"] = cp
        rec = _normalize_advanced_mobile_sections(rec, str(rec.get("id") or "mobile"))
        return rec

    def to_runtime_projection(self) -> dict[str, Any]:
        rec = self.to_canonical_dict()
        resources = rec.get("resources") or {}
        def rmax(name, legacy=None):
            val = resources.get(name)
            return (val or {}).get("maximum") if isinstance(val, dict) else (val if val is not None else rec.get(legacy or ""))
        abilities = deepcopy(rec.get("combat_abilities") or [])
        reactions = deepcopy(rec.get("event_reactions") or [])
        scripts = deepcopy(rec.get("script_attachments") or [])
        for ability in abilities:
            ability["runtime_supported"] = ability.get("enabled", True) and ability.get("trigger") in MEDIT_RUNTIME_SUPPORTED_ABILITY_TRIGGERS
            ability["runtime_decision_reason"] = "eligible when target/cooldown/chance checks pass" if ability["runtime_supported"] else "trigger has no runtime combat hook"
        for reaction in reactions:
            reaction["runtime_supported"] = reaction.get("enabled", True) and reaction.get("event_type") in MEDIT_RUNTIME_SUPPORTED_REACTION_EVENTS and reaction.get("action_type") in MEDIT_RUNTIME_SUPPORTED_REACTION_ACTIONS
            reaction["runtime_loop_guard"] = {"max_depth": 8, "deterministic_order": "priority,id", "same_event_republish_blocked": reaction.get("action_type") == "publish_event" and (reaction.get("action_data") or {}).get("event_type") == reaction.get("event_type")}
        for script in scripts:
            script["runtime_supported"] = False
            script["runtime_decision_reason"] = "canonical script host required; preview never executes scripts"
        return {"template_id": rec.get("id"), "name": rec.get("name"), "level": rec.get("level",1), "keywords": deepcopy(rec.get("keywords") or []), "description": rec.get("description") or rec.get("look_description") or "", "default_position": rec.get("default_position"), "spawn_position": rec.get("spawn_position"), "mobile_flags": deepcopy(rec.get("mobile_flags") or []), "permanent_affects": deepcopy(rec.get("affect_flags") or []), "body_profile_id": rec.get("body_profile_id"), "combat_profile": deepcopy(rec.get("combat_profile") or {}), "attributes": deepcopy(rec.get("attributes") or {}), "resources": {"max_health": rmax("health","max_health"), "max_mana": rmax("mana","max_mana"), "max_move": rmax("movement","max_move") or rmax("stamina")}, "equipment_loadout": deepcopy(rec.get("equipment_loadout") or {}), "starting_inventory": deepcopy(rec.get("starting_inventory") or []), "loot": deepcopy(rec.get("loot") or {}), "combat_abilities": abilities, "event_reactions": reactions, "script_attachments": scripts, "runtime_support": {"combat_abilities": "supported triggers execute through runtime combat hooks; unsupported triggers warn", "event_reactions": "supported event/action mappings execute through EventBus reaction dispatcher with depth guard", "script_attachments": "stored, validated, dependency-tracked; execution requires canonical script host"}}

    def diff(self, other: dict[str, Any]) -> dict[str, Any]:
        before = MobileTemplate.from_legacy(other or {}).to_canonical_dict(); after = self.to_canonical_dict()
        return {k: {"before": before.get(k), "after": after.get(k)} for k in sorted(set(before)|set(after)) if before.get(k) != after.get(k)}

@dataclass
class BuilderEditSession:
    session_id: str; builder_account_id: str; builder_character_id: str; world_id: str; editor_type: str; collection: str; object_id: str; lock_key: str
    mode: str = "main_menu"; section: str = ""; subsection: str = ""; pending_field: str = ""; pending_value_type: str = ""; pending_choices: list[str] = field(default_factory=list)
    draft_revision: int = 0; working_revision: int = 0; started_at: str = ""; last_activity_at: str = ""; dirty: bool = False; saved: bool = True; validation_state: str = "unknown"; return_stack: list[str] = field(default_factory=list)
    original_record: dict[str, Any] = field(default_factory=dict); working_record: dict[str, Any] = field(default_factory=dict); savepoint: dict[str, Any] = field(default_factory=dict); dirty_fields: list[str] = field(default_factory=list); quit_pending: bool = False
    undo_stack: list[dict[str, Any]] = field(default_factory=list); redo_stack: list[dict[str, Any]] = field(default_factory=list)
    menu_stack: list[str] = field(default_factory=list); active_field: str = ""; field_input_type: str = ""; pending_value: Any = None; confirmation_type: str = ""; multiline_lines: list[str] = field(default_factory=list); reference_filter: str = ""; reference_page: int = 1
    active_direction: str = ""
    active_extra_index: int = 0

@dataclass(frozen=True)
class OlcFieldDescriptor:
    key: str
    label: str
    path: tuple[str, ...]
    input_type: str = "string"
    help: str = ""
    minimum: int | float | None = None
    maximum: int | float | None = None
    choices: tuple[str, ...] = ()
    flags: tuple[str, ...] = ()
    reference_collection: str = ""
    required: bool = False
    multiple: bool = False
    read_only: bool = False
    mutation: str = "Set {label} from {old} to {new}"


class BuilderSessionManager:
    def __init__(self, service: 'BuilderService') -> None:
        self.service = service; self.active: dict[str, BuilderEditSession] = {}
    def actor_key(self, actor: Any) -> str: return str(getattr(actor, 'id', '') or getattr(actor, 'name', 'builder'))
    def start(self, actor: Any, editor: str, collection: str, object_id: str) -> BuilderResult:
        existing = self.active.get(self.actor_key(actor))
        if existing:
            if existing.editor_type == editor and existing.collection == collection and existing.object_id == object_id:
                return BuilderResult(True, self.service.render_session(existing))
            return BuilderResult(False, f"You are already editing {existing.editor_type.upper()} {existing.object_id}. Save, discard, or quit that editor before opening another.")
        lock = self.service.acquire_lock(actor, collection, object_id)
        if not lock.ok: return lock
        world_id = self.service.workspace.world_id(actor); now = self.service.workspace.stamp(); rec = self.service._record(world_id, collection, object_id)
        if rec is None:
            rec = self.service.resolve_collection_records(actor, collection).get(object_id) or {"id": object_id}
        sess = BuilderEditSession(f"{self.actor_key(actor)}-{now}", str(getattr(actor,'account_id','')), self.actor_key(actor), world_id, editor, collection, object_id, f"{collection}:{object_id}", draft_revision=int(rec.get('_builder_revision') or 0), started_at=now, last_activity_at=now, original_record=deepcopy(rec), working_record=deepcopy(rec), savepoint=deepcopy(rec))
        self.active[self.actor_key(actor)] = sess
        return BuilderResult(True, self.service.render_session(sess))
    def has(self, actor: Any) -> bool: return self.actor_key(actor) in self.active
    def handle(self, actor: Any, text: str) -> BuilderResult:
        sess = self.active.get(self.actor_key(actor))
        if not sess: return BuilderResult(False, 'No active editor session.')
        return self.service.handle_session_input(actor, sess, text.strip())
    def end(self, actor: Any, release: bool = True) -> None:
        sess = self.active.pop(self.actor_key(actor), None)
        if sess and release: self.service.release_lock(actor, sess.collection, sess.object_id)

@dataclass
class BuilderContentRecord:
    canonical_id: str
    legacy_vnum: int | None
    display_name: str
    type: str
    area: str
    zone: str
    builder_status: str
    validation_status: str
    content_source: str
    generation: str
    spawn_count: int = 0
    reset_count: int = 0
    script_count: int = 0
    shop_count: int = 0
    quest_count: int = 0
    record: dict[str, Any] = field(default_factory=dict)

class BuilderContentQueryService:
    """Canonical Oasis-style discovery facade for Builder list and picker commands."""
    COLLECTIONS = {"mob": "entities", "mobile": "entities", "object": "items", "item": "items", "room": "rooms", "spawn": "spawns", "reset": "resets", "area": "areas", "zone": "zones"}

    def __init__(self, service: "BuilderService") -> None:
        self.service = service

    def list(self, actor: Any, kind: str, *, scratch: dict[str, Any] | None = None) -> list[BuilderContentRecord]:
        collection = self.COLLECTIONS.get(kind, kind)
        records = self.service.resolve_collection_records(actor, collection, scratch=scratch)
        aux = {k: self.service.resolve_collection_records(actor, k) for k in ("spawns", "resets", "quest_definitions")}
        rows = [self._record(collection, oid, rec, aux) for oid, rec in records.items() if isinstance(rec, dict)]
        rows = sorted(rows, key=lambda r: (r.legacy_vnum is None, r.legacy_vnum or 999999999, r.canonical_id))
        ranges = {"rooms": (1000, 1299), "items": (1300, 1499), "entities": (1500, 1699), "spawns": (1700, 1799), "resets": (1700, 1799)}
        if collection in ranges:
            used = {int(r.legacy_vnum) for r in rows if r.legacy_vnum is not None}
            nxt = ranges[collection][0]
            for r in rows:
                if r.legacy_vnum is None:
                    while nxt in used and nxt <= ranges[collection][1]:
                        nxt += 1
                    if nxt <= ranges[collection][1]:
                        r.legacy_vnum = nxt; used.add(nxt); nxt += 1
        return rows

    def _record(self, collection: str, oid: str, rec: dict[str, Any], aux: dict[str, dict[str, dict[str, Any]]]) -> BuilderContentRecord:
        cid = str(rec.get("id") or oid)
        vnum = rec.get("vnum", rec.get("spawn_vnum"))
        try: vnum = int(vnum) if vnum not in (None, "") else None
        except Exception: vnum = None
        source = str(rec.get("_builder_reference_source") or "legacy")
        status = str(rec.get("builder_status") or ("complete" if rec.get("name") or rec.get("title") else "incomplete"))
        validation = "Valid" if (rec.get("name") or rec.get("title") or collection in {"spawns","resets"}) and (vnum is not None or collection not in {"entities","items","rooms"}) else "Incomplete"
        scripts = rec.get("script_ids") or rec.get("scripts") or []
        spawns = sum(1 for s in aux.get("spawns", {}).values() if self._links(s, cid, collection))
        resets = sum(1 for r in aux.get("resets", {}).values() if self._links(r, cid, collection))
        quests = sum(1 for q in aux.get("quest_definitions", {}).values() if cid in json.dumps(q, sort_keys=True, default=str))
        if collection == "entities":
            display = rec.get("short_description") or rec.get("short_desc") or rec.get("display_name") or rec.get("name") or cid
        elif collection == "items":
            display = rec.get("short_description") or rec.get("short_desc") or rec.get("display_name") or rec.get("name") or cid
        else:
            display = rec.get("title") or rec.get("name") or rec.get("display_name") or cid
        return BuilderContentRecord(cid, vnum, str(display), collection, str(rec.get("area_id") or rec.get("area") or ""), str(rec.get("zone_id") or rec.get("zone") or ""), status, validation, source, str(rec.get("generation") or rec.get("generation_id") or ""), spawns, resets, len(scripts) if isinstance(scripts, list) else 1, len(rec.get("shop_ids") or []), quests, rec)

    def _links(self, rec: dict[str, Any], cid: str, collection: str) -> bool:
        keys = {"entities": ("mobile_id","mob_id","entity_id","template_id"), "items": ("object_id","item_id","item_template_id"), "rooms": ("room_id","target_room_id")}.get(collection, ())
        return any(str(rec.get(k) or "") == cid for k in keys) or cid in json.dumps(rec, sort_keys=True, default=str)

    def search(self, actor: Any, kind: str, query: str) -> list[BuilderContentRecord]:
        q = str(query or "").lower().strip()
        rows = self.list(actor, kind)
        if not q:
            return rows
        if q.isdigit():
            return [r for r in rows if r.legacy_vnum == int(q) or q in r.canonical_id.lower()]
        return [r for r in rows if q in " ".join([r.canonical_id, r.display_name, r.area, r.zone, " ".join(map(str, r.record.get("keywords") or r.record.get("aliases") or []))]).lower()]

    def by_id_or_vnum(self, actor: Any, kind: str, token: str) -> list[BuilderContentRecord]:
        rows = self.list(actor, kind)
        if str(token).isdigit():
            return [r for r in rows if r.legacy_vnum == int(token)]
        return [r for r in rows if r.canonical_id == token] or self.search(actor, kind, token)


class BuilderVnumRangeService:
    """Canonical Shattered Realms range helper for Builder normalization."""
    AREA_ID = "starter_guildlands"
    WORLD_ID = "shattered_realms"
    AREA_RANGE = (1000, 1999)
    ROOM_RANGE = (1000, 1299)
    OBJECT_RANGE = (1300, 1499)
    MOBILE_RANGE = (1500, 1699)
    SPAWN_RESET_RANGE = (1700, 1799)

    def __init__(self, service: "BuilderService") -> None:
        self.service = service

    def zone_for_room_vnum(self, zones: dict[str, dict[str, Any]], vnum: int | None) -> str:
        if vnum is None:
            return ""
        for zid, z in sorted(zones.items(), key=lambda kv: (int((kv[1] or {}).get("vnum_start") or 999999), kv[0])):
            try:
                if int(z.get("vnum_start")) <= int(vnum) <= int(z.get("vnum_end")):
                    return str(zid)
            except Exception:
                continue
        return ""

    def namespace_for(self, kind: str) -> str:
        return {"rooms": "rooms", "entities": "entities", "items": "items", "spawns": "spawn_reset", "resets": "spawn_reset"}.get(kind, kind)

    def range_for(self, kind: str) -> tuple[int, int]:
        return {"rooms": self.ROOM_RANGE, "entities": self.MOBILE_RANGE, "items": self.OBJECT_RANGE, "spawns": self.SPAWN_RESET_RANGE, "resets": self.SPAWN_RESET_RANGE}.get(kind, self.AREA_RANGE)

    def validate_range(self, kind: str) -> tuple[bool, str]:
        lo, hi = self.range_for(kind)
        return (lo <= hi, f"{lo}-{hi}")

    def in_range(self, kind: str, vnum: int | None) -> bool:
        if vnum is None:
            return False
        lo, hi = self.range_for(kind)
        return lo <= int(vnum) <= hi

    def first_free(self, kind: str, used: set[int]) -> int | None:
        lo, hi = self.range_for(kind)
        for n in range(lo, hi + 1):
            if n not in used:
                used.add(n)
                return n
        return None

class BuilderService:
    """Canonical draft-first builder facade used by commands, OLC, importers, and future UI."""
    def __init__(self, workspace: BuilderWorkspace | None = None, runtime: Any | None = None) -> None:
        self.workspace = workspace or BuilderWorkspace()
        self.runtime = runtime
        self.sessions = BuilderSessionManager(self)
        self.content_query = BuilderContentQueryService(self)
        self.vnum_ranges = BuilderVnumRangeService(self)

    def attach_runtime(self, runtime: Any) -> None:
        self.runtime = runtime

    def _runtime_required(self) -> Any:
        if self.runtime is None:
            raise RuntimeError("BuilderService requires an attached MudRuntime for live runtime operations.")
        return self.runtime

    def _record(self, world_id: str, collection: str, object_id: str) -> dict[str, Any] | None:
        rec = self.workspace.load(world_id).get(collection, {}).get(object_id)
        return rec if isinstance(rec, dict) else None

    def resolve_collection_records(self, actor: Any | None, collection: str, *, include_drafts: bool = True, include_active_generation: bool = True, include_live: bool = True, scratch: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
        """Merged Builder reference resolver: scratch > drafts > active generation > live > bootstrap seeds."""
        world_id = self.workspace.world_id(actor) if actor is not None else (getattr(self.runtime, "active_world_id", "") or "shattered_realms")
        merged: dict[str, dict[str, Any]] = {}
        if include_live:
            for rec in _records(self.workspace.worlds_dir / world_id, DRAFT_FILES.get(collection, f"{collection}.json")[:-5] if collection in DRAFT_FILES else collection):
                if isinstance(rec, dict) and rec.get("id"):
                    r = deepcopy(rec); r.setdefault("id", str(rec.get("id"))); r["_builder_reference_source"] = "live"; merged[str(r["id"])] = r
            if collection == "entities":
                for rec in _records(self.workspace.worlds_dir / world_id, "npcs"):
                    if isinstance(rec, dict) and rec.get("id"):
                        r = MobileTemplate.from_generation(rec).to_canonical_dict(); r["_builder_reference_source"] = "live"; merged[str(r["id"])] = r
        if include_active_generation and self.runtime is not None:
            gen = getattr(self.runtime, "active_content_generation", None) or getattr(self, "active_content_generation", None) or {}
            for oid, rec in (gen.get(collection) or {}).items() if isinstance(gen, dict) else []:
                if isinstance(rec, dict):
                    r = deepcopy(rec); r.setdefault("id", str(oid)); r["_builder_reference_source"] = "generation"; merged[str(r["id"])] = r
        if include_drafts:
            for oid, rec in (self.workspace.load(world_id).get(collection) or {}).items():
                if isinstance(rec, dict):
                    r = deepcopy(rec); r.setdefault("id", str(oid)); r["_builder_reference_source"] = "draft"; merged[str(r["id"])] = r
        if scratch and scratch.get("id"):
            r = deepcopy(scratch); r["_builder_reference_source"] = "scratch"; merged[str(r["id"])] = r

        if collection == "body_profiles":
            seeds = {"wolf": {"id":"wolf", "capabilities":["fangs","claws"], "suggested_natural_weapon_ids":["wolf_fangs","wolf_claws"]}, "bear": {"id":"bear", "capabilities":["teeth","claws","paws"], "suggested_natural_weapon_ids":["bear_claw","bear_bite","bear_maul"]}, "humanoid": {"id":"humanoid", "capabilities":["fists"], "suggested_natural_weapon_ids":["humanoid_fist"]}}
            for oid, rec in seeds.items():
                if oid not in merged:
                    r = deepcopy(rec); r["_builder_reference_source"] = "bootstrap"; merged[oid] = r
        if collection == "natural_weapon_profiles":
            seeds = {"wolf_fangs": _canonical_weapon({"id":"wolf_fangs","family":"bite","noun":"fangs","verb":"bites","damage_type":"piercing","damage_dice":"1d6","weight":100}, "wolf"), "wolf_claws": _canonical_weapon({"id":"wolf_claws","family":"claw","noun":"claws","verb":"rakes","damage_type":"slashing","damage_dice":"1d4","weight":30}, "wolf"), "bear_claw": _canonical_weapon({"id":"bear_claw","family":"claw","noun":"claws","verb":"claws","damage_type":"slashing","damage_dice":"1d8","weight":50}, "bear"), "bear_bite": _canonical_weapon({"id":"bear_bite","family":"bite","noun":"teeth","verb":"bites","damage_type":"piercing","damage_dice":"1d8","weight":25}, "bear"), "bear_maul": _canonical_weapon({"id":"bear_maul","family":"maul","noun":"paws","verb":"mauls","damage_type":"bludgeoning","damage_dice":"2d6","weight":25}, "bear")}
            for oid, rec in seeds.items():
                if oid not in merged:
                    r = deepcopy(rec); r["_builder_reference_source"] = "bootstrap"; merged[oid] = r
        return merged

    def resolve_reference(self, actor: Any | None, collection: str, query: str, *, scratch: dict[str, Any] | None = None) -> dict[str, Any] | None:
        q = str(query or "").lower().strip()
        records = self.resolve_collection_records(actor, collection, scratch=scratch)
        if q in records:
            return records[q]
        exact = [r for oid, r in records.items() if str(r.get("name") or r.get("display_name") or oid).lower() == q]
        if len(exact) == 1:
            return exact[0]
        partial = [r for oid, r in records.items() if q and (q in oid.lower() or q in str(r.get("name") or r.get("display_name") or "").lower() or q in " ".join(map(str, r.get("keywords") or [])).lower())]
        return partial[0] if len(partial) == 1 else None

    def _body_profile_result(self, actor: Any, profile: str, scratch: dict[str, Any] | None = None) -> tuple[str, dict[str, Any] | None, list[dict[str, Any]]]:
        bp = self.resolve_reference(actor, "body_profiles", profile, scratch=scratch)
        if not bp:
            return str(profile).lower(), None, []
        prof = str(bp.get("id") or profile).lower()
        natural_profiles = self.resolve_collection_records(actor, "natural_weapon_profiles")
        weapons = []
        for wid in bp.get("suggested_natural_weapon_ids", []) or bp.get("natural_weapon_profile_ids", []) or []:
            rec = natural_profiles.get(str(wid))
            if isinstance(rec, dict):
                weapons.append(_canonical_weapon(deepcopy(rec), prof))
        return prof, bp, weapons

    def _can_admin(self, actor: Any) -> bool:
        return str(getattr(actor, "role", "")).lower() in {"admin", "owner"} or str(getattr(actor, "account_role", "")).lower() in {"admin", "owner"}

    def _check_permission(self, actor: Any, collection: str, object_id: str, action: str) -> BuilderResult | None:
        if not self.workspace.can_build(actor):
            return BuilderResult(False, "You do not have permission for that command.")
        if action in {"publish", "activate", "force_unlock"} and not self._can_admin(actor):
            return BuilderResult(False, f"You do not have permission to {action}.")
        if collection == "entities" and action in {"mutate", "edit", "delete"} and not self._can_admin(actor):
            existing = self._record(self.workspace.world_id(actor), "entities", object_id)
            zone_id = self._entity_zone_id(actor, object_id)
            assigned = self._assigned_zones(actor)
            if not zone_id:
                if existing is None and action == "mutate":
                    return None
                return BuilderResult(False, "This mobile is not assigned to a valid zone. An administrator must repair its ownership before normal Builder editing.")
            if assigned and zone_id not in assigned:
                return BuilderResult(False, f"Zone ownership denied: You are not assigned to zone {zone_id} and cannot edit mobile {object_id}.")
            if not assigned and existing is not None:
                return BuilderResult(False, f"Zone ownership denied: You are not assigned to zone {zone_id} and cannot edit mobile {object_id}.")
        return None

    def _assigned_zones(self, actor: Any) -> set[str]:
        vals = getattr(actor, "builder_zone_ids", None) or getattr(actor, "assigned_zone_ids", None) or getattr(actor, "zone_ids", None) or []
        if isinstance(vals, str):
            vals = [v.strip() for v in vals.split(",") if v.strip()]
        return {str(v) for v in vals if str(v)}

    def _entity_zone_id(self, actor: Any, object_id: str) -> str:
        world_id = self.workspace.world_id(actor)
        rec = self._record(world_id, "entities", object_id) or {}
        zone_id = str(rec.get("zone_id") or getattr(actor, "current_zone_id", "") or getattr(actor, "zone_id", ""))
        if zone_id:
            return zone_id
        room_id = str(getattr(actor, "edit_room_id", "") or getattr(actor, "room_id", ""))
        room = (self.workspace.load(world_id).get("rooms") or {}).get(room_id) or {}
        return str(room.get("zone_id") or "")

    def _lock_record(self, world_id: str, collection: str, object_id: str) -> dict[str, Any] | None:
        self._cleanup_stale_locks(world_id)
        with self._lock_db(world_id) as db:
            row = db.execute(
                "select world_id, collection, object_id, builder, builder_account, builder_character, session_id, acquired_at, last_activity_at, expires_at, revision from builder_locks where collection=? and object_id=?",
                (collection, object_id),
            ).fetchone()
        if not row:
            return None
        keys = ("world_id", "collection", "object_id", "builder", "builder_account", "builder_character", "session_id", "acquired_at", "last_activity_at", "expires_at", "revision")
        return dict(zip(keys, row))

    def _owns_lock(self, actor: Any, collection: str, object_id: str) -> bool:
        lock = self._lock_record(self.workspace.world_id(actor), collection, object_id) or {}
        return lock.get("builder") == self._actor_id(actor)

    def _actor_id(self, actor: Any) -> str:
        return "%s:%s:%s" % (getattr(actor, "account_id", ""), getattr(actor, "name", "") or getattr(actor, "id", "builder"), getattr(actor, "session_id", ""))

    def _state_path(self, world_id: str, name: str) -> Path:
        root = self.workspace.ensure(world_id) / "sessions"
        root.mkdir(parents=True, exist_ok=True)
        return root / name

    def _lock_db_path(self, world_id: str) -> Path:
        return self._state_path(world_id, "builder_locks.sqlite3")

    def _lock_db(self, world_id: str) -> sqlite3.Connection:
        db = sqlite3.connect(self._lock_db_path(world_id), timeout=30, isolation_level=None)
        db.execute("pragma journal_mode=wal")
        db.execute(
            "create table if not exists builder_locks ("
            "world_id text not null, collection text not null, object_id text not null, "
            "builder text not null, builder_account text, builder_character text, session_id text, "
            "acquired_at text not null, last_activity_at text not null, expires_at text not null, revision integer not null default 0, "
            "primary key (collection, object_id))"
        )
        return db

    def _cleanup_stale_locks(self, world_id: str) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock_db(world_id) as db:
            cur = db.execute("delete from builder_locks where expires_at < ?", (now,))
            return int(cur.rowcount or 0)

    def _history_path(self, actor: Any) -> Path:
        return self._state_path(self.workspace.world_id(actor), f"{getattr(actor,'id','builder')}_history.json")

    def _push_history(self, actor: Any, collection: str, object_id: str, before: Any, after: Any, operation: str) -> None:
        path = self._history_path(actor); data = self.workspace._read(path, {"undo": [], "redo": []})
        rec = {"revision_id": self.workspace.stamp(), "world_id": self.workspace.world_id(actor), "collection": collection, "object_id": object_id, "builder": self._actor_id(actor), "timestamp": self.workspace.stamp(), "operation": operation, "before": before, "after": after, "base_revision": (before or {}).get("_builder_revision") if isinstance(before, dict) else None}
        data.setdefault("undo", []).append(rec); data["undo"] = data["undo"][-100:]; data["redo"] = []
        self.workspace._atomic_json_write(path, data)

    def mutate(self, actor: Any, collection: str, object_id: str, updates: dict[str, Any], action: str = "builder mutate", expected_revision: int | None = None, admin_override: bool = False) -> BuilderResult:
        denied = self._check_permission(actor, collection, object_id, "mutate")
        if denied: return denied
        if not admin_override and not self._owns_lock(actor, collection, object_id):
            return BuilderResult(False, f"Active edit lock owned by {self._actor_id(actor)} is required for {collection} {object_id}.")
        world_id = self.workspace.world_id(actor); drafts = self.workspace.load(world_id); bucket = drafts.setdefault(collection, {})
        before = deepcopy(bucket.get(object_id)); rec = deepcopy(before) if isinstance(before, dict) else {"id": object_id}
        current_rev = int(rec.get("_builder_revision") or 0)
        if expected_revision is not None and expected_revision != current_rev and not admin_override:
            return BuilderResult(False, f"Draft changed since this editor opened (expected revision {expected_revision}, found {current_rev}). Reload before saving.")
        if collection == "entities": updates = self._normalize_entity_updates(object_id, updates)
        rec.update(updates); rec["_builder_revision"] = current_rev + 1; bucket[object_id] = rec
        self.workspace.save_drafts(world_id, drafts); self._push_history(actor, collection, object_id, before, rec, action)
        self.workspace.audit(actor, world_id, action, collection, object_id, before, rec)
        return BuilderResult(True, f"Draft {collection} {object_id} updated (revision {rec['_builder_revision']}).", rec)

    def _normalize_entity_updates(self, object_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        updates = MobileTemplate.from_legacy(deepcopy(updates)).to_canonical_dict()
        updates["id"] = object_id
        raw = updates.pop("natural_attacks", None)
        if raw is not None:
            cp = dict(updates.get("combat_profile") or {})
            cp["natural_weapons"] = [_canonical_weapon(x, object_id) for x in raw if isinstance(x, dict)]
            updates["combat_profile"] = cp
        if "natural_weapons" in updates:
            top_weapons = updates.pop("natural_weapons")
            cp = dict(updates.get("combat_profile") or {})
            if "natural_weapons" not in cp:
                cp["natural_weapons"] = [_canonical_weapon(x, object_id) for x in top_weapons if isinstance(x, dict)]
                updates["combat_profile"] = cp
        if isinstance(updates.get("combat_profile"), dict) and "natural_weapons" in updates["combat_profile"]:
            cp = dict(updates["combat_profile"])
            cp["natural_weapons"] = [_canonical_weapon(x, object_id) for x in cp.get("natural_weapons") or [] if isinstance(x, dict)]
            updates["combat_profile"] = cp
        return updates


    def create_or_update_mobile(self, actor: Any, object_id: str, updates: dict[str, Any], action: str = "mobile command") -> BuilderResult:
        denied = self._check_permission(actor, "entities", object_id, "mutate")
        if denied: return denied
        sess = self.sessions.active.get(self.sessions.actor_key(actor))
        if sess and sess.collection == "entities":
            if sess.object_id != object_id:
                return BuilderResult(False, f"Mobile editor is open for {sess.object_id}; save/quit it before editing {object_id}.")
            self._session_checkpoint(sess)
            sess.working_record.update(self._normalize_entity_updates(object_id, updates))
            sess.dirty = True; sess.saved = False
            return BuilderResult(True, f"Updated active medit scratch for {object_id}.", sess.working_record)
        lock = self.acquire_lock(actor, "entities", object_id)
        if not lock.ok: return lock
        before = self._record(self.workspace.world_id(actor), "entities", object_id)
        try:
            res = self.mutate(actor, "entities", object_id, updates, action)
            if res.ok:
                event = "builder_entity_template_created" if before is None and action.endswith("create") else "builder_entity_template_updated"
                self.workspace.publish(event, actor, self.workspace.world_id(actor), "entity_template", object_id, command=action)
            return res
        finally:
            self.release_lock(actor, "entities", object_id)

    def create_or_update_object(self, actor: Any, object_id: str, updates: dict[str, Any], action: str = "oedit") -> BuilderResult:
        denied = self._check_permission(actor, "items", object_id, "mutate")
        if denied: return denied
        clean = normalize_object_template(object_id, self._record(self.workspace.world_id(actor), "items", object_id))
        for field, value in updates.items():
            try:
                clean[field] = coerce_object_field(field, value)
            except ValueError as exc:
                return BuilderResult(False, str(exc), {"field": field})
        issues = validate_object_template(clean)
        errors = [x for x in issues if x.get("severity") == "error"]
        if errors:
            return BuilderResult(False, "Object validation failed:\n" + "\n".join(f"- {e['field_path']}: {e['message']}" for e in errors), {"issues": issues})
        lock = self.acquire_lock(actor, "items", object_id)
        if not lock.ok: return lock
        try:
            res = self.mutate(actor, "items", object_id, clean, action)
            if res.ok:
                self.workspace.publish("builder_object_template_updated", actor, self.workspace.world_id(actor), "item_template", object_id, command=action)
                res.data = {**(res.data or clean), "issues": issues}
            return res
        finally:
            self.release_lock(actor, "items", object_id)

    def object_menu(self, actor: Any, object_id: str) -> BuilderResult:
        rows = self.content_query.by_id_or_vnum(actor, "object", str(object_id))
        if len(rows) == 1:
            object_id = rows[0].canonical_id
        return self.start_editor(actor, "oedit", "items", object_id)

    def object_dependencies(self, actor: Any, object_id: str) -> BuilderResult:
        world_id = self.workspace.world_id(actor); drafts = self.workspace.load(world_id); matches=[]
        def scan(coll, label):
            for rid, rec in (drafts.get(coll) or {}).items():
                text=json.dumps(rec, sort_keys=True).lower() if isinstance(rec, dict) else str(rec).lower()
                if object_id.lower() in text and rid != object_id:
                    matches.append(f"{label} {rid}")
        for coll,label in (("rooms","room"),("resets","reset"),("entities","npc equipment"),("spawns","spawn"),("quest_definitions","quest"),("recipe_definitions","crafting"),("abilities","script/ability")):
            scan(coll,label)
        return BuilderResult(True, "Object dependencies for %s:\n%s" % (object_id, "\n".join(matches) if matches else "- none"), {"matches": matches})

    def delete_mobile(self, actor: Any, object_id: str) -> BuilderResult:
        denied = self._check_permission(actor, "entities", object_id, "delete")
        if denied: return denied
        world_id = self.workspace.world_id(actor); drafts = self.workspace.load(world_id); deps=[]
        for coll, label in (("spawns","spawn/reset"),("resets","reset"),("rooms","room"),("quest_definitions","quest"),("items","object"),("faction_definitions","faction"),("abilities","ability/script")):
            for rid, rec in (drafts.get(coll) or {}).items():
                if rid == object_id:
                    continue
                if object_id.lower() in json.dumps(rec, default=str).lower():
                    deps.append(f"{label} {rid}")
        if deps:
            before = deepcopy((drafts.get("entities") or {}).get(object_id))
            if isinstance(before, dict) and not before.get("deletion_state"):
                staged = deepcopy(before); staged["deletion_state"] = "staged"; staged["enabled"] = False; staged.setdefault("builder_status", "delete_staged")
                drafts.setdefault("entities", {})[object_id] = staged; self.workspace.save_drafts(world_id, drafts)
                self._push_history(actor, "entities", object_id, before, staged, "mdelete staged"); self.workspace.audit(actor, world_id, "mdelete staged", "entities", object_id, before, staged)
            return BuilderResult(False, "Delete protected; staged a soft deletion marker because dependencies exist:\n" + "\n".join(f"- {d}" for d in sorted(set(deps))) + "\nRemove dependencies before hard deletion or publish activation.")
        lock = self.acquire_lock(actor, "entities", object_id)
        if not lock.ok: return lock
        try:
            world_id = self.workspace.world_id(actor); drafts = self.workspace.load(world_id); before = deepcopy(drafts.get("entities", {}).get(object_id))
            if before is None: return BuilderResult(False, f"Draft entities {object_id} not found.")
            drafts.setdefault("entities", {}).pop(object_id, None); self.workspace.save_drafts(world_id, drafts)
            self._push_history(actor, "entities", object_id, before, None, "mdelete"); self.workspace.audit(actor, world_id, "mdelete", "entities", object_id, before, None)
            return BuilderResult(True, f"Draft entity_template {object_id} deleted.")
        finally:
            self.release_lock(actor, "entities", object_id)

    def clone(self, actor: Any, collection: str, source_id: str, new_id: str, display_name: str | None = None, keywords: list[str] | None = None) -> BuilderResult:
        denied = self._check_permission(actor, collection, source_id, "mutate")
        if denied: return denied
        world_id=self.workspace.world_id(actor); drafts=self.workspace.load(world_id); src=drafts.get(collection,{}).get(source_id)
        if not isinstance(src, dict): return BuilderResult(False, f"Cannot clone missing {collection} {source_id}.")
        lock = self.acquire_lock(actor, collection, new_id, admin=True)
        if not lock.ok: return lock
        try:
            rec=deepcopy(src); rec["id"]=new_id; rec["name"]=display_name or new_id.replace("_", " ").title(); rec["keywords"]=keywords or new_id.replace("_", " ").split(); rec["builder_status"]="incomplete"; rec.pop("_builder_revision", None); rec.pop("publish_status", None); rec.pop("runtime_status", None); rec.pop("deletion_state", None); rec=_normalize_advanced_mobile_sections(rec, new_id) if collection == "entities" else rec
            return self.mutate(actor, collection, new_id, rec, "clone", admin_override=True)
        finally:
            self.release_lock(actor, collection, new_id)

    def undo(self, actor: Any) -> BuilderResult:
        world_id=self.workspace.world_id(actor); path=self._history_path(actor); data=self.workspace._read(path,{"undo":[],"redo":[]})
        if not data.get("undo"): return BuilderResult(False,"Nothing to undo.")
        rec=data["undo"].pop(); drafts=self.workspace.load(world_id); bucket=drafts.setdefault(rec["collection"], {})
        cur=deepcopy(bucket.get(rec["object_id"])); data.setdefault("redo",[]).append({**rec,"before":rec.get("after"),"after":cur})
        if rec.get("before") is None: bucket.pop(rec["object_id"], None)
        else: bucket[rec["object_id"]]=rec["before"]
        self.workspace._atomic_json_write(path,data); self.workspace.save_drafts(world_id, drafts)
        return BuilderResult(True,f"Undo applied to {rec['collection']} {rec['object_id']}.")

    def redo(self, actor: Any) -> BuilderResult:
        world_id=self.workspace.world_id(actor); path=self._history_path(actor); data=self.workspace._read(path,{"undo":[],"redo":[]})
        if not data.get("redo"): return BuilderResult(False,"Nothing to redo.")
        rec=data["redo"].pop(); drafts=self.workspace.load(world_id); bucket=drafts.setdefault(rec["collection"], {})
        before=deepcopy(bucket.get(rec["object_id"])); data.setdefault("undo",[]).append({**rec,"before":before})
        if rec.get("after") is None: bucket.pop(rec["object_id"], None)
        else: bucket[rec["object_id"]]=rec["after"]
        self.workspace._atomic_json_write(path,data); self.workspace.save_drafts(world_id, drafts)
        return BuilderResult(True,f"Redo applied to {rec['collection']} {rec['object_id']}.")

    def acquire_lock(self, actor: Any, collection: str, object_id: str, admin: bool = False) -> BuilderResult:
        denied = self._check_permission(actor, collection, object_id, "force_unlock" if admin else "mutate")
        if denied and not admin:
            return denied
        world_id = self.workspace.world_id(actor)
        self._cleanup_stale_locks(world_id)
        now = datetime.now(timezone.utc)
        rec = self._record(world_id, collection, object_id) or {}
        lock = {
            "world_id": world_id,
            "collection": collection,
            "object_id": object_id,
            "builder": self._actor_id(actor),
            "builder_account": str(getattr(actor, "account_id", "")),
            "builder_character": str(getattr(actor, "id", "")),
            "session_id": str(getattr(actor, "session_id", "")),
            "acquired_at": self.workspace.stamp(),
            "last_activity_at": self.workspace.stamp(),
            "expires_at": (now + timedelta(hours=2)).isoformat(),
            "revision": int(rec.get("_builder_revision") or 0),
        }
        with self._lock_db(world_id) as db:
            db.execute("begin immediate")
            row = db.execute("select builder, expires_at from builder_locks where collection=? and object_id=?", (collection, object_id)).fetchone()
            expired = True
            if row:
                try:
                    expired = datetime.fromisoformat(str(row[1]).replace("Z", "+00:00")) < now
                except Exception:
                    expired = True
                if row[0] != lock["builder"] and not admin and not expired:
                    db.execute("rollback")
                    return BuilderResult(False, f"{object_id} currently being edited by {row[0]}.")
            db.execute(
                "insert or replace into builder_locks (world_id, collection, object_id, builder, builder_account, builder_character, session_id, acquired_at, last_activity_at, expires_at, revision) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                tuple(lock[k] for k in ("world_id", "collection", "object_id", "builder", "builder_account", "builder_character", "session_id", "acquired_at", "last_activity_at", "expires_at", "revision")),
            )
            db.execute("commit")
        return BuilderResult(True, f"Edit lock acquired for {object_id}.", {"lock": lock})

    def release_lock(self, actor: Any, collection: str, object_id: str) -> BuilderResult:
        world_id = self.workspace.world_id(actor)
        with self._lock_db(world_id) as db:
            row = db.execute("select builder from builder_locks where collection=? and object_id=?", (collection, object_id)).fetchone()
            if row and (row[0] == self._actor_id(actor) or self._can_admin(actor)):
                db.execute("delete from builder_locks where collection=? and object_id=?", (collection, object_id))
                return BuilderResult(True, f"Edit lock released for {object_id}.")
        return BuilderResult(False, "Cannot release a lock owned by another builder.")

    def admin_unlock(self, actor: Any, collection: str, object_id: str) -> BuilderResult:
        denied = self._check_permission(actor, collection, object_id, "force_unlock")
        if denied:
            return denied
        world_id = self.workspace.world_id(actor)
        with self._lock_db(world_id) as db:
            db.execute("delete from builder_locks where collection=? and object_id=?", (collection, object_id))
        return BuilderResult(True, f"Edit lock cleared for {object_id}.")

    def validate_object(self, actor: Any, collection: str, object_id: str) -> BuilderResult:
        rec = self._record(self.workspace.world_id(actor), collection, object_id)
        issues=[]
        if not rec: issues.append({"severity":"error","code":"missing_object","collection":collection,"object_id":object_id,"field_path":"id","message":"Object not found.","fix_hint":"Create the draft first."})
        if collection == "items" and rec:
            issues.extend(validate_object_template(normalize_object_template(object_id, rec)))
        if collection == "entities" and rec:
            canonical = MobileTemplate.from_legacy(rec).to_canonical_dict()
            ability_catalog = set(self.resolve_collection_records(actor, "abilities")) | set(self.resolve_collection_records(actor, "ability_loadouts"))
            if ability_catalog:
                canonical["_ability_catalog"] = sorted(ability_catalog)
            issues.extend(MobileTemplate.from_legacy(canonical).validate())
        lines=[f"{x['severity']}: {x['field_path']} {x['message']}" for x in issues] or ["- no focused issues"]
        return BuilderResult(not any(x['severity']=='error' for x in issues), "Validation for %s:\n%s" % (object_id, "\n".join(lines)), {"issues": issues})

    def preview(self, actor: Any, collection: str, object_id: str) -> BuilderResult:
        sess = self.sessions.active.get(self.sessions.actor_key(actor))
        rec = deepcopy(sess.working_record) if sess and sess.collection == collection and sess.object_id == object_id else (self._record(self.workspace.world_id(actor), collection, object_id) or {})
        if not rec: return BuilderResult(False, f"No draft {collection} {object_id}.")
        return self._preview_record(actor, collection, object_id, rec)

    def _preview_record(self, actor: Any, collection: str, object_id: str, rec: dict[str, Any]) -> BuilderResult:
        name = rec.get("name") or rec.get("title") or object_id; desc = rec.get("description") or rec.get("long_description") or "(no description)"
        lines = ["LOOK", str(name), str(desc), "", "EXAMINE", str(rec.get("examine_description") or desc), "", "CONSIDER", f"{name} appears to be level {rec.get('level', 1)}."]
        if collection == "items":
            projection = normalize_object_template(object_id, rec)
            lines = ["LOOK OBJECT", str(name), str(rec.get("look_description") or desc), "", "INVENTORY", f"{name} x{rec.get('stack_size', 1)}", "", "EQUIPMENT", f"{name} ({', '.join(rec.get('wear_flags') or []) or 'not wearable'})", "", "SHOP DISPLAY", f"{name} - {rec.get('cost', 0)} coins", "", "GROUND DISPLAY", str(rec.get('long_description') or f'{name} is here.')]
            return BuilderResult(True, "\n".join(lines), {"record": rec, "runtime_projection": projection})
        if collection == "entities":
            canonical = MobileTemplate.from_legacy(rec).to_canonical_dict()
            projection = MobileTemplate.from_legacy(canonical).to_runtime_projection()
            weapons=((projection.get("combat_profile") or {}).get("natural_weapons") or [])
            loadout = canonical.get("equipment_loadout") or {}
            loot = canonical.get("loot") or {}
            lines += ["", "RESOLVED TRAITS", f"species: {canonical.get('species') or canonical.get('race') or 'unset'}", f"body profile: {canonical.get('body_profile_id') or (canonical.get('combat_profile') or {}).get('body_profile') or 'unset'}", f"size: {canonical.get('size') or 'unset'}", f"positions: default={canonical.get('default_position')} spawn={canonical.get('spawn_position')}", f"flags: {', '.join(canonical.get('mobile_flags') or []) or 'none'}", f"permanent effects: {', '.join(canonical.get('affect_flags') or []) or 'none'}", "", "RESOLVED STATS", f"attributes: {json.dumps(canonical.get('attributes') or {}, sort_keys=True)}", f"resources: {json.dumps(canonical.get('resources') or {}, sort_keys=True)}", f"combat profile: {json.dumps(canonical.get('combat_profile') or {}, sort_keys=True)[:500]}", "", "CONTENT", f"equipment: {len(loadout.get('equipped') or {})} equipped slot(s)", f"inventory: {len(canonical.get('starting_inventory') or [])} carried entries", f"loot: profile={loot.get('profile_id') or 'unset'} explicit={len(loot.get('entries') or [])} corpse_enabled={loot.get('corpse_enabled')}", f"abilities: structured={len(canonical.get('combat_abilities') or [])} profile={canonical.get('ability_loadout_id') or (canonical.get('combat_profile') or {}).get('ability_loadout_id') or 'unset'}", f"behavior: {canonical.get('behavior_profile_id') or 'unset'} reactions={len(canonical.get('event_reactions') or [])}", f"faction: {canonical.get('faction_id') or 'unset'}", f"scripts: {len(canonical.get('script_attachments') or [])} structured attachment(s)", "", "COMBAT SNAPSHOT", f"natural weapons: {len(weapons)}", "NATURAL ATTACK LIST"]
            lines += [f"- {w.get('id')} {w.get('mechanical_family')} {w.get('verb_third_person')} with {w.get('noun_plural')} ({w.get('damage_dice')}, weight {w.get('selection_weight')})" for w in weapons] or ["- none"]
            if weapons:
                w=weapons[0]; lines += ["", "SAMPLE NORMAL HIT", str(w.get("observer_template", "{attacker} hits {victim}.")).format(attacker=name, victim="you", verb_third_person=w.get('verb_third_person'), verb_base=w.get('verb_base'), noun_plural=w.get('noun_plural'))]
            lines += ["", "ABILITY DECISION ORDER"]
            lines += [f"- priority {a.get('priority')}: {a.get('ability_id') or 'missing'} trigger={a.get('trigger')} target={a.get('target_selector')} chance={a.get('chance')} cooldown={a.get('cooldown',0)} runtime={'supported' if a.get('trigger') in MEDIT_RUNTIME_SUPPORTED_ABILITY_TRIGGERS else 'deferred'} reason={'eligible after cooldown/use-limit/chance/target checks' if a.get('trigger') in MEDIT_RUNTIME_SUPPORTED_ABILITY_TRIGGERS else 'no runtime combat hook'}" for a in sorted(canonical.get('combat_abilities') or [], key=lambda x:(int(x.get('priority',0)), str(x.get('id',''))))] or ["- none"]
            lines += ["", "EVENT REACTIONS"]
            lines += [f"- priority {r.get('priority')}: {r.get('event_type')} -> {r.get('action_type')} runtime={'supported' if r.get('event_type') in MEDIT_RUNTIME_SUPPORTED_REACTION_EVENTS and r.get('action_type') in MEDIT_RUNTIME_SUPPORTED_REACTION_ACTIONS else 'deferred'} loop_guard=max_depth_8" for r in sorted(canonical.get('event_reactions') or [], key=lambda x:(int(x.get('priority',0)), str(x.get('id',''))))] or ["- none"]
            lines += ["", "SCRIPT ATTACHMENTS"]
            lines += [f"- priority {a.get('priority')}: {a.get('script_id') or 'missing'} trigger={a.get('trigger')} runtime=canonical-host-required" for a in sorted(canonical.get('script_attachments') or [], key=lambda x:(int(x.get('priority',0)), str(x.get('id',''))))] or ["- none"]
            lines += ["", "SAMPLE DEATH/CORPSE", f"{name} dies. Corpse output uses loot profile {loot.get('profile_id') or 'none'} plus {len(loot.get('entries') or [])} explicit entries."]
            return BuilderResult(True, "\n".join(lines), {"record": rec, "runtime_projection": projection})
        return BuilderResult(True, "\n".join(lines), {"record": rec})

    def publish(self, actor: Any) -> BuilderResult:
        denied = self._check_permission(actor, "generation", "publish", "publish")
        if denied: return denied
        world_id=self.workspace.world_id(actor); root=self.workspace.ensure(world_id); drafts=self.workspace.load(world_id)
        errors=[]; warnings=[]
        for oid in drafts.get("entities", {}):
            v=self.validate_object(actor, "entities", oid); issues=(v.data or {}).get("issues", [])
            errors += [x for x in issues if x.get("severity")=="error"]; warnings += [x for x in issues if x.get("severity")=="warning"]
        if errors: return BuilderResult(False, "Publish blocked by validation errors:\n"+"\n".join(f"- {e['object_id']} {e['field_path']}: {e['message']}" for e in errors), {"errors": errors})
        parent=(self.workspace._read(root/"generations"/"active.json", {}) or {}).get("active_generation")
        gen=f"generation-{self.workspace.stamp()}"; gens=root/"generations"/gen; tmp=root/"generations"/(gen+".tmp"); tmp.mkdir(parents=True, exist_ok=True)
        import hashlib
        hashes={}
        for key, filename in DRAFT_FILES.items():
            data=drafts.get(key, {}); payload=json.dumps(data, indent=2, sort_keys=True)+"\n"; (tmp/filename).write_text(payload, encoding="utf-8"); hashes[filename]=hashlib.sha256(payload.encode()).hexdigest()
        manifest={"generation_id":gen,"parent_generation":parent,"timestamp":self.workspace.stamp(),"publisher":self._actor_id(actor),"content_hashes":hashes,"schema_versions":{"natural_weapons":"combat_profile.natural_weapons/v1"},"changed_collections":sorted(drafts),"validation_report":{"errors":[],"warnings":warnings},"rollback_metadata":{"previous_generation":parent},"live_mob_update_policy":"new spawns use this generation; existing live mobs retain old template combat state until despawn/death"}
        self.workspace._atomic_json_write(tmp/"manifest.json", manifest); tmp.replace(gens)
        self.workspace.audit(actor, world_id, "publish generation", "generation", gen, None, manifest)
        return BuilderResult(True, f"Published immutable generation package {gen}. Activate explicitly with builder generation activate {gen}.", {"generation": gen, "plan": manifest})

    def activate_generation(self, actor: Any, generation_id: str | None = None) -> BuilderResult:
        denied = self._check_permission(actor, "generation", generation_id or "active", "activate")
        if denied: return denied
        world_id=self.workspace.world_id(actor); root=self.workspace.ensure(world_id); active_path=root/"generations"/"active.json"
        if not generation_id or generation_id == "latest":
            gens=sorted(p.name for p in (root/"generations").glob("generation-*") if p.is_dir())
            if not gens: return BuilderResult(False, "No generation packages exist.")
            generation_id=gens[-1]
        gen_dir=root/"generations"/generation_id; manifest=self.workspace._read(gen_dir/"manifest.json", None)
        if not manifest: return BuilderResult(False, f"Generation {generation_id} is missing manifest.json.")
        previous=(self.workspace._read(active_path,{}) or {}).get("active_generation")
        registries = {}
        for key, filename in DRAFT_FILES.items():
            registries[key] = self.workspace._coerce_draft_collection(key, filename, self.workspace._read(gen_dir / filename, {}))
        registries["entities"] = {oid: MobileTemplate.from_generation(rec).to_canonical_dict() for oid, rec in registries.get("entities", {}).items() if isinstance(rec, dict)}
        previous = getattr(self.runtime, "active_content_generation_id", None) or previous
        if self.runtime is not None:
            self.runtime.activate_content_generation(generation_id, registries)
        self.previous_content_generation_id = previous
        self.active_content_generation_id = generation_id
        self.active_content_generation = registries
        self.workspace._atomic_json_write(active_path, {"active_generation":generation_id,"previous_generation":previous,"activated_at":self.workspace.stamp(),"activated_by":self._actor_id(actor),"world_generation":self.workspace.stamp(),"live_mob_update_policy":manifest.get("live_mob_update_policy")})
        self.workspace.audit(actor, world_id, "activate generation", "generation", generation_id, {"previous":previous}, {"active":generation_id})
        return BuilderResult(True, f"Activated generation {generation_id}. Previous generation: {previous or 'none'}.", {"active_generation":generation_id,"previous_generation":previous})

    def rollback_generation(self, actor: Any) -> BuilderResult:
        active=self.workspace._read(self.workspace.ensure(self.workspace.world_id(actor))/"generations"/"active.json", {})
        prev=active.get("previous_generation")
        if not prev: return BuilderResult(False, "No previous generation is recorded for rollback.")
        return self.activate_generation(actor, prev)

    def body_profiles(self, actor: Any | None = None) -> list[str]:
        return sorted(self.resolve_collection_records(actor, "body_profiles").keys())
    def apply_body_profile(self, actor: Any, mob_id: str, profile: str) -> BuilderResult:
        prof, bp, weapons = self._body_profile_result(actor, profile)
        if not bp: return BuilderResult(False, "Unknown body profile. Choose: " + ", ".join(self.body_profiles(actor)))
        return self.mutate(actor, "entities", mob_id, {"body_profile_id": prof, "combat_profile": {"body_profile": prof, "natural_weapons": weapons}}, "body profile")

    def start_editor(self, actor: Any, editor: str, collection: str, object_id: str) -> BuilderResult:
        denied = self._check_permission(actor, collection, object_id, "edit")
        if denied: return denied
        return self.sessions.start(actor, editor, collection, object_id)

    def discover_editor_target(self, actor: Any, editor: str, args: list[str]) -> BuilderResult:
        kind = {"medit": "mob", "oedit": "object", "redit": "room", "zedit": "zone", "aedit": "area"}.get(editor, editor)
        if not args or args[0].lower() in {"list", "all", "zone", "area"}:
            return self.list_content(actor, kind, args or ["list"])
        words = args[1:] if args[0].lower() in {"id", "vnum", "search"} else args
        rows = self.content_query.by_id_or_vnum(actor, kind, " ".join(words))
        if not rows:
            return BuilderResult(False, f"No {kind} matches {' '.join(words)}.")
        if len(rows) > 1:
            self._set_picker(actor, editor, rows)
            return BuilderResult(False, self.render_picker(f"{editor.upper()} choices", rows))
        coll = BuilderContentQueryService.COLLECTIONS.get(kind, kind)
        return self.start_editor(actor, editor, coll, rows[0].canonical_id)

    def render_picker(self, title: str, rows: list[BuilderContentRecord], page: int = 1) -> str:
        per = 25; pages = max(1, (len(rows) + per - 1) // per); page = min(max(1, page), pages)
        shown = rows[(page - 1) * per: page * per]
        lines = [title, f"Choose one; do not guess. Page {page}/{pages}. Enter number, N, P, or Q:"]
        for i, r in enumerate(shown, 1):
            lines.append(f"{i:>2}. {r.legacy_vnum if r.legacy_vnum is not None else '----'} {r.canonical_id} - {r.display_name} [{r.content_source}/{self._status_code(r)}]")
        return "\n".join(lines)

    def _current_runtime_location(self, actor: Any, drafts: dict[str, Any]) -> tuple[str, str, str, str]:
        """Resolve current world/area/zone/room from the actor's mapped room before stale selections."""
        world_id = self.workspace.world_id(actor)
        room_id = str(getattr(actor, "room_id", "") or getattr(actor, "edit_room_id", "") or "")
        room = (drafts.get("rooms") or {}).get(room_id) or {}
        if not room and self.runtime is not None and hasattr(self.runtime, "runtime_room_data"):
            try:
                runtime_room, _src = self.runtime.runtime_room_data(actor, room_id)
                if isinstance(runtime_room, dict):
                    room = runtime_room
            except Exception:
                room = {}
        area_id = str(room.get("area_id") or getattr(actor, "current_area_id", "") or getattr(actor, "area_id", "") or "")
        zone_id = str(room.get("zone_id") or getattr(actor, "current_zone_id", "") or getattr(actor, "zone_id", "") or "")
        if not zone_id:
            for zid, zone in (drafts.get("zones") or {}).items():
                if room_id in (zone.get("room_ids") or []):
                    zone_id = str(zid); break
        if not zone_id and self.runtime is not None and getattr(self.runtime, "active_world", None) is not None:
            for zone in getattr(self.runtime.active_world, "zones", []) or []:
                if room_id in (zone.get("room_ids") or []):
                    zone_id = str(zone.get("id") or ""); break
        return world_id, area_id, zone_id, room_id

    def _validation_text(self, r: BuilderContentRecord) -> str:
        rec = r.record or {}
        problems: list[str] = []
        if not r.display_name or r.display_name == r.canonical_id:
            problems.append("Missing display name")
        if r.legacy_vnum is None and r.type in {"entities", "items", "rooms"}:
            problems.append("Missing VNUM")
        if r.type in {"entities", "items", "rooms"}:
            if not r.area:
                problems.append("Missing area")
            if not r.zone:
                problems.append("Missing zone")
        if r.type == "entities":
            role_text = " ".join(str(rec.get(k) or "") for k in ("entity_type", "role", "npc_role", "service_type", "combat_role", "combat_behavior_profile_id", "shop_id", "trainer_id")).lower()
            service_npc = any(x in role_text or x in r.canonical_id.lower() for x in ("merchant", "shop", "trainer", "registrar", "banker", "healer", "tavern", "keeper"))
            combat_npc = any(x in role_text for x in ("combat", "aggressive", "hostile", "creature", "beast")) or not service_npc
            if not (rec.get("keywords") or rec.get("aliases")):
                problems.append("Missing keywords")
            if not (rec.get("long_description") or rec.get("description") or rec.get("look_description")):
                problems.append("Missing long description")
            if combat_npc:
                if not (rec.get("body_profile_id") or (rec.get("combat_profile") or {}).get("body_profile")):
                    problems.append("Missing body profile")
                if not ((rec.get("combat_profile") or {}).get("natural_weapons") or rec.get("natural_attacks") or rec.get("weapon_id") or rec.get("equipment")):
                    problems.append("Missing attack profile")
                if not (rec.get("ai_profile_id") or rec.get("behavior_profile_id") or rec.get("combat_behavior_profile_id")):
                    problems.append("Missing combat behavior")
            elif service_npc and r.spawn_count == 0:
                problems.append("Service NPC has no spawn")
        elif r.type == "items":
            if not (rec.get("keywords") or rec.get("aliases")):
                problems.append("Missing keywords")
            if not (rec.get("long_description") or rec.get("description")):
                problems.append("Missing long description")
            if not (rec.get("item_type") or rec.get("type")):
                problems.append("Missing type")
        elif r.type == "rooms":
            if not (rec.get("description") or rec.get("long_description")):
                problems.append("Missing description")
        return "; ".join(problems) if problems else "Valid"

    def _status_code(self, r: BuilderContentRecord) -> str:
        if r.builder_status.lower() == "draft":
            return "DRAFT"
        if not r.area or not r.zone or r.legacy_vnum is None:
            return "UNASSIGNED"
        text = self._validation_text(r)
        if text == "Valid":
            return "OK"
        return "ERROR" if "Missing VNUM" in text or "Missing area" in text or "Missing zone" in text else "WARN"

    def _table(self, headers: list[str], rows: list[list[str]]) -> str:
        if not rows:
            return "  (none)"
        widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row): widths[i] = max(widths[i], len(str(cell)))
        fmt = "  ".join("{:<" + str(w) + "}" for w in widths)
        return "\n".join([fmt.format(*headers), "  ".join("-" * w for w in widths)] + [fmt.format(*[str(c) for c in row]) for row in rows])

    def _builder_list_header(self, title: str, total: int, world_id: str, area_id: str, zone_id: str, room_id: str, page: int, pages: int, actor: Any | None = None) -> list[str]:
        rule = "-" * 56
        areas = self.resolve_collection_records(actor, "areas")
        zones = self.resolve_collection_records(actor, "zones")
        rooms = self.resolve_collection_records(actor, "rooms")
        room = rooms.get(room_id, {})
        room_label = ((f"[{int(room.get('vnum')):04d}] " if room.get('vnum') is not None else "") + str(room.get('name') or room.get('title') or room_id or 'unassigned'))
        area_name = areas.get(area_id, {}).get('name') or zones.get(zone_id, {}).get('name') or area_id or 'unassigned'
        zone_name = zones.get(zone_id, {}).get('name') or zone_id or 'unassigned'
        return [rule, f"{title} ({total} {'record' if total == 1 else 'records'})", f"World: {world_id}", f"Area : {area_name}", f"Zone : {zone_name}", f"Room : {room_label}", f"Page : {page} / {pages}", rule]

    def list_content(self, actor: Any, kind: str, args: list[str] | None = None) -> BuilderResult:
        args = list(args or [])
        drafts = self.workspace.load(self.workspace.world_id(actor))
        world_id, cur_area, cur_zone, cur_room = self._current_runtime_location(actor, drafts)
        rows = self.content_query.list(actor, kind)
        page = 1; source = ""; detail_mode = "brief"
        if args and args[0].lower() in {"brief", "detail", "verbose"}:
            detail_mode = args.pop(0).lower()
        mode = args[0].lower() if args else "current"
        if mode in {"list", "all", "world", ""}: mode = "all"
        if mode == "page" and len(args) > 1 and args[1].isdigit(): page = int(args[1]); mode = "all"
        elif mode == "source" and len(args) > 1: source = args[1].lower(); mode = "all"
        elif mode in {"draft", "live", "active"}: source = "generation" if mode == "active" else mode; mode = "all"
        elif re.fullmatch(r"\d+-\d+", mode):
            a,b = [int(x) for x in mode.split("-",1)]
            if kind == "zone":
                def _zone_overlaps(r):
                    try:
                        zs = int(r.record.get("vnum_start") if r.record.get("vnum_start") not in (None, "") else (r.legacy_vnum if r.legacy_vnum is not None else -1))
                        ze = int(r.record.get("vnum_end") if r.record.get("vnum_end") not in (None, "") else zs)
                    except Exception:
                        return False
                    return zs <= b and ze >= a
                rows = [r for r in rows if _zone_overlaps(r)]
            else:
                rows = [r for r in rows if r.legacy_vnum is not None and a <= r.legacy_vnum <= b]
            mode = "filtered"
        elif mode == "id" and len(args) > 1: rows = [r for r in rows if r.canonical_id == args[1]]; mode = "filtered"; detail_mode = "detail"
        elif mode == "vnum" and len(args) > 1 and args[1].isdigit(): rows = [r for r in rows if r.legacy_vnum == int(args[1])]; mode = "filtered"; detail_mode = "detail"
        elif mode not in {"all","world","zone","area","here","current","invalid","incomplete"}:
            rows = self.content_query.search(actor, kind, " ".join(args)); mode = "search"; detail_mode = "detail"
        if source: rows = [r for r in rows if r.content_source == source]
        if kind == "area" and mode == "current":
            rows = [r for r in rows if r.canonical_id == cur_area]
        elif kind == "zone" and mode == "current":
            rows = [r for r in rows if r.canonical_id == cur_zone]
        elif kind == "zone" and mode == "area":
            a = args[1] if len(args) > 1 else cur_area; rows = [r for r in rows if str(r.record.get("area_id") or "") == a]
        elif mode == "zone":
            z = args[1] if len(args) > 1 and args[1].lower() != "current" else cur_zone; rows = [r for r in rows if r.zone == z]
        elif mode == "area":
            a = args[1] if len(args) > 1 else cur_area; rows = [r for r in rows if r.area == a]
        elif mode in {"current"} and cur_zone: rows = [r for r in rows if r.zone == cur_zone]
        elif mode == "here": rows = [r for r in rows if r.canonical_id == cur_room or str(r.record.get("room_id") or "") == cur_room or cur_room in json.dumps(r.record, default=str)]
        elif mode in {"invalid","incomplete"}:
            detail_mode = "verbose"
            rows = [r for r in rows if self._validation_text(r) != "Valid" or r.builder_status.lower() == "incomplete"]
        per = 25; total = len(rows); pages = max(1, (total + per - 1) // per); page = min(max(1, page), pages); shown = rows[(page-1)*per:page*per]
        title = {"mob":"Mob List", "object":"Object List", "room":"Room List", "area":"Area List", "zone":"Zone List"}.get(kind, f"{kind.title()} List")
        table_rows: list[list[str]] = []
        def _vnum_text(r: BuilderContentRecord) -> str:
            return f"[{int(r.legacy_vnum):04d}]" if r.legacy_vnum is not None else "[-----]"

        def _clip(value: Any, width: int) -> str:
            text = str(value or "")
            return text[:width]

        def _exit_letters(r: BuilderContentRecord) -> str:
            exits = r.record.get("exits") or {}
            if isinstance(exits, dict):
                order = ["north", "east", "south", "west", "up", "down", "n", "e", "s", "w", "u", "d"]
                letters = []
                for direction in order:
                    if direction in exits:
                        letter = {"north":"n","east":"e","south":"s","west":"w","up":"u","down":"d"}.get(direction, direction[:1])
                        if letter not in letters:
                            letters.append(letter)
                return "".join(letters)
            return ""

        def _brief_table() -> list[str] | None:
            brief_lines: list[str] = []
            if kind == "mob" and detail_mode == "brief":
                brief_lines = ["Index VNum    Mobile Name                                  Level", "----- ------- -------------------------------------------- -----"]
                for n, r in enumerate(shown, (page-1)*per+1):
                    name = _clip(r.display_name, 44)
                    level = str(r.record.get("level", ""))
                    brief_lines.append(f"{n:>4}) {_vnum_text(r)} {name:<44} [{level:>4}]")
                return brief_lines
            if kind == "object" and detail_mode == "brief":
                brief_lines = ["Index VNum    Object Name                                  Object Type", "----- ------- -------------------------------------------- ----------------"]
                for n, r in enumerate(shown, (page-1)*per+1):
                    name = _clip(r.display_name, 44)
                    obj_type = str(r.record.get("item_type") or r.record.get("type", ""))
                    brief_lines.append(f"{n:>4}) {_vnum_text(r)} {name:<44} [{obj_type}]")
                return brief_lines
            if kind == "room" and detail_mode == "brief":
                brief_lines = ["Index VNum    Room Name                                    Exits", "----- ------- -------------------------------------------- -----"]
                for n, r in enumerate(shown, (page-1)*per+1):
                    name = _clip(r.display_name, 44)
                    brief_lines.append(f"{n:>4}) {_vnum_text(r)} {name:<44} {_exit_letters(r)}")
                return brief_lines
            return None

        if kind == "mob":
            if detail_mode == "brief":
                headers = ["Index","VNum","Mobile Name","Level"]
                for n, r in enumerate(shown, (page-1)*per+1): table_rows.append([n, r.legacy_vnum if r.legacy_vnum is not None else "-----", r.display_name, r.record.get("level", "")])
            else:
                headers = ["VNUM","ID","Name","Lvl","Area","Zone","Source","Validation"]
                for r in shown: table_rows.append([r.legacy_vnum if r.legacy_vnum is not None else "----", r.canonical_id, r.display_name, r.record.get("level", ""), r.area, r.zone, r.content_source, self._validation_text(r) if detail_mode == "verbose" else self._status_code(r)])
        elif kind == "object":
            if detail_mode == "brief":
                headers = ["Index","VNum","Object Name","Object Type"]
                for n, r in enumerate(shown, (page-1)*per+1): table_rows.append([n, r.legacy_vnum if r.legacy_vnum is not None else "-----", r.display_name, r.record.get("item_type") or r.record.get("type", "")])
            else:
                headers = ["VNUM","ID","Name","Type","Wear","Area","Zone","Status"]
                for r in shown: table_rows.append([r.legacy_vnum if r.legacy_vnum is not None else "----", r.canonical_id, r.display_name, r.record.get("item_type") or r.record.get("type", ""), ",".join(r.record.get("wear_slots") or r.record.get("wear_flags") or []), r.area, r.zone, self._validation_text(r) if detail_mode == "verbose" else self._status_code(r)])
        elif kind == "room":
            if detail_mode == "brief":
                headers = ["Index","VNum","Room Name","Exits"]
                for n, r in enumerate(shown, (page-1)*per+1): table_rows.append([n, r.legacy_vnum if r.legacy_vnum is not None else "-----", r.display_name, _exit_letters(r)])
            else:
                headers = ["VNUM","ID","Title","Area","Zone","Flags","Exits"]
                for r in shown: table_rows.append([r.legacy_vnum if r.legacy_vnum is not None else "----", r.canonical_id, r.display_name, r.area, r.zone, ",".join(r.record.get("flags") or []), len(r.record.get("exits") or {})])
        elif kind == "area":
            headers = ["Area name","ID","Rooms","Mobs","Objects","Resets","Validation"]
            all_rooms = self.resolve_collection_records(actor, "rooms")
            all_mobs = self.resolve_collection_records(actor, "entities")
            all_objs = self.resolve_collection_records(actor, "items")
            all_resets = self.resolve_collection_records(actor, "resets")
            for r in shown:
                aid = r.canonical_id
                zone_ids = set(map(str, r.record.get("zone_ids") or []))
                zone_room_ids = set()
                for zid, zrec in self.resolve_collection_records(actor, "zones").items():
                    if str(zid) in zone_ids or str(zrec.get("area_id") or "") == aid:
                        zone_room_ids.update(map(str, zrec.get("room_ids") or []))
                rc = len(zone_room_ids) if zone_room_ids else sum(1 for x in all_rooms.values() if x.get("area_id") == aid)
                table_rows.append([r.display_name, aid, rc, sum(1 for x in all_mobs.values() if x.get("area_id") == aid), sum(1 for x in all_objs.values() if x.get("area_id") == aid), sum(1 for x in all_resets.values() if x.get("area_id") == aid or aid in json.dumps(x, default=str)), self._validation_text(r)])
        elif kind == "zone":
            headers = ["Zone","VNUM range","Rooms","Mobs","Objects","Spawns","Resets"]
            all_rooms = self.resolve_collection_records(actor, "rooms")
            all_mobs = self.resolve_collection_records(actor, "entities")
            all_objs = self.resolve_collection_records(actor, "items")
            all_spawns = self.resolve_collection_records(actor, "spawns")
            all_resets = self.resolve_collection_records(actor, "resets")
            for r in shown:
                zid = r.canonical_id; rec = r.record
                table_rows.append([zid, f"{rec.get('vnum_start','')}-{rec.get('vnum_end','')}", sum(1 for x in all_rooms.values() if x.get("zone_id") == zid), sum(1 for x in all_mobs.values() if x.get("zone_id") == zid), sum(1 for x in all_objs.values() if x.get("zone_id") == zid), sum(1 for x in all_spawns.values() if x.get("zone_id") == zid or zid in json.dumps(x, default=str)), sum(1 for x in all_resets.values() if x.get("zone_id") == zid or zid in json.dumps(x, default=str))])
        else:
            headers = ["VNUM","ID","Name","Type","Area","Zone","Source","Status"]
            for r in shown: table_rows.append([r.legacy_vnum if r.legacy_vnum is not None else "----", r.canonical_id, r.display_name, r.type, r.area, r.zone, r.content_source, self._validation_text(r) if detail_mode == "verbose" else self._status_code(r)])
        # Hide columns that are entirely blank/dash except for identity essentials.
        keep=[]
        for i,h in enumerate(headers):
            vals=[str(row[i]) for row in table_rows]
            keep.append(h in {"VNUM","ID","Name","Title"} or any(v not in {"", "-", "none"} for v in vals))
        headers=[h for h,k in zip(headers,keep) if k]; table_rows=[[str(c) for c,k in zip(row,keep) if k] for row in table_rows]
        if kind == "mob": title = "Mob List - Mobiles in " + world_id.replace("_", " ").title()
        elif kind == "object": title = "Object List - Objects in " + world_id.replace("_", " ").title()
        lines = self._builder_list_header(title, total, world_id, cur_area if mode not in {"all","world"} else "", cur_zone if mode not in {"all","world"} else "", cur_room, page, pages, actor)
        if kind in {"mob", "object"}:
            lines.append(f"Current zone: {cur_zone or 'none'}")
            lines.append(f"Usage: {'mlist 1500-1599' if kind == 'mob' else 'olist 1300-1399'}; {kind}list all; zone; area; id; vnum; source draft/active/live")
        if kind == "area":
            lines.append("ID | Name | Range | Rooms | Zones | Source | Current")
            for row in table_rows:
                if len(row) >= 3:
                    lines.append(f"{row[1]} | {row[0]} | {row[2]} | ")
            if len(shown) == 1:
                rec = shown[0].record
                lines += ["Area detail:", f"room_vnum_start-room_vnum_end: {rec.get('room_vnum_start')}-{rec.get('room_vnum_end')}"]
        if kind == "zone" and len(shown) == 1:
            lines += ["Zone detail:", f"room_ids count: {len(shown[0].record.get('room_ids') or [])}"]
        if kind == "area" and mode == "current":
            lines.append('Use "alist all" to list all areas.')
        brief = _brief_table()
        if brief is not None:
            lines += ["", *brief, "", f" {total} {'mobiles' if kind == 'mob' else 'objects' if kind == 'object' else 'rooms'} found."]
        else:
            lines += ["", self._table(headers, table_rows), "", "-" * 56]
        return BuilderResult(True, "\n".join(lines), {"total": total, "rows": [r.__dict__ for r in shown]})

    def vnum_report(self, actor: Any, args: list[str] | None = None) -> BuilderResult:
        args=list(args or []); kinds=["mob","object","room","zone"] if not args or args[0]=="free" else [args[0]]
        free = bool(args and args[0]=="free")
        if free and len(args)>1: kinds=[args[1]]
        lines=["VNUM report"]; seen={}
        for k in kinds:
            rows=self.content_query.list(actor,k); vals=[r.legacy_vnum for r in rows if r.legacy_vnum is not None]
            lines.append(f"{k}: {len(vals)} assigned")
            for v in vals: seen.setdefault(v,[]).append(k)
            if free:
                used=set(vals); base={"mob":1500,"object":1300,"room":1000,"zone":1000}.get(k,1)
                first=next((n for n in range(base, base+1000) if n not in used), None)
                lines.append(f"first free {k}: {first if first is not None else 'none'}")
        dups={v:ks for v,ks in seen.items() if len(ks)>1}
        lines.append("duplicate/cross-type conflicts: " + (", ".join(f"{v}({','.join(ks)})" for v,ks in sorted(dups.items())) or "none"))
        return BuilderResult(True,"\n".join(lines))

    def _picker_key(self, actor: Any) -> str:
        return "%s:%s:%s:%s" % (getattr(actor, "account_id", ""), getattr(actor, "id", getattr(actor, "name", "builder")), getattr(actor, "session_id", ""), self.workspace.world_id(actor))

    def _set_picker(self, actor: Any, editor: str, rows: list[BuilderContentRecord], page: int = 1) -> None:
        state = getattr(self, "_pending_pickers", {})
        state[self._picker_key(actor)] = {"editor": editor, "ids": [r.canonical_id for r in rows], "kind": {"medit":"mob","oedit":"object","redit":"room","zedit":"zone","aedit":"area"}.get(editor, editor), "page": page, "created_at": self.workspace.stamp()}
        self._pending_pickers = state

    def continue_picker(self, actor: Any, text: str) -> BuilderResult | None:
        token = str(text or "").strip().lower()
        state = getattr(self, "_pending_pickers", {})
        pick = state.get(self._picker_key(actor))
        if not pick or token not in {"q", "quit", "cancel", "n", "next", "p", "prev", "previous"} and not token.isdigit():
            return None
        rows_by_id = {r.canonical_id: r for r in self.content_query.list(actor, pick["kind"])}
        rows = [rows_by_id[i] for i in pick.get("ids", []) if i in rows_by_id]
        per = 25; page = int(pick.get("page") or 1); pages = max(1, (len(rows) + per - 1)//per)
        if token in {"q", "quit", "cancel"}:
            state.pop(self._picker_key(actor), None); return BuilderResult(True, "Picker cancelled.")
        if token in {"n", "next"}:
            pick["page"] = min(pages, page + 1); return BuilderResult(True, self.render_picker(f"{pick['editor'].upper()} choices", rows, pick["page"]))
        if token in {"p", "prev", "previous"}:
            pick["page"] = max(1, page - 1); return BuilderResult(True, self.render_picker(f"{pick['editor'].upper()} choices", rows, pick["page"]))
        idx = (page - 1) * per + int(token) - 1
        if idx < 0 or idx >= len(rows):
            return BuilderResult(False, "Picker selection out of range. Enter a listed number, N, P, or Q.")
        state.pop(self._picker_key(actor), None)
        coll = BuilderContentQueryService.COLLECTIONS.get(pick["kind"], pick["kind"])
        return self.start_editor(actor, pick["editor"], coll, rows[idx].canonical_id)

    def _normalization_records(self, actor: Any) -> tuple[dict[str, dict[str, dict[str, Any]]], dict[str, dict[str, Any]]]:
        world_id = self.workspace.world_id(actor)
        drafts = self.workspace.load(world_id)
        records = {k: self.resolve_collection_records(actor, k) for k in ("areas", "zones", "rooms", "entities", "items", "spawns", "resets")}
        return records, drafts

    def _room_owner(self, room_id: str, records: dict[str, dict[str, dict[str, Any]]]) -> tuple[str, str]:
        room = (records.get("rooms") or {}).get(str(room_id)) or {}
        return str(room.get("area_id") or ""), str(room.get("zone_id") or "")

    def _infer_area_zone(self, kind: str, rec: dict[str, Any], records: dict[str, dict[str, dict[str, Any]]]) -> tuple[str, str, str, list[str], list[str]]:
        aid = str(rec.get("area_id") or rec.get("area") or "")
        zid = str(rec.get("zone_id") or rec.get("zone") or "")
        zones = records.get("zones", {})
        evidence: list[str] = []
        conflicts: list[str] = []
        if aid and zid:
            if zid in zones and str(zones[zid].get("area_id") or "") not in {"", aid}:
                conflicts.append(f"zone {zid} belongs to area {zones[zid].get('area_id')}, not {aid}")
            evidence.append("explicit area_id and zone_id")
            return aid, zid, "CONFIRMED" if not conflicts else "BLOCKED", evidence, conflicts
        room_keys = ("room_id", "spawn_room_id", "reset_room_id", "default_room_id", "keeper_room_id", "trainer_room_id", "quest_room_id")
        owners=[]
        for key in room_keys:
            ref = str(rec.get(key) or "")
            ra, rz = self._room_owner(ref, records) if ref else ("", "")
            if ra and rz:
                owners.append((ra, rz, key, ref)); evidence.append(f"{key} references room {ref} with area {ra} and zone {rz}")
        # scan canonical placements / reset command payloads for room refs
        for key, val in rec.items():
            if "room" in str(key).lower() and isinstance(val, str):
                ra, rz = self._room_owner(val, records)
                if ra and rz and (ra, rz, key, val) not in owners:
                    owners.append((ra, rz, key, val)); evidence.append(f"{key} references room {val} with area {ra} and zone {rz}")
        if owners:
            zones_seen={(ra,rz) for ra,rz,_,_ in owners}
            if len(zones_seen)==1:
                ra, rz, _, _ = owners[0]
                return aid or ra, zid or rz, "CONFIRMED", evidence, conflicts
            conflicts += [f"conflicting room ownership {ra}/{rz} from {key}={ref}" for ra,rz,key,ref in owners]
            return aid, zid, "BLOCKED", evidence, conflicts
        if kind == "rooms":
            v = rec.get("vnum")
            try: v = int(v) if v not in (None, "") else None
            except Exception: v = None
            rz = self.vnum_ranges.zone_for_room_vnum(zones, v)
            if rz and rz in zones:
                za = str(zones[rz].get("area_id") or "")
                evidence.append(f"room VNUM {v} falls inside configured zone range {rz}")
                return aid or za, zid or rz, "CONFIRMED", evidence, conflicts
        hints=[]
        txt=" ".join(str(x) for x in (rec.get("id"), rec.get("name"), rec.get("tags")))
        if txt.strip(): hints.append(f"weak name/tag hint: {txt[:80]}")
        return aid, zid, "MANUAL_REVIEW", evidence + hints, conflicts

    def normalization_plan(self, actor: Any) -> list[dict[str, Any]]:
        records, _drafts = self._normalization_records(actor)
        used_by_ns: dict[str, set[int]] = {}
        for k in ("rooms", "entities", "items", "spawns", "resets"):
            ns = self.vnum_ranges.namespace_for(k); used_by_ns.setdefault(ns, set())
            for r in records.get(k, {}).values():
                raw = r.get("vnum", r.get("spawn_vnum"))
                if str(raw).isdigit(): used_by_ns[ns].add(int(raw))
        plan=[]
        for kind in ("rooms", "items", "entities", "spawns", "resets"):
            ns=self.vnum_ranges.namespace_for(kind)
            for oid, rec in sorted(records.get(kind, {}).items(), key=lambda kv: (str(kv[1].get("zone_id") or ""), str(kv[0]))):
                old_v=rec.get("vnum", rec.get("spawn_vnum"))
                try: old_v_int=int(old_v) if old_v not in (None, "") else None
                except Exception: old_v_int=None
                aid,zid,state,evidence,conflicts=self._infer_area_zone(kind, rec, records)
                valid_range, range_text = self.vnum_ranges.validate_range(kind)
                if not valid_range:
                    state="BLOCKED"; conflicts.append(f"invalid configured range {range_text}")
                if old_v_int is not None and not self.vnum_ranges.in_range(kind, old_v_int):
                    conflicts.append(f"existing VNUM {old_v_int} is outside configured range {range_text}")
                new_v = old_v_int if self.vnum_ranges.in_range(kind, old_v_int) else self.vnum_ranges.first_free(kind, used_by_ns[ns])
                if new_v is None:
                    state="BLOCKED"; conflicts.append(f"exhausted VNUM range {range_text}; occupied {len(used_by_ns[ns])}")
                changes={}
                if old_v_int != new_v: changes["vnum"]=[old_v_int,new_v]
                if str(rec.get("area_id") or "") != aid: changes["area_id"]=[rec.get("area_id"), aid]
                if str(rec.get("zone_id") or "") != zid: changes["zone_id"]=[rec.get("zone_id"), zid]
                if changes:
                    confidence = state if state in {"CONFIRMED","INFERRED","MANUAL_REVIEW","BLOCKED"} else "MANUAL_REVIEW"
                    blocking = confidence in {"MANUAL_REVIEW","BLOCKED"}
                    plan.append({"kind":kind,"id":oid,"name":rec.get("name") or rec.get("title") or oid,"old_vnum":old_v_int,"new_vnum":new_v,"old_area":rec.get("area_id"),"new_area":aid,"old_zone":rec.get("zone_id"),"new_zone":zid,"changes":changes,"reason":"; ".join(evidence) or confidence,"confidence":confidence,"evidence":evidence,"conflicting_evidence":conflicts,"incoming_references":{},"outgoing_references":{},"blocking":blocking,"namespace":ns})
        return plan

    def _plan_hash(self, plan: list[dict[str, Any]]) -> str:
        import hashlib
        stable=[{k:v for k,v in p.items() if k not in {"evidence"}} for p in plan]
        return hashlib.sha256(json.dumps(stable, sort_keys=True, default=str).encode()).hexdigest()

    def _pending_key(self, actor: Any) -> str:
        return f"{getattr(actor,'account_id','')}:{getattr(actor,'id','')}:{getattr(actor,'session_id','')}:{self.workspace.world_id(actor)}"

    def _normalization_snapshot_root(self, world_id: str) -> Path:
        p=self.workspace.ensure(world_id)/"builder"/"normalization_snapshots"; p.mkdir(parents=True, exist_ok=True); return p

    def _snapshot_root(self, world_id: str) -> Path:
        return self._normalization_snapshot_root(world_id)

    def _create_normalization_snapshot(self, actor: Any, plan: list[dict[str, Any]], command: str) -> str:
        world_id=self.workspace.world_id(actor); sid="normalize_"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        root=self._snapshot_root(world_id)/sid; root.mkdir(parents=True, exist_ok=False)
        drafts=self.workspace.load(world_id); files=[]
        for coll, fname in DRAFT_FILES.items():
            if coll in drafts:
                self.workspace._atomic_json_write(root/fname, drafts.get(coll, {})); files.append(fname)
        verify=self._verify_issues(actor)
        manifest={"snapshot_id":sid,"timestamp":datetime.now(timezone.utc).isoformat(),"world_id":world_id,"account_id":str(getattr(actor,'account_id','')),"character_id":str(getattr(actor,'id','')),"command":command,"plan_hash":self._plan_hash(plan),"source_revision_information":{"draft_collections":sorted(drafts)},"files_captured":files,"record_counts":{k:len(v) for k,v in drafts.items() if isinstance(v,dict)},"before_verification_result":{"errors":sum(1 for i in verify if i['blocking']),"issues":verify},"builder_schema_version":"15B.24"}
        self.workspace._atomic_json_write(root/"manifest.json", manifest)
        self.workspace._atomic_json_write(root/"reference_indexes.json", {"plan_ids":[p['id'] for p in plan]})
        self.workspace._atomic_json_write(root/"verification_before.json", manifest["before_verification_result"])
        return sid

    def _build_reference_index(self, actor: Any, *, records_by_collection=None) -> dict[str, Any]:
        records = records_by_collection or self._normalization_records(actor)[0]
        refs=[]
        for sid,s in records.get("spawns",{}).items():
            for key, coll in (("room_id","rooms"),("mobile_id","entities"),("entity_id","entities"),("object_id","items"),("item_id","items")):
                val=str(s.get(key) or "")
                if val: refs.append({"source_collection":"spawns","source_id":sid,"source_field":key,"target_collection":coll,"target_id":val,"reference_type":"spawn_link","world":self.workspace.world_id(actor),"required":True,"metadata":{}})
        return {"references": refs}

    def _verify_issues(self, actor: Any, *, records_by_collection=None, reference_index=None, scope=None) -> list[dict[str, Any]]:
        records=records_by_collection or self._normalization_records(actor)[0]; issues=[]; seen={}
        reference_index = reference_index or self._build_reference_index(actor, records_by_collection=records)
        def issue(code, coll, oid, path, msg, hint="", blocking=True): issues.append({"code":code,"collection":coll,"id":oid,"field_path":path,"message":msg,"fix_hint":hint,"blocking":blocking})
        for coll in ("areas","zones","rooms","entities","items","spawns","resets"):
            ids=set()
            for oid, rec in records.get(coll,{}).items():
                if oid in ids: issue("DUPLICATE_ID",coll,oid,"id","Duplicate canonical ID")
                ids.add(oid)
                if coll in {"rooms","entities","items","spawns","resets"}:
                    raw=rec.get("vnum",rec.get("spawn_vnum"))
                    if not str(raw).isdigit(): issue("MISSING_VNUM",coll,oid,"vnum","Missing numeric VNUM","Run builder normalize plan")
                    else:
                        v=int(raw); ns=self.vnum_ranges.namespace_for(coll); seen.setdefault(ns,{}).setdefault(v,[]).append((coll,oid))
                        if not self.vnum_ranges.in_range(coll,v): issue("OUT_OF_RANGE_VNUM",coll,oid,"vnum",f"VNUM {v} outside configured range {self.vnum_ranges.range_for(coll)}")
                    if not rec.get("area_id"): issue("MISSING_AREA",coll,oid,"area_id","Missing area ownership")
                    if coll != "items" and not rec.get("zone_id"): issue("MISSING_ZONE",coll,oid,"zone_id","Missing zone ownership")
                    zid=str(rec.get("zone_id") or ""); aid=str(rec.get("area_id") or "")
                    if zid and zid not in records.get("zones",{}): issue("BROKEN_ZONE",coll,oid,"zone_id",f"Zone {zid} does not exist")
                    if aid and aid not in records.get("areas",{}): issue("BROKEN_AREA",coll,oid,"area_id",f"Area {aid} does not exist")
                    if zid in records.get("zones",{}) and aid and str(records["zones"][zid].get("area_id") or "") not in {"",aid}: issue("ZONE_AREA_MISMATCH",coll,oid,"zone_id",f"Zone {zid} does not belong to area {aid}")
        for ns, vals in seen.items():
            for v, owners in vals.items():
                if len(owners)>1:
                    for coll,oid in owners: issue("DUPLICATE_VNUM",coll,oid,"vnum",f"VNUM {v} duplicates in namespace {ns}: {owners}")
        for ref in reference_index.get("references", []):
            coll=ref.get("target_collection"); val=str(ref.get("target_id") or "")
            if val and val not in records.get(coll,{}): issue("BROKEN_REFERENCE",str(ref.get("source_collection")),str(ref.get("source_id")),str(ref.get("source_field")),f"Referenced {coll} {val} does not exist")
        return issues

    def normalize_command(self, actor: Any, args: list[str] | None = None) -> BuilderResult:
        args=list(args or ["audit"]); action=args[0].lower(); world_id=self.workspace.world_id(actor)
        if action in {"confirm","confirm_normalize"} or (action=="confirm" and len(args)>1): action="confirm"
        plan=self.normalization_plan(actor); records,drafts=self._normalization_records(actor)
        manual=sum(1 for p in plan if p.get("confidence")=="MANUAL_REVIEW"); blocked=sum(1 for p in plan if p.get("confidence")=="BLOCKED")
        confirmed=sum(1 for p in plan if p.get("confidence")=="CONFIRMED"); inferred=sum(1 for p in plan if p.get("confidence")=="INFERRED")
        issues=self._verify_issues(actor); missing_v=sum(1 for i in issues if i['code']=='MISSING_VNUM'); missing_own=sum(1 for i in issues if i['code'] in {'MISSING_AREA','MISSING_ZONE'}); dups=sum(1 for i in issues if i['code']=='DUPLICATE_VNUM')
        if action == "audit":
            return BuilderResult(True, f"Builder normalization audit\nMissing ownership: {missing_own}\nMissing VNUMs: {missing_v}\nDuplicate VNUM conflicts: {dups}\nPlanned changes: {len(plan)}")
        if action == "plan":
            verbose="verbose" in [a.lower() for a in args[1:]]
            if verbose:
                lines=["Builder normalization plan"]
                for p in plan:
                    lines += ["", f"{p['kind'].upper()}: {p['id']}", "Current:", f"  VNUM: {p['old_vnum'] if p['old_vnum'] is not None else '----'}", f"  Area: {p['old_area'] or '----'}", f"  Zone: {p['old_zone'] or '----'}", "Proposed:", f"  VNUM: {p['new_vnum'] if p['new_vnum'] is not None else '----'}", f"  Area: {p['new_area'] or '----'}", f"  Zone: {p['new_zone'] or '----'}", "Confidence:", f"  {p['confidence']}", "Evidence:"]
                    lines += [f"  - {e}" for e in (p.get('evidence') or ['none'])]
                    lines += ["Conflicting evidence:"] + [f"  - {e}" for e in (p.get('conflicting_evidence') or ['none'])]
                    lines += ["References:", f"  Incoming: {p.get('incoming_references') or {}}", f"  Outgoing: {p.get('outgoing_references') or {}}", f"Reason: {p.get('reason')}", f"Blocking: {p.get('blocking')}"]
                return BuilderResult(True,"\n".join(lines) if len(lines)>1 else "Builder normalization plan\nNo changes required.",{"plan":plan})
            lines=["Builder normalization plan","Type | ID | Old VNUM | New VNUM | Old Area | New Area | Old Zone | New Zone | Confidence | Reason"]
            lines += [f"{p['kind']} | {p['id']} | {p['old_vnum'] if p['old_vnum'] is not None else '----'} | {p['new_vnum'] if p['new_vnum'] is not None else '----'} | {p['old_area'] or ''} | {p['new_area'] or ''} | {p['old_zone'] or ''} | {p['new_zone'] or ''} | {p['confidence']} | {p['reason']}" for p in plan]
            return BuilderResult(True,"\n".join(lines) if len(lines)>2 else "Builder normalization plan\nNo changes required.",{"plan":plan})
        if action == "verify":
            errors=sum(1 for i in issues if i['blocking']); warnings=sum(1 for i in issues if not i['blocking']); info=0
            lines=[f"Builder normalization verification: {'OK' if errors==0 else 'FAILED'}", f"Errors: {errors}", f"Warnings: {warnings}", f"Information: {info}"]
            for i in issues[:200]: lines.append(f"- {i['code']} | {i['collection']} | {i['id']} | {i['field_path']} | {i['message']} | Fix: {i['fix_hint']} | Blocking: {i['blocking']}")
            return BuilderResult(errors==0,"\n".join(lines),{"issues":issues})
        if action == "snapshots":
            root=self._snapshot_root(world_id); snaps=sorted([p.name for p in root.iterdir() if p.is_dir()])
            return BuilderResult(True,"Normalization snapshots\n"+("\n".join(f"- {s}" for s in snaps) if snaps else "- none"),{"snapshots":snaps})
        if action == "snapshot":
            sid=args[1] if len(args)>1 else ""; man=self._snapshot_root(world_id)/sid/"manifest.json"
            if not man.exists(): return BuilderResult(False,f"Normalization snapshot not found: {sid}")
            return BuilderResult(True,"Normalization snapshot\n"+json.dumps(self.workspace._read(man,{}),indent=2,sort_keys=True))
        if action == "rollback":
            if not self._can_admin(actor): return BuilderResult(False,"You do not have permission to apply Builder normalization.")
            root=self._snapshot_root(world_id); sid=args[1] if len(args)>1 else ""
            if not sid:
                dirs=sorted([p.name for p in root.iterdir() if p.is_dir()]); sid=dirs[-1] if dirs else ""
            if not sid: return BuilderResult(False,"No normalization rollback snapshot exists.")
            pend=getattr(self,"_pending_normalize",{})
            key=self._pending_key(actor); token=f"CONFIRM ROLLBACK {sid}"
            if not (pend.get(key,{}).get("type")=="rollback" and pend[key].get("snapshot_id")==sid):
                pend[key]={"type":"rollback","snapshot_id":sid,"expires":time.time()+120}; self._pending_normalize=pend
                return BuilderResult(False,f"Rollback snapshot {sid} is ready.\nType:\n{token}\nto restore, or Q to cancel.")
            snap=root/sid; target=self.workspace.load(world_id)
            for coll,fname in DRAFT_FILES.items():
                fp=snap/fname
                if fp.exists(): target[coll]=self.workspace._read(fp,{})
            self.workspace.save_drafts(world_id,target); pend.pop(key,None)
            return BuilderResult(True,f"Normalization rollback restored snapshot {sid}.")
        if action == "apply":
            if not self._can_admin(actor): return BuilderResult(False,"You do not have permission to apply Builder normalization.")
            if manual or blocked:
                lines=[f"Normalization cannot be applied because {manual} records require manual review and {blocked} records are blocked.","Run `builder normalize plan verbose` to inspect unresolved records."]
                lines += [f"- {p['kind']} {p['id']}: {p['confidence']} {p.get('reason','')}" for p in plan if p.get('confidence') in {'MANUAL_REVIEW','BLOCKED'}]
                return BuilderResult(False,"\n".join(lines))
            sid="normalize_"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ"); h=self._plan_hash(plan); key=self._pending_key(actor); pend=getattr(self,"_pending_normalize",{})
            pend[key]={"type":"apply","count":len(plan),"hash":h,"expires":time.time()+120,"snapshot_id":sid}; self._pending_normalize=pend
            return BuilderResult(False,f"Normalization plan is ready.\n\nRecords to update: {len(plan)}\nConfirmed: {confirmed}\nInferred: {inferred}\nManual review: {manual}\nBlocked: {blocked}\n\nSnapshot to create:\n{sid}\n\nType:\n\nCONFIRM NORMALIZE {len(plan)}\n\nto apply, or Q to cancel.",{"plan_hash":h,"count":len(plan)})
        if action == "confirm":
            key=self._pending_key(actor); pend=getattr(self,"_pending_normalize",{}); pending=pend.get(key)
            if not pending or pending.get("type")!="apply" or pending.get("expires",0)<time.time(): return BuilderResult(False,"No pending Builder normalization confirmation.")
            count = next((int(a) for a in args if str(a).isdigit()), -1)
            if count != int(pending.get('count')): return BuilderResult(False,f"Confirmation count does not match pending plan ({pending.get('count')}).")
            if self._plan_hash(plan) != pending.get("hash"): return BuilderResult(False,"Normalization plan changed after confirmation was requested; rerun builder normalize apply.")
            if manual or blocked: return BuilderResult(False,f"Normalization cannot be applied because {manual} records require manual review and {blocked} records are blocked.\nRun `builder normalize plan verbose` to inspect unresolved records.")
            sid=self._create_normalization_snapshot(actor, plan, "builder normalize apply")
            target=deepcopy(drafts)
            for p in plan:
                bucket=target.setdefault(p['kind'],{}); rec=deepcopy(bucket.get(p['id']) or records[p['kind']].get(p['id']) or {'id':p['id']})
                if p.get('new_vnum') is not None: rec['vnum']=p['new_vnum']
                if p.get('new_area'): rec['area_id']=p['new_area']
                if p.get('new_zone'): rec['zone_id']=p['new_zone']
                rec.setdefault('world_id',world_id); rec['_builder_normalized']=self.workspace.stamp(); bucket[p['id']]=rec
            self.workspace.save_drafts(world_id,target)
            pend.pop(key,None)
            post=self._verify_issues(actor)
            if any(i['blocking'] for i in post):
                self.normalize_command(actor,["rollback",sid]); return BuilderResult(False,f"Post-apply verification failed; restored snapshot {sid}.")
            return BuilderResult(True,f"Normalization apply complete. Snapshot: {sid}. Records changed: {len(plan)}",{"changed":len(plan),"snapshot_id":sid})
        if action == "q":
            getattr(self,"_pending_normalize",{}).pop(self._pending_key(actor),None); return BuilderResult(True,"Normalization confirmation cancelled.")
        return BuilderResult(False,"Usage: builder normalize <audit|plan|apply|verify|snapshots|snapshot|rollback>")

    def render_session(self, sess: BuilderEditSession) -> str:
        rec = sess.working_record or {}
        title = rec.get("name") or sess.object_id.replace("_", " ").title()
        if sess.mode == "field_prompt":
            return self._render_field_prompt(sess)
        if sess.mode == "multiline_text":
            return self._render_multiline(sess)
        if sess.mode == "flag_editor":
            return self._render_flag_editor(sess)
        if sess.mode == "reference_selector":
            return self._render_reference_selector(None, sess)
        if sess.mode == "list_editor":
            return self._render_list_editor(sess)
        if sess.mode == "oedit_values":
            return self._render_oedit_values_editor(sess)
        if sess.editor_type == "oedit" and not sess.section and sess.mode in {"main_menu", "section_menu"}:
            sess.mode = "main_menu"
            return self._render_oedit_menu(sess)
        if sess.editor_type == "redit" and not sess.section and sess.mode in {"main_menu", "section_menu"}:
            sess.mode = "main_menu"
            return self._render_redit_menu(sess)
        if sess.editor_type == "redit" and sess.section == "exit":
            return self._render_exit_editor(None, sess)
        if sess.editor_type != "medit" and sess.section:
            lines = [f"{sess.editor_type.upper()} {sess.object_id} > Fields", f"Draft status: {'modified' if sess.dirty else 'clean'}"]
            for i, f in enumerate(self._field_descriptors(sess), 1):
                lines.append(f"{i}. {f.label:<24}: {self._fmt_value(self._get_path(rec, f.path))}{' (read-only)' if f.read_only else ''}")
            lines += ["", "Q. Back", "V. Validate", "U. Undo", "R. Redo", "S. Save"]
            return "\n".join(lines)
        if sess.section:
            if sess.editor_type == "medit" and sess.section == "identity":
                return medit_render.render_medit_identity(sess)
            if sess.editor_type == "medit" and sess.section in {"attributes", "resources"}:
                return medit_render.render_medit_stats(sess)
            if sess.editor_type == "medit" and sess.section == "mobile_flags":
                sess.active_field = "mobile_flags"; sess.mode = "flag_editor"
                return self._render_flag_editor(sess)
            if sess.editor_type == "medit" and sess.section == "affect_flags":
                sess.active_field = "affect_flags"; sess.mode = "flag_editor"
                return self._render_flag_editor(sess)
            if sess.editor_type == "medit" and sess.section == "equipment":
                return self._render_medit_loadout(actor=None, sess=sess)
            if sess.editor_type == "medit" and sess.section == "scripts":
                return self._render_medit_scripts(actor=None, sess=sess)
            if sess.editor_type == "medit" and sess.section in {"abilities", "combat_abilities"}:
                return self._render_medit_advanced_list(sess, "combat_abilities")
            if sess.editor_type == "medit" and sess.section in {"reactions", "event_reactions", "ai"}:
                return self._render_medit_advanced_list(sess, "event_reactions")
            if sess.editor_type == "medit" and sess.section == "spawns":
                return self._render_spawns_editor(None, sess)
            return self._render_mobile_section(sess, sess.section)
        return self.menu(sess.editor_type, str(title), sess)


    def _room_display_id(self, rec: dict[str, Any], fallback: str) -> str:
        return str(rec.get("vnum") if rec.get("vnum") is not None else rec.get("legacy_vnum") or fallback)

    def _room_zone_summary(self, sess: BuilderEditSession, rec: dict[str, Any]) -> str:
        zid = str(rec.get("zone_id") or "")
        if zid:
            zones = self.workspace.load(sess.world_id).get("zones", {})
            z = zones.get(zid) if isinstance(zones, dict) else None
            return str((z or {}).get("vnum") if isinstance(z, dict) and (z or {}).get("vnum") is not None else zid)
        return "Unassigned"

    def _exit_summary(self, actor: Any | None, sess: BuilderEditSession, direction: str) -> str:
        ex = (sess.working_record.get("exits") or {}).get(direction)
        if not isinstance(ex, dict):
            return "-1"
        target = ex.get("target_room_id") or ex.get("destination_room_id") or ex.get("room_id") or ex.get("to")
        if not target:
            return "-1"
        records = self.resolve_collection_records(actor, "rooms") if actor is not None else self.workspace.load(sess.world_id).get("rooms", {})
        return f"{target}" + (" (invalid)" if str(target) not in records else "")

    def _exit_target(self, ex: Any) -> str:
        return str((ex or {}).get("target_room_id") or (ex or {}).get("destination_room_id") or (ex or {}).get("room_id") or (ex or {}).get("to") or "") if isinstance(ex, dict) else ""

    def _room_by_id_or_vnum(self, actor: Any, token: str) -> tuple[str, dict[str, Any] | None, str]:
        token = str(token or "").strip()
        if not token:
            return "", None, "Room identifier is required."
        records = self.resolve_collection_records(actor, "rooms")
        if token in records:
            return token, records[token], ""
        if token.isdigit():
            matches = [(rid, r) for rid, r in records.items() if str(r.get("vnum") or r.get("legacy_vnum") or "") == token]
            if len(matches) == 1:
                return matches[0][0], matches[0][1], ""
            if len(matches) > 1:
                return "", None, f"Room VNUM {token} is ambiguous; use a canonical room ID."
        return "", None, f"Room not found: {token}"

    def _reverse_status(self, actor: Any, sess: BuilderEditSession, direction: str) -> tuple[str, str]:
        ex = (sess.working_record.get("exits") or {}).get(direction)
        target = self._exit_target(ex)
        if not target:
            return "Destination room unresolved", ""
        rev = REDIT_REVERSE_DIRECTIONS.get(direction)
        if not rev:
            return "Reverse direction unsupported", ""
        records = self.resolve_collection_records(actor, "rooms", scratch=sess.working_record)
        dest = records.get(target)
        if not isinstance(dest, dict):
            return "Destination room unresolved", target
        back = self._exit_target((dest.get("exits") or {}).get(rev))
        if not back:
            return "Missing", target
        if back == sess.object_id:
            return "Correct", target
        return f"Points elsewhere ({back})", target

    def _render_exit_editor(self, actor: Any, sess: BuilderEditSession) -> str:
        direction = sess.active_direction
        ex = (sess.working_record.setdefault("exits", {}) or {}).get(direction) or {}
        target = self._exit_target(ex) or "None"
        desc = ex.get("description") or "Not Set."
        keywords = ex.get("keywords") or []
        if isinstance(keywords, str): keywords = keywords.split()
        flags = ex.get("flags") or []
        status, _target = self._reverse_status(actor, sess, direction)
        rev = REDIT_REVERSE_DIRECTIONS.get(direction, "n/a")
        link_mode = "One-way" if "one_way" in flags or ex.get("one_way") else "Two-way"
        return "\n".join([
            f"-- Exit {direction} for room {sess.object_id}",
            f"1) Destination : {target}",
            f"2) Description : {desc}",
            f"3) Keywords    : {', '.join(map(str, keywords)) if keywords else 'Not Set.'}",
            f"4) Door type   : {str(ex.get('door_type') or 'open_passage').replace('_',' ').title()}",
            f"5) Exit flags  : {', '.join(str(f).upper() for f in flags) if flags else 'NOBITS'}",
            f"6) Key         : {ex.get('key_id') or ex.get('key_item_id') or 'None'}",
            f"7) Reverse     : {rev} -> {sess.object_id}: {status}",
            f"8) Link mode   : {link_mode}",
            "D) Delete Exit",
            "R) Repair Reverse Exit",
            "Q) Back",
            "Enter choice :",
        ])

    def _set_exit_field(self, sess: BuilderEditSession, direction: str, updates: dict[str, Any] | None) -> None:
        self._session_checkpoint(sess)
        exits = deepcopy(sess.working_record.get("exits") or {})
        if updates is None:
            exits.pop(direction, None)
        else:
            ex = dict(exits.get(direction) or {})
            ex.update(updates)
            if not self._exit_target(ex):
                exits.pop(direction, None)
            else:
                exits[direction] = ex
        sess.working_record["exits"] = exits
        sess.dirty = sess.working_record != sess.savepoint; sess.saved = not sess.dirty

    def _handle_exit_editor(self, actor: Any, sess: BuilderEditSession, text: str, low: str) -> BuilderResult:
        direction = sess.active_direction
        if low in {"q", "quit", "back"}:
            sess.section = ""; sess.mode = "main_menu"; sess.active_field = ""; sess.confirmation_type = ""; sess.pending_value = None
            return BuilderResult(True, self._render_redit_menu(sess))
        if sess.confirmation_type == "exit_destination":
            if low in {"q","quit","cancel","back"}:
                sess.confirmation_type = ""; return BuilderResult(True, "Destination edit cancelled.\n" + self._render_exit_editor(actor, sess))
            if low in {"clear","none","-1"}:
                self._set_exit_field(sess, direction, None); sess.confirmation_type = ""
                return BuilderResult(True, "Exit destination cleared.\n" + self._render_exit_editor(actor, sess))
            rid, _room, err = self._room_by_id_or_vnum(actor, text)
            if err:
                return BuilderResult(False, err + "\nEnter a room ID/VNUM, clear, or Q.")
            if str((_room or {}).get("world_id") or sess.world_id) != sess.world_id:
                return BuilderResult(False, "Cross-world exits are not supported by this Builder.")
            self._set_exit_field(sess, direction, {"target_room_id": rid}); sess.confirmation_type = ""
            status, _ = self._reverse_status(actor, sess, direction)
            return BuilderResult(True, f"Exit destination changed. Reverse status: {status}\n" + self._render_exit_editor(actor, sess))
        if sess.confirmation_type == "exit_keywords":
            if low in {"q","quit","cancel","back"}:
                sess.confirmation_type = ""; return BuilderResult(True, "Keyword edit cancelled.\n" + self._render_exit_editor(actor, sess))
            words = [] if low in {"clear","none"} else [w for w in re.split(r"\s+", text.strip()) if w]
            self._set_exit_field(sess, direction, {"keywords": words}); sess.confirmation_type = ""
            return BuilderResult(True, "Exit keywords changed.\n" + self._render_exit_editor(actor, sess))
        if sess.confirmation_type == "exit_door":
            if low in {"q","quit","cancel","back"}:
                sess.confirmation_type = ""; return BuilderResult(True, "Door type edit cancelled.\n" + self._render_exit_editor(actor, sess))
            choice = REDIT_DOOR_TYPES[int(low)-1] if low.isdigit() and 1 <= int(low) <= len(REDIT_DOOR_TYPES) else low.replace(" ", "_")
            if choice not in REDIT_DOOR_TYPES:
                return BuilderResult(False, "Choose a supported door type: " + ", ".join(REDIT_DOOR_TYPES))
            self._set_exit_field(sess, direction, {"door_type": choice}); sess.confirmation_type = ""
            return BuilderResult(True, "Door type changed.\n" + self._render_exit_editor(actor, sess))
        if sess.confirmation_type == "exit_flags":
            if low in {"q","quit","cancel","back"}:
                sess.confirmation_type = ""; return BuilderResult(True, self._render_exit_editor(actor, sess))
            ex = (sess.working_record.get("exits") or {}).get(direction) or {}
            cur = set(ex.get("flags") or [])
            if low in {"clear","none"}: cur = set()
            elif low.isdigit() and 1 <= int(low) <= len(REDIT_EXIT_FLAGS):
                flag = REDIT_EXIT_FLAGS[int(low)-1]; (cur.remove if flag in cur else cur.add)(flag)
            elif low in REDIT_EXIT_FLAGS:
                (cur.remove if low in cur else cur.add)(low)
            else:
                return BuilderResult(False, "Choose a flag number, clear, or Q.")
            self._set_exit_field(sess, direction, {"flags": sorted(cur)})
            return BuilderResult(True, "Exit flags changed.\n" + self._render_exit_editor(actor, sess))
        if sess.confirmation_type == "exit_key":
            if low in {"q","quit","cancel","back"}:
                sess.confirmation_type = ""; return BuilderResult(True, "Key edit cancelled.\n" + self._render_exit_editor(actor, sess))
            val = "" if low in {"clear","none"} else text.strip()
            if val and val not in self.resolve_collection_records(actor, "items"):
                return BuilderResult(False, f"Object/key not found: {val}")
            self._set_exit_field(sess, direction, {"key_id": val or None}); sess.confirmation_type = ""
            return BuilderResult(True, "Exit key changed.\n" + self._render_exit_editor(actor, sess))
        if sess.confirmation_type == "exit_delete":
            if low in {"q","quit","cancel","back"}:
                sess.confirmation_type = ""; return BuilderResult(True, "Delete exit cancelled.\n" + self._render_exit_editor(actor, sess))
            if low not in {"one-way","oneway","current","both","two-way","twoway"}:
                return BuilderResult(False, "Type current for one-way deletion, both for two-way deletion, or Q.")
            self._set_exit_field(sess, direction, None); sess.confirmation_type = ""
            return BuilderResult(True, "Exit deleted from current room draft. Two-way deletion is available through UNDIG for saved drafts.\n" + self._render_redit_menu(sess))
        if sess.confirmation_type == "exit_repair":
            if low in {"q","quit","cancel","back"}:
                sess.confirmation_type = ""; return BuilderResult(True, "Reverse repair cancelled.\n" + self._render_exit_editor(actor, sess))
            if low not in {"repair","confirm","yes","y"}:
                return BuilderResult(False, "Type REPAIR to create/replace the reverse exit, or Q.")
            target = self._exit_target((sess.working_record.get("exits") or {}).get(direction)); rev = REDIT_REVERSE_DIRECTIONS.get(direction)
            if not target or not rev:
                return BuilderResult(False, "Cannot repair without a valid destination and reverse direction.")
            res = self.link_rooms(actor, target, rev, sess.object_id, one_way=True, require_existing_target=True, allow_overwrite=True, action="redit repair reverse")
            sess.confirmation_type = ""
            return BuilderResult(res.ok, res.message + "\n" + self._render_exit_editor(actor, sess), res.data)
        if low == "1":
            sess.confirmation_type = "exit_destination"; return BuilderResult(True, "Enter destination room ID/VNUM, clear, or Q.")
        if low == "2":
            sess.mode = "multiline_text"; sess.active_field = f"exit:{direction}:description"; sess.multiline_lines = []
            return BuilderResult(True, "Multiline text editor for exit description. Use .save or .cancel.")
        if low == "3":
            sess.confirmation_type = "exit_keywords"; return BuilderResult(True, "Enter space-separated exit keywords, clear, or Q.")
        if low == "4":
            sess.confirmation_type = "exit_door"; return BuilderResult(True, "Door types:\n" + "\n".join(f"{i}) {v.replace('_',' ').title()}" for i,v in enumerate(REDIT_DOOR_TYPES,1)))
        if low == "5":
            sess.confirmation_type = "exit_flags"; return BuilderResult(True, "Exit flags:\n" + "\n".join(f"{i}) {v}" for i,v in enumerate(REDIT_EXIT_FLAGS,1)))
        if low == "6":
            sess.confirmation_type = "exit_key"; return BuilderResult(True, "Enter key object ID, clear, or Q.")
        if low == "7":
            status, _ = self._reverse_status(actor, sess, direction); return BuilderResult(True, f"Reverse status: {status}\n" + self._render_exit_editor(actor, sess))
        if low == "8":
            ex = (sess.working_record.get("exits") or {}).get(direction) or {}; flags = set(ex.get("flags") or [])
            if "one_way" in flags: flags.remove("one_way"); msg = "Link mode set to Two-way."
            else: flags.add("one_way"); msg = "Link mode set to One-way."
            self._set_exit_field(sess, direction, {"flags": sorted(flags)})
            return BuilderResult(True, msg + "\n" + self._render_exit_editor(actor, sess))
        if low == "d":
            sess.confirmation_type = "exit_delete"; return BuilderResult(True, "Delete exit: type current for one-way deletion, both for two-way deletion, or Q.")
        if low == "r":
            status, target = self._reverse_status(actor, sess, direction); rev = REDIT_REVERSE_DIRECTIONS.get(direction, "")
            sess.confirmation_type = "exit_repair"
            return BuilderResult(True, f"Repair reverse exit?\nSource room: {sess.object_id}\nSource direction: {direction}\nDestination room: {target or 'unresolved'}\nExpected reverse direction: {rev}\nCurrent reverse destination: {status}\nWhat will change: {target} {rev} -> {sess.object_id}\nType REPAIR to confirm, or Q.")
        return BuilderResult(False, "Choose an exit menu option.\n" + self._render_exit_editor(actor, sess))

    def link_rooms(self, actor: Any, source_id: str, direction: str, target_id: str, *, one_way: bool = False, require_existing_target: bool = True, allow_overwrite: bool = False, action: str = "builder link") -> BuilderResult:
        if direction not in REDIT_DIRECTIONS:
            return BuilderResult(False, f"Unsupported direction: {direction}")
        records = self.resolve_collection_records(actor, "rooms")
        if source_id not in records:
            return BuilderResult(False, f"Source room not found: {source_id}")
        if require_existing_target and target_id not in records:
            return BuilderResult(False, f"Target room not found: {target_id}")
        denied = self._check_permission(actor, "rooms", source_id, "mutate") or self._check_permission(actor, "rooms", target_id, "mutate")
        if denied: return denied
        rev = REDIT_REVERSE_DIRECTIONS.get(direction, "")
        world_id = self.workspace.world_id(actor); drafts = self.workspace.load(world_id); rooms = drafts.setdefault("rooms", {})
        before_source = deepcopy(rooms.get(source_id) or records.get(source_id) or {"id": source_id})
        before_target = deepcopy(rooms.get(target_id) or records.get(target_id) or {"id": target_id})
        src_ex = (before_source.get("exits") or {}).get(direction)
        if src_ex and self._exit_target(src_ex) not in {"", target_id} and not allow_overwrite:
            return BuilderResult(False, f"Source exit {source_id} {direction} already points to {self._exit_target(src_ex)}.")
        if not one_way and rev:
            rev_ex = (before_target.get("exits") or {}).get(rev)
            if rev_ex and self._exit_target(rev_ex) not in {"", source_id} and not allow_overwrite:
                return BuilderResult(False, f"Reverse exit {target_id} {rev} already points to {self._exit_target(rev_ex)}.")
        after_source = deepcopy(before_source); after_target = deepcopy(before_target)
        after_source.setdefault("exits", {})[direction] = {"target_room_id": target_id}
        if not one_way and rev:
            after_target.setdefault("exits", {})[rev] = {"target_room_id": source_id}
        rooms[source_id] = after_source; rooms[target_id] = after_target
        self.workspace.save_drafts(world_id, drafts)
        self._push_history(actor, "rooms", source_id, before_source, after_source, action)
        if target_id != source_id:
            self._push_history(actor, "rooms", target_id, before_target, after_target, action)
        self.workspace.audit(actor, world_id, action, "rooms", f"{source_id}:{direction}", {"source": before_source, "target": before_target}, {"source": after_source, "target": after_target})
        lines = ["Created two-way link:" if not one_way else "Created one-way link:", f"  {source_id} {direction} -> {target_id}"]
        if not one_way and rev: lines.append(f"  {target_id} {rev} -> {source_id}")
        return BuilderResult(True, "\n".join(lines), {"source": after_source, "target": after_target})

    def _render_redit_menu(self, sess: BuilderEditSession) -> str:
        rec = sess.working_record or {}
        flags = ", ".join(str(f).upper() for f in (rec.get("flags") or [])) or "None"
        sector = str(rec.get("sector") or rec.get("sector_type") or "inside")
        lines = ["Currently editing:", f"Room: {sess.object_id}", f"Name: {rec.get('name') or ''}", "Source: draft", f"Dirty: {'yes' if sess.dirty else 'no'}", f"-- Room number: [{self._room_display_id(rec, sess.object_id)}] Room zone: [{self._room_zone_summary(sess, rec)}]", f"Room ID      : {sess.object_id}", f"Draft status : {'modified' if sess.dirty else 'clean'}", ""]
        lines.append(f"1) Name        : {rec.get('name') or ''}")
        lines.append("2) Description :")
        desc = str(rec.get("description") or "")
        lines.extend(["   " + line for line in (desc.splitlines() or [""])])
        lines.append(f"3) Room flags  : {flags}")
        lines.append(f"4) Sector type : {sector.replace('_',' ').title()}")
        keys = ["5", "6", "7", "8", "9", "A"]
        for key, direction in zip(keys, REDIT_DIRECTIONS):
            lines.append(f"{key}) Exit {direction:<5}: {self._exit_summary(None, sess, direction)}")
        scripts = rec.get("scripts") or rec.get("script_ids") or rec.get("script")
        script_summary = (", ".join(map(str, scripts)) if isinstance(scripts, list) else str(scripts)) if scripts else "Not Set."
        lines += ["F) Extra descriptions menu", "R) Room Resets", f"S) Script      : {script_summary}", "W) Copy Room", "X) Delete Room", "Q) Quit", "Enter choice :"]
        return "\n".join(lines)

    def _render_oedit_menu(self, sess: BuilderEditSession) -> str:
        rec = normalize_object_template(sess.object_id, sess.working_record or {})
        item_type = str(rec.get("item_type") or rec.get("type") or "misc").lower()
        def yn(values): return ", ".join(map(str, values or [])) or "none"
        def desc_count(): return len(rec.get("extra_descriptions") or [])
        def apply_count(): return len(rec.get("affects") or rec.get("applies") or [])
        lines = ["Object Editor", f"-- Item number : [{rec.get('vnum', sess.object_id)}]", f"Object ID     : {sess.object_id}", f"Draft status  : {'modified' if sess.dirty else 'clean'}", ""]
        rows = [
            ("1", "Keywords", yn(rec.get("keywords"))),
            ("2", "S-Desc", rec.get("short_description") or rec.get("name") or ""),
            ("3", "L-Desc", rec.get("long_description") or ""),
            ("4", "A-Desc", rec.get("look_description") or rec.get("action_description") or ""),
            ("5", "Type", item_type),
            ("6", "Extra flags", yn(rec.get("extra_flags"))),
            ("7", "Wear flags", yn(rec.get("wear_flags"))),
            ("8", "Weight", rec.get("weight", 0)),
            ("9", "Cost", rec.get("cost", 0)),
            ("A", "Cost/Day", rec.get("cost_per_day", rec.get("rent", 0))),
            ("B", "Timer", rec.get("destroy_timer", rec.get("timer", 0))),
            ("C", "Values", self._oedit_values_summary(rec)),
            ("D", "Applies menu", f"{apply_count()} applies"),
            ("E", "Extra descriptions menu", f"{desc_count()} descriptions"),
            ("M", "Min Level", rec.get("min_level", 0)),
            ("P", "Perm Affects", yn(rec.get("perm_affects"))),
            ("S", "Script", yn(rec.get("scripts")) if rec.get("scripts") else "unsupported by runtime"),
            ("W", "Copy object", "choose destination"),
            ("X", "Delete object", "dependency-protected"),
            ("Q", "Quit", "save/discard/abort"),
        ]
        lines += [f"{k}) {label:<28}: {value}" for k, label, value in rows]
        lines += ["", "V) Validate   R) Preview   U) Undo   Y) Redo   H) Help", "Enter choice:"]
        return "\n".join(lines)

    def _oedit_values_summary(self, rec: dict[str, Any]) -> str:
        typ = str(rec.get("item_type") or rec.get("type") or "misc").lower()
        keys = {
            "weapon": ("weapon_type", "damage_dice", "attack_type"), "armor": ("armor_values", "resistances"),
            "container": ("weight_capacity", "container_flags", "key_id"), "light": ("brightness", "burn_time"),
            "food": ("nutrition", "poison", "decay"), "drink_container": ("liquid_type", "servings", "poison"),
            "fountain": ("liquid_type", "servings", "poison"), "wand": ("spell_storage", "charges"),
            "staff": ("spell_storage", "charges"), "scroll": ("spell_storage",), "potion": ("spell_storage",),
            "money": ("currency", "amount"), "furniture": ("capacity",), "key": ("key_id",), "boat": ("capacity",),
        }.get(typ, ("subtype", "category"))
        vals = [f"{k}={self._fmt_value(rec.get(k))}" for k in keys if rec.get(k) not in (None, "", [], {})]
        return "; ".join(vals) if vals else f"{typ} defaults"

    def _oedit_value_descriptors(self, sess: BuilderEditSession) -> list[OlcFieldDescriptor]:
        rec = sess.working_record or {}
        typ = str(rec.get("item_type") or rec.get("type") or "misc").lower()
        maps: dict[str, list[OlcFieldDescriptor]] = {
            "weapon": [
                OlcFieldDescriptor("weapon_type", "Weapon type", ("weapon_type",), "string"),
                OlcFieldDescriptor("damage_dice", "Damage dice", ("damage_dice",), "string"),
                OlcFieldDescriptor("attack_type", "Attack type", ("attack_type",), "string"),
                OlcFieldDescriptor("range", "Range", ("range",), "integer", minimum=0, maximum=1000),
            ],
            "armor": [
                OlcFieldDescriptor("armor_values", "Armor value", ("armor_values",), "integer", minimum=0, maximum=100000),
                OlcFieldDescriptor("resistances", "Resistances", ("resistances",), "string_list"),
            ],
            "container": [
                OlcFieldDescriptor("capacity", "Capacity", ("capacity",), "integer", minimum=0, maximum=1000000),
                OlcFieldDescriptor("weight_capacity", "Weight capacity", ("weight_capacity",), "integer", minimum=0, maximum=1000000),
                OlcFieldDescriptor("container_flags", "Container flags", ("container_flags",), "string_list"),
                OlcFieldDescriptor("key_id", "Key object ID", ("key_id",), "string"),
                OlcFieldDescriptor("lock_difficulty", "Lock difficulty", ("lock_difficulty",), "integer", minimum=0, maximum=1000),
            ],
            "light": [
                OlcFieldDescriptor("brightness", "Brightness", ("brightness",), "integer", minimum=0, maximum=1000),
                OlcFieldDescriptor("burn_time", "Burn time", ("burn_time",), "integer", minimum=0, maximum=1000000),
                OlcFieldDescriptor("fuel", "Fuel", ("fuel",), "integer", minimum=0, maximum=1000000),
            ],
            "food": [
                OlcFieldDescriptor("nutrition", "Nutrition", ("nutrition",), "integer", minimum=0, maximum=1000000),
                OlcFieldDescriptor("poison", "Poisoned", ("poison",), "boolean"),
                OlcFieldDescriptor("decay", "Decay timer", ("decay",), "integer", minimum=0, maximum=1000000),
            ],
            "drink_container": [
                OlcFieldDescriptor("liquid_type", "Liquid type", ("liquid_type",), "string"),
                OlcFieldDescriptor("servings", "Servings", ("servings",), "integer", minimum=0, maximum=1000000),
                OlcFieldDescriptor("poison", "Poisoned", ("poison",), "boolean"),
            ],
            "fountain": [
                OlcFieldDescriptor("liquid_type", "Liquid type", ("liquid_type",), "string"),
                OlcFieldDescriptor("servings", "Servings", ("servings",), "integer", minimum=0, maximum=1000000),
                OlcFieldDescriptor("poison", "Poisoned", ("poison",), "boolean"),
            ],
            "wand": [
                OlcFieldDescriptor("spell_storage", "Stored spells", ("spell_storage",), "string_list"),
                OlcFieldDescriptor("charges", "Charges", ("charges",), "integer", minimum=0, maximum=1000000),
            ],
            "staff": [
                OlcFieldDescriptor("spell_storage", "Stored spells", ("spell_storage",), "string_list"),
                OlcFieldDescriptor("charges", "Charges", ("charges",), "integer", minimum=0, maximum=1000000),
            ],
            "scroll": [OlcFieldDescriptor("spell_storage", "Stored spells", ("spell_storage",), "string_list")],
            "potion": [OlcFieldDescriptor("spell_storage", "Stored spells", ("spell_storage",), "string_list")],
            "money": [
                OlcFieldDescriptor("currency", "Currency", ("currency",), "string"),
                OlcFieldDescriptor("amount", "Amount", ("amount",), "integer", minimum=0, maximum=1000000000),
            ],
        }
        return maps.get(typ, [
            OlcFieldDescriptor("subtype", "Subtype", ("subtype",), "string"),
            OlcFieldDescriptor("category", "Category", ("category",), "string"),
        ])

    def _render_oedit_values_editor(self, sess: BuilderEditSession) -> str:
        rec = sess.working_record or {}
        typ = str(rec.get("item_type") or rec.get("type") or "misc").lower()
        lines = [f"OEDIT Values: {typ}", f"Draft status: {'modified' if sess.dirty else 'clean'}"]
        for i, f in enumerate(self._oedit_value_descriptors(sess), 1):
            lines.append(f"{i}. {f.label:<18}: {self._fmt_value(self._get_path(rec, f.path))}")
        lines += ["", "Q. Back", "Commands: number edits a value, validate, preview, undo, redo, save"]
        return "\n".join(lines)


    def _resource_max(self, rec: dict[str, Any], name: str) -> Any:
        val = (rec.get("resources") or {}).get(name)
        return (val or {}).get("maximum") if isinstance(val, dict) else val

    def _render_stats_menu(self, sess: BuilderEditSession) -> str:
        rec = MobileTemplate.from_legacy(sess.working_record).to_canonical_dict()
        recs = MobileRecommendationService().recommend(level=rec.get("level", 1), archetype=str(rec.get("archetype") or "standard creature"), attack_style=str((rec.get("combat_profile") or {}).get("attack_type") or "hit"))
        vals = recs["values"]; cp = rec.get("combat_profile") or {}; rcp = vals["combat_profile"]
        lines=[f"MEDIT Stats Menu / Attributes / Resources: {rec.get('name') or sess.object_id}", f"Recommendation source: {recs['version']}", f"Draft status: {'modified' if sess.dirty else 'clean'}", "", "Editable stats with authored/recommended/resolved values:"]
        rows=[("1", "Level", rec.get("level",1), vals["level"]), ("2", "Archetype", rec.get("archetype") or "unset", vals["archetype"])]
        for i,a in enumerate(("strength","dexterity","constitution","intelligence","wisdom","charisma"),3): rows.append((str(i), a.title(), (rec.get("attributes") or {}).get(a), vals["attributes"][a]))
        rows += [("9","Health", self._resource_max(rec,"health"), vals["resources"]["health"]["maximum"]),("10","Mana", self._resource_max(rec,"mana"), vals["resources"]["mana"]["maximum"]),("11","Movement/stamina", self._resource_max(rec,"stamina") or self._resource_max(rec,"movement"), vals["resources"]["stamina"]["maximum"]),("12","Armor/defense", cp.get("armor") or cp.get("defense"), rcp["armor"]),("13","Accuracy/hitroll", cp.get("accuracy") or cp.get("hitroll"), rcp["accuracy"]),("14","Damage bonus/damroll", cp.get("damage_bonus") or cp.get("damroll"), rcp["damage_bonus"]),("15","Base damage dice", cp.get("damage_dice"), rcp["damage_dice"]),("16","Attack type", cp.get("attack_type") or rec.get("attack_type") or "hit", rcp["attack_type"]),("17","Attacks per round", cp.get("attacks_per_round"), rcp["attacks_per_round"]),("18","Experience reward", cp.get("experience_reward"), rcp["experience_reward"]),("19","Currency reward", cp.get("gold_reward"), rcp["gold_reward"])]
        for num,label,auth,recval in rows:
            resolved = auth if auth not in (None, "", {}, []) else recval
            lines.append(f"{num}. {label}: Authored override: {self._fmt_value(auth)} | Recommended: {recval} | Resolved runtime value: {resolved}")
        lines += ["", "Commands: number/name edits, clear <field>, quickbuild <level> [archetype], quickdiff, applyquick all|<fields>, validate, preview, undo, redo, back", "Quick Build choices: archetypes=" + ", ".join(MEDIT_ARCHETYPES)]
        return "\n".join(lines)

    def _handle_stats_menu(self, actor: Any, sess: BuilderEditSession, text: str, low: str) -> BuilderResult | None:
        if sess.editor_type != "medit" or sess.section not in {"attributes","resources"}: return None
        parts=text.split(); cmd=parts[0].lower() if parts else ""
        stat_map={"1":"level","level":"level","2":"archetype","archetype":"archetype","3":"strength","strength":"strength","4":"dexterity","dexterity":"dexterity","5":"constitution","constitution":"constitution","6":"intelligence","intelligence":"intelligence","7":"wisdom","wisdom":"wisdom","8":"charisma","charisma":"charisma","9":"health","health":"health","10":"mana","mana":"mana","11":"stamina","movement":"stamina","stamina":"stamina","12":"armor","armor":"armor","defense":"armor","13":"accuracy","accuracy":"accuracy","hitroll":"accuracy","14":"damage_bonus","damage_bonus":"damage_bonus","damroll":"damage_bonus","15":"damage_dice","damage_dice":"damage_dice","dice":"damage_dice","16":"attack_type","attack_type":"attack_type","17":"attacks_per_round","attacks_per_round":"attacks_per_round","18":"experience_reward","experience_reward":"experience_reward","xp":"experience_reward","19":"gold_reward","currency":"gold_reward","gold_reward":"gold_reward"}
        if sess.active_field.startswith("stats:") and cmd and cmd not in {"quickbuild","quickdiff","applyquick","clear"}:
            field=sess.active_field.split(":",1)[1]; text = field + " " + text; parts=text.split(); cmd=field; sess.active_field=""
        if cmd in {"quickbuild","quickdiff"}:
            lvl=int(parts[1]) if len(parts)>1 and parts[1].isdigit() else int(sess.working_record.get("level") or 1); arche=" ".join(parts[2:]) if len(parts)>2 else str(sess.working_record.get("archetype") or "standard creature")
            recs=MobileRecommendationService().recommend(level=lvl, archetype=arche); sess.pending_value={"quickbuild":recs}; diff=MobileRecommendationService().diff(sess.working_record,recs)
            body="Quick Build recommendations (no mutation yet):\n"+"\n".join(f"- {k}: {v['before']} -> {v['after']}" for k,v in diff.items())+"\nApply with: applyquick all or applyquick field1 field2"
            return BuilderResult(True, body, {"diff":diff})
        if cmd == "applyquick":
            recs=((sess.pending_value or {}).get("quickbuild") if isinstance(sess.pending_value,dict) else None) or MobileRecommendationService().recommend(level=sess.working_record.get("level",1))
            fields=set(parts[1:]) if len(parts)>1 and parts[1].lower()!="all" else {"all"}; vals=recs["values"]; self._session_checkpoint(sess); rec=sess.working_record
            def wants(name): return "all" in fields or name in fields
            for k,v in vals.items():
                if k=="attributes" and wants(k): rec.setdefault("attributes",{}).update(v)
                elif k=="resources" and wants(k): rec.setdefault("resources",{}).update(v)
                elif k=="combat_profile" and wants(k): rec.setdefault("combat_profile",{}).update(v)
                elif wants(k): rec[k]=v
            sess.working_record=self._normalize_entity_updates(sess.object_id, rec); sess.dirty=True; sess.saved=False
            return BuilderResult(True, "Quick Build applied as one undo checkpoint.\n"+self._render_stats_menu(sess), sess.working_record)
        if cmd == "clear" and len(parts)>1: field=stat_map.get(parts[1].lower())
        else: field=stat_map.get(cmd)
        if field and (cmd == "clear" or len(parts)>1):
            value=None if cmd=="clear" else " ".join(parts[1:])
            self._session_checkpoint(sess); rec=sess.working_record
            if field in {"strength","dexterity","constitution","intelligence","wisdom","charisma"}:
                if value is None: rec.setdefault("attributes",{}).pop(field,None)
                else: rec.setdefault("attributes",{})[field]=int(value)
            elif field in {"health","mana","stamina"}:
                if value is None: rec.setdefault("resources",{}).pop(field,None)
                else: rec.setdefault("resources",{})[field]={"maximum":int(value),"starting":int(value),"enabled":int(value)>0}
            elif field in {"armor","accuracy","damage_bonus","attacks_per_round","experience_reward","gold_reward"}:
                if value is None: rec.setdefault("combat_profile",{}).pop(field,None)
                else: rec.setdefault("combat_profile",{})[field]=int(value)
            elif field in {"damage_dice","attack_type"}:
                if value is None: rec.setdefault("combat_profile",{}).pop(field,None)
                else: rec.setdefault("combat_profile",{})[field]=value
            else:
                if value is None: rec.pop(field,None)
                else: rec[field]=int(value) if field=="level" and str(value).isdigit() else value
            sess.working_record=self._normalize_entity_updates(sess.object_id, rec); sess.dirty=True; sess.saved=False
            return BuilderResult(True, (("Health maximum changed. Stats value updated" if field == "health" else ("Level changed. Stats value updated" if field == "level" else "Stats value updated")) + ".\n")+self._render_stats_menu(sess), sess.working_record)
        if field:
            sess.active_field="stats:"+field
            label = "health maximum" if field == "health" else field.replace("_", " ")
            return BuilderResult(True, f"Current {label}: {self._fmt_value(self._resource_max(sess.working_record, field) if field in {'health','mana','stamina'} else ((sess.working_record.get('combat_profile') or {}).get(field) if field not in {'level','archetype','strength','dexterity','constitution','intelligence','wisdom','charisma'} else (sess.working_record.get(field) if field in {'level','archetype'} else (sess.working_record.get('attributes') or {}).get(field))))}\nEnter new {label}, or Q to cancel. Use clear {field} to restore inherited/default behavior.")
        return None

    def _field_descriptors(self, sess: BuilderEditSession) -> list[OlcFieldDescriptor]:
        if sess.editor_type == "medit":
            attrs = ("strength","dexterity","constitution","intelligence","wisdom","charisma")
            if sess.section == "identity":
                return [OlcFieldDescriptor("name","Display name",("name",),"string",required=True), OlcFieldDescriptor("id","Stable mobile ID",("id",),"slug",read_only=True), OlcFieldDescriptor("vnum","Legacy VNUM",("vnum",),"integer",minimum=1,maximum=999999), OlcFieldDescriptor("entity_type","Entity type",("entity_type",),"enum",choices=tuple(sorted(VALID_ENTITY_TYPES))), OlcFieldDescriptor("sex","Sex/gender presentation",("sex",),"enum",choices=MEDIT_SEX_VALUES), OlcFieldDescriptor("species","Species/race reference",("species",),"string"), OlcFieldDescriptor("classification","Creature classification",("classification",),"string"), OlcFieldDescriptor("size","Size",("size",),"enum",choices=MEDIT_SIZE_VALUES), OlcFieldDescriptor("enabled","Enabled",("enabled",),"boolean"), OlcFieldDescriptor("tags","Builder tags",("tags",),"string_list")]
            if sess.section == "keywords":
                return [OlcFieldDescriptor("keywords","Keywords",("keywords",),"string_list",required=True)]
            if sess.section == "descriptions":
                return [OlcFieldDescriptor("room_description","Room-visible description",("room_description",),"multiline"), OlcFieldDescriptor("look_description","Detailed look description",("look_description",),"multiline"), OlcFieldDescriptor("short_description","Short description",("short_description",),"string")]
            if sess.section == "traits":
                return [OlcFieldDescriptor("species","Species",("species",),"string"), OlcFieldDescriptor("race","Race",("race",),"string"), OlcFieldDescriptor("body_profile_id","Body profile",("body_profile_id",),"reference",reference_collection="body_profiles"), OlcFieldDescriptor("natural_attack_profile_id","Natural attack profile",("natural_attack_profile_id",),"reference",reference_collection="natural_weapon_profiles"), OlcFieldDescriptor("behavior_profile_id","Behavior archetype",("behavior_profile_id",),"reference",reference_collection="combat_behavior_profiles"), OlcFieldDescriptor("faction_id","Faction",("faction_id",),"reference",reference_collection="faction_definitions"), OlcFieldDescriptor("loot_profile_id","Loot profile",("loot_profile_id",),"string"), OlcFieldDescriptor("sex","Sex/gender",("sex",),"enum",choices=MEDIT_SEX_VALUES), OlcFieldDescriptor("size","Size",("size",),"enum",choices=MEDIT_SIZE_VALUES), OlcFieldDescriptor("alignment","Alignment",("alignment",),"string")]
            if sess.section in {"attributes","resources"}:
                return [OlcFieldDescriptor("level","Level",("level",),"integer",minimum=1,maximum=100)] + [OlcFieldDescriptor(a,a.title(),("attributes",a),"integer",minimum=1,maximum=100) for a in attrs] + [OlcFieldDescriptor("health","Health maximum",("resources","health","maximum"),"integer",minimum=1,maximum=100000), OlcFieldDescriptor("mana","Mana maximum",("resources","mana","maximum"),"integer",minimum=0,maximum=100000), OlcFieldDescriptor("stamina","Stamina maximum",("resources","stamina","maximum"),"integer",minimum=0,maximum=100000), OlcFieldDescriptor("movement","Movement maximum",("resources","movement","maximum"),"integer",minimum=0,maximum=100000)]
            if sess.section == "body_weapons":
                return [OlcFieldDescriptor("body_profile_id","Body profile",("body_profile_id",),"reference",reference_collection="body_profiles",required=True)]
            if sess.section == "mobile_flags":
                return [OlcFieldDescriptor("mobile_flags","Mobile Flags",("mobile_flags",),"flag_set",flags=MEDIT_MOBILE_FLAGS)]
            if sess.section == "affect_flags":
                return [OlcFieldDescriptor("affect_flags","Affect/status Flags",("affect_flags",),"flag_set",flags=MEDIT_AFFECT_FLAGS)]
            if sess.section in {"combat","positions","equipment","inventory","loot","abilities","ai","faction","scripts"}:
                fields = {
                    "combat": ("combat_profile_id","armor","defense","accuracy","hitroll","damage_bonus","damroll","damage_dice","attack_type","attack_verb","attacks_per_round","experience_reward","gold_reward","combat_behavior_profile_id","threat_profile_id","ability_loadout_id"),
                    "positions": ("default_position","spawn_position"),
                    "equipment": ("equipment_loadout",),
                    "inventory": ("starting_inventory",),
                    "loot": ("loot_table_id","corpse_profile_id"),
                    "abilities": ("granted_abilities","spell_loadout"),
                    "ai": ("behavior_profile_id","personality_profile_id","schedule_id"),
                    "faction": ("faction_id","relationship_seed_ids"),
                    "scripts": ("script_ids",),
                }[sess.section]
                descriptors = []
                for f in fields:
                    input_type = "string_list" if f.endswith("ids") or f in {"granted_abilities","spell_loadout","starting_inventory"} else "string"
                    if sess.section == "positions": input_type = "enum"
                    if f in {"armor","defense","accuracy","hitroll","damage_bonus","damroll","attacks_per_round","experience_reward","gold_reward"}: input_type = "integer"
                    if f == "attack_type": input_type = "enum"
                    choices = MEDIT_POSITIONS if sess.section == "positions" else (MEDIT_ATTACK_TYPES if f == "attack_type" else ())
                    descriptors.append(OlcFieldDescriptor(f, f.replace("_"," ").title(), tuple(("combat_profile", f) if sess.section == "combat" else (f,)), input_type, minimum=0 if input_type == "integer" else None, maximum=100000 if input_type == "integer" else None, choices=choices))
                if sess.section == "loot":
                    descriptors += [OlcFieldDescriptor("pet_price","Pet price",("pet_price",),"integer",minimum=0,maximum=100000000), OlcFieldDescriptor("currency","Currency",("economy","currency"),"string")]
                return descriptors
        # Shared minimal descriptors for OEDIT/REDIT/ZEDIT/AEDIT.
        if sess.editor_type == "oedit":
            return [OlcFieldDescriptor("keywords","Keywords",("keywords",),"string_list"), OlcFieldDescriptor("short_description","Short description",("short_description",),"string",required=True), OlcFieldDescriptor("long_description","Long description",("long_description",),"multiline"), OlcFieldDescriptor("look_description","Action/look description",("look_description",),"multiline"), OlcFieldDescriptor("item_type","Item type",("item_type",),"enum",choices=TBA_ITEM_TYPES), OlcFieldDescriptor("extra_flags","Extra flags",("extra_flags",),"flag_set",flags=TBA_OEDIT_EXTRA_FLAGS), OlcFieldDescriptor("wear_flags","Wear flags",("wear_flags",),"flag_set",flags=TBA_OEDIT_WEAR_FLAGS), OlcFieldDescriptor("weight","Weight",("weight",),"integer",minimum=0,maximum=100000), OlcFieldDescriptor("cost","Cost",("cost",),"integer",minimum=0,maximum=100000000), OlcFieldDescriptor("cost_per_day","Cost per day",("cost_per_day",),"integer",minimum=0,maximum=100000000), OlcFieldDescriptor("destroy_timer","Timer",("destroy_timer",),"integer",minimum=0,maximum=1000000), OlcFieldDescriptor("values","Type-specific values",("type_values",),"list"), OlcFieldDescriptor("affects","Applies",("affects",),"list"), OlcFieldDescriptor("extra_descriptions","Extra descriptions",("extra_descriptions",),"list"), OlcFieldDescriptor("min_level","Minimum level",("min_level",),"integer",minimum=0,maximum=100), OlcFieldDescriptor("perm_affects","Permanent affects",("perm_affects",),"flag_set",flags=TBA_OEDIT_PERM_AFFECTS), OlcFieldDescriptor("scripts","Scripts",("scripts",),"list")]
        if sess.editor_type == "redit":
            return [OlcFieldDescriptor("name","Room name",("name",),"string",required=True), OlcFieldDescriptor("vnum","Room VNUM",("vnum",),"integer",minimum=1,maximum=999999), OlcFieldDescriptor("description","Room description",("description",),"multiline"), OlcFieldDescriptor("sector","Sector/terrain",("sector",),"enum",choices=REDIT_SECTORS), OlcFieldDescriptor("room_flags","Room flags",("flags",),"flag_set",flags=REDIT_ROOM_FLAGS), OlcFieldDescriptor("exits","Exits",("exits",),"list")]
        if sess.editor_type in {"zedit","aedit"}:
            return [OlcFieldDescriptor("name","Name",("name",),"string",required=True), OlcFieldDescriptor("id","Stable ID",("id",),"slug",read_only=True), OlcFieldDescriptor("flags","Flags",("flags",),"flag_set",flags=("starter","safe","builder","published"))]
        return []

    def _descriptor(self, sess: BuilderEditSession, token: str) -> OlcFieldDescriptor | None:
        direct = getattr(sess, "_medit_direct_descriptor", None)
        if direct is not None and (token == direct.key or not sess.section):
            return direct
        if sess.editor_type == "oedit" and (sess.mode == "oedit_values" or sess.section == "values"):
            fields = self._oedit_value_descriptors(sess)
            if str(token).isdigit():
                i = int(token) - 1
                return fields[i] if 0 <= i < len(fields) else None
            t = token.lower().replace("-","_")
            return next((f for f in fields if f.key == t or f.label.lower().replace(" ","_") == t), None)
        fields = self._field_descriptors(sess)
        if str(token).isdigit():
            i = int(token) - 1
            return fields[i] if 0 <= i < len(fields) else None
        t = token.lower().replace("-","_")
        return next((f for f in fields if f.key == t or f.label.lower().replace(" ","_") == t), None)

    def _get_path(self, rec: dict[str, Any], path: tuple[str, ...]) -> Any:
        cur: Any = rec
        for p in path:
            if not isinstance(cur, dict): return None
            cur = cur.get(p)
        return cur

    def _set_path(self, rec: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
        cur = rec
        for p in path[:-1]:
            cur = cur.setdefault(p, {})
        cur[path[-1]] = value

    def _fmt_value(self, value: Any) -> str:
        if value in (None, "", [], {}): return "none"
        if isinstance(value, list): return ", ".join(map(str, value)) or "none"
        if isinstance(value, dict): return json.dumps(value, sort_keys=True)
        return str(value)

    def _render_field_prompt(self, sess: BuilderEditSession) -> str:
        f = self._descriptor(sess, sess.active_field)
        if not f: return "No active field."
        cur = self._get_path(sess.working_record, f.path)
        rng = f" [{f.minimum}-{f.maximum}]" if f.minimum is not None or f.maximum is not None else ""
        choices = "\nChoices: " + ", ".join(f.choices) if f.choices else ""
        clear = " Use clear/none/unset to remove optional values." if not f.required else ""
        return f"Current {f.label.lower()}: {self._fmt_value(cur)}\nEnter new {f.label.lower()}{rng}, or Q to cancel.{clear}{choices}"

    def _render_multiline(self, sess: BuilderEditSession) -> str:
        return "Multiline text editor. Enter text lines. Commands: .save .cancel .clear .show .help"

    def _render_flag_editor(self, sess: BuilderEditSession) -> str:
        f = self._descriptor(sess, sess.active_field); field = f.path[0] if f and f.path else sess.active_field
        if sess.editor_type == "medit" and field in {"mobile_flags", "affect_flags"}:
            return medit_render.render_medit_flags(sess, field, f.flags if f else (), 79)
        cur = set(self._get_path(sess.working_record, f.path) or []) if f else set()
        lines = [f"{sess.editor_type.upper()} {sess.object_id} > {f.label if f else 'Flags'}"]
        for i, flag in enumerate((f.flags if f else ()), 1):
            lines.append(f"{i}. {flag.upper():<18} [{'X' if flag in cur else ' '}]")
        lines += ["Q. Back", "Commands: number toggles, all, none, clear, back"]
        return "\n".join(lines)

    def _render_list_editor(self, sess: BuilderEditSession) -> str:
        f = self._descriptor(sess, sess.active_field); cur = self._get_path(sess.working_record, f.path) if f else []
        cur = cur if isinstance(cur, list) else ([] if cur in (None,"") else [cur])
        lines = [f"{f.label if f else 'List'} list editor"]
        lines += [f"{i}. {v}" for i, v in enumerate(cur, 1)] or ["- none"]
        lines.append("Commands: list, add <value>, remove <number|value>, move <from> <to>, clear, back")
        return "\n".join(lines)

    def _render_reference_selector(self, actor: Any | None, sess: BuilderEditSession) -> str:
        f = self._descriptor(sess, sess.active_field)
        rows = []
        if f:
            rows = list(self.resolve_collection_records(actor, f.reference_collection).items())
            q = sess.reference_filter.lower().strip()
            if q:
                rows = [(k,v) for k,v in rows if q in k.lower() or q in str(v.get("name") or v.get("display_name") or "").lower()]
        cur = self._get_path(sess.working_record, f.path) if f else None
        lines = [f"{f.label if f else 'Reference'} selector", f"Current: {self._fmt_value(cur)}"]
        for i, (oid, rec) in enumerate(rows[:25], 1):
            lines.append(f"{i}. {rec.get('vnum','----')} {oid} - {rec.get('name') or rec.get('display_name') or oid}")
        lines.append("Commands: number, stable ID, search text, unset, back")
        return "\n".join(lines)

    def _render_mobile_section(self, sess: BuilderEditSession, section: str) -> str:
        rec = sess.working_record or {}
        cp = rec.get("combat_profile") or {}
        lines = [f"MEDIT {section.replace('_',' ').title()}: {rec.get('name') or sess.object_id}"]
        descriptors = self._field_descriptors(sess)
        if descriptors and section not in {"natural_weapons", "spawns", "diagnostics"}:
            lines = [f"{sess.editor_type.upper()} {sess.object_id} > {section.replace('_',' ').title()}", f"Draft status: {'modified' if sess.dirty else 'clean'}"]
            for i, f in enumerate(descriptors, 1):
                suffix = " (read-only)" if f.read_only else ""
                lines.append(f"{i}. {f.label:<28}: {self._fmt_value(self._get_path(rec, f.path))}{suffix}")
            lines += ["", "Q. Back", "V. Validate", "U. Undo", "R. Redo", "S. Save"]
            return "\n".join(lines)
        if section == "identity":
            lines += [f"1. Mobile ID: {sess.object_id}", f"2. Display name: {rec.get('name','')}", f"3. Entity type: {rec.get('entity_type','npc')}", f"4. Builder status: {rec.get('builder_status','incomplete')}", f"5. World: {rec.get('world_id', sess.world_id)}", f"6. Area: {rec.get('area_id','')}", f"7. Zone: {rec.get('zone_id','')}", f"8. Legacy VNUM: {rec.get('vnum','')}", f"9. Tags: {', '.join(rec.get('tags') or [])}", "Commands: choose a numbered field, preview, validate, undo, redo, save, back"]
        elif section == "keywords":
            lines += ["Keywords: " + (", ".join(rec.get("keywords") or rec.get("aliases") or []) or "none"), "Commands: choose Keywords, then use list editor actions: add item, remove selected item, move item, clear, back"]
        elif section == "descriptions":
            for k in ("short_description","room_description","look_description","examine_description","long_description","arrival_text","departure_text","death_text","dialogue_seed"):
                lines.append(f"- {k}: {str(rec.get(k) or rec.get('description' if k=='long_description' else k) or '')[:60]}")
            lines.append("Commands: choose a numbered description field, preview, validate, undo, redo, save, back")
        elif section == "traits":
            for k in ("sex","gender","race","species","size","age_category","alignment","faction_id","occupation","language_profile_id","body_profile_id"):
                lines.append(f"- {k}: {rec.get(k,'')}")
            lines.append("Commands: choose a numbered field, preview, validate, undo, redo, save, back")
        elif section in {"attributes","resources"}:
            attrs = rec.get("attributes") or {}; res = rec.get("resources") or {}
            lines += [f"Level: {rec.get('level',1)}", "Attributes: " + json.dumps(attrs, sort_keys=True), "Resources: " + json.dumps(res, sort_keys=True), "Commands: choose a numbered numeric field, preview, validate, undo, redo, save, back"]
        elif section == "combat":
            for k in ("armor_profile_id","accuracy_modifier","evasion_modifier","attack_power_modifier","combat_behavior_profile_id","threat_profile_id","aggression_profile_id","assist_profile_id","flee_profile_id","surrender_profile_id","pursuit_profile_id","ability_loadout_id"):
                lines.append(f"- {k}: {cp.get(k,'')}")
            lines.append("Commands: choose a numbered field, preview, validate, undo, redo, save, back")
        elif section == "body_weapons":
            lines += [f"Body profile: {rec.get('body_profile_id') or cp.get('body_profile','')}", "Commands: choose Body profile, open Natural Weapons, preview, validate, undo, redo, save, back"]
        elif section == "natural_weapons":
            weapons = cp.get("natural_weapons") or []
            lines += [f"{i+1}. {w.get('id')} {w.get('mechanical_family')} {w.get('noun_plural')} weight={w.get('selection_weight')} dice={w.get('damage_dice')}" for i,w in enumerate(weapons)] or ["- none"]
            lines.append("Commands: add weapon, edit weapon, delete weapon, preview, validate, back")
        else:
            summary = self._mobile_section_summary(rec, section)
            lines += [summary, "Commands: choose a numbered field, use list/reference editors where offered, preview, validate, undo, redo, save, back"]
        return "\n".join(lines)

    def _mobile_section_summary(self, rec: dict[str, Any], section: str) -> str:
        mapping = {
            "positions": ("default_position","spawn_position"), "mobile_flags": ("mobile_flags",), "affect_flags": ("affect_flags",),
            "equipment": ("equipment_loadout",), "inventory": ("starting_inventory",), "loot": ("loot", "corpse_profile_id"),
            "abilities": ("ability_loadout_id","granted_abilities"), "ai": ("ai_actor_enabled","behavior_profile_id","personality_profile_id","goal_profile_id","need_profile_id","memory_profile_id","schedule_id"),
            "faction": ("faction_id","organization_id","relationship_seed_ids","hostility_profile_id"), "scripts": ("script_ids","scripts"), "spawns": ("spawn_refs",), "diagnostics": ("schema_version","_builder_revision")}
        return "\n".join(f"- {k}: {rec.get(k,'')}" for k in mapping.get(section, ())) or "No fields configured."




    def _resolve_item_id_for_medit(self, actor: Any, token: str) -> str | None:
        rows=self.content_query.by_id_or_vnum(actor,"object",token)
        if len(rows)==1: return rows[0].canonical_id
        rec=self.resolve_reference(actor,"items",token)
        return str(rec.get('id')) if rec else None

    def _handle_medit_loadout(self, actor: Any, sess: BuilderEditSession, text: str) -> BuilderResult:
        low=text.lower().strip(); load=sess.working_record.setdefault('equipment_loadout',{}); load.setdefault('equipped',{}); load.setdefault('carried',[])
        if sess.confirmation_type == 'medit_equip_slot':
            choices=list(sess.pending_choices or [])
            if low in {'q','quit','cancel'}:
                sess.confirmation_type=''; sess.pending_choices=[]; sess.pending_value=None; return BuilderResult(True,"Cancelled.\n"+self._render_medit_loadout(actor,sess))
            idx=int(low)-1 if low.isdigit() else -1
            slot=choices[idx] if 0 <= idx < len(choices) else normalize_equipment_slot(low)
            if slot not in choices: return BuilderResult(False,"Choose a listed canonical slot (or Q to cancel):")
            iid=str(sess.pending_value or '')
            self._session_checkpoint(sess); load['equipped'][slot]={'slot':slot,'item_template_id':iid,'quantity':1,'chance':100}
            sess.confirmation_type=''; sess.pending_choices=[]; sess.pending_value=None; sess.dirty=True; sess.saved=False
            return BuilderResult(True,f"Equipped {iid} in {self._slot_label(slot)}.\n"+self._render_medit_loadout(actor,sess))
        if sess.confirmation_type in {'medit_equip','medit_inv_add','medit_loot_add'}:
            typ=sess.confirmation_type
            if low in {'q','quit','cancel'}:
                sess.confirmation_type=''; return BuilderResult(True,"Cancelled.\n"+self._render_medit_loadout(actor,sess))
            iid=self._resolve_item_id_for_medit(actor,text.strip())
            if not iid: return BuilderResult(False,"Object not found. Enter object ID, VNUM, or search term (Q to cancel):")
            self._session_checkpoint(sess)
            if typ=='medit_equip':
                item=self.resolve_collection_records(actor,'items').get(iid,{}) ; choices=self._compatible_equipment_slots_for_item(item)
                if not choices: return BuilderResult(False,f"{iid} has no compatible canonical equipment slots.")
                if len(choices)>1:
                    sess.confirmation_type='medit_equip_slot'; sess.pending_value=iid; sess.pending_choices=choices
                    return BuilderResult(True,"Choose equipment slot:\n"+"\n".join(f"{i}) {self._slot_label(slot)}" for i,slot in enumerate(choices,1))+"\nQ) Cancel")
                slot=choices[0]; load['equipped'][slot]={'slot':slot,'item_template_id':iid,'quantity':1,'chance':100}; msg=f"Equipped {iid} in {self._slot_label(slot)}."
            elif typ=='medit_inv_add': load['carried'].append({'item_template_id':iid,'quantity':1,'chance':100}); msg=f"Added {iid} to inventory."
            else:
                loot=sess.working_record.setdefault('loot',{}); loot.setdefault('entries',[]).append({'item_template_id':iid,'quantity':1,'chance':100}); msg=f"Added {iid} to loot."
            sess.confirmation_type=''; sess.dirty=True; sess.saved=False; return BuilderResult(True,msg+"\n"+self._render_medit_loadout(actor,sess))
        if low in {'q','quit','back'}: sess.section=''; sess.mode='main_menu'; return BuilderResult(True,self.render_session(sess))
        if low=='a': sess.confirmation_type='medit_equip'; return BuilderResult(True,"Enter object ID, VNUM, or search term to equip (Q to cancel):")
        if low=='b': sess.confirmation_type='medit_inv_add'; return BuilderResult(True,"Enter object ID, VNUM, or search term to add to inventory (Q to cancel):")
        if low=='c': sess.confirmation_type='medit_loot_add'; return BuilderResult(True,"Enter object ID, VNUM, or search term to add to loot (Q to cancel):")
        if low=='d':
            occ=[(slot,e) for slot,e in (load.get('equipped') or {}).items() if isinstance(e,dict)]
            if not occ: return BuilderResult(True,"No equipped items are available to remove.\n"+self._render_medit_loadout(actor,sess))
            self._session_checkpoint(sess); slot,_=occ[0]; load['equipped'].pop(slot,None); sess.dirty=True; sess.saved=False; return BuilderResult(True,"Equipped item removed.\n"+self._render_medit_loadout(actor,sess))
        if low=='e':
            if not load.get('carried'): return BuilderResult(True,"No inventory items are available to remove.\n"+self._render_medit_loadout(actor,sess))
            self._session_checkpoint(sess); load['carried'].pop(0); sess.dirty=True; sess.saved=False; return BuilderResult(True,"Inventory item removed.\n"+self._render_medit_loadout(actor,sess))
        if low=='f':
            loot=sess.working_record.setdefault('loot',{}); arr=loot.setdefault('entries',[])
            if not arr: return BuilderResult(True,"No loot entries are available to remove.\n"+self._render_medit_loadout(actor,sess))
            self._session_checkpoint(sess); arr.pop(0); sess.dirty=True; sess.saved=False; return BuilderResult(True,"Loot entry removed.\n"+self._render_medit_loadout(actor,sess))
        return BuilderResult(False,"Invalid choice. Use A, B, C, D, E, F, or Q.\n"+self._render_medit_loadout(actor,sess))

    def _handle_medit_scripts(self, actor: Any, sess: BuilderEditSession, text: str) -> BuilderResult:
        low=text.lower().strip(); arr=sess.working_record.setdefault('script_attachments',[])
        if low in {'q','quit','back'}: sess.section=''; sess.mode='main_menu'; return BuilderResult(True,self.render_session(sess))
        if low=='a': self._session_checkpoint(sess); arr.append({'script_id':f'script_{len(arr)+1}','trigger':'event','enabled':True}); sess.dirty=True; sess.saved=False; return BuilderResult(True,"Script attached.\n"+self._render_medit_scripts(actor,sess))
        if low=='d':
            if not arr: return BuilderResult(True,"No scripts are available to delete.\n"+self._render_medit_scripts(actor,sess))
            self._session_checkpoint(sess); arr.pop(0); sess.dirty=True; sess.saved=False; return BuilderResult(True,"Script deleted.\n"+self._render_medit_scripts(actor,sess))
        if low=='v': return BuilderResult(True,(json.dumps(arr[0],indent=2,sort_keys=True) if arr else "No scripts are attached.")+"\n"+self._render_medit_scripts(actor,sess))
        return BuilderResult(False,"Invalid choice. Use A, D, V, or Q.\n"+self._render_medit_scripts(actor,sess))

    def _handle_medit_advanced(self, actor: Any, sess: BuilderEditSession, text: str) -> BuilderResult:
        low=text.lower().strip(); key='combat_abilities' if sess.section in {'abilities','combat_abilities'} else 'event_reactions'; entries=sess.working_record.setdefault(key,[]); kind='combat_ability' if key=='combat_abilities' else 'event_reaction'
        if sess.mode in {'medit_ability_value','medit_reaction_value'}:
            idx=int(sess.pending_value or 0); field=str(sess.active_field or '')
            if low in {'q','quit','back'}:
                sess.mode='medit_ability_slot' if key=='combat_abilities' else 'medit_reaction_slot'; sess.active_field=''
                return BuilderResult(True,(self._render_medit_ability_slot(sess) if key=='combat_abilities' else self._render_medit_reaction_slot(sess)))
            self._session_checkpoint(sess); e=entries[idx]
            def as_int(v, default=0):
                try: return int(v)
                except Exception: return default
            if key=='combat_abilities':
                if field=='ability_type':
                    if low not in MEDIT_ADVANCED_ABILITY_TYPES: return BuilderResult(False,'Choose: '+', '.join(MEDIT_ADVANCED_ABILITY_TYPES))
                    e['ability_type']=low
                elif field=='ability_id': e['ability_id']=text.strip()
                elif field=='target_selector':
                    if low not in MEDIT_ADVANCED_TARGETS: return BuilderResult(False,'Choose: '+', '.join(MEDIT_ADVANCED_TARGETS))
                    e['target_selector']=low
                elif field=='trigger':
                    val = 'cooldown_ready' if low == 'cooldown' else low
                    if val not in MEDIT_ADVANCED_ABILITY_TRIGGERS: return BuilderResult(False,'Choose: '+', '.join(MEDIT_ADVANCED_ABILITY_TRIGGERS))
                    e['trigger']=val
                elif field=='timing':
                    parts=dict(x.split('=',1) for x in text.split() if '=' in x)
                    for k in ('cooldown','minimum_round','maximum_round','chance'): e[k]=as_int(parts.get(k,''), as_int(e.get(k, 0 if k!='chance' else 100)))
                elif field=='limits':
                    parts=dict(x.split('=',1) for x in text.split() if '=' in x)
                    for k in ('uses_per_combat','uses_per_spawn','priority'): e[k]=as_int(parts.get(k,''), as_int(e.get(k,0)))
                elif field=='flags':
                    vals={v.lower() for v in text.replace(',', ' ').split()}
                    if 'enabled' in vals: e['enabled']=True
                    if 'disabled' in vals: e['enabled']=False
                    e['requires_line_of_sight']='requires_line_of_sight' in vals or 'los' in vals; e['interruptible']='interruptible' in vals
            else:
                if field=='event_type':
                    if low not in MEDIT_ADVANCED_EVENT_TYPES: return BuilderResult(False,'Choose: '+', '.join(MEDIT_ADVANCED_EVENT_TYPES))
                    e['event_type']=low
                elif field=='action_type':
                    if low not in MEDIT_ADVANCED_ACTION_TYPES: return BuilderResult(False,'Choose: '+', '.join(MEDIT_ADVANCED_ACTION_TYPES))
                    e['action_type']=low
                elif field=='action_data':
                    try: e['action_data']=json.loads(text) if text.strip().startswith('{') else {'text':text.strip()}
                    except Exception: return BuilderResult(False,'Enter JSON object or plain action text.')
                elif field=='target_selector':
                    if low not in MEDIT_ADVANCED_TARGETS: return BuilderResult(False,'Choose: '+', '.join(MEDIT_ADVANCED_TARGETS))
                    e['target_selector']=low
                elif field=='cooldown':
                    parts=dict(x.split('=',1) for x in text.split() if '=' in x)
                    for k in ('cooldown','chance','priority'): e[k]=as_int(parts.get(k,''), as_int(e.get(k, 0 if k!='chance' else 100)))
                elif field=='limits':
                    parts=dict(x.split('=',1) for x in text.split() if '=' in x)
                    for k in ('uses_per_spawn','maximum_triggers'): e[k]=as_int(parts.get(k,''), as_int(e.get(k,0)))
                    if 'once' in low: e['once']=True
                    if 'stop' in low: e['stop_processing']=True
            sess.working_record[key]=[_canonical_advanced_entry(x,sess.object_id,kind,i+1) for i,x in enumerate(entries)]; sess.dirty=True; sess.saved=False; sess.mode='medit_ability_slot' if key=='combat_abilities' else 'medit_reaction_slot'; sess.active_field=''
            return BuilderResult(True,'Field updated.\n'+(self._render_medit_ability_slot(sess) if key=='combat_abilities' else self._render_medit_reaction_slot(sess)))
        if sess.mode in {'medit_ability_slot','medit_reaction_slot'}:
            if low in {'q','quit','back'}: sess.mode='section_menu'; return BuilderResult(True,self._render_medit_advanced_list(sess,key))
            field_map={'1':'ability_type','2':'ability_id','3':'target_selector','4':'trigger','5':'timing','6':'limits','7':'flags'} if key=='combat_abilities' else {'1':'event_type','2':'action_type','3':'action_data','4':'target_selector','5':'cooldown','6':'limits'}
            if low in field_map:
                sess.active_field=field_map[low]; sess.mode='medit_ability_value' if key=='combat_abilities' else 'medit_reaction_value'
                return BuilderResult(True,'Enter value for '+sess.active_field.replace('_',' ')+':')
            return BuilderResult(False,("Invalid choice. Use 1-7 or Q.\n" if key=='combat_abilities' else "Invalid choice. Use 1-6 or Q.\n")+(self._render_medit_ability_slot(sess) if key=='combat_abilities' else self._render_medit_reaction_slot(sess)))
        if low in {'q','quit','back'}: sess.section=''; sess.mode='main_menu'; return BuilderResult(True,self.render_session(sess))
        def commit(msg):
            sess.working_record[key]=[_canonical_advanced_entry(e,sess.object_id,kind,i+1) for i,e in enumerate(entries)]; sess.dirty=True; sess.saved=False; return BuilderResult(True,msg+'\n'+self._render_medit_advanced_list(sess,key))
        if low=='a': self._session_checkpoint(sess); entries.append({'ability_id':'','ability_type':'ability','trigger':'every_round','target_selector':'current_enemy','enabled':True} if key=='combat_abilities' else {'event_type':'spawn','action_type':'noop','target_selector':'self','enabled':True,'action_data':{}}); sess.pending_value=len(entries)-1; sess.mode='medit_ability_slot' if key=='combat_abilities' else 'medit_reaction_slot'; commit(''); return BuilderResult(True,self._render_medit_ability_slot(sess) if key=='combat_abilities' else self._render_medit_reaction_slot(sess))
        if low in {'e','edit'}:
            if not entries: return BuilderResult(False,"No entries are available to edit.\n"+self._render_medit_advanced_list(sess,key))
            sess.pending_value=0; sess.mode='medit_ability_slot' if key=='combat_abilities' else 'medit_reaction_slot'; return BuilderResult(True,self._render_medit_ability_slot(sess) if key=='combat_abilities' else self._render_medit_reaction_slot(sess))
        if low=='d':
            if not entries: return BuilderResult(False,"No entries are available to delete.\n"+self._render_medit_advanced_list(sess,key))
            self._session_checkpoint(sess); entries.pop(0); return commit('Entry deleted.')
        if low=='t':
            if not entries: return BuilderResult(False,"No entries are available to toggle.\n"+self._render_medit_advanced_list(sess,key))
            self._session_checkpoint(sess); entries[0]['enabled']=not entries[0].get('enabled',True); return commit('Entry toggled.')
        return BuilderResult(False,"Invalid choice. Use A, E, D, T, or Q.\n"+self._render_medit_advanced_list(sess,key))

    def _slot_label(self, slot: str) -> str:
        return equipment_slot_label(slot)

    def _obj_brief(self, actor: Any, item_id: str) -> str:
        rec = self.resolve_collection_records(actor, "items").get(str(item_id), {}) if actor is not None else {}
        name = rec.get('short_description') or rec.get('name') or str(item_id)
        return f"[{item_id}] {name}"



    def _compatible_equipment_slots_for_item(self, item: dict[str, Any]) -> list[str]:
        raw = item.get('wear_flags') or item.get('wear_slots') or item.get('equipment_slots') or item.get('occupies_slots') or []
        slots = canonicalize_slot_list(raw)
        if not slots:
            item_type = str(item.get('item_type') or item.get('type') or '').lower()
            keywords = {str(k).lower() for k in (item.get('keywords') or [])}
            name = str(item.get('name') or item.get('id') or '').lower()
            if item_type == 'weapon':
                slots = ['main_hand', 'off_hand']
            elif keywords & {'sword', 'blade', 'staff', 'mace', 'club', 'weapon'} or any(word in name for word in ('sword', 'staff', 'mace', 'club')):
                slots = ['main_hand']
            elif item_type == 'armor':
                slots = ['chest']
        return [slot for slot in CANONICAL_EQUIPMENT_SLOT_IDS if slot in slots]

    def _normalized_equipped_map(self, equipped: dict[str, Any], mobile_id: str) -> tuple[dict[str, Any], list[str]]:
        normalized: dict[str, Any] = {}
        errors: list[str] = []
        for raw_slot, entry in (equipped or {}).items():
            slot = normalize_equipment_slot(raw_slot)
            iid = str((entry or {}).get("item_template_id") or (entry or {}).get("item_id") or "") if isinstance(entry, dict) else ""
            if slot not in VALID_WEAR_SLOTS:
                errors.append(f"Mobile `{mobile_id}` assigns `{iid}` to unknown slot `{raw_slot}`.")
                continue
            if slot in normalized and normalized[slot] != entry:
                existing = normalized[slot]
                existing_iid = str((existing or {}).get("item_template_id") or (existing or {}).get("item_id") or "") if isinstance(existing, dict) else ""
                errors.append(f"Equipment slot conflict: `{raw_slot}` and `{slot}` both contain items on mobile `{mobile_id}` ({existing_iid}, {iid}). Resolve before publish.")
                continue
            normalized[slot] = entry
        return normalized, errors

    def _render_medit_loadout(self, actor: Any, sess: BuilderEditSession) -> str:
        rec=sess.working_record or {}; name=rec.get('name') or sess.object_id
        load=rec.setdefault('equipment_loadout', {}) if isinstance(rec.setdefault('equipment_loadout', {}), dict) else {}
        eq=load.get('equipped') or {}; inv=load.get('carried') or rec.get('starting_inventory') or []
        loot=((rec.get('loot') or {}).get('entries') if isinstance(rec.get('loot'), dict) else rec.get('loot')) or []
        lines=[f"-- Loadout / Loot: [{rec.get('vnum') or sess.object_id}] {name}","","EQUIPPED ITEMS",f"{name} is using:"]
        normalized_eq, _slot_errors = self._normalized_equipped_map(eq if isinstance(eq, dict) else {}, name)
        for slot in CANONICAL_EQUIPMENT_SLOT_IDS:
            ent=normalized_eq.get(slot) if isinstance(normalized_eq, dict) else None
            iid=str((ent or {}).get('item_template_id') or (ent or {}).get('item_id') or '') if isinstance(ent, dict) else ''
            lines.append(f"{self._slot_label(slot):<16} {self._obj_brief(actor, iid) if iid else '[NOTHING]'}")
        lines += ["","INVENTORY ITEMS"]
        if inv:
            for i,e in enumerate(inv,1):
                iid=str((e or {}).get('item_template_id') or (e or {}).get('item_id') or e) if not isinstance(e,str) else e; qty=(e or {}).get('quantity',1) if isinstance(e,dict) else 1
                lines.append(f"{i}) {self._obj_brief(actor, iid):<40} qty:{qty}")
        else: lines.append("   [NONE]")
        lines += ["","LOOT TABLE"]
        if loot:
            for i,e in enumerate(loot,1):
                iid=str((e or {}).get('item_template_id') or (e or {}).get('item_id') or (e or {}).get('object_id') or e) if not isinstance(e,str) else e; qty=(e or {}).get('quantity',1) if isinstance(e,dict) else 1; chance=(e or {}).get('chance') if isinstance(e,dict) else None
                tail=f"chance:{chance}%   qty:{qty}" if chance is not None else f"qty:{qty}"
                lines.append(f"{i}) [{iid}]      {tail}")
        else: lines.append("   [NONE]")
        lines += ["","A) Equip object","B) Add inventory item","C) Add loot item","D) Remove equipped item","E) Remove inventory item","F) Remove loot item","Q) Quit","Enter choice :"]
        return "\n".join(lines)

    def _render_medit_scripts(self, actor: Any, sess: BuilderEditSession) -> str:
        rec=sess.working_record or {}; scripts=rec.get('script_attachments') or rec.get('script_ids') or rec.get('scripts') or []
        lines=[f"-- Scripts: [{rec.get('vnum') or sess.object_id}] {rec.get('name') or sess.object_id}",""]
        lines += [f"{i}) [{(x.get('script_id') if isinstance(x,dict) else x)}]" for i,x in enumerate(scripts,1)] or ['   [NONE]']
        lines += ["","A) Add","D) Delete","V) View","Q) Quit","Enter choice :"]
        return "\n".join(lines)

    def _render_medit_advanced_list(self, sess: BuilderEditSession, key: str) -> str:
        title='Combat Abilities' if key=='combat_abilities' else 'Event Reactions'; entries=sess.working_record.get(key) or []
        maxn=10; lines=[f"{title} ({len(entries)}/{maxn})",""]
        if not entries: lines.append('   [NONE]')
        else:
            for i,e in enumerate(entries,1):
                if key=='combat_abilities': lines.append(f"{i}) {e.get('ability_id') or '<unset>':<10} target:{e.get('target_selector','current_enemy')}   trigger:{e.get('trigger','every_round')}   {'enabled' if e.get('enabled', True) else 'disabled'}")
                else: lines.append(f"{i}) {str(e.get('event_type') or '<unset>').replace('_',' ')} -> {str(e.get('action_type') or '<unset>').replace('_',' ')}")
        lines += ["","A) Add   E) Edit   D) Delete   T) Toggle   Q) Quit","Enter choice:"]
        return "\n".join(lines)

    def _render_medit_ability_slot(self, sess: BuilderEditSession) -> str:
        entries=sess.working_record.get('combat_abilities') or []; idx=int(sess.pending_value or 0); e=entries[idx] if 0<=idx<len(entries) else {}
        return "\n".join([f"Combat Ability Editor (slot {idx+1})","Choose what this mob can do during combat, who it targets, and when it should attempt the action.","",f"1) Type             : {e.get('ability_type','ability')}",f"2) Spell / Skill    : {e.get('ability_id') or '<unset>'}",f"3) Target           : {e.get('target_selector','current_enemy')}",f"4) Trigger Mode     : {e.get('trigger','every_round')}","5) Timing / Condition Details","6) Usage Limits","7) Status Flags","Q) Back","Enter field:"])

    def _render_medit_reaction_slot(self, sess: BuilderEditSession) -> str:
        entries=sess.working_record.get('event_reactions') or []; idx=int(sess.pending_value or 0); e=entries[idx] if 0<=idx<len(entries) else {}
        return "\n".join([f"Event Reaction Editor (slot {idx+1})","Choose what event triggers the reaction, what action is taken, and any cooldown or one-time limits.","",f"1) Event Type       : {str(e.get('event_type','spawn')).replace('_',' ')}",f"2) Action Type      : {str(e.get('action_type','noop')).replace('_',' ')}","3) Action Data",f"4) Target           : {e.get('target_selector','self')}","5) Cooldown / Chance","6) Limits / Conditions","Q) Back","Enter field:"])

    def _item_label(self, actor: Any, item_id: str) -> str:
        rec = self.resolve_collection_records(actor, "items").get(str(item_id), {})
        return f"{rec.get('name') or rec.get('short_description') or item_id} [{item_id}]"

    def _render_equipment_editor(self, actor: Any, sess: BuilderEditSession) -> str:
        rec = sess.working_record or {}
        loadout = rec.setdefault("equipment_loadout", {})
        equipped = loadout.get("equipped") if isinstance(loadout, dict) else {}
        carried = loadout.get("carried") if isinstance(loadout, dict) else []
        lines = [f"MEDIT Equipment Loadout: {rec.get('name') or sess.object_id}", f"Draft status: {'modified' if sess.dirty else 'clean'}", "", "Equipped slots:"]
        normalized_eq, _slot_errors = self._normalized_equipped_map(equipped if isinstance(equipped, dict) else {}, rec.get('name') or sess.object_id)
        for slot in CANONICAL_EQUIPMENT_SLOT_IDS:
            entry = (normalized_eq or {}).get(slot) if isinstance(normalized_eq, dict) else None
            if isinstance(entry, dict):
                lines.append(f"- {slot}: {self._item_label(actor, entry.get('item_template_id',''))} chance={entry.get('chance',100)} qty={entry.get('quantity',1)}")
            else:
                lines.append(f"- {slot}: empty")
        lines.append("Carried inventory:")
        for i, entry in enumerate(carried if isinstance(carried, list) else [], 1):
            lines.append(f"{i}. {self._item_label(actor, entry.get('item_template_id',''))} chance={entry.get('chance',100)} qty={entry.get('quantity',1)}")
        if not carried: lines.append("- none")
        lines += ["", "A. Assign equipment slot", "B. Edit equipment-slot entry", "C. Remove equipment-slot entry", "D. Add carried inventory object", "E. Edit carried inventory entry", "F. Remove carried inventory entry", "G. Clear complete loadout", "P. Preview spawned mobile loadout", "V. Validate", "U. Undo", "R. Redo", "Q. Back", "Commands: assign slot object [chance] [qty]; carry object [chance] [qty]; remove slot-or-number; search text; help equipment"]
        return "\n".join(lines)

    def _equipment_validate(self, actor: Any, sess: BuilderEditSession) -> list[str]:
        items = self.resolve_collection_records(actor, "items")
        loadout = (sess.working_record or {}).get("equipment_loadout") or {}
        errors=[]
        _normalized, collision_errors = self._normalized_equipped_map(loadout.get("equipped") or {}, sess.object_id)
        errors.extend(collision_errors)
        for slot, entry in (loadout.get("equipped") or {}).items():
            iid = str((entry or {}).get("item_template_id") or "")
            rec = items.get(iid)
            normalized_slot = normalize_equipment_slot(slot)
            if normalized_slot not in VALID_WEAR_SLOTS: errors.append(f"Mobile `{sess.object_id}` assigns `{iid}` to unknown slot `{slot}`.")
            elif normalized_slot != slot: errors.append(f"Equipment slot conflict/alias on mobile `{sess.object_id}`: `{slot}` should be normalized to `{normalized_slot}` before publish.")
            if not rec: errors.append(f"equipment.{slot}: missing object template {iid}")
            else:
                wear=set(canonicalize_slot_list(rec.get("wear_flags") or rec.get("wear_slots") or rec.get("slot_restrictions") or []))
                if wear and normalized_slot not in wear: errors.append(f"Mobile `{sess.object_id}` assigns `{iid}` to incompatible slot `{slot}`. Valid canonical slots: {', '.join(wear)}")
            try:
                ch=int((entry or {}).get("chance",100)); qty=int((entry or {}).get("quantity",1))
                if ch < 0 or ch > 100: errors.append(f"equipment.{slot}: chance must be 0-100")
                if qty <= 0: errors.append(f"equipment.{slot}: quantity must be positive")
            except Exception: errors.append(f"equipment.{slot}: chance and quantity must be whole numbers")
        for i, entry in enumerate(loadout.get("carried") or [], 1):
            iid=str((entry or {}).get("item_template_id") or "")
            if iid not in items: errors.append(f"carried.{i}: missing object template {iid}")
        return errors

    def _handle_equipment_editor(self, actor: Any, sess: BuilderEditSession, text: str) -> BuilderResult:
        low=text.lower().strip(); parts=text.split()
        if low in {"q","back","quit"}: sess.section=""; sess.mode="main_menu"; return BuilderResult(True,self.render_session(sess))
        if low in {"u","undo"}:
            if not sess.undo_stack: return BuilderResult(False,"Nothing to undo.")
            sess.redo_stack.append(deepcopy(sess.working_record)); sess.working_record=sess.undo_stack.pop(); sess.dirty=sess.working_record!=sess.savepoint; sess.saved=not sess.dirty; return BuilderResult(True,"Session undo applied.\n"+self._render_equipment_editor(actor,sess))
        if low in {"r","redo"}:
            if not sess.redo_stack: return BuilderResult(False,"Nothing to redo.")
            sess.undo_stack.append(deepcopy(sess.working_record)); sess.working_record=sess.redo_stack.pop(); sess.dirty=sess.working_record!=sess.savepoint; sess.saved=not sess.dirty; return BuilderResult(True,"Session redo applied.\n"+self._render_equipment_editor(actor,sess))
        if low in {"v","validate"}: 
            errs=self._equipment_validate(actor,sess); return BuilderResult(not errs, "Equipment validation:\n"+("\n".join("error: "+e for e in errs) if errs else "- no focused issues"))
        if low in {"p","preview"}: return BuilderResult(True, "Equipment loadout preview:\n"+self._render_equipment_editor(actor,sess))
        if low.startswith("search "):
            rows=self.content_query.search(actor,"object",text[7:].strip())[:10]
            return BuilderResult(True,"Object search results:\n"+"\n".join(f"{i}. {r.display_name} [{r.canonical_id}] type={r.record.get('item_type') or r.record.get('type')} wear={','.join(r.record.get('wear_flags') or [])}" for i,r in enumerate(rows,1)))
        if low in {"a","assign"}: return BuilderResult(True,"Enter: assign <slot> <object_id|vnum|search-term> [chance 0-100] [quantity]")
        if low in {"d","carry"}: return BuilderResult(True,"Enter: carry <object_id|vnum|search-term> [chance 0-100] [quantity]")
        if low in {"g","clear"}:
            self._session_checkpoint(sess); sess.working_record["equipment_loadout"]={"equipped":{},"carried":[]}; sess.dirty=True; sess.saved=False; return BuilderResult(True,"Equipment loadout cleared.\n"+self._render_equipment_editor(actor,sess))
        if parts and parts[0].lower() in {"assign","a"} and len(parts)>=3:
            slot=normalize_equipment_slot(parts[1].lower()); match=self.content_query.by_id_or_vnum(actor,"object",parts[2]);
            if slot not in VALID_WEAR_SLOTS: return BuilderResult(False,f"Invalid equipment slot {parts[1]}.")
            if len(match)!=1: return BuilderResult(False,"Object selection is ambiguous or missing; use search <text> then exact ID.")
            item=match[0]; wear=set(self._compatible_equipment_slots_for_item(item.record))
            if wear and slot not in wear: return BuilderResult(False,f"{item.canonical_id} cannot be worn in {self._slot_label(slot)}. Valid wear locations: {', '.join(equipment_slot_label(w) for w in wear) or 'none'}.")
            chance=int(parts[3]) if len(parts)>3 and parts[3].isdigit() else 100; qty=int(parts[4]) if len(parts)>4 and parts[4].isdigit() else 1
            if not (0<=chance<=100) or qty<=0: return BuilderResult(False,"Chance must be 0-100 and quantity must be positive.")
            self._session_checkpoint(sess); load=sess.working_record.setdefault("equipment_loadout",{}); load.setdefault("equipped",{})[slot]={"slot":slot,"item_template_id":item.canonical_id,"chance":chance,"quantity":qty}; load.setdefault("carried",[]); sess.dirty=True; sess.saved=False
            return BuilderResult(True,"Equipment slot assigned.\n"+self._render_equipment_editor(actor,sess))
        if parts and parts[0].lower() in {"carry","d"} and len(parts)>=2:
            match=self.content_query.by_id_or_vnum(actor,"object",parts[1]);
            if len(match)!=1: return BuilderResult(False,"Object selection is ambiguous or missing; use search <text> then exact ID.")
            chance=int(parts[2]) if len(parts)>2 and parts[2].isdigit() else 100; qty=int(parts[3]) if len(parts)>3 and parts[3].isdigit() else 1
            if not (0<=chance<=100) or qty<=0: return BuilderResult(False,"Chance must be 0-100 and quantity must be positive.")
            self._session_checkpoint(sess); load=sess.working_record.setdefault("equipment_loadout",{}); load.setdefault("equipped",{}); load.setdefault("carried",[]).append({"item_template_id":match[0].canonical_id,"chance":chance,"quantity":qty}); sess.dirty=True; sess.saved=False
            return BuilderResult(True,"Carried inventory entry added.\n"+self._render_equipment_editor(actor,sess))
        if parts and parts[0].lower() in {"remove","c","f"} and len(parts)>=2:
            self._session_checkpoint(sess); load=sess.working_record.setdefault("equipment_loadout",{}); tok=parts[1].lower()
            if tok.isdigit():
                arr=load.setdefault("carried",[]); idx=int(tok)-1
                if not 0<=idx<len(arr): sess.undo_stack.pop(); return BuilderResult(False,"Carried inventory index out of range.")
                arr.pop(idx)
            else: load.setdefault("equipped",{}).pop(normalize_equipment_slot(tok),None)
            sess.dirty=True; sess.saved=False; return BuilderResult(True,"Loadout entry removed.\n"+self._render_equipment_editor(actor,sess))
        return BuilderResult(False,"Equipment editor command not understood. Use assign, carry, remove, clear, preview, validate, undo, redo, back, or help equipment.")

    def _render_spawns_editor(self, actor: Any, sess: BuilderEditSession) -> str:
        mid=sess.object_id; sp=[]
        for sid, rec in self.resolve_collection_records(actor,"spawns").items():
            if str(rec.get("mobile_id") or rec.get("mob_id") or rec.get("entity_id") or rec.get("template_id")) == mid or mid in json.dumps(rec,default=str): sp.append((sid,rec))
        lines=[f"MEDIT Spawn References: {(sess.working_record or {}).get('name') or mid}", f"Draft status: {'modified' if sess.dirty else 'clean'}"]
        for i,(sid,r) in enumerate(sp,1): lines.append(f"{i}. {sid} area={r.get('area_id','')} zone={r.get('zone_id','')} room={r.get('room_id','')} profile={r.get('reset_profile_id') or r.get('profile_id','default')} max={r.get('max_count',r.get('maximum',1))} chance={r.get('chance',r.get('probability',100))} enabled={r.get('enabled',True)}")
        if not sp: lines.append("- none")
        lines += ["A. Add spawn reference", "E. Edit selected spawn reference", "R. Remove selected spawn reference", "G. Go to or inspect target room", "Z. Open related zone/reset profile", "P. Preview reset result", "T. Trace reset command", "V. Validate", "U. Undo", "D. Redo", "Q. Back", "Commands: add <room_id> [max] [chance]; edit <#> max <n>|chance <n>; remove <#>; preview; trace"]
        return "\n".join(lines)

    def _handle_spawns_editor(self, actor: Any, sess: BuilderEditSession, text: str) -> BuilderResult:
        low=text.lower().strip(); parts=text.split(); world=sess.world_id
        if low in {"q","back","quit"}: sess.section=""; sess.mode="main_menu"; return BuilderResult(True,self.render_session(sess))
        if low in {"p","preview"}: return BuilderResult(True,"Reset preview (working draft):\n"+self._render_spawns_editor(actor,sess))
        if low in {"t","trace"}: return BuilderResult(True,"Reset trace: canonical spawn references for this mobile are listed in command order above.")
        if low in {"v","validate"}: return BuilderResult(True,"Spawn validation:\n- no focused issues")
        if low in {"u","undo"}:
            if not sess.undo_stack: return BuilderResult(False,"Nothing to undo.")
            sess.redo_stack.append(deepcopy(sess.working_record)); sess.working_record=sess.undo_stack.pop(); sess.dirty=sess.working_record!=sess.savepoint; sess.saved=not sess.dirty; return BuilderResult(True,"Session undo applied.\n"+self._render_spawns_editor(actor,sess))
        if low in {"d","redo"}:
            if not sess.redo_stack: return BuilderResult(False,"Nothing to redo.")
            sess.undo_stack.append(deepcopy(sess.working_record)); sess.working_record=sess.redo_stack.pop(); sess.dirty=sess.working_record!=sess.savepoint; sess.saved=not sess.dirty; return BuilderResult(True,"Session redo applied.\n"+self._render_spawns_editor(actor,sess))
        drafts=self.workspace.load(world); spawns=drafts.setdefault("spawns",{})
        related=[(sid,r) for sid,r in spawns.items() if isinstance(r,dict) and (str(r.get("mobile_id") or r.get("mob_id") or r.get("entity_id") or r.get("template_id"))==sess.object_id or sess.object_id in json.dumps(r,default=str))]
        if parts and parts[0].lower() in {"add","a"} and len(parts)>=2:
            room=self.resolve_reference(actor,"rooms",parts[1])
            if not room: return BuilderResult(False,"Missing room; choose a valid room ID, VNUM, or search term.")
            maxc=int(parts[2]) if len(parts)>2 and parts[2].isdigit() else 1; chance=int(parts[3]) if len(parts)>3 and parts[3].isdigit() else 100
            if maxc<=0 or not 0<=chance<=100: return BuilderResult(False,"Maximum count must be positive and probability must be 0-100.")
            sid=f"spawn_{sess.object_id}_{room.get('id')}"; rec={"id":sid,"world_id":world,"area_id":room.get("area_id",""),"zone_id":room.get("zone_id",""),"room_id":room.get("id"),"mobile_id":sess.object_id,"reset_profile_id":"default","max_count":maxc,"chance":chance,"enabled":True}
            self._session_checkpoint(sess); spawns[sid]=rec; self.workspace.save_drafts(world,drafts); sess.working_record.setdefault("spawn_refs",[]); 
            if sid not in sess.working_record["spawn_refs"]: sess.working_record["spawn_refs"].append(sid)
            sess.dirty=True; sess.saved=False; return BuilderResult(True,"Spawn reference added to Builder draft.\n"+self._render_spawns_editor(actor,sess))
        if parts and parts[0].lower() in {"remove","r"} and len(parts)>=2 and parts[1].isdigit():
            idx=int(parts[1])-1
            if not 0<=idx<len(related): return BuilderResult(False,"Spawn reference index out of range.")
            self._session_checkpoint(sess); sid,_=related[idx]; spawns.pop(sid,None); self.workspace.save_drafts(world,drafts); sess.working_record["spawn_refs"]=[x for x in sess.working_record.get("spawn_refs",[]) if x!=sid]; sess.dirty=True; sess.saved=False; return BuilderResult(True,"Spawn reference removed from Builder draft.\n"+self._render_spawns_editor(actor,sess))
        if parts and parts[0].lower() in {"edit","e"} and len(parts)>=4 and parts[1].isdigit():
            idx=int(parts[1])-1
            if not 0<=idx<len(related): return BuilderResult(False,"Spawn reference index out of range.")
            field={"max":"max_count","maximum":"max_count","chance":"chance","probability":"chance"}.get(parts[2].lower())
            if not field or not parts[3].isdigit(): return BuilderResult(False,"Use: edit <#> max <n> or edit <#> chance <0-100>.")
            val=int(parts[3]);
            if (field=="max_count" and val<=0) or (field=="chance" and not 0<=val<=100): return BuilderResult(False,"Maximum count must be positive and probability must be 0-100.")
            self._session_checkpoint(sess); spawns[related[idx][0]][field]=val; self.workspace.save_drafts(world,drafts); sess.dirty=True; sess.saved=False; return BuilderResult(True,"Spawn reference updated.\n"+self._render_spawns_editor(actor,sess))
        return BuilderResult(False,"Spawn editor command not understood. Use add, edit, remove, preview, trace, validate, undo, redo, back.")


    def _advanced_section_config(self, section: str) -> tuple[str, str, str]:
        if section in {"abilities", "combat_abilities"}: return ("combat_abilities", "Combat Abilities", "combat_ability")
        if section in {"reactions", "event_reactions", "ai"}: return ("event_reactions", "Event Reactions", "event_reaction")
        return ("script_attachments", "Script Attachments", "script_attachment")

    def _render_advanced_mobile_editor(self, actor: Any, sess: BuilderEditSession) -> str:
        key, title, kind = self._advanced_section_config(sess.section)
        entries = sorted(sess.working_record.get(key) or [], key=lambda e: (int(e.get("priority", 0)), str(e.get("id", ""))))
        lines=[f"MEDIT {title}: {(sess.working_record or {}).get('name') or sess.object_id}", f"Draft status: {'modified' if sess.dirty else 'clean'}", f"Entries: {len(entries)}"]
        for i,e in enumerate(entries,1):
            if key == "combat_abilities": summary=f"{e.get('ability_type')}:{e.get('ability_id') or 'missing'} trigger={e.get('trigger')} target={e.get('target_selector')} chance={e.get('chance')} cooldown={e.get('cooldown',0)} runtime={'supported' if e.get('trigger') in MEDIT_RUNTIME_SUPPORTED_ABILITY_TRIGGERS else 'deferred'}"
            elif key == "event_reactions": summary=f"event={e.get('event_type')} action={e.get('action_type')} target={e.get('target_selector')} chance={e.get('chance')} cooldown={e.get('cooldown',0)} runtime={'supported' if e.get('event_type') in MEDIT_RUNTIME_SUPPORTED_REACTION_EVENTS and e.get('action_type') in MEDIT_RUNTIME_SUPPORTED_REACTION_ACTIONS else 'deferred'}"
            else: summary=f"script={e.get('script_id') or 'missing'} trigger={e.get('trigger')} priority={e.get('priority')} runtime=canonical-host-required"
            lines.append(f"{i}. {e.get('id')} [{'on' if e.get('enabled', True) else 'off'}] priority={e.get('priority')} {summary}")
        if not entries: lines.append("- none")
        lines += ["Commands: add <ref>, edit <#> <field> <value>, delete <#>, copy <#>, move <#> <to>, up <#>, down <#>, toggle <#>, inspect <#>, preview, validate, dependency, undo, redo, save, back"]
        return "\n".join(lines)

    def _advanced_preview(self, sess: BuilderEditSession, key: str, entries: list[dict[str, Any]]) -> str:
        title={"combat_abilities":"Combat ability decision trace", "event_reactions":"Event reaction trace", "script_attachments":"Script attachment dry-run"}[key]
        lines=[title, "Simulated only: no template mutation, EventBus publication, runtime persistence, or destructive script execution."]
        for e in sorted(entries, key=lambda x:(int(x.get('priority',0)), str(x.get('id','')))):
            if key == "combat_abilities": lines.append(f"- priority {e.get('priority')}: {e.get('ability_id') or 'missing ability'} on {e.get('trigger')} -> {e.get('target_selector')} chance={e.get('chance')} cooldown={e.get('cooldown',0)} uses/combat={e.get('uses_per_combat','unlimited')} runtime={'supported' if e.get('trigger') in MEDIT_RUNTIME_SUPPORTED_ABILITY_TRIGGERS else 'deferred'}")
            elif key == "event_reactions": lines.append(f"- priority {e.get('priority')}: when {e.get('event_type')} then {e.get('action_type')} target={e.get('target_selector')} stop={e.get('stop_processing',False)} runtime={'supported' if e.get('event_type') in MEDIT_RUNTIME_SUPPORTED_REACTION_EVENTS and e.get('action_type') in MEDIT_RUNTIME_SUPPORTED_REACTION_ACTIONS else 'deferred'}")
            else: lines.append(f"- priority {e.get('priority')}: attach {e.get('script_id') or 'missing script'} on {e.get('trigger')} policy={e.get('execution_policy')} dry-run only")
        return "\n".join(lines)

    def _handle_advanced_mobile_editor(self, actor: Any, sess: BuilderEditSession, text: str) -> BuilderResult:
        low=text.lower().strip(); parts=text.split(); key, title, kind = self._advanced_section_config(sess.section)
        entries=list(sess.working_record.get(key) or [])
        if low in {"q","back","quit","main"}: sess.section=""; sess.mode="main_menu"; return BuilderResult(True,self.render_session(sess))
        if low in {"u","undo"}:
            if not sess.undo_stack: return BuilderResult(False,"Nothing to undo.")
            sess.redo_stack.append(deepcopy(sess.working_record)); sess.working_record=sess.undo_stack.pop(); sess.dirty=sess.working_record!=sess.savepoint; sess.saved=not sess.dirty; return BuilderResult(True,"Session undo applied.\n"+self._render_advanced_mobile_editor(actor,sess))
        if low in {"r","redo"}:
            if not sess.redo_stack: return BuilderResult(False,"Nothing to redo.")
            sess.undo_stack.append(deepcopy(sess.working_record)); sess.working_record=sess.redo_stack.pop(); sess.dirty=sess.working_record!=sess.savepoint; sess.saved=not sess.dirty; return BuilderResult(True,"Session redo applied.\n"+self._render_advanced_mobile_editor(actor,sess))
        if low in {"s","save"}: return self._session_save(actor, sess)
        if low in {"v","validate"}:
            issues=[x for x in MobileTemplate.from_legacy(sess.working_record).validate() if x.get("field_path","").startswith(key)]
            lines=[f"{x['severity']}: {x['field_path']} {x['message']} Hint: {x.get('fix_hint','')}" for x in issues] or ["- no focused issues"]
            return BuilderResult(not any(x.get('severity')=='error' for x in issues), f"{title} validation:\n"+"\n".join(lines), {"issues":issues})
        if low in {"p","preview"}: return BuilderResult(True, self._advanced_preview(sess, key, entries))
        if low in {"dependency","dependencies","deps"}: return BuilderResult(True, f"{title} dependencies:\n"+"\n".join(f"- {key}.{e.get('id')} -> {e.get('ability_id') or e.get('script_id') or (e.get('action_data') or {})}" for e in entries) if entries else f"{title} dependencies:\n- none")
        if parts and parts[0].lower() in {"inspect","i"} and len(parts)>=2 and parts[1].isdigit():
            idx=int(parts[1])-1
            if not 0<=idx<len(entries): return BuilderResult(False,"Entry index out of range.")
            return BuilderResult(True, json.dumps(entries[idx], indent=2, sort_keys=True))
        def commit(msg):
            sess.working_record[key]=[_canonical_advanced_entry(e, sess.object_id, kind, i+1) for i,e in enumerate(entries)]
            sess.dirty=True; sess.saved=False
            return BuilderResult(True,msg+"\n"+self._render_advanced_mobile_editor(actor,sess), sess.working_record)
        if parts and parts[0].lower() in {"add","a"}:
            ref=parts[1] if len(parts)>1 else ""
            self._session_checkpoint(sess)
            if key=="combat_abilities": entries.append({"ability_id":ref,"ability_type":"ability","trigger":"every_round","target_selector":"current_enemy","priority":len(entries)+1,"chance":100,"enabled":True})
            elif key=="event_reactions": entries.append({"event_type":ref or "spawn","action_type":"noop","target_selector":"self","priority":len(entries)+1,"chance":100,"enabled":True,"action_data":{}})
            else: entries.append({"script_id":ref,"trigger":"event","priority":len(entries)+1,"chance":100,"enabled":True,"parameters":{}})
            return commit(f"{title} entry added.")
        if parts and parts[0].lower() in {"delete","remove","d"} and len(parts)>=2 and parts[1].isdigit():
            idx=int(parts[1])-1
            if not 0<=idx<len(entries): return BuilderResult(False,"Entry index out of range.")
            self._session_checkpoint(sess); entries.pop(idx); return commit(f"{title} entry deleted.")
        if parts and parts[0].lower() in {"copy","clone","c"} and len(parts)>=2 and parts[1].isdigit():
            idx=int(parts[1])-1
            if not 0<=idx<len(entries): return BuilderResult(False,"Entry index out of range.")
            self._session_checkpoint(sess); new=deepcopy(entries[idx]); new.pop("id",None); new["priority"]=len(entries)+1; entries.append(new); return commit(f"{title} entry copied with a fresh nested ID.")
        if parts and parts[0].lower() in {"toggle","t"} and len(parts)>=2 and parts[1].isdigit():
            idx=int(parts[1])-1
            if not 0<=idx<len(entries): return BuilderResult(False,"Entry index out of range.")
            self._session_checkpoint(sess); entries[idx]["enabled"]=not bool(entries[idx].get("enabled",True)); return commit(f"{title} entry toggled.")
        if parts and parts[0].lower() in {"move","m"} and len(parts)>=3 and parts[1].isdigit() and parts[2].isdigit():
            a,b=int(parts[1])-1,int(parts[2])-1
            if not (0<=a<len(entries) and 0<=b<len(entries)): return BuilderResult(False,"Move indexes are out of range.")
            self._session_checkpoint(sess); val=entries.pop(a); entries.insert(b,val); return commit(f"{title} entry moved.")
        if parts and parts[0].lower() in {"up","down"} and len(parts)>=2 and parts[1].isdigit():
            idx=int(parts[1])-1; to=idx-1 if parts[0].lower()=="up" else idx+1
            if not (0<=idx<len(entries) and 0<=to<len(entries)): return BuilderResult(False,"Entry cannot move further.")
            self._session_checkpoint(sess); entries[idx],entries[to]=entries[to],entries[idx]; return commit(f"{title} entry moved.")
        if parts and parts[0].lower() in {"edit","set","e"} and len(parts)>=4 and parts[1].isdigit():
            idx=int(parts[1])-1
            if not 0<=idx<len(entries): return BuilderResult(False,"Entry index out of range.")
            field=parts[2]; value=" ".join(parts[3:])
            if field in {"enabled","stop_processing"}: value=value.lower() in {"1","yes","true","on"}
            elif field in {"priority","chance","cooldown","initial_cooldown","minimum_round","maximum_round","uses_per_combat","uses_per_life","uses_per_reset","resource_cost"}:
                try: value=int(value)
                except Exception: return BuilderResult(False, f"{field} must be a whole number.")
            elif field in {"required_status","forbidden_status","required_tags","forbidden_tags","required_target_status","forbidden_target_status"}: value=[x.strip() for x in value.split(",") if x.strip()]
            self._session_checkpoint(sess); entries[idx][field]=value; return commit(f"{title} entry updated.")
        return BuilderResult(False, f"{title} command not understood. Use add, edit, delete, copy, move, up, down, toggle, inspect, preview, validate, dependency, undo, redo, save, or back.")

    def _session_checkpoint(self, sess: BuilderEditSession) -> None:
        sess.undo_stack.append(deepcopy(sess.working_record))
        sess.undo_stack = sess.undo_stack[-100:]
        sess.redo_stack = []

    def _session_preview(self, actor: Any, sess: BuilderEditSession) -> BuilderResult:
        return self._preview_record(actor, sess.collection, sess.object_id, sess.working_record)

    def _session_save(self, actor: Any, sess: BuilderEditSession) -> BuilderResult:
        if sess.collection == "entities":
            issues = MobileTemplate.from_legacy(sess.working_record).validate()
            errors = [i for i in issues if i.get("severity") == "error" or i.get("blocking")]
            if errors:
                return BuilderResult(False, "Save blocked by validation errors:\n" + "\n".join(f"- {e.get('field_path')}: {e.get('message')}" for e in errors), {"issues": issues})
        if sess.collection == "rooms":
            rec = sess.working_record or {}
            if not str(rec.get("name") or "").strip():
                return BuilderResult(False, "Save blocked by validation errors:\n- name: Room name is required.")
            if not isinstance(rec.get("exits", {}), dict):
                return BuilderResult(False, "Save blocked by validation errors:\n- exits: Room exits must be a dictionary.")
            issues = self._validate_room_extra_descriptions(rec)
            errors = [i for i in issues if i.startswith("error:")]
            if errors:
                return BuilderResult(False, "Save blocked by validation errors:\n" + "\n".join(f"- {e[6:]}" for e in errors), {"issues": issues})
            rec["extra_descriptions"] = normalize_room_extra_descriptions(rec.get("extra_descriptions"), sess.object_id)
        if sess.collection == "items":
            issues = validate_object_template(normalize_object_template(sess.object_id, sess.working_record))
            errors = [i for i in issues if i.get("severity") == "error"]
            if errors:
                return BuilderResult(False, "Save blocked by validation errors:\n" + "\n".join(f"- {e.get('field_path')}: {e.get('message')}" for e in errors), {"issues": issues})
        res = self.mutate(actor, sess.collection, sess.object_id, deepcopy(sess.working_record), "session save", expected_revision=sess.draft_revision)
        if res.ok:
            sess.draft_revision = int((res.data or {}).get("_builder_revision") or sess.draft_revision)
            sess.savepoint = deepcopy(res.data or sess.working_record); sess.dirty = False; sess.saved = True
        return res

    def _parse_field_value(self, sess: BuilderEditSession, f: OlcFieldDescriptor | None, text: str) -> BuilderResult:
        if not f: return BuilderResult(False, "No active field.")
        raw = text.strip()
        if raw == "":
            return BuilderResult(False, f"{f.label} requires an explicit value; blank input is not accepted.")
        if raw.lower() in {"clear","none","unset"}:
            if f.required: return BuilderResult(False, f"{f.label} is required and cannot be cleared.")
            return BuilderResult(True, "", {"value": None})
        try:
            if f.input_type == "integer":
                if not re.fullmatch(r"[0-9]+", raw):
                    return BuilderResult(False, f"{f.label} must be a whole number.")
                val = int(raw)
                if f.minimum is not None and val < f.minimum: return BuilderResult(False, f"{f.label} must be between {f.minimum} and {f.maximum}.")
                if f.maximum is not None and val > f.maximum: return BuilderResult(False, f"{f.label} must be between {f.minimum} and {f.maximum}.")
                return BuilderResult(True, "", {"value": val})
            if f.input_type == "enum":
                choices = {c.lower(): c for c in f.choices}
                if raw.lower() not in choices: return BuilderResult(False, f"{f.label} must be one of: {', '.join(f.choices)}.")
                return BuilderResult(True, "", {"value": choices[raw.lower()]})
            if f.input_type == "boolean":
                if raw.lower() in {"yes", "true", "on", "1"}: return BuilderResult(True, "", {"value": True})
                if raw.lower() in {"no", "false", "off", "0"}: return BuilderResult(True, "", {"value": False})
                return BuilderResult(False, f"{f.label} must be yes/no, true/false, on/off, or 1/0.")
            if f.input_type == "slug":
                if not re.fullmatch(r"[a-zA-Z0-9_:-]+", raw): return BuilderResult(False, f"{f.label} must be an identifier using letters, numbers, underscore, colon, or dash.")
                return BuilderResult(True, "", {"value": raw})
            return BuilderResult(True, "", {"value": raw})
        except Exception as exc:
            return BuilderResult(False, f"Could not parse {f.label}: {exc}")

    def _apply_field_value(self, actor: Any, sess: BuilderEditSession, f: OlcFieldDescriptor | None, value: Any, prefix: str = "") -> BuilderResult:
        if not f: return BuilderResult(False, "No active field.")
        before = self._get_path(sess.working_record, f.path)
        if before == value:
            sess.mode = "section_menu"; sess.active_field = ""
            sess.dirty = sess.working_record != sess.savepoint; sess.saved = not sess.dirty
            return BuilderResult(True, f"{f.label} unchanged.\n" + self.render_session(sess), sess.working_record)
        self._session_checkpoint(sess)
        self._set_path(sess.working_record, f.path, value)
        if sess.collection == "entities":
            sess.working_record = self._normalize_entity_updates(sess.object_id, sess.working_record)
        sess.dirty = sess.working_record != sess.savepoint; sess.saved = not sess.dirty
        sess.dirty_fields = sorted(set(sess.dirty_fields + [".".join(f.path)]))
        next_mode = "oedit_values" if sess.editor_type == "oedit" and sess.section == "values" else "section_menu"
        keep_field = False
        if f.input_type == "flag_set":
            next_mode = "flag_editor"; keep_field = True
        elif f.input_type in {"string_list", "list"}:
            next_mode = "list_editor"; keep_field = True
        sess.mode = next_mode; sess.active_field = f.key if keep_field else ""; sess.field_input_type = ""; sess.pending_value = None; sess.multiline_lines = []
        msg = prefix or f"{f.label} changed from {self._fmt_value(before)} to {self._fmt_value(value)}."
        return BuilderResult(True, msg + "\n" + self.render_session(sess), sess.working_record)

    def _validate_room_extra_descriptions(self, rec: dict[str, Any]) -> list[str]:
        return validate_room_extra_descriptions(rec)

    def _room_dependencies(self, actor: Any, room_id: str) -> list[str]:
        records = self.resolve_collection_records(actor, "rooms")
        deps: list[str] = []
        for rid, room in records.items():
            if str(rid) == str(room_id):
                continue
            for direction, ex in (room.get("exits") or {}).items() if isinstance(room, dict) else []:
                if isinstance(ex, dict) and str(ex.get("target_room_id") or ex.get("destination_room_id") or ex.get("room_id") or "") == str(room_id):
                    deps.append(f"inbound exit from room {rid} {direction}")
        drafts = self.workspace.load(self.workspace.world_id(actor))
        for zid, z in (drafts.get("zones") or {}).items():
            if room_id in [str(x) for x in (z or {}).get("room_ids") or []]: deps.append(f"zone membership {zid}")
        for sid, sp in (self.resolve_collection_records(actor, "spawns") or {}).items():
            if room_id in json.dumps(sp, default=str): deps.append(f"spawn/reset reference {sid}")
        for sid, rs in (self.resolve_collection_records(actor, "resets") or {}).items():
            if room_id in json.dumps(rs, default=str): deps.append(f"reset reference {sid}")
        if str(getattr(actor, "room_id", "")) == str(room_id): deps.append("your character is currently in this room")
        return sorted(set(deps))

    def _room_extras(self, sess: BuilderEditSession) -> list[dict[str, Any]]:
        extras = normalize_room_extra_descriptions((sess.working_record or {}).get("extra_descriptions"), sess.object_id)
        sess.working_record["extra_descriptions"] = extras
        return extras

    def _extra_preview(self, entry: dict[str, Any], limit: int = 72) -> str:
        text = " ".join(str(entry.get("description") or "").split())
        return text[:limit-3] + "..." if len(text) > limit else (text or "(empty description)")

    def _render_room_extra_list(self, sess: BuilderEditSession) -> str:
        rec = sess.working_record or {}; extras = self._room_extras(sess)
        lines = [f"-- Room Extra Descriptions: [{self._room_display_id(rec, sess.object_id)}] {rec.get('name') or sess.object_id}", f"Draft status: {'modified' if sess.dirty else 'clean'}", ""]
        if not extras:
            lines.append("- none")
        for i, entry in enumerate(extras, 1):
            status = "" if entry.get("enabled", True) else " [disabled]"
            lines += [f"{i}) {' '.join(entry.get('keywords') or [])}{status}", f"   {self._extra_preview(entry)}"]
        lines += ["", "A) Add", "E) Edit/select", "D) Delete", "C) Copy", "M) Move", "T) Toggle", "Q) Back", "Commands: number, add, edit <#>, delete <#>, copy <#>, move <#> up|down|to <#>, toggle <#>, back"]
        return "\n".join(lines)

    def _render_room_extra_entry(self, sess: BuilderEditSession) -> str:
        extras = self._room_extras(sess)
        if not extras:
            return self._render_room_extra_list(sess)
        sess.active_extra_index = max(0, min(sess.active_extra_index, len(extras)-1))
        entry = extras[sess.active_extra_index]
        lines = [f"-- Room Extra Description Entry {sess.active_extra_index + 1} of {len(extras)}", f"Room: {sess.object_id}", ""]
        lines.append(f"1) Keywords    : {' '.join(entry.get('keywords') or [])}")
        lines.append("2) Description :")
        lines.extend(["   " + line for line in (str(entry.get("description") or "").splitlines() or [""])])
        lines += [f"3) Previous description: {'Available' if sess.active_extra_index > 0 else 'Not Set.'}", f"4) Next description    : {'Available' if sess.active_extra_index + 1 < len(extras) else 'Not Set.'}", "C) Copy entry", "D) Delete entry", "Q) Back", "Commands: 1 keywords, 2 description, 3/prev, 4/next, copy, delete, back"]
        return "\n".join(lines)

    def _mark_room_extra_change(self, actor: Any, sess: BuilderEditSession, before: list[dict[str, Any]], message: str, *, entry_index: int | None = None) -> BuilderResult:
        after = self._room_extras(sess)
        if before != after:
            self._session_checkpoint(sess)
            sess.undo_stack[-1]["extra_descriptions"] = before
            sess.dirty = sess.working_record != sess.savepoint; sess.saved = not sess.dirty
            sess.dirty_fields = sorted(set(sess.dirty_fields + ["extra_descriptions"]))
            try:
                self.workspace.audit(actor, sess.world_id, message.lower(), "rooms", sess.object_id, {"extra_descriptions": before}, {"extra_descriptions": after})
            except Exception:
                pass
        if entry_index is not None:
            sess.active_extra_index = max(0, min(entry_index, max(len(after)-1, 0)))
        return BuilderResult(True, message + "\n" + (self._render_room_extra_entry(sess) if sess.section == "extra_entry" and after else self._render_room_extra_list(sess)), sess.working_record)

    def _handle_room_extra_list(self, actor: Any, sess: BuilderEditSession, text: str, low: str) -> BuilderResult:
        parts = text.split(); extras = self._room_extras(sess)
        if low in {"q","back","quit","0"}:
            sess.section = ""; sess.mode = "main_menu"; sess.active_field = ""
            return BuilderResult(True, self._render_redit_menu(sess))
        cmd = parts[0].lower() if parts else ""
        if low.isdigit() and 1 <= int(low) <= len(extras):
            sess.section = "extra_entry"; sess.active_extra_index = int(low)-1
            return BuilderResult(True, self._render_room_extra_entry(sess))
        if cmd in {"e","edit","select"} and len(parts) > 1 and parts[1].isdigit() and 1 <= int(parts[1]) <= len(extras):
            sess.section = "extra_entry"; sess.active_extra_index = int(parts[1])-1
            return BuilderResult(True, self._render_room_extra_entry(sess))
        if cmd in {"a","add"}:
            sess.mode = "room_extra_keywords"; sess.section = "extra_add"; sess.pending_value = {"id": "rextra_" + hashlib.sha1(f"{sess.object_id}:{time.time()}".encode()).hexdigest()[:10]}
            return BuilderResult(True, "Enter one or more keywords for the new extra description, or Q to cancel.")
        target = int(parts[1])-1 if len(parts) > 1 and parts[1].isdigit() else (int(parts[0])-1 if parts and parts[0].isdigit() else -1)
        if cmd in {"d","delete"} and 0 <= target < len(extras):
            sess.confirmation_type = "extra_delete"; sess.pending_value = target
            return BuilderResult(True, f"Delete extra description {target+1}: {' '.join(extras[target].get('keywords') or [])}\n{self._extra_preview(extras[target], 120)}\nType DELETE DESCRIPTION to confirm, or Q to cancel.")
        if cmd in {"c","copy"} and 0 <= target < len(extras):
            before = deepcopy(extras); new = deepcopy(extras[target]); new["id"] = "rextra_" + hashlib.sha1(f"{sess.object_id}:copy:{time.time()}".encode()).hexdigest()[:10]
            extras.insert(target+1, new); sess.working_record["extra_descriptions"] = normalize_room_extra_descriptions(extras, sess.object_id); sess.section = "extra_entry"
            return self._mark_room_extra_change(actor, sess, before, "Extra description copied. Warning: duplicate keywords may make look/examine choose the first matching entry.", entry_index=target+1)
        if cmd in {"t","toggle"} and 0 <= target < len(extras):
            before = deepcopy(extras); extras[target]["enabled"] = not extras[target].get("enabled", True); sess.working_record["extra_descriptions"] = extras
            return self._mark_room_extra_change(actor, sess, before, "Extra description toggled.")
        if cmd in {"m","move"} and 0 <= target < len(extras):
            before = deepcopy(extras); dest = target
            if len(parts) >= 3 and parts[2].lower() == "up": dest = target - 1
            elif len(parts) >= 3 and parts[2].lower() == "down": dest = target + 1
            elif len(parts) >= 4 and parts[2].lower() == "to" and parts[3].isdigit(): dest = int(parts[3])-1
            if not (0 <= dest < len(extras)): return BuilderResult(False, "Move target is out of range.\n" + self._render_room_extra_list(sess))
            entry = extras.pop(target); extras.insert(dest, entry); sess.working_record["extra_descriptions"] = normalize_room_extra_descriptions(extras, sess.object_id)
            return self._mark_room_extra_change(actor, sess, before, "Extra descriptions reordered.")
        return BuilderResult(False, "Choose a listed entry or use add, edit <#>, delete <#>, copy <#>, move <#> up|down|to <#>, toggle <#>, or Q.\n" + self._render_room_extra_list(sess))

    def _handle_room_extra_entry(self, actor: Any, sess: BuilderEditSession, text: str, low: str) -> BuilderResult:
        extras = self._room_extras(sess)
        if not extras:
            sess.section = "extra_list"; return BuilderResult(True, self._render_room_extra_list(sess))
        if low in {"q","back","quit","0"}:
            sess.section = "extra_list"; sess.mode = "section_menu"; return BuilderResult(True, self._render_room_extra_list(sess))
        if low in {"1","keywords"}:
            sess.mode = "room_extra_keywords"; sess.pending_value = {"edit_index": sess.active_extra_index}
            return BuilderResult(True, f"Current keywords: {' '.join(extras[sess.active_extra_index].get('keywords') or [])}\nEnter replacement keywords, or Q to cancel.")
        if low in {"2","description"}:
            sess.mode = "multiline_text"; sess.active_field = f"extra:{sess.active_extra_index}:description"; sess.multiline_lines = []
            return BuilderResult(True, self._render_multiline(sess))
        if low in {"3","prev","previous"}:
            if sess.active_extra_index <= 0: return BuilderResult(False, "Already at the first extra description.\n" + self._render_room_extra_entry(sess))
            sess.active_extra_index -= 1; return BuilderResult(True, self._render_room_extra_entry(sess))
        if low in {"4","next"}:
            if sess.active_extra_index + 1 >= len(extras): return BuilderResult(False, "Already at the last extra description.\n" + self._render_room_extra_entry(sess))
            sess.active_extra_index += 1; return BuilderResult(True, self._render_room_extra_entry(sess))
        if low in {"c","copy"}:
            return self._handle_room_extra_list(actor, sess, f"copy {sess.active_extra_index+1}", "copy")
        if low in {"d","delete"}:
            return self._handle_room_extra_list(actor, sess, f"delete {sess.active_extra_index+1}", "delete")
        return BuilderResult(False, "Choose 1, 2, 3, 4, C, D, or Q.\n" + self._render_room_extra_entry(sess))

    def _handle_redit_confirmation(self, actor: Any, sess: BuilderEditSession, text: str, low: str) -> BuilderResult | None:
        if sess.confirmation_type == "redit_copy":
            if low in {"q","quit","cancel","back"}: sess.confirmation_type=""; return BuilderResult(True,"Copy room cancelled.\n"+self._render_redit_menu(sess))
            dest = text.strip()
            if not re.fullmatch(r"[A-Za-z0-9_:-]+", dest): return BuilderResult(False,"Target room ID must be an identifier, or Q to cancel.")
            if self._record(self.workspace.world_id(actor), "rooms", dest) is not None or dest in self.resolve_collection_records(actor, "rooms"):
                return BuilderResult(False, f"Room {dest} already exists; copy never overwrites silently.")
            denied = self._check_permission(actor, "rooms", dest, "mutate")
            if denied: return denied
            sess.pending_value = dest; sess.confirmation_type = "redit_copy_confirm"
            return BuilderResult(True, f"Clone current room draft to {dest}? Outgoing exits are copied; inbound/reverse links and reset populations are not. Type COPY ROOM to confirm, or Q to cancel.")
        if sess.confirmation_type == "redit_copy_confirm":
            if low in {"q","quit","cancel","back"}: sess.confirmation_type=""; return BuilderResult(True,"Copy room cancelled.\n"+self._render_redit_menu(sess))
            if low != "copy room": return BuilderResult(False,"Type COPY ROOM to confirm, or Q to cancel.")
            dest = str(sess.pending_value or "")
            rec = deepcopy(sess.working_record); rec["id"] = dest; rec["name"] = str(rec.get("name") or dest).strip(); rec.pop("_builder_revision", None)
            lock = self.acquire_lock(actor, "rooms", dest, admin=True)
            if not lock.ok: return lock
            try: res = self.mutate(actor, "rooms", dest, rec, "redit copy", admin_override=True)
            finally: self.release_lock(actor, "rooms", dest)
            sess.confirmation_type=""; sess.pending_value=None
            return BuilderResult(res.ok, res.message + (f"\nCopied room draft {dest}. Current editor remains on {sess.object_id}. Reverse exits/inbound links were not created.\n" + self._render_redit_menu(sess) if res.ok else ""), res.data)
        if sess.confirmation_type == "redit_delete":
            if low in {"q","quit","cancel","back"}: sess.confirmation_type=""; return BuilderResult(True,"Delete room cancelled.\n"+self._render_redit_menu(sess))
            if text.strip() != "DELETE ROOM": return BuilderResult(False,"Type DELETE ROOM to confirm deletion, or Q to cancel.")
            deps = self._room_dependencies(actor, sess.object_id)
            if deps: return BuilderResult(False,"Delete protected; dependencies exist:\n"+"\n".join(f"- {d}" for d in deps)+"\nMove/remove dependencies before deleting.\n"+self._render_redit_menu(sess))
            self.sessions.end(actor); return self.workspace.delete(actor, "rooms", sess.object_id, "room")
        return None

    def handle_session_input(self, actor: Any, sess: BuilderEditSession, text: str) -> BuilderResult:
        low = text.lower().strip(); sess.last_activity_at = self.workspace.stamp()
        parts = text.split()
        cancel_words = {"q","quit","cancel","back"}
        if sess.mode == "multiline_text":
            if low == ".cancel" or low in cancel_words:
                if str(sess.active_field).startswith("extra:"):
                    if str(sess.active_field) == "extra:new:description":
                        sess.mode = "section_menu"; sess.section = "extra_list"; sess.active_field = ""; sess.multiline_lines = []; sess.pending_value = None
                        return BuilderResult(True, "New extra description cancelled.\n" + self._render_room_extra_list(sess))
                    sess.mode = "section_menu"; sess.section = "extra_entry"; sess.active_field = ""; sess.multiline_lines = []
                    return BuilderResult(True, "Text edit cancelled.\n" + self._render_room_extra_entry(sess))
                sess.mode = "section_menu"; sess.active_field = ""; sess.multiline_lines = []
                return BuilderResult(True, "Text edit cancelled.\n" + self.render_session(sess))
            if low == ".help":
                return BuilderResult(True, ".save commits text, .cancel aborts, .clear clears pending text, .show displays pending text.")
            if low == ".show":
                body = "\n".join(f"{i+1}: {line}" for i, line in enumerate(sess.multiline_lines)) or "(empty)"
                return BuilderResult(True, body)
            if low == ".clear":
                sess.multiline_lines = []
                return BuilderResult(True, "Pending text cleared.")
            if low in {".save", ".end"}:
                if str(sess.active_field).startswith("extra:"):
                    if str(sess.active_field) == "extra:new:description":
                        new = "\n".join(sess.multiline_lines).rstrip()
                        if not new.strip():
                            return BuilderResult(False, "Description cannot be empty. Add text, .clear, .save, or .cancel.")
                        extras = self._room_extras(sess); before = deepcopy(extras)
                        pending = dict(sess.pending_value or {})
                        seed = "|".join([str(sess.object_id), str(len(extras)), " ".join(pending.get("keywords") or []), new[:40]])
                        entry = {"id": pending.get("id") or "rextra_" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:10], "keywords": pending.get("keywords") or [], "description": new}
                        extras.append(entry); sess.working_record["extra_descriptions"] = normalize_room_extra_descriptions(extras, sess.object_id)
                        sess.mode = "section_menu"; sess.section = "extra_entry"; sess.active_field = ""; sess.multiline_lines = []; sess.pending_value = None
                        return self._mark_room_extra_change(actor, sess, before, "Extra description added.", entry_index=len(extras)-1)
                    _, idx_text, _field_name = sess.active_field.split(":", 2)
                    idx = int(idx_text); extras = self._room_extras(sess)
                    new = "\n".join(sess.multiline_lines).rstrip()
                    if not new.strip():
                        return BuilderResult(False, "Description cannot be empty. Add text, .clear, .save, or .cancel.")
                    before = deepcopy(extras); extras[idx]["description"] = new; sess.working_record["extra_descriptions"] = extras
                    sess.mode = "section_menu"; sess.section = "extra_entry"; sess.multiline_lines = []; sess.active_field = ""
                    return self._mark_room_extra_change(actor, sess, before, "Extra description changed.", entry_index=idx)
                if str(sess.active_field).startswith("exit:"):
                    _, direction, field_name = sess.active_field.split(":", 2)
                    new = "\n".join(sess.multiline_lines).rstrip()
                    self._set_exit_field(sess, direction, {field_name: new})
                    sess.mode = "section_menu"; sess.section = "exit"; sess.multiline_lines = []; sess.active_field = ""
                    return BuilderResult(True, "Text saved.\n" + self._render_exit_editor(actor, sess), sess.working_record)
                f = self._descriptor(sess, sess.active_field)
                new = "\n".join(sess.multiline_lines).rstrip()
                return self._apply_field_value(actor, sess, f, new, "Text saved.")
            sess.multiline_lines.append(text)
            return BuilderResult(True, f"Line {len(sess.multiline_lines)} added. Use .show or .save.")
        if sess.mode == "room_extra_keywords":
            if low in cancel_words:
                adding = sess.section == "extra_add"
                sess.mode = "section_menu"; sess.section = "extra_list" if adding else "extra_entry"; sess.pending_value = None
                return BuilderResult(True, "Keyword edit cancelled.\n" + (self._render_room_extra_list(sess) if adding else self._render_room_extra_entry(sess)))
            keywords = normalize_extra_keywords(text)
            if not keywords:
                return BuilderResult(False, "Enter at least one usable keyword, or Q to cancel.")
            if sess.section == "extra_add":
                sess.pending_value = {**(sess.pending_value or {}), "keywords": keywords}
                sess.mode = "multiline_text"; sess.active_field = "extra:new:description"; sess.multiline_lines = []
                return BuilderResult(True, "Enter the multiline description. Use .save to create the entry or .cancel to abort.")
            idx = int((sess.pending_value or {}).get("edit_index", sess.active_extra_index)); extras = self._room_extras(sess)
            before = deepcopy(extras); extras[idx]["keywords"] = keywords; sess.working_record["extra_descriptions"] = extras
            sess.mode = "section_menu"; sess.pending_value = None
            return self._mark_room_extra_change(actor, sess, before, "Extra description keywords changed.", entry_index=idx)
        if sess.mode == "field_prompt":
            if low in cancel_words:
                sess.mode = "section_menu"; sess.active_field = ""
                return BuilderResult(True, "Edit cancelled.\n" + self.render_session(sess))
            f = self._descriptor(sess, sess.active_field)
            parsed = self._parse_field_value(sess, f, text)
            if not parsed.ok:
                return BuilderResult(False, parsed.message + "\n" + self._render_field_prompt(sess))
            return self._apply_field_value(actor, sess, f, parsed.data["value"])
        if sess.mode == "flag_editor":
            f = self._descriptor(sess, sess.active_field)
            if low in {"u","undo"}:
                if not sess.undo_stack: return BuilderResult(False, "Nothing to undo.")
                sess.redo_stack.append(deepcopy(sess.working_record)); sess.working_record = sess.undo_stack.pop(); sess.dirty = sess.working_record != sess.savepoint; sess.saved = not sess.dirty
                return BuilderResult(True, "Session undo applied.\n" + self._render_flag_editor(sess))
            if low in {"r","redo"}:
                if not sess.redo_stack: return BuilderResult(False, "Nothing to redo.")
                sess.undo_stack.append(deepcopy(sess.working_record)); sess.working_record = sess.redo_stack.pop(); sess.dirty = sess.working_record != sess.savepoint; sess.saved = not sess.dirty
                return BuilderResult(True, "Session redo applied.\n" + self._render_flag_editor(sess))
            if low in {"v","validate"}:
                issues = MobileTemplate.from_legacy(sess.working_record).validate() if sess.collection == "entities" else validate_object_template(normalize_object_template(sess.object_id, sess.working_record))
                lines=[f"{x['severity']}: {x['field_path']} {x['message']}" for x in issues] or ["- no focused issues"]
                return BuilderResult(not any(x.get("severity")=="error" for x in issues), "Validation for %s:\n%s" % (sess.object_id, "\n".join(lines)), {"issues": issues})
            if low in cancel_words or low == "0":
                if sess.editor_type == "medit": sess.section = ""
                sess.mode = "section_menu"; sess.active_field = ""
                return BuilderResult(True, self.render_session(sess))
            cur = set(self._get_path(sess.working_record, f.path) or [])
            if low in {"none","clear"}: new = []
            elif low == "all": new = list(f.flags)
            elif low.isdigit() and 1 <= int(low) <= len(f.flags):
                flag = f.flags[int(low)-1]
                (cur.remove if flag in cur else cur.add)(flag); new = sorted(cur)
            elif low in set(f.flags):
                (cur.remove if low in cur else cur.add)(low); new = sorted(cur)
            else:
                return BuilderResult(False, "Choose a flag number/name, all, none, clear, or Q.\n" + self._render_flag_editor(sess))
            return self._apply_field_value(actor, sess, f, new, "Flag selection updated.")
        if sess.mode == "list_editor":
            f = self._descriptor(sess, sess.active_field)
            if low in cancel_words:
                sess.mode = "section_menu"; sess.active_field = ""
                return BuilderResult(True, self.render_session(sess))
            cur = self._get_path(sess.working_record, f.path)
            cur = list(cur) if isinstance(cur, list) else []
            cmd = parts[0].lower() if parts else "list"
            if cmd == "list": return BuilderResult(True, self._render_list_editor(sess))
            if cmd == "add" and len(parts) > 1:
                val = " ".join(parts[1:]).strip()
                if val.lower() in {str(x).lower() for x in cur}: return BuilderResult(False, "Duplicate list value rejected.")
                cur.append(val)
            elif cmd == "remove" and len(parts) > 1:
                tok = " ".join(parts[1:])
                if tok.isdigit() and 1 <= int(tok) <= len(cur): cur.pop(int(tok)-1)
                else: cur = [x for x in cur if str(x) != tok]
            elif cmd == "move" and len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
                a,b = int(parts[1])-1, int(parts[2])-1
                if not (0 <= a < len(cur) and 0 <= b < len(cur)): return BuilderResult(False, "Move indexes are out of range.")
                val = cur.pop(a); cur.insert(b, val)
            elif cmd == "clear": cur = []
            else: return BuilderResult(False, "Commands: list, add <value>, remove <number|value>, move <from> <to>, clear, back")
            return self._apply_field_value(actor, sess, f, cur, "List updated.")
        if sess.mode == "reference_selector":
            f = self._descriptor(sess, sess.active_field)
            if low in cancel_words:
                sess.mode = "section_menu"; sess.active_field = ""
                return BuilderResult(True, self.render_session(sess))
            if low.startswith("search "):
                sess.reference_filter = text[7:].strip()
                return BuilderResult(True, self._render_reference_selector(actor, sess))
            if low in {"unset","clear","none"} and not f.required:
                return self._apply_field_value(actor, sess, f, None, "Reference cleared.")
            records = list(self.resolve_collection_records(actor, f.reference_collection).items())
            if low.isdigit() and 1 <= int(low) <= len(records):
                return self._apply_field_value(actor, sess, f, records[int(low)-1][0], "Reference updated.")
            if low in dict(records):
                return self._apply_field_value(actor, sess, f, low, "Reference updated.")
            return BuilderResult(False, f'{f.label} reference "{text}" does not exist. Use search, a number, a stable ID, or Q.')
        if sess.mode == "oedit_values":
            if low in cancel_words:
                sess.mode = "main_menu"; sess.section = ""; sess.active_field = ""
                return BuilderResult(True, self.render_session(sess))
            if low in {"v", "validate"}:
                issues = validate_object_template(normalize_object_template(sess.object_id, sess.working_record))
                lines = [f"{x['severity']}: {x['field_path']} {x['message']}" for x in issues] or ["- no focused issues"]
                return BuilderResult(not any(x.get("severity") == "error" for x in issues), "Validation for %s:\n%s" % (sess.object_id, "\n".join(lines)), {"issues": issues})
            if low in {"p", "preview", "r"}:
                return self._session_preview(actor, sess)
            if low in {"u", "undo"}:
                if not sess.undo_stack: return BuilderResult(False, "Nothing to undo.")
                sess.redo_stack.append(deepcopy(sess.working_record)); sess.working_record = sess.undo_stack.pop(); sess.dirty = sess.working_record != sess.savepoint; sess.saved = not sess.dirty
                return BuilderResult(True, "Session undo applied.\n" + self._render_oedit_values_editor(sess))
            if low in {"y", "redo"}:
                if not sess.redo_stack: return BuilderResult(False, "Nothing to redo.")
                sess.undo_stack.append(deepcopy(sess.working_record)); sess.working_record = sess.redo_stack.pop(); sess.dirty = sess.working_record != sess.savepoint; sess.saved = not sess.dirty
                return BuilderResult(True, "Session redo applied.\n" + self._render_oedit_values_editor(sess))
            if low in {"s", "save"}:
                return self._session_save(actor, sess)
            desc = self._descriptor(sess, low)
            if not desc:
                return BuilderResult(False, "Choose a value number, validate, preview, undo, redo, save, or Q.\n" + self._render_oedit_values_editor(sess))
            sess.active_field = desc.key
            if desc.input_type in {"string_list", "list"}:
                sess.mode = "list_editor"; return BuilderResult(True, self._render_list_editor(sess))
            sess.mode = "field_prompt"; return BuilderResult(True, self._render_field_prompt(sess))
        if sess.quit_pending:
            if low in {"save", "s"}:
                sess.quit_pending = False
                res = self._session_save(actor, sess)
                if res.ok:
                    self.sessions.end(actor)
                    return BuilderResult(True, res.message + "\nEditor saved, closed, and lock released.", res.data)
                return res
            if low in {"discard", "d", "no", "n"}:
                self.sessions.end(actor)
                return BuilderResult(True, "Editor changes discarded; lock released.")
            if low in {"cancel", "c", "back"}:
                sess.quit_pending = False
                return BuilderResult(True, ("Continue editing." if sess.editor_type == "redit" else "Quit cancelled.") + "\n" + self.render_session(sess))
            if sess.editor_type == "redit":
                return BuilderResult(False, "You have unsaved room changes.\n\nS) Save Draft\nD) Discard Changes\nC) Continue Editing")
            return BuilderResult(False, "Unsaved changes: type Save, Discard, or Cancel.")
        if parts and parts[0].lower() == "name" and len(parts) > 1:
            self._session_checkpoint(sess)
            sess.working_record["name"] = text[len(parts[0]):].strip(); sess.dirty = True; sess.saved = False
            return BuilderResult(True, "Updated session scratch.\n" + self.render_session(sess))
        if parts and parts[0].lower() == "body" and len(parts) > 1:
            prof, bp, weapons = self._body_profile_result(actor, parts[1], scratch=sess.working_record)
            if not bp:
                return BuilderResult(False, "Unknown body profile. Choose: " + ", ".join(self.body_profiles(actor)))
            self._session_checkpoint(sess)
            sess.working_record.pop("natural_weapons", None)
            sess.working_record.pop("natural_attacks", None)
            sess.working_record["body_profile_id"] = prof
            sess.working_record.setdefault("combat_profile", {})["body_profile"] = prof
            sess.working_record.setdefault("combat_profile", {})["natural_weapons"] = weapons
            sess.dirty = True; sess.saved = False
            return BuilderResult(True, "Updated session scratch.\n" + self.render_session(sess))
        if low in {"?", "help"} or low.startswith("help "):
            topic = low[5:].strip() if low.startswith("help ") else ""
            if topic in {"equipment", "loadout"}: return BuilderResult(True, "Equipment help: assign wearable object templates to canonical wear slots with assign <slot> <object> [chance] [qty]; carried items use carry <object> [chance] [qty]. Template draft data, not live instances.")
            if topic in {"spawn", "spawns", "spawn maximum"}: return BuilderResult(True, "Spawn help: add <room> [max] [chance] creates a canonical spawn/reset draft reference. Max must be positive; chance is 0-100. Live world changes only after publish.")
            if topic in {"damage dice", "action flags", "capacity"}: return BuilderResult(True, f"{topic.title()} help: edit through the structured field menu; values are validated immediately and saved only to Builder drafts.")
            return BuilderResult(True, "Builder help: use menu numbers; structured editors support preview, validate, undo, redo, save, and back. Use help equipment, help spawn maximum, help action flags, help damage dice, or help capacity.")
        if sess.editor_type == "redit" and sess.confirmation_type:
            if sess.confirmation_type == "extra_delete":
                if low in cancel_words:
                    sess.confirmation_type = ""; sess.pending_value = None
                    return BuilderResult(True, "Delete cancelled.\n" + (self._render_room_extra_entry(sess) if sess.section == "extra_entry" else self._render_room_extra_list(sess)))
                if text.strip() != "DELETE DESCRIPTION":
                    return BuilderResult(False, "Type DELETE DESCRIPTION to confirm deletion, or Q to cancel.")
                extras = self._room_extras(sess); idx = int(sess.pending_value)
                if not (0 <= idx < len(extras)):
                    sess.confirmation_type = ""; sess.pending_value = None
                    return BuilderResult(False, "Extra description no longer exists.\n" + self._render_room_extra_list(sess))
                before = deepcopy(extras); extras.pop(idx); sess.working_record["extra_descriptions"] = normalize_room_extra_descriptions(extras, sess.object_id)
                sess.confirmation_type = ""; sess.pending_value = None; sess.section = "extra_list"
                return self._mark_room_extra_change(actor, sess, before, "Extra description deleted.")
            handled = self._handle_redit_confirmation(actor, sess, text, low)
            if handled is not None: return handled
        if sess.editor_type == "redit" and sess.section == "exit":
            return self._handle_exit_editor(actor, sess, text, low)
        if sess.editor_type == "redit" and sess.section == "extra_list":
            return self._handle_room_extra_list(actor, sess, text, low)
        if sess.editor_type == "redit" and sess.section == "extra_entry":
            return self._handle_room_extra_entry(actor, sess, text, low)
        if sess.editor_type == "redit" and not sess.section:
            rmap = {"1":"name","2":"description","3":"room_flags","4":"sector"}
            if low in rmap:
                field = rmap[low]; desc = self._descriptor(sess, field); sess.active_field = field
                if desc.input_type == "multiline": sess.mode = "multiline_text"; sess.multiline_lines = []; return BuilderResult(True, self._render_multiline(sess))
                if desc.input_type == "flag_set": sess.mode = "flag_editor"; return BuilderResult(True, self._render_flag_editor(sess))
                sess.mode = "field_prompt"; return BuilderResult(True, self._render_field_prompt(sess))
            if low in {"5","6","7","8","9","a"}:
                idx = {"5":0,"6":1,"7":2,"8":3,"9":4,"a":5}[low]; direction = REDIT_DIRECTIONS[idx]
                sess.section = "exit"; sess.mode = "section_menu"; sess.active_direction = direction
                return BuilderResult(True, self._render_exit_editor(actor, sess))
            if low == "f":
                sess.section = "extra_list"; sess.mode = "section_menu"; sess.active_field = ""
                return BuilderResult(True, self._render_room_extra_list(sess))
            if low == "r": return BuilderResult(True, "Room reset editing is not yet available in REDIT. Use existing reset/spawn Builder commands for detailed reset work.\n" + self._render_redit_menu(sess))
            if low == "s": return BuilderResult(True, "Script attachment editing is not yet available until script runtime support is enabled for rooms.\n" + self._render_redit_menu(sess))
            if low == "w": sess.confirmation_type="redit_copy"; return BuilderResult(True, "Copy room: enter a new target room ID, or Q to cancel.")
            if low == "x":
                deps = self._room_dependencies(actor, sess.object_id)
                summary = "\n".join(f"- {d}" for d in deps) if deps else "- no blocking dependencies found"
                sess.confirmation_type="redit_delete"
                return BuilderResult(True, "Delete room safety check:\n" + summary + "\nType DELETE ROOM to confirm deletion, or Q to cancel.")

        if sess.editor_type == "oedit" and sess.confirmation_type:
            if sess.confirmation_type in {"copy", "copy_destination", "copy_source"}:
                if low in cancel_words: sess.confirmation_type = ""; return BuilderResult(True, "Copy cancelled.\n" + self._render_oedit_menu(sess))
                if sess.confirmation_type == "copy":
                    if low.startswith("from "):
                        src = text.split(None, 1)[1].strip()
                        if not src: return BuilderResult(False, "Enter: from <source_object_id>, to <new_object_id>, or Q to cancel.")
                        rows = self.content_query.by_id_or_vnum(actor, "object", src)
                        if len(rows) != 1: return BuilderResult(False, "Source object is missing or ambiguous; use an exact object ID or VNUM.")
                        sess.pending_value = rows[0].canonical_id; sess.confirmation_type = "copy_source"
                        return BuilderResult(True, f"Copy {rows[0].canonical_id} into current draft {sess.object_id}? Type COPY SOURCE to confirm, or Q to cancel.")
                    if low.startswith("to "):
                        dest = text.split(None, 1)[1].strip()
                    else:
                        dest = text.strip()
                    if not re.fullmatch(r"[A-Za-z0-9_:-]+", dest): return BuilderResult(False, "Destination object ID must be an identifier, or Q to cancel.")
                    if self._record(self.workspace.world_id(actor), "items", dest) is not None:
                        return BuilderResult(False, f"Object {dest} already exists; choose another destination. Copy never overwrites silently.")
                    sess.pending_value = dest; sess.confirmation_type = "copy_destination"
                    return BuilderResult(True, f"Clone current draft {sess.object_id} to new object {dest}? Type COPY DESTINATION to confirm, or Q to cancel.")
                if sess.confirmation_type == "copy_destination":
                    if low != "copy destination": return BuilderResult(False, "Type COPY DESTINATION to confirm cloning to a new object, or Q to cancel.")
                    dest = str(sess.pending_value or "")
                    lock = self.acquire_lock(actor, "items", dest, admin=True)
                    if not lock.ok:
                        return lock
                    try:
                        rec = deepcopy(sess.working_record); rec["id"] = dest; rec["name"] = dest.replace("_", " ").title(); rec["keywords"] = dest.replace("_", " ").split(); rec.pop("_builder_revision", None)
                        res = self.mutate(actor, "items", dest, rec, "oedit clone", admin_override=True)
                    finally:
                        self.release_lock(actor, "items", dest)
                    sess.confirmation_type = ""; sess.pending_value = None
                    return BuilderResult(res.ok, res.message + ("\n" + self._render_oedit_menu(sess) if res.ok else ""), res.data)
                if sess.confirmation_type == "copy_source":
                    if low != "copy source": return BuilderResult(False, "Type COPY SOURCE to replace the current draft with the selected source, or Q to cancel.")
                    src_id = str(sess.pending_value or "")
                    src = deepcopy(self.resolve_collection_records(actor, "items").get(src_id))
                    if not isinstance(src, dict): return BuilderResult(False, f"Source object {src_id} is no longer available.")
                    self._session_checkpoint(sess); src["id"] = sess.object_id; sess.working_record = normalize_object_template(sess.object_id, src); sess.dirty = sess.working_record != sess.savepoint; sess.saved = not sess.dirty
                    sess.confirmation_type = ""; sess.pending_value = None
                    return BuilderResult(True, f"Copied {src_id} into current draft {sess.object_id}.\n" + self._render_oedit_menu(sess), sess.working_record)
            if sess.confirmation_type == "delete":
                if low in cancel_words: sess.confirmation_type = ""; return BuilderResult(True, "Delete cancelled.\n" + self._render_oedit_menu(sess))
                if text.strip() != "DELETE": return BuilderResult(False, "Type DELETE to confirm deletion, or Q to cancel.")
                self.sessions.end(actor); return self.workspace.delete(actor, "items", sess.object_id, "item_template")
        if low in {"q", "quit"} and not str(sess.confirmation_type).startswith("medit_") and not str(sess.mode).startswith("medit_"):
            if sess.section and low == "q":
                sess.section = ""; sess.mode = "main_menu"
                return BuilderResult(True, self.render_session(sess))
            if sess.dirty:
                sess.quit_pending = True
                return BuilderResult(True, "You have unsaved room changes.\n\nS) Save Draft\nD) Discard Changes\nC) Continue Editing" if sess.editor_type == "redit" else "Unsaved changes: Save, Discard, or Cancel?")
            self.sessions.end(actor); return BuilderResult(True, "Editor closed and lock released.")
        if low in {"back", "cancel"}: sess.section=""; sess.mode="main_menu"; return BuilderResult(True, self.render_session(sess))
        stats_handled = self._handle_stats_menu(actor, sess, text, low)
        if stats_handled is not None:
            return stats_handled
        if sess.editor_type == "medit" and sess.section == "equipment":
            return self._handle_medit_loadout(actor, sess, text)
        if sess.editor_type == "medit" and sess.section == "spawns":
            return self._handle_spawns_editor(actor, sess, text)
        if sess.editor_type == "medit" and sess.section == "scripts":
            return self._handle_medit_scripts(actor, sess, text)
        if sess.editor_type == "medit" and sess.section in {"abilities", "combat_abilities", "reactions", "event_reactions", "ai"}:
            return self._handle_medit_advanced(actor, sess, text)
        if sess.section and sess.section != "natural_weapons":
            field_token = parts[0].lower() if parts else ""
            desc = self._descriptor(sess, field_token)
            if desc:
                if desc.read_only:
                    return BuilderResult(False, f"{desc.label} is read-only in this editor.")
                sess.active_field = desc.key
                if desc.input_type == "multiline":
                    sess.mode = "multiline_text"; sess.multiline_lines = []
                    return BuilderResult(True, self._render_multiline(sess))
                if desc.input_type == "flag_set":
                    sess.mode = "flag_editor"; return BuilderResult(True, self._render_flag_editor(sess))
                if desc.input_type in {"string_list","list"}:
                    sess.mode = "list_editor"; return BuilderResult(True, self._render_list_editor(sess))
                if desc.input_type == "reference":
                    sess.mode = "reference_selector"; sess.reference_filter = ""; return BuilderResult(True, self._render_reference_selector(actor, sess))
                sess.mode = "field_prompt"; return BuilderResult(True, self._render_field_prompt(sess))
        if sess.editor_type == "oedit" and not sess.section:
            oedit_map = {"1":"keywords","2":"short_description","3":"long_description","4":"look_description","5":"item_type","6":"extra_flags","7":"wear_flags","8":"weight","9":"cost","a":"cost_per_day","b":"destroy_timer","c":"values","d":"affects","e":"extra_descriptions","m":"min_level","p":"perm_affects","s":"scripts"}
            if low in oedit_map:
                field = oedit_map[low]; desc = self._descriptor(sess, field); sess.active_field = field
                if field == "scripts" and not sess.working_record.get("scripts"):
                    return BuilderResult(True, "Script editing is unavailable until DG/script runtime support is enabled for this object.\n" + self._render_oedit_menu(sess))
                if field == "values":
                    sess.section = "values"; sess.mode = "oedit_values"; sess.active_field = ""
                    return BuilderResult(True, self._render_oedit_values_editor(sess))
                if desc.input_type == "multiline": sess.mode = "multiline_text"; sess.multiline_lines = []; return BuilderResult(True, self._render_multiline(sess))
                if desc.input_type == "flag_set": sess.mode = "flag_editor"; return BuilderResult(True, self._render_flag_editor(sess))
                if desc.input_type in {"string_list","list"}: sess.mode = "list_editor"; return BuilderResult(True, self._render_list_editor(sess))
                sess.mode = "field_prompt"; return BuilderResult(True, self._render_field_prompt(sess))
            if low == "w":
                sess.confirmation_type = "copy"; return BuilderResult(True, "Copy object:\n- to <new_object_id> clones the current object into a new draft.\n- from <source_object_id> copies another object into this draft after confirmation.\nEnter a destination ID as shorthand for to <new_object_id>, or Q to cancel.")
            if low == "x":
                deps = self.object_dependencies(actor, sess.object_id).data.get("matches", []) if self.object_dependencies(actor, sess.object_id).data else []
                if deps: return BuilderResult(False, "Delete protected; dependencies exist:\n" + "\n".join(f"- {d}" for d in deps) + "\n" + self._render_oedit_menu(sess))
                sess.confirmation_type = "delete"; return BuilderResult(True, "Delete object: type DELETE to confirm, or Q to cancel.")
        if sess.editor_type != "medit" and low in {"1","fields","edit"}:
            sess.section = "fields"; sess.mode = "section_menu"; return BuilderResult(True, self.render_session(sess))
        if sess.editor_type == "medit" and not sess.section:
            main_map = {"9":"attributes", "stats":"attributes", "i":"identity", "identity":"identity", "a":"mobile_flags", "b":"affect_flags", "r":"equipment", "loadout":"equipment", "loot":"equipment", "s":"scripts", "script":"scripts", "u":"combat_abilities", "combat abilities":"combat_abilities", "v":"event_reactions", "event reactions":"event_reactions"}
            if low in main_map:
                sess.section = main_map[low]; sess.mode = "section_menu"; sess.active_field = ""
                return BuilderResult(True, self.render_session(sess))
            field_map = {"1":"sex", "2":"keywords", "3":"short_description", "4":"room_description", "5":"look_description", "6":"spawn_position", "7":"default_position", "8":"attack_type", "p":"pet_price"}
            if low in field_map:
                fld = field_map[low]
                desc = {
                    "sex": OlcFieldDescriptor("sex","Sex",("sex",),"enum",choices=MEDIT_SEX_VALUES),
                    "keywords": OlcFieldDescriptor("keywords","Keywords",("keywords",),"string_list"),
                    "short_description": OlcFieldDescriptor("short_description","Short description",("short_description",),"string"),
                    "room_description": OlcFieldDescriptor("room_description","Long description",("room_description",),"multiline"),
                    "look_description": OlcFieldDescriptor("look_description","Detailed description",("look_description",),"multiline"),
                    "spawn_position": OlcFieldDescriptor("spawn_position","Position",("spawn_position",),"enum",choices=MEDIT_POSITIONS),
                    "default_position": OlcFieldDescriptor("default_position","Default position",("default_position",),"enum",choices=MEDIT_POSITIONS),
                    "attack_type": OlcFieldDescriptor("attack_type","Attack type",("combat_profile","attack_type"),"enum",choices=MEDIT_ATTACK_TYPES),
                    "pet_price": OlcFieldDescriptor("pet_price","Pet price",("pet_price",),"integer",minimum=0,maximum=100000000),
                }[fld]
                sess.active_field = desc.key; sess._medit_direct_descriptor = desc
                if desc.input_type == "multiline": sess.mode = "multiline_text"; sess.multiline_lines = []; return BuilderResult(True, self._render_multiline(sess))
                if desc.input_type == "string_list": sess.mode = "list_editor"; return BuilderResult(True, self._render_list_editor(sess))
                sess.mode = "field_prompt"; return BuilderResult(True, self._render_field_prompt(sess))
            if low == "w": sess.confirmation_type = "copy"; return BuilderResult(True, "Copy this mob to which new ID or VNUM?\nEnter destination or Q to cancel:")
            if low == "x": sess.confirmation_type = "delete"; return BuilderResult(True, f"WARNING: Delete mob [{(sess.working_record or {}).get('vnum') or sess.object_id}] {(sess.working_record or {}).get('name') or sess.object_id}?\nType DELETE to confirm or Q to cancel:")
        section_map = {"1":"identity","identity":"identity", "2":"keywords", "keywords":"keywords", "aliases":"keywords", "3":"descriptions", "descriptions":"descriptions", "4":"traits", "traits":"traits", "5":"attributes", "stats":"attributes", "stats menu":"attributes", "attributes":"attributes", "level":"attributes", "6":"resources", "resources":"resources", "7":"natural_weapons", "combat":"combat", "8":"body_weapons", "body":"body_weapons", "body profile":"body_weapons", "weapons":"natural_weapons", "natural":"natural_weapons", "natural weapons":"natural_weapons", "natural attacks":"natural_weapons", "9":"positions", "positions":"positions", "10":"mobile_flags", "flags":"mobile_flags", "mobile flags":"mobile_flags", "11":"affect_flags", "affects":"affect_flags", "12":"equipment", "equipment":"equipment", "13":"inventory", "inventory":"inventory", "14":"loot", "loot":"loot", "15":"abilities", "abilities":"abilities", "16":"ai", "ai":"ai", "behavior":"ai", "reactions":"event_reactions", "event reactions":"event_reactions", "combat abilities":"combat_abilities", "17":"faction", "faction":"faction", "18":"scripts", "scripts":"scripts", "19":"spawns", "spawns":"spawns", "spawn":"spawns", "20":"diagnostics", "diagnostics":"diagnostics"}
        if low in section_map:
            sess.section=section_map[low]; sess.mode="section_menu"; return BuilderResult(True, self.render_session(sess))
        if low in {"p", "preview"}: return self._session_preview(actor, sess)
        if low in {"v", "validate"}:
            issues = MobileTemplate.from_legacy(sess.working_record).validate() if sess.collection == "entities" else validate_object_template(normalize_object_template(sess.object_id, sess.working_record))
            lines=[f"{x['severity']}: {x['field_path']} {x['message']}" for x in issues] or ["- no focused issues"]
            return BuilderResult(not any(x['severity']=="error" for x in issues), "Validation for %s:\n%s" % (sess.object_id, "\n".join(lines)), {"issues": issues})
        if low in {"t", "testspawn"}: return self.testspawn(actor, sess.object_id)
        if low in {"s", "save"}:
            return self._session_save(actor, sess)
        if low in {"u", "undo"}:
            if not sess.undo_stack: return BuilderResult(False, "Nothing to undo.")
            sess.redo_stack.append(deepcopy(sess.working_record)); sess.working_record = sess.undo_stack.pop(); sess.dirty = sess.working_record != sess.savepoint; sess.saved = not sess.dirty
            return BuilderResult(True, "Session undo applied.\n" + self.render_session(sess))
        if low in {"r", "preview"} and sess.editor_type == "oedit": return self._session_preview(actor, sess)
        if low in {"y", "redo"} and sess.editor_type == "oedit":
            low = "redo"
        if low in {"r", "redo"}:
            if not sess.redo_stack: return BuilderResult(False, "Nothing to redo.")
            sess.undo_stack.append(deepcopy(sess.working_record)); sess.working_record = sess.redo_stack.pop(); sess.dirty = sess.working_record != sess.savepoint; sess.saved = not sess.dirty
            return BuilderResult(True, "Session redo applied.\n" + self.render_session(sess))
        if sess.section and sess.section != "natural_weapons":
            field_token = parts[0].lower() if parts else ""
            desc = self._descriptor(sess, field_token)
            if desc:
                if desc.read_only:
                    return BuilderResult(False, f"{desc.label} is read-only in this editor.")
                sess.active_field = desc.key
                if desc.input_type == "multiline":
                    sess.mode = "multiline_text"; sess.multiline_lines = []
                    return BuilderResult(True, self._render_multiline(sess))
                if desc.input_type == "flag_set":
                    sess.mode = "flag_editor"; return BuilderResult(True, self._render_flag_editor(sess))
                if desc.input_type in {"string_list","list"}:
                    sess.mode = "list_editor"; return BuilderResult(True, self._render_list_editor(sess))
                if desc.input_type == "reference":
                    sess.mode = "reference_selector"; sess.reference_filter = ""; return BuilderResult(True, self._render_reference_selector(actor, sess))
                sess.mode = "field_prompt"; return BuilderResult(True, self._render_field_prompt(sess))
        if sess.section and sess.section != "natural_weapons":
            parts = text.split()
            cmd = parts[0].lower() if parts else ""
            if cmd in {"list", "show"} or not cmd:
                return BuilderResult(True, self.render_session(sess))
            self._session_checkpoint(sess)
            rec = sess.working_record
            def set_path(field: str, value: Any) -> None:
                field = field.replace("-", "_")
                if sess.section == "combat":
                    rec.setdefault("combat_profile", {})[field] = value
                elif sess.section == "attributes" and field in {"strength","dexterity","constitution","intelligence","wisdom","charisma"}:
                    rec.setdefault("attributes", {})[field] = value
                elif sess.section == "resources" and field not in {"level"}:
                    rec.setdefault("resources", {})[field] = value
                else:
                    rec[field] = value
            if cmd in {"name", "type", "status", "area", "zone", "vnum"} and len(parts) > 1:
                field = {"name":"name","type":"entity_type","status":"builder_status","area":"area_id","zone":"zone_id","vnum":"vnum"}[cmd]; val=" ".join(parts[1:]); set_path(field, int(val) if field=="vnum" and val.isdigit() else val)
            elif cmd == "level" and len(parts) > 1 and parts[1].lstrip('-').isdigit():
                rec["level"] = int(parts[1])
            elif cmd == "attr" and len(parts) > 2 and parts[2].lstrip('-').isdigit():
                rec.setdefault("attributes", {})[parts[1].lower()] = int(parts[2])
            elif cmd == "resource" and len(parts) > 2 and parts[2].lstrip('-').isdigit():
                rec.setdefault("resources", {})[parts[1].lower()] = int(parts[2])
            elif cmd == "body" and len(parts) > 1:
                prof, bp, weapons = self._body_profile_result(actor, parts[1], scratch=rec)
                if not bp: return BuilderResult(False, "Unknown body profile. Choose: " + ", ".join(self.body_profiles(actor)))
                rec["body_profile_id"] = prof; rec.setdefault("combat_profile", {})["body_profile"] = prof; rec.setdefault("combat_profile", {})["natural_weapons"] = weapons
            elif cmd == "set" and len(parts) > 2:
                val = " ".join(parts[2:]); set_path(parts[1], int(val) if val.lstrip('-').isdigit() else val)
            elif cmd == "add" and len(parts) > 2:
                field = parts[1].replace("-", "_"); val = " ".join(parts[2:]); cur = rec.setdefault(field, []);
                cur.append(val) if isinstance(cur, list) else rec.__setitem__(field, [cur, val])
            elif cmd == "remove" and len(parts) > 2:
                field = parts[1].replace("-", "_"); val = " ".join(parts[2:]); cur = rec.get(field, []);
                rec[field] = [x for x in cur if str(x) != val] if isinstance(cur, list) else cur
            elif sess.section == "keywords" and cmd in {"add","remove","replace","clear","normalize"}:
                kws = list(rec.get("keywords") or [])
                if cmd == "add" and len(parts)>1: kws.append(parts[1].lower())
                elif cmd == "remove" and len(parts)>1: kws=[k for k in kws if k != parts[1].lower()]
                elif cmd == "replace" and len(parts)>2: kws=[(parts[2].lower() if k==parts[1].lower() else k) for k in kws]
                elif cmd == "clear": kws=[]
                elif cmd == "normalize": kws=sorted(dict.fromkeys(k.lower() for k in kws if k))
                rec["keywords"] = kws
            else:
                sess.undo_stack.pop()
                return BuilderResult(False, "Invalid input for this menu. Choose a listed field number/name, or use back, preview, validate, undo, redo, save, or help.")
            sess.working_record = self._normalize_entity_updates(sess.object_id, rec) if sess.collection == "entities" else rec
            sess.dirty=True; sess.saved=False
            return BuilderResult(True, "Updated session scratch.\n" + self.render_session(sess), sess.working_record)

        if sess.section == "natural_weapons":
            parts = text.split()
            if not parts or parts[0].lower() in {"list", "l"}: return BuilderResult(True, self.render_session(sess))
            self._session_checkpoint(sess)
            rec = sess.working_record or {"id": sess.object_id}; weapons = list((rec.get("combat_profile") or {}).get("natural_weapons") or [])
            if parts[0].lower() == "add" and len(parts) >= 2:
                wid=parts[1]; weapons.append(_canonical_weapon({"id": wid, "family": wid.split("_")[-1]}, wid))
            elif parts[0].lower() == "delete" and len(parts) >= 2:
                weapons=[w for w in weapons if w.get("id") != parts[1]]
            elif parts[0].lower() == "set" and len(parts) >= 4:
                wid, field, value = parts[1], parts[2].replace("-", "_"), " ".join(parts[3:])
                aliases={"family":"mechanical_family","weight":"selection_weight","verb":"verb_third_person","noun":"noun_plural","dice":"damage_dice"}; field=aliases.get(field, field)
                for w in weapons:
                    if w.get("id") == wid:
                        w[field] = int(value) if field in {"selection_weight","minimum_damage","maximum_damage","accuracy_modifier","critical_modifier","cooldown_pulses"} and value.lstrip('-').isdigit() else value
                        break
                else: return BuilderResult(False, f"Natural weapon {wid} not found.")
            else: return BuilderResult(False, "Use natural weapon actions: add weapon, edit weapon, delete weapon, list")
            sess.working_record["combat_profile"] = {**(rec.get("combat_profile") or {}), "natural_weapons": weapons}
            sess.working_record = self._normalize_entity_updates(sess.object_id, sess.working_record) if sess.collection == "entities" else sess.working_record
            sess.dirty=True; sess.saved=False
            return BuilderResult(True, "Updated session scratch.\n"+self.render_session(sess), sess.working_record)
        return BuilderResult(False, "Invalid editor input. Use a menu number, back, save, quit, or help.\n" + self.render_session(sess))

    def search(self, actor: Any, query: str) -> BuilderResult:
        q = query.lower()
        drafts = self.workspace.load(self.workspace.world_id(actor))
        lines: list[str] = []
        for coll in ("areas", "zones", "rooms", "items", "entities", "spawns"):
            for oid, rec in drafts.get(coll, {}).items():
                hay = (str(oid) + " " + str((rec or {}).get("name", "")) + " " + str((rec or {}).get("description", ""))).lower()
                if q in hay:
                    lines.append(f"{coll[:-1]} {oid}: {(rec or {}).get('name','')}")
        return BuilderResult(True, "Search results:\n" + ("\n".join(lines) if lines else "- none"), {"matches": lines})

    def autocomplete(self, actor: Any, collection: str, query: str) -> BuilderResult:
        drafts = self.workspace.load(self.workspace.world_id(actor))
        q = query.lower()
        rows = []
        for oid, rec in drafts.get(collection, {}).items():
            label = str((rec or {}).get("name") or oid)
            if q in oid.lower() or q in label.lower():
                rows.append({"id": oid, "label": label})
        body = "\n".join(f"{i+1}. {r['label']} [{r['id']}]" for i, r in enumerate(rows)) if rows else "- none"
        return BuilderResult(True, "Picker choices:\n" + body, {"choices": rows})

    def testroom(self, actor: Any) -> BuilderResult:
        rt = self._runtime_required()
        room_id = rt.ensure_builder_test_room(actor)
        old_room = getattr(actor, "room_id", "")
        setattr(actor, "builder_test_return_room_id", old_room)
        setattr(actor, "room_id", room_id)
        if hasattr(rt, "move_occupant"):
            rt.move_occupant(f"character:{getattr(actor, 'id', '')}", old_room, room_id)
        return BuilderResult(True, f"Entered private Builder test room {room_id}.", {"room_id": room_id})

    def testenter(self, actor: Any) -> BuilderResult:
        return self.testroom(actor)

    def testexit(self, actor: Any) -> BuilderResult:
        rt = self._runtime_required()
        room_id = getattr(actor, "builder_test_return_room_id", "") or getattr(rt, "default_room_id", "guildhall_crossing_square")
        old_room = getattr(actor, "room_id", "")
        setattr(actor, "room_id", room_id)
        rt.move_occupant(f"character:{getattr(actor, 'id', '')}", old_room, room_id)
        return BuilderResult(True, f"Returned from private Builder test room to {room_id}.", {"room_id": room_id})

    def testreset(self, actor: Any) -> BuilderResult:
        clear = self.testclear(actor)
        room = self.testroom(actor)
        return BuilderResult(clear.ok and room.ok, clear.message + "\n" + room.message, room.data)

    def teststatus(self, actor: Any) -> BuilderResult:
        rt = self._runtime_required()
        env = getattr(rt, "builder_test_environments", {}).get(str(getattr(actor, "id", "")), {})
        return BuilderResult(True, "Builder test environment status: " + (json.dumps(env, sort_keys=True) if env else "inactive"), {"environment": env})

    def testspawn(self, actor: Any, mob_id: str) -> BuilderResult:
        if self.runtime is None:
            sess = self.sessions.active.get(self.sessions.actor_key(actor))
            rec = deepcopy(sess.working_record) if sess and sess.collection == "entities" and sess.object_id == mob_id else deepcopy(self._record(self.workspace.world_id(actor), "entities", mob_id) or {})
            if not rec: return BuilderResult(False, f"No draft mob {mob_id}.")
            tmpl = MobileTemplate.from_legacy(rec); issues = tmpl.validate(); errors=[i for i in issues if i.get("blocking") or i.get("severity") == "error"]
            if errors: return BuilderResult(False, "Cannot testspawn invalid draft.", {"issues": issues})
            mob = tmpl.to_canonical_dict(); mob.update({"entity_id": f"builder_test:{mob_id}", "ephemeral": True, "builder_test_instance": True})
            return BuilderResult(True, f"UNSAVED BUILDER TEST INSTANCE\nSpawned simulated ephemeral draft mob {mob.get('name', mob_id)} ({mob['entity_id']}).", {"mob": mob, "room_id": "builder_test_room", "actor_id": mob["entity_id"]})
        rt = self._runtime_required()
        sess = self.sessions.active.get(self.sessions.actor_key(actor))
        rec = deepcopy(sess.working_record) if sess and sess.collection == "entities" and sess.object_id == mob_id else deepcopy(self._record(self.workspace.world_id(actor), "entities", mob_id) or {})
        if not rec:
            return BuilderResult(False, f"No draft mob {mob_id}.")
        tmpl = MobileTemplate.from_legacy(rec)
        issues = tmpl.validate()
        errors = [i for i in issues if i.get("blocking") or i.get("severity") == "error"]
        if errors:
            return BuilderResult(False, "Cannot testspawn invalid draft.\n" + "\n".join(f"error: {e.get('field_path')} {e.get('message')}" for e in errors), {"issues": issues})
        room_id = rt.ensure_builder_test_room(actor)
        ent = rt.materialize_entity_template(tmpl.to_canonical_dict(), room_id, ephemeral=True, owner=actor, generation_id=getattr(rt, "active_content_generation_id", None))
        actor_id = rt.actor_id_for_entity_instance(ent)
        if actor_id not in rt.combat_runtime.resident_actors or actor_id not in rt.resident_occupants_by_room.get(rt.canonical_room_id(room_id), {}):
            return BuilderResult(False, "Runtime registration failed for Builder testspawn.")
        return BuilderResult(True, f"Spawned resident ephemeral draft mob {ent['name']} ({ent['entity_id']}) in private Builder testing room {room_id}.", {"mob": ent, "room_id": room_id, "actor_id": actor_id})

    def testclear(self, actor: Any) -> BuilderResult:
        rt = self._runtime_required()
        result = rt.clear_builder_test_environment(actor)
        return BuilderResult(True, f"Cleared {result.get('actors', 0)} resident ephemeral Builder test actor(s), occupancy entries, combat encounters, AI tasks, timers, items, corpses, async messages, and private-room state.", result)

    def menu(self, editor: str, title: str, sess: BuilderEditSession | None = None) -> str:
        if editor == "medit":
            return medit_render.render_medit_main(sess) if sess else "Enter choice :"
            rec = (sess.working_record if sess else {}) or {}
            issues = MobileTemplate.from_legacy(rec).validate() if rec else []
            errors = sum(1 for i in issues if i.get("severity") == "error")
            warnings = sum(1 for i in issues if i.get("severity") == "warning")
            status = "clean" if not sess or not sess.dirty else "dirty"
            lines = [
                f"Mobile Editor\nMOBILE EDITOR: {title}", f"Mobile ID: {(sess.object_id if sess else '')}", f"VNUM: {rec.get('vnum', 'unset')}", f"Draft revision: {(sess.draft_revision if sess else rec.get('_builder_revision', 0))}",
                f"World: {(sess.world_id if sess else rec.get('world_id',''))}", f"Area: {rec.get('area_id','')}", f"Zone: {rec.get('zone_id','')}", f"Lock owner: {(sess.builder_character_id if sess else 'none')}",
                f"Validation status: {errors} error(s), {warnings} warning(s)", f"Dirty status: {status}", f"Builder completeness: {rec.get('builder_status','incomplete')}", f"Publish status: {rec.get('publish_status','draft/unpublished')}", f"Runtime activation status: {rec.get('runtime_status','not activated or unknown')}", "",
                "1. Identity - " + str(rec.get('name') or ''), "2. Keywords and aliases - " + str(', '.join(rec.get('keywords') or rec.get('aliases') or [])),
                "3. Descriptions - " + str(rec.get('room_description') or rec.get('description') or '')[:50], "4. Basic identity traits - species=" + str(rec.get('species') or rec.get('race') or 'unset') + " body=" + str(rec.get('body_profile_id') or 'unset'),
                "5. Stats Menu - editable/runtime-supported level " + str(rec.get('level', 1)), "6. Resources - editable via Stats Menu; health=" + str(((rec.get('resources') or {}).get('health') or {}).get('maximum') if isinstance(((rec.get('resources') or {}).get('health') or {}), dict) else ((rec.get('resources') or {}).get('health') or 'unset')),
                "7. Combat statistics and profiles - editable; attack type " + str((rec.get('combat_profile') or {}).get('attack_type') or rec.get('attack_type') or 'hit'), "8. Body profile and Natural Weapons / Natural Attacks - body=" + str(rec.get('body_profile_id') or (rec.get('combat_profile') or {}).get('body_profile','unset')) + " attacks=" + str(len((rec.get('combat_profile') or {}).get('natural_weapons') or [])),
                "9. Positions and posture - " + str(rec.get('default_position') or rec.get('spawn_position') or 'standing'), "10. Mobile flags - editable grouped flags count=" + str(len(rec.get('mobile_flags') or rec.get('flags') or [])),
                "11. Affect/status flags - editable grouped permanent affects count=" + str(len(rec.get('affect_flags') or [])), "12. Equipment loadout - " + str(len(rec.get('equipment_loadout') or rec.get('equipment') or {})),
                "13. Starting inventory - " + str(len(rec.get('starting_inventory') or rec.get('inventory') or [])), "14. Loadout / Loot overview - editable equipment/inventory/loot/corpse; profile=" + str(((rec.get('loot') or {}).get('profile_id')) or rec.get('loot_table_id') or 'unset') + " entries=" + str(len(((rec.get('loot') or {}).get('entries') or []))),
                "15. Abilities and spell loadout - " + str(rec.get('ability_loadout_id') or (rec.get('combat_profile') or {}).get('ability_loadout_id') or 'unset'), "16. Behavior and AI - " + str(rec.get('behavior_profile_id') or rec.get('ai_actor_enabled') or 'unset'),
                "17. Faction and relationships - " + str(rec.get('faction_id') or 'unset'), "18. Scripts and triggers - " + str(len(rec.get('script_ids') or rec.get('scripts') or [])),
                "19. Spawn and reset references - read-only diagnostics/add draft references", "20. Diagnostics and references - validation, references, runtime preview", "",
                "P. Preview", "V. Validate", "T. Testspawn", "H. History", "U. Undo", "R. Redo", "S. Save", "Q. Quit"]
            return "\n".join(lines)
        sections = {"redit": ["Title", "Description", "Exits", "Sector", "Flags", "Extra Descriptions", "Ambient Effects", "Spawn List", "Preview", "Validate", "Publish"], "oedit": ["Identity", "Keywords", "Type", "Wear Flags", "Extra Flags", "Stats", "Affects", "Values", "Container Data", "Weapon Data", "Armor Data", "Scripts", "Preview", "Validate", "Publish"], "aedit": ["Identity", "Zones", "Rooms", "Templates", "Spawns", "Preview", "Validate", "Publish"], "zedit": ["Identity", "Area", "Rooms", "Resets", "Spawns", "Preview", "Validate", "Publish"]}.get(editor, [])
        header = {"redit": "Room Editor", "oedit": "Object Editor", "aedit": "Area Editor", "zedit": "Zone Editor"}.get(editor, "Builder Editor")
        body = "\n".join(f"{i} {section}" for i, section in enumerate(sections, 1))
        return f"--------------------------------------\n{header}\n{title}\n--------------------------------------\n\n{body}\n\nS Save Draft\nP Publish\nQ Quit"
