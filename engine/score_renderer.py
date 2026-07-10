"""Single modular Adventurer's-Lair-style score sheet rendering for Actors.

The renderer is intentionally presentation-only: it does not execute combat,
formulas, spell, skill, equipment bonus, or AI logic.  All score-related
commands should call :class:`ActorScoreRenderer` so the Actor presentation layer
has one permanent render path.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any, Callable

from engine.actors import Actor, FormulaRegistry
from engine.phase5f import BodyProfileRegistry
from engine.combat_equipment import CombatContentRegistry
from engine.mud_displays import semantic

ADMIN_SECTIONS = {"diagnostics", "formulas", "raw", "behavior", "threat", "tactics"}

BOX_WIDTH = 78
EMPTY = "--"

REMOVED_GAMEPLAY_SLOTS = {"primary_weapon", "secondary_weapon", "shield", "quiver", "ranged", "ammo", "both_hands"}
RESOURCE_ROWS = [
    ("health", "Health", "hp"), ("mana", "Mana", "mp"), ("movement", "Movement", "score_value"),
    ("stamina", "Stamina", "stamina"), ("hunger", "Hunger", "score_value"), ("thirst", "Thirst", "score_value"),
    ("fatigue", "Fatigue", "score_value"), ("drunkenness", "Drunkenness", "score_value"),
    ("warmth", "Warmth", "score_value"), ("body_temperature", "Body Temperature", "score_value"),
    ("corruption", "Corruption", "score_value"), ("sanity", "Sanity", "score_value"), ("oxygen", "Oxygen", "score_value"),
]
DERIVED_KEYS = [
    "attack_rating", "defense_rating", "armor", "hit_bonus", "damage_bonus", "critical_chance",
    "critical_damage", "critical_avoidance", "parry", "block", "dodge", "initiative", "threat",
    "spell_power", "healing_power", "movement_regeneration", "mana_regeneration", "health_regeneration",
    "carry_weight", "carry_capacity", "reach", "range", "casting_speed", "attack_speed",
]
COMBAT_FIELDS = [
    "primary_weapon", "secondary_weapon", "attack_style", "combat_profile", "aggression_profile",
    "combat_stance", "target", "range", "attack_delay", "combat_flags", "natural_attacks",
    "shield_status", "dual_wield_status", "builder_combat_profile",
]
CONDITIONS = ["standing", "resting", "sleeping", "fighting", "flying", "swimming", "invisible", "hidden", "sneaking", "mounted"]
RESISTANCES = ["physical", "slash", "pierce", "blunt", "fire", "cold", "lightning", "poison", "disease", "holy", "shadow", "arcane", "mental", "bleeding"]
AFFECT_GROUPS = ["positive", "negative", "passive", "equipment", "temporary", "permanent", "future_ai"]
SPELLUP_GROUPS = ["permanent", "long", "medium", "short", "expiring"]
PROGRESSION_FIELDS = ["level", "experience", "experience_to_next", "practice_sessions", "training_sessions", "remorts", "builder_progression_data", "future_advancement_data"]
CURRENCY_FIELDS = ["gold", "silver", "copper", "premium"]
RELATIONSHIP_FIELDS = ["faction", "guild_standing", "clan_standing", "friends", "enemies", "followers", "pet", "mount", "mentor", "family", "marriage", "builder_relationship_data"]
SIMULATION_FIELDS = ["current_schedule", "current_goal", "current_activity", "current_need", "current_mood", "current_location", "current_simulation_tick", "current_world_time"]


def _human(key: str) -> str:
    return str(key).replace("_", " ").title()


def _value(value: Any) -> str:
    if value is None or value == "":
        return EMPTY
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (list, tuple, set)):
        return ", ".join(_value(v) for v in value) if value else EMPTY
    if isinstance(value, dict):
        if "name" in value:
            return str(value["name"])
        return ", ".join(f"{_human(k)}={_value(v)}" for k, v in value.items()) if value else EMPTY
    return str(value)


def _line(left: str = "") -> str:
    return semantic("system", f"| {left:<{BOX_WIDTH - 4}} |")


def _rule(ch: str = "-") -> str:
    if ch == "=":
        return semantic("system", ch * (BOX_WIDTH - 2))
    return semantic("system", "+" + ch * (BOX_WIDTH - 2) + "+")


def _header(title: str) -> list[str]:
    text = f" {title} "
    fill = BOX_WIDTH - 2 - len(text)
    return [_rule("="), semantic("system", "|" + text + "-" * max(0, fill) + "|") + semantic("system", f"  [{title.title()}]"), _rule("-")]


def _field(label: str, value: Any, *, role: str = "score_value", width: int = 22) -> str:
    return f"{semantic('score_label', label + ':'):<0} {semantic(role, _value(value))}".ljust(width)


def _json_default(obj: Any) -> Any:
    if is_dataclass(obj):
        return asdict(obj)
    return str(obj)


class ActorScoreRenderer:
    """The one score renderer, with independently renderable sections."""

    order = [
        "identity", "resources", "primary_attributes", "derived_attributes", "combat", "equipment",
        "conditions", "resistances", "affects", "spellup", "abilities", "skills", "spells", "cooldowns", "current_cast", "combat_loadout", "passive_abilities", "progression", "professions", "crafting", "recipes", "quests", "journal", "questhistory", "currencies", "banking", "transactions", "relationships",
        "simulation", "party", "organizations", "guild", "clan", "memberships", "social", "behavior", "threat", "tactics", "diagnostics", "formulas", "raw",
    ]
    aliases = {
        "score": "all", "preview": "all", "actor": "all", "attrs": "primary_attributes", "attributes": "primary_attributes",
        "derived": "derived_attributes", "resists": "resistances", "saff": "affects", "spellups": "spellup",
        "worth": "currencies", "profession": "professions", "recipe": "recipes", "cast": "current_cast", "currency": "currencies", "money": "currencies", "bank": "banking", "banking": "banking", "transactions": "transactions", "builder": "diagnostics",
        "questlog": "journal", "quest_history": "questhistory", "builder_diagnostics": "diagnostics", "ai": "simulation", "ai_diagnostics": "simulation", "behaviour": "behavior", "membership": "memberships",
    }

    def __init__(self, formula_registry: FormulaRegistry | None = None, *, ansi: bool = False):
        self.formula_registry = formula_registry or FormulaRegistry.default()
        self.body_registry = BodyProfileRegistry()
        self.ansi = ansi
        self.combat_content = CombatContentRegistry()
        self._renderers: dict[str, Callable[[Actor, bool], str]] = {name: getattr(self, f"render_{name}") for name in self.order}

    def render(self, actor: Actor, section: str = "all", *, admin: bool = False, ansi: bool | None = None) -> str:
        section = self.aliases.get((section or "all").lower(), (section or "all").lower())
        if section != "all":
            return self.render_section(actor, section, admin=admin, ansi=ansi)
        return "\n".join(self.render_section(actor, s, admin=admin, ansi=ansi) for s in self.order if admin or s not in ADMIN_SECTIONS)

    def render_section(self, actor: Actor, section: str, *, admin: bool = False, ansi: bool | None = None) -> str:
        section = self.aliases.get(section, section)
        if section not in self._renderers:
            return f"Unknown score section: {section}"
        if section in ADMIN_SECTIONS and not admin:
            return "That score section is restricted to administrators and Builders."
        return self._renderers[section](actor, admin)


    def render_quests(self, actor: Actor, admin: bool = False) -> str:
        data = getattr(actor, "quest_summary", {}) or {}
        active = data.get("active_count", len(data.get("active", [])) if isinstance(data.get("active"), list) else 0)
        ready = data.get("ready_to_turn_in_count", len(data.get("ready_to_turn_in", [])) if isinstance(data.get("ready_to_turn_in"), list) else 0)
        return self._section("Quests", [_line(f"Active quests: {active}"), _line(f"Ready to turn in: {ready}")])

    def render_journal(self, actor: Actor, admin: bool = False) -> str:
        quests = (getattr(actor, "quest_summary", {}) or {}).get("active", [])
        rows = []
        for q in quests:
            if isinstance(q, dict): rows.append(_line(f"{q.get('name', q.get('quest_id','Quest'))}: {q.get('current_stage','')}"))
        return self._section("Quest Journal", rows)

    def render_questhistory(self, actor: Actor, admin: bool = False) -> str:
        hist = (getattr(actor, "quest_summary", {}) or {}).get("history", [])
        rows = [_line(str(h.get('operation', h)) if isinstance(h, dict) else str(h)) for h in hist[:10]]
        return self._section("Quest History", rows)

    def _section(self, title: str, rows: list[str]) -> str:
        return "\n".join(_header(title) + (rows or [_line("None.")]) + [_rule("-")])

    def _two_col(self, pairs: list[tuple[str, Any, str]]) -> list[str]:
        rows = []
        for idx in range(0, len(pairs), 2):
            l_label, l_value, l_role = pairs[idx]
            left = _field(l_label, l_value, role=l_role)
            if idx + 1 < len(pairs):
                r_label, r_value, r_role = pairs[idx + 1]
                right = _field(r_label, r_value, role=r_role)
            else:
                right = ""
            rows.append(_line(f"{left:<36} {right}"))
        return rows



    def _organization_summary(self, actor: Actor) -> dict[str, Any]:
        return getattr(actor, "organization_summary", None) or (actor.plugin_data or {}).get("organization_summary", {}) or {}

    def render_party(self, actor: Actor, admin: bool = False) -> str:
        data = self._organization_summary(actor).get("party", {})
        rows = [_line(f"Party: {_value(data.get('name'))}"), _line(f"Role: {_value(data.get('role'))}  Members: {_value(data.get('member_count', 0))}"), _line(f"Status: {_value(data.get('status', 'No active party'))}")]
        if admin and data.get("organization_instance_id"):
            rows.append(_line(f"Organization ID: {data.get('organization_instance_id')}"))
        return self._section("SCORE PARTY", rows)

    def render_organizations(self, actor: Actor, admin: bool = False) -> str:
        orgs = self._organization_summary(actor).get("organizations", [])
        rows = [_line(f"{o.get('name', o.get('organization_instance_id','Organization'))}: {o.get('role_id', o.get('role','member'))}") for o in orgs if isinstance(o, dict)]
        if admin:
            rows.append(_line("Phase 8B runtime IDs, memberships, invitations, applications, audit, combat, and quest traces are available through orgtrace."))
        return self._section("SCORE ORGANIZATIONS", rows)

    def render_guild(self, actor: Actor, admin: bool = False) -> str:
        guild = self._organization_summary(actor).get("guild", {})
        rows = [_line(f"Guild: {_value(guild.get('name'))}"), _line(f"Role: {_value(guild.get('role'))}  Members: {_value(guild.get('member_count', 0))}"), _line(f"Applications: {_value(guild.get('application_status', '--'))}")]
        return self._section("SCORE GUILD", rows)

    def render_clan(self, actor: Actor, admin: bool = False) -> str:
        clan = self._organization_summary(actor).get("clan", {})
        rows = [_line(f"Clan: {_value(clan.get('name'))}"), _line(f"Role: {_value(clan.get('role'))}  Members: {_value(clan.get('member_count', 0))}")]
        return self._section("SCORE CLAN", rows)

    def render_memberships(self, actor: Actor, admin: bool = False) -> str:
        data = self._organization_summary(actor)
        rows = [_line(f"Invitations: {_value(data.get('invitation_count', 0))}"), _line(f"Applications: {_value(data.get('application_count', 0))}"), _line(f"Primary title: {_value(data.get('primary_title', '--'))}")]
        return self._section("SCORE MEMBERSHIPS", rows)

    def render_social(self, actor: Actor, admin: bool = False) -> str:
        data = self._organization_summary(actor)
        rows = [_line(f"Party: {_value((data.get('party') or {}).get('name'))}"), _line(f"Guild: {_value((data.get('guild') or {}).get('name'))}"), _line(f"Clan: {_value((data.get('clan') or {}).get('name'))}")]
        return self._section("SCORE SOCIAL", rows)

    def render_behavior(self, actor: Actor, admin: bool = False) -> str:
        cb = (actor.plugin_data or {}).get("combat_behavior", {})
        cp = actor.combat_profile or {}
        rows = self._two_col([
            ("Behavior Profile", cp.get("combat_behavior_profile_id") or actor.plugin_data.get("combat_behavior_profile_id") or cb.get("profile_id") or "safe_default", "score_value"),
            ("Aggression Policy", cb.get("aggression_policy") or cp.get("aggression") or "derived", "score_value"),
            ("Pet Mode", cb.get("pet_mode") or actor.plugin_data.get("pet_mode") or "--", "score_value"),
            ("Protected Targets", cb.get("protected_actor_ids") or [], "score_value"),
        ])
        return self._section("SCORE BEHAVIOR", rows)

    def render_threat(self, actor: Actor, admin: bool = False) -> str:
        table = (actor.plugin_data or {}).get("threat_table", [])
        rows = [_line(f"{r.get('target_actor_id')}: {r.get('threat_value')}") for r in table] if isinstance(table, list) else [_line(_value(table))]
        if not rows: rows = [_line("No active threat entries.")]
        return self._section("SCORE THREAT", rows)

    def render_tactics(self, actor: Actor, admin: bool = False) -> str:
        st = (actor.plugin_data or {}).get("combat_behavior_state", {})
        cp = actor.combat_profile or {}
        rows = self._two_col([
            ("Tactical State", st.get("current_tactical_state") or cp.get("combat_state") or "idle", "score_value"),
            ("Current Target", st.get("current_target_id") or cp.get("target") or "--", "score_value"),
            ("Current Action", st.get("current_action_type") or "--", "score_value"),
            ("Selected Ability", st.get("current_ability_id") or "--", "score_value"),
            ("Next Decision", st.get("next_decision_world_time") or "--", "score_value"),
            ("Deterministic Seed", st.get("deterministic_seed") or "--", "score_value"),
        ])
        return self._section("SCORE TACTICS", rows)

    def render_identity(self, actor: Actor, admin: bool = False) -> str:
        i = actor.identity
        pairs = [("Name", i.name, "player"), ("Title", i.title, "score_value"), ("Race", i.race, "score_value"), ("Class", i.class_placeholder, "score_value"), ("Profession", i.profession_placeholder, "score_value"), ("Guild", i.guild, "score_value"), ("Clan", i.clan, "score_value"), ("Religion", i.religion, "score_value"), ("Alignment", i.alignment, "score_value"), ("Gender", i.gender, "score_value"), ("Age", i.age, "score_value"), ("Height", i.height, "score_value"), ("Weight", i.weight, "score_value"), ("Languages Known", i.languages, "score_value"), ("Speaking Language", i.speaking_language, "score_value"), ("Current Position", i.position, "score_value"), ("World", i.current_world, "score_value"), ("Area", i.current_area, "score_value"), ("Zone", i.current_zone, "score_value"), ("Room", i.current_location, "score_value")]
        if admin:
            pairs.append(("Builder Actor ID", actor.actor_id, "score_value"))
        rows = self._two_col(pairs)
        rows.append(_line(_field("Description", i.description or "None", width=70)))
        return self._section("SCORE IDENTITY", rows)

    def render_resources(self, actor: Actor, admin: bool = False) -> str:
        r = actor.resources
        pairs = []
        for key, label, role in RESOURCE_ROWS:
            maxv = getattr(r, f"maximum_{key}", None)
            cur = getattr(r, key, None)
            val = f"{cur}/{maxv}  Regen: future  Mods: future" if maxv is not None else f"{_value(cur)}  Regen: future  Mods: future"
            pairs.append((label, val, role))
        for key, value in actor.plugin_data.get("resources", {}).items():
            pairs.append((_human(key), f"{_value(value)}  Regen: future  Mods: future", "score_value"))
        return self._section("RESOURCES", self._two_col(pairs))

    def render_primary_attributes(self, actor: Actor, admin: bool = False) -> str:
        return self._section("PRIMARY ATTRIBUTES", self._two_col([(_human(k), v, "score_value") for k, v in actor.attributes.items()]))

    def render_derived_attributes(self, actor: Actor, admin: bool = False) -> str:
        stats = dict(actor.derived_statistics_cache)
        for key in DERIVED_KEYS:
            stats.setdefault(key, None)
        pairs = []
        for key, stat in stats.items():
            formula = getattr(stat, "formula_name", key)
            value = getattr(stat, "value", None)
            label = getattr(stat, "label", _human(key))
            pairs.append((label, f"{_value(value)}  Formula: {formula}", "score_value"))
        return self._section("DERIVED ATTRIBUTES", self._two_col(pairs))

    def render_combat(self, actor: Actor, admin: bool = False) -> str:
        data = dict(actor.combat_profile or {})
        pairs = [(_human(k), data.get(k, "future"), "score_value") for k in COMBAT_FIELDS]
        return self._section("COMBAT PROFILE", self._two_col(pairs))

    def render_equipment(self, actor: Actor, admin: bool = False) -> str:
        eq = actor.equipment_profile.get("equipped", actor.equipment_profile) or {}
        profile = self.body_registry.get(getattr(actor, "body_profile_id", "humanoid"))
        rows = []
        if admin:
            rows.append(_line(_field("Body Profile", profile.id, width=70)))
        pairs = []
        for slot in profile.slots:
            if not slot.visible:
                continue
            item = eq.get(slot.id) or eq.get(slot.display_name) or "nothing"
            pairs.append((slot.display_name, item, "equipment_item"))
        rows.extend(self._two_col(pairs))
        weapon = eq.get("main_hand") or eq.get("primary_weapon") or eq.get("weapon")
        if isinstance(weapon, dict):
            rows.append(_line(_field("Current Weapon", weapon.get("name", weapon.get("id")), width=70)))
            rows.append(_line(_field("Attack Profile", weapon.get("attack_profile", "--"), width=34) + " " + _field("Weapon Class", weapon.get("weapon_class", "--"), width=34)))
            rows.append(_line(_field("Damage Profile", weapon.get("damage_profile", "--"), width=34) + " " + _field("Critical Profile", weapon.get("critical_profile", "--"), width=34)))
        armors = [item for item in eq.values() if isinstance(item, dict) and ("armor_class" in item or "armor_value" in item)]
        armor_value = sum(int(item.get("armor_value", 0) or 0) for item in armors)
        armor_classes = ", ".join(str(item.get("armor_class")) for item in armors if item.get("armor_class")) or "--"
        rows.append(_line(_field("Armor Class", armor_classes, width=34) + " " + _field("Armor Value", armor_value, width=34)))
        naturals = actor.combat_profile.get("natural_weapon_profile_ids") or actor.combat_profile.get("natural_weapons") or []
        rows.append(_line(_field("Natural Weapons", naturals or "--", width=70)))
        rows.append(_line(_field("Equipment Summary", f"{len([v for v in eq.values() if v and v != 'nothing'])} equipped", width=70)))
        return self._section("EQUIPMENT", rows)

    def render_conditions(self, actor: Actor, admin: bool = False) -> str:
        data = dict(actor.condition_profile or {})
        pairs = [(_human(k), data.get(k, "future"), "score_value") for k in CONDITIONS]
        for k, v in data.items():
            if k not in CONDITIONS:
                pairs.append((_human(k), v, "score_value"))
        return self._section("CONDITIONS", self._two_col(pairs))

    def render_resistances(self, actor: Actor, admin: bool = False) -> str:
        data = dict(actor.resistance_profile or {})
        keys = RESISTANCES + [k for k in data if k not in RESISTANCES]
        rows = [_line(f"{semantic('score_label','Type'):<22} {semantic('score_label','Base'):<10} {semantic('score_label','Equipment'):<12} {semantic('score_label','Effects'):<10} {semantic('score_label','Total')}")]
        for key in keys:
            val = data.get(key, {})
            if not isinstance(val, dict):
                val = {"base": val, "equipment": "future", "effects": "future", "total": val}
            rows.append(_line(f"{_human(key):<20} {_value(val.get('base','future')):<10} {_value(val.get('equipment','future')):<12} {_value(val.get('effects','future')):<10} {_value(val.get('total','future'))}"))
        return self._section("RESISTANCES", rows)

    def _grouped_effect_rows(self, effects: Any, groups: list[str]) -> list[str]:
        rows: list[str] = []
        source = effects if isinstance(effects, dict) else {}
        flat = source.get("affects", source)
        for group in groups + [g for g in flat if isinstance(flat.get(g), list) and g not in groups]:
            rows.append(_line(semantic("score_label", _human(group))))
            items = flat.get(group, []) if isinstance(flat, dict) else []
            if isinstance(items, dict):
                items = [dict(v, name=k) if isinstance(v, dict) else {"name": k, "source": v} for k, v in items.items()]
            if not items:
                rows.append(_line("  none")); continue
            rows.append(_line("  Name                 Source        Duration   Remaining  Stacks Category"))
            for item in items:
                if not isinstance(item, dict):
                    item = {"name": item}
                rows.append(_line(f"  {_value(item.get('name')):<20} {_value(item.get('source','future')):<13} {_value(item.get('duration','future')):<10} {_value(item.get('remaining','future')):<10} {_value(item.get('stacks', item.get('stack_count', 1))):<6} {_value(item.get('category', group))}"))
        return rows

    def render_affects(self, actor: Actor, admin: bool = False) -> str:
        return self._section("AFFECTS", self._grouped_effect_rows(actor.effect_container, AFFECT_GROUPS))

    def render_spellup(self, actor: Actor, admin: bool = False) -> str:
        return self._section("SPELLUP", self._grouped_effect_rows(actor.effect_container.get("spellup", {}), SPELLUP_GROUPS))

    def _ability_rows(self, actor: Actor, kinds: set[str] | None = None) -> list[str]:
        abilities = actor.plugin_data.get("abilities", []) or []
        if isinstance(abilities, dict): abilities = list(abilities.values())
        rows = []
        for a in abilities:
            if not isinstance(a, dict): a = {"name": str(a), "ability_type": "custom"}
            if kinds and str(a.get("ability_type")) not in kinds: continue
            rows.append(_line(f"{_value(a.get('name', a.get('id'))):<24} {_value(a.get('ability_type','custom')):<12} Cost={_value(a.get('cost','--')):<10} Cooldown={_value(a.get('cooldown','--')):<8} Cast={_value(a.get('cast_time','0'))}"))
        return rows or [_line("No abilities available in this actor view.")]

    def render_abilities(self, actor: Actor, admin: bool = False) -> str:
        return self._section("ABILITIES", self._ability_rows(actor))

    def render_skills(self, actor: Actor, admin: bool = False) -> str:
        return self._section("SKILLS", self._ability_rows(actor, {"skill", "technique"}))

    def render_spells(self, actor: Actor, admin: bool = False) -> str:
        return self._section("SPELLS", self._ability_rows(actor, {"spell", "heal", "buff", "debuff"}))

    def render_cooldowns(self, actor: Actor, admin: bool = False) -> str:
        rows = [_line(f"{_value(c.get('ability_id','')):<24} Ready={_value(c.get('ready_world_time','--')):<10} Group={_value(c.get('cooldown_group','--'))}") for c in actor.plugin_data.get("cooldowns", []) if isinstance(c, dict)]
        return self._section("COOLDOWNS", rows or [_line("No active cooldowns.")])

    def render_current_cast(self, actor: Actor, admin: bool = False) -> str:
        cast = actor.plugin_data.get("current_cast") or {}
        rows = [_line(f"{_human(k)}: {_value(v)}") for k, v in cast.items()] if isinstance(cast, dict) and cast else [_line("No current cast.")]
        return self._section("CURRENT CAST", rows)

    def render_combat_loadout(self, actor: Actor, admin: bool = False) -> str:
        return self._section("COMBAT LOADOUT", [_line(_field("Ability Loadout", actor.combat_profile.get("ability_loadout_id", "--"), width=70))])

    def render_passive_abilities(self, actor: Actor, admin: bool = False) -> str:
        return self._section("PASSIVE ABILITIES", self._ability_rows(actor, {"passive"}))

    def render_progression(self, actor: Actor, admin: bool = False) -> str:
        data = actor.progression_profile or {}
        return self._section("PROGRESSION", self._two_col([(_human(k), data.get(k, "future"), "score_value") for k in PROGRESSION_FIELDS]))

    def render_professions(self, actor: Actor, admin: bool = False) -> str:
        data = (actor.plugin_data.get("professions", {}) if getattr(actor, "plugin_data", None) else {})
        rows = []
        if isinstance(data, dict):
            for pid, st in sorted(data.items()):
                rows.append(_line(f"{pid:<24} rank={st.get('rank', 1) if isinstance(st, dict) else st} xp={st.get('experience', 0) if isinstance(st, dict) else 0}"))
        if not rows:
            rows = [_line("No profession progress recorded yet.")]
        if admin:
            rows.append(_line("Admin detail: actor_profession_state stores rank, XP, thresholds, and metadata."))
        return self._section("PROFESSIONS", rows)

    def render_crafting(self, actor: Actor, admin: bool = False) -> str:
        data = (actor.plugin_data.get("crafting", {}) if getattr(actor, "plugin_data", None) else {})
        rows = [_line(f"Active jobs: {data.get('active_job_count', 0) if isinstance(data, dict) else 0}"), _line(f"Current job: {data.get('current_job', '--') if isinstance(data, dict) else '--'}"), _line(f"Pending outputs: {data.get('pending_outputs', '--') if isinstance(data, dict) else '--'}")]
        if admin:
            rows.append(_line("Admin detail: job IDs, reservation IDs, workstation IDs, quality seed, and packet IDs are in CraftingService traces."))
        return self._section("CRAFTING", rows)

    def render_recipes(self, actor: Actor, admin: bool = False) -> str:
        data = (actor.plugin_data.get("recipes", []) if getattr(actor, "plugin_data", None) else [])
        count = len(data) if isinstance(data, list) else int(data.get("count", 0) if isinstance(data, dict) else 0)
        rows = [_line(f"Known recipes: {count}"), _line("Use recipes, recipe <name>, and craft preview <recipe> for player-safe details.")]
        if admin:
            rows.append(_line("Admin detail: actor_recipe_knowledge preserves independent knowledge sources."))
        return self._section("RECIPES", rows)

    def render_currencies(self, actor: Actor, admin: bool = False) -> str:
        data = actor.plugin_data.get("currencies", {})
        keys = CURRENCY_FIELDS + [k for k in data if k not in CURRENCY_FIELDS]
        return self._section("CURRENCIES", self._two_col([(_human(k), data.get(k, 0 if k in {"gold", "silver", "copper"} else "future"), "gold" if k in {"gold", "silver", "copper"} else "score_value") for k in keys]))

    def render_banking(self, actor: Actor, admin: bool = False) -> str:
        data = (actor.plugin_data.get("banking", {}) if getattr(actor, "plugin_data", None) else {})
        pairs = [("Banked Gold", data.get("gold", 0), "gold"), ("Banked Silver", data.get("silver", 0), "score_value"), ("Banked Copper", data.get("copper", 0), "score_value")]
        if admin:
            pairs.append(("Bank Account IDs", data.get("bank_account_ids", "available through EconomyService"), "score_value"))
        return self._section("BANKING", self._two_col(pairs))

    def render_transactions(self, actor: Actor, admin: bool = False) -> str:
        data = (actor.plugin_data.get("transactions", []) if getattr(actor, "plugin_data", None) else [])
        rows = [_line(str(x)[:BOX_WIDTH-6]) for x in data[-5:]] or [_line("Recent transactions are available from EconomyService ledger traces.")]
        if admin:
            rows.append(_line("Admin trace includes transaction IDs, quote IDs, and ledger entry IDs."))
        return self._section("TRANSACTIONS", rows)

    def render_relationships(self, actor: Actor, admin: bool = False) -> str:
        data = actor.relationship_profile or {}
        return self._section("RELATIONSHIPS", self._two_col([(_human(k), data.get(k, "future"), "score_value") for k in RELATIONSHIP_FIELDS]))

    def render_simulation(self, actor: Actor, admin: bool = False) -> str:
        data = actor.simulation_profile or {}
        pairs = [(_human(k), data.get(k, "future"), "score_value") for k in SIMULATION_FIELDS]
        if admin:
            pairs.extend([("Need Profile", actor.need_profile or "future", "score_value"), ("Goal Profile", actor.goal_profile or "future", "score_value"), ("Memory Profile", actor.memory_profile or "future", "score_value")])
        return self._section("SIMULATION", self._two_col(pairs))

    def render_diagnostics(self, actor: Actor, admin: bool = False) -> str:
        warnings = []
        if not actor.identity.name or actor.identity.name == "Unnamed":
            warnings.append("Missing identity.name")
        missing = [k for k, v in actor.attributes.items() if v is None]
        if missing:
            warnings.append("Missing base attributes: " + ", ".join(missing))
        data = {"actor_id": actor.actor_id, "actor_type": actor.actor_type, "builder_metadata": actor.builder_metadata, "validation_warnings": warnings or ["none"], "renderer_sections": self.order, "single_renderer": "ActorScoreRenderer", "future_formula_names": {s.formula_name: self.formula_registry.has(s.formula_name) for s in actor.derived_statistics_cache.values()}, "derived_placeholders": list(actor.derived_statistics_cache)}
        return self._section("BUILDER DIAGNOSTICS", self._two_col([(_human(k), v, "score_value") for k, v in data.items()]))

    def render_formulas(self, actor: Actor, admin: bool = False) -> str:
        rows = [_line("Statistic             Formula                  Base       Modifiers       Final")]
        for key, stat in actor.derived_statistics_cache.items():
            formula = getattr(stat, "formula_name", key)
            label = getattr(stat, "label", _human(key))
            rows.append(_line(f"{label:<21} {formula:<24} placeholder placeholder    placeholder"))
        return self._section("FORMULA DEBUG", rows)

    def render_raw(self, actor: Actor, admin: bool = False) -> str:
        text = json.dumps(actor.to_dict(), indent=2, sort_keys=True, default=_json_default)
        return self._section("RAW ACTOR JSON", [_line(line[: BOX_WIDTH - 6]) for line in text.splitlines()])
