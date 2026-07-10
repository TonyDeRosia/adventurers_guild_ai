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
cm("look",("l","glance","scan"),"informational","implemented","Look around or at a target.", usage="look [target]"),cm("desc",(),"builder","implemented","Builder Mode alias for rdesc.",builder=True, usage="desc <description>"),cm("examine",("exa",),"informational","implemented","Examine a target.", usage="examine <target>"),cm("exits",(),"informational","placeholder","List visible exits."),cm("score",("sc",),"informational","implemented","Display your character sheet summary."),cm("worth",(),"informational","implemented","Show carried gold."),cm("properties",(),"property","implemented","List your property summary."),cm("property",(),"property","implemented","Inspect, rent, buy, renew, terminate, and manage property.", usage="property <available|info|rent|buy|renew|terminate|access|grant|revoke|guests|invite|remove|storage>"),cm("locker",(),"property","implemented","Use personal lockers.", usage="locker [list|store|retrieve]"),cm("store",(),"property","implemented","Store an item in property storage.", usage="store <item> [container]"),cm("retrieve",(),"property","implemented","Retrieve an item from property storage.", usage="retrieve <item> [container]"),cm("home",(),"property","implemented","Show or set property home location.", usage="home [set|clear]"),cm("keys",(),"property","implemented","List property keys and credentials."),cm("key",(),"property","implemented","Inspect a property key.", usage="key inspect <item>"),cm("inventory",("inv","i"),"informational","implemented","List carried items."),cm("equipment",("eq",),"informational","implemented","Show worn and wielded equipment."),cm("affects",("aff","saff"),"informational","implemented","List active affects."),cm("spellup",(),"informational","implemented","List active self-buffs."),cm("resists",("resistances",),"informational","implemented","Show resistance placeholders."),cm("skills",("sk",),"character","implemented","List known skills."),cm("spells",("sp",),"magic","implemented","List known spells."),cm("abilities",(),"character","implemented","List available abilities."),cm("ability",(),"character","implemented","Show an ability.", usage="ability <name>"),cm("cooldowns",(),"combat","implemented","Show ability cooldowns."),cm("cancel",(),"combat","implemented","Cancel current cast."),cm("commands",("cmds",),"system","implemented","List available commands."),cm("help",("h",),"system","implemented","Show help for a command."),cm("save",("asave","bsave","wsave","rsave"),"system","implemented","Save character state or builder drafts.", usage="save"),cm("who",(),"informational","implemented","List online players."),cm("whoami",(),"informational","implemented","Show your account and character roles."),cm("where",(),"informational","placeholder","Show your current location."),cm("recall",(),"movement","placeholder","Return to a recall location."),cm("weather",(),"informational","placeholder","Show local weather."),cm("time",(),"informational","placeholder","Show world time."),cm("consider",("con",),"combat","implemented","Assess a target without starting combat."),cm("diagnose",(),"combat","implemented","Assess a target's condition."),cm("levels",(),"character","placeholder","Show level guidance."),
cm("get",("take","pickup","grab"),"object","implemented","Pick up an item.", usage="get <object>"),cm("drop",(),"object","implemented","Drop an item.", usage="drop <object>"),cm("put",(),"object","placeholder","Put an object somewhere.", usage="put <item> <container>"),cm("give",(),"object","placeholder","Give an object to someone.", usage="give <item> <target>"),cm("wear",(),"equipment","implemented","Wear equipment.", usage="wear <item>"),cm("remove",("rem",),"equipment","implemented","Remove equipment.", usage="remove <item>"),cm("wield",(),"equipment","implemented","Wield a weapon.", usage="wield <item>"),cm("hold",(),"equipment","implemented","Hold an item.", usage="hold <item>"),cm("eat",(),"object","placeholder","Eat something."),cm("drink",(),"object","placeholder","Drink something.", usage="drink <target>"),cm("taste",(),"object","placeholder","Taste something."),cm("fill",(),"object","placeholder","Fill a container."),cm("pour",(),"object","placeholder","Pour from a container."),cm("open",(),"interaction","placeholder","Open something."),cm("close",(),"interaction","placeholder","Close something."),cm("lock",(),"interaction","placeholder","Lock something."),cm("unlock",(),"interaction","placeholder","Unlock something."),cm("pick",(),"interaction","placeholder","Pick a lock."),cm("read",(),"object","placeholder","Read something.", usage="read <target>"),cm("use",(),"object","implemented","Use an ability or object.", usage="use <ability> [target]"),cm("identify",("id",),"object","placeholder","Identify an object.", usage="identify <target>"),
cm("say",(),"communication","implemented","Say something."),cm("tell",(),"communication","placeholder","Tell another player."),cm("reply",(),"communication","placeholder","Reply to a tell."),cm("ask",(),"communication","placeholder","Ask about a topic."),cm("whisper",(),"communication","placeholder","Whisper."),cm("emote",(),"social","implemented","Perform an emote."),cm("gossip",(),"communication","placeholder","Global gossip channel."),cm("auction",(),"economy","future_economy","Auction channel.",phase="Economy"),cm("shout",(),"communication","placeholder","Shout."),cm("holler",(),"communication","placeholder","Holler."),cm("socials",(),"social","placeholder","List socials."),cm("practice",("prac",),"character","placeholder","Practice skills."),cm("train",(),"character","placeholder","Training is not implemented yet."),cm("spellbook",(),"magic","future_magic","Spellbooks are future magic work.",phase="Magic"),cm("study",(),"character","placeholder","Study is not implemented yet."),
cm("brief",(),"toggle","implemented","Toggle brief room descriptions."),cm("compact",(),"toggle","implemented","Toggle compact output."),cm("autoexits",(),"toggle","implemented","Toggle automatic exits."),cm("autoloot",(),"toggle","placeholder","Store autoloot preference; loot is future combat work."),cm("autogold",(),"toggle","placeholder","Store autogold preference; gold loot is future economy work."),cm("autosplit",(),"toggle","placeholder","Store autosplit preference; groups/economy are future work."),cm("automap",(),"toggle","placeholder","Store automap preference; automap rendering is future work."),cm("norepeat",(),"toggle","placeholder","Toggle norepeat preference."),cm("notell",(),"toggle","placeholder","Toggle tell blocking."),cm("nosummon",(),"toggle","placeholder","Toggle summon blocking."),cm("afk",(),"toggle","implemented","Toggle AFK status."),cm("prompt",(),"toggle","implemented","Explain Smart MUD web prompt settings."),
*[cm(x,("rtarget","target") if x == "btarget" else (),"builder","implemented",f"{x} Builder Mode command.",phase="Builder Mode",builder=True, usage=x) for x in "builder build goto btarget redit rstat rcreate rset rdesc rname rexits rfeature rdelete exedit excreate exset exdelete fedit fcreate fset fdesc fdelete oedit ocreate oset odesc odelete ostat medit mcreate mset mdesc mdelete mstat spawnedit spawncreate spawnset spawndelete spawnstat zstat astat wstat rooms rlist rfind rsearch rwhere home areas alist acreate aedit astat aset adelete zones zlist zcreate zedit zstat zset zdelete dig link unlink del delete mlist olist map rmap rassign rmove rrenameid builder_migrate builder_import formula modifier actor".split()],
cm("grantrole",(),"admin","implemented","Owner-only role grant command.",admin=True,usage="grantrole <character/account> <role>"),
*[cm(x,(),"admin","future_admin",f"{x} is a future/admin command.",phase="Admin",admin=True) for x in "load purge stat vnum wizhelp transfer restore set".split()],
*[cm(x,(),"combat","implemented",f"{x} combat command.",phase="Combat") for x in "kill attack flee assist combat".split()],
*[cm(x,(),"admin","implemented",f"{x} combat diagnostic command.",phase="Combat",admin=True) for x in "combatstat attacktrace damagetrace combatdebug actorcombat".split()],
*[cm(x,(),"magic" if x in {"cast","invoke"} else "combat","implemented",f"{x} ability command.",phase="Abilities") for x in "cast invoke perform".split()],
*[cm(x,(),"builder","implemented",f"{x} ability Builder command.",phase="Abilities",builder=True) for x in "abilitylist abilitystat abilitycreate abilityclone abilityset abilitydelete abilityvalidate abilitypreview abilitytrace loadoutlist loadoutstat loadoutcreate loadoutclone loadoutset loadoutability loadoutdelete loadoutvalidate abilitygrant abilityrevoke actorabilities abilitycooldowns abilitycasts".split()],
*[cm(x,(),"combat","future_combat",f"{x} is future combat work.",phase="Combat") for x in "hit rescue kick bash backstab quaff recite".split()],
# Phase 8B organization, party, guild, clan, and group foundations.
*[cm(x,(),"group","implemented",f"{x} organization command.",phase="Organizations", usage=x) for x in "party group guild clan organizations organization invitations applications members gtell ptell ctell officer orgsay".split()],
*[cm(x,(),"builder","implemented",f"{x} organization Builder/Admin command.",phase="Organizations",builder=True, usage=x) for x in "orglist orgstat orgcreate orgclone orgset orgdelete orgvalidate orgpreview orgrolelist orgrolestat orgrolecreate orgroleclone orgroleset orgroledelete orgrolevalidate orgpermissionlist orgpermissionset orgpermissiontrace orgmembershiplist orgmembershipstat orgmembershipcreate orgmembershipset orgmembershipdelete orgmembershipvalidate orgcommlist orgcommstat orgcommcreate orgcommset orgcommdelete orgcommvalidate orgcombatlist orgcombatstat orgcombatcreate orgcombatset orgcombatdelete orgcombatvalidate orgquestlist orgqueststat orgquestcreate orgquestset orgquestdelete orgquestvalidate orginstance orgmembers orgcreateinstance orgaddmember orgremovemember orgsetrole orgtransfer orgdisband orginvite orgapplicationlist orgaudit orgtrace partytrace groupcombat groupquesttrace orgseedapply organizationaudit membershiptrace roletrace permissiontrace invitationtrace applicationtrace groupcombattrace orgrelationshiptrace orgseedtrace orgmessagetrace".split()],


    *[cm(x,(),"builder","implemented",f"{x} faction Builder/Admin command.",phase="Factions",builder=True, usage=x) for x in "factionlist factionstat factioncreate factionclone factionset factiondelete factionvalidate factionpreview repprofilelist repprofilestat repprofilecreate repprofileset repprofileclone repprofiledelete repprofilevalidate standingprofilelist standingprofilestat standingprofilecreate standingtier standingprofilevalidate standingprofilepreview diplomacylist diplomacystat diplomacycreate diplomacyset diplomacydelete diplomacyvalidate factionaccesslist factionaccessstat factionaccesscreate factionaccessrule factionaccessvalidate factionaccesspreview factionpricinglist factionpricingstat factionpricingcreate factionpricingset factionpricingdelete factionpricingvalidate factionrewardlist factionrewardstat factionrewardcreate factionrewardset factionrewarddelete factionrewardvalidate reputationtrace standingtrace repadd repremove repset represet rephistory factionaccess factionhostility factionrelationship factionrelationshipset factionrelationshipclear factionrewardcheck factionrewardgrant factiondecaytick factionaudit factiontrace repeventtrace diplomacytrace factionhostilitytrace factionaccesstrace factionpricingtrace factionrewardtrace factioncombattrace factiondecaytrace factionmembershiptrace".split()],
    *[cm(x,(),"informational","implemented",f"{x} faction player command.",phase="Factions",usage=x) for x in "reputation factions faction standing".split()],
