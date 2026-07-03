"""Data-driven Smart MUD command registry and deterministic command handlers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.mud_rendering import render_room, render_semantic_plain
from engine.world_registry import WorldRegistry, by_id

DIRECTION_ALIASES = {"n":"north","s":"south","e":"east","w":"west","u":"up","d":"down","ne":"northeast","nw":"northwest","se":"southeast","sw":"southwest","enter":"in","leave":"out"}
DIRECTIONS = {"north","south","east","west","up","down","northeast","northwest","southeast","southwest","in","out", *DIRECTION_ALIASES}

@dataclass(frozen=True)
class MudCommand:
    name: str
    aliases: tuple[str, ...] = ()
    category: str = "Utility"
    required_position: str = "standing"
    min_level: int = 1
    handler_name: str = "placeholder"
    help: str = ""
    usage: str = ""
    examples: tuple[str, ...] = ()
    ai_routed: bool = False
    deterministic: bool = True
    subcommand: str | None = None

@dataclass
class MudCommandResult:
    ok: bool
    output_text: str
    semantic_output: str | None = None
    output_html: str | None = None
    prompt_update: str | None = None
    state_changes: dict[str, Any] = field(default_factory=dict)
    save_required: bool = False
    ai_required: bool = False
    ai_context: dict[str, Any] | None = None

@dataclass
class ParsedMudCommand:
    raw: str
    verb: str
    args: str
    command: MudCommand | None = None
    error: str = ""
    unknown: bool = False

class MudCommandRegistry:
    def __init__(self) -> None:
        self.commands: dict[str, MudCommand] = {}
        self.aliases: dict[str, str] = {}

    def register(self, command: MudCommand) -> None:
        self.commands[command.name] = command
        for alias in command.aliases:
            self.aliases[alias] = command.name

    def parse_command(self, input_text: str) -> tuple[str, str]:
        text = str(input_text or "").strip()
        if text.startswith("'") and len(text) > 1:
            return "say", text[1:].strip()
        if text.startswith(":") and len(text) > 1:
            return "emote", text[1:].strip()
        parts = text.split(maxsplit=1)
        return (parts[0].lower() if parts else "", parts[1].strip() if len(parts) > 1 else "")

    def resolve(self, input_text: str) -> ParsedMudCommand:
        raw = str(input_text or "").strip(); verb, args = self.parse_command(raw)
        if not verb:
            return ParsedMudCommand(raw, "", "", error="What do you want to do?")
        if verb == "go" and args.split(maxsplit=1)[0].lower() in DIRECTIONS:
            return ParsedMudCommand(raw, "go", args, self.commands["go"])
        if verb in DIRECTIONS:
            return ParsedMudCommand(raw, verb, args, self.commands[DIRECTION_ALIASES.get(verb, verb)])
        if verb in self.commands:
            return ParsedMudCommand(raw, verb, args, self.commands[verb])
        if verb in self.aliases:
            return ParsedMudCommand(raw, verb, args, self.commands[self.aliases[verb]])
        matches = [c for c in self.commands.values() if c.name.startswith(verb) or any(a.startswith(verb) for a in c.aliases)]
        uniq = {m.name: m for m in matches}
        if len(uniq) == 1:
            cmd = next(iter(uniq.values())); return ParsedMudCommand(raw, verb, args, cmd)
        if len(uniq) > 1:
            names = ", ".join(sorted(uniq))
            return ParsedMudCommand(raw, verb, args, error=f"Which command did you mean? {names}")
        return ParsedMudCommand(raw, verb, args, unknown=True)

    def list_commands(self, category: str | None = None) -> list[MudCommand]:
        cmds = [c for c in self.commands.values() if c.category.lower() != "developer"]
        if category:
            cmds = [c for c in cmds if c.category.lower() == category.lower()]
        return sorted(cmds, key=lambda c: (c.category, c.name))

    def get_help(self, command_name: str) -> str:
        parsed = self.resolve(command_name)
        if not parsed.command:
            return "No help is available for that command."
        c = parsed.command
        lines = [c.name, c.help or "No detailed help is available.", f"Usage: {c.usage or c.name}"]
        if c.aliases: lines.append("Aliases: " + ", ".join(c.aliases))
        if c.examples: lines.append("Examples: " + "; ".join(c.examples))
        return "\n".join(lines)

def _cmd(name, aliases=(), cat="Utility", handler="placeholder", help="", usage="", ai=False, deterministic=True):
    return MudCommand(name, tuple(aliases), cat, handler_name=handler, help=help, usage=usage, ai_routed=ai, deterministic=deterministic)

def default_registry() -> MudCommandRegistry:
    r = MudCommandRegistry()
    for d, a in [("north",("n",)),("south",("s",)),("east",("e",)),("west",("w",)),("up",("u",)),("down",("d",)),("northeast",("ne",)),("northwest",("nw",)),("southeast",("se",)),("southwest",("sw",)),("in",("enter",)),("out",("leave",))]: r.register(_cmd(d,a,"Movement","movement",f"Move {d}.",d))
    specs=[("go",(),"Movement","movement","Move in a direction.","go <direction>"),("exits",(),"Movement","exits","Show visible exits.","exits"),("look",("l",),"Looking","look","Look at the room or a target.","look [target]"),("examine",("exa",),"Looking","look","Examine a target.","examine <target>"),("inspect",(),"Looking","look","Inspect a target.","inspect <target>"),("read",(),"Looking","placeholder","Read something.","read <target>"),("scan",(),"Looking","placeholder","Scan nearby surroundings.","scan"),("score",("sc",),"Character","score","Show character score.","score"),("character",(),"Character","score","Show character sheet summary.","character"),("stats",(),"Character","stats","Show ability stats.","stats"),("inventory",("inv","i"),"Character","inventory","Show carried items.","inventory"),("equipment",("eq",),"Character","equipment","Show equipped items.","equipment"),("gold",(),"Character","gold","Show coin.","gold"),("affects",(),"Character","placeholder","Show active affects.","affects"),("skills",(),"Character","abilities","Show skills.","skills"),("spells",(),"Magic","abilities","Show spells.","spells"),("spellbook",(),"Magic","abilities","Show known spells.","spellbook"),("abilities",(),"Character","abilities","Show abilities.","abilities"),("cooldowns",("cd",),"Character","placeholder","Show cooldowns.","cooldowns"),("get",("take",),"Items","get","Get an item.","get <item>|all"),("drop",(),"Items","drop","Drop an item.","drop <item>"),("put",(),"Items","placeholder","Put an item somewhere.","put <item> <container>"),("give",(),"Items","placeholder","Give an item.","give <item> <target>"),("wear",(),"Items","equip","Wear armor.","wear <item>"),("wield",(),"Items","equip","Wield a weapon.","wield <item>"),("hold",(),"Items","equip","Hold an item.","hold <item>"),("remove",(),"Items","remove","Remove equipment.","remove <item>"),("use",(),"Items","placeholder","Use an item.","use <item>"),("quaff",(),"Items","placeholder","Quaff a potion.","quaff <item>"),("drink",(),"Items","placeholder","Drink something.","drink <item>"),("eat",(),"Items","placeholder","Eat something.","eat <item>"),("open",(),"Items","door","Open a door or object.","open <target>"),("close",(),"Items","door","Close a door or object.","close <target>"),("lock",(),"Items","door","Lock a door or object.","lock <target>"),("unlock",(),"Items","door","Unlock a door or object.","unlock <target>"),("pick",(),"Items","door","Pick a lock.","pick <target>"),("say",("'",),"Social","social","Say something.","say <message>",True,False),("tell",(),"Social","social","Tell someone something.","tell <target> <message>",True,False),("ask",(),"Social","social","Ask someone about a topic.","ask <target> about <topic>",True,False),("talk",(),"Social","social","Talk to someone.","talk <target>",True,False),("emote",(":",),"Social","social","Emote an action.","emote <action>",True,False),("whisper",(),"Social","social","Whisper.","whisper <target> <message>",True,False),("shout",(),"Social","social","Shout.","shout <message>",True,False),("reply",(),"Social","social","Reply.","reply <message>",True,False),("kill",("k",),"Combat","combat","Attack a target.","kill <target>"),("hit",(),"Combat","combat","Hit a target.","hit <target>"),("attack",(),"Combat","combat","Attack a target.","attack <target>"),("flee",(),"Combat","placeholder","Flee combat.","flee"),("assist",(),"Combat","placeholder","Assist someone.","assist <target>"),("rescue",(),"Combat","placeholder","Rescue someone.","rescue <target>"),("consider",("con",),"Combat","placeholder","Consider a foe.","consider <target>"),("appraise",(),"Combat","placeholder","Appraise a target.","appraise <target>"),("cast",("c",),"Magic","placeholder","Cast a spell.","cast <spell> [target]"),("backstab",(),"Combat","placeholder","Backstab.","backstab <target>"),("bash",(),"Combat","placeholder","Bash.","bash <target>"),("kick",(),"Combat","placeholder","Kick.","kick <target>"),("hide",(),"Combat","placeholder","Hide.","hide"),("sneak",(),"Combat","placeholder","Sneak.","sneak"),("steal",(),"Combat","placeholder","Steal.","steal <item> <target>"),("practice",("prac",),"Training","placeholder","Practice skills.","practice [skill]"),("train",(),"Training","placeholder","Train stats.","train [stat]"),("study",(),"Training","placeholder","Study.","study <subject>"),("quest",("quests",),"Quest","quests","Show quests.","quests"),("journal",(),"Quest","quests","Show journal.","journal"),("levels",(),"Training","placeholder","Show level info.","levels"),("help",("h",),"Utility","help","Show help.","help [command|category]"),("commands",("com",),"Utility","commands","List commands.","commands [category]"),("socials",(),"Social","commands","List socials.","socials"),("areas",(),"Utility","placeholder","List areas.","areas"),("map",(),"Utility","placeholder","Show map.","map"),("time",(),"Utility","placeholder","Show time.","time"),("weather",(),"Utility","placeholder","Show weather.","weather"),("history",(),"Utility","history","Show command history.","history [count]"),("clear",("cls",),"Utility","clear","Clear visible output.","clear"),("save",(),"Utility","save","Save the character.","save"),("quit",(),"Utility","quit","Quit the MUD.","quit")]
    for s in specs: r.register(_cmd(*s))
    return r

REGISTRY = default_registry()

def _item_name(item_id: str, items: dict[str, dict[str, Any]]) -> str:
    return items.get(item_id, {}).get("name") or item_id.replace("_", " ")

def execute_mud_command(state: Any, store: Any, text: str, *, history_limit: int = 100) -> MudCommandResult:
    parsed = REGISTRY.resolve(text)
    if parsed.error:
        return MudCommandResult(False, parsed.error)
    if parsed.unknown:
        return MudCommandResult(True, f"You try to {text}.", ai_required=True, ai_context={"action": text, "route": "freeform"})
    cmd = parsed.command; assert cmd
    world = WorldRegistry().load_world(state.structured_state.runtime.world_id or "shattered_realms")
    room = world.room(state.structured_state.runtime.current_room_id or world.default_starting_room_id)
    items = by_id(world.items); npcs = by_id(world.npcs); areas = by_id(world.areas)
    cid = state.player.id or "player_1"
    core = state.structured_state.runtime.player_core or {}; derived = core.get("derived_stats", {})
    player = {"hp": state.player.hp, "max_hp": state.player.max_hp, "mana": state.player.energy_or_mana, "max_mana": state.player.energy_or_mana, "stamina": derived.get("Stamina",0), "max_stamina": derived.get("Stamina",0), "level": state.player.level, "xp": state.player.xp, "gold": (state.structured_state.runtime.inventory_state.get("currency",{}) or {}).get("gold",0), "race": str(core.get("race_id","human")).title(), "class": state.player.char_class}
    def room_text(narrative=None):
        return render_semantic_plain(render_room(room, world.manifest, player, npcs=[npcs[n] for n in room.get("npcs",[]) if n in npcs], objects=[{"id": o, "name": o.replace("_"," ").title()} for o in room.get("objects",[])], narrative=narrative or []))
    if cmd.handler_name == "movement":
        direction = DIRECTION_ALIASES.get(parsed.verb, parsed.verb)
        if cmd.name == "go": direction = DIRECTION_ALIASES.get(parsed.args.split()[0].lower() if parsed.args else "", parsed.args.split()[0].lower() if parsed.args else "")
        rt = store.load_room_runtime(room["id"]).get("state", {})
        doors = rt.get("doors", {}) if isinstance(rt, dict) else {}
        ex = next((e for e in room.get("exits",[]) if e.get("direction") == direction and not e.get("hidden")), None)
        if not ex or ex.get("locked") or doors.get(direction, {}).get("closed"):
            return MudCommandResult(False, "You cannot go that way.")
        room = world.room(ex["destination_room_id"]); state.current_location_id = room["id"]; state.structured_state.runtime.current_room_id = room["id"]; state.structured_state.runtime.current_location_id = room["id"]; store.mark_room_visited(room["id"])
        out = room_text([f"You travel {direction}."])
    elif cmd.handler_name == "exits":
        out = "Obvious exits: " + (", ".join(e.get("direction","") for e in room.get("exits",[]) if not e.get("hidden")) or "none")
    elif cmd.handler_name == "look":
        target = parsed.args
        out = room_text() if not target else next((items[o].get("description") or items[o].get("name") for o in room.get("objects",[]) if o in items and target.lower() in items[o].get("name",o).lower()), "You see nothing like that here.")
    elif cmd.handler_name == "score":
        out = f"{state.player.name} the {state.player.char_class}\nLevel: {state.player.level}\nHP: {player['hp']}/{player['max_hp']}   MP: {player['mana']}/{player['max_mana']}   STM: {player['stamina']}/{player['max_stamina']}\nXP: {player['xp']}       Gold: {player['gold']}"
    elif cmd.handler_name == "stats":
        stats = core.get("stats", {}) or {}; out = "Stats:\n" + "\n".join(f"  {k}: {v}" for k,v in stats.items()) if stats else "You have no recorded stats."
    elif cmd.handler_name == "abilities":
        abs_ = state.structured_state.runtime.abilities or []; out = "Abilities:\n" + "\n".join(f"  {a.get('name', a.get('id','ability'))}" for a in abs_) if abs_ else "You know no abilities yet."
    elif cmd.handler_name == "inventory":
        inv = state.structured_state.runtime.inventory_state.get("entries", []) or []; out = "You are carrying:\n" + "\n".join(f"  {e.get('name') or _item_name(e.get('item_id', e.get('id','item')), items)}" for e in inv) if inv else "You are carrying nothing."
    elif cmd.handler_name == "equipment":
        eq = [e for e in state.structured_state.runtime.inventory_state.get("entries", []) or [] if e.get("equipped") or e.get("equipped_slot")]; out = "You are equipped with:\n" + "\n".join(f"  {e.get('equipped_slot') or e.get('slot','worn')}: {e.get('name') or _item_name(e.get('item_id', e.get('id','item')), items)}" for e in eq) if eq else "You are not using any equipment."
    elif cmd.handler_name == "gold": out = f"You have {player['gold']} gold."
    elif cmd.handler_name == "quests": out = "Quests:\n" + "\n".join(f"  {q.get('title', q.get('id'))}" for q in world.quests[:10])
    elif cmd.handler_name == "help":
        arg=parsed.args.strip(); cats=["Movement","Looking","Character","Items","Social","Combat","Magic","Training","Quest","Utility"]
        out = "Command categories:\n" + "\n".join(f"  {c}" for c in cats) if not arg else (commands_for(arg) if arg.title() in cats else REGISTRY.get_help(arg))
    elif cmd.handler_name == "commands": out = commands_for(parsed.args.strip())
    elif cmd.handler_name == "history":
        lim = int(parsed.args) if parsed.args.isdigit() else 20; hist=store.load_command_history(cid, min(lim, history_limit)); out="Recent commands:\n"+"\n".join(f"{i+1}. {h['command_text']}" for i,h in enumerate(hist))
    elif cmd.handler_name == "clear": out = ""
    elif cmd.handler_name == "save": out = "Saved."
    elif cmd.handler_name == "social": out = f"You {cmd.name}: {parsed.args}"; return MudCommandResult(True, out, ai_required=True, ai_context={"command":cmd.name,"args":parsed.args})
    elif cmd.handler_name == "combat": out = "You do not see that here." if parsed.args else f"{cmd.name.title()} whom?"
    elif cmd.handler_name == "door": out = handle_door(store, room, cmd.name, parsed.args)
    elif cmd.handler_name in {"get","drop","equip","remove"}: out = handle_item(state, store, room, items, cmd.handler_name, parsed.args); 
    else: out = placeholder(cmd.name, parsed.args)
    state.structured_state.runtime.last_narration = out
    return MudCommandResult(True, out, save_required=True)

def commands_for(category: str) -> str:
    cat = category.strip().title() if category else ""
    cmds = REGISTRY.list_commands(cat or None)
    if cat and not cmds: return "No commands found for that category."
    if cat: return f"{cat} commands:\n" + ", ".join(" ".join((c.name, *c.aliases)).strip() for c in cmds)
    groups: dict[str, list[str]] = {}
    for c in cmds: groups.setdefault(c.category, []).append(c.name)
    return "Commands:\n" + "\n".join(f"{k}: {', '.join(v)}" for k,v in groups.items())

def placeholder(name: str, args: str) -> str:
    if name in {"practice","train"}: return "You need a trainer to practice here."
    if name in {"open","close","lock","unlock","pick"}: return "You see nothing like that here."
    if name == "cast": return "Usage: cast <spell> [target]" if not args else "The magic gathers, but nothing answers yet."
    return f"That command is not available here."

def handle_door(store: Any, room: dict[str, Any], action: str, target: str) -> str:
    target = (target or "").lower(); exits = room.get("exits", [])
    ex = next((e for e in exits if target and (target in e.get("direction","") or target in str(e.get("name","")).lower() or target == "door")), None)
    if not ex: return "You see nothing like that here."
    direction = ex.get("direction"); rt = store.load_room_runtime(room["id"]); state = rt.get("state", {}) or {}; doors = state.setdefault("doors", {}); door = doors.setdefault(direction, {"closed": bool(ex.get("closed", False)), "locked": bool(ex.get("locked", False))})
    if action == "open":
        if door.get("locked"): return "It is locked."
        door["closed"] = False; msg = "You open it."
    elif action == "close": door["closed"] = True; msg = "You close it."
    elif action == "lock": door["locked"] = True; door["closed"] = True; msg = "You lock it."
    elif action == "unlock": door["locked"] = False; msg = "You unlock it."
    else: door["locked"] = False; msg = "You pick the lock."
    store.save_room_runtime(room["id"], state); return msg

def handle_item(state: Any, store: Any, room: dict[str, Any], items: dict[str, dict[str, Any]], action: str, args: str) -> str:
    inv = list(state.structured_state.runtime.inventory_state.get("entries", []) or [])
    def match_inv(t): return next((e for e in inv if t and t in (e.get("name") or _item_name(e.get("item_id",e.get("id","")), items)).lower()), None)
    if action == "get":
        if not args: return "Get what?"
        room_items = store.load_room_items(room["id"])
        if args.lower() == "all":
            if not room_items: return "You see nothing like that here."
            for ri in room_items:
                inv.append({**(ri.get("state") or {}), "item_id": ri.get("item_id"), "name": _item_name(ri.get("item_id", ""), items), "quantity": ri.get("quantity", 1)})
            with store.connect() as con: con.execute("DELETE FROM room_items WHERE room_id=?", (room["id"],))
            state.structured_state.runtime.inventory_state["entries"] = inv; store.save_inventory(state.player.id or "player_1", inv)
            return "You get everything you can."
        target = args.lower(); ri = next((r for r in room_items if target in _item_name(r.get("item_id", ""), items).lower() or target in str(r.get("item_id", "")).lower()), None)
        if not ri: return "You see nothing like that here."
        entry = {**(ri.get("state") or {}), "item_id": ri.get("item_id"), "name": _item_name(ri.get("item_id", ""), items), "quantity": ri.get("quantity", 1)}
        inv.append(entry); state.structured_state.runtime.inventory_state["entries"] = inv; store.save_inventory(state.player.id or "player_1", inv)
        with store.connect() as con: con.execute("DELETE FROM room_items WHERE id=?", (ri.get("id"),))
        return f"You get {entry.get('name')}."
    if action == "drop":
        e = match_inv(args.lower());
        if not e: return "You are not carrying that."
        inv.remove(e); state.structured_state.runtime.inventory_state["entries"] = inv; store.save_inventory(state.player.id or "player_1", inv); store.add_room_item(room["id"], e.get("item_id") or e.get("id") or e.get("name"), 1, e); return f"You drop {e.get('name') or 'it'}."
    if action == "equip":
        e = match_inv(args.lower());
        if not e: return "You are not carrying that."
        e["equipped"] = True; e["equipped_slot"] = e.get("slot") or ("main_hand" if args else "held"); store.save_inventory(state.player.id or "player_1", inv); return f"You equip {e.get('name') or 'it'}."
    if action == "remove":
        e = match_inv(args.lower());
        if not e: return "You are not using that."
        e.pop("equipped", None); e.pop("equipped_slot", None); store.save_inventory(state.player.id or "player_1", inv); return f"You remove {e.get('name') or 'it'}."
    return "You cannot do that here."
