"""Smart MUD command engine with deterministic and hybrid routing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Callable
import re
from engine.mud_displays import semantic
from engine.command_registry import CommandRegistry
from smart_mud.builder import BuilderWorkspace


@dataclass
class CommandResult:
    """Result of command execution."""
    narrative: str
    prompt: str = ""
    scrollback: str = ""
    state_updates: dict[str, Any] = None
    should_exit: bool = False
    ok: bool = True


# Known deterministic commands (no AI needed)
DETERMINISTIC_COMMANDS = {
    # Information
    "score": {"category": "info", "aliases": ["sc"], "admin": False},
    "worth": {"category": "info", "admin": False},
    "finger": {"category": "info", "admin": False},
    "inventory": {"category": "info", "aliases": ["inv", "i"], "admin": False},
    "equipment": {"category": "info", "aliases": ["eq"], "admin": False},
    "spells": {"category": "info", "aliases": ["sp"], "admin": False},
    "skills": {"category": "info", "aliases": ["sk"], "admin": False},
    "abilities": {"category": "info", "admin": False},
    "affects": {"category": "info", "aliases": ["aff"], "admin": False},
    "resists": {"category": "info", "admin": False},
    "who": {"category": "info", "admin": False},
    "whoami": {"category": "info", "admin": False},
    "where": {"category": "info", "admin": False},
    "commands": {"category": "help", "aliases": ["cmds"], "admin": False},
    "help": {"category": "help", "aliases": ["h"], "admin": False},
    "socials": {"category": "help", "admin": False},
    "areas": {"category": "info", "admin": False},
    "map": {"category": "info", "admin": False},
    "time": {"category": "info", "admin": False},
    "weather": {"category": "info", "admin": False},
    "practice": {"category": "info", "aliases": ["prac"], "admin": False},
    "train": {"category": "shop", "admin": False},
    "study": {"category": "shop", "admin": False},
    "list": {"category": "shop", "admin": False},
    "buy": {"category": "shop", "admin": False},
    "sell": {"category": "shop", "admin": False},
    "value": {"category": "shop", "admin": False},
    "consider": {"category": "combat", "aliases": ["con"], "admin": False},
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
    "look": {"category": "movement", "aliases": ["l", "glance", "scan"], "admin": False},
    "examine": {"category": "movement", "admin": False},
    "identify": {"category": "interaction", "aliases": ["id"], "admin": False},
    "use": {"category": "interaction", "admin": False},
    "read": {"category": "interaction", "admin": False},
    "pray": {"category": "interaction", "admin": False},
    "touch": {"category": "interaction", "admin": False},
    "push": {"category": "interaction", "admin": False},
    "pull": {"category": "interaction", "admin": False},
    "climb": {"category": "interaction", "admin": False},
    "get": {"category": "item", "aliases": ["take", "pickup"], "admin": False},
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
    "sit": {"category": "interaction", "admin": False},
    "stand": {"category": "interaction", "admin": False},
    "rest": {"category": "interaction", "admin": False},
    "sleep": {"category": "interaction", "admin": False},
    "wake": {"category": "interaction", "admin": False},
    "talk": {"category": "communication", "admin": False},
    "greet": {"category": "communication", "admin": False},
    "hello": {"category": "communication", "admin": False},
    "give": {"category": "interaction", "admin": False},
    "put": {"category": "interaction", "admin": False},
    "say": {"category": "communication", "admin": False},
    "emote": {"category": "communication", "admin": False},
    
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
        self.command_handlers: dict[str, Callable] = {
            # Info commands
            "score": self._cmd_score,
            "worth": self._cmd_worth,
            "inventory": self._cmd_inventory,
            "equipment": self._cmd_equipment,
            "spells": self._cmd_spells,
            "skills": self._cmd_skills,
            "abilities": self._cmd_abilities,
            "affects": self._cmd_affects,
            "who": self._cmd_who,
            "whoami": self._cmd_whoami,
            "save": self._cmd_save,
            "desc": self._cmd_builder_edit,
            "recall": self._cmd_generic,
            "grantrole": self._cmd_grantrole,
            "help": self._cmd_help,
            "commands": self._cmd_commands,
            "look": self._cmd_look,
            "say": self._cmd_say,
            "emote": self._cmd_emote,
            "study": self._cmd_generic,
            "train": self._cmd_generic,
            "practice": self._cmd_generic,
            "socials": self._cmd_generic,
            "holler": self._cmd_generic,
            "shout": self._cmd_generic,
            "gossip": self._cmd_generic,
            "whisper": self._cmd_generic,
            "ask": self._cmd_generic,
            "reply": self._cmd_generic,
            "tell": self._cmd_generic,
            "prompt": self._cmd_generic,
            "afk": self._cmd_generic,
            "automap": self._cmd_generic,
            "autosplit": self._cmd_generic,
            "autogold": self._cmd_generic,
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
            "diagnose": self._cmd_generic,
            "consider": self._cmd_generic,
            "levels": self._cmd_generic,
            "time": self._cmd_generic,
            "weather": self._cmd_generic,
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
            "astat": self._cmd_builder_nav,
            "aset": self._cmd_builder_nav,
            "zones": self._cmd_builder_nav,
            "zlist": self._cmd_builder_nav,
            "zstat": self._cmd_builder_nav,
            "zset": self._cmd_builder_nav,
            "dig": self._cmd_dig,
            "link": self._cmd_link,
            "unlink": self._cmd_unlink,
            "exits": self._cmd_builder_nav,
            "x": self._cmd_builder_nav,
            "back": self._cmd_builder_nav,
            "forward": self._cmd_builder_nav,
            "bstatus": self._cmd_builder,
            "status": self._cmd_builder,

            # Builder foundation
            "builder": self._cmd_builder,
            "build": self._cmd_builder,
            # Admin
            "wizhelp": self._cmd_wizhelp,
            "goto": self._cmd_goto,
            "stat": self._cmd_stat,
        }
        for _name in " rsave redit rstat rcreate rset rdesc rname rexits rfeature rdelete exedit excreate exset exdelete fedit fcreate fset fdesc fdelete oedit ocreate oset odesc odelete ostat medit mcreate mset mdesc mdelete mstat spawnedit spawncreate spawnset spawndelete spawnstat zstat astat wstat btarget rtarget target asave bsave wsave".split():
            if _name:
                self.command_handlers[_name] = self._cmd_builder_edit

    def handle_command(self, character: Any, command_text: str) -> CommandResult:
        """Route command to deterministic handler or AI."""
        cmd_tokens = command_text.strip().split()
        if not cmd_tokens:
            return CommandResult(narrative="")
        
        raw_cmd_name = cmd_tokens[0].lower()
        cmd_name = self.resolve_alias(raw_cmd_name)
        if raw_cmd_name in self.command_handlers and not cmd_name:
            cmd_name = raw_cmd_name
        if not cmd_name:
            choices = self.registry.resolve(raw_cmd_name)[1].split(":",1)[1].strip()
            return CommandResult(narrative=f"Which command did you mean? {choices}", ok=False)
        args = cmd_tokens[1:]
        self._publish("command_received", character, command_text, raw_input=command_text, canonical_command=raw_cmd_name, arguments=args, current_room_id=getattr(character, "room_id", ""))
        
        print(f"[mud-command] Routing {raw_cmd_name} as {cmd_name} for {character.name}")
        
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
            result = self.command_handlers[cmd_name](character, args, command_text)
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
        
        # Fallback
        print(f"[mud-command] Unknown command: {cmd_name}")
        self._publish("command_unknown", character, command_text, raw_input=command_text, canonical_command=cmd_name, arguments=args, current_room_id=getattr(character, "room_id", ""), result_summary="unknown")
        result = CommandResult(narrative=semantic("error", "Unknown command. Type HELP or COMMANDS."), ok=False)
        self._publish("command_executed", character, command_text, raw_input=command_text, canonical_command=cmd_name, arguments=args, current_room_id=getattr(character, "room_id", ""), result_summary=result.narrative[:120])
        return result


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

    def _cmd_score(self, character: Any, args: list[str], raw: str) -> CommandResult:
        """Display character score (stats)."""
        narrative = "\n".join([
            f"{semantic('score_label', 'Name:')} {semantic('player', character.name)}",
            f"{semantic('score_label', 'Level:')} {semantic('score_value', character.level)}",
            f"{semantic('hp', 'HP:')} {semantic('score_value', f'{character.hp}/{character.max_hp}')}",
            f"{semantic('mp', 'Mana:')} {semantic('score_value', f'{character.mana}/{character.max_mana}')}",
            f"{semantic('stamina', 'Stamina:')} {semantic('score_value', f'{character.stamina}/{character.max_stamina}')}",
            f"{semantic('score_label', 'XP:')} {semantic('score_value', character.xp)}",
            f"{semantic('gold', 'Gold:')} {semantic('gold', character.gold)}",
            f"{semantic('score_label', 'Character Role:')} {semantic('score_value', getattr(character, 'role', 'player'))}",
            f"{semantic('score_label', 'Account Role:')} {semantic('score_value', getattr(character, 'account_role', 'player'))}",
        ])
        print(f"[mud-command] Score displayed for {character.name}")
        return CommandResult(narrative=narrative)

    def _cmd_inventory(self, character: Any, args: list[str], raw: str) -> CommandResult:
        """Display inventory."""
        if not character.inventory:
            narrative = semantic("system", "You are not carrying anything.")
        else:
            items = "\n".join([f"  {semantic('item_' + str(i.get('rarity', 'common')), i.get('name', 'unknown'))} x{i.get('quantity', 1)}" 
                              for i in character.inventory])
            narrative = f"{semantic('system', 'You are carrying:')}\n{items}"
        
        print(f"[mud-command] Inventory for {character.name}")
        return CommandResult(narrative=narrative)

    def _cmd_equipment(self, character: Any, args: list[str], raw: str) -> CommandResult:
        """Display equipped items."""
        if not character.equipment:
            narrative = semantic("system", "You are not wearing anything.")
        else:
            slots = "\n".join([f"  {semantic('equipment_slot', slot)}: {semantic('equipment_item', item.get('name', 'empty') if item else 'nothing')}" 
                              for slot, item in character.equipment.items()])
            narrative = f"{semantic('system', 'You are wearing:')}\n{slots}"
        
        print(f"[mud-command] Equipment for {character.name}")
        return CommandResult(narrative=narrative)

    def _cmd_spells(self, character: Any, args: list[str], raw: str) -> CommandResult:
        """Display known spells."""
        spells = [a for a in character.abilities if a.startswith("spell_")]
        if not spells:
            narrative = "You know no spells."
        else:
            narrative = f"You know: {', '.join(spells)}"
        
        return CommandResult(narrative=narrative)

    def _cmd_skills(self, character: Any, args: list[str], raw: str) -> CommandResult:
        """Display known skills."""
        skills = [a for a in character.abilities if a.startswith("skill_")]
        if not skills:
            narrative = "You know no skills."
        else:
            narrative = f"You know: {', '.join(skills)}"
        
        return CommandResult(narrative=narrative)

    def _cmd_abilities(self, character: Any, args: list[str], raw: str) -> CommandResult:
        """Display abilities."""
        if not character.abilities:
            narrative = "You have no abilities."
        else:
            narrative = f"Your abilities:\n" + "\n".join(f"  {a}" for a in character.abilities)
        
        return CommandResult(narrative=narrative)

    def _cmd_affects(self, character: Any, args: list[str], raw: str) -> CommandResult:
        """Display active affects/buffs."""
        if not character.affects:
            narrative = "You have no active affects."
        else:
            narrative = "Active affects:\n" + "\n".join(
                f"  {k}: {v}" for k, v in character.affects.items()
            )
        
        return CommandResult(narrative=narrative)

    def _cmd_worth(self, character: Any, args: list[str], raw: str) -> CommandResult:
        """Display net worth."""
        narrative = f"{semantic('system', 'You have')} {semantic('gold', character.gold)} {semantic('gold', 'gold coins.')}"
        return CommandResult(narrative=narrative)

    def _cmd_who(self, character: Any, args: list[str], raw: str) -> CommandResult:
        """List connected players."""
        narrative = f"{semantic('system', 'Players currently online:')}\n{semantic('player', character.name)}"
        return CommandResult(narrative=narrative)

    def _cmd_say(self, character: Any, args: list[str], raw: str) -> CommandResult:
        text = raw.split(maxsplit=1)[1] if len(raw.split(maxsplit=1)) > 1 else ""
        if not text:
            return CommandResult(narrative="Say what?")
        return CommandResult(narrative=f'You say, "{text}."' if not text.endswith((".", "!", "?")) else f'You say, "{text}"')

    def _cmd_emote(self, character: Any, args: list[str], raw: str) -> CommandResult:
        text = raw.split(maxsplit=1)[1] if len(raw.split(maxsplit=1)) > 1 else ""
        if not text:
            return CommandResult(narrative="Emote what?")
        return CommandResult(narrative=f"{character.name} {text}")

    def _cmd_look(self, character: Any, args: list[str], raw: str) -> CommandResult:
        """Look around or at draft Builder features when present."""
        if args:
            room_id = self.builder.current_room_id(character)
            features = self.builder.load(self.builder.world_id(character)).get("rooms", {}).get(room_id, {}).get("features", {})
            target = args[0].lower()
            for fid, feature in features.items():
                keys = [fid, feature.get("name", ""), *(feature.get("keywords", []) if isinstance(feature.get("keywords"), list) else [])]
                if target in [str(k).lower() for k in keys if k]:
                    return CommandResult(narrative=feature.get("long_description") or feature.get("short_description") or feature.get("name") or fid)
        return CommandResult(narrative="", state_updates={"render_room": True})

    def _cmd_help(self, character: Any, args: list[str], raw: str) -> CommandResult:
        """Display help."""
        if not args:
            narrative = """
