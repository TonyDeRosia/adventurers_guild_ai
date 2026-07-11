"""Safe in-game Builder workspace services for Smart MUD."""
from __future__ import annotations

import json, shutil, re
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from smart_mud.world_registry import WORLDS_DIR, _records

BUILDER_ROLES = {"builder", "admin", "owner"}
VALID_WEAR_SLOTS = {"head","face","neck","shoulders","back","chest","body","torso","arms","wrists","hands","finger","wrist","finger_left","finger_right","waist","legs","feet","mainhand","main_hand","primary_weapon","offhand","off_hand","secondary_weapon","held","wield","shield","quiver","ammo","ranged","light","accessory_1","accessory_2"}
VALID_ENTITY_TYPES = {"npc", "mob", "merchant", "trainer", "banker", "healer", "critter", "object"}

DRAFT_FILES = {
    "areas": "areas.json", "zones": "zones.json", "rooms": "rooms.json",
    "features": "features.json", "items": "item_templates.json", "item_placements": "item_placements.json", "entities": "entity_templates.json", "spawns": "spawns.json", "schedules": "schedules.json", "relationship_seeds": "relationship_seeds.json", "memory_seeds": "memory_seeds.json", "need_profiles": "need_profiles.json", "goal_profiles": "goal_profiles.json", "formulas": "formulas.json", "modifier_types": "modifier_types.json", "future_formula_templates": "future_formula_templates.json", "abilities": "abilities.json", "ability_loadouts": "ability_loadouts.json", "ability_schools": "ability_schools.json", "ability_categories": "ability_categories.json", "cooldown_groups": "cooldown_groups.json", "targeting_profiles": "targeting_profiles.json", "healing_profiles": "healing_profiles.json", "casting_profiles": "casting_profiles.json", "combat_behavior_profiles": "combat_behavior_profiles.json", "threat_profiles": "threat_profiles.json", "aggression_profiles": "aggression_profiles.json", "assist_profiles": "assist_profiles.json", "flee_profiles": "flee_profiles.json", "surrender_profiles": "surrender_profiles.json", "pursuit_profiles": "pursuit_profiles.json", "combat_groups": "combat_groups.json", "combat_action_rules": "combat_action_rules.json", "recipe_definitions": "recipe_definitions.json", "workstation_profiles": "workstation_profiles.json", "production_profiles": "production_profiles.json", "item_quality_profiles": "item_quality_profiles.json", "crafting_quality_profiles": "crafting_quality_profiles.json", "ingredient_substitution_profiles": "ingredient_substitution_profiles.json", "crafting_message_profiles": "crafting_message_profiles.json", "profession_experience_curves": "profession_experience_curves.json", "profession_growth_profiles": "profession_growth_profiles.json", "quest_definitions": "quest_definitions.json", "quest_series": "quest_series.json", "quest_chapters": "quest_chapters.json", "quest_stages": "quest_stages.json", "quest_objectives": "quest_objectives.json", "quest_availability_profiles": "quest_availability_profiles.json", "quest_acceptance_profiles": "quest_acceptance_profiles.json", "quest_repeat_policies": "quest_repeat_policies.json", "quest_failure_profiles": "quest_failure_profiles.json", "quest_abandon_profiles": "quest_abandon_profiles.json", "quest_sharing_profiles": "quest_sharing_profiles.json", "quest_action_definitions": "quest_action_definitions.json", "conversation_definitions": "conversation_definitions.json", "conversation_nodes": "conversation_nodes.json", "conversation_choices": "conversation_choices.json", "conversation_conditions": "conversation_conditions.json", "conversation_actions": "conversation_actions.json", "quest_message_profiles": "quest_message_profiles.json", "quest_time_limit_profiles": "quest_time_limit_profiles.json", "world_state_definitions": "world_state_definitions.json", "organization_definitions": "organization_definitions.json", "organization_roles": "organization_roles.json", "organization_membership_policies": "organization_membership_policies.json", "organization_invitation_policies": "organization_invitation_policies.json", "organization_application_policies": "organization_application_policies.json", "organization_leadership_policies": "organization_leadership_policies.json", "organization_permission_profiles": "organization_permission_profiles.json", "organization_communication_profiles": "organization_communication_profiles.json", "organization_group_combat_profiles": "organization_group_combat_profiles.json", "organization_shared_quest_profiles": "organization_shared_quest_profiles.json", "organization_reward_profiles": "organization_reward_profiles.json", "organization_relationship_profiles": "organization_relationship_profiles.json", "organization_seeds": "organization_seeds.json", "organization_message_profiles": "organization_message_profiles.json", "faction_definitions": "faction_definitions.json", "faction_reputation_profiles": "faction_reputation_profiles.json", "faction_standing_tier_profiles": "faction_standing_tier_profiles.json", "faction_membership_reputation_policies": "faction_membership_reputation_policies.json", "faction_diplomacy_profiles": "faction_diplomacy_profiles.json", "faction_hostility_profiles": "faction_hostility_profiles.json", "faction_access_profiles": "faction_access_profiles.json", "faction_guard_response_profiles": "faction_guard_response_profiles.json", "faction_economy_modifier_profiles": "faction_economy_modifier_profiles.json", "faction_reward_profiles": "faction_reward_profiles.json", "faction_reputation_decay_profiles": "faction_reputation_decay_profiles.json", "faction_combat_reputation_profiles": "faction_combat_reputation_profiles.json", "faction_title_profiles": "faction_title_profiles.json", "faction_message_profiles": "faction_message_profiles.json", "trainer_definitions": "trainer_definitions.json", "training_offer_definitions": "training_offer_definitions.json", "training_requirement_profiles": "training_requirement_profiles.json", "training_cost_profiles": "training_cost_profiles.json", "training_result_profiles": "training_result_profiles.json", "trainer_availability_profiles": "trainer_availability_profiles.json", "class_track_training_profiles": "class_track_training_profiles.json", "advancement_conversion_profiles": "advancement_conversion_profiles.json", "respec_profiles": "respec_profiles.json", "training_refund_profiles": "training_refund_profiles.json", "training_cooldown_profiles": "training_cooldown_profiles.json", "training_message_profiles": "training_message_profiles.json", "written_document_definitions": "written_document_definitions.json", "written_content_profiles": "written_content_profiles.json", "written_content_pages": "written_content_pages.json", "written_access_profiles": "written_access_profiles.json", "written_retention_profiles": "written_retention_profiles.json", "written_render_profiles": "written_render_profiles.json", "written_sanitization_profiles": "written_sanitization_profiles.json", "mail_service_profiles": "mail_service_profiles.json", "bulletin_board_definitions": "bulletin_board_definitions.json", "bulletin_posting_profiles": "bulletin_posting_profiles.json", "written_moderation_profiles": "written_moderation_profiles.json", "written_message_profiles": "written_message_profiles.json", "readable_item_profiles": "readable_item_profiles.json", "journal_profiles": "journal_profiles.json", "book_profiles": "book_profiles.json"
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
        ordered = {k: record.get(k) for k in ("id","name","description","world_id","area_id","zone_id","vnum","exits","features","flags","tags","plugin_data")}
        for k, v in record.items():
            if k not in ordered: ordered[k] = v
        return ordered, ordered != original

    def normalize_drafts(self, world_id: str, drafts: dict[str, Any], actor: Any | None = None) -> bool:
        changed = False
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
        return changed

    def save_drafts(self, world_id: str, drafts: dict[str, Any]) -> None:
        self.normalize_drafts(world_id, drafts)
        root = self.ensure(world_id)
        for key, filename in DRAFT_FILES.items():
            (root / filename).write_text(json.dumps(drafts.get(key, {}), indent=2, sort_keys=True) + "\n", encoding="utf-8")

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
        for iid, item in drafts["items"].items():
            if not item.get("name"): errors.append(f"item {iid} missing name")
            for slot in item.get("wear_slots", []) if isinstance(item.get("wear_slots", []), list) else []:
                if str(slot) not in VALID_WEAR_SLOTS: errors.append(f"item {iid} invalid wear slot {slot}")
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
