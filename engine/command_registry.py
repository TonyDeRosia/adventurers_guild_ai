"""Canonical Smart MUD command registry."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

CATEGORIES = ["movement","informational","interaction","object","equipment","communication","social","character","magic","combat","group","economy","quest","clan","toggle","builder","admin","system"]
STATUSES = ["implemented","placeholder","planned","intentionally_omitted","future_builder","future_admin","future_combat","future_magic","future_economy","future_quest"]

@dataclass(frozen=True)
class CommandMeta:
    command: str
    aliases: tuple[str, ...] = ()
    category: str = "system"
    minimum_position: str = "standing"
    minimum_role: str = "player"
    status: str = "placeholder"
    handler: str = ""
    short_help: str = ""
    long_help: str = ""
    implemented: bool = False
    placeholder: bool = True
    future_phase: str = ""
    transport_safe: bool = True
    usage: str = ""
    admin_only: bool = False
    builder_only: bool = False

class CommandRegistry:
    def __init__(self, event_bus: Any | None = None):
        self.event_bus = event_bus
        self.commands: dict[str, CommandMeta] = {}
        self.aliases: dict[str, str] = {}
        for meta in DEFAULT_COMMANDS:
            self.register(meta)

    def register(self, meta: CommandMeta) -> None:
        self.commands[meta.command] = meta
        self._publish("command_registered", {"command": meta.command, "category": meta.category, "status": meta.status})
        for alias in meta.aliases:
            self.aliases[alias] = meta.command
            self._publish("command_alias_registered", {"command": meta.command, "alias": alias})

    def resolve(self, token: str) -> tuple[str, str]:
        token = token.lower()
        if token in self.commands: return token, "exact"
        if token in self.aliases: return self.aliases[token], "alias"
        matches = sorted({c for c in self.commands if c.startswith(token)} | {self.aliases[a] for a in self.aliases if a.startswith(token)})
        if len(matches) == 1: return matches[0], "abbreviation"
        if len(matches) > 1: return "", "ambiguous:" + ", ".join(matches)
        return token, "unknown"

    def available(self, role: str = "player", include_planned: bool = False) -> list[CommandMeta]:
        admin = role in {"admin", "owner", "implementor"}; builder = role in {"builder", "admin", "owner", "implementor"}
        out=[]
        for m in self.commands.values():
            if m.admin_only and not admin: continue
            if m.builder_only and not builder: continue
            if not include_planned and m.status not in {"implemented", "placeholder"}: continue
            out.append(m)
        return sorted(out, key=lambda m:(CATEGORIES.index(m.category) if m.category in CATEGORIES else 99, m.command))

    def _publish(self, name: str, payload: dict[str, Any]) -> None:
        if self.event_bus: self.event_bus.publish(name, payload, source_system="command_registry")

def cm(command, aliases=(), category="system", status="placeholder", short="", long="", phase="", admin=False, builder=False, handler="", usage=""):
    implemented=status=="implemented"; placeholder=status=="placeholder"
    return CommandMeta(command, tuple(aliases), category, status=status, short_help=short, long_help=long or short, implemented=implemented, placeholder=placeholder, future_phase=phase, usage=usage or command, admin_only=admin, builder_only=builder, minimum_role="admin" if admin else "builder" if builder else "player", handler=handler)

DEFAULT_COMMANDS = [
cm("north",("n",),"movement","implemented","Move north."),cm("south",("s",),"movement","implemented","Move south."),cm("east",("e",),"movement","implemented","Move east."),cm("west",("w",),"movement","implemented","Move west."),cm("up",("u",),"movement","implemented","Move up."),cm("down",("d",),"movement","implemented","Move down."),cm("enter",(),"movement","placeholder","Enter a place or portal."),cm("leave",(),"movement","placeholder","Leave a place."),cm("run",(),"movement","implemented","Run in a direction."),cm("walk",(),"movement","implemented","Walk in a direction."),cm("follow",(),"group","placeholder","Follow another character."),cm("unfollow",(),"group","placeholder","Stop following."),cm("mount",(),"movement","placeholder","Mounts are not implemented yet."),cm("dismount",(),"movement","placeholder","Mounts are not implemented yet."),cm("sit",(),"interaction","implemented","Sit down."),cm("stand",(),"interaction","implemented","Stand up."),cm("rest",(),"interaction","implemented","Rest."),cm("sleep",(),"interaction","implemented","Sleep."),cm("wake",(),"interaction","implemented","Wake up."),
cm("look",("l","glance","scan"),"informational","implemented","Look around or at a target.", usage="look [target]"),cm("desc",(),"builder","implemented","Builder Mode alias for rdesc.",builder=True, usage="desc <description>"),cm("examine",("exa",),"informational","implemented","Examine a target.", usage="examine <target>"),cm("exits",(),"informational","placeholder","List visible exits."),cm("score",("sc",),"informational","implemented","Display your character sheet summary."),cm("worth",(),"informational","implemented","Show carried gold."),cm("inventory",("inv","i"),"informational","implemented","List carried items."),cm("equipment",("eq",),"informational","implemented","Show worn and wielded equipment."),cm("affects",("aff","saff"),"informational","implemented","List active affects."),cm("spellup",(),"informational","implemented","List active self-buffs."),cm("resists",("resistances",),"informational","implemented","Show resistance placeholders."),cm("skills",("sk",),"character","implemented","List known skills."),cm("spells",("sp",),"magic","implemented","List known spells."),cm("commands",("cmds",),"system","implemented","List available commands."),cm("help",("h",),"system","implemented","Show help for a command."),cm("save",("asave","bsave","wsave","rsave"),"system","implemented","Save character state or builder drafts.", usage="save"),cm("who",(),"informational","implemented","List online players."),cm("whoami",(),"informational","implemented","Show your account and character roles."),cm("where",(),"informational","placeholder","Show your current location."),cm("recall",(),"movement","placeholder","Return to a recall location."),cm("weather",(),"informational","placeholder","Show local weather."),cm("time",(),"informational","placeholder","Show world time."),cm("consider",("con",),"informational","placeholder","Assess a target without starting combat."),cm("diagnose",(),"informational","placeholder","Assess a target's condition."),cm("levels",(),"character","placeholder","Show level guidance."),
cm("get",("take","pickup","grab"),"object","implemented","Pick up an item.", usage="get <object>"),cm("drop",(),"object","implemented","Drop an item.", usage="drop <object>"),cm("put",(),"object","placeholder","Put an object somewhere.", usage="put <item> <container>"),cm("give",(),"object","placeholder","Give an object to someone.", usage="give <item> <target>"),cm("wear",(),"equipment","implemented","Wear equipment.", usage="wear <item>"),cm("remove",("rem",),"equipment","implemented","Remove equipment.", usage="remove <item>"),cm("wield",(),"equipment","implemented","Wield a weapon.", usage="wield <item>"),cm("hold",(),"equipment","implemented","Hold an item.", usage="hold <item>"),cm("eat",(),"object","placeholder","Eat something."),cm("drink",(),"object","placeholder","Drink something.", usage="drink <target>"),cm("taste",(),"object","placeholder","Taste something."),cm("fill",(),"object","placeholder","Fill a container."),cm("pour",(),"object","placeholder","Pour from a container."),cm("open",(),"interaction","placeholder","Open something."),cm("close",(),"interaction","placeholder","Close something."),cm("lock",(),"interaction","placeholder","Lock something."),cm("unlock",(),"interaction","placeholder","Unlock something."),cm("pick",(),"interaction","placeholder","Pick a lock."),cm("read",(),"object","placeholder","Read something.", usage="read <target>"),cm("use",(),"object","placeholder","Use something.", usage="use <target>"),cm("identify",("id",),"object","placeholder","Identify an object.", usage="identify <target>"),
cm("say",(),"communication","implemented","Say something."),cm("tell",(),"communication","placeholder","Tell another player."),cm("reply",(),"communication","placeholder","Reply to a tell."),cm("ask",(),"communication","placeholder","Ask about a topic."),cm("whisper",(),"communication","placeholder","Whisper."),cm("emote",(),"social","implemented","Perform an emote."),cm("gossip",(),"communication","placeholder","Global gossip channel."),cm("auction",(),"economy","future_economy","Auction channel.",phase="Economy"),cm("shout",(),"communication","placeholder","Shout."),cm("holler",(),"communication","placeholder","Holler."),cm("socials",(),"social","placeholder","List socials."),cm("practice",("prac",),"character","placeholder","Practice skills."),cm("train",(),"character","placeholder","Training is not implemented yet."),cm("spellbook",(),"magic","future_magic","Spellbooks are future magic work.",phase="Magic"),cm("study",(),"character","placeholder","Study is not implemented yet."),
cm("brief",(),"toggle","implemented","Toggle brief room descriptions."),cm("compact",(),"toggle","implemented","Toggle compact output."),cm("autoexits",(),"toggle","implemented","Toggle automatic exits."),cm("autoloot",(),"toggle","placeholder","Store autoloot preference; loot is future combat work."),cm("autogold",(),"toggle","placeholder","Store autogold preference; gold loot is future economy work."),cm("autosplit",(),"toggle","placeholder","Store autosplit preference; groups/economy are future work."),cm("automap",(),"toggle","placeholder","Store automap preference; automap rendering is future work."),cm("norepeat",(),"toggle","placeholder","Toggle norepeat preference."),cm("notell",(),"toggle","placeholder","Toggle tell blocking."),cm("nosummon",(),"toggle","placeholder","Toggle summon blocking."),cm("afk",(),"toggle","implemented","Toggle AFK status."),cm("prompt",(),"toggle","implemented","Explain Smart MUD web prompt settings."),
*[cm(x,("rtarget","target") if x == "btarget" else (),"builder","implemented",f"{x} Builder Mode command.",phase="Builder Mode",builder=True, usage=x) for x in "builder build goto btarget redit rstat rcreate rset rdesc rname rexits rfeature rdelete exedit excreate exset exdelete fedit fcreate fset fdesc fdelete oedit ocreate oset odesc odelete ostat medit mcreate mset mdesc mdelete mstat spawnedit spawncreate spawnset spawndelete spawnstat zstat astat wstat rooms rlist rfind rsearch rwhere home areas alist acreate aedit astat aset adelete zones zlist zcreate zedit zstat zset zdelete dig link unlink del delete mlist olist map rmap rassign rmove rrenameid builder_migrate builder_import".split()],
cm("grantrole",(),"admin","implemented","Owner-only role grant command.",admin=True,usage="grantrole <character/account> <role>"),
*[cm(x,(),"admin","future_admin",f"{x} is a future/admin command.",phase="Admin",admin=True) for x in "load purge stat vnum wizhelp transfer restore set".split()],
*[cm(x,(),"combat","future_combat",f"{x} is future combat work.",phase="Combat") for x in "kill hit flee assist rescue kick bash backstab cast quaff recite".split()],
]