Available commands:
  score - Display your stats
  inventory - List your items
  equipment - Show worn items
  look - Examine surroundings
  help <topic> - Get help on a topic
  """
        else:
            topic = args[0].lower()
            resolved = self.resolve_alias(topic) or topic
            meta = self.registry.commands.get(resolved)
            self._publish("command_help_requested", character, raw, topic=topic, resolved_command=resolved)
            if meta:
                narrative = f"Command: {meta.command}\nPurpose: {meta.long_help or meta.short_help}\nUsage: {meta.usage or meta.command}\nAliases: {', '.join(meta.aliases) if meta.aliases else 'none'}\nCategory: {meta.category}\nStatus: {meta.status}"
            else:
                narrative = f"Help on '{topic}' is not available."
        
        return CommandResult(narrative=narrative)

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
        if cmd == "prompt":
            return CommandResult(narrative="Smart MUD uses a pinned web prompt separate from scrollback. Configure the web prompt through Smart MUD settings; future telnet prompt customization is planned.")
        self._publish("command_placeholder_used", character, raw, canonical_command=cmd)
        return CommandResult(narrative=self._placeholder_for(cmd))


    def _builder_value(self, text: str, count: int) -> str:
        parts = text.split(maxsplit=count)
        return parts[count] if len(parts) > count else ""

    def _cmd_builder_nav(self, character: Any, args: list[str], raw: str) -> CommandResult:
        runtime = getattr(self, "runtime", None)
        cmd = raw.strip().split()[0].lower()
        if runtime and hasattr(runtime, "_builder_nav_command"):
            res = runtime._builder_nav_command(character, cmd, args, raw)
            if res is not None:
                return res
        if cmd in {"areas", "alist", "astat", "aset", "zones", "zlist", "zstat", "zset"}:
            if cmd in {"aset", "zset"} and len(args) >= 2 and args[0] == "current":
                setattr(character, "current_area_id" if cmd == "aset" else "current_zone_id", args[1])
                self.builder.publish("builder_area_context_changed" if cmd == "aset" else "builder_zone_context_changed", character, self.builder.world_id(character), "context", args[1], command=raw)
                return CommandResult(f"Current {'area' if cmd == 'aset' else 'zone'} set to {args[1]}.")
            return CommandResult(f"{cmd}: context only. Current area={getattr(character,'current_area_id','')} zone={getattr(character,'current_zone_id','')}.")
        return CommandResult(f"{cmd} requires the MudRuntime builder overlay.", ok=False)

    def _reverse_dir(self, direction: str) -> str:
        return {"north":"south","south":"north","east":"west","west":"east","up":"down","down":"up","in":"out","out":"in"}.get(direction, "")

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
        direction, rid = args[0].lower(), args[1]
        if not self._valid_room_id(rid):
            self.builder.publish("builder_dig_rejected", character, self.builder.world_id(character), "room", rid, command=raw)
            return CommandResult(self._room_id_usage(rid, "dig"), ok=False)
        one_way = "--one-way" in args
        allow_self_loop = "--allow-self-loop" in args
        name_parts = [a for a in args[2:] if a not in {"--one-way", "--allow-self-loop"}]
        if len(name_parts) > 1 and '"' not in raw and "'" not in raw:
            return CommandResult(usage, ok=False)
        name = " ".join(name_parts) or rid.replace("_", " ").title()
        world_id = self.builder.world_id(character); old = self.builder.current_room_id(character)
        if rid == old and not allow_self_loop:
            return CommandResult("Self-loop exits are blocked. Use --allow-self-loop to create one intentionally.", ok=False)
        self.builder.create_or_update(character, "rooms", rid, {"name": name, "description": "", "area_id": getattr(character,"current_area_id", getattr(character,"area_id", "")), "zone_id": getattr(character,"current_zone_id", getattr(character,"zone_id", "")), "world_id": world_id, "exits": {}, "features": {}}, "dig", "room")
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
        return CommandResult(f"Dug {direction} to {rid}.\n" + "\n".join(["Created room:", "", "ID:", rid, "", "Name:", name, "", "Linked:", "", old, f"{direction.title()} -> {rid}", "", rid, f"{self._reverse_dir(direction).title()} -> {old}" if not one_way and self._reverse_dir(direction) else "", "", "Editing:", rid]) + "\n" + self._builder_room_status(character, rid, self.builder.load(world_id)), state_updates={"render_room": True})

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

    def _cmd_builder(self, character: Any, args: list[str], raw: str) -> CommandResult:
        sub = args[0].lower() if args else "status"
        if raw.strip().split()[0].lower() in {"bstatus", "status"}:
            sub = "status"
        if sub in {"on", "enable"} or raw.split()[0].lower() == "build":
            res = self.builder.set_builder_mode(character, True)
            status = self._builder_room_status(character, self.builder.current_room_id(character), self.builder.load(self.builder.world_id(character))) if res.ok else ""
            return CommandResult(narrative=res.message + (("\n" + status) if status else ""), ok=res.ok)
        if sub in {"off", "disable"}:
            res = self.builder.set_builder_mode(character, False)
            return CommandResult(narrative=res.message, ok=res.ok)
        if sub == "validate":
            res = self.builder.validate(character); return CommandResult(narrative=res.message + "\n" + self._builder_room_status(character, self.builder.current_room_id(character), self.builder.load(self.builder.world_id(character))), ok=res.ok)
        if sub == "save":
            res = self.builder.export(character); return CommandResult(narrative=res.message + "\n" + self._builder_room_status(character, self.builder.current_room_id(character), self.builder.load(self.builder.world_id(character))), ok=res.ok)
        if sub == "reload":
            self.builder.publish("builder_reload_requested", character, self.builder.world_id(character), "builder", "reload", command="builder reload")
            return CommandResult(narrative="Builder drafts reloaded from workspace.\n" + self._builder_room_status(character, self.builder.current_room_id(character), self.builder.load(self.builder.world_id(character))))
        if sub == "snapshot":
            res = self.builder.snapshot(character); return CommandResult(narrative=res.message + "\n" + self._builder_room_status(character, self.builder.current_room_id(character), self.builder.load(self.builder.world_id(character))), ok=res.ok)
        if sub == "history":
            res = self.builder.history(character); return CommandResult(narrative=res.message, ok=res.ok)
        if sub == "status":
            return CommandResult(narrative=self._builder_room_status(character, self.builder.current_room_id(character), self.builder.load(self.builder.world_id(character))))
        return CommandResult(narrative=f"Builder mode is {'ON' if getattr(character, 'builder_mode', False) else 'OFF'}. Use builder on/off, builder validate, builder save, builder snapshot, builder history.")

    def _builder_room_status(self, character: Any, room_id: str, drafts: dict[str, Any]) -> str:
        runtime = getattr(self, "runtime", None)
        loc_id = str(getattr(character, "room_id", "") or getattr(character, "current_room_id", "") or "start")
        def info(rid: str):
            draft = drafts.get("rooms", {}).get(rid)
            live = runtime.runtime_room_data(character, rid)[0] if runtime and hasattr(runtime, "runtime_room_data") else None
            rec = draft or live or {}
            return (rec.get("name") or rec.get("title") or "(unnamed)", "draft" if draft is not None else "live" if live is not None else "unknown", draft is not None)
        loc_name, loc_source, _ = info(loc_id)
        lines = ["Builder Status:", "================================================", "Builder Mode", "", "Location:", loc_id, "", "Currently editing:", "Editing:"]
        if not room_id:
            lines.append("none")
        else:
            name, source, dirty = info(room_id)
            lines += [f"Room: {room_id}", f"Name: {name}", f"Source: {source}", f"Dirty: {'yes' if dirty else 'no'}", f"Editing room: {room_id} {name}"]
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
            if len(args) != 1:
                return CommandResult(self._room_id_usage(" ".join(args), "rcreate"), ok=False)
            rid = args[0]
            if not self._valid_room_id(rid):
                return CommandResult(self._room_id_usage(rid, "rcreate"), ok=False)
            setattr(character, "last_room_id", getattr(character, "room_id", room_id)); setattr(character, "room_id", rid); setattr(character, "edit_room_id", rid); setattr(character, "last_edited_target", rid); setattr(character, "last_created_room_id", rid)
            res = self.builder.create_or_update(character, "rooms", rid, {"area_id": getattr(character,"current_area_id", getattr(character,"area_id", "")), "zone_id": getattr(character,"current_zone_id", getattr(character,"zone_id", "")), "world_id": world_id, "exits": {}, "features": {}}, "rcreate", "room")
            return CommandResult(res.message + "\n" + self._builder_room_status(character, rid, self.builder.load(world_id)), ok=res.ok)
        if cmd == "rname":
            if not getattr(character, "edit_room_id", "") and not getattr(character, "last_edited_target", ""):
                return CommandResult("No room is currently selected. Use rcreate, redit <room_id>, goto <room_id>, or btarget room <room_id>.", ok=False)
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
            val = self._builder_value(raw,1)
            if not val:
                setattr(character, "builder_desc_editor_room_id", room_id); setattr(character, "builder_desc_editor_lines", [])
                return CommandResult("Description editor\n\nEnter description.\n\nFinish with:\n.end\n\nCancel:\n.cancel")
            res = self.builder.create_or_update(character, "rooms", room_id, {"description": val}, cmd, "room")
            name = self.builder.load(world_id).get("rooms",{}).get(room_id,{}).get("name") or "(unnamed)"
            lines=[f"Description updated for room {room_id}.", f"Room {room_id} description changed.", "Updated room:", "", "ID:", room_id, "", "Name:", name, "", "Dirty:", "yes"]
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
            "weather": "The weather is calm.", "time": "Time passes steadily in Smart MUD.", "levels": "Level progression is tracked, but level tables are not implemented yet.",
            "consider": "You do not sense anything unusual.", "diagnose": "You do not sense anything unusual.", "taste": "You taste nothing unusual.",
            "fill": "Liquid containers are not implemented yet.", "pour": "Liquid containers are not implemented yet.", "read": "There is nothing readable here.",
            "use": "You find no obvious way to use that.", "identify": "You identify it but learn nothing unusual.", "follow": "Following is not implemented yet.",
            "unfollow": "You are not following anyone.", "mount": "Mounts are not implemented yet.", "dismount": "Mounts are not implemented yet.",
            "tell": "Private tells are not implemented yet.", "reply": "You have nobody to reply to.", "ask": "Ask whom about what?", "whisper": "Whisper to whom?",
            "gossip": "Global channels are not implemented yet.", "shout": "You shout, but global shout routing is not implemented yet.", "holler": "Holler is not implemented yet.",
            "socials": "Social commands are tracked but the socials list is not implemented yet.", "recall": "Recall is tracked as a future room-changing command and is not implemented yet.", "practice": "Practice is not implemented yet.", "train": "Training is not implemented yet.", "study": "Study is not implemented yet.",
        }
        meta = getattr(self, "registry", None).commands.get(cmd_name) if getattr(self, "registry", None) else None
        if meta and meta.short_help and meta.status.startswith("future"):
            return meta.short_help
        return placeholders.get(cmd_name, f"The {cmd_name.upper()} command is not available yet.")

    def resolve_alias(self, cmd: str) -> str:
        """Resolve command aliases to canonical command."""
        resolved, kind = self.registry.resolve(cmd)
        if kind.startswith("ambiguous"):
            return ""
        return resolved