# Phase 9A canonical training and advancement commands.
*[cm(x,(),"character","implemented",f"{x} training command.",phase="Training",usage=x) for x in "train learn practice skills spells abilities class profession professions respec trainers".split()],
*[cm(x,(),"builder","implemented",f"{x} training Builder/Admin command.",phase="Training",builder=True,usage=x) for x in "trainerlist trainerstat trainercreate trainerclone trainerset trainerdelete trainervalidate trainerpreview trainingofferlist trainingofferstat trainingoffercreate trainingofferclone trainingofferset trainingofferdelete trainingoffervalidate trainingofferpreview trainingrequirementlist trainingrequirementstat trainingrequirementcreate trainingrequirementset trainingrequirementdelete trainingrequirementvalidate trainingcostlist trainingcoststat trainingcostcreate trainingcostset trainingcostdelete trainingcostvalidate trainingresultlist trainingresultstat trainingresultcreate trainingresultset trainingresultdelete trainingresultvalidate respeclist respecstat respeccreate respecset respecdelete respecvalidate respecpreview trainingoffers trainingpreview trainingconfirm trainingcancel trainingtransaction trainingtrace traininghistory trainerstate trainerenable trainerdisable granttrainingoffer respecactor trainingaudit trainertrace trainingoffertrace trainingquotetrace trainingtransactiontrace trainingcosttrace trainingresulttrace abilitytrainingtrace classtrainingtrace professiontrainingtrace attributetrainingtrace respectrace trainingcooldowntrace".split()],
# Phase 10A canonical written content, mail, boards, readable objects.
*[cm(x,(),"communication","implemented",f"{x} written-content command.",phase="Written Content",usage=x) for x in "mail mailbox boards board read contents write sign seal unseal copy".split()],
*[cm(x,(),"builder","implemented",f"{x} written-content Builder/Admin command.",phase="Written Content",builder=True,usage=x) for x in "documentlist documentstat documentcreate documentclone documentset documentdelete documentvalidate documentpreview contentlist contentstat contentcreate contentset contentdelete contentvalidate boardlist boardstat boardcreate boardclone boardset boarddelete boardvalidate boardpreview mailprofilelist mailprofilestat mailprofilecreate mailprofileset mailprofiledelete mailprofilevalidate writtenaccesslist writtenaccessstat writtenaccesscreate writtenaccessset writtenaccessdelete writtenaccessvalidate moderationprofilelist moderationprofilestat moderationprofilecreate moderationprofileset moderationprofiledelete moderationprofilevalidate mailboxtrace mailtrace maildeliver mailreturn mailpurge documentinstance documenttrace documentcopy documentgrant boardinstance boardtrace boardpostadmin boardhide boardrestore boardlock boardpin writtenaudit writtencontenttrace documentversiontrace mailattachmenttrace maildeliverytrace boardposttrace writtenaccesstrace readstatetrace sanitizationtrace retentiontrace".split()],

]
