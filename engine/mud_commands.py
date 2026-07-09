"""Smart MUD command engine with deterministic and hybrid routing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Callable
import re


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
    "look": {"category": "movement", "aliases": ["l"], "admin": False},
    "examine": {"category": "movement", "admin": False},
    "get": {"category": "item", "aliases": ["take"], "admin": False},
    "drop": {"category": "item", "admin": False},
    "wear": {"category": "item", "admin": False},
    "remove": {"category": "item", "aliases": ["rem"], "admin": False},
    "wield": {"category": "item", "admin": False},
    "unwield": {"category": "item", "admin": False},
    "hold": {"category": "item", "admin": False},
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
            "help": self._cmd_help,
            "commands": self._cmd_commands,
            "look": self._cmd_look,
            "say": self._cmd_say,
            "emote": self._cmd_emote,
            
            # Admin
            "wizhelp": self._cmd_wizhelp,
            "goto": self._cmd_goto,
            "stat": self._cmd_stat,
        }

    def handle_command(self, character: Any, command_text: str) -> CommandResult:
        """Route command to deterministic handler or AI."""
        cmd_tokens = command_text.strip().split()
        if not cmd_tokens:
            return CommandResult(narrative="")
        
        raw_cmd_name = cmd_tokens[0].lower()
        cmd_name = self.resolve_alias(raw_cmd_name)
        args = cmd_tokens[1:]
        self._publish("command_received", character, command_text, raw_input=command_text, canonical_command=raw_cmd_name, arguments=args, current_room_id=getattr(character, "room_id", ""))
        
        print(f"[mud-command] Routing {raw_cmd_name} as {cmd_name} for {character.name}")
        
        # Check if admin command
        if cmd_name in DETERMINISTIC_COMMANDS and DETERMINISTIC_COMMANDS[cmd_name].get("admin"):
            if character.role not in ["admin", "implementor"]:
                print(f"[mud-command] Access denied: {character.name} not admin")
                result = CommandResult(narrative="You do not have permission for that command.")
                self._publish("command_executed", character, command_text, raw_input=command_text, canonical_command=cmd_name, arguments=args, current_room_id=getattr(character, "room_id", ""), result_summary=result.narrative[:120])
                return result
        
        # Route to deterministic handler if exists
        if cmd_name in self.command_handlers:
            print(f"[mud-command] Deterministic: {cmd_name}")
            result = self.command_handlers[cmd_name](character, args, command_text)
            self._publish("command_executed", character, command_text, raw_input=command_text, canonical_command=cmd_name, arguments=args, current_room_id=getattr(character, "room_id", ""), result_summary=(result.narrative or "render_room")[:120])
            return result
        
        # Known deterministic command with no specific handler
        if cmd_name in DETERMINISTIC_COMMANDS:
            print(f"[mud-command] Known deterministic placeholder: {cmd_name}")
            result = CommandResult(narrative=self._placeholder_for(cmd_name))
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
        result = CommandResult(narrative="Unknown command. Type HELP or COMMANDS.", ok=False)
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

    def _cmd_score(self, character: Any, args: list[str], raw: str) -> CommandResult:
        """Display character score (stats)."""
        narrative = f"""
Name: {character.name}
Level: {character.level}
HP: {character.hp}/{character.max_hp}
Mana: {character.mana}/{character.max_mana}
Stamina: {character.stamina}/{character.max_stamina}
XP: {character.xp}
Gold: {character.gold}
Role: {character.role}
"""
        print(f"[mud-command] Score displayed for {character.name}")
        return CommandResult(narrative=narrative)

    def _cmd_inventory(self, character: Any, args: list[str], raw: str) -> CommandResult:
        """Display inventory."""
        if not character.inventory:
            narrative = "You are not carrying anything."
        else:
            items = "\n".join([f"  {i.get('name', 'unknown')} x{i.get('quantity', 1)}" 
                              for i in character.inventory])
            narrative = f"You are carrying:\n{items}"
        
        print(f"[mud-command] Inventory for {character.name}")
        return CommandResult(narrative=narrative)

    def _cmd_equipment(self, character: Any, args: list[str], raw: str) -> CommandResult:
        """Display equipped items."""
        if not character.equipment:
            narrative = "You are not wearing anything."
        else:
            slots = "\n".join([f"  <{slot}> {item.get('name', 'empty')}" 
                              for slot, item in character.equipment.items()])
            narrative = f"You are wearing:\n{slots}"
        
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
        narrative = f"You have {character.gold} gold coins."
        return CommandResult(narrative=narrative)

    def _cmd_who(self, character: Any, args: list[str], raw: str) -> CommandResult:
        """List connected players."""
        narrative = f"Players currently online:\n{character.name}"
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
        """Look around (stub - real impl in mud_displays)."""
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
            narrative = f"Help on '{topic}' is not available."
        
        return CommandResult(narrative=narrative)

    def _cmd_commands(self, character: Any, args: list[str], raw: str) -> CommandResult:
        """List available commands."""
        cmds = list(DETERMINISTIC_COMMANDS.keys())
        # Filter out admin commands for non-admins
        if character.role not in ["admin", "implementor"]:
            cmds = [c for c in cmds if not DETERMINISTIC_COMMANDS[c].get("admin", False)]
        
        narrative = f"Available commands ({len(cmds)}):\n  " + " ".join(sorted(cmds))
        return CommandResult(narrative=narrative)

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
            "spells": "You know no spells.",
            "skills": "You know no skills.",
            "abilities": "You have no abilities.",
            "affects": "You have no active affects.",
            "commands": "Type COMMANDS to list available commands.",
        }
        return placeholders.get(cmd_name, f"The {cmd_name.upper()} command is not available yet.")

    def resolve_alias(self, cmd: str) -> str:
        """Resolve command aliases to canonical command."""
        for canonical, info in DETERMINISTIC_COMMANDS.items():
            if cmd == canonical or cmd in info.get("aliases", []):
                return canonical
        return cmd
