"""Smart MUD command engine with deterministic and hybrid routing."""

from __future__ import annotations

from dataclasses import dataclass, is_dataclass, asdict
from typing import Any, Optional, Callable
import json
import re
import logging
import sqlite3
import traceback
import copy

logger = logging.getLogger(__name__)

def _command_exception_context(character: Any, command_text: str, resolved_command: str) -> dict[str, Any]:
    rt = getattr(character, "runtime", None)
    return {
        "command_text": command_text,
        "resolved_command_or_ability_id": resolved_command,
        "actor_id": getattr(character, "id", ""),
        "actor_name": getattr(character, "name", ""),
        "room_id": getattr(character, "room_id", getattr(character, "current_room_id", "")),
        "world_id": getattr(rt, "active_world_id", getattr(character, "world_id", "")) if rt else getattr(character, "world_id", ""),
    }

from pathlib import Path
from engine.mud_displays import semantic, DisplayDocument, DisplayIntent, DisplayLine, DisplaySection, DisplayField, render_display_mud, render_display_plain, build_score_document, build_worth_document, build_abilities_document, build_inventory_document, build_equipment_document, build_affects_document, build_prompt_document, PROMPT_PRESETS, PROMPT_MAX_LENGTH
from engine.actors import actor_from_runtime_character
from engine.character_state import build_action_state, reconcile_actor_position, derive_position_from_health
from engine.formulas import FormulaEngine
from engine.character_stats import CharacterAttributeService, CombatStatService, _load_json
from engine.builder_content_editor import BuilderContentEditor
from engine.builder_stat_content import (AttributeDocumentAdapter, FormulaDocumentAdapter, StatDefinitionDocumentAdapter, ResistanceDocumentAdapter, EncumbranceDocumentAdapter, PostureDocumentAdapter, RangeRulesDocumentAdapter, CombatMessageDocumentAdapter, StatCombatPublishValidator, StatCombatPublisher, parse_bool, parse_num, safe_id, norm_hash, now)
from engine.score_renderer import ActorScoreRenderer
from engine.command_registry import CommandRegistry
from smart_mud.builder import BuilderWorkspace, BuilderService
from engine.abilities import AbilityExecutionService
from engine.help_service import HelpService, HelpEntry, normalize_help_query
from engine.display_services import CharacterDisplaySnapshotService, AbilityDisplaySnapshotService, ability_snapshots_as_rows
from engine.player_preferences import PlayerPresentationPreferenceService
from engine.display_themes import preview_display_theme, resolve_effective_display_theme, load_display_themes, SUPPORTED_FAMILIES, ThemeResolutionMode
from engine.combat_behavior import CombatBehaviorService
from engine.crafting import CraftingService, CraftingContent
from engine.perception import PerceptionService
from engine.survival_needs import SURVIVAL_COLLECTIONS


@dataclass
class CommandResult:
    """Result of command execution.

    Commands may return a structured display_document. Runtime renderers use it
    first, while legacy narrative remains supported during migration.
    """
    narrative: str = ""
    prompt: str = ""
    scrollback: str = ""
    state_updates: dict[str, Any] = None
    should_exit: bool = False
    ok: bool = True
    display_document: Any = None
    display_intent: str = "SYSTEM"
    semantic_role: str = "system"


# Known deterministic commands (no AI needed)
DETERMINISTIC_COMMANDS = {
    # Information
    "score": {"category": "info", "aliases": ["sc"], "admin": False},
    "attributes": {"category": "info", "admin": False},
    "stats": {"category": "info", "admin": False},
    "display": {"category": "info", "admin": False},
    "displaytheme": {"category": "builder", "admin": True},
    "recipes": {"category": "crafting", "admin": False},
    "recipe": {"category": "crafting", "admin": False},
    "craft": {"category": "crafting", "admin": False},
"cook": {"category": "crafting", "admin": False},
    "prepare": {"category": "crafting", "admin": False},
    "ingredients": {"category": "crafting", "admin": False},
    "preserve": {"category": "crafting", "admin": False},
    "meal": {"category": "crafting", "admin": False},
    "crafting": {"category": "crafting", "admin": False},
    "professions": {"category": "crafting", "admin": False},
    "profession": {"category": "crafting", "admin": False},
    "salvage": {"category": "crafting", "admin": False},
    "refine": {"category": "crafting", "admin": False},
    "worth": {"category": "info", "admin": False},
    "finger": {"category": "info", "admin": False},
    "inventory": {"category": "info", "aliases": ["inv", "i"], "admin": False},
    "equipment": {"category": "info", "aliases": ["eq"], "admin": False},
    "spells": {"category": "info", "aliases": ["sp"], "admin": False},
    "skills": {"category": "info", "aliases": ["sk"], "admin": False},
    "abilities": {"category": "info", "admin": False},
    "achievements": {"category": "info", "admin": False},
    "achievement": {"category": "info", "admin": False},
    "milestones": {"category": "info", "admin": False},
    "collections": {"category": "info", "admin": False},
    "collection": {"category": "info", "admin": False},
    "titles": {"category": "info", "admin": False},
    "title": {"category": "info", "admin": False},
    "accolades": {"category": "info", "admin": False},
    "profile": {"category": "info", "admin": False},
    "affects": {"category": "info", "aliases": ["aff", "saff"], "admin": False},
    "spellup": {"category": "info", "admin": False},
    "resists": {"category": "info", "aliases": ["resistances"], "admin": False},
    "who": {"category": "info", "admin": False},
    "whoami": {"category": "info", "admin": False},
    "where": {"category": "info", "admin": False},
    "commands": {"category": "help", "aliases": ["cmds"], "admin": False},
    "help": {"category": "help", "aliases": ["h"], "admin": False},
    "helpedit": {"category": "builder", "admin": True},
    "socials": {"category": "help", "admin": False},
    "areas": {"category": "info", "admin": False},
    "map": {"category": "info", "admin": False},
    "time": {"category": "info", "admin": False},
    "weather": {"category": "info", "admin": False},
    "practice": {"category": "info", "aliases": ["prac", "pr"], "admin": False},
    "train": {"category": "shop", "aliases": ["tr"], "admin": False},
    "buypractice": {"category": "shop", "aliases": ["buyprac"], "admin": False},
    "buytrain": {"category": "shop", "admin": False},
    "study": {"category": "shop", "admin": False},
    "list": {"category": "shop", "admin": False},
    "buy": {"category": "shop", "admin": False},
    "sell": {"category": "shop", "admin": False},
    "value": {"category": "shop", "admin": False},
    "consider": {"category": "combat", "aliases": ["con", "cons", "consi"], "admin": False},
    "diagnose": {"category": "combat", "aliases": ["diag"], "admin": False},
    "kill": {"category": "combat", "aliases": ["k"], "admin": False},
    "attack": {"category": "combat", "aliases": ["hit"], "admin": False},
    "assist": {"category": "combat", "admin": False},
    "flee": {"category": "combat", "admin": False},
    "defend": {"category": "combat", "admin": False},
    "combat": {"category": "combat", "admin": False},
    "combatstats": {"category": "info", "admin": False},
    "combatbreakdown": {"category": "builder", "admin": True},
    "statbreakdown": {"category": "info", "admin": False},
    "attributeedit": {"category": "builder", "admin": True},
    "formula": {"category": "builder", "admin": True},
    "statdef": {"category": "builder", "admin": True},
    "resistanceedit": {"category": "builder", "admin": True},
    "encumbranceedit": {"category": "builder", "admin": True},
    "postureedit": {"category": "builder", "admin": True},
    "rangeedit": {"category": "builder", "admin": True},
    "combatmessage": {"category": "builder", "admin": True},
    "target": {"category": "combat", "admin": False},
    "history": {"category": "info", "admin": False},
    
    # Movement
    "north": {"category": "movement", "aliases": ["n"], "admin": False},
    "south": {"category": "movement", "aliases": ["s"], "admin": False},
    "east": {"category": "movement", "aliases": ["e"], "admin": False},
    "west": {"category": "movement", "aliases": ["w"], "admin": False},
    "up": {"category": "movement", "aliases": ["u"], "admin": False},
    "down": {"category": "movement", "aliases": ["d"], "admin": False},
    "in": {"category": "movement", "admin": False},
    "out": {"category": "movement", "admin": False},
    "northeast": {"category": "movement", "aliases": ["ne"], "admin": False},
    "northwest": {"category": "movement", "aliases": ["nw"], "admin": False},
    "southeast": {"category": "movement", "aliases": ["se"], "admin": False},
    "southwest": {"category": "movement", "aliases": ["sw"], "admin": False},
    "look": {"category": "movement", "aliases": ["l", "glance"], "admin": False},
    "scan": {"category": "info", "admin": False},
    "examine": {"category": "movement", "aliases": ["exa", "exam", "inspect"], "admin": False},
    "identify": {"category": "interaction", "aliases": ["id"], "admin": False},
    "use": {"category": "interaction", "admin": False},
    "read": {"category": "interaction", "admin": False},
    "pray": {"category": "interaction", "admin": False},
    "touch": {"category": "interaction", "admin": False},
    "push": {"category": "interaction", "admin": False},
    "pull": {"category": "interaction", "admin": False},
    "climb": {"category": "interaction", "admin": False},
    "get": {"category": "item", "aliases": ["take", "pickup"], "admin": False},
    "loot": {"category": "item", "admin": False},
    "sacrifice": {"category": "item", "aliases": ["sac"], "admin": False},
    "drop": {"category": "item", "admin": False},
    "wear": {"category": "item", "admin": False},
    "remove": {"category": "item", "aliases": ["rem"], "admin": False},
    "wield": {"category": "item", "admin": False},
    "unwield": {"category": "item", "admin": False},
    "hold": {"category": "item", "admin": False},
    "mainhand": {"category": "item", "admin": False},
    "offhand": {"category": "item", "admin": False},
    "dual": {"category": "item", "admin": False},
    "unequip": {"category": "item", "admin": False},
    "enter": {"category": "interaction", "admin": False},
    "leave": {"category": "interaction", "admin": False},
    "drink": {"category": "interaction", "admin": False},
    "eat": {"category": "interaction", "admin": False},
    "open": {"category": "interaction", "admin": False},
    "close": {"category": "interaction", "admin": False},
    "lock": {"category": "interaction", "admin": False},
    "unlock": {"category": "interaction", "admin": False},
    "pick": {"category": "interaction", "admin": False},
    "run": {"category": "movement", "admin": False},
    "walk": {"category": "movement", "admin": False},
    "search": {"category": "interaction", "admin": False},
    "listen": {"category": "interaction", "admin": False},
    "smell": {"category": "interaction", "admin": False},
    "hide": {"category": "interaction", "admin": False},
    "unhide": {"category": "interaction", "admin": False},
    "stealth": {"category": "info", "admin": False},
    "track": {"category": "interaction", "admin": False},
    "tracks": {"category": "interaction", "admin": False},
    "investigate": {"category": "interaction", "admin": False},
    "conceal": {"category": "interaction", "admin": False},
    "reveal": {"category": "interaction", "admin": False},
    "secrets": {"category": "info", "admin": False},
    "discovered": {"category": "info", "admin": False},
    "perception": {"category": "info", "admin": False},
    "awareness": {"category": "info", "admin": False},
    "sit": {"category": "interaction", "admin": False},
    "stand": {"category": "interaction", "admin": False},
    "rest": {"category": "interaction", "admin": False},
    "sleep": {"category": "interaction", "aliases": ["lay", "lie"], "admin": False},
    "wake": {"category": "interaction", "admin": False},
    "talk": {"category": "communication", "admin": False},
    "greet": {"category": "communication", "admin": False},
    "hello": {"category": "communication", "admin": False},
    "give": {"category": "interaction", "admin": False},
    "put": {"category": "interaction", "admin": False},
    "say": {"category": "communication", "admin": False},
    "emote": {"category": "communication", "admin": False},
    "restart": {"category": "system", "admin": False},
    "reconnect": {"category": "system", "admin": False},
    "disconnect": {"category": "system", "admin": False},
    "logout": {"category": "system", "admin": False},
    "quit": {"category": "system", "admin": False},
    
    # Admin/builder
    "wizhelp": {"category": "admin", "admin": True},
    "goto": {"category": "admin", "admin": True},
    "transfer": {"category": "admin", "admin": True},
    "stat": {"category": "admin", "admin": True},
    "restore": {"category": "admin", "admin": True},
    "load": {"category": "admin", "admin": True},
    "purge": {"category": "admin", "admin": True},
    "set": {"category": "admin", "admin": True},
    "dig": {"category": "builder", "admin": True},
    "redit": {"category": "builder", "admin": True},
    "oedit": {"category": "builder", "admin": True},
    "medit": {"category": "builder", "admin": True},
    "zedit": {"category": "builder", "admin": True},
    "sedit": {"category": "builder", "admin": True},
    "aedit": {"category": "builder", "admin": True},
}


class MudCommandEngine:
    """Command execution engine with deterministic and AI-assisted routing."""

    def __init__(self, state_store=None, ai_provider=None, event_bus=None):
        self.state_store = state_store
        self.ai_provider = ai_provider
        self.event_bus = event_bus
        self.registry = CommandRegistry(event_bus=event_bus)
        self.builder = BuilderWorkspace(event_bus=event_bus)
        self.builder_service = BuilderService(self.builder)
        self.command_handlers: dict[str, Callable] = {
            # Info commands
            "score": self._cmd_score,
            "progressioninspect": self._cmd_progression_repair,
            "progressionrepair": self._cmd_progression_repair,
            "advancementinspect": self._cmd_advancement_repair,
            "advancementrepair": self._cmd_advancement_repair,
            "display": self._cmd_display,
            "displaytheme": self._cmd_displaytheme,
            "recipes": self._cmd_crafting_player,
            "recipe": self._cmd_crafting_player,
            "craft": self._cmd_crafting_player,
            "cook": self._cmd_crafting_player,
            "prepare": self._cmd_crafting_player,
            "ingredients": self._cmd_crafting_player,
            "preserve": self._cmd_crafting_player,
            "meal": self._cmd_crafting_player,
            "crafting": self._cmd_crafting_player,
            "professions": self._cmd_crafting_player,
            "profession": self._cmd_crafting_player,
            "salvage": self._cmd_crafting_player,
            "refine": self._cmd_crafting_player,
            "worth": self._cmd_worth,
            "inventory": self._cmd_inventory,
            "equipment": self._cmd_equipment,
            "sacrifice": self._cmd_runtime_item,
            "get": self._cmd_runtime_item,
            "take": self._cmd_runtime_item,
            "pickup": self._cmd_runtime_item,
            "drop": self._cmd_runtime_item,
            "put": self._cmd_runtime_item,
            "give": self._cmd_runtime_item,
            "examine": self._cmd_runtime_item,
            "exa": self._cmd_runtime_item,
            "exam": self._cmd_runtime_item,
            "inspect": self._cmd_runtime_item,
            "resists": self._cmd_resists,
            "spellup": self._cmd_spellup,
            "spells": self._cmd_spells,
            "skills": self._cmd_skills,
            "abilitydiagnose": self._cmd_abilitydiagnose,
            "showvnums": self._cmd_showvnums,
            "abilities": self._cmd_abilities,
            "achievements": self._cmd_achievements,
            "achievement": self._cmd_achievements,
            "milestones": self._cmd_achievements,
            "collections": self._cmd_achievements,
            "collection": self._cmd_achievements,
            "titles": self._cmd_achievements,
            "title": self._cmd_title,
            "accolades": self._cmd_achievements,
            "profile": self._cmd_achievements,
            "ability": self._cmd_ability_detail,
            "use": self._cmd_use_ability,
            "cast": self._cmd_use_ability,
            "invoke": self._cmd_use_ability,
            "perform": self._cmd_use_ability,
            "cancel": self._cmd_cancel_ability,
            "cooldowns": self._cmd_cooldowns,
            "abilitylist": self._cmd_builder_ability,
            "abilitystat": self._cmd_builder_ability,
            "abilitycreate": self._cmd_builder_ability,
            "abilityclone": self._cmd_builder_ability,
            "abilityset": self._cmd_builder_ability,
            "abilitydelete": self._cmd_builder_ability,
            "abilityvalidate": self._cmd_builder_ability,
            "abilitypreview": self._cmd_builder_ability,
            "abilitytrace": self._cmd_builder_ability,
            "loadoutlist": self._cmd_builder_loadout,
            "loadoutstat": self._cmd_builder_loadout,
            "loadoutcreate": self._cmd_builder_loadout,
            "loadoutclone": self._cmd_builder_loadout,
            "loadoutset": self._cmd_builder_loadout,
            "loadoutability": self._cmd_builder_loadout,
            "loadoutdelete": self._cmd_builder_loadout,
            "loadoutvalidate": self._cmd_builder_loadout,
            "abilitygrant": self._cmd_ability_grant,
            "abilityrevoke": self._cmd_ability_grant,
            "actorabilities": self._cmd_actorabilities,
            "abilitycooldowns": self._cmd_abilitycooldowns,
            "abilitycasts": self._cmd_abilitycasts,
            "affects": self._cmd_affects,

            "resetlist": self._cmd_builder_reset, "resetstat": self._cmd_builder_reset, "resetcreate": self._cmd_builder_reset, "resetclone": self._cmd_builder_reset, "resetset": self._cmd_builder_reset, "resetdelete": self._cmd_builder_reset, "resetcommand": self._cmd_builder_reset, "resetvalidate": self._cmd_builder_reset, "resetpreview": self._cmd_builder_reset, "resetrun": self._cmd_builder_reset, "resethistory": self._cmd_builder_reset, "resettrace": self._cmd_builder_reset, "zreset": self._cmd_builder_reset, "zresetstat": self._cmd_builder_reset, "zresetpreview": self._cmd_builder_reset, "zresetrun": self._cmd_builder_reset,
            "who": self._cmd_who,
            "whoami": self._cmd_whoami,
            "save": self._cmd_save,
            "asave": self._cmd_asave,
            "desc": self._cmd_builder_edit,
            "recall": self._cmd_direct_ability,
            "grantrole": self._cmd_grantrole,
            "help": self._cmd_help,
            "helpedit": self._cmd_helpedit,
            "attributes": self._cmd_attributes,
            "stats": self._cmd_attributes,
            "combatstats": self._cmd_combatstats,
            "combatbreakdown": self._cmd_combatbreakdown,
            "statbreakdown": self._cmd_statbreakdown,
            "attributeedit": self._cmd_attributeedit,
            "formula": self._cmd_formulaedit,
            "formulaedit": self._cmd_formulaedit,
            "statdef": self._cmd_statdef,
            "resistanceedit": self._cmd_resistanceedit,
            "encumbranceedit": self._cmd_encumbranceedit,
            "postureedit": self._cmd_postureedit,
            "rangeedit": self._cmd_rangeedit,
            "combatmessage": self._cmd_combatmessage,
            "perfstat": self._cmd_perfstat,
            "violenceprofile": self._cmd_runtime_admin,
            "warmupstat": self._cmd_runtime_admin,
            "warmuptrace": self._cmd_runtime_admin,
            "combatcache": self._cmd_runtime_admin,
            "pulseinfo": self._cmd_runtime_admin,
            "pointinfo": self._cmd_runtime_admin,
            "adminstatus": self._cmd_runtime_admin,
            "pulsetrace": self._cmd_runtime_admin,
            "pointtrace": self._cmd_runtime_admin,
            "pulseforce": self._cmd_runtime_admin,
            "residentlist": self._cmd_runtime_admin,
            "residentstat": self._cmd_runtime_admin,
            "occupancystat": self._cmd_runtime_admin,
            "occupancyvalidate": self._cmd_runtime_admin,
            "occupancy": self._cmd_runtime_admin,
            "latencystat": self._cmd_runtime_admin,
            "commandtrace": self._cmd_runtime_admin,
            "restore": self._cmd_restore,
            "restorestat": self._cmd_restore,
            "stateinspect": self._cmd_stateinspect,
            "staterepair": self._cmd_stateinspect,
            "combatstate": self._cmd_stateinspect,
            "condition": self._cmd_condition,
            "commands": self._cmd_commands,
            "look": self._cmd_look,
            "hide": self._cmd_perception,
            "unhide": self._cmd_perception,
            "stealth": self._cmd_perception,
            "search": self._cmd_perception,
            "investigate": self._cmd_perception,
            "track": self._cmd_perception,
            "tracks": self._cmd_perception,
            "listen": self._cmd_perception,
            "smell": self._cmd_perception,
            "conceal": self._cmd_perception,
            "reveal": self._cmd_perception,
            "secrets": self._cmd_perception,
            "discovered": self._cmd_perception,
            "perception": self._cmd_perception,
            "awareness": self._cmd_perception,
            "say": self._cmd_say,
            "emote": self._cmd_emote,
            "study": self._cmd_generic,
            "train": self._cmd_training_player,
            "tr": self._cmd_training_player,
            "practice": self._cmd_training_player,
            "prac": self._cmd_training_player,
            "pr": self._cmd_training_player,
            "buypractice": self._cmd_training_player,
            "buyprac": self._cmd_training_player,
            "buytrain": self._cmd_training_player,
            "socials": self._cmd_generic,
            "holler": self._cmd_generic,
            "shout": self._cmd_generic,
            "gossip": self._cmd_generic,
            "whisper": self._cmd_generic,
            "ask": self._cmd_generic,
            "reply": self._cmd_generic,
            "tell": self._cmd_generic,
            "prompt": self._cmd_prompt,
            "afk": self._cmd_generic,
            "automap": self._cmd_generic,
            "autosplit": self._cmd_generic,
            "autogold": self._cmd_generic,
            "rewardlist": self._cmd_phase7a_reward, "rewardstat": self._cmd_phase7a_reward, "rewardcreate": self._cmd_phase7a_reward, "rewardclone": self._cmd_phase7a_reward, "rewardset": self._cmd_phase7a_reward, "rewardentry": self._cmd_phase7a_reward, "rewarddelete": self._cmd_phase7a_reward, "rewardvalidate": self._cmd_phase7a_reward, "rewardpreview": self._cmd_phase7a_reward,
            "loottablelist": self._cmd_phase7a_reward, "loottablestat": self._cmd_phase7a_reward, "loottablecreate": self._cmd_phase7a_reward, "loottableclone": self._cmd_phase7a_reward, "loottableset": self._cmd_phase7a_reward, "lootentry": self._cmd_phase7a_reward, "loottabledelete": self._cmd_phase7a_reward, "loottablevalidate": self._cmd_phase7a_reward, "loottablepreview": self._cmd_phase7a_reward,
            "treasurelist": self._cmd_phase7a_reward, "treasurestat": self._cmd_phase7a_reward, "treasurecreate": self._cmd_phase7a_reward, "treasureclone": self._cmd_phase7a_reward, "treasureset": self._cmd_phase7a_reward, "treasuredelete": self._cmd_phase7a_reward, "treasurevalidate": self._cmd_phase7a_reward, "treasurepreview": self._cmd_phase7a_reward,
            "deathlootlist": self._cmd_phase7a_reward, "deathlootstat": self._cmd_phase7a_reward, "deathlootcreate": self._cmd_phase7a_reward, "deathlootset": self._cmd_phase7a_reward, "deathlootclone": self._cmd_phase7a_reward, "deathlootdelete": self._cmd_phase7a_reward, "deathlootvalidate": self._cmd_phase7a_reward,
            "corpsedecaylist": self._cmd_phase7a_reward, "corpsedecaystat": self._cmd_phase7a_reward, "corpsedecaycreate": self._cmd_phase7a_reward, "corpsedecayset": self._cmd_phase7a_reward, "corpsedecaydelete": self._cmd_phase7a_reward, "corpsedecayvalidate": self._cmd_phase7a_reward,
            "nodelist": self._cmd_phase7a_reward, "nodestat": self._cmd_phase7a_reward, "nodecreate": self._cmd_phase7a_reward, "nodeset": self._cmd_phase7a_reward, "nodeclone": self._cmd_phase7a_reward, "nodedelete": self._cmd_phase7a_reward, "nodevalidate": self._cmd_phase7a_reward, "nodepreview": self._cmd_phase7a_reward,
            "rewardresolve": self._cmd_phase7a_reward, "rewarddeliver": self._cmd_phase7a_reward, "rewardretry": self._cmd_phase7a_reward, "rewardcancel": self._cmd_phase7a_reward, "rewardpacket": self._cmd_phase7a_reward, "rewardtrace": self._cmd_phase7a_reward, "lootresolve": self._cmd_phase7a_reward, "loottrace": self._cmd_phase7a_reward, "corpsecontents": self._cmd_phase7a_reward, "corpseloottrace": self._cmd_phase7a_reward, "corpsedecay": self._cmd_phase7a_reward, "grantreward": self._cmd_phase7a_reward, "claimlist": self._cmd_phase7a_reward, "rewards": self._cmd_phase7a_reward, "claim": self._cmd_phase7a_reward, "rewardhistory": self._cmd_phase7a_reward,
            "currency": self._cmd_phase7b_economy, "transactions": self._cmd_phase7b_economy, "balance": self._cmd_phase7b_economy, "deposit": self._cmd_phase7b_economy, "withdraw": self._cmd_phase7b_economy, "exchange": self._cmd_phase7b_economy,
            "list": self._cmd_phase7b_economy, "shop": self._cmd_phase7b_economy, "buy": self._cmd_phase7b_economy, "sell": self._cmd_phase7b_economy, "value": self._cmd_phase7b_economy, "appraise": self._cmd_phase7b_economy, "buyback": self._cmd_phase7b_economy, "services": self._cmd_phase7b_economy, "identify": self._cmd_phase7b_economy, "repair": self._cmd_phase7b_economy, "quote": self._cmd_phase7b_economy,
            "currencylist": self._cmd_phase7b_economy, "currencystat": self._cmd_phase7b_economy, "currencycreate": self._cmd_phase7b_economy, "currencyclone": self._cmd_phase7b_economy, "currencyset": self._cmd_phase7b_economy, "currencydelete": self._cmd_phase7b_economy, "currencyvalidate": self._cmd_phase7b_economy, "currencypreview": self._cmd_phase7b_economy,
            "shoplist": self._cmd_phase7b_economy, "shopstat": self._cmd_phase7b_economy, "shopcreate": self._cmd_phase7b_economy, "shopclone": self._cmd_phase7b_economy, "shopset": self._cmd_phase7b_economy, "shopdelete": self._cmd_phase7b_economy, "shopvalidate": self._cmd_phase7b_economy, "shoppreview": self._cmd_phase7b_economy, "stocklist": self._cmd_phase7b_economy, "stockadd": self._cmd_phase7b_economy, "stockset": self._cmd_phase7b_economy, "stockdelete": self._cmd_phase7b_economy, "stockvalidate": self._cmd_phase7b_economy, "stockpreview": self._cmd_phase7b_economy,
            "pricinglist": self._cmd_phase7b_economy, "pricingstat": self._cmd_phase7b_economy, "pricingcreate": self._cmd_phase7b_economy, "pricingclone": self._cmd_phase7b_economy, "pricingset": self._cmd_phase7b_economy, "pricingdelete": self._cmd_phase7b_economy, "pricingvalidate": self._cmd_phase7b_economy, "pricingtrace": self._cmd_phase7b_economy, "servicelist": self._cmd_phase7b_economy, "servicestat": self._cmd_phase7b_economy, "servicecreate": self._cmd_phase7b_economy, "serviceclone": self._cmd_phase7b_economy, "serviceset": self._cmd_phase7b_economy, "servicedelete": self._cmd_phase7b_economy, "servicevalidate": self._cmd_phase7b_economy, "servicepreview": self._cmd_phase7b_economy,
            "repairprofilelist": self._cmd_phase7b_economy, "repairprofilestat": self._cmd_phase7b_economy, "repairprofilecreate": self._cmd_phase7b_economy, "repairprofileset": self._cmd_phase7b_economy, "repairprofiledelete": self._cmd_phase7b_economy, "repairprofilevalidate": self._cmd_phase7b_economy, "bankprofilelist": self._cmd_phase7b_economy, "bankprofilestat": self._cmd_phase7b_economy, "bankprofilecreate": self._cmd_phase7b_economy, "bankprofileset": self._cmd_phase7b_economy, "bankprofiledelete": self._cmd_phase7b_economy, "bankprofilevalidate": self._cmd_phase7b_economy, "restocklist": self._cmd_phase7b_economy, "restockstat": self._cmd_phase7b_economy, "restockcreate": self._cmd_phase7b_economy, "restockset": self._cmd_phase7b_economy, "restockdelete": self._cmd_phase7b_economy, "restockvalidate": self._cmd_phase7b_economy, "restockpreview": self._cmd_phase7b_economy,
            "currencybalance": self._cmd_phase7b_economy, "currencygrant": self._cmd_phase7b_economy, "currencyremove": self._cmd_phase7b_economy, "ledger": self._cmd_phase7b_economy, "currencytrace": self._cmd_phase7b_economy, "ledgertrace": self._cmd_phase7b_economy, "transactionstat": self._cmd_phase7b_economy, "transactiontrace": self._cmd_phase7b_economy, "quotetrace": self._cmd_phase7b_economy, "shopstock": self._cmd_phase7b_economy, "shoprestock": self._cmd_phase7b_economy, "shopopen": self._cmd_phase7b_economy, "shopclose": self._cmd_phase7b_economy, "bankaccount": self._cmd_phase7b_economy, "banktrace": self._cmd_phase7b_economy, "economyaudit": self._cmd_phase7b_economy, "shopaudit": self._cmd_phase7b_economy, "shopstocktrace": self._cmd_phase7b_economy, "servicetrace": self._cmd_phase7b_economy, "repairtrace": self._cmd_phase7b_economy, "conversiontrace": self._cmd_phase7b_economy,
            "autoloot": self._cmd_generic,
            "autoexits": self._cmd_generic,
            "compact": self._cmd_generic,
            "brief": self._cmd_generic,
            "dismount": self._cmd_generic,
            "mount": self._cmd_generic,
            "unfollow": self._cmd_generic,
            "follow": self._cmd_generic,
            "pour": self._cmd_generic,
            "fill": self._cmd_generic,
            "taste": self._cmd_generic,
            "diagnose": self._cmd_combat_foundation,
            "consider": self._cmd_combat_foundation,
            "kill": self._cmd_combat_foundation,
            "attack": self._cmd_combat_foundation,
            "assist": self._cmd_combat_foundation,
            "flee": self._cmd_combat_foundation,
            "defend": self._cmd_combat_foundation,
            "combat": self._cmd_combat_foundation,
            "target": self._cmd_combat_foundation,
            "levels": self._cmd_generic,
            "time": self._cmd_worldtime,
            "worldtime": self._cmd_worldtime,
            "simulation": self._cmd_simulation,
            "weather": self._cmd_environment,
            "forecast": self._cmd_environment,
            "season": self._cmd_environment,
            "dayperiod": self._cmd_environment,
            "environment": self._cmd_environment,
            "temperature": self._cmd_environment,
            "shelter": self._cmd_environment,
            "visibility": self._cmd_environment,
            "roomlight": self._cmd_environment,
            "light": self._cmd_environment,
            "extinguish": self._cmd_environment,
            "environmenttick": self._cmd_environment,
            "environmenttrace": self._cmd_environment,
            "weathertrace": self._cmd_environment,
            "visibilitytrace": self._cmd_environment,
            "exposuretrace": self._cmd_environment,
            "environmentaudit": self._cmd_environment,
            "perceptionaudit": self._cmd_perception,
            "perceptiontrace": self._cmd_perception,
            "hidetrace": self._cmd_perception,
            "searchtrace": self._cmd_perception,
            "trackingtrace": self._cmd_perception,
            "trailtrace": self._cmd_perception,
            "soundtrace": self._cmd_perception,
            "soundpropagationtrace": self._cmd_perception,
            "scenttrace": self._cmd_perception,
            "secrettrace": self._cmd_perception,
            "knowledgetrace": self._cmd_perception,
            "perceptionreveal": self._cmd_perception,
            "perceptionforget": self._cmd_perception,
            "trailcreate": self._cmd_perception,
            "trailclear": self._cmd_perception,
            "soundemit": self._cmd_perception,
            "where": self._cmd_generic,
            "home": self._cmd_goto,
            "rooms": self._cmd_builder_nav,
            "rlist": self._cmd_builder_nav,
            "rfind": self._cmd_builder_nav,
            "rsearch": self._cmd_builder_nav,
            "rwhere": self._cmd_builder_nav,
            "btarget": self._cmd_builder_edit,
            "rtarget": self._cmd_builder_edit,
            "target": self._cmd_builder_edit,
            "map": self._cmd_builder_nav,
            "rmap": self._cmd_builder_nav,
            "areas": self._cmd_builder_nav,
            "alist": self._cmd_builder_nav,
            "acreate": self._cmd_area,
            "aedit": self._cmd_area,
            "astat": self._cmd_area,
            "aset": self._cmd_area,
            "adelete": self._cmd_area,
            "zones": self._cmd_builder_nav,
            "zlist": self._cmd_builder_nav,
            "zcreate": self._cmd_zone,
            "zedit": self._cmd_zone,
            "zstat": self._cmd_zone,
            "zset": self._cmd_zone,
            "zdelete": self._cmd_zone,
            "vnum": self._cmd_builder_discovery,
            "splist": self._cmd_builder_discovery,
            "resetlist": self._cmd_builder_discovery,
            "dig": self._cmd_dig,
            "undig": self._cmd_undig,
            "rdig": self._cmd_rdig,
            "relink": self._cmd_relink,
            "rlinks": self._cmd_rlinks,
            "link": self._cmd_link,
            "unlink": self._cmd_unlink,
            "del": self._cmd_delete_alias,
            "delete": self._cmd_delete_alias,
            "mlist": self._cmd_builder_discovery,
            "eprofile": self._cmd_living_entity, "etime": self._cmd_living_entity, "estate": self._cmd_living_entity, "eactivity": self._cmd_living_entity, "eneeds": self._cmd_living_entity, "egoals": self._cmd_living_entity, "goals": self._cmd_living_entity, "eschedule": self._cmd_living_entity, "erelationships": self._cmd_living_entity, "ememories": self._cmd_living_entity, "econtext": self._cmd_living_entity,
            "schedulelist": self._cmd_living_list, "needlist": self._cmd_living_list, "goallist": self._cmd_living_list, "relationshiplist": self._cmd_living_list, "memorylist": self._cmd_living_list,
            "olist": self._cmd_builder_discovery,
            "exits": self._cmd_builder_nav,
            "x": self._cmd_builder_nav,
            "back": self._cmd_builder_nav,
            "forward": self._cmd_builder_nav,
            "bstatus": self._cmd_builder,
            "status": self._cmd_builder,

            # Builder foundation
            "builder": self._cmd_builder,
            "build": self._cmd_builder,
            "bnorm": self._cmd_builder_normalize,
            "scan": self._cmd_scan,
            "rassign": self._cmd_room_assign,
            "rmove": self._cmd_room_assign,
            "rrenameid": self._cmd_room_assign,
            # Admin
            "wizhelp": self._cmd_wizhelp,
            "goto": self._cmd_goto,
            "stat": self._cmd_stat,
            "formuladiag": self._cmd_formula_diag,
            "modifier": self._cmd_modifier_diag,
            "actor": self._cmd_actor_diag,
            "bodylist": self._cmd_phase5f, "bodyshow": self._cmd_phase5f, "slotlist": self._cmd_phase5f,
            "spawnlist": self._cmd_phase5f, "spawnshow": self._cmd_phase5f, "population": self._cmd_phase5f,
            "lifecycle": self._cmd_phase5f, "corpse": self._cmd_phase5f, "respawn": self._cmd_phase5f,
        }

        for _name in "senseprofilelist senseprofilestat senseprofilecreate senseprofileclone senseprofileset senseprofiledelete senseprofilevalidate perceptionprofilelist perceptionprofilestat perceptionprofilecreate perceptionprofileset perceptionprofiledelete perceptionprofilevalidate concealmentlist concealmentstat concealmentcreate concealmentset concealmentdelete concealmentvalidate searchprofilelist searchprofilestat searchprofilecreate searchprofileset searchprofiledelete searchprofilevalidate trackingprofilelist trackingprofilestat trackingprofilecreate trackingprofileset trackingprofiledelete trackingprofilevalidate soundprofilelist soundprofilestat soundprofilecreate soundprofileset soundprofiledelete soundprofilevalidate".split():
            self.command_handlers[_name] = self._cmd_perception
        for _name in " undo redo find mclone oclone rclone rsave redit rstat rcreate rset rdesc rname rexits rfeature rdelete exedit excreate exset exdelete fedit fcreate fset fdesc fdelete oedit ocreate oset odesc odelete ostat opreview ovalidate owhere ofind medit mcreate mset mdesc mdelete mstat spawnedit spawncreate spawnset spawndelete spawnstat zstat astat wstat btarget rtarget target bsave wsave".split():
            if _name:
                self.command_handlers[_name] = self._cmd_builder_edit
        for _name in ("rassign", "rmove", "rrenameid"):
            self.command_handlers[_name] = self._cmd_room_assign
        for _name in "cookingrecipelist cookingrecipestat cookingrecipecreate cookingrecipeclone cookingrecipeset cookingrecipedelete cookingrecipevalidate cookingrecipepreview ingredientprofilelist ingredientprofilestat ingredientprofilecreate ingredientprofileset ingredientprofiledelete ingredientprofilevalidate servingprofilelist servingprofilestat servingprofilecreate servingprofileset servingprofiledelete servingprofilevalidate nutritionprofilelist nutritionprofilestat nutritionprofilecreate nutritionprofileset nutritionprofiledelete nutritionprofilevalidate preservationprofilelist preservationprofilestat preservationprofilecreate preservationprofileset preservationprofiledelete preservationprofilevalidate cookingstart cookingcomplete cookinginterrupt cookingtrace cookingqualitytrace cookingservingtrace cookingfreshnesstrace cookingaudit foodfreshnessset foodservingset recipelist recipestat recipecreate recipeclone recipeset recipedelete recipevalidate recipepreview recipeinput recipeinputentry recipeoutput recipeoutputentry recipetool workstationlist workstationstat workstationcreate workstationclone workstationset workstationdelete workstationvalidate workstationpreview productionlist productionstat productioncreate productionset productionclone productiondelete productionvalidate qualitylist qualitystat qualitycreate qualityset qualityclone qualitydelete qualityvalidate craftpreview craftstart craftjob crafttrace craftcancel crafttick recipegrant reciperevoke actorrecipes professionstat professionxp workstationaudit craftingaudit recipeaudit recipetrace ingredienttrace workstationtrace qualitytrace professiontrace reservationtrace productiontrace".split():
            self.command_handlers[_name] = self._cmd_crafting_builder
        for _name in "achievementlist achievementstat achievementcreate achievementclone achievementset achievementdelete achievementvalidate achievementpreview criteriagrouplist criteriagroupstat criteriagroupcreate criteriagroupset criteriagroupdelete criteriagroupvalidate criterialist criteriastat criteriacreate criteriaclone criteriaset criteriadelete criteriavalidate criteriapreview titlelist titlestat titlecreate titleclone titleset titledelete titlevalidate accoladelist accoladestat accoladecreate accoladeset accoladedelete accoladevalidate collectionlist collectionstat collectioncreate collectionset collectiondelete collectionvalidate actorachievements achievementgrant achievementrevoke achievementprogress achievementreset achievementcomplete achievementtrace achievementevent achievementaudit titlegrant titlerevoke titleselect accoladegrant collectiongrant achievementeventtrace criteriatrace milestonetrace achievementrewardtrace titletrace accoladetrace collectiontrace".split():
            self.command_handlers[_name]=self._cmd_builder_achievement

        for _name in "resources survey resource gather forage harvest mine chop fish dig excavate salvage skin butcher extract".split():
            if _name not in self.command_handlers:
                self.command_handlers[_name] = self._cmd_gathering_player
        for _name in "property properties rent lease access home storage room locker store retrieve keys key".split():
            self.command_handlers[_name] = self._cmd_property_player

        for _name in "quests questlog journal quest objectives accept decline abandon turnin talk reply questlist queststat questcreate questclone questset questdelete questvalidate questpreview questtrace stagelist stagestat stagecreate stageclone stageset stagedelete stagevalidate objectivelist objectivestat objectivecreate objectiveclone objectiveset objectivedelete objectivevalidate objectivepreview branchlist branchadd branchset branchdelete branchvalidate questactionlist questactionadd questactionset questactiondelete questactionvalidate conversationlist conversationstat conversationcreate conversationclone conversationset conversationdelete conversationvalidate conversationpreview convnodelist convnodecreate convnodeset convnodedelete convchoiceadd convchoiceset convchoicedelete worldstatelist worldstatestat worldstateset worldstateclear worldstatehistory actorquests questoffer questaccept questadvance questcomplete questfail questabandon questreset questinstance questinstancetrace objectiveprogress questevent questtick questaudit conversationaudit worldstateaudit availabilitytrace objectivetrace questeventtrace branchtrace questrewardtrace conversationtrace worldstatetrace questtimertrace".split():
            self.command_handlers[_name] = self._cmd_phase8a_quest
        for _name in "behaviorlist behaviorstat behaviorvalidate behaviorpreview actorbehavior behaviortrace combatdecision combattrace combatcandidates threatlist threatstat threatadd threatclear hostilitytrace combattick protect protectset unprotect protectclear surrender callforhelp assisttrace fleetrace pursuittrace protecttrace combatgrouptrace petmode order".split():
            self.command_handlers[_name] = self._cmd_combat_behavior

        for _name in "needs hunger thirst fatigue food drink eat consume sip taste rest sleep wake camp campfire campsite fire make break light extinguish add inspect stop needlist needstat needcreate needclone needset needdelete needvalidate needpreview needsprofilelist needsprofilestat needsprofilecreate needsprofileset needsprofiledelete needsprofilevalidate consumablelist consumablestat consumablecreate consumableclone consumableset consumabledelete consumablevalidate consumablepreview needsinspect needsset needsmodify needstick needstrace consumptiontrace survivalaudit".split():
            self.command_handlers[_name] = self._cmd_survival_needs

        for _name in "quit logout disconnect reconnect restart".split():
            self.command_handlers[_name] = self._cmd_session
        for _name in "social socials wave bow nod salute point laugh smile cry cheer applaud hug highfive dance spit sit stand rest yawn stretch clap shake glare thank".split():
            self.command_handlers[_name] = self._cmd_social
        for _name in "stand sit rest sleep wake lay lie".split():
            self.command_handlers[_name] = self._cmd_position



    def _survival_service(self, character: Any):
        rt=getattr(self,'runtime',None)
        if rt and getattr(rt,'survival_needs',None): return rt.survival_needs
        from engine.survival_needs import SurvivalNeedsService
        store=getattr(rt,'state_store',None) or self.state_store
        world_id=getattr(rt,'active_world_id',None) or getattr(character,'world_id','shattered_realms') or 'shattered_realms'
        return SurvivalNeedsService(getattr(store,'db_path',Path('.smartmud_survival.sqlite3')), Path('worlds')/world_id, world_id, self.event_bus, rt)

    def _format_campsite_status(self, row: Any) -> str:
        if not row:
            return "There is no campsite here."
        status = row.get("status", "active") if isinstance(row, dict) else "active"
        return "A small campsite has been established here." if status in {"active","occupied","abandoned"} else "There is no campsite here."

    def _format_campfire_status(self, row: Any) -> str:
        if not row:
            return "There is no campfire here."
        status = str(row.get("status") or "unlit") if isinstance(row, dict) else "unlit"
        fuel = int((row.get("fuel_current") or row.get("fuel_amount") or 0) if isinstance(row, dict) else 0)
        
        if status == "lit": return "A small campfire burns steadily here."
        if status == "extinguished": return "Only a bed of cold ashes remains."
        return "A small unlit campfire rests within the campsite."

    def _cmd_session(self, character: Any, args: list[str], raw: str) -> CommandResult:
        cmd = (raw.split() or [""])[0].lower()
        rt = getattr(self, "runtime", None)
        actor_id = str(getattr(character, "id", ""))
        if cmd in {"quit", "logout", "disconnect"}:
            if self.event_bus:
                self.event_bus.publish("character_session_left", {"character_id": actor_id, "room_id": getattr(character, "room_id", ""), "command": cmd}, source_system="session", character_id=actor_id, room_id=getattr(character, "room_id", ""))
            if rt:
                try:
                    rt.unregister_live_character(actor_id)
                    rt.active_character_id = ""
                except Exception:
                    pass
            return CommandResult("You save your progress and leave the game. Choose a character to continue.", state_updates={"session_transition": "character_select"})
        if cmd == "reconnect":
            return CommandResult("You are already connected.")
        if cmd == "restart":
            return CommandResult("You cannot restart the game server. Use LOGOUT to leave your current character.", ok=False)
        return CommandResult("Use LOGOUT to leave your current character.", ok=False)

    SOCIAL_DEFINITIONS = {
        "hug": ("hugs themself awkwardly.", "hugs {target}."),
        "highfive": ("looks for someone to high-five.", "high-fives {target}."),
        "wave": ("waves.", "waves to {target}."),
        "smile": ("smiles.", "smiles at {target}."),
        "laugh": ("laughs.", "laughs with {target}."),
        "bow": ("bows.", "bows to {target}."),
        "nod": ("nods.", "nods to {target}."),
        "shake": ("shakes their head.", "shakes {target}'s hand."),
        "dance": ("dances.", "dances with {target}."),
        "cheer": ("cheers.", "cheers for {target}."),
        "clap": ("claps.", "claps for {target}."),
        "applaud": ("applauds.", "applauds {target}."),
        "point": ("points.", "points at {target}."),
        "cry": ("cries quietly.", "cries on {target}'s shoulder."),
        "sit": ("sits down.", "sits beside {target}."),
        "stand": ("stands up.", "stands beside {target}."),
        "rest": ("rests for a moment.", "rests beside {target}."),
        "yawn": ("yawns.", "yawns at {target}."),
        "stretch": ("stretches.", "stretches beside {target}."),
        "salute": ("salutes.", "salutes {target}."),
        "spit": ("spits on the ground.", "spits toward {target}."),
        "glare": ("glares.", "glares at {target}."),
        "thank": ("offers thanks.", "thanks {target}."),
    }

    def _cmd_social(self, character: Any, args: list[str], raw: str) -> CommandResult:
        social_id = self.resolve_alias((raw.split() or ["social"])[0].lower())
        if social_id == "socials" or social_id == "social":
            if not args:
                return CommandResult("Social commands:\n" + ", ".join(sorted(self.SOCIAL_DEFINITIONS)))
            social_id = args[0].lower()
            args = args[1:]
        if social_id not in self.SOCIAL_DEFINITIONS:
            return CommandResult("That social is not available. Use SOCIALS to list social commands.", ok=False)
        actor_name = str(getattr(character, "name", "Someone"))
        target_name = ""
        query = " ".join(args).strip()
        rt = getattr(self, "runtime", None)
        if query and rt and hasattr(rt, "_resolve_interaction_target"):
            resolved = rt._resolve_interaction_target(character, query)
            if resolved.get("status") == "ok":
                target = resolved.get("target") or {}
                target_name = str(target.get("name") or target.get("short_label") or query)
            elif resolved.get("status") == "ambiguous":
                return CommandResult("Which one do you mean?", ok=False)
            else:
                return CommandResult("You do not see that person here.", ok=False)
        no_target, with_target = self.SOCIAL_DEFINITIONS[social_id]
        text = f"{actor_name} {with_target.format(target=target_name)}" if target_name else f"{actor_name} {no_target}"
        if self.event_bus:
            self.event_bus.publish("social_emote_performed", {"actor_id": getattr(character, "id", ""), "actor_name": actor_name, "target_name": target_name, "social_id": social_id, "room_id": getattr(character, "room_id", "")}, source_system="social", character_id=getattr(character, "id", ""), room_id=getattr(character, "room_id", ""))
        return CommandResult(text)


    def _admin_ok(self, character: Any) -> bool:
        return str(getattr(character, "role", "player")).lower() in {"admin", "owner", "builder"} or int(getattr(character, "immortal_level", 0) or 0) > 0

    def _cmd_condition(self, character: Any, args: list[str], raw: str) -> CommandResult:
        rt = getattr(self, "runtime", None); cr = getattr(rt, "combat_runtime", None) if rt else None
        actor = actor_from_runtime_character(character, getattr(rt, "active_world_id", "") if rt else "")
        actor.actor_id = cr.actor_id_for_character(character) if cr else f"character:{getattr(character,'id','')}"
        reconcile_actor_position(actor, rt, reason="condition_command")
        st = build_action_state(actor, rt, active_encounter_id=(cr.find_actor_encounter(actor.actor_id) if cr else "") or "")
        return CommandResult(f"Condition: {st.health}/{st.maximum_health} health\nPosition: {st.derived_position.replace('_',' ')}\nCan move: {'yes' if st.can_move else 'no'}\nCan fight: {'yes' if st.can_attack else 'no'}" + (f"\nBlocked: {st.blocking_reason}" if st.blocking_reason else ""))

    def _cmd_stateinspect(self, character: Any, args: list[str], raw: str) -> CommandResult:
        if not self._admin_ok(character):
            return CommandResult("You do not have permission for that command.", ok=False)
        rt = getattr(self, "runtime", None); cr = getattr(rt, "combat_runtime", None) if rt else None
        cmd = (raw.split() or [""])[0].lower()
        target = args[0] if args else getattr(character, "id", "")
        ch = character if target in {getattr(character,"id", ""), getattr(character,"name", "")} else (rt.state_store.load_character(target) if rt and hasattr(rt, "state_store") else None)
        if not ch:
            return CommandResult(f"Character not found: {target}", ok=False)
        actor = actor_from_runtime_character(ch, getattr(rt, "active_world_id", "") if rt else "")
        actor.actor_id = cr.actor_id_for_character(ch) if cr else f"character:{getattr(ch,'id','')}"
        active = cr.find_actor_encounter(actor.actor_id) if cr else ""
        stored, derived, changed = reconcile_actor_position(actor, rt, reason=cmd, persist_dirty=(cmd == "staterepair" and "--apply" in args)) if (cmd == "staterepair" and "--apply" in args) else (actor.combat_profile.get("combat_state",""), derive_position_from_health(actor.resources.health, actor.combat_profile.get("combat_state","standing"), actor.lifecycle_state), False)
        st = build_action_state(actor, rt, active_encounter_id=active or "")
        proposed = []
        if st.repair_required:
            proposed.append(f"position: {st.stored_position} -> {st.derived_position} (safe: health/lifecycle threshold)")
        if active and cmd in {"staterepair", "combatstate"}:
            proposed.append(f"active encounter: {active} (inspect/cleanup if stale)")
        applied = cmd == "staterepair" and "--apply" in args and changed
        title = "Combat State" if cmd == "combatstate" else ("State Repair" if cmd == "staterepair" else "State Inspect")
        return CommandResult(title + f"\ncharacter: {getattr(ch,'id','')}\ncurrent_health: {actor.resources.health}/{actor.resources.maximum_health}\npersisted_health: {getattr(ch,'hp',0)}/{getattr(ch,'max_hp',0)}\nstored_position: {st.stored_position}\nderived_position: {st.derived_position}\ncombat_state: {st.combat_state}\nlifecycle_state: {st.lifecycle_state}\nactive_encounter: {active or 'none'}\nactive_target: {st.active_target_id or 'none'}\nattack_allowed: {'yes' if st.can_attack else 'no'}\nblocking_reason: {st.blocking_reason or 'none'}\nproposed_repair: {('; '.join(proposed)) if proposed else 'none'}\napplied: {'yes' if applied else 'no'}")

    def _cmd_perfstat(self, character: Any, args: list[str], raw: str) -> CommandResult:
        if str(getattr(character, "role", "player")).lower() not in {"admin", "owner", "builder"} and int(getattr(character, "immortal_level", 0) or 0) <= 0:
            return CommandResult("You do not have permission for that command.", ok=False)
        rt = getattr(self, "runtime", None)
        counters = getattr(rt, "performance_counters", {}) if rt else {}
        if args and args[0].lower() == "reset":
            from engine.performance_counters import reset_performance_counters
            ok, invalid = reset_performance_counters(rt)
            if not ok:
                return CommandResult(f"Performance counter reset aborted; invalid counter schema: {invalid}.", ok=False)
            return CommandResult("Performance counters reset.")
        if args and args[0].lower() == "validate":
            from engine.performance_counters import validate_all_performance_counter_schema
            errors = validate_all_performance_counter_schema(counters)
            return CommandResult("Performance counter schema valid." if not errors else "Performance counter schema invalid:\n" + "\n".join(errors), ok=not bool(errors))
        if args and args[0].lower() == "schema":
            from engine.performance_counters import schema_rows
            rows = schema_rows(counters)
            return CommandResult("Performance counter schema:\n" + "\n".join(f"{r['key']} {r['type']} {r['category']} {r['reset_policy']} current={r['current_type']} {'valid' if r['valid'] else 'invalid'}" for r in rows))
        keys = [k for k in sorted(counters) if k.startswith(("runtime_", "combat_", "practice_", "train_", "position_", "autosave_", "resident_", "regeneration_"))]
        return CommandResult("Performance counters:\n" + "\n".join(f"{k}: {counters.get(k,0)}" for k in keys))

    def _is_admin(self, character: Any) -> bool:
        return str(getattr(character, "role", "player")).lower() in {"admin", "owner", "builder"} or int(getattr(character, "immortal_level", 0) or 0) > 0

    def _cmd_runtime_admin(self, character: Any, args: list[str], raw: str) -> CommandResult:
        if not self._is_admin(character):
            return CommandResult("You do not have permission for that command.", ok=False)
        rt = getattr(self, "runtime", None)
        cmd = (raw.split() or [""])[0].lower()
        if not rt:
            return CommandResult("Runtime is unavailable.", ok=False)
        if cmd == "adminstatus":
            role = str(getattr(character, "role", "player")).lower(); imm = int(getattr(character, "immortal_level", 0) or 0)
            allowed = self._is_admin(character)
            perms = [p for p in ("RESTORE", "PERFSTAT", "PULSEFORCE") if allowed]
            return CommandResult(f"Admin status:\naccount_id: {getattr(character, 'account_id', '') or 'unknown'}\ncharacter_id: {getattr(character, 'id', '')}\ncanonical_role: {role}\nadministrator_level: {imm}\nimmortal_level: {imm}\npermissions_granted: {', '.join(perms) if perms else 'none'}\nRESTORE allowed: {'yes' if allowed else 'no'}\nPERFSTAT allowed: {'yes' if allowed else 'no'}\nPULSEFORCE allowed: {'yes' if allowed else 'no'}")
        if cmd in {"pulseinfo", "pointinfo"}:
            cfg = getattr(rt, "pulse_config", {})
            lines = ["Pulse configuration:"] + [f"{k}: {v}" for k, v in sorted(cfg.items())] + [f"current_pulse: {getattr(rt, '_runtime_pulse_counter', 0)}"]
            if cmd == "pointinfo":
                rr = getattr(rt, "runtime_resources", None); cr=getattr(rt,"combat_runtime",None); aid=f"character:{getattr(character,'id','')}"; actor=getattr(cr,"resident_actors",{}).get(aid) if cr else None
                pos = (actor.combat_profile.get("position") if actor else (getattr(character, "actor_data", {}) or {}).get("position", "standing"))
                mult = 4 if pos == "sleeping" else 2 if pos == "resting" else 0 if pos in {"fighting","in_combat","dead"} else 1
                online = getattr(character,'id','') in getattr(rt,'active_characters',{})
                eligible = bool(actor and online and mult and not (cr.find_actor_encounter(aid) if cr else ""))
                reason = "eligible" if eligible else ("not_registered" if not actor else "offline" if not online else "blocked_position")
                lines += [f"heartbeat pulse: {getattr(rt, '_runtime_pulse_counter', 0)}", f"point-update interval: {getattr(rr, 'point_update_interval_seconds', 6.0) if rr else 6.0}", f"last point-update: {getattr(rr, 'last_point_update_monotonic', 0.0) if rr else 0.0}", f"next point-update: {getattr(rr, '_next_regeneration_monotonic', 0.0) if rr else 0.0}", f"actor registered: {'yes' if actor else 'no'}", f"actor online: {'yes' if online else 'no'}", f"actor eligible: {'yes' if eligible else 'no'}", f"current position: {pos}", f"HP gain formula result: {mult}", f"Mana gain result: {mult}", f"Move gain result: {mult}", "hunger/thirst modifiers: none", "poison modifiers: none", f"blocking reason: {reason}"]
            return CommandResult("\n".join(lines))
        if cmd == "warmupstat":
            cw=getattr(rt,"combat_warmup",None); return CommandResult(cw.render_stat() if cw else "Combat warmup unavailable.", ok=bool(cw))
        if cmd == "warmuptrace":
            cw=getattr(rt,"combat_warmup",None); return CommandResult(cw.render_trace() if cw else "Combat warmup unavailable.", ok=bool(cw))
        if cmd == "combatcache":
            cw=getattr(rt,"combat_warmup",None)
            if not cw: return CommandResult("Combat cache unavailable.", ok=False)
            if args and args[0].lower()=="reset":
                if any(getattr(e,"status","")=="active" for e in getattr(getattr(rt,"combat_runtime",None),"resident_encounters",{}).values()): return CommandResult("Cannot reset combat cache during active combat.", ok=False)
                cw.cache.reset(); cw.warm(); return CommandResult("Combat cache reset and rebuilt.")
            if args and args[0].lower()=="validate": return CommandResult("Combat cache validation: ready" if cw.report.status in {"ready","warning"} else "Combat cache validation failed", ok=cw.report.status in {"ready","warning"})
            return CommandResult("Combat cache:\n"+"\n".join(f"{k}: {v}" for k,v in cw.cache.stats().items()))
        if cmd == "violenceprofile":
            cr = getattr(rt, "combat_runtime", None)
            if not cr or not getattr(cr, "violence_profiler", None):
                return CommandResult("Violence profiler is unavailable.", ok=False)
            if args and args[0].lower() == "reset":
                cr.violence_profiler.reset(); return CommandResult("Violence profile reset.")
            return CommandResult(cr.violence_profiler.render())
        if cmd == "commandtrace":
            tid = args[0] if args else ""
            traces = getattr(rt, "command_traces", {})
            if not tid:
                recent = list(traces.keys())[-10:]
                return CommandResult("Command traces:\n" + ("\n".join(recent) if recent else "none"))
            tr = traces.get(tid)
            if not tr:
                return CommandResult(f"Command trace not found: {tid}", ok=False)
            base = float(tr.get("request_received") or tr.get("request_started") or 0.0)
            keys = ["request_received","routing_started","target_resolved","encounter_created","opening_attack_started","opening_attack_completed","response_ready","response_sent"]
            lines = [f"Command trace {tid}:"]
            for k in keys:
                if k in tr:
                    lines.append(f"{k}: {(float(tr[k])-base)*1000.0:.3f} ms")
            lines.append(f"total_server_ms: {float(tr.get('total_server_ms', 0.0)):.3f}")
            waits = tr.get("awaits") or []
            lines.append("awaited_operations:")
            lines.extend([f"- {w.get('operation','unknown')}: {float(w.get('ms',0.0)):.3f} ms" for w in waits] or ["- none"])
            return CommandResult("\n".join(lines))
        if cmd == "pointtrace":
            mode = args[0].lower() if args else ""
            if mode in {"on", "off"}:
                rt.performance_counters["point_update_trace_enabled"] = 1 if mode == "on" else 0
                return CommandResult(f"Point trace {mode}.")
            keys = [k for k in sorted(getattr(rt, "performance_counters", {})) if k.startswith(("point_update_", "regeneration_", "recovery_"))]
            return CommandResult("Point trace:\n" + "\n".join(f"{k}: {rt.performance_counters.get(k,0)}" for k in keys))
        if cmd == "pulsetrace":
            keys = [k for k in sorted(getattr(rt, "performance_counters", {})) if k.startswith(("runtime_", "scheduler_", "combat_", "autosave_", "corpse_"))]
            return CommandResult("Pulse trace:\n" + "\n".join(f"{k}: {rt.performance_counters.get(k,0)}" for k in keys))
        if cmd == "pulseforce":
            subsystem = (args[0].lower() if args else "")
            if subsystem in {"combat", "violence"}:
                n = rt.combat_runtime.process_due_rounds(rt.combat_runtime.world_time()) if getattr(rt, "combat_runtime", None) else []
                return CommandResult(f"Forced combat violence pulse; messages={len(n)}.")
            if subsystem in {"point", "point_update", "regeneration"}:
                n = rt.runtime_resources.process_due_regeneration(10**12) if getattr(rt, "runtime_resources", None) else 0
                return CommandResult(f"Forced point update; actors={n}.")
            if subsystem == "autosave":
                return CommandResult(f"Forced autosave; characters_saved={rt.autosave_dirty_characters()}.")
            if subsystem in {"corpse", "corpse_decay"}:
                return CommandResult(f"Forced corpse decay; corpses_decayed={rt.process_corpse_decay(10**12)}.")
            return CommandResult("Usage: pulseforce combat|point_update|autosave|corpse_decay", ok=False)
        if cmd in {"occupancystat", "occupancyvalidate", "occupancy"}:
            if cmd == "occupancyvalidate":
                problems = rt.validate_room_occupancy() if hasattr(rt, "validate_room_occupancy") else ["runtime lacks validator"]
                return CommandResult("Occupancy validation: ok" if not problems else "Occupancy validation errors:\n" + "\n".join(problems), ok=not bool(problems))
            if cmd == "occupancystat" or not args:
                idx = getattr(rt, "resident_occupants_by_room", {})
                total = sum(len(v) for v in idx.values())
                return CommandResult(f"Resident occupancy rooms={len(idx)} occupants={total} actors={len(getattr(rt.combat_runtime, 'resident_actors', {}))}")
            if args[0] == "room":
                rid = rt.canonical_room_id(args[1] if len(args) > 1 else getattr(character, "room_id", ""))
                ids = list(getattr(rt, "resident_occupants_by_room", {}).get(rid, {}))
                return CommandResult(f"Occupancy room {rid}:\n" + ("\n".join(ids) if ids else "none"))
            if args[0] == "actor" and len(args) > 1:
                aid = args[1]
                actor = getattr(rt.combat_runtime, "resident_actors", {}).get(aid)
                return CommandResult(f"Occupancy actor {aid}: room={getattr(getattr(actor, 'identity', None), 'current_location', 'missing')}")
            return CommandResult("Usage: occupancyvalidate | occupancystat | occupancy room [room] | occupancy actor <actor>", ok=False)
        if cmd == "residentlist":
            ids = sorted(getattr(rt, "active_characters", {}).keys())
            return CommandResult("Residents:\n" + ("\n".join(ids) if ids else "none"))
        if cmd == "residentstat":
            cid = args[0] if args else getattr(character, "id", "")
            cid = cid.removeprefix("character:")
            ch = getattr(rt, "active_characters", {}).get(cid)
            aid = f"character:{cid}"
            dirty = sorted(getattr(rt, "_dirty_characters", {}).get(cid, set()))
            attached = getattr(rt, "character_session_ids", {}).get(cid, "")
            combat = rt.combat_runtime.find_actor_encounter(aid) if getattr(rt, "combat_runtime", None) else ""
            generation = ((getattr(ch, "actor_data", {}) or {}).get("hydration_generation") if ch else "absent")
            text = (
                f"Resident {cid}:\n"
                f"session_attached: {attached or 'no'}\n"
                f"online: {'yes' if ch else 'no'}\n"
                "reconnect_grace: no\n"
                f"resident_actor_generation: {generation}\n"
                f"dirty: {', '.join(dirty) if dirty else 'no'}\n"
                f"combat_active: {combat or 'no'}\n"
                f"regeneration_active: {'yes' if aid in getattr(getattr(rt, 'combat_runtime', None), 'resident_actors', {}) else 'no'}\n"
                f"last_autosave: {(getattr(rt, 'character_dirty_state', {}).get(cid, {}) or {}).get('last_saved_at', '')}\n"
                "planned_eviction_time: none"
            )
            return CommandResult(text)
        if cmd == "latencystat":
            if args and args[0].lower() == "reset":
                rt.performance_counters["command_blocked_on_save_ms"] = 0
                return CommandResult("Latency counters reset.")
            return CommandResult("Latency statistics:\ncommand_blocked_on_save_ms: " + str(rt.performance_counters.get("command_blocked_on_save_ms", 0)) + "\ncombat_message_delivery_latency_ms: " + str(rt.performance_counters.get("combat_message_delivery_latency_ms", 0)))
        if cmd == "commandtrace":
            return CommandResult("Command traces are returned per command response in development diagnostics.")
        return CommandResult("Unknown runtime admin command.", ok=False)

    def _resolve_character_for_admin(self, rt: Any, token: str) -> tuple[Any | None, bool]:
        key = (token or "").removeprefix("character:")
        if key.lower() in {"self", "me"}:
            return None, True
        for ch in getattr(rt, "active_characters", {}).values():
            if key.lower() in {str(getattr(ch, "id", "")).lower(), str(getattr(ch, "name", "")).lower()}:
                return ch, True
        ch = None
        try:
            ch = rt.state_store.load_character(key)
        except Exception:
            ch = None
        if not ch:
            try:
                import sqlite3
                with sqlite3.connect(rt.state_store.db_path) as con:
                    row = con.execute("SELECT id FROM characters WHERE lower(id)=? OR lower(name)=? LIMIT 1", (key.lower(), key.lower())).fetchone()
                if row:
                    ch = rt.state_store.load_character(str(row[0]))
            except Exception:
                pass
        return ch, False

    def _restore_actor_for_character(self, rt: Any, ch: Any, online: bool):
        rr = getattr(rt, "runtime_resources", None)
        if online:
            aid = rt.combat_runtime.actor_id_for_character(ch) if getattr(rt, "combat_runtime", None) else f"character:{getattr(ch,'id','')}"
            actor = getattr(getattr(rt, "combat_runtime", None), "resident_actors", {}).get(aid)
            if actor is None:
                rt.register_live_character(ch)
                actor = getattr(getattr(rt, "combat_runtime", None), "resident_actors", {}).get(aid)
        else:
            actor = actor_from_runtime_character(ch, getattr(rt, "active_world_id", "")); actor.actor_id = f"character:{getattr(ch,'id','')}"
        if actor is None:
            actor = actor_from_runtime_character(ch, getattr(rt, "active_world_id", "")); actor.actor_id = f"character:{getattr(ch,'id','')}"
        before = rr.build_resource_snapshot(actor) if rr else {}
        removed = []
        affects = getattr(ch, "affects", {}) if isinstance(getattr(ch, "affects", {}), dict) else {}
        for key, val in list(affects.items()):
            meta = val if isinstance(val, dict) else {"type": str(val)}
            tags = {str(x).lower() for x in meta.get("tags", [])} | {str(meta.get("type", "")).lower(), str(meta.get("category", "")).lower()}
            if tags & {"poison", "blind", "curse", "debuff", "harmful", "death", "stun"}:
                removed.append(key); affects.pop(key, None)
        ch.affects = affects
        if rr:
            rr.restore_all_resources(actor)
        else:
            actor.resources.health=actor.resources.maximum_health; actor.resources.mana=actor.resources.maximum_mana; actor.resources.stamina=actor.resources.maximum_stamina
        actor.lifecycle_state = "alive"; actor.combat_profile["position"] = "standing"; actor.combat_profile["combat_state"] = "idle"; actor.combat_profile.pop("target_id", None); actor.combat_profile.pop("active_target_id", None)
        if getattr(rt, 'combat_runtime', None):
            rt.combat_runtime.clear_actor_combat_state(actor.actor_id, "admin_restore", status="restored")
        if rr: rr._sync_runtime_character(actor, reason="admin_restore")
        else:
            ch.hp=actor.resources.health; ch.mana=actor.resources.mana; ch.stamina=actor.resources.stamina
        data = ch.actor_data if isinstance(getattr(ch, "actor_data", {}), dict) else {}
        data.update({"position":"standing", "posture":"standing", "lifecycle_state":"alive", "combat_state":"idle"}); ch.actor_data=data
        if online:
            if hasattr(rt, 'invalidate_character_projections'): rt.invalidate_character_projections(ch.id, 'admin_restore')
            rt.mark_character_dirty(ch.id, "admin_restore"); rt.save_character_if_dirty(ch, "admin_restore", force=True)
        else:
            ch.hp=actor.resources.health; ch.max_hp=actor.resources.maximum_health; ch.mana=actor.resources.mana; ch.max_mana=actor.resources.maximum_mana; ch.stamina=actor.resources.stamina; ch.max_stamina=actor.resources.maximum_stamina
            rt.state_store.save_character(ch, rt.active_world_id or '')
        after = rr.build_resource_snapshot(actor) if rr else {}
        return before, after, removed

    def _cmd_restore(self, character: Any, args: list[str], raw: str) -> CommandResult:
        if not self._is_admin(character):
            return CommandResult("You do not have permission for that command.", ok=False)
        rt = getattr(self, "runtime", None)
        if not rt:
            return CommandResult("Runtime is unavailable.", ok=False)
        counters = getattr(rt, "performance_counters", {})
        counters["restore_attempts"] = counters.get("restore_attempts", 0) + 1
        cmd = (raw.split() or ["restore"])[0].lower(); readonly = cmd == "restorestat"
        target_name = args[0] if args else "self"
        targets: list[tuple[Any, bool]] = []
        form = target_name.lower()
        if form in {"self", "me"}:
            counters["restore_self"] = counters.get("restore_self", 0) + 1; targets = [(character, True)]
        elif form == "all":
            targets = [(ch, True) for ch in getattr(rt, "active_characters", {}).values() if str(getattr(ch, "role", "player")).lower() == "player"]
            counters["restore_all_targets"] = counters.get("restore_all_targets", 0) + len(targets)
        else:
            ch, online = self._resolve_character_for_admin(rt, target_name)
            if ch: targets = [(ch, online)]; counters["restore_online_target" if online else "restore_offline_target"] = counters.get("restore_online_target" if online else "restore_offline_target", 0) + 1
        if not targets:
            counters["restore_failures"] = counters.get("restore_failures", 0) + 1
            return CommandResult(f"Character '{target_name}' not found.", ok=False)
        lines=[]; restored=0; skipped=0
        for ch, online in targets:
            aid=f"character:{getattr(ch,'id','')}"; actor=getattr(getattr(rt,'combat_runtime',None),'resident_actors',{}).get(aid) if online else None
            rr=getattr(rt,'runtime_resources',None)
            before = rr.build_resource_snapshot(actor) if (rr and actor) else {"health":getattr(ch,'hp',0),"maximum_health":getattr(ch,'max_hp',0),"mana":getattr(ch,'mana',0),"maximum_mana":getattr(ch,'max_mana',0),"stamina":getattr(ch,'stamina',0),"maximum_stamina":getattr(ch,'max_stamina',0),"hunger":0,"thirst":0,"position":(getattr(ch,'actor_data',{}) or {}).get('position','standing'),"lifecycle":(getattr(ch,'actor_data',{}) or {}).get('lifecycle_state','alive')}
            if readonly:
                active = rt.combat_runtime.find_actor_encounter(aid) if getattr(rt, 'combat_runtime', None) else ""
                lines.append(f"Restore stat {ch.name}:\nresources: {before['health']}/{before['maximum_health']} HP {before['mana']}/{before['maximum_mana']} MP {before['stamina']}/{before['maximum_stamina']} MV\nhunger: {before.get('hunger',0)}\nthirst: {before.get('thirst',0)}\nposition: {before.get('position')}\nlifecycle_state: {before.get('lifecycle')}\nactive_encounter: {active or 'none'}\nactive_harmful_effects: {len(getattr(ch,'affects',{}) or {})}")
                continue
            before, after, removed = self._restore_actor_for_character(rt, ch, online)
            counters["restore_effects_removed"] = counters.get("restore_effects_removed", 0) + len(removed)
            restored += 1; counters["restore_successes"] = counters.get("restore_successes", 0) + 1
            if online and ch is not character and getattr(rt, 'combat_runtime', None):
                rt.combat_runtime.enqueue_output(ch.id, "You have been fully healed by an immortal.", room_id=getattr(ch,'room_id',''), category="recovery")
            lines.append(f"Restored {ch.name}:\nHealth {before['health']}/{before['maximum_health']} -> {after['health']}/{after['maximum_health']}\nMana {before['mana']}/{before['maximum_mana']} -> {after['mana']}/{after['maximum_mana']}\nMove {before['stamina']}/{before['maximum_stamina']} -> {after['stamina']}/{after['maximum_stamina']}\nHunger {before.get('hunger',0)} -> {after.get('hunger',0)}\nThirst {before.get('thirst',0)} -> {after.get('thirst',0)}\nPosition {before.get('position')} -> {after.get('position')}\nLifecycle {before.get('lifecycle')} -> {after.get('lifecycle')}\nHarmful effects removed: {', '.join(removed) if removed else 'none'}\nCombat state cleared: yes\n({'online' if online else 'offline'})")
        if form == "all": lines.append(f"Restore all summary: restored={restored} skipped={skipped} failures=0")
        return CommandResult("\n".join(lines), state_updates={"prompt": True, "score": True, "resource_changed": True, "prompt_changed": True, "position_changed": True, "condition_changed": True})

    def _cmd_advancement_repair(self, character: Any, args: list[str], raw: str) -> CommandResult:
        if str(getattr(character, "role", "player")).lower() not in {"admin", "owner", "builder"} and int(getattr(character, "immortal_level", 0) or 0) <= 0:
            return CommandResult("You do not have permission for that command.", ok=False)
        rt = getattr(self, "runtime", None)
        ps = rt._progression_service() if rt and hasattr(rt, "_progression_service") else self._training_service(character).progression
        cmd = (raw.split() or [""])[0].lower()
        target = args[0] if args else str(getattr(character, "id", ""))
        apply = "--apply" in args
        state = ps.initialize_actor_progression(target)
        events = []
        with ps.store.connect() as con:
            con.row_factory = sqlite3.Row
            events = [dict(r) for r in con.execute("SELECT * FROM actor_advancement_currency_events WHERE actor_id=? AND currency_id='attribute_points' ORDER BY created_at", (target,))]
        demo_grants = [e for e in events if "demonstration" in (str(e.get("reason","")) + str(e.get("source_type","")) + str(e.get("metadata_json",""))).lower()]
        spent = sum(int(e.get("amount") or 0) for e in events if e.get("event_type") == "spend")
        demo_total = sum(int(e.get("amount") or 0) for e in demo_grants)
        removable = max(0, min(int(state.get("attribute_points") or 0), max(0, demo_total - spent)))
        if cmd == "advancementrepair" and apply and removable:
            ps.spend_currency(target, "attribute_points", removable, "remove proven unspent demonstration points")
            state = ps.get_actor_progression(target) or state
        report = {
            "character": target,
            "current_attribute_points": int(state.get("attribute_points") or 0),
            "grant_history": [e for e in events if e.get("event_type") == "grant"],
            "spending_history": [e for e in events if e.get("event_type") == "spend"],
            "demonstration_grant_amount": demo_total,
            "legitimate_grants": sum(int(e.get("amount") or 0) for e in events if e.get("event_type") == "grant" and e not in demo_grants),
            "unspent_demonstration_amount": removable,
            "proposed_correction": f"remove {removable} attribute_points",
            "ambiguity_status": "ambiguous_no_demonstration_history" if not demo_grants else "proven_by_history",
            "applied": bool(cmd == "advancementrepair" and apply),
        }
        return CommandResult(json.dumps(report, indent=2, sort_keys=True))

    def _cmd_position(self, character: Any, args: list[str], raw: str) -> CommandResult:
        import time
        t0 = time.monotonic()
        cmd = (raw.split() or [""])[0].lower()
        if cmd in {"lay", "lie"}:
            cmd = "sleep"
        rt = getattr(self, "runtime", None)
        cr = getattr(rt, "combat_runtime", None) if rt else None
        actor_id = cr.actor_id_for_character(character) if cr else f"character:{getattr(character,'id','')}"
        in_combat = bool(cr and cr.is_actor_in_active_combat(actor_id))
        data = getattr(character, "actor_data", {}) if isinstance(getattr(character, "actor_data", {}), dict) else {}
        pos = str(data.get("position") or data.get("posture") or "standing").lower()
        def finish(msg: str, ok: bool = True, newpos: str | None = None) -> CommandResult:
            if newpos:
                data["position"] = newpos; data["posture"] = newpos; character.actor_data = data
                if rt: rt.mark_character_dirty(getattr(character, "id", ""), "position")
            if rt: rt.performance_counters["position_command_duration_ms"] = int((time.monotonic()-t0)*1000)
            return CommandResult(msg, ok=ok, state_updates={"prompt": True})
        if cmd == "sit":
            if in_combat: return finish("Sit down while fighting? Are you MAD?", False)
            if pos == "sitting": return finish("You're sitting already.")
            return finish("You sit down.", True, "sitting")
        if cmd == "rest":
            if in_combat: return finish("Rest while fighting? Are you MAD?", False)
            if pos == "resting": return finish("You are already resting.")
            return finish("You sit down and rest your tired bones." if pos == "standing" else "You rest your tired bones.", True, "resting")
        if cmd == "sleep":
            if in_combat: return finish("Sleep while fighting? Are you MAD?", False)
            if pos == "sleeping": return finish("You are already sound asleep.")
            return finish("You go to sleep.", True, "sleeping")
        if cmd == "stand":
            if in_combat: return finish("Do you not consider fighting as standing?", False)
            if pos == "sleeping": return finish("You have to wake up first!", False)
            if pos == "resting": return finish("You stop resting, and stand up.", True, "standing")
            if pos == "sitting": return finish("You stand up.", True, "standing")
            return finish("You are already standing.")
        if cmd == "wake":
            if pos == "sleeping": return finish("You awaken, and stand up.", True, "standing")
            if pos in {"resting", "sitting"}: return finish("You stand up.", True, "standing")
            return finish("You are already awake...")
        return finish("You cannot do that right now.", False)

    def _cmd_survival_needs(self, character: Any, args: list[str], raw: str) -> CommandResult:
        svc=self._survival_service(character); cmd=raw.split()[0].lower(); actor_id=str(getattr(character,'id',getattr(character,'character_id','self')))
        if cmd in {'rest','sleep','wake','camp','campfire','campsite','fire','make','break','light','extinguish','add','inspect','stop','set','build'}:
            phrase=' '.join([cmd]+args).lower().strip()
            if phrase in {'rest status','sleep status'}: return CommandResult("Rest status is available. You can REST or SLEEP when the area is safe.")
            if phrase in {'stop resting','wake'} or cmd=='wake':
                res=svc.wake_actor(actor_id,'command'); return CommandResult("You wake and gather yourself." if res.get('ok', True) else "You are already awake.", ok=bool(res.get('ok', True)))
            if cmd=='rest':
                res=svc.start_rest(actor_id, args[0] if args and args[0] not in {'here','status'} else None); return CommandResult("You settle down to rest." if res.get('ok', True) else "You cannot rest here right now.", ok=bool(res.get('ok', True)))
            if cmd=='sleep':
                res=svc.start_sleep(actor_id, args[-1] if args and args[0]=='on' else None); return CommandResult("You settle in to sleep." if res.get('ok', True) else "You cannot sleep here right now.", ok=bool(res.get('ok', True)))
            if phrase in {'camp','campsite','camp status','campsite status'} or phrase in {'inspect campsite','look campsite','examine campsite'}:
                rid=getattr(character,'room_id','')
                with sqlite3.connect(svc.db_path) as c:
                    row=c.execute("SELECT campsite_instance_id FROM campsite_instances WHERE room_id=? AND status IN ('active','occupied','abandoned') ORDER BY created_at DESC LIMIT 1",(rid,)).fetchone()
                return CommandResult(self._format_campsite_status(svc.trace_campsite(row[0] if row else '')))
            if phrase in {'campfire','fire','campfire status','fire status','inspect campfire','look campfire','examine campfire'}:
                rid=getattr(character,'room_id','')
                with sqlite3.connect(svc.db_path) as c:
                    row=c.execute("SELECT campfire_instance_id FROM campfire_instances WHERE room_id=? AND status IN ('unlit','lit','extinguished','low_fuel') ORDER BY created_at DESC LIMIT 1",(rid,)).fetchone()
                return CommandResult(self._format_campfire_status(svc.trace_campfire(row[0] if row else '')))
            if phrase in {'set camp','make camp','establish camp'}:
                res=svc.create_campsite(actor_id,'basic_campsite'); msg='You abandon your previous campsite and establish a new one here.' if res.get('replaced_previous') else 'You establish a modest campsite here.'; denial=res.get('message') or ('A campsite is already established here.' if res.get('reason')=='existing_campsite' else 'You cannot establish a camp here.'); return CommandResult(msg if res.get('ok', True) else denial, ok=bool(res.get('ok', True)), state_updates={'render_room': bool(res.get('ok', True))})
            if phrase in {'break camp','campsite dismantle','dismantle campsite'}:
                res=svc.dismantle_campsite(actor_id,args[-1] if args and args[-1].startswith('campsite_') else ''); return CommandResult('You dismantle the campsite.' if res.get('ok', True) else 'There is no campsite here to dismantle.', ok=bool(res.get('ok', True)), state_updates={'render_room': bool(res.get('ok', True))})
            if phrase in {'build campfire','make campfire','create campfire'}:
                rid=getattr(character,'room_id','')
                with sqlite3.connect(svc.db_path) as c:
                    has_camp=c.execute("SELECT 1 FROM campsite_instances WHERE room_id=? AND created_by_actor_id=? AND status IN ('active','occupied','abandoned')",(rid,actor_id)).fetchone()
                if not has_camp: return CommandResult('You need an active campsite here before building a campfire.', ok=False)
                cf=svc.create_campfire(actor_id,'basic_campfire'); msg='Your previous campfire fades as you build a new one here.' if cf.get('replaced_previous') else 'You build a small campfire.'; return CommandResult(msg if cf.get('ok', True) else ('You need an active campsite here before building a campfire.' if cf.get('reason')=='requires_campsite' else 'You cannot build a campfire here right now.'), ok=bool(cf.get('ok', True)), state_updates={'render_room': bool(cf.get('ok', True))})
            if cmd=='light' and (not args or phrase in {'light campfire','light fire'}):
                cfid = ''
                try:
                    with sqlite3.connect(svc.db_path) as c:
                        row=c.execute("SELECT campfire_instance_id FROM campfire_instances WHERE room_id=(SELECT room_id FROM characters WHERE id=?) ORDER BY created_at DESC LIMIT 1",(actor_id,)).fetchone(); cfid = row[0] if row else ''
                except Exception: cfid=''
                res=svc.light_campfire(actor_id,cfid)
                reason=str(res.get('reason','')).lower()
                if not res.get('ok', True) and 'already' in reason: return CommandResult('The campfire is already lit.')
                return CommandResult('You light the campfire. Flames begin to crackle across the fuel.' if res.get('ok', True) else 'There is no unlit campfire here.', ok=bool(res.get('ok', True)), state_updates={'render_room': bool(res.get('ok', True))})
            if phrase=='extinguish campfire':
                cfid = args[-1] if args and args[-1].startswith('campfire_') else ''
                if not cfid:
                    try:
                        with sqlite3.connect(svc.db_path) as c:
                            row=c.execute("SELECT campfire_instance_id FROM campfire_instances WHERE room_id=(SELECT room_id FROM characters WHERE id=?) AND status='lit' ORDER BY created_at DESC LIMIT 1",(actor_id,)).fetchone(); cfid = row[0] if row else ''
                    except Exception: cfid=''
                res=svc.extinguish_campfire(actor_id,cfid); return CommandResult('You extinguish the campfire.' if res.get('ok', True) else 'There is no lit campfire here.', ok=bool(res.get('ok', True)), state_updates={'render_room': bool(res.get('ok', True))})
            if phrase=='add fuel':
                res=svc.add_campfire_fuel(actor_id,args[0] if args and args[0].startswith('campfire_') else '', args[1] if len(args)>1 else None); return CommandResult('You add fuel to the campfire.' if res.get('ok', True) else 'You need suitable fuel before you can feed the campfire.', ok=bool(res.get('ok', True)))
        if cmd in {'needs','hunger','thirst','fatigue','food'} or (cmd=='drink' and args[:1]==['status']):
            rows=svc.get_actor_needs(actor_id)
            if cmd in {'hunger','thirst','fatigue'}: rows=[r for r in rows if r['need_definition_id']==cmd or cmd in r['need_definition_id']]
            lines=['Survival needs:']+[f"{r['need_definition_id']}: {float(r['current_value']):.1f} ({r['status']})" for r in rows]
            return CommandResult('\n'.join(lines))
        if cmd in {'eat','drink','consume','sip','taste'}:
            if not args: return CommandResult(f"What do you want to {cmd}?", ok=False)
            if cmd=='taste': return CommandResult('You inspect it cautiously and notice nothing safe to taste.')
            target=' '.join(args); item_id=target
            if not target.startswith('item_'):
                for it in getattr(character,'inventory',[]) or []:
                    if target.lower() in str(it.get('name') or it.get('template_id') or it.get('id','')).lower(): item_id=it.get('instance_id') or it.get('id') or item_id; break
            res=svc.consume_item(actor_id,item_id,1)
            return CommandResult(('Consumed one serving.' if res.get('ok') else f"Cannot consume: {res.get('reason')}"), ok=bool(res.get('ok')))
        if cmd in {'needstick'}:
            if not args: return CommandResult('Usage: needstick <duration>', ok=False)
            return CommandResult(json.dumps(svc.process_actor_needs(actor_id, svc._world_minutes()+int(args[0])), indent=2, sort_keys=True))
        if cmd in {'needsinspect','needstrace'}: return CommandResult(json.dumps(svc.trace_actor_needs(args[0] if args else actor_id), indent=2, sort_keys=True))
        if cmd in {'needsset','needsmodify'}:
            if len(args)<3: return CommandResult(f'Usage: {cmd} <actor> <need> <value>', ok=False)
            fn=svc.set_actor_need if cmd=='needsset' else svc.modify_actor_need
            return CommandResult(json.dumps(fn(args[0],args[1],float(args[2]),'admin_command'), indent=2, sort_keys=True))
        if cmd=='consumptiontrace': return CommandResult(json.dumps(svc.trace_consumption(args[0] if args else ''), indent=2, sort_keys=True))
        if cmd=='resttrace': return CommandResult(json.dumps(svc.trace_rest(args[0] if args else ''), indent=2, sort_keys=True))
        if cmd=='campfiretrace': return CommandResult(json.dumps(svc.trace_campfire(args[0] if args else ''), indent=2, sort_keys=True))
        if cmd=='campsitetrace': return CommandResult(json.dumps(svc.trace_campsite(args[0] if args else ''), indent=2, sort_keys=True))
        if cmd=='survivalaudit': return CommandResult('Survival audit events are stored in SQLite survival_audit_events.')
        coll = 'actor_need_definitions' if cmd.startswith('need') else 'actor_needs_profiles' if cmd.startswith('needsprofile') else 'consumable_profiles'
        if cmd.endswith('list') or cmd in {'needlist'}: return CommandResult('\n'.join(f"{x.get('id')} - {x.get('name','')}" for x in svc.content.list(coll)) or f'No {coll}.')
        if cmd.endswith('stat') and args: return CommandResult(json.dumps(svc.content.get(coll,args[0]), indent=2, sort_keys=True))
        if cmd.endswith('validate') or cmd in {'needvalidate','consumablevalidate','needsprofilevalidate'}: return CommandResult(json.dumps(svc.content.validate(), indent=2, sort_keys=True))
        if cmd.endswith('preview') or cmd in {'needpreview','consumablepreview'}: return CommandResult(json.dumps({'collection':coll,'id':args[0] if args else None,'preview':'draft-safe'}, indent=2, sort_keys=True))
        return CommandResult('That survival command is not available here.', ok=False)


    def _training_service(self, character: Any):
        from engine.training import TrainingService
        store = self.state_store
        world_id = getattr(character, "world_id", "") or getattr(getattr(self, "runtime", None), "active_world_id", "") or "shattered_realms"
        if store is not None and not hasattr(store, "connect"):
            store.connect = lambda: __import__("sqlite3").connect(store.db_path)  # type: ignore[attr-defined]
        if store is not None and not hasattr(store, "world_id"):
            store.world_id = world_id  # type: ignore[attr-defined]
        if store is not None and not hasattr(store, "campaign_id"):
            store.campaign_id = world_id  # type: ignore[attr-defined]
        if store is not None and not hasattr(store, "initialize"):
            
            def _init_progression_tables():
                with store.connect() as con:
                    con.execute("""CREATE TABLE IF NOT EXISTS actor_progression_state(progression_state_id TEXT PRIMARY KEY,world_id TEXT,actor_type TEXT,actor_id TEXT,species_id TEXT,race_id TEXT,primary_class_id TEXT,primary_class_track_id TEXT,profession_ids_json TEXT,level INTEGER,experience INTEGER,experience_to_next INTEGER,total_experience INTEGER,practice_sessions INTEGER,training_sessions INTEGER,skill_points INTEGER,attribute_points INTEGER,talent_points_placeholder INTEGER,remort_count INTEGER,prestige_rank INTEGER,advancement_flags_json TEXT,last_level_at TEXT,created_at TEXT,updated_at TEXT,metadata_json TEXT,UNIQUE(actor_type,actor_id))""")
                    con.execute("""CREATE TABLE IF NOT EXISTS actor_ability_progression(actor_id TEXT,ability_id TEXT,rank INTEGER,maximum_rank INTEGER,proficiency INTEGER,learned_at_level INTEGER,source_class_id TEXT,source_race_id TEXT,source_profession_id TEXT,source_track_id TEXT,practice_cost INTEGER,training_cost INTEGER,skill_point_cost INTEGER,requirements_json TEXT,active INTEGER,learned_at TEXT,metadata_json TEXT,PRIMARY KEY(actor_id,ability_id))""")
            store.initialize = _init_progression_tables  # type: ignore[attr-defined]
        return TrainingService(store, economy=getattr(self, "economy_service", None), event_bus=self.event_bus, world_id=world_id, world_root=Path("worlds")/world_id)

    def _cmd_training_player(self, character: Any, args: list[str], raw: str) -> CommandResult:
        import time
        t0 = time.monotonic()
        rt = getattr(self, "runtime", None)
        ps = rt._progression_service() if rt and hasattr(rt, "_progression_service") else self._training_service(character).progression
        cmd = (raw.split() or ["train"])[0].lower()
        if cmd == "tr": cmd = "train"
        if cmd in {"prac", "pr"}: cmd = "practice"
        actor_id = str(getattr(character, "id", "self"))
        room_id = str(getattr(character, "room_id", ""))
        world_id = getattr(character, "world_id", "") or getattr(rt, "active_world_id", "") or "shattered_realms"
        root = Path("worlds") / world_id
        trainers = []
        try:
            data = json.loads((root/"trainer_definitions"/"trainer_definitions.json").read_text(encoding="utf-8"))
            raw_trainers = data.get("trainer_definitions", data if isinstance(data, list) else [])
            if isinstance(raw_trainers, dict):
                raw_trainers = list(raw_trainers.values())
            trainers = [t for t in raw_trainers if isinstance(t, dict) and room_id in (t.get("room_ids") or []) and t.get("enabled", True)]
        except Exception:
            trainers = []
        def at_trainer() -> bool:
            return bool(trainers)
        def trainer_name() -> str:
            return str((trainers[0] if trainers else {}).get("name") or "your trainer")
        state = ps.initialize_actor_progression(character)
        def done(text: str, ok: bool = True) -> CommandResult:
            if rt: rt.performance_counters["train_command_duration_ms" if cmd in {"train","buytrain"} else "practice_command_duration_ms"] = int((time.monotonic()-t0)*1000)
            return CommandResult(text, ok=ok)
        if cmd in {"buypractice", "buyprac", "buytrain"}:
            if not at_trainer(): return done("You need to be at your guild or trainer for that.", False)
            cur = "practice_sessions" if cmd != "buytrain" else "training_sessions"
            res = ps.purchase_session_with_glory(actor_id, cur, source_id=str((trainers[0] if trainers else {}).get("id") or "guild_trainer"))
            if not res.get("ok"):
                return done(f"You need {res.get('cost')} Glory for that purchase; you currently have {res.get('glory')} Glory.", False)
            if rt: rt.mark_character_dirty(actor_id, "progression")
            label = "practice" if cur.startswith("practice") else "training"
            return done(f"You spend {res['cost']} Glory and buy one {label} session. You now have {res['sessions']} {label} sessions and {res['glory']} Glory remaining.")
        if cmd == "train":
            query = " ".join(args).lower().strip()
            if not at_trainer() and query:
                return done("You need to be at your guild or trainer to train.", False)
            stats = {"str":"strength","dex":"dexterity","con":"constitution","int":"intelligence","wis":"wisdom","cha":"charisma"}
            aliases = {**stats, "strength":"strength","dexterity":"dexterity","constitution":"constitution","intelligence":"intelligence","wisdom":"wisdom","charisma":"charisma"}
            if not query:
                lines=[f"{trainer_name()} can help you train." if at_trainer() else "Training overview", f"You have {state.get('training_sessions',0)} training sessions available.", f"Attribute points: {state.get('attribute_points',0)}", "","Base stats"]
                for short, full in stats.items():
                    val = int(getattr(character, full, getattr(character, short, 10)) or 10)
                    lines.append(f"{short.capitalize()} {val}/20" + (" [MAX]" if val >= 20 else ""))
                lines += ["", "Use TRAIN STR/DEX/CON/INT/WIS/CHA (cost 1, cap 20)", "Use TRAIN HIT/MANA/MOVE (cost 10)"]
                return done("\n".join(lines))
            if query in aliases:
                if int(state.get("training_sessions",0) or 0) < 1: return done("You do not have enough training sessions.", False)
                attr = aliases[query]
                from engine.progression import TRAINING_ATTRIBUTE_CAP
                attrsvc = getattr(rt, "attribute_service", None) if rt else None
                if attrsvc is None:
                    from engine.character_stats import CharacterAttributeService
                    attrsvc = CharacterAttributeService(ps.store, world_id=world_id, world_root=root)
                before_stats = attrsvc.get_primary_stats(character, {"runtime": rt} if rt else {})
                old = int(before_stats.get(attr).base_value + before_stats.get(attr).permanent_component) if before_stats.get(attr) else int(getattr(character, attr, 10) or 10)
                if old >= TRAINING_ATTRIBUTE_CAP: return done(f"Your {attr} is already at the training cap.", False)
                ps.spend_currency(actor_id, "training_sessions", 1, f"train {attr}")
                with ps.store.connect() as con:
                    con.execute("UPDATE character_attributes SET permanent_modifier=permanent_modifier+1,updated_at=?,source=? WHERE character_id=? AND attribute_id=?", (__import__("engine.mud_state_store", fromlist=["utc_now"]).utc_now(), "training", actor_id, attr))
                if rt: rt.mark_character_dirty(actor_id, "training")
                after_stats = attrsvc.get_primary_stats(character, {"runtime": rt} if rt else {})
                changed = [f"Training successful.", f"  {attr.capitalize()}: {old} -> {old+1}", f"  Training sessions: {int(state.get('training_sessions',0))} -> {int(state.get('training_sessions',0))-1}"]
                return done("\n".join(changed))
            resmap = {"hit":"max_hp","hp":"max_hp","mana":"max_mana","move":"max_stamina"}
            if query in resmap:
                from engine.progression import TRAINING_RESOURCE_BONUS, TRAINING_RESOURCE_SESSION_COST
                if int(state.get("training_sessions",0) or 0) < 10: return done("You need ten training sessions for that.", False)
                field = resmap[query]; old = int(getattr(character, field, 0) or 0)
                ps.spend_currency(actor_id, "training_sessions", TRAINING_RESOURCE_SESSION_COST, f"train {query}")
                rkey = "health" if query in {"hit","hp"} else ("mana" if query == "mana" else "stamina")
                setattr(character, field, old + TRAINING_RESOURCE_BONUS)
                curfield = {"health": "hp", "mana": "mana", "stamina": "stamina"}[rkey]
                current = int(getattr(character, curfield, 0) or 0)
                with ps.store.connect() as con:
                    con.execute("CREATE TABLE IF NOT EXISTS actor_progression_modifiers(modifier_id TEXT PRIMARY KEY,actor_id TEXT,modifier_type TEXT,resource_id TEXT,amount INTEGER,source_type TEXT,source_id TEXT,active INTEGER DEFAULT 1,created_at TEXT,metadata_json TEXT)")
                    con.execute("INSERT INTO actor_progression_modifiers(modifier_id,actor_id,modifier_type,resource_id,amount,source_type,source_id,active,created_at,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?)", ("mod_"+__import__("uuid").uuid4().hex, actor_id, "maximum_resource", rkey, TRAINING_RESOURCE_BONUS, "training", f"train {query}", 1, __import__("engine.mud_state_store", fromlist=["utc_now"]).utc_now(), "{}"))
                    con.execute("INSERT INTO actor_resource_versions(actor_id,resource,value,maximum,version,updated_at) VALUES(?,?,?,?,1,?) ON CONFLICT(actor_id,resource) DO UPDATE SET maximum=actor_resource_versions.maximum+?,version=actor_resource_versions.version+1,updated_at=excluded.updated_at", ("character:"+actor_id, rkey, current, old + TRAINING_RESOURCE_BONUS, __import__("engine.mud_state_store", fromlist=["utc_now"]).utc_now(), TRAINING_RESOURCE_BONUS))
                if rt: rt.mark_character_dirty(actor_id, "training")
                label = "Move" if query == "move" else ("Hit points" if query in {"hit","hp"} else "Mana")
                return done(f"Training successful.\n  {label}: {old} -> {old+TRAINING_RESOURCE_BONUS}\n  Training sessions: {int(state.get('training_sessions',0))} -> {int(state.get('training_sessions',0))-TRAINING_RESOURCE_SESSION_COST}")
            return done("Train what? Try TRAIN STR, DEX, CON, INT, WIS, CHA, HIT, MANA, or MOVE.", False)
        # practice
        intelligence = int(getattr(character, "intelligence", 10) or 10)
        abilities = ps.list_known_practice_abilities(actor_id, intelligence=intelligence) if hasattr(ps, "list_known_practice_abilities") else []
        if not args:
            lines=[f"Practice sessions: {state.get('practice_sessions',0)}", "Use TRAIN for permanent attributes and resources.", "","You know:"]
            if not abilities: lines.append("  No practiced abilities yet.")
            for a in abilities:
                prof=int(a.get("current_proficiency") or 1); desc="awful" if prof<20 else "poor" if prof<40 else "fair" if prof<60 else "good" if prof<80 else "superb"
                lines.append(f"  {str(a.get('display_name') or a.get('ability_id')):24s} {prof:3d}% ({desc})")
            return done("\n".join(lines))
        if not at_trainer(): return done("You need to be at your guild or trainer to practice.", False)
        query=" ".join(args).lower().strip()
        resolved = ps.resolve_practice_ability(actor_id, query, intelligence=intelligence)
        if not resolved.get("ok"):
            if resolved.get("ambiguous"): return done("Which ability do you mean? " + ", ".join(resolved["ambiguous"]), False)
            return done("You do not know of that ability.", False)
        a = resolved["ability"]
        res = ps.practice_ability(actor_id, a["ability_id"], intelligence=intelligence, trainer_ok=True)
        if not res.get("ok"):
            if res.get("reason") == "at_cap": return done("You are already learned in that area.", False)
            if res.get("reason") == "insufficient_practice_sessions": return done("You do not have enough practice sessions.", False)
            return done("You cannot practice that right now.", False)
        if rt: rt.mark_character_dirty(actor_id, "practice")
        return done(f"You practice {a['display_name']}.\nYou are now {res['after']}% learned. Practice sessions remaining: {res['sessions']}")

    def _gathering_service(self, character: Any):
        from engine.gathering import GatheringService
        db = getattr(self.state_store, "db_path", Path(".smartmud_gathering.sqlite3")); world_id=getattr(character,"world_id","") or getattr(getattr(self,"runtime",None),"active_world_id","") or "shattered_realms"
        return GatheringService(db, world_id=world_id, world_root=Path("worlds")/world_id, event_bus=self.event_bus, reward_service=getattr(self,"reward_service",None))

    def _cmd_gathering_player(self, character: Any, args: list[str], raw: str) -> CommandResult:
        svc=self._gathering_service(character); cmd=(raw.split() or [""])[0].lower(); actor_id=str(getattr(character,'id','self')); room_id=str(getattr(character,'room_id',''))
        if cmd in {'resources','resource','survey'}:
            nodes=svc.list_room_nodes(room_id)
            return CommandResult("Resources here:\n" + ("\n".join(f"- {n.get('name') or n.get('node_definition_id')}" for n in nodes) if nodes else "No obvious resources are ready here."))
        if cmd in {'skin','butcher','harvest','extract'} and args and 'corpse' in ' '.join(args).lower():
            return CommandResult("Corpse processing requires a specific corpse. Use LOOK CORPSE, then SKIN <corpse> or BUTCHER <corpse>.", ok=False)
        if cmd in {'gather','forage','mine','chop','fish','dig','excavate','salvage','harvest'}:
            if not args and cmd=='gather': return CommandResult('Usage: gather <resource>. Try RESOURCES HERE first.', ok=False)
            mode={'forage':'harvesting','harvest':'harvesting','mine':'mining','chop':'lumberjacking','fish':'fishing','dig':'excavation','excavate':'excavation','salvage':'scavenging'}.get(cmd, None)
            res=svc.gather_mode(mode, actor_id, room_id, ' '.join(args) or None)
            if not res.get('ok'): return CommandResult('You cannot gather that here: '+str(res.get('reason','no matching resource')), ok=False)
            ys=', '.join(str(y.get('item_template_id') or y.get('resource_definition_id')) for y in res.get('yields',[])) or 'materials'
            return CommandResult('You gather '+ys+'.')
        return CommandResult('Usage: resources here | gather <resource> | forage/mine/harvest <target> | skin/butcher <corpse>.')

    def _property_service(self, character: Any):
        from engine.property import PropertyService
        db=getattr(self.state_store,'db_path',Path('.smartmud_property.sqlite3')); world_id=getattr(character,'world_id','') or getattr(getattr(self,'runtime',None),'active_world_id','') or 'shattered_realms'
        return PropertyService(db, world_id=world_id, world_root=Path('worlds')/world_id, event_bus=self.event_bus, economy_service=getattr(self,'economy_service',None))

    def _cmd_property_player(self, character: Any, args: list[str], raw: str) -> CommandResult:
        svc=self._property_service(character); cmd=(raw.split() or ['property'])[0].lower(); actor_id=str(getattr(character,'id','self'))
        if cmd in {'property','properties','lease','home','storage','access'} and (not args or args[0] in {'info','status'}):
            avail=svc.list_available_properties(actor_id)
            leases=[]
            import sqlite3
            with sqlite3.connect(svc.db_path) as con:
                con.row_factory=sqlite3.Row; leases=[dict(r) for r in con.execute("SELECT * FROM property_leases WHERE tenant_id=? AND status IN ('active','pending','grace')",(actor_id,))]
            lines=['Property:']
            lines.append('Active leases: '+(str(len(leases)) if leases else 'none'))
            lines.append('Available rentals: '+(str(len(avail)) if avail else 'none here'))
            for p in avail[:5]: lines.append(f"- {p.get('name')} ({p.get('property_type')})")
            return CommandResult('\n'.join(lines))
        if cmd=='rent' or (cmd=='property' and args[:1]==['rent']):
            avail=svc.list_available_properties(actor_id)
            if not avail: return CommandResult('No rentable property is available here.', ok=False)
            q=svc.quote_rent(actor_id, avail[0]['property_instance_id'])
            return CommandResult(f"Rental quote for {avail[0].get('name')}: {q.total}. Confirm through PROPERTY RENT <property> when ready.")
        return CommandResult('Usage: property | properties | rent | home | storage | access.')

    def _quest_service(self, character: Any):
        from engine.quests import QuestService
        store = self.state_store
        db_path = getattr(store, "db_path", None) or ":memory:"
        world_id = getattr(character, "world_id", "") or "shattered_realms"
        reward_service = getattr(self, "reward_service", None)
        return QuestService(db_path, world_id=world_id, event_bus=self.event_bus, reward_service=reward_service)

    def _cmd_phase8a_quest(self, character: Any, args: list[str], raw: str) -> CommandResult:
        from engine.quests import QuestValidator
        svc = self._quest_service(character)
        cmd = raw.split()[0].lower() if raw.split() else "quests"
        actor_id = getattr(character, "id", "") or getattr(character, "character_id", "") or "self"
        if cmd in {"quests", "questlog", "journal", "quest", "progress", "objectives"} and not args:
            if args and args[0].lower() == "available":
                qs = svc.list_available_quests(actor_id)
                return CommandResult("Available quests:\n" + "\n".join(f"{i+1}. {q.get('name')}" for i,q in enumerate(qs)))
            rows = svc.get_quest_journal(actor_id)
            if not rows: return CommandResult("Quest Journal:\nNo active quests.")
            return CommandResult("Quest Journal:\n" + "\n".join(f"{i+1}. {r['name']} - {r['status']} - {r['current_stage']}" for i,r in enumerate(rows)))
        if cmd == "quest" and args:
            if args[0].lower() in {"history", "completed"}:
                return CommandResult("Quest history is recorded in actor_quest_history.")
            qid = args[-1].replace(" ", "_")
            q = svc.get_quest_definition(qid)
            return CommandResult(f"Quest {qid}: {q.get('summary','') if q else 'not found'}", ok=bool(q))
        if cmd == "accept" and args:
            inst = svc.accept_quest(actor_id, args[0], {"source_type":"command"})
            return CommandResult(f"Accepted quest {inst['quest_id']}.")
        if cmd == "abandon" and args:
            qs = [q for q in svc.get_actor_quests(actor_id) if q['quest_id'] == args[0] or q['quest_instance_id'] == args[0]]
            if not qs: return CommandResult("Quest not found.", ok=False)
            svc.abandon_quest(actor_id, qs[0]['quest_instance_id']); return CommandResult(f"Abandoned {qs[0]['quest_id']}.")
        if cmd == "turnin" and args:
            qs = [q for q in svc.get_actor_quests(actor_id) if q['quest_id'] == args[0] or q['quest_instance_id'] == args[0]]
            if not qs: return CommandResult("Quest not found.", ok=False)
            svc.turn_in_quest(actor_id, qs[0]['quest_instance_id'], {"source_type":"command"}); return CommandResult(f"Turned in {qs[0]['quest_id']}.")
        if cmd == "decline": return CommandResult("Quest offer declined.")
        if cmd == "talk": return CommandResult("Talk to whom?", ok=False)
        if cmd == "reply": return CommandResult("Reply requires an active canonical conversation choice.")
        if cmd in {"questlist", "queststat", "questvalidate", "questaudit"}:
            if cmd == "questlist": return CommandResult("Quests:\n" + "\n".join(q['id'] for q in svc.content.list('quest_definitions')))
            if cmd == "queststat" and args: return CommandResult(json.dumps(svc.get_quest_definition(args[0]) or {}, indent=2, sort_keys=True))
            res = QuestValidator(svc.content).validate_quest(args[0]) if args else QuestValidator(svc.content).validate_all()
            return CommandResult(f"Quest validation: {'ok' if res.ok else 'failed'}\nErrors: {res['errors']}\nWarnings: {res['warnings']}", ok=res.ok)
        if cmd.startswith("worldstate"):
            if cmd == "worldstateset" and len(args) >= 4:
                val = " ".join(args[3:]); parsed = True if val.lower()=="true" else False if val.lower()=="false" else val
                svc.world_state.set_state(args[0], args[1], args[2], parsed, source_type="command", source_id=actor_id); return CommandResult("World state set.")
            if cmd == "worldstatehistory" and len(args) >= 3: return CommandResult(json.dumps(svc.world_state.get_state_history(args[0],args[1],args[2]), indent=2))
            if cmd == "worldstatestat" and len(args) >= 3: return CommandResult(json.dumps(svc.world_state.get_state(args[0],args[1],args[2]) or {}, indent=2))
            return CommandResult("Usage: worldstateset <scope> <scope_id> <key> <value>")
        return CommandResult("Quest command usage: QUESTS, JOURNAL, QUEST <name>, ACCEPT <quest>, TURNIN <quest>.")

    def _crafting_service(self, character: Any) -> CraftingService | None:
        store = self.state_store
        db_path = getattr(store, "db_path", None)
        if not db_path:
            return None
        world_id = getattr(character, "world_id", "") or "shattered_realms"
        return CraftingService(db_path, world_id=world_id, runtime=getattr(self, "runtime", None), event_bus=self.event_bus)

    def _recipe_match(self, svc: CraftingService, query: str) -> dict[str, Any] | None:
        q = str(query or "").lower().replace(" ", "_")
        recipes = svc.content.list("recipe_definitions")
        for r in recipes:
            vals = {str(r.get("id", "")).lower(), str(r.get("short_name", "")).lower(), str(r.get("name", "")).lower().replace(" ", "_")}
            if q in vals or any(q and q in v for v in vals):
                return r
        return None


    def _achievement_service(self, character: Any = None):
        from engine.achievements import AchievementService
        db_path = getattr(self.state_store, "db_path", None) or Path("/tmp/smartmud-achievements.sqlite3")
        world_id = getattr(character, "current_world", None) or getattr(self.state_store, "world_id", "shattered_realms") or "shattered_realms"
        return AchievementService(db_path, world_id=world_id, world_root=Path("worlds") / world_id, event_bus=self.event_bus)

    def _actor_id_for_achievements(self, character: Any = None) -> str:
        return str(getattr(character, "actor_id", None) or getattr(character, "id", None) or getattr(character, "name", None) or "self")

    def _cmd_achievements(self, character: Any, args: list[str], command: str = "achievements") -> CommandResult:
        svc = self._achievement_service(character); actor_id = self._actor_id_for_achievements(character)
        cmd = command
        if cmd == "profile" and args and args[0] in {"achievements", "titles"}: cmd = args[0]
        if cmd in {"achievements", "achievement"}:
            if args and args[0] == "completed":
                rows = svc.get_actor_achievements(actor_id, "completed")
                return CommandResult("Completed achievements:\n" + "\n".join(f"{i+1}. {r['achievement_id']}" for i,r in enumerate(rows)))
            if args and args[0] in {"available", "categories", "series"}:
                key = "achievement_definitions" if args[0] == "available" else "achievement_" + args[0]
                return CommandResult(json.dumps(svc.content.data.get(key, {}), indent=2, default=str))
            if args and args[0] not in {"progress"}:
                return CommandResult(json.dumps(svc.trace_achievement(actor_id, args[0]), indent=2, default=str))
            defs=svc.list_achievements(actor_id)
            return CommandResult("Achievements:\n" + "\n".join(f"{i+1}. {a.get('name')}" for i,a in enumerate(defs)))
        if cmd == "titles":
            return CommandResult("Titles:\n" + "\n".join(f"{i+1}. {t['title_id']}{' (selected)' if t.get('selected') else ''}" for i,t in enumerate(svc.list_titles(actor_id))))
        if cmd == "title":
            if args[:1] == ["clear"]: svc.clear_selected_title(actor_id); return CommandResult("Selected title cleared.")
            if len(args) >= 2 and args[0] == "select": svc.select_title(actor_id, args[1]); return CommandResult(f"Selected title: {args[1]}")
            return self._cmd_achievements(character, [], "titles")
        if cmd == "accolades":
            return CommandResult("Accolades:\n" + "\n".join(f"{i+1}. {a['accolade_id']}" for i,a in enumerate(svc.list_accolades(actor_id))))
        if cmd in {"collections", "collection"}:
            if args: return CommandResult(json.dumps(svc.get_collection_progress(actor_id,args[0]), indent=2, default=str))
            return CommandResult("Collections:\n" + "\n".join(f"{i+1}. {c.get('name')}" for i,c in enumerate(svc.content.list('collection_definitions'))))
        if cmd == "milestones": return CommandResult(json.dumps(svc.content.data.get('achievement_milestone_profiles', {}), indent=2, default=str))
        return CommandResult(json.dumps(svc.trace_achievement(actor_id, args[0] if args else 'first_blood'), indent=2, default=str))

    def _cmd_builder_achievement(self, character: Any, args: list[str], command: str = "achievementlist") -> CommandResult:
        svc = self._achievement_service(character); cmd=command
        mapping={"achievement":"achievement_definitions","criteriagroup":"achievement_criteria_groups","criteria":"achievement_criteria","title":"title_definitions","accolade":"accolade_definitions","collection":"collection_definitions"}
        base=next((v for k,v in mapping.items() if cmd.startswith(k)), "achievement_definitions")
        if cmd.endswith("list"): return CommandResult(json.dumps(svc.content.list(base), indent=2, default=str))
        if "stat" in cmd or "preview" in cmd or "trace" in cmd: return CommandResult(json.dumps(svc.content.get(base,args[0]) if args else svc.content.validate(), indent=2, default=str))
        if "validate" in cmd or cmd == "achievementaudit": return CommandResult(json.dumps(svc.content.validate(), indent=2, default=str))
        if cmd == "achievementcomplete" and len(args)>=2: return CommandResult(json.dumps(svc.complete_achievement(args[0],args[1]), indent=2, default=str))
        if cmd == "titlegrant" and len(args)>=2: return CommandResult(str(svc.grant_title(args[0],args[1],"admin","command")))
        if cmd == "titleselect" and len(args)>=2: svc.select_title(args[0],args[1]); return CommandResult("Title selected.")
        if cmd == "accoladegrant" and len(args)>=2: return CommandResult(str(svc.grant_accolade(args[0],args[1],"admin","command")))
        if cmd == "collectiongrant" and len(args)>=3: return CommandResult(str(svc.add_collection_entry(args[0],args[1],args[2],"admin","command")))
        return CommandResult("Phase 9B Builder achievement command foundation is available; edit JSON drafts through Builder workspace/import pipeline.")

    def _cmd_crafting_player(self, character: Any, args: list[str], raw: str) -> CommandResult:
        svc = self._crafting_service(character)
        if not svc:
            return CommandResult(narrative="Crafting is unavailable in this runtime.", ok=False)
        cmd = raw.split()[0].lower() if raw.split() else "recipes"
        actor_id = getattr(character, "id", "") or getattr(character, "character_id", "")
        if cmd in {"recipes", "learned"} or raw.lower().startswith("learned recipes"):
            if args and args[0].lower()=="cooking":
                recs=svc.list_cooking_recipes(actor_id)
                return CommandResult(narrative="Cooking recipes:\n" + "\n".join(f"{i+1}. {r.get('name')}" for i,r in enumerate(recs)))
            prof = args[0] if args else ""
            recs = [r for r in svc.get_actor_recipes(actor_id) if not prof or r.get("profession_id") == prof]
            lines = ["Known recipes:"] + [f"{i+1}. {r.get('name')} ({r.get('profession_id') or 'general'})" for i, r in enumerate(recs)]
            return CommandResult(narrative="\n".join(lines or ["No known recipes."]))
        if cmd == "cook":
            if not args or args[0].lower() in {"list","recipes"}:
                recs=svc.list_cooking_recipes(actor_id); return CommandResult(narrative="Cooking recipes:\n"+"\n".join(f"{i+1}. {r.get('name')}" for i,r in enumerate(recs)))
            query=" ".join(args); workstation=None
            if " at campfire" in query: query=query.replace(" at campfire",""); workstation="campfire"
            r=self._recipe_match(svc, query)
            if not r: return CommandResult(narrative="Usage: cook <recipe> [at campfire]", ok=False)
            try: job=svc.start_cooking(actor_id,r["id"],workstation_id=workstation)
            except Exception as exc: return CommandResult(narrative=f"Cannot cook: {exc}", ok=False)
            return CommandResult(narrative=f"Cooking job started: {r.get('name')} status={job['status']}.")
        if cmd == "ingredients":
            r=self._recipe_match(svc," ".join(args[1:] if args[:1]==["for"] else args)) if args else None
            if not r: return CommandResult(narrative="Usage: ingredients for <recipe>", ok=False)
            return CommandResult(narrative="Ingredients for "+r.get("name",r["id"])+":\n"+"\n".join(g.get("id","") for g in r.get("input_groups",[])))
        if cmd == "preserve":
            return CommandResult(narrative=json.dumps(svc.preserve_food(actor_id,args[0] if args else ""), indent=2))
        if cmd in {"prepare","meal"}: return CommandResult(narrative="Ingredient preparation is routed through cooking recipes and CraftingService jobs.")
        if cmd == "recipe":
            r = self._recipe_match(svc, " ".join(args)) if args else None
            if not r: return CommandResult(narrative="Usage: recipe <name>", ok=False)
            p = svc.preview_recipe(actor_id, r["id"], 1)
            d = p.details
            lines = [r.get("name", r["id"]), r.get("description", ""), f"Profession: {r.get('profession_id') or 'none'} rank {r.get('minimum_profession_rank', 0)}", f"Workstation: {d.get('workstation') or 'none'}", f"Duration: {d.get('duration', 0)}", f"Eligible: {p.eligible}"]
            if d.get("missing_inputs"): lines.append(f"Missing: {d['missing_inputs']}")
            return CommandResult(narrative="\n".join(lines))
        if cmd in {"craft", "refine"}:
            if args and args[0].lower()=="preview":
                query=" ".join(args[1:]); start=False
            else:
                query=" ".join(args); start=True
            qty=1
            toks=query.split()
            if toks and toks[-1].isdigit(): qty=int(toks[-1]); query=" ".join(toks[:-1])
            r=self._recipe_match(svc, query)
            if not r: return CommandResult(narrative="Usage: craft [preview] <recipe> [quantity]", ok=False)
            p=svc.preview_recipe(actor_id,r["id"],qty)
            if not start:
                return CommandResult(narrative=f"Craft preview: {r.get('name')} x{qty}\nEligible: {p.eligible}\nSelected: {p.details.get('selected_inputs')}\nMissing: {p.details.get('missing_inputs')}\nDuration: {p.details.get('duration')}\nQuality: {p.details.get('quality_range')}\nWarnings: {p.details.get('warnings')}")
            try: job=svc.start_crafting(actor_id,r["id"],qty)
            except Exception as exc: return CommandResult(narrative=f"Cannot craft: {exc}", ok=False)
            return CommandResult(narrative=f"Crafting job started: {job['crafting_job_id']} status={job['status']} completes at world time {job['completes_world_time']}.")
        if cmd == "salvage":
            r = next((x for x in svc.content.list("recipe_definitions") if x.get("recipe_type")=="salvage"), None)
            if not r: return CommandResult(narrative="No salvage recipe is available.", ok=False)
            p=svc.preview_recipe(actor_id,r["id"],1)
            return CommandResult(narrative=f"Salvage preview: {r.get('name')}\nEligible: {p.eligible}\nWarning: destructive; exact selected item instances: {p.details.get('selected_inputs')}\nMissing: {p.details.get('missing_inputs')}")
        if cmd == "crafting":
            if args and args[0].lower()=="cancel" and len(args)>1:
                job=svc.cancel_crafting(actor_id,args[1]); return CommandResult(narrative=f"Cancelled crafting job {job['crafting_job_id']}.")
            jobs=svc.list_actor_crafting_jobs(actor_id)
            return CommandResult(narrative="Crafting jobs:\n"+"\n".join([f"- {j['crafting_job_id']} {j['recipe_id']} {j['status']} completes={j['completes_world_time']}" for j in jobs] or ["- none"]))
        if cmd in {"professions", "profession"}:
            return CommandResult(narrative="Professions and ranks are managed by the canonical CraftingService profession state. Use score professions for summary.")
        return CommandResult(narrative="Usage: recipes | ingredients for <recipe> | cook <recipe> [at campfire] | craft preview <recipe>.")

    def _cmd_crafting_builder(self, character: Any, args: list[str], raw: str) -> CommandResult:
        svc = self._crafting_service(character)
        if not svc:
            return CommandResult(narrative="Crafting is unavailable in this runtime.", ok=False)
        cmd = raw.split()[0].lower() if raw.split() else ""
        if cmd.startswith("cooking") or cmd.startswith("ingredientprofile") or cmd.startswith("servingprofile") or cmd.startswith("nutritionprofile") or cmd.startswith("preservationprofile") or cmd in {"foodfreshnessset","foodservingset"}:
            cmap={"ingredientprofile":"cooking_ingredient_profiles","servingprofile":"cooking_serving_yield_profiles","nutritionprofile":"food_nutrition_profiles","preservationprofile":"food_preservation_profiles"}
            pref=next((k for k in cmap if cmd.startswith(k)), None)
            coll=cmap.get(pref,"recipe_definitions")
            if cmd.endswith("list"): return CommandResult(narrative="\n".join([f"- {x.get('id')}: {x.get('name','')}" for x in svc.content.list(coll)]))
            if "trace" in cmd and args: return CommandResult(narrative=json.dumps(svc.trace_cooking_job(args[0]), indent=2, default=str))
            if cmd=="cookingstart" and len(args)>=2: return CommandResult(narrative=json.dumps(svc.start_cooking(args[0],args[1],workstation_id=args[2] if len(args)>2 else None), indent=2, default=str))
            if cmd=="cookingcomplete" and args: return CommandResult(narrative=json.dumps(svc.complete_cooking(args[0]), indent=2, default=str))
            if cmd=="cookinginterrupt" and len(args)>=2: return CommandResult(narrative=json.dumps(svc.interrupt_cooking(args[0]," ".join(args[1:])), indent=2, default=str))
            if "validate" in cmd or cmd=="cookingaudit": v=svc.content.validate(); return CommandResult(narrative=json.dumps(v, indent=2))
            if "stat" in cmd and args: return CommandResult(narrative=json.dumps(svc.content.get(coll,args[0]) or {}, indent=2, default=str))
            return CommandResult(narrative="Cooking Builder/Admin command foundation is available.")
        if cmd.endswith("list") or cmd in {"recipelist", "workstationlist", "productionlist", "qualitylist"}:
            coll = {"recipelist":"recipe_definitions","workstationlist":"workstation_profiles","productionlist":"production_profiles","qualitylist":"item_quality_profiles"}.get(cmd,"recipe_definitions")
            return CommandResult(narrative="\n".join([f"- {x.get('id')}: {x.get('name', x.get('display_name',''))}" for x in svc.content.list(coll)] or [f"No {coll}."]))
        if cmd in {"recipevalidate","workstationvalidate","productionvalidate","qualityvalidate","craftingaudit","recipeaudit"}:
            v=svc.content.validate(); return CommandResult(narrative=f"Errors:\n"+"\n".join(v['errors'] or ["none"])+"\nWarnings:\n"+"\n".join(v['warnings'] or ["none"]))
        if cmd in {"craftpreview","recipepreview"} and len(args)>=2:
            actor=args[1] if cmd=="recipepreview" else args[0]; recipe=args[0] if cmd=="recipepreview" else args[1]; qty=int(args[2]) if len(args)>2 and args[2].isdigit() else 1
            p=svc.preview_recipe(actor,recipe,qty); return CommandResult(narrative=json.dumps({"eligible":p.eligible, **p.details}, indent=2, default=str))
        if cmd=="craftstart" and len(args)>=2:
            job=svc.start_crafting(args[0],args[1],int(args[2]) if len(args)>2 and args[2].isdigit() else 1); return CommandResult(narrative=json.dumps(job, indent=2, default=str))
        if cmd=="crafttick":
            wt=int(args[0]) if args and args[0].isdigit() else 0; done=svc.process_crafting_jobs(world_time=wt); return CommandResult(narrative=f"Processed {len(done)} crafting jobs.")
        if cmd=="recipegrant" and len(args)>=2: return CommandResult(narrative=f"Granted recipe knowledge {svc.grant_recipe(args[0],args[1])}.")
        if cmd=="reciperevoke" and len(args)>=2: svc.revoke_recipe(args[0],args[1]); return CommandResult(narrative="Recipe source revoked.")
        if cmd=="actorrecipes" and args: return CommandResult(narrative="\n".join(r['id'] for r in svc.get_actor_recipes(args[0])) or "No recipes.")
        if cmd in {"craftjob","crafttrace","productiontrace"} and args: return CommandResult(narrative=json.dumps(svc.trace_crafting_job(args[0]), indent=2, default=str))
        if cmd=="professionxp" and len(args)>=3: return CommandResult(narrative=json.dumps(svc.award_profession_experience(args[0],args[1],int(args[2])), indent=2, default=str))
        return CommandResult(narrative="Crafting Builder/Admin command foundation is available; edits are stored through Builder draft JSON in Phase 7C content collections.")

    def _living_entity(self, query: str) -> dict[str, Any] | None:
        rt=getattr(self,'runtime',None)
        if not rt: return None
        ents=rt._fetch_entities('world_id=?',(getattr(rt,'active_world_id','') or '',))
        q=str(query or '').lower()
        for e in ents:
            if q in {str(e.get('instance_id','')).lower(), str(e.get('template_id','')).lower()} or q in str(e.get('name','')).lower(): return e
        return None


    def _formula_engine(self) -> FormulaEngine:
        if not hasattr(self, "_phase5d_formula_engine"):
            self._phase5d_formula_engine = FormulaEngine()
        return self._phase5d_formula_engine



    def _combat_behavior_service(self, character: Any) -> CombatBehaviorService:
        svc = getattr(self, "combat_behavior_service", None)
        if not svc:
            svc = CombatBehaviorService(event_bus=self.event_bus, ability_service=getattr(self, "ability_service", None), world_id=getattr(character, "world_id", ""))
            self.combat_behavior_service = svc
        svc.register_actor(actor_from_runtime_character(character, getattr(character, "world_id", "")))
        return svc

    def _cmd_combat_behavior(self, character: Any, args: list[str], raw: str) -> CommandResult:
        cmd = raw.split()[0].lower() if raw.split() else ""
        svc = self._combat_behavior_service(character)
        role = self._effective_role(character) if hasattr(self, "_effective_role") else str(getattr(character, "role", "player")).lower()
        admin = role in {"builder", "admin", "owner"} or bool(getattr(character, "builder_mode", False))
        actor_id = args[0] if args else getattr(character, "id", "")
        if cmd == "behaviorlist":
            return CommandResult("Combat behavior profiles\n" + "\n".join(sorted(svc.registry.profiles)))
        if cmd in {"behaviorstat", "behaviorpreview"}:
            prof = svc.registry.get(args[0] if args else "civilian_safe")
            return CommandResult(json.dumps(prof.to_dict(), indent=2, sort_keys=True))
        if cmd == "behaviorvalidate":
            errs = svc.registry.validate()
            return CommandResult("Behavior validation OK." if not errs else "\n".join(errs), ok=not bool(errs))
        if cmd in {"actorbehavior", "behaviortrace"}:
            return CommandResult(json.dumps(svc.trace_actor_combat_behavior(actor_id), indent=2, sort_keys=True))
        if cmd in {"combatdecision", "combattrace"}:
            return CommandResult(json.dumps(svc.trace_combat_decision(actor_id), indent=2, sort_keys=True))
        if cmd == "combatcandidates":
            return CommandResult(json.dumps([c.to_dict() for c in svc.build_combat_action_candidates(actor_id)], indent=2, sort_keys=True))
        if cmd in {"threatlist", "threatstat"}:
            return CommandResult(json.dumps(svc.threat.get_actor_threat_table(actor_id), indent=2, sort_keys=True))
        if cmd == "threatadd":
            if not admin: return CommandResult("You do not have permission for that command.", ok=False)
            target = args[1] if len(args)>1 else ""; amount = float(args[2]) if len(args)>2 else 1
            return CommandResult(json.dumps(svc.threat.add_threat(actor_id, target, amount, "scripted"), indent=2, sort_keys=True))
        if cmd == "threatclear":
            if not admin: return CommandResult("You do not have permission for that command.", ok=False)
            svc.threat.clear_actor_threat(actor_id); return CommandResult("Threat cleared.")
        if cmd == "hostilitytrace":
            target = args[1] if len(args)>1 else getattr(character, "id", "")
            return CommandResult(json.dumps(svc.hostility.evaluate_hostility(actor_id, target), indent=2, sort_keys=True))
        if cmd == "combattick":
            count = int(args[0]) if args and args[0].isdigit() else 1
            results=[]
            for i in range(count): results.extend(svc.evaluate_world_combat_behavior(getattr(character,"world_id",""), i))
            return CommandResult(json.dumps(results, indent=2, sort_keys=True))
        if cmd in {"petmode", "order"}:
            mode = args[-1].lower() if args else "passive"
            allowed={"attack","assist","flee","stay","follow","protect","passive","defensive","aggressive"}
            if mode not in allowed: return CommandResult("Unsupported order. Allowed: " + ", ".join(sorted(allowed)), ok=False)
            return CommandResult(f"{cmd} accepted: {mode}.")
        return CommandResult(f"{cmd} intent recorded through combat behavior service.")

    def _cmd_phase5f(self, character: Any, args: list[str], raw: str) -> CommandResult:
        if self._effective_role(character) not in {"builder", "admin", "owner"}:
            return CommandResult("You do not have permission for that command.", ok=False)
        from engine.phase5f import BodyProfileRegistry, PopulationManager, LIFECYCLE_STATES
        rt=getattr(self,"runtime",None); world=getattr(rt,"active_world",None) if rt else None; cmd=raw.split()[0].lower()
        profiles=BodyProfileRegistry(getattr(world,"body_profiles",None) or None)
        if cmd=="bodylist": return CommandResult("Body Profiles\n"+"\n".join(sorted(profiles.profiles)))
        if cmd=="bodyshow":
            prof=profiles.get(args[0] if args else "humanoid"); return CommandResult(json.dumps(prof.to_dict(), indent=2, sort_keys=True))
        if cmd=="slotlist":
            prof=profiles.get(args[0] if args else "humanoid"); return CommandResult("Slots for "+prof.id+"\n"+"\n".join(f"{s.order}: {s.id} ({s.display_name})" for s in prof.slots))
        defs=getattr(world,"population_definitions",None) or getattr(world,"spawns",[]) or []
        pm=PopulationManager(rt.state_store.db_path, getattr(rt,"active_world_id","") or "", defs) if rt else None
        if cmd=="spawnlist": return CommandResult("Spawn Definitions\n"+"\n".join(str(d.get("id")) for d in defs))
        if cmd=="spawnshow":
            q=args[0] if args else ""; return CommandResult(json.dumps(next((d for d in defs if str(d.get("id"))==q), {}), indent=2, sort_keys=True))
        if cmd=="population":
            action=args[0].lower() if args else "diagnostics"
            if action=="validate": return CommandResult("Population validation\n"+("\n".join(pm.validate()) or "passed"))
            if action=="reload": return CommandResult("Population definitions reloaded for current world package.")
            return CommandResult(json.dumps({"definitions":len(defs),"instances":pm.instances() if pm else [],"diagnostics":"deterministic population manager active"}, indent=2, sort_keys=True))
        if cmd=="lifecycle": return CommandResult("Lifecycle states\n"+" -> ".join(LIFECYCLE_STATES))
        if cmd=="corpse": return CommandResult("Corpse diagnostics: corpse ownership is stored on corpse_instances; loot is intentionally not implemented.")
        if cmd=="respawn": return CommandResult("Respawn diagnostics: respawn_queue is persisted by world time.")
        return CommandResult("Phase 5F command unavailable.", ok=False)

    def _cmd_formula_diag(self, character: Any, args: list[str], raw: str) -> CommandResult:
        if self._effective_role(character) not in {"builder", "admin", "owner"}:
            return CommandResult("You do not have permission for that command.", ok=False)
        engine = self._formula_engine(); action = args[0].lower() if args else "list"
        if action == "list":
            ids = [m["id"] for m in engine.formulas.metadata()]
            return CommandResult("Formula Registry\n" + "\n".join(ids))
        if action == "show" and len(args) >= 2:
            f = engine.formulas.get(args[1]); return CommandResult(json.dumps(f.__dict__ if f else {"missing": args[1]}, indent=2, sort_keys=True), ok=bool(f))
        if action == "trace" and len(args) >= 2:
            actor = actor_from_runtime_character(character, self.builder.world_id(character)); res = actor.get_derived_value(args[1], engine)
            return CommandResult(json.dumps(res.__dict__, default=str, indent=2, sort_keys=True))
        if action in {"validate", "debug"}:
            v = engine.formulas.validate(); return CommandResult("Formula validation " + ("passed" if v.ok else "failed") + "\nErrors:\n" + ("\n".join(v.errors) or "- none") + "\nWarnings:\n" + ("\n".join(v.warnings) or "- none"), ok=v.ok)
        return CommandResult("Usage: formula <list|show|trace|validate|debug> [formula_or_stat]", ok=False)

    def _cmd_modifier_diag(self, character: Any, args: list[str], raw: str) -> CommandResult:
        if self._effective_role(character) not in {"builder", "admin", "owner"}:
            return CommandResult("You do not have permission for that command.", ok=False)
        engine = self._formula_engine(); action = args[0].lower() if args else "list"
        if action == "list":
            return CommandResult("Modifier Registry\n" + ("\n".join(sorted(engine.modifiers.modifiers)) or "- none"))
        if action in {"trace", "debug"}:
            stat = args[1] if len(args) > 1 else "attack_rating"
            mods = [m.__dict__ for m in engine.modifiers.stacked_for_stat(stat)]
            return CommandResult(json.dumps({"stat": stat, "modifiers": mods}, indent=2, sort_keys=True))
        return CommandResult("Usage: modifier <list|trace|debug> [stat]", ok=False)

    def _cmd_actor_diag(self, character: Any, args: list[str], raw: str) -> CommandResult:
        if self._effective_role(character) not in {"builder", "admin", "owner"}:
            return CommandResult("You do not have permission for that command.", ok=False)
        if not args or args[0].lower() not in {"formulas", "modifiers"}:
            return CommandResult("Usage: actor <formulas|modifiers>", ok=False)
        actor = actor_from_runtime_character(character, self.builder.world_id(character))
        if args[0].lower() == "formulas":
            return CommandResult("Actor formulas\n" + "\n".join(f"{k}: {v.formula_name}" for k, v in sorted(actor.derived_statistics_cache.items())))
        return self._cmd_modifier_diag(character, ["list"], raw)

    def _environment_service(self):
        rt = getattr(self, "runtime", None)
        svc = getattr(rt, "environment", None) if rt else getattr(self, "environment_service", None)
        if svc:
            return svc
        from engine.environment import EnvironmentService
        world_id = getattr(rt, "active_world_id", "shattered_realms") if rt else "shattered_realms"
        db_path = getattr(getattr(rt, "state_store", None), "db_path", getattr(self.state_store, "db_path", "mud_state.db"))
        return EnvironmentService(db_path, Path("worlds") / world_id, world_id, self.event_bus)

    def _cmd_environment(self, character: Any, args: list[str], raw: str) -> CommandResult:
        svc = self._environment_service(); cmd = raw.split()[0].lower()
        rt = getattr(self, "runtime", None); wid = getattr(rt, "active_world_id", svc.world_id) if rt else svc.world_id
        wt = rt.get_world_time(wid) if rt else {"day": 1, "hour": 12, "minute": 0}
        room = {}
        if rt and getattr(rt, "active_world", None) and getattr(character, "room_id", ""):
            try: room = rt.active_world.room(character.room_id)
            except Exception: room = {"id": getattr(character, "room_id", "")}
        if cmd == "environmenttick":
            minutes = int(args[0]) if args and str(args[0]).isdigit() else 60
            new_time = rt.advance_world_time(wid, minutes) if rt else minutes
            changes = svc.process_environment_time(wid, new_time)
            return CommandResult(f"Environment tick completed.\nMinutes: {minutes}\nWeather transitions: {len(changes)}")
        if cmd == "forecast":
            f = svc.get_forecast()
            return CommandResult(f"Forecast\nCurrent: {f['current_conditions']}\nLikely next: {f['likely_next_weather']}\nTransition window: {f['transition_window']}\nPrecipitation risk: {f['precipitation_risk']}\nUncertainty: {f['uncertainty_label']}")
        if cmd == "season":
            s = svc.resolve_season(wt)
            return CommandResult(f"Season: {s.get('name') or s.get('id')} (cycle day {s.get('cycle_day')})")
        if cmd == "dayperiod":
            d = svc.resolve_day_period(wt)
            return CommandResult(f"Day period: {d['period']}")
        if cmd in {"roomlight", "light"} and (not args or cmd == "roomlight"):
            e = svc.resolve_room_environment(room, world_time=wt)
            return CommandResult(f"Room light: {e['light']['light_class']} (effective {e['light']['effective_light']:.2f})")
        if cmd == "light":
            item = args[0] if args else "light"
            res = svc.activate_light_source("item", f"{getattr(character,'id','actor')}:{item}", "torch_light", "actor", getattr(character,"id",""), getattr(character,"room_id",""), svc._world_minutes(wt))
            return CommandResult(f"You light {item}. Light source {res['status']}.")
        if cmd == "extinguish":
            item = args[0] if args else "light"
            ok = svc.extinguish_light_source("item", f"{getattr(character,'id','actor')}:{item}")
            return CommandResult(f"You extinguish {item}." if ok else "That is not lit.", ok=ok)
        if cmd in {"environmenttrace", "environmentaudit"}:
            return CommandResult(json.dumps(svc.trace_room_environment(room), indent=2, sort_keys=True))
        if cmd == "weathertrace":
            return CommandResult(json.dumps(svc.trace_weather(args[0] if args else "world", args[1] if len(args)>1 else "default"), indent=2, sort_keys=True))
        if cmd == "visibilitytrace":
            target = args[-1] if args else "self"
            return CommandResult(json.dumps(svc.evaluate_visibility(getattr(character,"id","self"), "target", target, room), indent=2, sort_keys=True))
        if cmd == "exposuretrace":
            return CommandResult(json.dumps(svc.accumulate_exposure(getattr(character,"id","self"), room, svc._world_minutes(wt)), indent=2, sort_keys=True))
        e = svc.resolve_room_environment(room, world_time=wt); w=e["weather"]
        if cmd == "weather": return CommandResult(f"Weather: {w['current_weather_type']}\nTemperature: {e['temperature']:.1f} C")
        if cmd == "temperature": return CommandResult(f"Temperature: {e['temperature']:.1f} C")
        if cmd == "shelter": return CommandResult("Sheltered: yes" if e["sheltered"] else "Sheltered: no")
        if cmd == "visibility": return CommandResult(f"Visibility: {svc.evaluate_visibility(getattr(character,'id','self'), 'room', room.get('id',''), room)['result']}")
        return CommandResult(f"Environment\nWeather: {w['current_weather_type']}\nSeason: {svc.resolve_season(wt).get('id')}\nDay period: {e['day_period']['period']}\nLight: {e['light']['light_class']}\nSheltered: {e['sheltered']}")

    def _cmd_worldtime(self, character: Any, args: list[str], raw: str) -> CommandResult:
        rt=getattr(self,'runtime',None); wid=getattr(rt,'active_world_id','') if rt else self.builder.world_id(character)
        if not rt: return CommandResult('Runtime unavailable.', ok=False)
        if args and args[0]=='set' and len(args)>=3: t=rt.set_world_time(wid,int(args[1]),args[2])
        elif args and args[0]=='advance' and len(args)>=2: t=rt.advance_world_time(wid,int(args[1]))
        elif args and args[0]=='pause': t=rt.pause_world_time(wid)
        elif args and args[0]=='resume': t=rt.resume_world_time(wid)
        else: t=rt.get_world_time(wid)
        return CommandResult(f"World time status\nWorld: {wid}\nDay: {t['day']}\nTime: {int(t['hour']):02d}:{int(t['minute']):02d}\nPaused: {t['paused']}\nScale: {t['time_scale']}")

    def _cmd_simulation(self, character: Any, args: list[str], raw: str) -> CommandResult:
        rt=getattr(self,'runtime',None); wid=getattr(rt,'active_world_id','') if rt else self.builder.world_id(character)
        if not rt: return CommandResult('Runtime unavailable.', ok=False)
        if args and args[0]=='tick' and len(args)>=2:
            t=rt.simulate_world(wid,int(args[1])); return CommandResult(f"Simulation tick completed.\nWorld: {wid}\nMinutes: {int(args[1])}\nTime: day {t['day']} {t['hour']:02d}:{t['minute']:02d}")
        if args and args[0]=='pause': rt.pause_world_time(wid); return CommandResult('Simulation paused.')
        if args and args[0]=='resume': rt.resume_world_time(wid); return CommandResult('Simulation resumed.')
        return CommandResult(f"Simulation status\nWorld: {wid}\n{rt.get_world_time(wid)}")

    def _cmd_living_entity(self, character: Any, args: list[str], raw: str) -> CommandResult:
        rt=getattr(self,'runtime',None); cmd=raw.split()[0].lower(); ent=self._living_entity(' '.join(args) or (args[0] if args else ''))
        if not rt or not ent: return CommandResult('Entity not found.', ok=False)
        eid=ent['instance_id']
        if cmd in {'eprofile'}: data=rt.get_entity_profile(eid)
        elif cmd in {'econtext'}: data=rt.get_entity_context(eid)
        elif cmd in {'eschedule','etime'}: data=rt.evaluate_entity_schedule(eid)
        elif cmd in {'eneeds'}: data=rt.living_world.list_needs(eid)
        elif cmd in {'egoals','goals'}: data=rt.list_entity_goals(eid)
        elif cmd in {'erelationships'}: data=[]
        elif cmd in {'ememories'}: data=rt.get_recent_memories(eid)
        elif cmd in {'estate'}: data={'state':ent.get('current_state'), 'raw':ent.get('state')}
        elif cmd in {'eactivity'}: data={'activity':(ent.get('state') or {}).get('current_activity','idle')}
        else: data=ent
        return CommandResult(json.dumps(data, indent=2, sort_keys=True))

    def _cmd_living_list(self, character: Any, args: list[str], raw: str) -> CommandResult:
        rt=getattr(self,'runtime',None); cmd=raw.split()[0].lower()
        if not rt: return CommandResult('Runtime unavailable.', ok=False)
        if cmd=='schedulelist': vals=[s.get('id') for s in getattr(rt.active_world,'schedules',[]) or []]
        elif cmd=='needlist': vals=list(__import__('engine.living_world', fromlist=['NEED_TYPES']).NEED_TYPES)
        elif cmd=='goallist': vals=['follow_schedule','go_to_room','work','rest','sleep','guard','patrol','socialize','return_home','return_to_work','idle']
        elif cmd=='relationshiplist': vals=['stranger','acquaintance','friend','ally','rival','enemy','family','coworker','custom']
        else: vals=['observation','interaction','conversation','schedule','location','relationship','gift','world_event','custom']
        return CommandResult('\n'.join(vals))

    def handle_command(self, character: Any, command_text: str) -> CommandResult:
        """Route command to deterministic handler or AI."""
        command_text = str(command_text or "")
        if command_text.startswith("'"):
            spoken = command_text[1:].strip()
            if not spoken:
                return CommandResult(narrative="Usage: '<message> (same as say <message>)", ok=False)
            command_text = "say " + spoken
        cmd_tokens = command_text.strip().split()
        if not cmd_tokens:
            return CommandResult(narrative="")
        
        raw_cmd_name = cmd_tokens[0].lower()
        if len(cmd_tokens) >= 2 and raw_cmd_name == "combat" and cmd_tokens[1].lower() == "stats":
            cmd_tokens = ["combatstats"] + cmd_tokens[2:]
            raw_cmd_name = "combatstats"
        if raw_cmd_name in {".end", ".cancel"} and not (getattr(self, "builder_service", None) and self.builder_service.sessions.has(character)):
            return CommandResult(narrative="No active editor session.", ok=False)
        if raw_cmd_name == "confirm" and len(cmd_tokens) >= 2 and cmd_tokens[1].lower() == "normalize" and getattr(self, "builder_service", None):
            self.builder_service.workspace = self.builder
            res = self.builder_service.normalize_command(character, ["confirm"] + cmd_tokens[2:])
            return CommandResult(narrative=res.message, ok=res.ok)
        if raw_cmd_name == "confirm" and len(cmd_tokens) >= 2 and cmd_tokens[1].lower() == "rollback" and getattr(self, "builder_service", None):
            self.builder_service.workspace = self.builder
            res = self.builder_service.normalize_command(character, ["rollback"] + cmd_tokens[2:])
            return CommandResult(narrative=res.message, ok=res.ok)
        if getattr(self, "builder_service", None) and self.builder_service.sessions.has(character):
            res = self.builder_service.sessions.handle(character, command_text)
            return CommandResult(narrative=res.message, ok=res.ok)
        if raw_cmd_name == "q" and getattr(self, "builder_service", None):
            res = self.builder_service.normalize_command(character, ["q"])
            if res.ok:
                return CommandResult(narrative=res.message, ok=res.ok)
        if getattr(self, "builder_service", None) and hasattr(self.builder_service, "continue_picker"):
            pick = self.builder_service.continue_picker(character, command_text)
            if pick is not None:
                return CommandResult(narrative=pick.message, ok=pick.ok)
        if raw_cmd_name in self.command_handlers:
            cmd_name = raw_cmd_name
        else:
            cmd_name = 'target' if raw_cmd_name == 'target' else self.resolve_alias(raw_cmd_name)
        if not cmd_name:
            choices = self.registry.resolve(raw_cmd_name)[1].split(":",1)[1].strip()
            return CommandResult(narrative=f"Which command did you mean? {choices}", ok=False)
        args = cmd_tokens[1:]
        self._publish("command_received", character, command_text, raw_input=command_text, canonical_command=raw_cmd_name, arguments=args, current_room_id=getattr(character, "room_id", ""))
        
        print(f"[mud-command] Routing {raw_cmd_name} as {cmd_name} for {character.name}")

        # Exact help topics that are not usable player commands should guide to HELP.
        exact_topic = self._help_service(character).suggest(command_text, character)
        meta_for_topic = self.registry.commands.get(cmd_name)
        if exact_topic and normalize_help_query(command_text) in {normalize_help_query(exact_topic.title), *(normalize_help_query(x) for x in exact_topic.keywords), *(normalize_help_query(x) for x in exact_topic.aliases)} and cmd_name not in {"help", "title"} and (not meta_for_topic or meta_for_topic.builder_only or meta_for_topic.admin_only or cmd_name not in self.command_handlers):
            return CommandResult(f"{command_text.strip().upper()} is a help topic, not a command.\nType HELP {exact_topic.title.upper()} for more information.", ok=False)

        if cmd_name == "target" and str(getattr(character, "role", "player")).lower() not in {"builder", "admin", "owner"}:
            result = self._cmd_combat_foundation(character, args, command_text)
            self._publish("command_executed", character, command_text, raw_input=command_text, canonical_command=cmd_name, arguments=args, current_room_id=getattr(character, "room_id", ""), result_summary=result.narrative[:120])
            return result

        if cmd_name == "desc":
            result = self._cmd_builder_edit(character, args, command_text)
            self._publish("command_executed", character, command_text, raw_input=command_text, canonical_command=cmd_name, arguments=args, current_room_id=getattr(character, "room_id", ""), result_summary=result.narrative[:120])
            return result

        # Check if admin command
        meta = self.registry.commands.get(cmd_name)
        if meta and (meta.admin_only or meta.builder_only):
            effective_role = self._effective_role(character)
            if effective_role not in (["admin", "owner"] if meta.admin_only else ["builder", "admin", "owner"]):
                print(f"[mud-command] Access denied: {character.name} not admin")
                result = CommandResult(narrative="You do not have permission for that command.", ok=False)
                self._publish("command_executed", character, command_text, raw_input=command_text, canonical_command=cmd_name, arguments=args, current_room_id=getattr(character, "room_id", ""), result_summary=result.narrative[:120])
                return result
        
        # Route to deterministic handler if exists
        if cmd_name in self.command_handlers:
            print(f"[mud-command] Deterministic: {cmd_name}")
            try:
                raw_result = self.command_handlers[cmd_name](character, args, command_text)
                result = self._normalize_command_result(raw_result, cmd_name)
            except Exception as exc:
                context = _command_exception_context(character, command_text, cmd_name)
                if not context.get("world_id") and getattr(self, "runtime", None):
                    context["world_id"] = getattr(self.runtime, "active_world_id", "")
                context.update({
                    "exception_type": type(exc).__name__,
                    "exception_message": str(exc),
                    "traceback": traceback.format_exc(),
                })
                logger.error("Unexpected command exception", extra=context, exc_info=True)
                result = CommandResult("Something went wrong while handling that command. Please try again or use HELP for syntax.", ok=False)
            self._publish("command_executed", character, command_text, raw_input=command_text, canonical_command=cmd_name, arguments=args, current_room_id=getattr(character, "room_id", ""), result_summary=(result.narrative or "render_room")[:120])
            return result
        
        # Known deterministic command with no specific handler
        if cmd_name in DETERMINISTIC_COMMANDS or cmd_name in self.registry.commands:
            print(f"[mud-command] Known deterministic placeholder: {cmd_name}")
            result = CommandResult(narrative=self._placeholder_for(cmd_name))
            self._publish("command_placeholder_used", character, command_text, raw_input=command_text, canonical_command=cmd_name, arguments=args)
            self._publish("command_executed", character, command_text, raw_input=command_text, canonical_command=cmd_name, arguments=args, current_room_id=getattr(character, "room_id", ""), result_summary=result.narrative[:120])
            return result
        
        # Social/freeform - route to AI if available
        if self.ai_provider:
            print(f"[mud-command] AI-assisted: {command_text}")
            context = self._build_ai_context(character, command_text)
            try:
                ai_response = self.ai_provider.generate(
                    prompt=f"SQLite AI context: {context}\nCharacter {character.name} says: {command_text}",
                    system_prompt="You are a MUD game narrator. Use the provided SQLite context before responding in 1-2 sentences."
                )
                result = CommandResult(narrative=ai_response)
                self._publish("command_executed", character, command_text, raw_input=command_text, canonical_command=cmd_name, arguments=args, current_room_id=getattr(character, "room_id", ""), result_summary=result.narrative[:120])
                return result
            except Exception as e:
                print(f"[mud-command] AI error: {e}")
                result = CommandResult(narrative="The world responds but remains silent.")
                self._publish("command_executed", character, command_text, raw_input=command_text, canonical_command=cmd_name, arguments=args, current_room_id=getattr(character, "room_id", ""), result_summary=result.narrative[:120])
                return result
        
        # Fallback with help-topic and typo guidance
        print(f"[mud-command] Unknown command: {cmd_name}")
        self._publish("command_unknown", character, command_text, raw_input=command_text, canonical_command=cmd_name, arguments=args, current_room_id=getattr(character, "room_id", ""), result_summary="unknown")
        topic = self._help_service(character).suggest(command_text, character)
        if topic and normalize_help_query(command_text) in {normalize_help_query(topic.title), *(normalize_help_query(x) for x in topic.keywords), *(normalize_help_query(x) for x in topic.aliases)}:
            msg = f"{command_text.strip().upper()} is a help topic, not a command.\nType HELP {topic.title.upper()} for more information."
        else:
            import difflib
            names=[m.command for m in self.registry.available(getattr(character,'role','player'), include_planned=False) if not (m.admin_only or m.builder_only)]
            close=difflib.get_close_matches(raw_cmd_name, names, n=1, cutoff=0.78)
            if close:
                msg=f"Unknown command “{raw_cmd_name}.”\nDid you mean {close[0].upper()}?"
            elif topic:
                msg=f"Unknown command “{raw_cmd_name}.”\nDid you mean {topic.title.upper()}?\nType HELP {topic.title.upper()} for more information."
            else:
                msg="Unknown command. Type HELP or COMMANDS."
        result = CommandResult(narrative=semantic("error", msg), ok=False)
        self._publish("command_executed", character, command_text, raw_input=command_text, canonical_command=cmd_name, arguments=args, current_room_id=getattr(character, "room_id", ""), result_summary=result.narrative[:120])
        return result


    def _normalize_command_result(self, value: Any, command_name: str = "") -> CommandResult:
        """Normalize player command adapter output to a safe CommandResult."""
        if isinstance(value, CommandResult):
            value.narrative = str(value.narrative or "")
            return value
        if value is None:
            return CommandResult("Nothing happens.", ok=False)
        if isinstance(value, bool):
            return CommandResult("Done." if value else "That did not work.", ok=bool(value))
        if isinstance(value, tuple):
            text = " ".join(str(part) for part in value if part is not None)
            return CommandResult(text or "Done.")
        if is_dataclass(value):
            value = asdict(value)
        if isinstance(value, sqlite3.Row):
            value = dict(value)
        if isinstance(value, dict):
            ok = bool(value.get("ok", True))
            text = value.get("message") or value.get("narrative") or value.get("output")
            if not text:
                text = "Done." if ok else "That did not work."
            return CommandResult(str(text), ok=ok)
        if isinstance(value, list):
            return CommandResult("\n".join(str(v) for v in value) if value else "Nothing to show.")
        return CommandResult(str(value))

    def _publish(self, event_name: str, character: Any, command: str, **payload: Any) -> None:
        if not self.event_bus:
            return
        payload.setdefault("character_id", getattr(character, "id", ""))
        payload.setdefault("character_name", getattr(character, "name", ""))
        self.event_bus.publish(event_name, payload, source_system="command", character_id=getattr(character, "id", ""), command=command)

    def _build_ai_context(self, character: Any, command_text: str) -> dict[str, Any]:
        """Load the authoritative SQLite context required before any LLM call."""
        character_id = getattr(character, "id", "") or getattr(character, "character_id", "")
        room_id = getattr(character, "room_id", "") or getattr(character, "current_room_id", "")
        npc_id = ""
        tokens = command_text.strip().split()
        if len(tokens) > 1:
            npc_id = tokens[-1].lower()
        if self.state_store and hasattr(self.state_store, "build_ai_context"):
            return self.state_store.build_ai_context(character_id, npc_id, room_id)
        return {"character": {"id": character_id, "name": getattr(character, "name", ""), "role": getattr(character, "role", "")}, "command": command_text}


    def _role_rank(self, role: str) -> int:
        return {"player": 0, "helper": 1, "builder": 2, "admin": 3, "owner": 4}.get(str(role or "player").lower(), 0)

    def _effective_role(self, character: Any) -> str:
        crole = str(getattr(character, "role", "player") or "player").lower()
        arole = str(getattr(character, "account_role", "player") or "player").lower()
        return arole if self._role_rank(arole) > self._role_rank(crole) else crole

    def _cmd_whoami(self, character: Any, args: list[str], raw: str) -> CommandResult:
        lines = [
            f"Account: {getattr(character, 'account_id', '') or 'unlinked'}",
            f"Account Role: {getattr(character, 'account_role', 'player')}",
            f"Character: {getattr(character, 'name', '')} ({getattr(character, 'id', '')})",
            f"Character Role: {getattr(character, 'role', 'player')}",
            f"Effective Role: {self._effective_role(character)}",
        ]
        return CommandResult(narrative="\n".join(lines))

    def _cmd_grantrole(self, character: Any, args: list[str], raw: str) -> CommandResult:
        if self._effective_role(character) != "owner":
            return CommandResult(narrative="You do not have permission for that command.", ok=False)
        if len(args) != 2 or args[1].lower() not in {"player", "helper", "builder", "admin", "owner"}:
            return CommandResult(narrative="Usage: grantrole <character/account> <player|helper|builder|admin|owner>", ok=False)
        if not self.state_store or not hasattr(self.state_store, "grant_role"):
            return CommandResult(narrative="Role assignment is CLI-only for this runtime.", ok=False)
        target, role = args[0], args[1].lower()
        try:
            rec = self.state_store.grant_role(role=role, account=target, source="game", granted_by_account_id=getattr(character, "account_id", ""), granted_by_character_id=getattr(character, "id", ""))
        except ValueError:
            try:
                rec = self.state_store.grant_role(role=role, character=target, source="game", granted_by_account_id=getattr(character, "account_id", ""), granted_by_character_id=getattr(character, "id", ""))
            except Exception as exc:
                return CommandResult(narrative=str(exc), ok=False)
        return CommandResult(narrative=f"Granted {rec['role']} to account {rec.get('account_id') or 'n/a'} character {rec.get('character_name') or rec.get('character_id') or 'n/a'}.")

    def _is_score_admin(self, character: Any) -> bool:
        return str(getattr(character, "role", "player")).lower() in {"builder", "admin", "owner"} or bool(getattr(character, "builder_enabled", False)) or bool(getattr(character, "builder_mode", False))

    def _render_score_section(self, character: Any, section: str = "all") -> str:
        actor = actor_from_runtime_character(character, getattr(self, "world_id", ""))
        return ActorScoreRenderer().render(actor, section, admin=self._is_score_admin(character))


    def _perception_service(self) -> PerceptionService:
        db_path = getattr(self.state_store, "db_path", None) or Path("user_data") / "mud_state.db"
        world_id = getattr(getattr(self, "builder", None), "world_id", "shattered_realms")
        return PerceptionService(db_path, Path("worlds") / world_id, world_id, self.event_bus)

    def _cmd_perception(self, character: Any, args: list[str], raw: str) -> CommandResult:
        """Route Phase 11B sensory, stealth, search, tracking, and diagnostics commands."""
        svc = self._perception_service()
        cmd = (raw.split()[0].lower() if raw.split() else "perception")
        actor_id = getattr(character, "character_id", None) or getattr(character, "id", None) or getattr(character, "name", "actor")
        room_id = getattr(character, "current_room_id", None) or getattr(character, "current_location", None) or ""
        if cmd == "hide":
            res = svc.attempt_hide(actor_id, room_id=room_id)
            return CommandResult(res.get("message", "You try to hide."), ok=bool(res.get("ok", True)))
        if cmd == "unhide":
            svc.break_hide(actor_id, "unhide")
            return CommandResult("You step out of concealment.")
        if cmd in {"stealth", "hidetrace"}:
            state = svc.trace_hide(actor_id if cmd == "stealth" or not args else args[0])
            return CommandResult("Stealth Status\n" + json.dumps(state, indent=2, sort_keys=True, default=str))
        if cmd in {"search", "investigate"}:
            res = svc.search_room(actor_id, room_id=room_id, search_type=" ".join(args) or None)
            return CommandResult(res.get("message", "You search."))
        if cmd in {"track", "tracks"}:
            if cmd == "tracks" or not args or args[0] in {"footprints", "tracks"}:
                trails = svc.find_tracks(actor_id, room_id)
                if not trails: return CommandResult("You find no readable tracks here.")
                return CommandResult("Tracks\n" + "\n".join(f"- {t['trail_type']} leading {t.get('direction') or 'onward'} ({t.get('age_minutes',0)} minutes old)" for t in trails))
            res = svc.track_target(actor_id, " ".join(args), room_id=room_id)
            return CommandResult(res.get("message", "You begin tracking."))
        if cmd == "listen":
            return CommandResult("You listen carefully. Nearby sounds would be reported as directional clues.")
        if cmd == "smell":
            return CommandResult(svc.detect_scent(actor_id, room_id).get("message", "You smell nothing unusual."))
        if cmd == "conceal":
            item = args[0] if args else "item"
            svc.conceal_item(item, actor_id, room_id)
            return CommandResult("You conceal the item without moving its canonical ownership.")
        if cmd == "reveal":
            return CommandResult("You reveal what you were concealing, if present.")
        if cmd in {"secrets", "discovered", "perception", "awareness"}:
            return CommandResult(self._render_score_section(character, "perception" if cmd in {"perception","awareness"} else "investigation"))
        if cmd == "trailcreate":
            typ=args[0] if args else "footprint"; source=args[1] if len(args)>1 else actor_id; room=args[2] if len(args)>2 else room_id
            res=svc.create_trail(typ, source, room, direction="north")
            return CommandResult(f"Trail created: {res['trail_id']}")
        if cmd == "soundemit":
            profile=args[0] if args else "normal_speech"; room=args[1] if len(args)>1 else room_id; intensity=float(args[2]) if len(args)>2 else None
            res=svc.emit_sound(profile, room, intensity, source_actor_id=actor_id)
            return CommandResult(f"Sound emitted: {res['sound_event_id']}")
        if cmd.endswith("trace") or cmd == "perceptiontrace":
            return CommandResult(json.dumps({"command": cmd, "args": args, "trace": svc.trace_search(actor_id, " ".join(args))}, indent=2, sort_keys=True, default=str))
        if cmd.endswith("validate") or cmd in {"perceptionaudit"}:
            return CommandResult("Perception validation\n" + json.dumps(svc.validate_content(), indent=2, sort_keys=True))
        if cmd.endswith("list"):
            return CommandResult("Perception profile commands are implemented for Phase 11B collections.")
        if cmd.endswith("stat") or cmd.endswith("create") or cmd.endswith("clone") or cmd.endswith("set") or cmd.endswith("delete"):
            return CommandResult(f"{cmd} updates builder-authored perception collections through the canonical PerceptionService foundation.")
        return CommandResult("PerceptionService is active for stealth, search, tracking, scent, sound, and sensory diagnostics.")

    def _cmd_score(self, character: Any, args: list[str], raw: str) -> CommandResult:
        """Display normal player score as a focused structured document."""
        section = args[0].lower() if args else "score"
        mode_aliases = {"all": "score", "compact": "compact", "full": "full", "detailed": "detailed", "score": "score"}
        legacy_sections = {"resources", "attributes", "combat", "progression", "currency", "survival", "quests"}
        if section not in mode_aliases:
            if section in legacy_sections:
                section = "score"
            elif self._is_score_admin(character):
                return CommandResult(self._render_score_section(character, section))
            else:
                return CommandResult("That score mode is not available. Try SCORE, SCORE COMPACT, or SCORE FULL.", ok=False, display_intent="WARNING", semantic_role="warning")
        mode = mode_aliases.get(section, "score")
        if mode == "detailed" and not self._is_score_admin(character):
            return CommandResult("Detailed SCORE is available to Builder/admin characters only.", ok=False, display_intent="WARNING", semantic_role="warning")
        svc = getattr(self, "character_display_snapshots", None) or getattr(getattr(self, "runtime", None), "character_display_snapshots", None) or CharacterDisplaySnapshotService(getattr(self, "runtime", None))
        try:
            rt = getattr(self, "runtime", None)
            snap = rt.build_projection(character, "score") if rt and hasattr(rt, "build_projection") else svc.build_snapshot(character)
        except Exception:
            return CommandResult("Your character sheet is temporarily unavailable.", ok=False, display_intent="ERROR", semantic_role="error")
        theme = resolve_effective_display_theme(character, family="score")
        try:
            doc = build_score_document(character, snapshot=snap, theme=theme, mode=mode, detailed_allowed=self._is_score_admin(character))
        except PermissionError as exc:
            return CommandResult(str(exc), ok=False, display_intent="WARNING", semantic_role="warning")
        except ValueError as exc:
            text = str(exc)
            if text.startswith("score_projection_incomplete"):
                missing = text.split("field=", 1)[1] if "field=" in text else "unknown"
                rt = getattr(self, "runtime", None)
                entry = getattr(character, "entry_context", None)
                gen = getattr(getattr(rt, "projection_cache", None), "generation", lambda _cid: 0)(str(getattr(character, "id", ""))) if rt else 0
                logger.error("score_projection_incomplete", extra={"character_id": getattr(character, "id", ""), "world_id": getattr(rt, "active_world_id", "") if rt else "", "entry_id": getattr(entry, "entry_id", ""), "projection_generation": gen, "missing_field": missing})
                cache = getattr(rt, "projection_cache", None) if rt else None
                if cache and hasattr(cache, "mark_failed"):
                    cache.mark_failed(str(getattr(character, "id", "")), getattr(rt, "active_world_id", ""), "score", text)
                return CommandResult("Your character data could not be loaded completely. Please contact an administrator.", ok=False, display_intent="ERROR", semantic_role="error")
            return CommandResult(str(exc), ok=False, display_intent="WARNING", semantic_role="warning")
        return CommandResult(
            narrative=render_display_mud(doc, color_enabled=theme.color_enabled),
            display_document=doc,
            display_intent="SCORE",
            state_updates={"snapshot_version": doc.debug_metadata.get("snapshot_version"), "display_mode": mode},
        )

    def _cmd_progression_repair(self, character: Any, args: list[str], raw: str) -> CommandResult:
        if not self._is_score_admin(character):
            return CommandResult("You are not allowed to repair progression state.", ok=False, display_intent="WARNING", semantic_role="warning")
        rt = getattr(self, "runtime", None)
        if not rt or not hasattr(rt, "_progression_service"):
            return CommandResult("Progression service is unavailable.", ok=False, display_intent="ERROR", semantic_role="error")
        target = args[0] if args else getattr(character, "id", "")
        apply = "--apply" in args or raw.split()[0].lower() == "progressioninspect" and False
        if raw.split()[0].lower() == "progressionrepair" and "--dry-run" not in args and "--apply" not in args:
            apply = False
        try:
            target_char = rt.state_store.load_character(target) if hasattr(rt.state_store, "load_character") else None
            if target_char is None and target != getattr(character, "id", ""):
                return CommandResult(f"Character not found: {target}", ok=False, display_intent="ERROR", semantic_role="error")
            target_char = target_char or character
            result = rt._progression_service().repair_legacy_progression_identity(target_char, apply=apply)
            if apply and hasattr(rt, "invalidate_character_projections"):
                rt.invalidate_character_projections(result["character_id"], "progression_identity")
            lines=[
                f"Character ID: {result['character_id']}",
                f"Current progression row: {'present' if result['row_exists'] else 'missing'}",
                f"Proposed race ID: {result['proposed_race_id']}",
                f"Proposed class ID: {result['proposed_class_id']}",
                f"Proposed track ID: {result['proposed_track_id'] or '(none)'}",
                f"Definition validation: {result['definition_validation']}",
                f"Fields that would change: {', '.join(result['changed_fields']) or '(none)'}",
                f"Applied: {result['applied']}",
            ]
            return CommandResult("\n".join(lines), display_intent="ADMIN", semantic_role="admin")
        except Exception as exc:
            logger.exception("progression_repair_failed", extra={"target": target})
            return CommandResult(f"Progression repair failed: {exc}", ok=False, display_intent="ERROR", semantic_role="error")


    def _cmd_phase7a_reward(self, character: Any, args: list[str], raw: str) -> CommandResult:
        from engine.rewards import RewardContent, RewardService
        rt=getattr(self, 'runtime', None); store=getattr(rt, 'state_store', None)
        world_id=getattr(rt, 'active_world_id', None) or self.builder.world_id(character)
        content=RewardContent(Path('worlds')/world_id)
        cmd=(args[0] if args else raw.split()[0]).lower(); target=args[1] if len(args)>1 else ''
        if cmd.endswith('list') or cmd in {'rewards','claimlist'}:
            mapping={'rewardlist':'reward_definitions','loottablelist':'loot_tables','treasurelist':'treasure_groups','deathlootlist':'death_loot_profiles','corpsedecaylist':'corpse_decay_profiles','nodelist':'resource_node_profiles'}
            coll=mapping.get(cmd)
            if cmd in {'rewards','claimlist'}: return CommandResult('Pending reward claims: none.')
            return CommandResult('\n'.join(f"{i.get('id')} - {i.get('name','')}" for i in content.list(coll)) or f'No {coll}.')
        if cmd in {'loottablepreview','loottrace'} and target:
            svc=RewardService(store=store, runtime=rt, content=content, world_id=world_id)
            seed=args[2] if len(args)>2 else None; return CommandResult(json.dumps(svc.trace_loot_table(target, seed=seed), indent=2, sort_keys=True))
        if cmd in {'rewardvalidate','loottablevalidate','treasurevalidate','deathlootvalidate','corpsedecayvalidate','nodevalidate'}:
            return CommandResult(json.dumps(content.validate(set(getattr(rt,'item_templates',{}).keys()) if rt else set()), indent=2, sort_keys=True))
        return CommandResult('Phase 7A reward command foundation is available; mutating Builder edits are draft-only placeholders in this build.')


    def _economy_service(self, character: Any):
        from engine.economy import EconomyService
        rt=getattr(self, 'runtime', None); store=getattr(rt, 'state_store', None) or self.state_store
        db_path=getattr(store, 'db_path', None) or Path('.smartmud_economy.sqlite3')
        world_id=getattr(rt, 'active_world_id', None) or self.builder.world_id(character)
        return EconomyService(db_path, world_id=world_id, world_root=Path('worlds')/world_id, event_bus=self.event_bus, runtime=rt)


    def _resolve_shop_context(self, character: Any, svc: Any) -> tuple[dict[str, Any] | None, str]:
        rt = getattr(self, "runtime", None)
        room_id = str(getattr(character, "room_id", "") or getattr(character, "current_room_id", ""))
        npcs = getattr(rt, "resident_entities_by_actor_id", {}) if rt else {}
        for shop in svc.content.list("shop_definitions"):
            rooms = set(str(r) for r in (shop.get("room_ids") or []) if r)
            keeper_template = str(shop.get("keeper_template_id") or "")
            if room_id in rooms:
                return shop, "room"
            for ent in npcs.values():
                if str(ent.get("room_id") or ent.get("current_room_id") or "") == room_id and str(ent.get("template_id") or ent.get("entity_template_id") or ent.get("npc_id") or ent.get("id") or "") == keeper_template:
                    return shop, "keeper"
            if keeper_template:
                tmpl = (getattr(rt, "entity_templates", {}) if rt else {}).get(keeper_template) or {}
                if str(tmpl.get("default_room_id") or "") == room_id:
                    return shop, "keeper-default"
        return None, "none"

    def _shop_stock_rows(self, svc: Any, shop_id: str) -> list[dict[str, Any]]:
        return [r for r in svc.initialize_shop_stock(shop_id) if int(r.get("available") or 0) and int(r.get("quantity") or 0) - int(r.get("reserved_quantity") or 0) > 0]

    def _shop_item_name(self, template_id: str) -> str:
        rt = getattr(self, "runtime", None)
        tmpl = (getattr(rt, "item_templates", {}) if rt else {}).get(template_id) or {}
        return str(tmpl.get("name") or template_id.replace("_", " ").title())

    def _resolve_shop_stock(self, svc: Any, shop_id: str, query: str) -> dict[str, Any] | None:
        rows = self._shop_stock_rows(svc, shop_id)
        q = str(query or "").strip().lower()
        if q.isdigit():
            idx = int(q) - 1
            return rows[idx] if 0 <= idx < len(rows) else None
        for r in rows:
            name = self._shop_item_name(r.get("item_template_id", "")).lower()
            tid = str(r.get("item_template_id") or "").lower()
            if q in {tid, name} or all(part in name or part in tid for part in q.split()):
                return r
        return None

    def _cmd_shop_runtime(self, character: Any, args: list[str], raw: str) -> CommandResult | None:
        svc = self._economy_service(character)
        cmd = (raw.split() or [""])[0].lower()
        actor_id = str(getattr(character, "id", getattr(character, "character_id", "self")))
        shop, source = self._resolve_shop_context(character, svc)
        if not shop:
            return CommandResult("There is no shopkeeper here.", ok=False)
        shop_id = shop.get("id")
        keeper = (shop.get("name") or "The shopkeeper").replace("'s Shop", "")
        if cmd == "list":
            rows = self._shop_stock_rows(svc, shop_id)
            if not rows:
                return CommandResult(f'{keeper} says, "I have nothing for sale."')
            lines = ["#   Item                         Price   Qty"]
            for i, r in enumerate(rows, 1):
                meta = json.loads(r.get("metadata_json") or "{}")
                price = next(iter((meta.get("price_override") or {"gold": 10}).values()))
                qty = int(r.get("quantity") or 0) - int(r.get("reserved_quantity") or 0)
                lines.append(f"{i:<3} {self._shop_item_name(r.get('item_template_id',''))[:28]:<28} {price:>5}   {qty}")
            return CommandResult("\n".join(lines))
        if cmd == "buy":
            if not args:
                return CommandResult("Buy what?", ok=False)
            qty = 1; query = " ".join(args)
            if len(args) >= 2 and args[0].isdigit():
                qty = max(1, int(args[0])); query = " ".join(args[1:])
            row = self._resolve_shop_stock(svc, shop_id, query)
            if not row:
                return CommandResult(f'{keeper} says, "I do not have that for sale."', ok=False)
            try:
                q = svc.quote_purchase(actor_id, shop_id, row, qty)
                txn = svc.confirm_purchase(actor_id, q.quote_id)
                logger.debug("[shop] actor=%s keeper=%s action=buy result=%s", actor_id, keeper, txn.get("status") if isinstance(txn, dict) else "ok")
                return CommandResult(f"{keeper} gives you {qty} {self._shop_item_name(row.get('item_template_id',''))}.")
            except ValueError as e:
                return CommandResult(f'{keeper} says, "{str(e).replace("_", " ").capitalize()}."', ok=False)
        if cmd in {"value", "sell"}:
            if not args:
                return CommandResult(f"{cmd.title()} what?", ok=False)
            rt = getattr(self, "runtime", None)
            inv = rt.find_inventory_items(actor_id) if rt and hasattr(rt, "find_inventory_items") else []
            if args[0].lower() == "all" and cmd == "sell":
                sold = skipped = total = 0
                for item in list(inv):
                    try:
                        q = svc.quote_sale(actor_id, shop_id, item["instance_id"]); amt = next(iter(q.total.values()))
                        svc.confirm_sale(actor_id, q.quote_id); sold += 1; total += int(amt)
                    except Exception:
                        skipped += 1
                logger.debug("[shop] actor=%s keeper=%s action=sell-all sold=%s skipped=%s", actor_id, keeper, sold, skipped)
                return CommandResult(f"You sell {sold} items for {total} gold.\n{skipped} items could not be sold.")
            res = rt.resolve_item_keywords(" ".join(args), inv) if rt and hasattr(rt, "resolve_item_keywords") else {"status":"missing"}
            if res.get("status") != "ok":
                return CommandResult(f'{keeper} says, "You do not have that item."', ok=False)
            item = res["item"]
            q = svc.quote_sale(actor_id, shop_id, item["instance_id"]); amt = next(iter(q.total.values()))
            if cmd == "value":
                return CommandResult(f'{keeper} says, "I will give you {amt} gold for {item.get("name")}."')
            svc.confirm_sale(actor_id, q.quote_id)
            return CommandResult(f"You sell {item.get('name')} for {amt} gold.")
        return None

    def _cmd_phase7b_economy(self, character: Any, args: list[str], raw: str) -> CommandResult:
        from engine.economy import EconomyContent
        svc=self._economy_service(character); cmd=(raw.split()[0] if raw.split() else (args[0] if args else "")).lower(); actor_id=str(getattr(character,'id',getattr(character,'character_id','self')))
        if cmd in {'list','buy','sell','value'}:
            shop_result = self._cmd_shop_runtime(character, args, raw)
            if shop_result is not None:
                return shop_result
        coll_map={'currency':'currency_profiles','shop':'shop_definitions','stock':'shop_stock_profiles','pricing':'pricing_profiles','service':'service_definitions','repairprofile':'repair_profiles','bankprofile':'bank_profiles','restock':'shop_restock_profiles'}
        if cmd in {'currency','currencybalance','balance'}:
            bals=svc.get_currency_balances('actor', actor_id) or {'gold': svc.get_currency_balance('actor', actor_id, 'gold')}
            bank=svc.bank_balance(actor_id,'gold') if cmd=='balance' else None
            text='Carried currency: '+', '.join(f"{v} {k}" for k,v in sorted(bals.items()))
            if bank is not None: text += f"\nBanked currency: {bank} gold"
            return CommandResult(text)
        if cmd in {'currencygrant','currencyremove'}:
            if len(args)<4: return CommandResult('Usage: currencygrant <actor> <currency> <amount>', ok=False)
            (svc.credit_currency if cmd=='currencygrant' else svc.debit_currency)('actor', args[1], args[2], int(args[3]), reason='admin_command')
            return CommandResult('Currency mutation recorded through EconomyService ledger.')
        if cmd in {'ledger','currencytrace','ledgertrace'}:
            target=args[1] if len(args)>1 and args[1] != 'self' else actor_id
            return CommandResult(json.dumps(svc.trace_currency_balance('actor', target, None, int(args[2]) if len(args)>2 and args[2].isdigit() else 20), indent=2, sort_keys=True))
        if cmd.endswith('list'):
            prefix=cmd[:-4]; coll=coll_map.get(prefix)
            return CommandResult('\n'.join(f"{x.get('id')} - {x.get('name','')}" for x in svc.content.list(coll)) if coll else 'Economy collection unavailable.')
        if cmd.endswith('validate') or cmd=='economyaudit':
            return CommandResult(json.dumps(svc.content.validate(set(getattr(getattr(self,'runtime',None),'item_templates',{}).keys())), indent=2, sort_keys=True))
        if cmd in {'shop','shop info'} or (cmd=='shop' and args[1:2]==['info']):
            shops=svc.content.list('shop_definitions'); return CommandResult('\n'.join(f"{s.get('name')} — {s.get('description')}" for s in shops) or 'No shop is available here.')
        if cmd in {'list','shopstock','shopstocktrace'}:
            shop_id=args[1] if len(args)>1 else 'blacksmith_shop'; stock=svc.initialize_shop_stock(shop_id)
            return CommandResult('\n'.join(f"{i+1}. {r.get('item_template_id')} — {r.get('quantity')-r.get('reserved_quantity',0)} available" for i,r in enumerate(stock)) or 'No stock.')
        if cmd=='buy':
            if len(args)<2: return CommandResult('Buy what?', ok=False)
            q=svc.quote_purchase(actor_id,'blacksmith_shop',' '.join(args[1:])); return CommandResult(f"Quote {q.quote_id}: {q.total}. Use confirm_purchase in EconomyService to commit.")
        if cmd=='deposit':
            if len(args)<3: return CommandResult('Usage: deposit <amount> <currency>', ok=False)
            return CommandResult(f"Deposit transaction {svc.deposit(actor_id,int(args[1]),args[2])} completed.")
        if cmd=='withdraw':
            if len(args)<3: return CommandResult('Usage: withdraw <amount> <currency>', ok=False)
            return CommandResult(f"Withdrawal transaction {svc.withdraw(actor_id,int(args[1]),args[2])} completed.")
        if cmd=='exchange':
            if len(args)<5: return CommandResult('Usage: exchange <amount> <from_currency> to <to_currency>', ok=False)
            return CommandResult(json.dumps(svc.convert_currency(actor_id,int(args[1]),args[2],args[4]), sort_keys=True))
        if cmd in {'transactions','transactiontrace','transactionstat','quotetrace','pricingtrace','servicetrace','repairtrace','banktrace','conversiontrace','shopaudit'}:
            return CommandResult('Economy diagnostics are available through EconomyService trace APIs and SQLite ledger rows.')
        return CommandResult('Phase 7B EconomyService command foundation is available; Builder edits are draft-safe placeholders in this build.')

    def _cmd_inventory(self, character: Any, args: list[str], raw: str) -> CommandResult:
        """Display inventory."""
        rt = getattr(self, "runtime", None)
        if rt and hasattr(rt, "find_inventory_items"):
            inv = rt.find_inventory_display_items(getattr(character, "id", "")) if hasattr(rt, "find_inventory_display_items") else rt.find_inventory_items(getattr(character, "id", ""))
        else:
            inv = rt.build_projection(character, "inventory") if rt and hasattr(rt, "build_projection") else list(getattr(character, "inventory", []) or [])
        theme = resolve_effective_display_theme(character, family="inventory")
        doc = build_inventory_document(list(inv or []), theme=theme)
        return CommandResult(narrative=render_display_mud(doc, color_enabled=theme.color_enabled), display_document=doc, display_intent="INVENTORY")

    def _cmd_runtime_item(self, character: Any, args: list[str], raw: str) -> CommandResult:
        rt = getattr(self, "runtime", None)
        if rt and hasattr(rt, "_handle_item_command"):
            parsed = rt._parse_interaction_command(raw) if hasattr(rt, "_parse_interaction_command") else {"cmd": (raw.split() or [""])[0].lower(), "args": args}
            cmd = parsed.get("cmd") or (raw.split() or [""])[0].lower()
            res = rt._handle_item_command(character, raw, cmd, parsed.get("args", args))
            if res is not None:
                return res
        return CommandResult("You cannot do that right now.", ok=False)

    def _cmd_equipment(self, character: Any, args: list[str], raw: str) -> CommandResult:
        """Display equipped items through the single score renderer."""
        rt = getattr(self, "runtime", None)
        if rt and hasattr(rt, "find_equipped_items"):
            items = rt.find_equipped_items(getattr(character, "id", ""))
            slots = list(getattr(rt, "EQUIPMENT_SLOTS", ["head", "chest", "main_hand", "off_hand", "legs", "feet"]))
        else:
            items = list((getattr(character, "equipment", {}) or {}).values()) if isinstance(getattr(character, "equipment", None), dict) else list(getattr(character, "equipment", []) or [])
            slots = ["head", "chest", "main_hand", "off_hand", "legs", "feet"]
        theme = resolve_effective_display_theme(character, family="equipment")
        doc=build_equipment_document(items, slots, theme=theme)
        return CommandResult(narrative=render_display_mud(doc, color_enabled=theme.color_enabled), display_document=doc, display_intent="EQUIPMENT")


    def _world_root(self, character: Any) -> Path:
        rt=getattr(self,"runtime",None); wid=getattr(rt,"active_world_id","") if rt else self.builder.world_id(character)
        wid=wid or getattr(character,"world_id","") or "shattered_realms"
        root=getattr(rt,"root",Path(".")) if rt else Path(".")
        return Path(root)/"worlds"/wid if not (Path(root)/wid).exists() else Path(root)/wid

    def _help_service(self, character: Any) -> HelpService:
        root=self._world_root(character); svc=getattr(self,"help_service",None)
        if not svc or getattr(svc,"world_root",None)!=root:
            svc=HelpService(root, self._ability_service(character)); self.help_service=svc
        else:
            svc.ability_service=self._ability_service(character)
        return svc

    def _render_help_entry(self, entry: HelpEntry, character: Any, *, title_prefix: str="") -> str:
        lines=[(title_prefix + entry.title).upper()]
        if entry.summary: lines += ["", entry.summary]
        if entry.body: lines += ["", entry.body]
        if entry.syntax: lines += ["", "Syntax:", *[f"  {x}" for x in entry.syntax]]
        if entry.examples: lines += ["", "Examples:", *[f"  {x}" for x in entry.examples]]
        if entry.related_topics: lines += ["", "Related topics: " + ", ".join(entry.related_topics)]
        if entry.category: lines += ["", f"Category: {entry.category}"]
        return "\n".join(lines)

    def _cmd_title(self, character: Any, args: list[str], raw: str) -> CommandResult:
        if not args:
            current=getattr(character,"title","") or "no custom title"
            return CommandResult(f"Current title: {current}\nUsage: title <text>\nType HELP TITLE for more information.")
        text=" ".join(args).strip()
        if len(text)>60: return CommandResult("Titles must be 60 characters or fewer.", ok=False)
        if not re.fullmatch(r"[A-Za-z0-9 ,.'-]+", text): return CommandResult("Titles may contain letters, numbers, spaces, commas, periods, apostrophes, and hyphens.", ok=False)
        setattr(character,"title",text)
        return CommandResult(f"Your title is now: {text}")

    def _stat_services(self, character: Any):
        rt=getattr(self,"runtime",None); world_id=getattr(rt,'active_world_id',None) or self.builder.world_id(character)
        store=getattr(rt,'state_store',None) or self.state_store
        attr=CharacterAttributeService(store, world_id=world_id, event_bus=self.event_bus)
        attr.runtime=rt
        return attr, CombatStatService(attr)

    def _cmd_attributes(self, character: Any, args: list[str], raw: str) -> CommandResult:
        attr,_=self._stat_services(character); attrs=attr.get_all_attributes(character, {"runtime": getattr(self,"runtime",None)})
        if args:
            key=args[0].lower(); found=attrs.get(key) or next((v for v in attrs.values() if v.name.lower()==key),None)
            if not found: return CommandResult("That attribute is not available.", ok=False)
            lines=[found.name, f"Base: {found.base_value}", f"Permanent: {found.permanent_modifier:+}", f"Equipment: {found.equipment_modifier:+g}", f"Affects: {found.affect_modifier:+g}", f"Temporary: {found.temporary_modifier:+g}", f"Situational: {found.situational_modifier:+g}", f"Final: {found.final_value}"]
            return CommandResult("\n".join(lines))
        lines=["ATTRIBUTES"]
        for a in attrs.values(): lines.append(f"{a.name + ':':<14} {a.final_value:>3}")
        return CommandResult("\n".join(lines))

    def _cmd_combatstats(self, character: Any, args: list[str], raw: str) -> CommandResult:
        _,combat=self._stat_services(character); s=combat.get_combat_snapshot(character, {"runtime": getattr(self,"runtime",None)})
        mode=(args[0].lower() if args else "all")
        valid={"all","offense","defense","saves","resistances","damage","speed","breakdown"}
        if mode not in valid:
            mode="all"
        if mode=="breakdown":
            if len(args)<2: return CommandResult("Usage: combatstats breakdown <stat-id>", ok=False)
            stat=args[1].lower()
            return CommandResult("COMBAT STAT BREAKDOWN\n"+json.dumps(combat.get_breakdown(character, stat, {"runtime": getattr(self,"runtime",None)}), indent=2, default=str))
        sections=[]
        def add(title, mapping, formatter=None):
            lines=[title]
            for k,v in (mapping or {}).items():
                val=formatter(k,v) if formatter else v
                lines.append(f"{k.replace('_',' ').title()}: {val}")
            sections.append(lines)
        if mode in {"all","offense"}: add("OFFENSE", s.offense)
        if mode in {"all","defense"}: add("DEFENSE", s.defense)
        if mode in {"all","saves"}: add("SAVES", s.saves)
        if mode in {"all","resistances"}: add("RESISTANCES", s.resistances, lambda k,v: f"{v}%")
        if mode in {"all","damage"}:
            lines=["DAMAGE", f"Unarmed: {s.unarmed_profile.minimum_damage}-{s.unarmed_profile.maximum_damage} {s.unarmed_profile.damage_type}"]
            if s.weapon_profile: lines.append(f"Weapon: {s.weapon_profile.minimum_damage}-{s.weapon_profile.maximum_damage} {s.weapon_profile.damage_type}")
            sections.append(lines)
        if mode in {"all","speed"}: add("SPEED", s.speed)
        if mode=="all": add("CARRYING", s.carrying)
        lines=["COMBAT STATS"]
        for section in sections:
            lines.append(""); lines.extend(section)
        return CommandResult("\n".join(lines))



    def _cmd_combatbreakdown(self, character: Any, args: list[str], raw: str) -> CommandResult:
        if self._effective_role(character) not in {"builder","admin","owner"}: return CommandResult("Combat breakdown diagnostics require Builder access.", ok=False)
        rt=getattr(self, "runtime", None); cr=getattr(rt, "combat_runtime", None) if rt else None
        if not cr: return CommandResult("Combat runtime diagnostics are not available.", ok=False)
        sub=(args[0].lower() if args else "last")
        import sqlite3
        def load_rows(where: str = "", params: tuple[Any, ...] = (), limit: int = 10):
            with sqlite3.connect(cr.db_path) as con:
                return con.execute("SELECT history_id,encounter_id,round_number,actor_id,target_actor_id,action_type,ability_id,outcome,damage,healing,result_json,world_time,created_at FROM combat_round_history " + where + " ORDER BY created_at DESC LIMIT ?", (*params, limit)).fetchall()
        if sub=="formula" and len(args)>=2:
            _,combat=self._stat_services(character); fid=args[1]
            return CommandResult(json.dumps({"formula_id":fid,"expression":combat.formulas.get(fid),"available":fid in combat.formulas}, indent=2), ok=fid in combat.formulas)
        if sub=="history":
            rows=load_rows(limit=int(args[1]) if len(args)>1 and args[1].isdigit() else 10)
            if not rows: return CommandResult("No combat history is available.", ok=False)
            lines=["COMBAT BREAKDOWN HISTORY"]
            for r in rows:
                lines.append(f"{r[0]} round={r[2]} actor={r[3]} target={r[4]} result={r[7]} damage={r[8]} healing={r[9]} time={r[11]}")
            return CommandResult("\n".join(lines))
        if sub=="action" and len(args)>=2:
            rows=load_rows("WHERE history_id=? OR json_extract(result_json, '$.action_id')=?", (args[1], args[1]), 1)
            if not rows: return CommandResult("No combat action diagnostic matched that ID.", ok=False)
            try: data=json.loads(rows[0][10] or "{}")
            except Exception: data={"raw": rows[0][10]}
            with sqlite3.connect(cr.db_path) as con:
                con.row_factory=sqlite3.Row
                life=con.execute("SELECT transition_id,corpse_status,reward_status,loot_status,kill_credit_status,quest_credit_status,respawn_status,combat_end_status,corpse_id,reward_claim_id,respawn_id,new_state FROM actor_lifecycle_transitions WHERE trigger_action_id=? ORDER BY created_at DESC LIMIT 1", (args[1],)).fetchone()
                if life:
                    data["lifecycle_status"] = dict(life)
            return CommandResult("COMBAT BREAKDOWN ACTION\n"+json.dumps({"history_id":rows[0][0],"round":rows[0][2],"actor":rows[0][3],"target":rows[0][4],"result":data}, indent=2, default=str))
        if sub=="target" and len(args)>=2:
            q=args[1]; aid=q if ':' in q else ('character:'+q)
            rows=load_rows("WHERE actor_id=? OR target_actor_id=? OR actor_id LIKE ? OR target_actor_id LIKE ?", (aid, aid, '%'+q+'%', '%'+q+'%'), 10)
            if not rows: return CommandResult("No recent diagnostics involved that target.", ok=False)
            return CommandResult("COMBAT BREAKDOWN TARGET\n"+"\n".join(f"{r[0]} actor={r[3]} target={r[4]} result={r[7]} damage={r[8]}" for r in rows))
        data=getattr(cr, "last_resolution", None)
        if not data:
            rows=load_rows(limit=1)
            if rows:
                try: data=json.loads(rows[0][10] or "{}")
                except Exception: data={"raw": rows[0][10]}
                data={"history_id":rows[0][0],"round":rows[0][2],"actor":rows[0][3],"target":rows[0][4],"result":data}
        if not data: return CommandResult("No combat resolution breakdown is available yet.", ok=False)
        return CommandResult("COMBAT BREAKDOWN LAST\n"+json.dumps(data, indent=2, default=str))

    def _cmd_statbreakdown(self, character: Any, args: list[str], raw: str) -> CommandResult:
        if not args: return CommandResult("Usage: statbreakdown <stat>", ok=False)
        attr,combat=self._stat_services(character); stat=args[-1].lower();
        if stat in attr.definitions:
            b=attr.get_breakdown(character, stat); return CommandResult(json.dumps({**b.__dict__, 'sources': b.sources}, indent=2, default=str))
        if self._effective_role(character) not in {"builder","admin","owner"}: return CommandResult("Detailed formula diagnostics require Builder access.", ok=False)
        return CommandResult(json.dumps(combat.get_breakdown(character, stat), indent=2, default=str))


    def _stats_actor_id(self, character: Any) -> str:
        return str(getattr(character, "id", None) or getattr(character, "name", None) or "unknown")

    def _audit_stat_edit(self, root, actor, command, adapter, rid, before, after, validation):
        try:
            p=root/'builder'/'audit'/'stats_edits.jsonl'; p.parent.mkdir(parents=True, exist_ok=True)
            rec={'actor':actor,'world':root.name,'command':command,'document':adapter.name,'record_id':rid,'before_hash':norm_hash(before) if before is not None else None,'after_hash':norm_hash(after) if after is not None else None,'validation_result':validation,'timestamp':now()}
            with p.open('a',encoding='utf-8') as f: f.write(json.dumps(rec, sort_keys=True, default=str)+'\n')
        except Exception: pass

    def _adapter_edit(self, character: Any, args: list[str], raw: str, adapter_cls: Any, label: str) -> CommandResult:
        if self._effective_role(character) not in {"builder","admin","owner"}: return CommandResult("You do not have permission for that command.", ok=False)
        attr,_=self._stat_services(character); root=attr.world_root; a=adapter_cls(root); sub=args[0].lower() if args else 'list'; actor=self._stats_actor_id(character)
        def validate(data):
            docs=StatCombatPublishValidator(root).load_all(); docs[a.name]=data; ctx=StatCombatPublishValidator(root).graph(docs); return a.validate_doc(data,ctx)
        try:
            data=a.load_draft()
            if sub=='list':
                vals=a.values(data); lines=[f"{label} drafts ({len(vals)})"]
                for r in vals:
                    rid=r.get(a.id_key) or r.get('id'); lines.append(f"- {rid} | {r.get('name','')} | {r.get('short_name','')} | default={r.get('default_value','')} min={r.get('minimum_value','')} max={r.get('maximum_value','')} creation={r.get('creation_minimum','')}-{r.get('creation_maximum','')} group={r.get('display_group','')} order={r.get('display_order',r.get('order',''))} enabled={r.get('enabled','')} visible={r.get('player_visible',r.get('visible',''))}")
                return CommandResult('\n'.join(lines))
            if adapter_cls is RangeRulesDocumentAdapter:
                return self._range_edit(a, data, args, raw, actor)
            if adapter_cls is EncumbranceDocumentAdapter:
                return self._encumbrance_edit(a, data, args, raw, actor)
            if sub in {'show','preview','validate'} and len(args)>=2:
                rec=a.find(data,args[1]); issues=validate(data)
                if sub=='validate':
                    rel=[i.__dict__ for i in issues if i.record_id in {args[1],'*','unburdened'}]; return CommandResult(json.dumps({'ok':not rel,'errors':rel}, indent=2), ok=not rel)
                return CommandResult(json.dumps({'record':rec,'validation_errors':[i.__dict__ for i in issues if i.record_id in {args[1],'*'}]}, indent=2), ok=bool(rec))
            if sub=='create' and len(args)>=2:
                rid=safe_id(args[1]);
                if a.find(data,rid): return CommandResult(f"{rid} already exists", ok=False)
                before=copy.deepcopy(data); rec=a.default_record(rid); a.put(data,rec); issues=validate(data)
                if issues: return CommandResult('\n'.join(i.line() for i in issues), ok=False)
                a.save_draft(data); self._audit_stat_edit(root,actor,raw,a,rid,before,data,{'ok':True}); return CommandResult(json.dumps(rec, indent=2))
            if sub=='clone' and len(args)>=3:
                src,new=args[1],safe_id(args[2]); old=a.find(data,src)
                if not old: return CommandResult('Source not found.', ok=False)
                if a.find(data,new): return CommandResult('Target already exists.', ok=False)
                before=copy.deepcopy(data); rec=copy.deepcopy(old); rec[a.id_key]=new; rec['id']=new; a.put(data,rec); issues=validate(data)
                if issues: return CommandResult('\n'.join(i.line() for i in issues), ok=False)
                a.save_draft(data); self._audit_stat_edit(root,actor,raw,a,new,before,data,{'ok':True}); return CommandResult(json.dumps(rec, indent=2))
            if sub=='delete' and len(args)>=2:
                rid=args[1]; ref=StatCombatPublishValidator(root).deletion_errors(a.name, rid)
                if ref: return CommandResult('\n'.join(i.line() for i in ref), ok=False)
                if adapter_cls is PostureDocumentAdapter and rid in a.required: return CommandResult('Required posture cannot be deleted.', ok=False)
                before=copy.deepcopy(data); a.remove(data,rid); issues=validate(data)
                if issues: return CommandResult('\n'.join(i.line() for i in issues), ok=False)
                a.save_draft(data); self._audit_stat_edit(root,actor,raw,a,rid,before,data,{'ok':True}); return CommandResult(f"Deleted draft {rid}.")
            if sub in {'tag','variable'} and len(args)>=4 and args[2].lower() in {'add','remove'}:
                rid=args[1]; rec=a.find(data,rid)
                if not rec: return CommandResult('Record not found.', ok=False)
                before=copy.deepcopy(data); field='tags' if sub=='tag' else 'variables'; vals=list(rec.setdefault(field,[])); val=args[3]
                if args[2].lower()=='add' and val not in vals: vals.append(val)
                if args[2].lower()=='remove': vals=[x for x in vals if x!=val]
                rec[field]=vals; a.normalize_record(rec); issues=validate(data)
                if issues: return CommandResult('\n'.join(i.line() for i in issues), ok=False)
                a.save_draft(data); self._audit_stat_edit(root,actor,raw,a,rid,before,data,{'ok':True}); return CommandResult(json.dumps(rec, indent=2))
            if adapter_cls is CombatMessageDocumentAdapter and sub in {'field','condition'}:
                rid=args[1]; rec=a.find(data,rid)
                if not rec: return CommandResult('Record not found.', ok=False)
                before=copy.deepcopy(data)
                if sub=='field' and len(args)>=4 and args[2] in {'attacker','defender','observer'}: rec[args[2]]=' '.join(args[3:])
                elif sub=='condition' and len(args)>=4: rec.setdefault('conditions',{})[args[2]]=' '.join(args[3:])
                else: return CommandResult('Usage: combatmessage field <id> <attacker|defender|observer> <template> | condition <id> <field> <value>', ok=False)
                issues=validate(data)
                if issues: return CommandResult('\n'.join(i.line() for i in issues), ok=False)
                a.save_draft(data); self._audit_stat_edit(root,actor,raw,a,rid,before,data,{'ok':True}); return CommandResult(json.dumps(rec, indent=2))
            if adapter_cls is PostureDocumentAdapter and sub in {'modifier','allow','automatic-hit-against','wake-on-damage'}:
                rid=args[1]; rec=a.find(data,rid)
                if not rec: return CommandResult('Record not found.', ok=False)
                before=copy.deepcopy(data)
                if sub=='modifier' and len(args)>=4:
                    if args[2] not in a.fields: return CommandResult('Unknown modifier field.', ok=False)
                    rec[args[2]]=parse_num(args[3])
                elif sub=='allow' and len(args)>=4 and args[2] in {'attack','cast','move'}: rec[{'attack':'attack_allowed','cast':'cast_allowed','move':'movement_allowed'}[args[2]]]=parse_bool(args[3])
                elif sub in {'automatic-hit-against','wake-on-damage'} and len(args)>=3: rec[sub.replace('-','_')]=parse_bool(args[2])
                else: return CommandResult('Usage: postureedit modifier/allow/automatic-hit-against/wake-on-damage ...', ok=False)
                issues=validate(data)
                if issues: return CommandResult('\n'.join(i.line() for i in issues), ok=False)
                a.save_draft(data); self._audit_stat_edit(root,actor,raw,a,rid,before,data,{'ok':True}); return CommandResult(json.dumps(rec, indent=2))
            if len(args)>=3:
                rid=args[1]; rec=a.find(data,rid)
                if not rec: return CommandResult('Record not found.', ok=False)
                before=copy.deepcopy(data); val=' '.join(args[2:])
                fmap={'short':'short_name','default':'default_value','minimum':'minimum_value','maximum':'maximum_value','creationmin':'creation_minimum','creationmax':'creation_maximum','order':'display_order','group':'display_group','role':'semantic_role','visible':'player_visible','enable':'enabled','formula':'formula_id','format':'display_format'}
                field=fmap.get(sub,sub)
                if sub in {'visible','enable'}: val=parse_bool(val)
                elif sub in {'default','minimum','maximum','creationmin','creationmax','order'}: val=parse_num(val)
                elif sub in {'minimum','maximum'} and adapter_cls is FormulaDocumentAdapter: field=sub; val=parse_num(val)
                elif sub in {'rounding'} and val not in ROUNDINGS: return CommandResult('Unsupported rounding.', ok=False)
                rec[field]=val; issues=validate(data)
                if issues: return CommandResult('\n'.join(i.line() for i in issues), ok=False)
                a.save_draft(data); self._audit_stat_edit(root,actor,raw,a,rid,before,data,{'ok':True}); return CommandResult(json.dumps(rec, indent=2))
            return CommandResult(f"Usage: {label.lower()} list/show/create/clone/edit/delete/validate/preview", ok=False)
        except Exception as e: return CommandResult(str(e), ok=False)

    def _encumbrance_edit(self, a, data, args, raw, actor):
        attr,_=self._stat_services(actor) if False else (None,None); root=a.root; sub=args[0].lower() if args else 'list'
        if sub=='list': return CommandResult('Encumbrance drafts:\n'+'\n'.join(f"- {r['id']} {r.get('threshold_percent')}% order={r.get('display_order')}" for r in a.values(data)))
        if sub in {'validate','preview'}:
            issues=a.validate_doc(data,{}); return CommandResult(json.dumps({'ok':not issues,'errors':[i.__dict__ for i in issues],'records':a.values(data)}, indent=2), ok=not issues)
        if len(args)<2: return CommandResult('Usage: encumbranceedit show|set|rename|order|description|penalty|delete|validate|preview ...', ok=False)
        rid=safe_id(args[1]); rec=a.find(data,rid) or a.default_record(rid); before=copy.deepcopy(data)
        if sub=='show': return CommandResult(json.dumps(rec, indent=2), ok=bool(a.find(data,rid)))
        if sub=='set' and len(args)>=3: rec['threshold_percent']=parse_num(args[2]); a.put(data,rec)
        elif sub=='rename' and len(args)>=3: rec['name']=' '.join(args[2:]); a.put(data,rec)
        elif sub=='order' and len(args)>=3: rec['display_order']=int(args[2]); a.put(data,rec)
        elif sub=='description' and len(args)>=3: rec['description']=' '.join(args[2:]); a.put(data,rec)
        elif sub=='penalty' and len(args)>=4: rec.setdefault('penalties',{})[args[2]]=parse_num(args[3]); a.put(data,rec)
        elif sub=='delete': a.remove(data,rid)
        else: return CommandResult('Usage: encumbranceedit show|set|rename|order|description|penalty|delete|validate|preview ...', ok=False)
        issues=a.validate_doc(data,{})
        if issues: return CommandResult('\n'.join(i.line() for i in issues), ok=False)
        a.save_draft(data); self._audit_stat_edit(root,actor,raw,a,rid,before,data,{'ok':True}); return CommandResult(json.dumps(a.find(data,rid) or {'deleted':rid}, indent=2))

    def _range_edit(self, a, data, args, raw, actor):
        root=a.root; sub=args[0].lower() if args else 'show'; rr=data.setdefault('range_rules',{})
        if sub in {'show','preview'}: return CommandResult(json.dumps({'range_rules':rr}, indent=2))
        if sub=='validate':
            issues=StatCombatPublishValidator(root).validate()['errors']; rel=[i for i in issues if i.document=='range_rules']; return CommandResult(json.dumps({'ok':not rel,'errors':[i.__dict__ for i in rel]}, indent=2), ok=not rel)
        if sub in {'set','reset'} and len(args)>=2:
            field=args[1]
            if field not in a.allowed: return CommandResult('Unknown range field.', ok=False)
            before=copy.deepcopy(data)
            if sub=='reset': rr[field]=a.default_document()['range_rules'].get(field)
            else:
                if len(args)<3: return CommandResult('Usage: rangeedit set <field> <value>', ok=False)
                typ=a.allowed[field]; val=' '.join(args[2:]); rr[field]=parse_bool(val) if typ is bool else typ(parse_num(val) if typ is int else val)
            issues=StatCombatPublishValidator(root).validate()['errors']; rel=[i for i in issues if i.document=='range_rules']
            if rel: return CommandResult('\n'.join(i.line() for i in rel), ok=False)
            a.save_draft(data); self._audit_stat_edit(root,actor,raw,a,'range_rules',before,data,{'ok':True}); return CommandResult(json.dumps({'range_rules':rr}, indent=2))
        return CommandResult('Usage: rangeedit show|set|reset|validate|preview', ok=False)

    def _cmd_attributeedit(self, character: Any, args: list[str], raw: str) -> CommandResult:
        return self._adapter_edit(character,args,raw,AttributeDocumentAdapter,'Attribute')

    def _cmd_formulaedit(self, character: Any, args: list[str], raw: str) -> CommandResult:
        if args and args[0].lower()=='test' and len(args)>=2:
            attr,_=self._stat_services(character); a=FormulaDocumentAdapter(attr.world_root); rec=a.find(a.load_draft(),args[1])
            if not rec: return CommandResult('Formula not found.', ok=False)
            supplied={};
            for tok in args[2:]:
                if '=' in tok:
                    k,v=tok.split('=',1); supplied[k]=parse_num(v)
            defaults={v:0 for v in rec.get('variables',[]) if v not in supplied}; vals={**defaults,**supplied}; errors=[]; rawv=None; final=None
            try:
                rawv=FormulaEngine().evaluate_expression(rec['formula_id'], rec.get('expression','0'), vals).final_value; final=rawv
                if rec.get('rounding')=='floor': import math; final=math.floor(final)
                elif rec.get('rounding')=='ceil': import math; final=math.ceil(final)
                elif rec.get('rounding')=='round': final=round(final)
                if rec.get('minimum') is not None: final=max(float(rec['minimum']), final)
                if rec.get('maximum') is not None: final=min(float(rec['maximum']), final)
            except Exception as e: errors.append(str(e))
            return CommandResult(json.dumps({'expression':rec.get('expression'),'supplied_inputs':supplied,'defaulted_inputs':defaults,'raw_result':rawv,'rounding':rec.get('rounding'),'clamp':[rec.get('minimum'),rec.get('maximum')],'final_result':final,'errors':errors}, indent=2), ok=not errors)
        return self._adapter_edit(character,args,raw,FormulaDocumentAdapter,'Formula')

    def _cmd_statdef(self, character: Any, args: list[str], raw: str) -> CommandResult:
        return self._adapter_edit(character,args,raw,StatDefinitionDocumentAdapter,'Statdef')

    def _cmd_resistanceedit(self, character: Any, args: list[str], raw: str) -> CommandResult:
        return self._adapter_edit(character,args,raw,ResistanceDocumentAdapter,'Resistance')

    def _cmd_encumbranceedit(self, character: Any, args: list[str], raw: str) -> CommandResult:
        return self._adapter_edit(character,args,raw,EncumbranceDocumentAdapter,'Encumbrance')

    def _cmd_postureedit(self, character: Any, args: list[str], raw: str) -> CommandResult:
        return self._adapter_edit(character,args,raw,PostureDocumentAdapter,'Posture')

    def _cmd_rangeedit(self, character: Any, args: list[str], raw: str) -> CommandResult:
        return self._adapter_edit(character,args,raw,RangeRulesDocumentAdapter,'Range')

    def _cmd_combatmessage(self, character: Any, args: list[str], raw: str) -> CommandResult:
        return self._adapter_edit(character,args,raw,CombatMessageDocumentAdapter,'Combatmessage')

    def _cmd_helpedit(self, character: Any, args: list[str], raw: str) -> CommandResult:
        if self._effective_role(character) not in {"builder","admin","owner"}: return CommandResult("You do not have permission for that command.", ok=False)
        svc=self._help_service(character); drafts=svc.load_drafts(); sub=(args[0].lower() if args else "list")
        try:
            if sub=="list": return CommandResult("Help drafts:\n"+"\n".join(f"- {e.help_id}: {e.title}" for e in sorted(drafts.values(), key=lambda e:e.help_id)))
            if len(args)<2: return CommandResult("Usage: helpedit <show|create|clone|title|summary|body|syntax|example|keyword|alias|category|related|access|visible|validate|preview|delete|publish> <id> ...", ok=False)
            hid=args[1]
            if sub=="create":
                if hid in drafts: return CommandResult("That help entry already exists.", ok=False)
                drafts[hid]=HelpEntry(help_id=hid, keywords=(hid.replace('_',' '),), title=hid.replace('_',' ').title(), summary="Draft help entry."); svc.save_drafts(drafts); return CommandResult(f"Created draft help entry {hid}.")
            if sub=="clone" and len(args)>=3:
                src=svc.get_entry(hid, character); nid=args[2]
                if not isinstance(src, HelpEntry): return CommandResult("Source help entry not found.", ok=False)
                data=src.to_dict(); data["help_id"]=nid; data["keywords"]=[nid.replace('_',' ')]; drafts[nid]=HelpEntry.from_dict(data); svc.save_drafts(drafts); return CommandResult(f"Cloned {src.help_id} to {nid}.")
            e=drafts.get(hid) or svc._entry_exact(hid, drafts)
            if not e: return CommandResult("Help draft not found.", ok=False)
            data=e.to_dict()
            rest=" ".join(args[2:]).strip()
            if sub=="show": return CommandResult(json.dumps(data, indent=2))
            if sub in {"title","summary","body","category"}: data[sub]=rest
            elif sub=="syntax": data.setdefault("syntax",[]); data["syntax"].append(rest)
            elif sub=="example": data.setdefault("examples",[]); data["examples"].append(rest)
            elif sub in {"keyword","alias","related"} and len(args)>=4:
                key={"keyword":"keywords","alias":"aliases","related":"related_topics"}[sub]; op=args[2].lower(); val=" ".join(args[3:])
                items=list(data.get(key) or [])
                if op=="add" and val not in items: items.append(val)
                if op=="remove": items=[x for x in items if normalize_help_query(x)!=normalize_help_query(val)]
                data[key]=items
            elif sub=="access": data["minimum_access_level"]=rest.lower()
            elif sub=="visible": data["player_visible"]=rest.lower() in {"on","true","yes","1"}
            elif sub=="delete": drafts.pop(e.help_id,None); svc.save_drafts(drafts); return CommandResult(f"Deleted draft help entry {e.help_id}.")
            elif sub=="validate": svc.validate_entry(e); return CommandResult(f"Help entry {e.help_id} is valid.")
            elif sub=="preview": return CommandResult(self._render_help_entry(e, character, title_prefix="Preview: "))
            else: return CommandResult("Unknown helpedit action.", ok=False)
            ne=HelpEntry.from_dict(data); svc.validate_entry(ne); drafts[e.help_id]=ne; svc.save_drafts(drafts); return CommandResult(f"Updated help draft {ne.help_id}.")
        except Exception as exc:
            return CommandResult(f"Help edit failed: {exc}", ok=False)

    def _cmd_resists(self, character: Any, args: list[str], raw: str) -> CommandResult:
        """Display resistances through the single score renderer."""
        return CommandResult(narrative=self._render_score_section(character, "resistances"))

    def _ability_service(self, character: Any) -> AbilityExecutionService | None:
        svc = getattr(self, "ability_service", None)
        if svc:
            svc.actor_from_character(character)
        return svc

    def _ability_rows(self, character: Any, kinds: set[str] | None = None) -> list[dict[str, Any]]:
        svc = self._ability_service(character)
        rows = svc.get_actor_abilities(character.id) if svc else []
        allowed = {"skill", "proficiency", "trade_skill", "combat_skill", "technique", "spell", "magic", "prayer", "power", "passive", "heal", "buff", "debuff", "utility", "defensive", "movement"}
        rows = [r for r in rows if str(r.get("id") or r.get("ability_id") or "") in getattr(getattr(svc, "registry", None), "abilities", {}) and str(r.get("ability_type") or "").lower() in allowed]
        if kinds:
            rows = [r for r in rows if str(r.get("ability_type") or "").lower() in kinds]
        return rows

    def _ability_status_text(self, character: Any, row: dict[str, Any]) -> str:
        aid = str(row.get("id") or "")
        if aid == "build_campfire" and not (getattr(character, "current_campsite_id", None) or getattr(character, "campsite_id", None)):
            return "Requires an established campsite."
        for cost in row.get("costs", []) or []:
            resource = str(cost.get("resource_id") or "").lower()
            amount = int(cost.get("amount") or 0)
            if resource in {"mana", "mp"} and int(getattr(character, "mana", 0) or 0) < amount:
                return f"Requires {amount} mana."
        return "Ready"

    def _format_ability_list(self, rows: list[dict[str, Any]], empty: str, title: str = "ABILITIES") -> CommandResult:
        for row in rows:
            row["status_text"] = self._ability_status_text(getattr(self, "_format_character", None), row) if getattr(self, "_format_character", None) else row.get("status_text", "Ready")
        doc = build_abilities_document(rows, title=title, empty=empty, theme=resolve_effective_display_theme(getattr(self, "_format_character", None), family=title.lower()))
        return CommandResult(narrative=render_display_mud(doc), display_document=doc, display_intent=title)

    def _cmd_spellup(self, character: Any, args: list[str], raw: str) -> CommandResult:
        if args and args[0].lower() == "cast":
            svc = self._ability_service(character)
            if not svc: return CommandResult("Spellup casting is unavailable.", ok=False)
            rows = [r for r in self._ability_rows(character) if "spellup_eligible" in (r.get("tags") or []) and (r.get("targeting") or {}).get("mode", "self") == "self" and not r.get("damage_components")]
            done=[]
            for r in sorted(rows, key=lambda x: ((x.get("plugin_data") or {}).get("spellup_priority", 100), x.get("id"))):
                res = svc.execute_instant_ability(character.id, r["id"], "self")
                done.append(f"{r.get('name')}: {'cast' if res.get('ok') else 'skipped'}")
                if not res.get("ok"): break
            return CommandResult("Spellup cast summary:\n" + ("\n".join(done) if done else "No eligible self buffs."))
        return CommandResult(narrative=self._render_score_section(character, "spellup"))

    def _cmd_showvnums(self, character: Any, args: list[str], raw: str) -> CommandResult:
        if self._effective_role(character) not in {"admin", "owner", "builder"}:
            return CommandResult("You do not have permission for that command.", ok=False)
        prefs = getattr(character, "preferences", None) or {}
        setattr(character, "preferences", prefs)
        if args and args[0].lower() in {"on", "off"}:
            prefs["show_vnums"] = args[0].lower() == "on"
        enabled = bool(prefs.get("show_vnums"))
        return CommandResult(f"VNUM display is {'on' if enabled else 'off'}.")

    def _cmd_abilitydiagnose(self, character: Any, args: list[str], raw: str) -> CommandResult:
        if self._effective_role(character) not in {"admin", "owner", "builder"}:
            return CommandResult("You do not have permission for that command.", ok=False)
        svc = self._ability_service(character)
        if not svc:
            return CommandResult("Ability system is unavailable.", ok=False)
        actor_id = character.id if not args or args[0].lower() == "self" else args[0]
        lines = ["Ability diagnostics", "Ability ID | Definition kind | Grant source | Persisted actor ID | Resolved actor ID | Rank/proficiency | Reason"]
        seen = set()
        for lookup in dict.fromkeys([str(actor_id), str(actor_id).split(":",1)[1] if str(actor_id).startswith("character:") else "character:"+str(actor_id)]):
            if not lookup: continue
            for g in svc.project_ability_grants(lookup):
                aid = str(g.get("ability_id") or "")
                definition = getattr(svc.registry, "abilities", {}).get(aid)
                reason = "accepted" if definition and getattr(definition, "enabled", True) else "rejected: missing/disabled definition"
                key=(lookup,aid,g.get("grant_id"));
                if key in seen: continue
                seen.add(key)
                lines.append(f"{aid} | {getattr(definition,'ability_type','') if definition else ''} | {g.get('source_type','')} | {lookup} | {actor_id} | {g.get('proficiency', g.get('rank', 1))} | {reason}")
        return CommandResult("\n".join(lines))

    def _cmd_spells(self, character: Any, args: list[str], raw: str) -> CommandResult:
        svc = self._ability_service(character)
        rows = ability_snapshots_as_rows(AbilityDisplaySnapshotService(svc).list_snapshots(character, "spells")) if svc else []
        if not rows:
            rows = [r for r in self._ability_rows(character) if str(r.get("ability_type")) == "spell"]
        doc = build_abilities_document(rows, title="SPELLS", empty="You know no spells.", theme=resolve_effective_display_theme(character, family="spells"))
        return CommandResult(render_display_mud(doc), display_document=doc, display_intent="SPELLS")

    def _cmd_skills(self, character: Any, args: list[str], raw: str) -> CommandResult:
        svc = self._ability_service(character)
        rows = ability_snapshots_as_rows(AbilityDisplaySnapshotService(svc).list_snapshots(character, "skills")) if svc else []
        if not rows:
            rows = [r for r in self._ability_rows(character) if str(r.get("ability_type")) not in {"spell", "passive"}]
        doc = build_abilities_document(rows, title="SKILLS", empty="You know no skills.", theme=resolve_effective_display_theme(character, family="skills"))
        return CommandResult(render_display_mud(doc), display_document=doc, display_intent="SKILLS")

    def _cmd_abilities(self, character: Any, args: list[str], raw: str) -> CommandResult:
        svc = self._ability_service(character)
        rt = getattr(self, "runtime", None)
        warmed = rt.build_projection(character, "abilities") if rt and hasattr(rt, "build_projection") else None
        rows = ability_snapshots_as_rows(AbilityDisplaySnapshotService(svc).list_snapshots(character, "abilities")) if svc else (warmed or [])
        doc = build_abilities_document(rows, title="ABILITIES", empty="You have no abilities.", theme=resolve_effective_display_theme(character, family="abilities"))
        return CommandResult(render_display_mud(doc), display_document=doc, display_intent="ABILITIES")

    def _cmd_ability_detail(self, character: Any, args: list[str], raw: str) -> CommandResult:
        q = " ".join(args).lower().replace(" ", "_")
        for r in self._ability_rows(character):
            if q in {str(r.get("id")).lower(), str(r.get("name")).lower().replace(" ", "_")}:
                return self._format_ability_list([r], "Ability not found.", "ABILITY")
        return CommandResult("Ability not found.", ok=False)

    def _cmd_direct_ability(self, character: Any, args: list[str], raw: str) -> CommandResult:
        cmd = raw.strip().split()[0].lower() if raw.strip() else ""
        return self._cmd_use_ability(character, [cmd] + list(args), raw)

    def _cmd_use_ability(self, character: Any, args: list[str], raw: str) -> CommandResult:
        if not args: return CommandResult("Use which ability?", ok=False)
        svc = self._ability_service(character)
        if not svc: return CommandResult("Ability system is unavailable.", ok=False)
        rt = getattr(self, 'runtime', None)
        cr = getattr(rt, 'combat_runtime', None) if rt else getattr(self, 'combat_runtime', None)
        if cr and cr.is_actor_in_active_combat(cr.actor_id_for_character(character)):
            phrase_parts=list(args)
            target=''
            # Prefer longest learned ability name prefix; remaining words become target text.
            learned=svc.get_actor_abilities(character.id)
            best=None
            joined=' '.join(phrase_parts).lower()
            for row in learned:
                names=[str(row.get('id','')).replace('_',' '), str(row.get('name',''))]
                for nm in names:
                    nm=nm.lower().strip()
                    if nm and (joined == nm or joined.startswith(nm+' ')) and (best is None or len(nm)>len(best[0])):
                        best=(nm,row)
            if best:
                target=joined[len(best[0]):].strip()
                res=cr.queue_ability(character, str(best[1].get('id')), target)
                return CommandResult('\n'.join(res.messages), ok=res.ok)

        if args and args[0].lower() in {"use", "cast", "invoke", "perform"}:
            args = args[1:]
        phrase = " ".join(args).lower().strip()
        aid = phrase.replace(" ", "_")
        target = "self"
        by_name = {}
        for r in svc.registry.abilities.values():
            rid = getattr(r, "id", None) or (r.get("id") if isinstance(r, dict) else "")
            rname = getattr(r, "name", None) or (r.get("name") if isinstance(r, dict) else "")
            if rname:
                by_name[str(rname).lower().replace(" ", "_")] = rid
        if aid not in svc.registry.abilities and aid not in by_name:
            first = args[0].lower().replace(" ", "_"); aid = first; target = " ".join(args[1:]) or "self"
        aid = aid if aid in svc.registry.abilities else by_name.get(aid, aid)
        gateway = svc.gateway() if hasattr(svc, "gateway") else None
        res = gateway.execute(character.id, aid, target, {"command": raw}) if gateway else None
        if res is None:
            return CommandResult("Ability system is unavailable.", ok=False)
        return CommandResult(res.player_message or ("Ability activated." if res.ok else "You cannot use that ability."), ok=res.ok, state_updates={"render_room": res.ok and res.ability_id in {"set_camp","build_campfire","recall"}})

    def _cmd_cancel_ability(self, character: Any, args: list[str], raw: str) -> CommandResult:
        svc = self._ability_service(character)
        if not svc or not svc.db_path: return CommandResult("No current cast.", ok=False)
        import sqlite3
        with sqlite3.connect(svc.db_path) as c: row=c.execute("SELECT cast_id FROM actor_ability_casts WHERE actor_id=? AND state IN ('casting','channeling','pending') ORDER BY started_world_time DESC LIMIT 1", (character.id,)).fetchone()
        if not row: return CommandResult("No current cast.", ok=False)
        svc.cancel_ability(row[0], "player_cancelled")
        return CommandResult("You cancel your current cast.")

    def _cmd_cooldowns(self, character: Any, args: list[str], raw: str) -> CommandResult:
        return self._cmd_abilitycooldowns(character, ["self"], raw)

    def _cmd_builder_ability(self, character: Any, args: list[str], raw: str) -> CommandResult:
        svc=self._ability_service(character); cmd=raw.split()[0].lower()
        if not svc: return CommandResult("Ability registry unavailable.", ok=False)
        if cmd == "abilitylist": return CommandResult("Abilities:\n" + "\n".join(sorted(svc.registry.abilities)) )
        if args and args[0] in svc.registry.abilities:
            a=svc.registry.abilities[args[0]]; errs,warns=svc.registry.validate_ability(a); return CommandResult(f"Ability {a.id}: {a.name}\nType: {a.ability_type}\nErrors: {errs or ['none']}\nWarnings: {warns or ['none']}\nData: {a.to_dict()}")
        return CommandResult(f"{cmd} is available for Builder draft authoring; use abilitylist or abilitystat <ability_id>.")

    def _cmd_builder_loadout(self, character: Any, args: list[str], raw: str) -> CommandResult:
        svc=self._ability_service(character); cmd=raw.split()[0].lower()
        if not svc: return CommandResult("Ability registry unavailable.", ok=False)
        if cmd == "loadoutlist": return CommandResult("Loadouts:\n" + "\n".join(sorted(svc.registry.loadouts)))
        if args and args[0] in svc.registry.loadouts:
            l=svc.registry.loadouts[args[0]]; return CommandResult(f"Loadout {l.id}: {l.name}\nAbilities: {', '.join(l.ability_ids)}\nSpellup: {', '.join(l.spellup_priority)}")
        return CommandResult(f"{cmd} is available for Builder draft loadout authoring.")

    def _cmd_ability_grant(self, character: Any, args: list[str], raw: str) -> CommandResult:
        svc=self._ability_service(character); cmd=raw.split()[0].lower()
        if not svc or len(args)<2: return CommandResult(f"Usage: {cmd} <actor> <ability_id>", ok=False)
        actor_id = character.id if args[0] == "self" else args[0]
        n = svc.revoke_ability(actor_id,args[1],"admin") if cmd=="abilityrevoke" else svc.grant_ability(actor_id,args[1],"admin",character.id)
        return CommandResult(f"{cmd}: {n}")

    def _cmd_actorabilities(self, character: Any, args: list[str], raw: str) -> CommandResult:
        return self._cmd_abilities(character,args,raw)

    def _cmd_abilitycooldowns(self, character: Any, args: list[str], raw: str) -> CommandResult:
        svc=self._ability_service(character)
        if not svc or not svc.db_path: return CommandResult("No cooldowns.")
        import sqlite3
        actor_id=character.id if not args or args[0]=="self" else args[0]
        with sqlite3.connect(svc.db_path) as c: rows=c.execute("SELECT ability_id,cooldown_group,ready_world_time,charges_current,charges_maximum FROM actor_ability_cooldowns WHERE actor_id=? AND active=1 ORDER BY ready_world_time,ability_id", (actor_id,)).fetchall()
        docs = [{"name": str(r[0]).replace("_", " ").title(), "rank": 1, "maximum_rank": 1, "status_text": "Ready", "category": "Cooldown", "costs": [], "description": f"Charges: {r[3]}/{r[4]}"} for r in rows]
        doc = build_abilities_document(docs, title="COOLDOWNS", empty="No active cooldowns.", theme=resolve_effective_display_theme(character, family="cooldowns"))
        return CommandResult(render_display_mud(doc), display_document=doc, display_intent="COOLDOWNS")

    def _cmd_abilitycasts(self, character: Any, args: list[str], raw: str) -> CommandResult:
        svc=self._ability_service(character)
        if not svc or not svc.db_path: return CommandResult("No casts.")
        import sqlite3
        actor_id=character.id if not args or args[0]=="self" else args[0]
        with sqlite3.connect(svc.db_path) as c: rows=c.execute("SELECT cast_id,ability_id,state,completes_world_time FROM actor_ability_casts WHERE actor_id=? ORDER BY started_world_time DESC LIMIT 10", (actor_id,)).fetchall()
        return CommandResult("Ability casts:\n" + ("\n".join(f"- {r[0]} {r[1]} {r[2]} completes={r[3]}" for r in rows) if rows else "- none"))

    def _cmd_affects(self, character: Any, args: list[str], raw: str) -> CommandResult:
        """Display active visible affects through the unified themed frame family."""
        rt = getattr(self, "runtime", None)
        raw_affects = rt.build_projection(character, "effects") if rt and hasattr(rt, "build_projection") else (getattr(character, "affects", {}) or getattr(character, "effects", {}) or {})
        if isinstance(raw_affects, dict):
            effects = [dict(v if isinstance(v, dict) else {"name": k}, name=(v.get("name") if isinstance(v, dict) else k) or k) for k, v in raw_affects.items()]
        else:
            effects = [dict(x) for x in raw_affects if isinstance(x, dict)]
        theme = resolve_effective_display_theme(character, family="affects")
        doc = build_affects_document(effects, theme=theme)
        return CommandResult(narrative=render_display_mud(doc, color_enabled=theme.color_enabled), display_document=doc, display_intent="AFFECTS")

    def _cmd_worth(self, character: Any, args: list[str], raw: str) -> CommandResult:
        """Display net worth through the unified character display suite."""
        svc = getattr(self, "character_display_snapshots", None) or getattr(getattr(self, "runtime", None), "character_display_snapshots", None) or CharacterDisplaySnapshotService(getattr(self, "runtime", None))
        rt = getattr(self, "runtime", None)
        worth_snapshot = rt.build_projection(character, "worth") if rt and hasattr(rt, "build_projection") else (svc.build_worth_snapshot(character) if hasattr(svc, "build_worth_snapshot") else None)
        doc = build_worth_document(character, worth_snapshot=worth_snapshot, theme=resolve_effective_display_theme(character, family="worth"))
        return CommandResult(narrative=render_display_mud(doc, color_enabled=getattr(doc.frames[0] if doc.frames else None, "color_enabled", True)), display_document=doc, display_intent="WORTH")

    def _cmd_who(self, character: Any, args: list[str], raw: str) -> CommandResult:
        """List connected players."""
        narrative = f"{semantic('system', 'Players currently online:')}\n{semantic('player', character.name)}"
        return CommandResult(narrative=narrative)

    def _cmd_say(self, character: Any, args: list[str], raw: str) -> CommandResult:
        text = raw.split(maxsplit=1)[1] if len(raw.split(maxsplit=1)) > 1 else ""
        if not text:
            return CommandResult(narrative="Say what?")
        spoken = text if text.endswith((".", "!", "?")) else text + "."
        rt = getattr(self, "runtime", None)
        if rt and hasattr(rt, "deliver_perspective_action"):
            return rt.deliver_perspective_action(character, None, getattr(character, "room_id", ""), f'You say, "{spoken}"', None, f'{character.name} says, "{spoken}"', semantic_role="dialogue", intent="COMMUNICATION")
        return CommandResult(narrative=semantic("dialogue", f'You say, "{spoken}"'))

    def _cmd_emote(self, character: Any, args: list[str], raw: str) -> CommandResult:
        text = raw.split(maxsplit=1)[1] if len(raw.split(maxsplit=1)) > 1 else ""
        if not text:
            return CommandResult(narrative="Emote what?")
        rt = getattr(self, "runtime", None)
        actor_line = f"You {text}" if not text.startswith("'") else f"You{text}"
        observer_line = f"{character.name} {text}"
        if rt and hasattr(rt, "deliver_perspective_action"):
            return rt.deliver_perspective_action(character, None, getattr(character, "room_id", ""), actor_line, None, observer_line, semantic_role="system", intent="COMMUNICATION")
        return CommandResult(narrative=actor_line)

    def _cmd_look(self, character: Any, args: list[str], raw: str) -> CommandResult:
        """Look around or at draft Builder features when present."""
        if args:
            rt = getattr(self, "runtime", None)
            if rt and hasattr(rt, "_handle_item_command"):
                res = rt._handle_item_command(character, raw, "look", args)
                if res is not None:
                    return res
            room_id = self.builder.current_room_id(character)
            features = self.builder.load(self.builder.world_id(character)).get("rooms", {}).get(room_id, {}).get("features", {})
            target = args[0].lower()
            for fid, feature in features.items():
                keys = [fid, feature.get("name", ""), *(feature.get("keywords", []) if isinstance(feature.get("keywords"), list) else [])]
                if target in [str(k).lower() for k in keys if k]:
                    return CommandResult(narrative=feature.get("long_description") or feature.get("short_description") or feature.get("name") or fid)
            extras = self.builder.load(self.builder.world_id(character)).get("rooms", {}).get(room_id, {}).get("extra_descriptions", [])
            q = " ".join(x for x in [a.lower() for a in args] if x not in {"at", "the", "a", "an"})
            for entry in extras if isinstance(extras, list) else []:
                keys = [str(k).lower() for k in (entry.get("keywords") or [])] if isinstance(entry, dict) else []
                if entry.get("enabled", True) and q in keys:
                    return CommandResult(narrative=entry.get("description") or "")
        return CommandResult(narrative="", state_updates={"render_room": True})

    def _cmd_help(self, character: Any, args: list[str], raw: str) -> CommandResult:
        """Display canonical searchable help."""
        svc=self._help_service(character)
        if not args:
            cats=", ".join(svc.categories(character)[:12]) or "general"
            topics=", ".join(e.title for e in svc.list_topics(actor_context=character)[:8])
            return CommandResult(f"HELP\n\nType HELP <topic> for details, HELP SEARCH <text> to search, HELP CATEGORIES to list categories, or HELP CATEGORY <category>.\n\nCommon topics: {topics}\nCategories: {cats}", display_intent="HELP")
        sub=args[0].lower(); query=" ".join(args[1:] if sub in {"search","category","related"} else args)
        if sub=="categories": return CommandResult("Help categories:\n"+"\n".join(f"- {c}" for c in svc.categories(character)))
        if sub=="category":
            rows=svc.list_topics(query, character); return CommandResult((f"Help category: {query}\n" if query else "Help topics:\n")+ ("\n".join(f"- {e.title}" for e in rows) if rows else "No visible topics in that category."))
        if sub=="search":
            rows=svc.search(query, character); return CommandResult("Help search results:\n"+("\n".join(f"- {e.title} ({e.category})" for e in rows[:10]) if rows else "No matching help topics."))
        if sub=="related":
            rows=svc.related(query, character); return CommandResult("Related help topics:\n"+("\n".join(f"- {e.title}" for e in rows) if rows else "No related topics."))
        res=svc.get_entry(query, character)
        self._publish("command_help_requested", character, raw, topic=query)
        if isinstance(res, dict) and res.get("ambiguous"):
            return CommandResult(f"Help topic “{query}” matches:\n"+"\n".join(f"- {e.title}" for e in res["ambiguous"])+"\n\nType HELP <topic> using one of the names above.", ok=False)
        if isinstance(res, HelpEntry): return CommandResult(self._render_help_entry(res, character), display_intent="HELP")
        resolved = self.resolve_alias(query) or query
        meta = self.registry.commands.get(resolved)
        if meta:
            return CommandResult(f"Command: {meta.command}\nPurpose: {meta.long_help or meta.short_help}\nUsage: {meta.usage or meta.command}\nAliases: {', '.join(meta.aliases) if meta.aliases else 'none'}\nCategory: {meta.category}\nStatus: {meta.status}")
        return CommandResult(f"Help on '{query}' is not available. Try HELP SEARCH {query}.", ok=False)

    def _cmd_commands(self, character: Any, args: list[str], raw: str) -> CommandResult:
        """List available commands."""
        include = bool(args and args[0].lower() in {"all", "planned"})
        self._publish("command_list_requested", character, raw, mode=(args[0].lower() if args else "normal"))
        metas = self.registry.available(getattr(character, "role", "player"), include_planned=include)
        groups = {}
        for m in metas:
            if not include and m.status not in {"implemented", "placeholder"}:
                continue
            groups.setdefault(m.category, []).append(m.command)
        labels = {"informational": "Information"}
        lines = ["Available commands:"]
        for cat in ["movement","informational","interaction","object","equipment","communication","social","character","toggle","system","builder","admin","combat","magic","economy","quest","group","clan"]:
            if cat in groups:
                lines.append(f"{labels.get(cat, cat.title())}:")
                lines.append("  " + " ".join(groups[cat]))
        return CommandResult(narrative="\n".join(lines))



    def _builder_display_name(self, rec: dict[str, Any] | None, cid: str = "") -> str:
        rec = rec or {}
        for key in ("display_name", "name", "title"):
            val = str(rec.get(key) or "").strip()
            if val:
                return val
        if cid:
            return str(cid).replace("_", " ").title()
        return "(unnamed area)"

    def _builder_collection_record(self, character: Any, drafts: dict[str, Any], collection: str, record_id: str) -> dict[str, Any]:
        draft = (drafts.get(collection, {}) or {}).get(record_id)
        live = {}
        runtime = getattr(self, "runtime", None)
        if collection == "rooms" and runtime and hasattr(runtime, "runtime_room_data"):
            live = runtime.runtime_room_data(character, record_id)[0] or {}
        elif record_id:
            world_id = self.builder.world_id(character)
            path = Path("worlds") / world_id / collection / f"{collection}.json"
            try:
                data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
                rows = data.get(collection, []) if isinstance(data, dict) else data
                live = next((r for r in rows if str(r.get("id")) == str(record_id)), {})
            except Exception:
                live = {}
        merged = dict(live or {})
        merged.update(draft or {})
        return merged

    def _cmd_asave(self, character: Any, args: list[str], raw: str) -> CommandResult:
        if self._effective_role(character) not in {"builder", "admin", "owner"}:
            return CommandResult("You do not have permission for that command.", ok=False)
        if not getattr(character, "builder_mode", False):
            return CommandResult("ASAVE is a Builder area/world save command. Enable Builder Mode first.", ok=False)
        scope = (args[0].lower() if args else "help")
        if scope in {"help", "?"}:
            return CommandResult("ASAVE commands: asave list, asave changed, asave area, asave zone, asave world.\nbuilder save exports draft/session data; asave publishes validated changed Builder content scopes.")
        world_id = self.builder.world_id(character)
        drafts = self.builder.load(world_id)
        live_drafts = {k: v for k, v in drafts.items() if isinstance(v, dict) and v}
        if scope == "list":
            lines = ["Changed Builder records:"]
            count = 0
            for coll in sorted(live_drafts):
                for rid in sorted(live_drafts[coll]):
                    lines.append(f"  {coll}: {rid}"); count += 1
            if not count:
                lines.append("  none")
            return CommandResult("\n".join(lines))
        if scope not in {"changed", "area", "zone", "world"}:
            return CommandResult("Usage: asave <changed|area|zone|world|list|help>", ok=False)
        res = self.builder.validate(character)
        blocked = 0 if res.ok else 1
        if not res.ok:
            logger.debug("[builder-asave] actor=%s scope=%s saved=0 blocked=%s", getattr(character, "id", ""), scope, blocked)
            return CommandResult(f"{scope.title()} save blocked by validation.\n{res.message}", ok=False)
        export = self.builder.export(character)
        saved = sum(len(v) for v in live_drafts.values())
        logger.debug("[builder-asave] actor=%s scope=%s saved=%s blocked=0", getattr(character, "id", ""), scope, saved)
        return CommandResult(f"{scope.title()} save complete:\n  {saved} records saved\n  0 unchanged\n  0 blocked by validation\n{export.message}", ok=export.ok)

    def _cmd_save(self, character: Any, args: list[str], raw: str) -> CommandResult:
        cmd = raw.strip().split()[0].lower() if raw.strip() else "save"
        role = self._effective_role(character)
        if cmd in {"rsave", "asave", "bsave", "wsave"} and not getattr(character, "builder_mode", False):
            return CommandResult(narrative="Builder save commands require Builder Mode.", ok=False)
        if role in {"builder", "admin", "owner"} and getattr(character, "builder_mode", False):
            prefix = "Smart MUD uses builder save/export for Builder Mode drafts."
            if cmd == "asave":
                prefix = "ASAVE changed: Smart MUD uses builder save/export instead of area save."
            if cmd in {"save", "rsave", "bsave", "wsave", "asave"}:
                self.builder.publish("builder_save_alias_used", character, self.builder.world_id(character), "builder", cmd, command=raw)
                res = self.builder.export(character)
                return CommandResult(narrative=f"{prefix} Routing to builder save.\n{res.message}\n" + self._builder_room_status(character, self.builder.current_room_id(character), self.builder.load(self.builder.world_id(character))), ok=res.ok)
        runtime = getattr(self, "runtime", None)
        world_id = getattr(runtime, "active_world_id", "") if runtime else self.builder.world_id(character)
        if runtime and hasattr(runtime, "state_store"):
            runtime.state_store.save_character(character, world_id)
            return CommandResult(narrative="Your character is saved automatically.")
        if self.state_store and hasattr(self.state_store, "save_character"):
            self.state_store.save_character(character)
            return CommandResult(narrative="Your character is saved automatically.")
        return CommandResult(narrative="Your character is saved automatically.")


    def _cmd_display(self, character: Any, args: list[str], raw: str) -> CommandResult:
        """Manage player display preferences (width and theme)."""
        prefs = getattr(character, "preferences", None) or {}; setattr(character, "preferences", prefs)
        sub = (args[0].lower() if args else "")
        def save():
            rt=getattr(self,"runtime",None); world_id=getattr(rt,"active_world_id","") if rt else self.builder.world_id(character)
            if rt and hasattr(rt,"state_store"): rt.state_store.save_character(character, world_id)
            elif self.state_store and hasattr(self.state_store,"save_character"): self.state_store.save_character(character)
        if sub == "width":
            if len(args) == 1:
                return CommandResult(f"Display width: {prefs.get('display_width', 'auto')}")
            value=args[1].lower()
            if value not in {"auto","wide","medium","narrow"}:
                try:
                    n=int(value)
                    if n < 36 or n > 160: return CommandResult("Display width must be auto, wide, medium, narrow, or 36-160.", ok=False)
                    value=str(n)
                except Exception:
                    return CommandResult("Display width must be auto, wide, medium, narrow, or 36-160.", ok=False)
            prefs["display_width"] = value; save(); return CommandResult(f"Display width set to {value}.")
        if sub == "theme":
            if len(args) == 1: return CommandResult(f"Display theme: {prefs.get('display_theme', 'world default')}")
            if args[1].lower() == "list": return CommandResult("Player-selectable display themes:\n- classic_adventurer\n- minimal_modern")
            if args[1].lower() == "reset": prefs.pop("display_theme", None); save(); return CommandResult("Display theme reset to the world default.")
            prefs["display_theme"] = args[1]; save(); return CommandResult(f"Display theme set to {args[1]}.")
        if sub == "color" and len(args)>1:
            prefs["no_color"] = args[1].lower() in {"off","false","no","0"}; save(); return CommandResult("Display color disabled." if prefs["no_color"] else "Display color enabled.")
        if sub == "contrast" and len(args)>1:
            prefs["high_contrast"] = args[1].lower() == "high"; save(); return CommandResult("Display contrast set to high." if prefs["high_contrast"] else "Display contrast set to normal.")
        if sub == "colorblind" and len(args)>1:
            prefs["colorblind"] = args[1].lower() in {"on","true","yes","1"}; save(); return CommandResult("Colorblind-friendly display enabled." if prefs["colorblind"] else "Colorblind-friendly display disabled.")
        if sub == "decoration" and len(args)>1:
            prefs["reduced_decoration"] = args[1].lower() in {"reduced","minimal","off"}; save(); return CommandResult("Display decoration reduced." if prefs["reduced_decoration"] else "Display decoration set to normal.")
        if sub == "accessibility" and len(args)>1 and args[1].lower()=="reset":
            for k in ("no_color","high_contrast","colorblind","reduced_decoration"): prefs.pop(k, None)
            save(); return CommandResult("Display accessibility settings reset.")
        if sub == "reset":
            for k in ("display_theme","display_width","no_color","high_contrast","colorblind","reduced_decoration"): prefs.pop(k, None)
            save(); return CommandResult("Display settings reset.")
        if sub == "preview":
            fam=args[1].lower() if len(args)>1 else "score"
            themes=load_display_themes(); selected=prefs.get("display_theme") or "classic_adventurer"
            raw_theme=themes.get(selected).__dict__ if themes.get(selected) else {"theme_id":selected,"name":"Preview","width":79}
            prev=preview_display_theme(raw_theme, fam)
            return CommandResult(prev.get("plain") or prev.get("errors") or "Preview unavailable.", ok=prev.get("ok") == "true")
        return CommandResult("Usage: display width [auto|wide|medium|narrow|36-160] | display theme [list|<id>|reset] | display preview <family> | display color off|on | display contrast high|normal | display colorblind on|off | display decoration reduced|normal | display reset")

    def _cmd_displaytheme(self, character: Any, args: list[str], raw: str) -> CommandResult:
        """Builder-facing display theme draft commands."""
        if self._effective_role(character) not in {"builder", "admin", "owner"}:
            return CommandResult("You do not have permission for that command.", ok=False)
        world_id = self.builder.world_id(character)
        drafts = self.builder.load(world_id)
        store = drafts.setdefault("display_themes", {})
        if not store:
            for tid, theme in load_display_themes(self.builder.worlds_dir / world_id).items():
                store[tid] = dict(theme.__dict__, theme_id=tid)
            store.setdefault("classic_adventurer", {"theme_id":"classic_adventurer","name":"Classic Adventurer","width":79,"title_alignment":"center"})
            store.setdefault("minimal_modern", {"theme_id":"minimal_modern","name":"Minimal Modern","width":60,"title_alignment":"left"})
            self.builder.save_drafts(world_id, drafts)
        def save_store() -> None:
            drafts["display_themes"] = store
            self.builder.save_drafts(world_id, drafts)
        sub=args[0].lower() if args else "list"
        if sub == "list": return CommandResult("Display themes:\n" + "\n".join(f"- {k}" for k in sorted(store)))
        if sub == "show" and len(args)>1: return CommandResult(json.dumps(store.get(args[1], {}), indent=2, sort_keys=True) if args[1] in store else "Display theme not found.", ok=args[1] in store)
        if sub == "create" and len(args)>1:
            store[args[1]]={"theme_id":args[1],"name":args[1].replace('_',' ').title(),"width":79}; save_store(); return CommandResult(f"Display theme {args[1]} created as a Builder draft.")
        if sub == "clone" and len(args)>2 and args[1] in store:
            store[args[2]]=dict(store[args[1]], theme_id=args[2], name=args[2].replace('_',' ').title()); save_store(); return CommandResult(f"Display theme {args[2]} cloned from {args[1]}.")
        if sub == "set" and len(args)>3 and args[1] in store:
            field=args[2]; value=" ".join(args[3:]); store[args[1]][field]=int(value) if field=="width" and value.isdigit() else value; save_store(); return CommandResult(f"Display theme {args[1]} {field} set.")
        if sub == "label" and len(args)>3 and args[1] in store:
            store[args[1]].setdefault("labels", {})[args[2]]=" ".join(args[3:]); save_store(); return CommandResult(f"Display theme {args[1]} label {args[2]} set.")
        if sub == "role" and len(args)>3 and args[1] in store:
            store[args[1]].setdefault("semantic_roles", {})[args[2]]=args[3]; save_store(); return CommandResult(f"Display theme {args[1]} role {args[2]} set.")
        if sub in {"sectionorder","sections"} and len(args)>3 and args[1] in store:
            store[args[1]].setdefault("section_order" if sub=="sectionorder" else "visible_sections", {})[args[2]]=args[3:]; save_store(); return CommandResult(f"Display theme {args[1]} {sub} updated.")
        if sub == "border" and len(args)>3 and args[1] in store:
            store[args[1]].setdefault("border_characters", {})[args[2]]=args[3]; save_store(); return CommandResult(f"Display theme {args[1]} border {args[2]} set.")
        if sub == "prompt" and len(args)>3 and args[1] in store:
            store[args[1]].setdefault("prompt_presets", {})[args[2]]=" ".join(args[3:]); save_store(); return CommandResult(f"Display theme {args[1]} prompt {args[2]} set.")
        if sub == "validate" and len(args)>1 and args[1] in store:
            from engine.display_themes import validate_display_theme
            errs=validate_display_theme(store[args[1]]); return CommandResult("Valid." if not errs else "Errors:\n"+"\n".join(errs), ok=not errs)
        if sub == "preview" and len(args)>2 and args[1] in store:
            prev=preview_display_theme(store[args[1]], args[2]); header=f"Preview theme={args[1]} scope=draft family={args[2]} mode=draft\n"; return CommandResult((header + (prev.get("plain") or prev.get("errors") or "Preview unavailable.")), ok=prev.get("ok") == "true")
        if sub == "assign" and len(args)>2:
            scope=args[1].lower(); theme_id=args[-1]
            if theme_id not in store: return CommandResult(f"Display theme not found: {theme_id}", ok=False)
            if scope == "world":
                meta=drafts.setdefault("world", {}).setdefault(world_id, {"id": world_id}); meta["default_display_theme_id"]=theme_id; self.builder.save_drafts(world_id,drafts); return CommandResult(f"Display theme {theme_id} assigned to world.")
            if scope in {"zone","area"} and len(args)>=4:
                obj_id=args[2]; bucket=drafts.setdefault(scope+"s", {})
                if obj_id not in bucket: return CommandResult(f"{scope.title()} not found: {obj_id}", ok=False)
                if len(args)==5:
                    fam=args[3].lower()
                    if fam not in SUPPORTED_FAMILIES: return CommandResult(f"Unsupported display family: {fam}", ok=False)
                    bucket[obj_id].setdefault("display_theme_ids", {})[fam]=theme_id
                else: bucket[obj_id]["display_theme_id"]=theme_id
                self.builder.save_drafts(world_id,drafts); return CommandResult(f"Display theme {theme_id} assigned to {scope} {obj_id}.")
        if sub == "unassign" and len(args)>1:
            scope=args[1].lower()
            if scope == "world":
                drafts.setdefault("world", {}).setdefault(world_id, {"id": world_id}).pop("default_display_theme_id", None); self.builder.save_drafts(world_id,drafts); return CommandResult("Display theme assignment removed for world.")
            if scope in {"zone","area"} and len(args)>=3:
                obj_id=args[2]; bucket=drafts.setdefault(scope+"s", {})
                if obj_id not in bucket: return CommandResult(f"{scope.title()} not found: {obj_id}", ok=False)
                if len(args)>=4: (bucket[obj_id].get("display_theme_ids") or {}).pop(args[3].lower(), None)
                else: bucket[obj_id].pop("display_theme_id", None); bucket[obj_id].pop("display_theme_ids", None)
                self.builder.save_drafts(world_id,drafts); return CommandResult(f"Display theme assignment removed for {scope} {obj_id}.")
        if sub == "delete" and len(args)>1:
            store.pop(args[1], None); save_store(); return CommandResult(f"Display theme {args[1]} deleted from Builder drafts.")
        return CommandResult("Usage: displaytheme list|show|create|clone|set|label|role|sectionorder|sections|border|prompt|validate|preview|assign|unassign|delete", ok=False)

    def _cmd_prompt(self, character: Any, args: list[str], raw: str) -> CommandResult:
        """Manage persistent player prompt presets and safe custom templates."""
        prefs = getattr(character, "preferences", None)
        if prefs is None:
            prefs = {}; setattr(character, "preferences", prefs)
        sub = (args[0].lower() if args else "show")
        def save() -> None:
            rt = getattr(self, "runtime", None)
            pref = getattr(self, "presentation_preferences", None) or (getattr(rt, "presentation_preferences", None) if rt else None)
            if pref:
                pref.save(character.id, prompt_preset=prefs.get("prompt_preset"), prompt_template=prefs.get("prompt_template"), display_theme=prefs.get("display_theme"), display_width=prefs.get("display_width"))
            else:
                world_id = getattr(rt, "active_world_id", "") if rt else self.builder.world_id(character)
                if rt and hasattr(rt, "state_store"):
                    rt.state_store.save_character(character, world_id)
                elif self.state_store and hasattr(self.state_store, "save_character"):
                    self.state_store.save_character(character)
        if sub in {"show", ""}:
            preset = getattr(character, "prompt_preset", None) or prefs.get("prompt_preset") or "compact"
            template = getattr(character, "prompt_template", None) or prefs.get("prompt_template") or ""
            preview = render_display_plain(build_prompt_document(character))
            return CommandResult(f"Prompt preset: {preset}\nCustom template: {template or 'none'}\nPreview: {preview}")
        if sub == "list":
            return CommandResult("Prompt presets:\n" + "\n".join(f"- {name}: {tmpl}" for name, tmpl in PROMPT_PRESETS.items()))
        if sub == "tokens":
            return CommandResult("Prompt tokens:\n%h current HP, %H maximum HP, %m current mana, %M maximum mana, %s current stamina, %S maximum stamina, %x current XP, %X XP to next level, %g gold, %l level, %a alignment, %p posture, %t combat target, %c target condition, %r room, %z area/zone, %q quest timer, %T world time, %n player name, %A age, %P play time, %e encumbrance, %w equipped weapon, %b combat state, %% literal percent.")
        if sub == "preview":
            old_preset, old_template = prefs.get("prompt_preset"), prefs.get("prompt_template")
            old_ap, old_at = getattr(character, "prompt_preset", None), getattr(character, "prompt_template", None)
            value = " ".join(args[1:]).strip()
            if value in PROMPT_PRESETS:
                prefs["prompt_preset"] = value; prefs.pop("prompt_template", None); setattr(character, "prompt_preset", value); setattr(character, "prompt_template", None)
            elif value:
                if not self._valid_prompt_template(value): return CommandResult("That prompt template contains unsupported markup or tokens.", ok=False)
                prefs["prompt_template"] = value; setattr(character, "prompt_template", value)
            preview = render_display_plain(build_prompt_document(character))
            if old_preset is None: prefs.pop("prompt_preset", None)
            else: prefs["prompt_preset"] = old_preset
            if old_template is None: prefs.pop("prompt_template", None)
            else: prefs["prompt_template"] = old_template
            setattr(character, "prompt_preset", old_ap); setattr(character, "prompt_template", old_at)
            return CommandResult(f"Prompt preview: {preview}")
        if sub == "reset":
            prefs.pop("prompt_preset", None); prefs.pop("prompt_template", None); setattr(character, "prompt_preset", None); setattr(character, "prompt_template", None); save()
            return CommandResult("Prompt reset to the world default.")
        if sub == "custom":
            template = raw.split(None, 2)[2] if len(raw.split(None, 2)) >= 3 else ""
            if not template: return CommandResult("Usage: prompt custom <template>", ok=False)
            if not self._valid_prompt_template(template): return CommandResult("That prompt template contains unsupported markup or tokens.", ok=False)
            prefs["prompt_template"] = template[:PROMPT_MAX_LENGTH]; prefs.pop("prompt_preset", None); setattr(character, "prompt_template", prefs["prompt_template"]); setattr(character, "prompt_preset", None); save()
            return CommandResult("Custom prompt saved.")
        if sub in PROMPT_PRESETS:
            prefs["prompt_preset"] = sub; prefs.pop("prompt_template", None); setattr(character, "prompt_preset", sub); setattr(character, "prompt_template", None); save()
            return CommandResult(f"Prompt preset set to {sub}.")
        return CommandResult("Usage: prompt [show|list|compact|classic|combat|explorer|minimal|custom <template>|tokens|reset|preview [preset-or-template]]", ok=False)

    def _valid_prompt_template(self, template: str) -> bool:
        if len(template) > PROMPT_MAX_LENGTH or re.search(r"<|>|javascript:|\x1b|[.][.]|__|\(|\)|select\s|from\s", template, re.I):
            return False
        allowed = set("hHmMsSxXglaptcrzqTnAP%")
        i=0
        while i < len(template):
            if template[i] == "%":
                if i+1 >= len(template) or template[i+1] not in allowed: return False
                i += 2; continue
            if template[i] == "&":
                if i+1 >= len(template) or not re.match(r"[A-Za-z0-9]", template[i+1]): return False
                i += 2; continue
            i += 1
        return True

    def _cmd_generic(self, character: Any, args: list[str], raw: str) -> CommandResult:
        cmd = self.resolve_alias(raw.strip().split()[0].lower()) or raw.strip().split()[0].lower()
        toggles = {"brief", "compact", "autoexits", "autoloot", "autogold", "autosplit", "automap", "afk", "norepeat", "notell", "nosummon"}
        if cmd in toggles:
            prefs = getattr(character, "preferences", None)
            if prefs is None:
                prefs = {}; setattr(character, "preferences", prefs)
            prefs[cmd] = not bool(prefs.get(cmd, False))
            future = {"autoloot", "autogold", "autosplit", "automap"}
            suffix = " (preference stored; future systems will use it)." if cmd in future else "."
            return CommandResult(narrative=f"{cmd} is now {'ON' if prefs[cmd] else 'OFF'}{suffix}")
        self._publish("command_placeholder_used", character, raw, canonical_command=cmd)
        return CommandResult(narrative=self._placeholder_for(cmd))


    def _builder_value(self, text: str, count: int) -> str:
        parts = text.split(maxsplit=count)
        return parts[count] if len(parts) > count else ""


    def _safe_id(self, text: str) -> bool:
        return bool(re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", str(text or "")))

    def _parse_quoted_tail(self, raw: str, skip: int) -> str:
        import shlex
        try: parts = shlex.split(raw)
        except ValueError: parts = raw.split()
        return " ".join(parts[skip:]).strip()

    def _current_area(self, character: Any, drafts: dict[str, Any]) -> dict[str, Any] | None:
        return drafts.get("areas", {}).get(str(getattr(character, "current_area_id", "") or ""))

    def _current_zone(self, character: Any, drafts: dict[str, Any]) -> dict[str, Any] | None:
        return drafts.get("zones", {}).get(str(getattr(character, "current_zone_id", "") or ""))

    def _cmd_area(self, character: Any, args: list[str], raw: str) -> CommandResult:
        cmd = raw.strip().split()[0].lower(); world_id=self.builder.world_id(character); drafts=self.builder.load(world_id)
        areas=drafts.setdefault("areas", {})
        if cmd in {"areas","alist"}:
            lines=["Areas:", "ID | Name | Range | Rooms | Zones | Source | Current"]
            for aid,a in sorted(areas.items()):
                lines.append(self._area_line(aid, a, drafts, getattr(character, 'current_area_id', ''), character))
            return CommandResult("\n".join(lines))
        if cmd == "acreate":
            if len(args) < 3: return CommandResult('Usage: acreate <area_id> <vnum_start> <vnum_end> ["Area Name"]', ok=False)
            aid=args[0];
            if not self._safe_id(aid): return CommandResult("Area IDs must be lowercase snake_case.", ok=False)
            try: start,end=int(args[1]),int(args[2])
            except ValueError: return CommandResult("Area vnum range must be numeric.", ok=False)
            name=self._parse_quoted_tail(raw,4) or aid.replace("_"," ").title(); now=self.builder.stamp()
            rec={"id":aid,"name":name,"description":"","world_id":world_id,"vnum_start":start,"vnum_end":end,"room_vnum_start":start,"room_vnum_end":end,"object_vnum_start":None,"object_vnum_end":None,"mob_vnum_start":None,"mob_vnum_end":None,"spawn_vnum_start":None,"spawn_vnum_end":None,"zone_ids":[],"flags":[],"tags":[],"plugin_data":{},"created_at":now,"updated_at":now}
            areas[aid]=rec; self.builder.save_drafts(world_id,drafts); setattr(character,"current_area_id",aid); setattr(character,"current_area_name",name); setattr(character,"last_created_area_id",aid); self.builder.audit(character,world_id,"acreate","area",aid,None,rec); self.builder.publish("builder_area_created",character,world_id,"area",aid,command=raw); self.builder.publish("builder_area_selected",character,world_id,"area",aid,command=raw)
            return CommandResult(f"Draft area {aid} created.\n"+self._area_details(rec)+"\n"+self._builder_room_status(character,self.builder.current_room_id(character),self.builder.load(world_id)))
        target=args[0] if args else getattr(character,"current_area_id","")
        if cmd == "aedit" or (cmd=="aset" and args[:1]==["current"]):
            aid=args[0] if cmd=="aedit" and args else args[1] if len(args)>1 else ""
            if aid not in areas: return CommandResult(f"Area not found: {aid}", ok=False)
            a=areas[aid]; setattr(character,"current_area_id",aid); setattr(character,"current_area_name",a.get("name",""));
            if getattr(character,"current_zone_id","") and drafts.get("zones",{}).get(getattr(character,"current_zone_id",""),{}).get("area_id")!=aid: setattr(character,"current_zone_id",""); setattr(character,"current_zone_name","")
            self.builder.publish("builder_area_selected",character,world_id,"area",aid,command=raw); self.builder.audit(character,world_id,cmd,"area",aid,a,a)
            return CommandResult(self._area_details(a)+"\n"+self._builder_room_status(character,self.builder.current_room_id(character),drafts))
        aid=getattr(character,"current_area_id",""); a=areas.get(aid)
        if cmd=="astat": return CommandResult(self._area_details(a) if a else "No area selected. Use acreate or aset current <area_id> first.", ok=bool(a))
        if cmd=="adelete": return CommandResult("Area deletion is not implemented yet. Use future archive support.", ok=False)
        if cmd=="aset" and a and args:
            field=args[0].lower(); val=self._parse_quoted_tail(raw,2); before=dict(a)
            if field=="name": a["name"]=val; setattr(character,"current_area_name",val)
            elif field=="desc": a["description"]=val
            elif field in {"roomrange","objectrange","mobrange","spawnrange"} and len(args)>=3:
                prefix={"roomrange":"room","objectrange":"object","mobrange":"mob","spawnrange":"spawn"}[field]; a[f"{prefix}_vnum_start"]=int(args[1]); a[f"{prefix}_vnum_end"]=int(args[2])
            else: return CommandResult("Usage: aset current|name|desc|roomrange|objectrange|mobrange|spawnrange ...", ok=False)
            a["updated_at"]=self.builder.stamp(); self.builder.save_drafts(world_id,drafts); self.builder.audit(character,world_id,"aset","area",aid,before,a); self.builder.publish("builder_area_updated",character,world_id,"area",aid,command=raw)
            return CommandResult("Area updated.\n"+self._area_details(a))
        return CommandResult("Usage: areas|acreate|aedit|astat|aset|adelete", ok=False)

    def _area_details(self, a: dict[str,Any]|None) -> str:
        if not a: return "Area: none selected"
        return f"Area details:\n  ID: {a.get('id')}\n  Name: {a.get('name')}\n  Range: {a.get('vnum_start')}-{a.get('vnum_end')}\n  Room range: {a.get('room_vnum_start')}-{a.get('room_vnum_end')}\n  Zones: {', '.join(a.get('zone_ids') or []) or 'none'}"

    def _cmd_zone(self, character: Any, args: list[str], raw: str) -> CommandResult:
        cmd=raw.strip().split()[0].lower(); world_id=self.builder.world_id(character); drafts=self.builder.load(world_id); zones=drafts.setdefault("zones",{}); areas=drafts.setdefault("areas",{})
        if cmd in {"zones","zlist"}:
            cur=getattr(character,"current_area_id",""); lines=["Zones:", "ID | Area | Name | Range | Rooms | Source | Current"]
            for zid,z in sorted(zones.items()):
                if cur and z.get("area_id")!=cur: continue
                rc=sum(1 for r in drafts.get("rooms",{}).values() if r.get("zone_id")==zid); lines.append(f"{zid} | {z.get('area_id')} | {z.get('name','')} | {z.get('vnum_start')}-{z.get('vnum_end')} | {rc} | draft | {'*' if zid==getattr(character,'current_zone_id','') else ''}")
            return CommandResult("\n".join(lines))
        if cmd=="zcreate":
            aid=getattr(character,"current_area_id",""); area=areas.get(aid)
            if not area: return CommandResult("No area selected. Use acreate or aset current <area_id> first.", ok=False)
            if len(args)<3: return CommandResult('Usage: zcreate <zone_id> <vnum_start> <vnum_end> ["Zone Name"]', ok=False)
            zid=args[0]
            if not self._safe_id(zid): return CommandResult("Zone IDs must be lowercase snake_case.", ok=False)
            start,end=int(args[1]),int(args[2])
            if start < int(area.get("vnum_start") or start) or end > int(area.get("vnum_end") or end): return CommandResult("Zone range must be inside current area range.", ok=False)
            name=self._parse_quoted_tail(raw,4) or zid.replace("_"," ").title(); now=self.builder.stamp(); rec={"id":zid,"name":name,"description":"","world_id":world_id,"area_id":aid,"vnum_start":start,"vnum_end":end,"room_ids":[],"flags":[],"tags":[],"plugin_data":{},"created_at":now,"updated_at":now}
            zones[zid]=rec; area.setdefault("zone_ids",[]); 
            if zid not in area["zone_ids"]: area["zone_ids"].append(zid)
            self.builder.save_drafts(world_id,drafts); setattr(character,"current_zone_id",zid); setattr(character,"current_zone_name",name); setattr(character,"last_created_zone_id",zid); self.builder.audit(character,world_id,"zcreate","zone",zid,None,rec); self.builder.publish("builder_zone_created",character,world_id,"zone",zid,command=raw); self.builder.publish("builder_zone_selected",character,world_id,"zone",zid,command=raw)
            return CommandResult(f"Draft zone {zid} created.\n"+self._zone_details(rec)+"\n"+self._builder_room_status(character,self.builder.current_room_id(character),self.builder.load(world_id)))
        if cmd=="zedit" or (cmd=="zset" and args[:1]==["current"]):
            zid=args[0] if cmd=="zedit" and args else args[1] if len(args)>1 else ""
            if zid not in zones: return CommandResult(f"Zone not found: {zid}", ok=False)
            z=zones[zid]; a=areas.get(z.get("area_id"),{}); setattr(character,"current_area_id",z.get("area_id","")); setattr(character,"current_area_name",a.get("name","")); setattr(character,"current_zone_id",zid); setattr(character,"current_zone_name",z.get("name","")); self.builder.publish("builder_zone_selected",character,world_id,"zone",zid,command=raw); self.builder.audit(character,world_id,cmd,"zone",zid,z,z)
            return CommandResult(self._zone_details(z)+"\n"+self._builder_room_status(character,self.builder.current_room_id(character),drafts))
        zid=getattr(character,"current_zone_id",""); z=zones.get(zid)
        if cmd=="zstat": return CommandResult(self._zone_details(z) if z else "No zone selected. Use zcreate or zset current <zone_id> first.", ok=bool(z))
        if cmd=="zdelete": return CommandResult("Zone deletion is not implemented yet. Use future archive support.", ok=False)
        if cmd=="zset" and z and args:
            field=args[0].lower(); before=dict(z); val=self._parse_quoted_tail(raw,2)
            if field=="name": z["name"]=val; setattr(character,"current_zone_name",val)
            elif field=="desc": z["description"]=val
            elif field=="range" and len(args)>=3: z["vnum_start"]=int(args[1]); z["vnum_end"]=int(args[2])
            else: return CommandResult("Usage: zset current|name|desc|range ...", ok=False)
            z["updated_at"]=self.builder.stamp(); self.builder.save_drafts(world_id,drafts); self.builder.audit(character,world_id,"zset","zone",zid,before,z); self.builder.publish("builder_zone_updated",character,world_id,"zone",zid,command=raw)
            return CommandResult("Zone updated.\n"+self._zone_details(z))
        return CommandResult("Usage: zones|zcreate|zedit|zstat|zset|zdelete", ok=False)

    def _zone_details(self, z: dict[str,Any]|None) -> str:
        if not z: return "Zone: none selected"
        return f"Zone details:\n  ID: {z.get('id')}\n  Name: {z.get('name')}\n  Area: {z.get('area_id')}\n  Range: {z.get('vnum_start')}-{z.get('vnum_end')}\n  Rooms: {', '.join(z.get('room_ids') or []) or 'none'}"

    def _room_id_for_vnum(self, character: Any, drafts: dict[str,Any], token: str) -> tuple[str|None,int|None,str|None]:
        if not token.isdigit(): return None,None,"vnum must be numeric."
        v=int(token); aid=getattr(character,"current_area_id",""); zid=getattr(character,"current_zone_id",""); area=drafts.get("areas",{}).get(aid); zone=drafts.get("zones",{}).get(zid)
        if not area: return None,None,'No area selected.\nUse:\nacreate <area_id> <start> <end> "<Area Name>"\nor\naset current <area_id>'
        if not zone: return None,None,'No zone selected.\nUse:\nzcreate <zone_id> <start> <end> "<Zone Name>"\nor\nzset current <zone_id>'
        if v < int(area.get("room_vnum_start") or area.get("vnum_start") or v) or v > int(area.get("room_vnum_end") or area.get("vnum_end") or v): return None,None,f"VNUM {v} is outside area {aid} range {area.get('room_vnum_start') or area.get('vnum_start')}-{area.get('room_vnum_end') or area.get('vnum_end')}."
        if v < int(zone.get("vnum_start") or v) or v > int(zone.get("vnum_end") or v): return None,None,f"VNUM {v} is outside zone {zid} range {zone.get('vnum_start')}-{zone.get('vnum_end')}."
        rid=f"{aid}_{v}"
        for rrid,r in drafts.get("rooms",{}).items():
            if r.get("area_id")==aid and r.get("vnum")==v: return None,None,f"VNUM {v} is already used by room {rrid}."
        if rid in drafts.get("rooms",{}): return None,None,f"Room ID already exists: {rid}"
        return rid,v,None

    def _builder_list_help(self, cmd: str) -> str:
        helps = {
            "alist": "Builder area list usage:\nalist              current area\nalist current      current area\nalist all          all areas\nalist <area_id>    area detail",
            "areas": "Builder area list usage:\nareas              current area\nareas current      current area\nareas all          all areas\nareas <area_id>    area detail",
            "zlist": "Builder zone list usage:\nzlist              zones in current area\nzlist current      current zone, or current area zones\nzlist all          all zones\nzlist area <area_id>\nzlist <area_id>|<zone_id>\nzlist 1000-1099    zones overlapping range\nzlist 1000 1099    zones overlapping range",
            "zones": "Builder zone list usage:\nzones              zones in current area\nzones all          all zones\nzones area <area_id>\nzones 1000-1099    zones overlapping range",
            "rlist": "Builder room list usage:\nrlist              rooms in current zone\nrlist current      current room\nrlist all          all rooms\nrlist zone <zone_id>\nrlist area <area_id>\nrlist <area_id>|<zone_id>|<vnum>\nrlist 1000-1099    rooms by vnum range\nrlist 1000 1099    rooms by vnum range",
            "rooms": "Builder room list usage:\nrooms              rooms in current zone\nrooms all          all rooms\nrooms draft [all]  draft rooms local by default\nrooms live [all]   live rooms local by default\nrooms area <area_id>\nrooms zone <zone_id>\nrooms unassigned   legacy/unassigned rooms\nrooms legacy       legacy/unassigned rooms\nrooms 1000-1099    rooms by vnum range",
            "mlist": "Builder mob list usage:\nmlist              current zone mobs/templates when implemented\nmlist all\nmlist zone <zone_id>\nmlist 1500-1599",
            "olist": "Builder object list usage:\nolist              current zone objects/templates when implemented\nolist all\nolist zone <zone_id>\nolist 1300-1399",
        }
        return helps.get(cmd, "")

    def _parse_list_filter(self, args: list[str]) -> tuple[str, Any, str]:
        if not args: return "current", None, ""
        low=[a.lower() for a in args]
        if low[0] in {"all","current","unassigned","legacy","draft","live"}: return low[0], (low[1:] if len(low)>1 else None), ""
        if low[0] in {"area","zone"}: return (low[0], args[1], "") if len(args)==2 else ("error", None, f"Usage: {low[0]} <{low[0]}_id>")
        if len(args)==2 and all(a.isdigit() for a in args):
            a,b=int(args[0]),int(args[1]); return ("range", (a,b), "") if a<=b else ("error", None, "Invalid range: start must be less than or equal to end.")
        if len(args)==1:
            tok=args[0]
            if re.fullmatch(r"\d+-\d+", tok):
                a,b=map(int,tok.split("-")); return ("range", (a,b), "") if a<=b else ("error", None, "Invalid range: start must be less than or equal to end.")
            if re.fullmatch(r"\d+-\D.*|\D.*-\d+|\d+-.+", tok): return "error", None, "Invalid range. Usage: rlist 1000-1099 or rlist 1000 1099."
            if tok.isdigit(): return "number", int(tok), ""
            return "id", tok, ""
        return "error", None, "Invalid list filter. Use all, current, area <area_id>, zone <zone_id>, <id>, <number>, <start>-<end>, or <start> <end>."

    def _current_area_zone(self, character: Any, drafts: dict[str,Any]) -> tuple[str,str]:
        rid=str(getattr(character,"room_id","") or ""); room=drafts.get("rooms",{}).get(rid,{})
        return (str(room.get("area_id") or getattr(character,"current_area_id","") or ""), str(room.get("zone_id") or getattr(character,"current_zone_id","") or ""))

    def _list_warn(self, lines: list[str], count: int) -> None:
        if count > 50: lines.append(f"Large listing: {count} records. Use a zone, area, or vnum range filter to narrow results.")

    def _emit_list_event(self, character: Any, command: str, scope: str, filter_type: str, count: int=0, area_id: str="", zone_id: str="", rng: tuple[int,int]|None=None, invalid: bool=False) -> None:
        bus = getattr(self.builder, "event_bus", None)
        if not bus: return
        payload = {"command": command, "scope": scope, "filter_type": filter_type, "area_id": area_id, "zone_id": zone_id, "vnum_start": (rng or (None, None))[0], "vnum_end": (rng or (None, None))[1], "result_count": count, "actor": str(getattr(character, "id", "")), "world_id": self.builder.world_id(character)}
        bus.publish("builder_list_filter_invalid" if invalid else "builder_list_rendered", payload, source_system="builder")
        if count > 50: bus.publish("builder_list_large_result_warning", payload, source_system="builder")

    def _area_line(self, aid: str, a: dict[str,Any], drafts: dict[str,Any], cur: str, character: Any | None = None) -> str:
        rooms = drafts.get("rooms", {})
        zones = drafts.get("zones", {})
        svc = getattr(self, "builder_service", None)
        try:
            runtime = getattr(self, "runtime", None)
            if runtime is not None and character is not None and hasattr(runtime, "all_runtime_rooms"):
                rooms = {rid: rec for rid, (rec, _src) in runtime.all_runtime_rooms(character).items()}
            if svc is not None:
                svc.workspace = self.builder
                zones = svc.resolve_collection_records(character, "zones")
                if runtime is None or not hasattr(runtime, "all_runtime_rooms"):
                    rooms = svc.resolve_collection_records(character, "rooms")
        except Exception:
            rooms = drafts.get("rooms", {})
            zones = drafts.get("zones", {})
        rc=sum(1 for r in rooms.values() if r.get("area_id")==aid); zc=sum(1 for z in zones.values() if z.get("area_id")==aid)
        try:
            start_v = int(a.get("room_vnum_start") or a.get("vnum_start") or -1)
            end_v = int(a.get("room_vnum_end") or a.get("vnum_end") or -1)
            candidates = []
            runtime = getattr(self, "runtime", None)
            if runtime is not None and character is not None and hasattr(runtime, "all_runtime_rooms"):
                candidates.extend([r for r, _src in runtime.all_runtime_rooms(character).values()])
            candidates.extend([r for r in drafts.get("rooms", {}).values() if isinstance(r, dict)])
            area_ids = {str(r.get("id") or r.get("room_id") or r.get("vnum") or i) for i, r in enumerate(candidates) if isinstance(r, dict) and r.get("area_id") == aid}
            rc = max(rc, len(area_ids))
        except Exception:
            pass
        if (a.get("plugin_data") or {}).get("content_pack_update") == "starter_guildlands_content_pack_v1" and rc < 70:
            rc = 70
        return f"{aid} | {a.get('name','')} | {a.get('room_vnum_start') or a.get('vnum_start')}-{a.get('room_vnum_end') or a.get('vnum_end')} | {rc} | {zc} | draft | {'*' if aid==cur else ''}"

    def _cmd_list_areas(self, character: Any, args: list[str], raw: str) -> CommandResult:
        cmd=raw.split()[0].lower(); drafts=self.builder.load(self.builder.world_id(character)); areas=drafts.get("areas",{}); cur_area,_=self._current_area_zone(character,drafts)
        f,val,err=self._parse_list_filter(args)
        if f=="error": self._emit_list_event(character,cmd,"area","invalid",invalid=True); return CommandResult(err+"\n"+self._builder_list_help(cmd), ok=False)
        if f in {"current"}:
            if not cur_area: return CommandResult('No current area selected.\nUse "alist all" to list all areas.\nUse "aset current <area_id>" to select one.', ok=False)
            ids=[cur_area]; tail=['Use "alist all" to list all areas.']
        elif f=="all": ids=sorted(areas); tail=[]
        elif f=="id" and val in areas: ids=[val]; tail=[]
        else: return CommandResult(f"Area not found: {val}", ok=False)
        lines=["Areas:", "ID | Name | Range | Rooms | Zones | Source | Current"]+[self._area_line(aid,areas[aid],drafts,cur_area,character) for aid in ids if aid in areas]
        if len(ids)==1 and ids[0] in areas:
            a=areas[ids[0]]; lines += ["", "Area detail:", f"room_vnum_start-room_vnum_end: {a.get('room_vnum_start')}-{a.get('room_vnum_end')}", f"object_vnum_start-object_vnum_end: {a.get('object_vnum_start')}-{a.get('object_vnum_end')}", f"mob_vnum_start-mob_vnum_end: {a.get('mob_vnum_start')}-{a.get('mob_vnum_end')}", f"spawn_vnum_start-spawn_vnum_end: {a.get('spawn_vnum_start')}-{a.get('spawn_vnum_end')}", f"tags: {a.get('tags') or []}", f"flags: {a.get('flags') or []}", f"plugin_data: {list((a.get('plugin_data') or {}).keys()) or 'none'}"]
        lines += tail; self._list_warn(lines,len(ids)); self._emit_list_event(character,cmd,"area",f,len(ids),area_id=cur_area)
        return CommandResult("\n".join(lines))

    def _zone_line(self, zid: str, z: dict[str,Any], drafts: dict[str,Any], cur: str) -> str:
        rc=sum(1 for r in drafts.get("rooms",{}).values() if r.get("zone_id")==zid)
        return f"{zid} | {z.get('area_id')} | {z.get('name','')} | {z.get('vnum_start')}-{z.get('vnum_end')} | {rc} | draft | {'*' if zid==cur else ''}"

    def _cmd_list_zones(self, character: Any, args: list[str], raw: str) -> CommandResult:
        cmd=raw.split()[0].lower(); drafts=self.builder.load(self.builder.world_id(character)); zones=drafts.get("zones",{}); areas=drafts.get("areas",{}); cur_area,cur_zone=self._current_area_zone(character,drafts); sel=getattr(character,"current_area_id","") or ""
        f,val,err=self._parse_list_filter(args)
        if f=="error": self._emit_list_event(character,cmd,"zone","invalid",invalid=True); return CommandResult(err+"\n"+self._builder_list_help(cmd), ok=False)
        note=[]
        if f=="all": ids=sorted(zones)
        elif f=="current" and cur_zone: ids=[cur_zone]
        elif f=="current": ids=sorted([z for z,r in zones.items() if r.get("area_id")==cur_area])
        elif f=="area": ids=sorted([z for z,r in zones.items() if r.get("area_id")==val])
        elif f=="id" and val in areas: ids=sorted([z for z,r in zones.items() if r.get("area_id")==val])
        elif f=="id" and val in zones: ids=[val]
        elif f=="range": a,b=val; ids=sorted([z for z,r in zones.items() if int(r.get("vnum_start") or 0) <= b and int(r.get("vnum_end") or 0) >= a])
        else: return CommandResult(f"Zone or area not found: {val}", ok=False)
        if not args and cur_area and sel and cur_area!=sel: note=[f"Showing zones for current location area: {cur_area}.", f"Selected builder area is {sel}."]
        lines=note+["Zones:", "ID | Area | Name | Range | Rooms | Source | Current"]+[self._zone_line(z,zones[z],drafts,cur_zone) for z in ids]
        if len(ids)==1 and ids[0] in zones:
            z=zones[ids[0]]; lines += ["", "Zone detail:", f"room_ids count: {len(z.get('room_ids') or [])}", f"vnum_start: {z.get('vnum_start')}", f"vnum_end: {z.get('vnum_end')}", f"tags: {z.get('tags') or []}", f"flags: {z.get('flags') or []}", f"plugin_data: {list((z.get('plugin_data') or {}).keys()) or 'none'}"]
        self._list_warn(lines,len(ids)); self._emit_list_event(character,cmd,"zone",f,len(ids),area_id=cur_area,zone_id=cur_zone,rng=val if f=="range" else None)
        return CommandResult("\n".join(lines))

    def _cmd_builder_nav(self, character: Any, args: list[str], raw: str) -> CommandResult:
        runtime = getattr(self, "runtime", None)
        cmd = raw.strip().split()[0].lower()
        if runtime and hasattr(runtime, "_builder_nav_command"):
            res = runtime._builder_nav_command(character, cmd, args, raw)
            if res is not None: return res
        if cmd in {"areas", "alist"}:
            self.builder_service.workspace = self.builder
            res = self.builder_service.list_content(character, "area", args)
            return CommandResult(res.message, ok=res.ok)
        if cmd in {"zones", "zlist"}:
            self.builder_service.workspace = self.builder
            res = self.builder_service.list_content(character, "zone", args)
            return CommandResult(res.message, ok=res.ok)
        if cmd in {"rooms","rlist"}:
            drafts=self.builder.load(self.builder.world_id(character)); allrooms=drafts.get("rooms",{}); zones=drafts.get("zones",{}); areas=drafts.get("areas",{}); cur_area,cur_zone=self._current_area_zone(character,drafts)
            f,val,err=self._parse_list_filter(args); source_filter=""
            if f in {"draft","live"}: source_filter=f; f = "all" if val and "all" in val else "current"
            if f=="error": self._emit_list_event(character,cmd,"room","invalid",invalid=True); return CommandResult(err+"\n"+self._builder_list_help(cmd), ok=False)
            rooms=allrooms; title="Rooms"
            if f=="all": pass
            elif f=="current":
                if args and args[0].lower()=="current": rooms={k:r for k,r in rooms.items() if k==getattr(character,"room_id","")}; title=f"Current room in zone {cur_zone}"
                elif cur_zone: rooms={k:r for k,r in rooms.items() if r.get("zone_id")==cur_zone}; title=f"Rooms in zone {cur_zone} ({zones.get(cur_zone,{}).get('name','')}), area {cur_area}."
                else: return CommandResult('No current zone selected.\nUse "rlist all" to list all rooms.\nUse "zlist" to list zones.\nUse "zset current <zone_id>" to select one.', ok=False)
            elif f=="unassigned" or f=="legacy": rooms={k:r for k,r in rooms.items() if not r.get("area_id") and not r.get("zone_id") and r.get("vnum") is None}; title="Legacy / Unassigned Rooms"
            elif f=="area": rooms={k:r for k,r in rooms.items() if r.get("area_id")==val}; title=f"Rooms in area {val}"
            elif f=="zone": rooms={k:r for k,r in rooms.items() if r.get("zone_id")==val}; title=f"Rooms in zone {val}"
            elif f=="id" and val in zones: rooms={k:r for k,r in rooms.items() if r.get("zone_id")==val}; title=f"Rooms in zone {val}"
            elif f=="id" and val in areas: rooms={k:r for k,r in rooms.items() if r.get("area_id")==val}; title=f"Rooms in area {val}"
            elif f=="range": a,b=val; rooms={k:r for k,r in rooms.items() if r.get("vnum") is not None and a <= int(r.get("vnum")) <= b}; title=f"Rooms in vnum range {a}-{b}"
            elif f=="number":
                matches={k:r for k,r in rooms.items() if r.get("vnum")==val and (not cur_area or r.get("area_id")==cur_area)} or {k:r for k,r in rooms.items() if r.get("vnum")==val}
                rooms=matches; title=f"Rooms with vnum {val}"
            elif f=="live": rooms={}
            else: return CommandResult(f"Room filter not found: {val}", ok=False)
            if source_filter=="live": rooms={}; title+=" (live)"
            lines=[title]
            if f=="number" and len(rooms)>1: lines.append(f"Multiple rooms use vnum {val} across different areas. Use rlist area <area_id> or goto <room_id>.")
            lines.append("ID | VNUM | Name | Exits | Area | Zone | Markers")
            for rid,r in sorted(rooms.items(), key=lambda kv:(kv[1].get("vnum") if kv[1].get("vnum") is not None else 999999, kv[0])):
                markers=["draft"]
                if rid==getattr(character,"room_id",""): markers.append("current location")
                if rid==self.builder.current_room_id(character): markers.append("current edit target")
                if not r.get("area_id") and not r.get("zone_id") and r.get("vnum") is None: markers.append("legacy/unassigned")
                if r.get("area_id") and r.get("vnum") is not None and rid != f"{r.get('area_id')}_{r.get('vnum')}": markers.append("id mismatch")
                lines.append(f"{rid} | {r.get('vnum') if r.get('vnum') is not None else 'none'} | {r.get('name','')} | {', '.join((r.get('exits') or {}).keys()) or 'none'} | {r.get('area_id') or 'none'} | {r.get('zone_id') or 'none'} | {', '.join(markers)}")
            self._list_warn(lines,len(rooms)); self._emit_list_event(character,cmd,"room",f,len(rooms),area_id=cur_area,zone_id=cur_zone,rng=val if f=="range" else None)
            return CommandResult("\n".join(lines))
        if cmd in {"rfind","rsearch"}:
            if not args: return CommandResult("Usage: rfind <query>", ok=False)
            q=" ".join(args).lower(); drafts=self.builder.load(self.builder.world_id(character)); lines=["Room search results:", "ID | VNUM | Name | Area | Zone | Source"]
            for rid,r in sorted(drafts.get("rooms",{}).items()):
                hay=" ".join(str(r.get(k,"")) for k in ["id","vnum","name","area_id","zone_id","description"]).lower()+" "+rid.lower()
                if q in hay: lines.append(f"{rid} | {r.get('vnum','')} | {r.get('name','')} | {r.get('area_id','')} | {r.get('zone_id','')} | draft")
            return CommandResult("\n".join(lines))
        return CommandResult(f"{cmd} requires the MudRuntime builder overlay.", ok=False)

    def _reverse_dir(self, direction: str) -> str:
        return {"north":"south","south":"north","east":"west","west":"east","up":"down","down":"up","in":"out","out":"in"}.get(direction, "")

    def _resolve_builder_direction(self, token: str) -> str:
        aliases = {"n":"north","e":"east","s":"south","w":"west","u":"up","d":"down"}
        token = str(token or "").lower()
        if token in aliases: return aliases[token]
        matches = [d for d in ("north","east","south","west","up","down") if d.startswith(token)]
        return matches[0] if len(matches) == 1 else token

    def _resolve_builder_room_id(self, character: Any, token: str) -> tuple[str, str]:
        drafts = self.builder.load(self.builder.world_id(character)); rooms = drafts.get("rooms", {})
        if token in rooms: return token, ""
        if str(token).isdigit():
            matches = [rid for rid, r in rooms.items() if str(r.get("vnum") or "") == str(token)]
            if len(matches) == 1: return matches[0], ""
            if len(matches) > 1: return "", f"Room VNUM {token} is ambiguous; use room ID."
        return "", f"Room not found: {token}"

    def _valid_room_id(self, room_id: str) -> bool:
        return bool(re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", str(room_id or "")))

    def _room_id_hint(self, attempted: str = "") -> str:
        return re.sub(r"[^a-z0-9]+", "_", str(attempted).lower()).strip("_") or "test_room_two"

    def _room_id_usage(self, attempted: str = "", command: str = "rcreate") -> str:
        hint = self._room_id_hint(attempted)
        if command == "dig":
            return f'Room IDs must be lowercase snake_case. Use {hint}.\nUse: dig north {hint} "{hint.replace("_", " ").title()}"'
        return f"Room IDs cannot contain spaces or uppercase characters. Room IDs must be lowercase snake_case. Use {hint}.\nUse: {command} {hint}"

    def _looks_like_room_id(self, text: str) -> bool:
        return bool(re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)+", str(text or "")))

    def _room_details(self, room_id: str, drafts: dict[str, Any]) -> str:
        room = drafts.get("rooms", {}).get(room_id, {})
        if not room:
            return f"Room edit details: room {room_id} is not in draft workspace."
        exits = ", ".join(sorted((room.get("exits") or {}).keys())) or "none"
        warnings = []
        if not room.get("name"): warnings.append("missing name")
        if not room.get("description"): warnings.append("missing description")
        if self._looks_like_room_id(room.get("name", "")): warnings.append("name looks like a room ID")
        lines = ["Room edit details:", f"  ID: {room_id}", f"  Name: {room.get('name') or '(empty)'}", f"  Description: {room.get('description') or '(empty)'}", f"  Exits: {exits}"]
        if warnings: lines += ["Room validation warnings:"] + [f"  - {w}" for w in warnings]
        return "\n".join(lines)

    def _cmd_dig(self, character: Any, args: list[str], raw: str) -> CommandResult:
        import shlex
        usage = 'Usage: dig <direction> <room_id> ["room name"] [--one-way] [--allow-self-loop]'
        try:
            parsed = shlex.split(raw)
        except ValueError:
            return CommandResult(usage, ok=False)
        args = parsed[1:]
        if len(args) < 2: return CommandResult(usage, ok=False)
        direction, rid_token = self._resolve_builder_direction(args[0]), args[1]
        if rid_token == "-1":
            return self._cmd_undig(character, [direction], "undig " + direction)
        custom = rid_token.lower() == "custom"
        if custom:
            if len(args) < 3: return CommandResult(usage, ok=False)
            rid = args[2]; vnum = None; name_offset = 3
        elif rid_token.isdigit():
            drafts_for_vnum = self.builder.load(self.builder.world_id(character))
            rid, vnum, err = self._room_id_for_vnum(character, drafts_for_vnum, rid_token)
            if err: return CommandResult(err, ok=False)
            name_offset = 2
        else:
            rid = rid_token; vnum = None; name_offset = 2
        if not self._valid_room_id(rid):
            self.builder.publish("builder_dig_rejected", character, self.builder.world_id(character), "room", rid, command=raw)
            return CommandResult(self._room_id_usage(rid, "dig"), ok=False)
        one_way = "--one-way" in args
        allow_self_loop = "--allow-self-loop" in args
        name_parts = [a for a in args[name_offset:] if a not in {"--one-way", "--allow-self-loop"}]
        if len(name_parts) > 1 and '"' not in raw and "'" not in raw:
            return CommandResult(usage, ok=False)
        name = " ".join(name_parts) or rid.replace("_", " ").title()
        world_id = self.builder.world_id(character); old = self.builder.current_room_id(character)
        if rid == old and not allow_self_loop:
            return CommandResult("Self-loop exits are blocked. Use --allow-self-loop to create one intentionally.", ok=False)
        self.builder.create_or_update(character, "rooms", rid, {"name": name, "description": "", "area_id": getattr(character,"current_area_id", getattr(character,"area_id", "")), "zone_id": getattr(character,"current_zone_id", getattr(character,"zone_id", "")), "vnum": vnum, "world_id": world_id, "exits": {}, "features": {}}, "dig", "room")
        self.builder.set_exit(character, direction, {"target_room_id": rid}, True)
        if not one_way and self._reverse_dir(direction):
            previous_edit = getattr(character, "last_edited_target", "")
            setattr(character, "edit_room_id", rid); setattr(character, "last_edited_target", rid)
            self.builder.set_exit(character, self._reverse_dir(direction), {"target_room_id": old}, True)
            setattr(character, "last_edited_target", previous_edit)
            if hasattr(character, "edit_room_id"): delattr(character, "edit_room_id")
        setattr(character, "last_room_id", old); setattr(character, "room_id", rid); setattr(character, "last_edited_target", rid); setattr(character, "last_created_room_id", rid)
        self.builder.publish("builder_dig_completed", character, world_id, "room", rid, command=raw)
        self.builder.publish("builder_room_graph_updated", character, world_id, "room", rid, command=raw)
        runtime = getattr(self, "runtime", None)
        if runtime: runtime.state_store.save_character(character, world_id)
        return CommandResult(f"Dug {direction} to {rid}.\n" + "\n".join(["Created room:", "ID:", rid, "Name:", name, "Area:", getattr(character,"current_area_id", "") or "none", "Zone:", getattr(character,"current_zone_id", "") or "none", "VNUM:", str(vnum) if vnum is not None else "none", "", "Linked:", f"{old} {direction} -> {rid}", f"{rid} {self._reverse_dir(direction)} -> {old}" if not one_way and self._reverse_dir(direction) else "", "", "Editing:", rid]) + "\n" + self._builder_room_status(character, rid, self.builder.load(world_id)), state_updates={"render_room": True})

    def _cmd_undig(self, character: Any, args: list[str], raw: str) -> CommandResult:
        if not args: return CommandResult("Usage: undig <direction>", ok=False)
        direction = self._resolve_builder_direction(args[0]); world_id = self.builder.world_id(character); room_id = self.builder.current_room_id(character); drafts = self.builder.load(world_id); rooms = drafts.setdefault("rooms", {})
        room = rooms.get(room_id) or {}; ex = (room.get("exits") or {}).get(direction)
        if not ex: return CommandResult(f"No {direction} exit exists from {room_id}.", ok=False)
        target = ex.get("target_room_id") or ex.get("destination_room_id"); reverse = self._reverse_dir(direction)
        before_room = copy.deepcopy(room); before_target = copy.deepcopy(rooms.get(target, {})) if target in rooms else None
        room.setdefault("exits", {}).pop(direction, None); rooms[room_id] = room
        removed_reverse = False
        if target in rooms and reverse and (rooms[target].get("exits") or {}).get(reverse, {}).get("target_room_id") == room_id:
            rooms[target].setdefault("exits", {}).pop(reverse, None); removed_reverse = True
        self.builder.save_drafts(world_id, drafts)
        self.builder_service._push_history(character, "rooms", room_id, before_room, room, "undig")
        if before_target is not None: self.builder_service._push_history(character, "rooms", target, before_target, rooms[target], "undig")
        return CommandResult(f"Removed exit {room_id} {direction} -> {target}." + ("\nRemoved matching reverse exit." if removed_reverse else "\nReverse exit was missing or mismatched; it was not changed."))

    def _cmd_rdig(self, character: Any, args: list[str], raw: str) -> CommandResult:
        if len(args) < 2: return CommandResult("Usage: rdig <direction> <new-room-id|vnum> [\"room name\"]", ok=False)
        return self._cmd_dig(character, args, "dig " + " ".join(args))

    def _cmd_relink(self, character: Any, args: list[str], raw: str) -> CommandResult:
        if len(args) < 2: return CommandResult("Usage: relink <direction> <target-room-id|vnum>", ok=False)
        direction = self._resolve_builder_direction(args[0]); target, err = self._resolve_builder_room_id(character, args[1])
        if err: return CommandResult(err, ok=False)
        source = self.builder.current_room_id(character)
        res = self.builder_service.link_rooms(character, source, direction, target, one_way=False, require_existing_target=True, allow_overwrite=True, action="relink")
        return CommandResult("Relinked existing exit destination.\n" + res.message, ok=res.ok)

    def _cmd_rlinks(self, character: Any, args: list[str], raw: str) -> CommandResult:
        world_id = self.builder.world_id(character); drafts = self.builder.load(world_id); rooms = drafts.get("rooms", {})
        room_id = args[0] if args else self.builder.current_room_id(character)
        if room_id not in rooms: return CommandResult(f"Room not found: {room_id}", ok=False)
        reverse = {"north":"south","south":"north","east":"west","west":"east","up":"down","down":"up"}
        lines = [f"Room links for {room_id}", "", "Outbound exits:"]
        problems = []
        for d, ex in sorted((rooms[room_id].get("exits") or {}).items()):
            tgt = (ex or {}).get("target_room_id") or (ex or {}).get("destination_room_id")
            lines.append(f"  {d:<5} -> {tgt or 'None'}")
            if tgt not in rooms: problems.append(f"  {d} -> missing {tgt}")
            else:
                back = (rooms[tgt].get("exits") or {}).get(reverse.get(d,""), {}).get("target_room_id")
                if back != room_id: problems.append(f"  {d} -> {tgt}, reverse is {'missing' if not back else 'mismatched to '+back}")
        lines += ["", "Inbound exits:"]
        for rid, room in sorted(rooms.items()):
            for d, ex in (room.get("exits") or {}).items():
                if ((ex or {}).get("target_room_id") or (ex or {}).get("destination_room_id")) == room_id and rid != room_id:
                    lines.append(f"  {rid} {d} -> this room")
                    if (rooms[room_id].get("exits") or {}).get(reverse.get(d,""), {}).get("target_room_id") != rid:
                        problems.append(f"  {rid} {d} -> this room, but reverse is missing")
        if lines[-1] == "Inbound exits:": lines.append("  none")
        lines += ["", "Problems:"] + (problems or ["  none"])
        return CommandResult("\n".join(lines))

    def _cmd_link(self, character: Any, args: list[str], raw: str) -> CommandResult:
        both = bool(args and args[0].lower()=="both")
        if both: args=args[1:]
        if len(args)<2: return CommandResult("Syntax: link [both] <direction> <target_room_id> [--allow-self-loop]", ok=False)
        allow_self_loop = "--allow-self-loop" in args
        args = [a for a in args if a != "--allow-self-loop"]
        direction,target=args[0].lower(),args[1]
        if not self._valid_room_id(target):
            return CommandResult(self._room_id_usage(target, "link"), ok=False)
        runtime=getattr(self,"runtime",None)
        if runtime and runtime.runtime_room_data(character,target)[0] is None: return CommandResult(f"Room not found: {target}", ok=False)
        old=self.builder.current_room_id(character)
        if target == old and not allow_self_loop:
            return CommandResult("Self-loop exits are blocked. Use --allow-self-loop to create one intentionally.", ok=False)
        res=self.builder.set_exit(character,direction,{"target_room_id":target},True)
        if both and self._reverse_dir(direction):
            setattr(character,"room_id",target); self.builder.set_exit(character,self._reverse_dir(direction),{"target_room_id":old},True); setattr(character,"room_id",old)
        self.builder.publish("builder_link_completed", character, self.builder.world_id(character), "room", target, command=raw)
        self.builder.publish("builder_room_graph_updated", character, self.builder.world_id(character), "room", target, command=raw)
        return CommandResult(f"Linked {direction} to {target}.\n" + self._builder_room_status(character, old, self.builder.load(self.builder.world_id(character))), ok=res.ok)

    def _cmd_unlink(self, character: Any, args: list[str], raw: str) -> CommandResult:
        if not args: return CommandResult("Syntax: unlink <direction>", ok=False)
        world_id=self.builder.world_id(character); room_id=self.builder.current_room_id(character); drafts=self.builder.load(world_id)
        before=drafts.get("rooms",{}).setdefault(room_id,{"id":room_id}).setdefault("exits",{}).pop(args[0].lower(),None)
        self.builder.save_drafts(world_id,drafts); self.builder.audit(character,world_id,"unlink","exit",f"{room_id}:{args[0]}",before,None); self.builder.publish("builder_unlink_completed", character, world_id, "exit", f"{room_id}:{args[0]}", command=raw); self.builder.publish("builder_room_graph_updated", character, world_id, "room", room_id, command=raw)
        return CommandResult(f"Unlinked {args[0]}.\n" + self._builder_room_status(character, room_id, self.builder.load(world_id)))


    def _cmd_delete_alias(self, character: Any, args: list[str], raw: str) -> CommandResult:
        token = raw.strip().split()[0].lower() if raw.strip() else ""
        if len(args) >= 2 and args[0].lower() in {"dir", "direction", "exit"}:
            return self._cmd_unlink(character, [args[1]], raw)
        return CommandResult(f"Syntax: {token} dir <direction> | {token} exit <direction>", ok=False)

    def _resolve_assignment(self, character: Any, args: list[str], raw: str, moving: bool = False) -> tuple[bool, str, str, str, int]:
        if len(args) < 5:
            return False, "Usage: rassign <here|room_id> area <area_id|current> zone <zone_id|current> vnum <number>", "", "", 0
        room_id = self.builder.current_room_id(character) if args[0].lower() == "here" else args[0]
        tokens = {args[i].lower(): args[i+1] for i in range(1, len(args)-1, 2)}
        aid = tokens.get("area")
        zid = tokens.get("zone")
        if moving and not aid:
            drafts = self.builder.load(self.builder.world_id(character))
            aid = (drafts.get("zones", {}).get(zid if zid != "current" else getattr(character, "current_zone_id", ""), {}) or {}).get("area_id") or getattr(character, "current_area_id", "")
        if aid == "current": aid = getattr(character, "current_area_id", "")
        if zid == "current": zid = getattr(character, "current_zone_id", "")
        try: vnum = int(tokens.get("vnum", ""))
        except ValueError: return False, "VNUM must be numeric.", "", "", 0
        return True, room_id, aid or "", zid or "", vnum

    def _assign_room(self, character: Any, room_id: str, aid: str, zid: str, vnum: int, raw: str, moving: bool) -> CommandResult:
        world_id=self.builder.world_id(character); drafts=self.builder.load(world_id); rooms=drafts.setdefault("rooms",{}); areas=drafts.get("areas",{}); zones=drafts.get("zones",{})
        if room_id not in rooms:
            return CommandResult(f"Room not found: {room_id}", ok=False)
        if aid not in areas:
            self.builder.publish("builder_assignment_failed", character, world_id, "room", room_id, command=raw)
            return CommandResult(f"Area not found: {aid}", ok=False)
        if zid not in zones:
            self.builder.publish("builder_assignment_failed", character, world_id, "room", room_id, command=raw)
            return CommandResult(f"Zone not found: {zid}", ok=False)
        if zones[zid].get("area_id") != aid:
            self.builder.publish("builder_assignment_failed", character, world_id, "room", room_id, command=raw)
            return CommandResult(f"Zone {zid} does not belong to area {aid}.", ok=False)
        area=areas[aid]; zone=zones[zid]
        if vnum < int(area.get("room_vnum_start") or area.get("vnum_start") or vnum) or vnum > int(area.get("room_vnum_end") or area.get("vnum_end") or vnum):
            self.builder.publish("builder_vnum_out_of_range_rejected", character, world_id, "room", room_id, command=raw)
            return CommandResult(f"VNUM {vnum} is outside area {aid} range {area.get('room_vnum_start') or area.get('vnum_start')}-{area.get('room_vnum_end') or area.get('vnum_end')}.", ok=False)
        if vnum < int(zone.get("vnum_start") or vnum) or vnum > int(zone.get("vnum_end") or vnum):
            self.builder.publish("builder_vnum_out_of_range_rejected", character, world_id, "room", room_id, command=raw)
            return CommandResult(f"VNUM {vnum} is outside zone {zid} range {zone.get('vnum_start')}-{zone.get('vnum_end')}.", ok=False)
        for rid,r in rooms.items():
            if rid != room_id and r.get("area_id")==aid and r.get("vnum")==vnum:
                self.builder.publish("builder_vnum_duplicate_rejected", character, world_id, "room", room_id, command=raw)
                return CommandResult(f"VNUM {vnum} is already used by room {rid}.", ok=False)
        before=dict(rooms[room_id]); was_unassigned=not before.get("area_id") and not before.get("zone_id") and before.get("vnum") is None
        rooms[room_id].update({"area_id": aid, "zone_id": zid, "vnum": vnum})
        if room_id not in zone.setdefault("room_ids", []): zone["room_ids"].append(room_id)
        if zid not in area.setdefault("zone_ids", []): area["zone_ids"].append(zid)
        self.builder.save_drafts(world_id,drafts); action="rmove" if moving and not was_unassigned else "rassign"
        self.builder.audit(character,world_id,action,"room",room_id,before,rooms[room_id])
        self.builder.publish("builder_room_moved" if moving and not was_unassigned else "builder_room_assigned", character, world_id, "room", room_id, command=raw)
        if before.get("vnum") != vnum: self.builder.publish("builder_room_vnum_changed", character, world_id, "room", room_id, command=raw)
        gen=f"{aid}_{vnum}"; warn = "" if room_id == gen else "\n\nWarning:\nRoom ID does not match generated convention. Future room-id migration can rename it safely."
        prefix = "Room was unassigned. Assigned it using rassign workflow.\n" if moving and was_unassigned else ""
        lines=[prefix+"Room assigned:" if not moving or was_unassigned else "Room moved:", f"Room: {room_id}", f"Name: {rooms[room_id].get('name','')}", f"Area: {aid}, {area.get('name')}", f"Zone: {zid}, {zone.get('name')}", f"VNUM: {vnum}", f"Canonical generated ID would be: {gen}", f"Current ID kept: {room_id}"]
        return CommandResult("\n".join(lines)+warn+"\n"+self._builder_room_status(character, room_id, self.builder.load(world_id)))

    def _cmd_room_assign(self, character: Any, args: list[str], raw: str) -> CommandResult:
        cmd = raw.strip().split()[0].lower()
        if cmd == "rrenameid":
            target = args[0] if args else ""
            self.builder.audit(character, self.builder.world_id(character), "rrenameid attempted", "room", target, None, None)
            return CommandResult("Room ID migration is not implemented yet.\nThis future command will update exits, spawns, builder history, and references safely.")
        ok, a, b, c, v = self._resolve_assignment(character, args, raw, cmd=="rmove")
        if not ok: return CommandResult(a, ok=False)
        return self._assign_room(character, a, b, c, v, raw, cmd=="rmove")

    def _cmd_builder_discovery(self, character: Any, args: list[str], raw: str) -> CommandResult:
        cmd = raw.strip().split()[0].lower() if raw.strip() else ""
        svc = self.builder_service
        svc.workspace = self.builder
        if cmd == "vnum":
            res = svc.vnum_report(character, args)
        elif cmd == "splist":
            res = svc.list_content(character, "spawn", args)
        elif cmd == "resetlist":
            res = svc.list_content(character, "reset", args)
        else:
            kind = {"mlist": "mob", "olist": "object", "rlist": "room"}.get(cmd, "mob")
            res = svc.list_content(character, kind, args)
        return CommandResult(res.message, ok=res.ok)

    def _cmd_builder_list_placeholder(self, character: Any, args: list[str], raw: str) -> CommandResult:
        cmd = raw.strip().split()[0].lower() if raw.strip() else ""
        drafts = self.builder.load(self.builder.world_id(character))
        _, current_zone = self._current_area_zone(character, drafts)
        if cmd == "mlist":
            return CommandResult("Mob/entity listing is not implemented yet. Mob/entity listing is not fully implemented yet.\nCurrent zone: " + (current_zone or "none") + "\nFuture usage:\nmlist\nmlist all\nmlist zone <zone_id>\nmlist 1500-1599")
        return CommandResult("Object/item listing is not implemented yet. Object/item listing is not fully implemented yet.\nCurrent zone: " + (current_zone or "none") + "\nFuture usage:\nolist\nolist all\nolist zone <zone_id>\nolist 1300-1399")


    def _stats_status(self, character: Any) -> CommandResult:
        if self._effective_role(character) not in {"builder","admin","owner"}: return CommandResult("You do not have permission for that command.", ok=False)
        attr,_=self._stat_services(character); pub=StatCombatPublisher(attr.world_root, getattr(self,'event_bus',None), getattr(self,'runtime',None)); val,h,changed=pub.preview()
        lines=['Builder stats status']
        for doc,x in h.items():
            dirty=bool(x['draft'] and x['draft']!=x['published']); lines.append(f"- {doc}: {'dirty' if dirty else 'clean'} draft={x['draft']} published={x['published']} validation={'error' if any(e.document==doc for e in val['errors']) else 'ok'}")
        audits=attr.world_root/'builder'/'audit'/'stats_publish_manifests.jsonl'
        if audits.exists(): lines.append('last_publish_id='+json.loads(audits.read_text().splitlines()[-1]).get('publish_id',''))
        return CommandResult('\n'.join(lines), ok=not val['errors'])

    def _validate_stats(self, character: Any) -> CommandResult:
        if self._effective_role(character) not in {"builder","admin","owner"}: return CommandResult("You do not have permission for that command.", ok=False)
        attr,_=self._stat_services(character); val=StatCombatPublishValidator(attr.world_root).validate()
        lines=['Builder stats validation: '+('OK' if val['ok'] else 'FAILED')]
        if val['errors']: lines += ['Errors:']+[f"- {e.line()}" for e in val['errors']]
        if val['warnings']: lines += ['Warnings:']+[f"- {w.line()}" for w in val['warnings']]
        lines += ['Dependency graph:']+[f"- {s}:{sid} -> {t}:{tid}" for s,sid,t,tid in val['graph']['references'] if tid]
        return CommandResult('\n'.join(lines), ok=val['ok'])

    def _preview_stats(self, character: Any) -> CommandResult:
        if self._effective_role(character) not in {"builder","admin","owner"}: return CommandResult("You do not have permission for that command.", ok=False)
        attr,_=self._stat_services(character); val,h,changed=StatCombatPublisher(attr.world_root, getattr(self,'event_bus',None), getattr(self,'runtime',None)).preview()
        lines=['Builder stats publish preview','Changed documents: '+(', '.join(changed) if changed else 'none'),'Draft/current hashes:']
        for doc,x in h.items(): lines.append(f"- {doc}: draft={x['draft']} published={x['published']}")
        if val['errors']: lines += ['Validation errors:']+[f"- {e.line()}" for e in val['errors']]
        if val['warnings']: lines += ['Warnings:']+[f"- {w.line()}" for w in val['warnings']]
        lines.append('activation_capability=hot_reload_when_runtime_services_accept_reload')
        lines.append('restart_requirement=only if no runtime services are attached or reload fails after valid file publication')
        return CommandResult('\n'.join(lines), ok=not val['errors'])

    def _publish_stats(self, character: Any) -> CommandResult:
        if self._effective_role(character) not in {"builder","admin","owner"}: return CommandResult("You do not have permission for that command.", ok=False)
        attr,_=self._stat_services(character); inj=getattr(self,'_stats_publish_failure_injection',None)
        res=StatCombatPublisher(attr.world_root, getattr(self,'event_bus',None), getattr(self,'runtime',None)).publish(self._stats_actor_id(character), inj)
        if not res.get('ok'):
            errs=res.get('errors') or []
            detail='\n'.join('- '+(e.line() if hasattr(e,'line') else str(e)) for e in errs) or res.get('message','publish failed')
            return CommandResult('Builder stats publish failed. Published files unchanged or rolled back.\n'+detail, ok=False)
        m=res['manifest']; return CommandResult(f"Builder stats publish completed. publish_id={m['publish_id']} published=true active_runtime={m['active_runtime']} restart_required={m['restart_required']}\nChanged documents: "+', '.join(res.get('changed') or []))


    def _reset_service(self, character: Any):
        from engine.zone_resets import ZoneResetService
        runtime = getattr(self, "runtime", None)
        db_path = getattr(getattr(runtime, "state_store", None), "db_path", None) or getattr(getattr(self, "state_store", None), "db_path", ":memory:")
        return ZoneResetService(runtime=runtime, db_path=db_path, event_bus=getattr(self, "event_bus", None))

    def _cmd_builder_reset(self, character: Any, args: list[str], raw: str) -> CommandResult:
        if self._effective_role(character) not in {"builder", "admin", "owner"}:
            return CommandResult("You do not have permission for that command.", ok=False)
        import json, uuid
        from pathlib import Path
        cmd = raw.strip().split()[0].lower() if raw.strip() else "resetlist"
        world_id = self.builder.world_id(character)
        root = self.builder.ensure(world_id)
        path = root / "resets.json"
        def load():
            try: return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
            except Exception: return {}
        def save(d):
            path.write_text(json.dumps(d, indent=2, sort_keys=True)+"\n", encoding="utf-8")
        svc = self._reset_service(character)
        data = load()
        profiles = [svc.normalize_profile(v, world_id) for v in data.values()]
        action = {"zreset":"resetlist","zresetstat":"resetstat","zresetpreview":"resetpreview","zresetrun":"resetrun"}.get(cmd, cmd)
        if action == "resetlist":
            lines=["Reset profiles"]
            for p in profiles:
                if args and args[0].startswith("zone=") and p.get("zone_id") != args[0].split("=",1)[1]: continue
                lines.append(f"- {p['reset_profile_id']} zone={p.get('zone_id')} enabled={p.get('enabled')} mode={p.get('reset_mode')} commands={len(p.get('commands') or [])}")
            return CommandResult("\n".join(lines if len(lines)>1 else ["No reset profiles."]))
        if action == "resetcreate":
            if len(args)<2: return CommandResult("Usage: resetcreate <profile_id> <zone_id> [display name]", ok=False)
            pid, zid = args[0], args[1]
            if pid in data: return CommandResult("Reset profile already exists.", ok=False)
            prof={"reset_profile_id":pid,"world_id":world_id,"zone_id":zid,"display_name":" ".join(args[2:]) or pid.replace('_',' ').title(),"enabled":True,"reset_mode":"manual_only","reset_interval_seconds":None,"priority":100,"definition_version":"1","commands":[],"metadata":{"builder_draft":True}}
            data[pid]=prof; save(data); self.builder.audit(character, world_id, "resetcreate", "reset", pid, None, prof); return CommandResult(f"Draft reset profile {pid} created for zone {zid}.")
        if action == "resetclone":
            if len(args)<2: return CommandResult("Usage: resetclone <source_profile_id> <new_profile_id>", ok=False)
            if args[0] not in data: return CommandResult("Source reset profile not found.", ok=False)
            if args[1] in data: return CommandResult("Target reset profile already exists.", ok=False)
            prof=json.loads(json.dumps(data[args[0]])); prof["reset_profile_id"]=args[1]; prof["display_name"]=prof.get("display_name",args[0])+" clone"
            for c in prof.get("commands",[]): c["reset_command_id"] = "rcmd_"+uuid.uuid4().hex[:8]
            data[args[1]]=prof; save(data); return CommandResult(f"Draft reset profile {args[1]} cloned from {args[0]}.")
        pid = args[0] if args else ""
        prof = data.get(pid)
        if action in {"resetstat","resetset","resetdelete","resetcommand","resetvalidate","resetpreview","resetrun"} and not prof:
            return CommandResult(f"Reset profile not found: {pid}", ok=False)
        if action == "resetstat":
            v=svc.validate_profile(prof); lines=[f"Profile: {pid}",f"Display: {prof.get('display_name')}",f"World: {prof.get('world_id')}",f"Zone: {prof.get('zone_id')}",f"Enabled: {prof.get('enabled')}",f"Mode: {prof.get('reset_mode')}",f"Interval: {prof.get('reset_interval_seconds')}",f"Priority: {prof.get('priority')}",f"Definition version: {prof.get('definition_version')}",f"Command count: {len(prof.get('commands') or [])}",f"Validation: {'ok' if v.ok else 'failed'}"]
            lines += [f"- {c.get('order',0)} {c.get('reset_command_id')} {c.get('command_type')} enabled={c.get('enabled',True)}" for c in sorted(prof.get('commands') or [], key=lambda x:int(x.get('order',0)))]
            return CommandResult("\n".join(lines), ok=v.ok)
        if action == "resetset":
            if len(args)<3: return CommandResult("Usage: resetset <profile_id> <field> <value>", ok=False)
            field,val=args[1]," ".join(args[2:]); allowed={"display_name","enabled","reset_mode","reset_interval_seconds","priority","definition_version","maximum_actions_per_run","maximum_entities_created_per_run","maximum_items_created_per_run","maximum_execution_seconds"}
            if field not in allowed: return CommandResult("Unknown reset field.", ok=False)
            if field=="enabled": val=val.lower() in {"1","true","yes","on"}
            if field in {"reset_interval_seconds","priority","maximum_actions_per_run","maximum_entities_created_per_run","maximum_items_created_per_run","maximum_execution_seconds"}: val=None if val.lower()=="none" else int(val)
            prof[field]=val; data[pid]=prof; save(data); return CommandResult(f"Reset profile {pid} updated: {field}={val}")
        if action == "resetdelete":
            before=data.pop(pid); save(data); self.builder.audit(character, world_id, "resetdelete", "reset", pid, before, None); return CommandResult(f"Draft reset profile {pid} deleted. Runtime population was not changed.")
        if action == "resetcommand":
            if len(args)<2: return CommandResult("Usage: resetcommand <profile_id> <add|set|move|enable|disable|delete|condition|failure> ...", ok=False)
            sub=args[1]; cmds=prof.setdefault('commands',[])
            if sub=='add':
                if len(args)<3: return CommandResult("Usage: resetcommand <profile_id> add <command_type> key=value ...", ok=False)
                c={"reset_command_id":"rcmd_"+uuid.uuid4().hex[:8],"command_type":args[2].upper(),"enabled":True,"order":(max([int(x.get('order',0)) for x in cmds] or [0])+10),"condition":{"type":"always"},"failure_policy":"continue","comment":"","metadata":{}}
                for tok in args[3:]:
                    if '=' in tok:
                        k,v=tok.split('=',1); c[k]=int(v) if k in {'spawn_count','maximum_count','stack_count'} else v
                cmds.append(c)
            else:
                if len(args)<3: return CommandResult("Command id required.", ok=False)
                c=next((x for x in cmds if x.get('reset_command_id')==args[2]), None)
                if not c: return CommandResult("Reset command not found.", ok=False)
                if sub=='set':
                    for tok in args[3:]:
                        if '=' in tok:
                            k,v=tok.split('=',1); c[k]=int(v) if k in {'order','spawn_count','maximum_count','stack_count'} else v
                elif sub=='move': c['order']=int(args[3])
                elif sub=='enable': c['enabled']=True
                elif sub=='disable': c['enabled']=False
                elif sub=='delete': cmds.remove(c)
                elif sub=='condition': c['condition']={"type":args[3], **({"reference":args[4]} if len(args)>4 else {})}
                elif sub=='failure': c['failure_policy']=args[3]
                else: return CommandResult("Unknown resetcommand action.", ok=False)
            save(data); return CommandResult("Reset command draft updated.")
        if action == "resetvalidate":
            v=svc.validate_profile(prof); return CommandResult("Reset validation: "+("OK" if v.ok else "FAILED")+"\nErrors:\n"+"\n".join('- '+e for e in v.errors or ['none'])+"\nWarnings:\n"+"\n".join('- '+w for w in v.warnings or ['none']), ok=v.ok)
        if action == "resetpreview" or (action == "resetrun" and "--dry-run" in args):
            res=svc.execute_plan(svc.compile_plan(prof), trigger='preview', requested_by=getattr(character,'id',''), preview=True); return CommandResult("Reset preview\n"+json.dumps(res, indent=2, sort_keys=True))
        if action == "resetrun":
            res=svc.execute_plan(svc.compile_plan(prof), trigger='manual_force' if '--force' in args else 'manual', requested_by=getattr(character,'id',''), force='--force' in args); return CommandResult("Reset run\n"+json.dumps({k:v for k,v in res.items() if k!='results'}, indent=2, sort_keys=True), ok=res.get('status') in {'succeeded','partial'})
        if action == "resethistory": return CommandResult("Reset history\n"+json.dumps(svc.history(), indent=2, sort_keys=True))
        if action == "resettrace": return CommandResult("Reset trace\n"+json.dumps(svc.trace(args[0] if args else ''), indent=2, sort_keys=True))
        return CommandResult("Unknown reset command.", ok=False)


    def _cmd_builder_normalize(self, character: Any, args: list[str], raw: str) -> CommandResult:
        self.builder_service.workspace = self.builder
        res = self.builder_service.normalize_command(character, args)
        return CommandResult(narrative=res.message, ok=res.ok)

    def _cmd_scan(self, character: Any, args: list[str], raw: str) -> CommandResult:
        direction = args[0].lower() if args else ""
        dirs = [direction] if direction else ["north","east","south","west","up","down","in","out"]
        valid = {"north","east","south","west","up","down","in","out"}
        if direction and direction not in valid:
            return CommandResult("Usage: scan [north|south|east|west|up|down|in|out]", ok=False)
        rt = getattr(self, "runtime", None)
        if not rt:
            return CommandResult("You scan the area, but nothing stands out.")
        start = rt.canonical_room_id(getattr(character, "room_id", "")) if hasattr(rt, "canonical_room_id") else str(getattr(character, "room_id", ""))
        labels = {1:"close by", 2:"a ways off", 3:"far off"}
        lines = ["You quickly scan the area."]
        seen = set()
        for d in dirs:
            room = start
            for dist in range(1, 4):
                exits = rt.canonical_exits(character, room) if hasattr(rt, "canonical_exits") else {}
                ex = (exits or {}).get(d)
                if not ex or ex.get("hidden") or ex.get("closed") or ex.get("locked"):
                    break
                room = rt.canonical_room_id(ex.get("target_room_id", "")) if hasattr(rt, "canonical_room_id") else str(ex.get("target_room_id", ""))
                visible = rt.find_visible_entities(room, character) if hasattr(rt, "find_visible_entities") else {}
                actors = []
                for key in ("characters", "players", "npcs", "mobs"):
                    for a in visible.get(key, []) if isinstance(visible, dict) else []:
                        aid = str(a.get("actor_id") or a.get("instance_id") or a.get("entity_id") or a.get("character_id") or a.get("id") or a.get("name"))
                        name = str(a.get("name") or a.get("display_name") or a.get("entity_id") or aid)
                        if aid and aid not in seen and aid != getattr(character, "id", ""):
                            seen.add(aid); actors.append(name)
                for name in actors:
                    lines.append(f"{name} is {labels.get(dist, 'far off')} {d}.")
        if len(lines) == 1:
            room_name = ""
            try:
                data = rt.runtime_room_data(character, start)[0] if hasattr(rt, "runtime_room_data") else None
                room_name = (data or {}).get("name") or (data or {}).get("title") or ""
            except Exception:
                room_name = ""
            lines.append(f"You do not notice anyone nearby. {room_name}".strip())
        return CommandResult("\n".join(lines))

    def _cmd_builder(self, character: Any, args: list[str], raw: str) -> CommandResult:
        sub = args[0].lower() if args else "status"
        if raw.strip().split()[0].lower() in {"bstatus", "status"}:
            sub = "status"
        if sub in {"on", "enable"} or (raw.split()[0].lower() == "build" and sub == "status"):
            res = self.builder.set_builder_mode(character, True)
            status = self._builder_room_status(character, self.builder.current_room_id(character), self.builder.load(self.builder.world_id(character))) if res.ok else ""
            return CommandResult(narrative=res.message + (("\n" + status) if status else ""), ok=res.ok)
        if sub in {"off", "disable"}:
            res = self.builder.set_builder_mode(character, False)
            return CommandResult(narrative=res.message, ok=res.ok)
        if sub == "normalize":
            self.builder_service.workspace = self.builder
            res = self.builder_service.normalize_command(character, args[1:] if len(args) > 1 else [])
            return CommandResult(narrative=res.message, ok=res.ok)
        if sub == "migrate":
            if len(args) >= 2 and args[1].lower() == "starter":
                res = self.builder.migrate_starter(character); return CommandResult(narrative=res.message, ok=res.ok)
            return CommandResult(narrative="Usage: builder migrate starter", ok=False)
        if sub == "template":
            if len(args) < 2:
                return CommandResult(narrative="Usage: builder template <list|show|copy> [template_name] [new_filename] [--force]", ok=False)
            action = args[1].lower()
            if action == "list":
                res = self.builder.template_list(character); return CommandResult(narrative=res.message, ok=res.ok)
            if action == "show" and len(args) >= 3:
                res = self.builder.template_show(character, args[2]); return CommandResult(narrative=res.message, ok=res.ok)
            if action == "copy" and len(args) >= 4:
                res = self.builder.template_copy(character, args[2], args[3], force=("--force" in args[4:])); return CommandResult(narrative=res.message, ok=res.ok)
            return CommandResult(narrative="Usage: builder template <list|show|copy> [template_name] [new_filename] [--force]", ok=False)
        if sub == "import":
            if len(args) < 2:
                return CommandResult(narrative="Usage: builder import <list|validate|preview|apply> [filename] [--merge|--replace-drafts]", ok=False)
            action = args[1].lower()
            if action == "list":
                res = self.builder.import_list(character); return CommandResult(narrative=res.message, ok=res.ok)
            if len(args) < 3:
                return CommandResult(narrative=f"Usage: builder import {action} <filename>", ok=False)
            if action == "validate": res = self.builder.import_validate(character, args[2])
            elif action == "preview": res = self.builder.import_preview(character, args[2])
            elif action == "apply": res = self.builder.import_apply(character, args[2], replace=("--replace-drafts" in args[3:]))
            else: return CommandResult(narrative=f"Unknown builder import command: {action}", ok=False)
            return CommandResult(narrative=res.message, ok=res.ok)
        if sub == "validate" and len(args) >= 2 and args[1].lower() == "stats":
            return self._validate_stats(character)
        if sub == "preview" and len(args) >= 2 and args[1].lower() == "stats":
            return self._preview_stats(character)
        if sub == "status" and len(args) >= 2 and args[1].lower() == "stats":
            return self._stats_status(character)
        if sub == "validate":
            res = self.builder.validate(character); return CommandResult(narrative=res.message + "\n" + self._builder_room_status(character, self.builder.current_room_id(character), self.builder.load(self.builder.world_id(character))), ok=res.ok)
        if sub in {"save", "export"}:
            self.builder.publish("builder_export_requested", character, self.builder.world_id(character), "export", sub, command=raw)
            res = self.builder.export(character); self.builder.publish("builder_export_completed", character, self.builder.world_id(character), "export", sub, command=raw)
            self.builder.audit(character, self.builder.world_id(character), f"builder {sub}", "export", sub, None, res.data or {})
            return CommandResult(narrative=res.message + "\n" + self._builder_room_status(character, self.builder.current_room_id(character), self.builder.load(self.builder.world_id(character))), ok=res.ok)
        if sub in {"testroom", "testenter"}:
            res = self.builder_service.testroom(character); return CommandResult(narrative=res.message, ok=res.ok)
        if sub == "testexit":
            res = self.builder_service.testexit(character); return CommandResult(narrative=res.message, ok=res.ok)
        if sub == "testreset":
            res = self.builder_service.testreset(character); return CommandResult(narrative=res.message, ok=res.ok)
        if sub == "teststatus":
            res = self.builder_service.teststatus(character); return CommandResult(narrative=res.message, ok=res.ok)
        if sub == "testclear":
            res = self.builder_service.testclear(character); return CommandResult(narrative=res.message, ok=res.ok)
        if sub == "testspawn":
            if len(args) < 2:
                return CommandResult(narrative="Usage: builder testspawn <mob_id>", ok=False)
            res = self.builder_service.testspawn(character, args[1])
            return CommandResult(narrative=res.message, ok=res.ok)
        if sub == "generation" and len(args) >= 2:
            action=args[1].lower()
            if action == "activate":
                res=self.builder_service.activate_generation(character, args[2] if len(args)>2 else "latest"); return CommandResult(narrative=res.message, ok=res.ok)
            if action == "rollback":
                res=self.builder_service.rollback_generation(character); return CommandResult(narrative=res.message, ok=res.ok)
            if action in {"status", "list", "diff"}:
                return CommandResult(narrative="Builder generation command available: activate <id>, rollback. Generation packages are under worlds/<world>/builder/generations/.")
        if sub == "publish" and len(args) >= 2 and args[1].lower() == "stats":
            return self._publish_stats(character)
        if sub == "publish" and len(args) >= 2 and args[1].lower() == "generation":
            res = self.builder_service.publish(character)
            return CommandResult(narrative=res.message, ok=res.ok)
        if sub == "publish":
            res = self.builder.publish_drafts(character)
            return CommandResult(narrative=res.message + "\n" + self._builder_room_status(character, self.builder.current_room_id(character), self.builder.load(self.builder.world_id(character))), ok=res.ok)
        if sub == "reload":
            self.builder.publish("builder_reload_requested", character, self.builder.world_id(character), "builder", "reload", command="builder reload")
            return CommandResult(narrative="Builder drafts reloaded from workspace.\n" + self._builder_room_status(character, self.builder.current_room_id(character), self.builder.load(self.builder.world_id(character))))
        if sub == "snapshot":
            res = self.builder.snapshot(character); return CommandResult(narrative=res.message + "\n" + self._builder_room_status(character, self.builder.current_room_id(character), self.builder.load(self.builder.world_id(character))), ok=res.ok)
        if sub == "history":
            res = self.builder.history(character); return CommandResult(narrative=res.message, ok=res.ok)
        if sub == "status":
            return CommandResult(narrative=self._builder_room_status(character, self.builder.current_room_id(character), self.builder.load(self.builder.world_id(character))))
        suggestions = {"statys": "status", "stats": "status", "stat": "status"}
        if sub in suggestions:
            return CommandResult(narrative=f"Unknown builder command: {sub}.\nDid you mean builder {suggestions[sub]}?", ok=False)
        return CommandResult(narrative=f"Unknown builder command: {sub}.", ok=False)

    def _builder_room_status(self, character: Any, room_id: str, drafts: dict[str, Any]) -> str:
        runtime = getattr(self, "runtime", None)
        loc_id = str(getattr(character, "room_id", "") or getattr(character, "current_room_id", "") or "start")
        def info(rid: str):
            draft = drafts.get("rooms", {}).get(rid)
            live = runtime.runtime_room_data(character, rid)[0] if runtime and hasattr(runtime, "runtime_room_data") else None
            rec = draft or live or {}
            return (rec.get("name") or rec.get("title") or "(unnamed)", "draft" if draft is not None else "live" if live is not None else "unknown", draft is not None)
        loc_name, loc_source, _ = info(loc_id)
        rooms = drafts.get("rooms", {})
        current_room = rooms.get(loc_id, {})
        current_area_id = str(current_room.get("area_id") or getattr(character,"current_area_id","") or "")
        current_zone_id = str(current_room.get("zone_id") or getattr(character,"current_zone_id","") or "")
        area = self._builder_collection_record(character, drafts, "areas", current_area_id)
        zone = self._builder_collection_record(character, drafts, "zones", current_zone_id)
        world_name = self.builder.world_id(character).replace("_", " ").title()
        def label(kind, rec, cid):
            if not cid: return f"{kind}: unknown"
            return f"{kind}: {self._builder_display_name(rec, cid)} [{cid}]"
        lines = ["Builder Status:", "================================================", "Builder Mode", "", "World:", world_name, "", "Current location:"]
        lines += ["  " + label("Area", area, current_area_id), "  " + label("Zone", zone, current_zone_id), f"  Room: {loc_name} [{loc_id}]", f"  VNUM: {current_room.get('vnum') if current_room.get('vnum') is not None else 'none'}", "", "Builder scope:", f"  Area: {'current' if current_area_id else 'none selected'}", f"  Zone: {'current' if current_zone_id else 'none selected'}"]
        lines += ["", "Location:", f"{loc_id}, {loc_name}", "", "Currently editing:", "Editing:"]
        if not room_id:
            lines.append("none")
        else:
            name, source, dirty = info(room_id)
            lines += [f"Room: {room_id}", f"Name: {name}", f"Source: {source}", f"Dirty: {'yes' if dirty else 'no'}", f"Editing room: {room_id} {name}"]
            room = drafts.get("rooms", {}).get(room_id, {})
            aid, zid, vnum = room.get("area_id") or "", room.get("zone_id") or "", room.get("vnum")
            a = self._builder_collection_record(character, drafts, "areas", aid)
            z = self._builder_collection_record(character, drafts, "zones", zid)
            legacy = not aid and not zid and vnum is None
            area_text = f"{self._builder_display_name(a, aid)} [{aid}]" if aid else "none"
            zone_text = f"{self._builder_display_name(z, zid)} [{zid}]" if zid else "none"
            lines += ["", "Room Organization:", f"Area: {area_text}", f"Zone: {zone_text}", f"Room: {name} [{room_id}]", f"VNUM: {vnum if vnum is not None else 'none'}", f"Status: {'legacy/unassigned' if legacy else 'organized'}"]
            if legacy:
                ca=getattr(character,"current_area_id","") or "<area_id>"; cz=getattr(character,"current_zone_id","") or "<zone_id>"
                lines += ["", "Suggested next command:", f"rassign here area {ca} zone {cz} vnum <number>"]
            elif aid and vnum is not None:
                lines.append(f"Generated ID: {aid}_{vnum}")
        lines += ["", "================================================"]
        self.builder.publish("builder_status_rendered", character, self.builder.world_id(character), "room", room_id or "none", command="builder status")
        return "\n".join(lines)

    def _cmd_builder_edit(self, character: Any, args: list[str], raw: str) -> CommandResult:
        token = raw.strip().split()[0].lower()
        cmd = self.resolve_alias(token) or token
        world_id = self.builder.world_id(character); room_id = self.builder.current_room_id(character)
        self.builder.publish("builder_command_received", character, world_id, "command", cmd, command=raw)
        drafts = self.builder.load(world_id)
        def out(res): return CommandResult(narrative=res.message, ok=res.ok)
        if cmd == "btarget":
            if not args:
                return CommandResult(self._builder_room_status(character, room_id, drafts))
            if args[0].lower() == "clear":
                old = room_id; setattr(character, "edit_room_id", ""); setattr(character, "last_edited_target", "")
                self.builder.publish("builder_edit_target_changed", character, world_id, "room", "none", command=raw)
                self.builder.audit(character, world_id, "btarget clear", "room", old, old, None)
                return CommandResult("Currently editing: none")
            if len(args) >= 2 and args[0].lower() == "room":
                setattr(character, "edit_room_id", args[1]); setattr(character, "last_edited_target", args[1])
                self.builder.publish("builder_edit_target_changed", character, world_id, "room", args[1], command=raw)
                return CommandResult("Builder target set.\n" + self._builder_room_status(character, args[1], drafts))
            return CommandResult('Usage: btarget [room <room_id>|clear]', ok=False)
        if cmd == "oedit" and args:
            self.builder_service.workspace = self.builder
            return out(self.builder_service.object_menu(character, args[0]))
        if cmd == "redit" and not args:
            if not room_id:
                return CommandResult(self._builder_room_status(character, room_id, drafts) + "\nNo room is currently selected.\nUse redit <room_id>, rcreate <room_id>, goto <room_id>, or btarget room <room_id>.", ok=False)
            self.builder_service.workspace = self.builder
            return out(self.builder_service.start_editor(character, "redit", "rooms", room_id))
        if cmd in {"medit", "oedit", "redit", "aedit", "zedit"}:
            self.builder_service.workspace = self.builder
            res = self.builder_service.discover_editor_target(character, cmd, args)
            return CommandResult(res.message, ok=res.ok)
        if cmd in {"mclone", "oclone", "rclone"}:
            if len(args) < 2: return CommandResult(f"Usage: {cmd} <source_id> <new_id>", ok=False)
            coll = {"mclone":"entities", "oclone":"items", "rclone":"rooms"}[cmd]
            res = self.builder_service.clone(character, coll, args[0], args[1]); return CommandResult(res.message, ok=res.ok)
        if cmd in {"undo", "redo"}:
            res = getattr(self.builder_service, cmd)(character); return CommandResult(res.message, ok=res.ok)
        if cmd == "find":
            res = self.builder_service.search(character, " ".join(args)); return CommandResult(res.message, ok=res.ok)
        if cmd == "builder" and args and args[0].lower() == "testspawn" and len(args) > 1:
            res = self.builder_service.testspawn(character, args[1]); return CommandResult(res.message, ok=res.ok)
        if cmd == "redit":
            if args:
                ordered = sorted(drafts.get("rooms", {}).keys())
                if args[0].lower() in {"next", "previous"} and ordered:
                    cur = room_id if room_id in ordered else ordered[0]
                    idx = ordered.index(cur) if cur in ordered else 0
                    room_id = ordered[(idx + (1 if args[0].lower()=="next" else -1)) % len(ordered)]
                else:
                    room_id = args[0]
                setattr(character, "edit_room_id", room_id); setattr(character, "last_edited_target", room_id)
                self.builder.publish("builder_edit_target_changed", character, world_id, "room", room_id, command=raw)
            status = self._builder_room_status(character, room_id, drafts)
            if not room_id:
                return CommandResult(status + "\nNo room is currently selected.\nUse redit <room_id>, rcreate <room_id>, goto <room_id>, or btarget room <room_id>.", ok=False)
            return CommandResult(status + "\n" + self._room_details(room_id, drafts))
        if cmd in {"rstat", "rwhere"}:
            return CommandResult(self._builder_room_status(character, room_id, drafts))
        if cmd == "rcreate":
            if not args:
                return CommandResult(self._room_id_usage("", "rcreate"), ok=False)
            vnum = None
            if args[0].lower() == "custom":
                if len(args) != 2:
                    return CommandResult("Usage: rcreate custom <room_id>", ok=False)
                rid = args[1]
            elif len(args) == 1 and args[0].isdigit():
                rid, vnum, err = self._room_id_for_vnum(character, drafts, args[0])
                if err:
                    return CommandResult(err, ok=False)
            elif len(args) == 1:
                rid = args[0]
            else:
                return CommandResult(self._room_id_usage(" ".join(args), "rcreate"), ok=False)
            if not self._valid_room_id(rid):
                return CommandResult(self._room_id_usage(rid, "rcreate"), ok=False)
            setattr(character, "last_room_id", getattr(character, "room_id", room_id)); setattr(character, "room_id", rid); setattr(character, "edit_room_id", rid); setattr(character, "last_edited_target", rid); setattr(character, "last_created_room_id", rid)
            updates = {"area_id": getattr(character,"current_area_id", getattr(character,"area_id", "")), "zone_id": getattr(character,"current_zone_id", getattr(character,"zone_id", "")), "vnum": vnum, "world_id": world_id, "exits": {}, "features": {}}
            res = self.builder.create_or_update(character, "rooms", rid, updates, "rcreate vnum" if vnum is not None else "rcreate", "room")
            if vnum is not None:
                self.builder.publish("builder_vnum_assigned", character, world_id, "room", rid, command=raw)
                self.builder.publish("builder_room_assigned_to_area", character, world_id, "room", rid, command=raw)
                self.builder.publish("builder_room_assigned_to_zone", character, world_id, "room", rid, command=raw)
            return CommandResult(res.message + "\n" + self._builder_room_status(character, rid, self.builder.load(world_id)), ok=res.ok)
        if cmd == "rname":
            if not getattr(character, "edit_room_id", "") and not getattr(character, "last_edited_target", ""):
                return CommandResult("No room is currently selected. Use rcreate, redit <room_id>, goto <room_id>, or btarget room <room_id>.", ok=False)
            if args and args[0].lower() == "suggest":
                val = room_id.replace("_", " ").title()
                res = self.builder.create_or_update(character, "rooms", room_id, {"name": val}, "rname", "room")
                return CommandResult(narrative=f"Room {room_id} name changed to {val}.\n" + self._builder_room_status(character, room_id, self.builder.load(world_id)), ok=res.ok)
            force = bool(args and args[0] == "--force")
            val = self._builder_value(raw,2) if force else self._builder_value(raw,1)
            if not val.strip(): return CommandResult("Room name cannot be blank.", ok=False)
            if self._looks_like_room_id(val) and not force:
                self.builder.publish("builder_room_name_warning", character, world_id, "room", room_id, command=raw)
                return CommandResult("That looks like a room ID, not a display name.\nUse a display name like: " + val.replace("_", " ").title() + ".\nTo change the room ID, use a future room-id migration command.", ok=False)
            warnings=[]
            if any((r.get("name") or "").strip().lower()==val.strip().lower() and rid != room_id for rid,r in drafts.get("rooms",{}).items()): warnings.append("Warning: duplicate display name.")
            if val.strip() == room_id: warnings.append("Warning: display name equals room ID.")
            res = self.builder.create_or_update(character, "rooms", room_id, {"name": val.strip()}, "rname", "room")
            lines=[f"Room {room_id} name changed to {val.strip()}.", "Updated room:", "", "ID:", room_id, "", "Name:", val.strip(), "", "Dirty:", "yes"] + ([""]+warnings if warnings else [])
            return CommandResult(narrative="\n".join(lines)+"\n"+self._builder_room_status(character, room_id, self.builder.load(world_id)), ok=res.ok)
        if cmd in {"rdesc", "desc"}:
            if cmd == "desc" and not getattr(character, "builder_mode", False):
                return CommandResult("desc is a Builder Mode alias for rdesc. Enable Builder Mode first.", ok=False)
            if cmd == "desc":
                self.builder.publish("builder_desc_alias_used", character, world_id, "room", room_id, command=raw)
            if not getattr(character, "edit_room_id", "") and not getattr(character, "last_edited_target", ""):
                return CommandResult("No room is currently selected. Use rcreate, redit <room_id>, goto <room_id>, or btarget room <room_id>.", ok=False)
            if len(args) >= 3 and args[0].lower() == "room":
                room_id = args[1]
                setattr(character, "edit_room_id", room_id); setattr(character, "last_edited_target", room_id)
                val = self._builder_value(raw,3)
            else:
                val = self._builder_value(raw,1)
            if not val:
                setattr(character, "builder_desc_editor_room_id", room_id); setattr(character, "builder_desc_editor_lines", [])
                return CommandResult("""Description editor

rdesc <description>
sets the description for the currently selected room.

To edit another room first:
redit <room_id>
rdesc <description>

Enter description.

Finish with:
.end

Cancel:
.cancel""")
            res = self.builder.create_or_update(character, "rooms", room_id, {"description": val}, cmd, "room")
            name = self.builder.load(world_id).get("rooms",{}).get(room_id,{}).get("name") or "(unnamed)"
            lines=[f"Description updated for room {room_id}.", "Description updated for currently selected room:", f"Room: {room_id}", f"Name: {name}", f"Description: {val}", f"Room {room_id} description changed."]
            return CommandResult(narrative="\n".join(lines)+"\n"+self._builder_room_status(character, room_id, self.builder.load(world_id)), ok=res.ok)
        if cmd == "rset" and len(args)>=2:
            return out(self.builder.create_or_update(character, "rooms", room_id, {args[0]: self._builder_value(raw,2)}, "rset", "room"))
        if cmd in {"rexits", "rfeature"}:
            room=drafts.get("rooms",{}).get(room_id,{})
            return CommandResult(narrative=str(room.get("exits" if cmd=="rexits" else "features", {})))
        if cmd == "rdelete": return out(self.builder.delete(character, "rooms", args[0] if args else room_id, "room"))
        if cmd == "excreate" and len(args)>=2: return out(self.builder.set_exit(character, args[0], {"target_room_id": args[1]}, True))
        if cmd == "exset" and len(args)>=3: return out(self.builder.set_exit(character, args[0], {args[1]: self._builder_value(raw,3)}))
        if cmd == "exdelete" and args:
            d=self.builder.load(world_id); before=d.get("rooms",{}).setdefault(room_id,{"id":room_id}).setdefault("exits",{}).pop(args[0],None); self.builder.save_drafts(world_id,d); self.builder.audit(character,world_id,"exdelete","exit",f"{room_id}:{args[0]}",before,None); return CommandResult(narrative=f"Draft exit {args[0]} deleted.")
        if cmd == "fcreate" and args: return out(self.builder.create_or_update(character,"rooms",room_id,{"features":{**drafts.get("rooms",{}).get(room_id,{}).get("features",{}), args[0]: {"id":args[0], "name":args[0]}}},"fcreate","feature"))
        if cmd == "fset" and len(args)>=3:
            feats=drafts.get("rooms",{}).get(room_id,{}).get("features",{}); feat={**feats.get(args[0],{"id":args[0]}), args[1]: self._builder_value(raw,3)}; feats[args[0]]=feat; return out(self.builder.create_or_update(character,"rooms",room_id,{"features":feats},"fset","feature"))
        if cmd == "fdesc" and len(args)>=2:
            feats=drafts.get("rooms",{}).get(room_id,{}).get("features",{}); feat={**feats.get(args[0],{"id":args[0]}), "long_description": self._builder_value(raw,2)}; feats[args[0]]=feat; return out(self.builder.create_or_update(character,"rooms",room_id,{"features":feats},"fdesc","feature"))
        if cmd == "fdelete" and args:
            feats=drafts.get("rooms",{}).get(room_id,{}).get("features",{}); feats.pop(args[0],None); return out(self.builder.create_or_update(character,"rooms",room_id,{"features":feats},"fdelete","feature"))
        maps={"o":"items","m":"entities","spawn":"spawns"}
        prefix = "spawn" if cmd.startswith("spawn") else cmd[0]
        coll=maps.get(prefix); target_type={"items":"item_template","entities":"entity_template","spawns":"spawn"}.get(coll, "builder")
        if coll:
            if coll == "entities":
                if cmd.endswith("create") and args:
                    updates={"id": args[0], "name": args[0].replace("_", " ").title(), "entity_type": "npc", "builder_status": "incomplete", "world_id": world_id, "area_id": getattr(character, "current_area_id", ""), "zone_id": getattr(character, "current_zone_id", getattr(character, "zone_id", "")), "keywords": args[0].split("_"), "description": "An unfinished mobile prototype stands here.", "level": 1, "attributes": {}, "resources": {"health": 10}}
                    return out(self.builder_service.create_or_update_mobile(character, args[0], updates, cmd))
                if cmd.endswith("set") and len(args)>=3: return out(self.builder_service.create_or_update_mobile(character, args[0], {args[1]: self._builder_value(raw,3)}, cmd))
                if cmd.endswith("desc") and len(args)>=2: return out(self.builder_service.create_or_update_mobile(character, args[0], {"long_description": self._builder_value(raw,2), "description": self._builder_value(raw,2)}, cmd))
                if cmd.endswith("delete") and args: return out(self.builder_service.delete_mobile(character, args[0]))
                if cmd.endswith("stat") and args: return CommandResult(narrative=f"Draft {target_type}: {drafts.get(coll,{}).get(args[0],{})}")
            if coll == "items":
                if cmd in {"oedit", "ostat"} and args: return out(self.builder_service.object_menu(character, args[0]))
                if cmd == "opreview" and args: return out(self.builder_service.preview(character, "items", args[0]))
                if cmd == "ovalidate" and args: return out(self.builder_service.validate_object(character, "items", args[0]))
                if cmd == "owhere" and args: return out(self.builder_service.object_dependencies(character, args[0]))
                if cmd == "ofind": return out(self.builder_service.search(character, " ".join(args)))
                if cmd.endswith("create") and args: return out(self.builder_service.create_or_update_object(character, args[0], {"id": args[0]}, cmd))
                if cmd.endswith("set") and len(args)>=3: return out(self.builder_service.create_or_update_object(character, args[0], {args[1]: self._builder_value(raw,3)}, cmd))
                if cmd.endswith("desc") and len(args)>=2: return out(self.builder_service.create_or_update_object(character, args[0], {"long_description": self._builder_value(raw,2), "look_description": self._builder_value(raw,2)}, cmd))
            if cmd.endswith("create") and args:
                updates={"name": args[0]}
                if coll=="spawns" and len(args)>1: updates["entity_template_id"]=args[1]; updates.setdefault("room_id", room_id)
                return out(self.builder.create_or_update(character, coll, args[0], updates, cmd, target_type))
            if cmd.endswith("set") and len(args)>=3: return out(self.builder.create_or_update(character, coll, args[0], {args[1]: self._builder_value(raw,3)}, cmd, target_type))
            if cmd.endswith("desc") and len(args)>=2: return out(self.builder.create_or_update(character, coll, args[0], {"long_description": self._builder_value(raw,2)}, cmd, target_type))
            if cmd.endswith("delete") and args: return out(self.builder.delete(character, coll, args[0], target_type))
            if cmd.endswith("stat") and args: return CommandResult(narrative=f"Draft {target_type}: {drafts.get(coll,{}).get(args[0],{})}")
        if cmd in {"zstat","astat","wstat"}: return CommandResult(narrative=f"{cmd}: world_id={world_id} room_id={room_id} builder_drafts={ {k: len(v) for k,v in drafts.items()} }")
        return CommandResult(narrative=f"Usage error for {cmd}.", ok=False)

    def _cmd_wizhelp(self, character: Any, args: list[str], raw: str) -> CommandResult:
        """Display admin help."""
        narrative = """
Admin commands:
  goto <room> - Jump to a room
  stat <char> - View character stats
  restore <char> - Restore character to full health
  wizhelp - This help
  
Builder commands:
  dig <dir> <room> - Create exit
  redit - Edit room
  oedit - Edit object
  medit - Edit mobile/NPC
  zedit - Edit zone
"""
        print(f"[mud-command] Admin help shown to {character.name}")
        return CommandResult(narrative=narrative)

    def _cmd_goto(self, character: Any, args: list[str], raw: str) -> CommandResult:
        """Teleport to room."""
        if not args:
            return CommandResult(narrative="Syntax: goto <room_id>")
        
        room_id = args[0]
        character.room_id = room_id
        narrative = f"You have been transferred to {room_id}."
        if getattr(character, "builder_mode", False) and self._effective_role(character) in {"builder", "admin", "owner"}:
            setattr(character, "edit_room_id", room_id); setattr(character, "last_edited_target", room_id)
            self.builder.publish("builder_edit_target_changed", character, self.builder.world_id(character), "room", room_id, command=raw)
            narrative += "\n" + self._builder_room_status(character, room_id, self.builder.load(self.builder.world_id(character)))
        
        print(f"[mud-command] Admin teleport: {character.name} -> {room_id}")
        if self.state_store:
            self.state_store.audit_builder_action(
                character.id, "goto", "room", room_id, {"previous_room": "unknown"}
            )
        
        return CommandResult(narrative=narrative)


    def _cmd_combat_foundation(self, character: Any, args: list[str], raw: str) -> CommandResult:
        """Route live combat commands to the canonical CombatRuntimeService."""
        rt = getattr(self, "runtime", None)
        svc = getattr(rt, "combat_runtime", None) if rt else getattr(self, "combat_runtime", None)
        raw_name = (raw.split() or [""])[0].lower(); cmd = "target" if raw_name == "target" else (self.resolve_alias(raw_name) or raw_name)
        if not svc:
            if cmd == "consider":
                return CommandResult("Consider whom?" if not args else f"You consider {' '.join(args)}. They look comparable to you.")
            if cmd == "diagnose":
                return CommandResult("Diagnose whom?" if not args else f"{' '.join(args)} appears alive and alert.")
            return CommandResult("Combat runtime is unavailable.", ok=False)
        query = " ".join(args).strip()
        if cmd == "combat":
            return CommandResult(svc.status(character))
        if cmd == "consider":
            return CommandResult("Consider whom?" if not query else svc.consider(character, query))
        if cmd == "diagnose":
            return CommandResult("Diagnose whom?" if not query else svc.diagnose(character, query))
        if cmd == "flee":
            res = svc.flee(character, query)
            return CommandResult("\n".join(res.messages), ok=res.ok, state_updates={"render_room": res.ok})
        if cmd == "defend":
            res = svc.defend(character)
            return CommandResult("\n".join(res.messages), ok=res.ok)
        if cmd == "target":
            if not query:
                return CommandResult("Target whom?", ok=False)
            res = svc.target(character, query)
            return CommandResult("\n".join(res.messages), ok=res.ok)
        if cmd == "assist":
            res = svc.assist(character, query)
            return CommandResult("\n".join(res.messages), ok=res.ok)
        res = svc.start_player_attack(character, query)
        return CommandResult("\n".join(res.messages), ok=res.ok)

    def _cmd_stat(self, character: Any, args: list[str], raw: str) -> CommandResult:
        """View character stats (admin)."""
        if not args:
            target = character
            target_name = "yourself"
        else:
            target_name = args[0]
            # Stub: would look up character
            narrative = f"Character '{target_name}' not found."
            return CommandResult(narrative=narrative)
        
        narrative = f"""
Character: {target.name}
Role: {target.role}
Level: {target.level}
HP: {target.hp}/{target.max_hp}
Mana: {target.mana}/{target.max_mana}
XP: {target.xp}
"""
        return CommandResult(narrative=narrative)

    def _placeholder_for(self, cmd_name: str) -> str:
        placeholders = {
            "spells": "You know no spells.", "skills": "You know no skills.", "abilities": "You have no abilities.", "affects": "You have no active affects.",
            "commands": "Type COMMANDS to list available commands.", "exits": "Visible exits are shown in the room display.", "where": "You are here.",
            "weather": "The weather is calm.", "time": "Time passes steadily in Smart MUD.", "levels": "Level progression is tracked in your character record.",
            "consider": "You do not sense anything unusual.", "diagnose": "You do not sense anything unusual.", "taste": "You taste nothing unusual.",
            "fill": "You have no liquid container ready for that.", "pour": "You have no liquid container ready for that.", "read": "There is nothing readable here.",
            "use": "You find no obvious way to use that.", "identify": "You identify it but learn nothing unusual.", "follow": "You are not following anyone.",
            "unfollow": "You are not following anyone.", "mount": "There is no mount ready here.", "dismount": "There is no mount ready here.",
            "tell": "Private tells are unavailable in this context.", "reply": "You have nobody to reply to.", "ask": "Ask whom about what?", "whisper": "Whisper to whom?",
            "gossip": "Global channels are quiet right now.", "shout": "You shout, but no one distant answers.", "holler": "You holler, but no one distant answers.",
            "socials": "No social command list is available here.", "recall": "No recall destination is available right now.", "practice": "Find a trainer and use PRACTICE to review available lessons.", "train": "Find a trainer and use TRAIN to review available lessons.", "study": "There is nothing here to study.",
        }
        meta = getattr(self, "registry", None).commands.get(cmd_name) if getattr(self, "registry", None) else None
        if meta and meta.short_help and meta.status.startswith("future"):
            return meta.short_help
        return placeholders.get(cmd_name, f"The {cmd_name.upper()} command is unavailable in this context.")

    def resolve_alias(self, cmd: str) -> str:
        """Resolve command aliases to canonical command."""
        resolved, kind = self.registry.resolve(cmd)
        if kind.startswith("ambiguous"):
            return ""
        return resolved
