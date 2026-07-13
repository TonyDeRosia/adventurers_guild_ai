"""Canonical searchable help service for authored world help and ability fallbacks."""
from __future__ import annotations

import json, re, tempfile
from dataclasses import dataclass, field, asdict
from difflib import get_close_matches
from pathlib import Path
from typing import Any

SAFE_ID_RE = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
HTML_RE = re.compile(r"<\s*/?\s*(?:script|span|div|html|body|a|img|iframe|style|p|br|table|tr|td|ul|li|ol|h[1-6])\b[^>]*>", re.I)
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
BAD_TEXT_RE = re.compile(r"\b(?:javascript|import\s+|from\s+\w+\s+import|eval\s*\(|exec\s*\(|select\s+.+\s+from|drop\s+table|\.\./|/bin/|__\w+__)\b", re.I)


def normalize_help_query(text: Any) -> str:
    value = str(text or "").strip().lower()
    value = re.sub(r"[_-]+", " ", value)
    value = re.sub(r"[^a-z0-9 '\"]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" '\"")
    return value


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", normalize_help_query(text)).strip("_") or "help"

@dataclass(frozen=True)
class HelpEntry:
    help_id: str
    keywords: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    title: str = ""
    summary: str = ""
    body: str = ""
    syntax: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()
    related_topics: tuple[str, ...] = ()
    category: str = "general"
    minimum_access_level: str = "player"
    player_visible: bool = True
    builder_visible: bool = True
    source_type: str = "authored"
    source_id: str = ""
    sort_order: int = 1000
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "HelpEntry":
        def tup(name):
            v = raw.get(name) or ()
            return tuple(str(x).strip() for x in (v if isinstance(v, (list, tuple)) else [v]) if str(x).strip())
        return cls(
            help_id=str(raw.get("help_id") or raw.get("id") or "").strip(),
            keywords=tup("keywords"), aliases=tup("aliases"), title=str(raw.get("title") or "").strip(),
            summary=str(raw.get("summary") or "").strip(), body=str(raw.get("body") or "").strip(),
            syntax=tup("syntax"), examples=tup("examples"), related_topics=tup("related_topics"),
            category=str(raw.get("category") or "general").strip().lower(),
            minimum_access_level=str(raw.get("minimum_access_level") or "player").strip().lower(),
            player_visible=bool(raw.get("player_visible", True)), builder_visible=bool(raw.get("builder_visible", True)),
            source_type=str(raw.get("source_type") or "authored").strip(), source_id=str(raw.get("source_id") or "").strip(),
            sort_order=int(raw.get("sort_order") or 1000),
            metadata={k:v for k,v in (raw.get("metadata") or {}).items() if k in {"notes","version","status"}},
        )
    def to_dict(self):
        d=asdict(self)
        for k in ("keywords","aliases","syntax","examples","related_topics"): d[k]=list(d[k])
        return d

class HelpService:
    role_rank = {"player":0,"helper":1,"builder":2,"admin":3,"owner":4}
    def __init__(self, world_root: str|Path, ability_service: Any = None):
        self.world_root=Path(world_root); self.ability_service=ability_service; self.entries={}; self._index={}; self.reload()
    @property
    def published_path(self): return self.world_root/"help"/"help_entries.json"
    @property
    def draft_path(self): return self.world_root/"builder"/"help_entries.json"
    def reload(self, world_id: str=""):
        self.entries=self._load_entries(self.published_path); self._build_index(); return self
    def _load_entries(self,path):
        if not path.exists(): return {}
        data=json.loads(path.read_text())
        rows=data.get("help_entries", data if isinstance(data,list) else [])
        entries={}
        for r in rows:
            e=HelpEntry.from_dict(r); self.validate_entry(e, entries); entries[e.help_id]=e
        return entries
    def validate_entry(self,e, existing=None):
        errs=[]
        if not e.help_id or not SAFE_ID_RE.fullmatch(e.help_id): errs.append(f"invalid help_id: {e.help_id}")
        for field_name in ("title","summary","body","category", "source_id"):
            self._validate_text(getattr(e, field_name), field_name, errs)
        for seq_name in ("keywords","aliases","syntax","examples","related_topics"):
            for v in getattr(e, seq_name): self._validate_text(v, seq_name, errs)
        if not e.title: errs.append(f"{e.help_id}: title is required")
        if not e.keywords: errs.append(f"{e.help_id}: at least one keyword is required")
        if existing and e.help_id in existing: errs.append(f"duplicate help_id: {e.help_id}")
        if errs: raise ValueError("; ".join(errs))
    def _validate_text(self, text, name, errs):
        s=str(text or "")
        if ANSI_RE.search(s): errs.append(f"{name}: raw ANSI is not allowed")
        if HTML_RE.search(s): errs.append(f"{name}: HTML is not allowed")
        if CONTROL_RE.search(s): errs.append(f"{name}: control characters are not allowed")
        if BAD_TEXT_RE.search(s): errs.append(f"{name}: unsafe expression-like text is not allowed")
    def validate_all(self, entries):
        seen_alias={}; errors=[]
        for e in entries.values():
            try: self.validate_entry(e)
            except ValueError as exc: errors.append(str(exc))
            for a in e.aliases:
                n=normalize_help_query(a)
                if n in seen_alias and seen_alias[n]!=e.help_id: errors.append(f"alias conflict: {a}")
                seen_alias[n]=e.help_id
            for rel in e.related_topics:
                if rel and not self._entry_exact(rel, entries): errors.append(f"{e.help_id}: unknown related topic {rel}")
        if errors: raise ValueError("; ".join(errors))
    def _build_index(self):
        self._index={"id":{},"keyword":{},"alias":{},"title":{}}
        for e in self.entries.values():
            self._index["id"][normalize_help_query(e.help_id)]=e.help_id
            self._index["title"][normalize_help_query(e.title)]=e.help_id
            for k in e.keywords: self._index["keyword"].setdefault(normalize_help_query(k),[]).append(e.help_id)
            for a in e.aliases: self._index["alias"].setdefault(normalize_help_query(a),[]).append(e.help_id)
    def _visible(self,e, actor):
        role=str(getattr(actor,"account_role",getattr(actor,"role","player")) or "player").lower()
        return e and e.player_visible and self.role_rank.get(role,0)>=self.role_rank.get(e.minimum_access_level,0)
    def _entry_exact(self, q, entries=None):
        n=normalize_help_query(q); entries=entries or self.entries
        for e in entries.values():
            keys=[e.help_id,e.title,*e.keywords,*e.aliases]
            if n in {normalize_help_query(x) for x in keys}: return e
        return None
    def get_entry(self, query, actor_context=None):
        n=normalize_help_query(query)
        for bucket in ("id","keyword","alias","title"):
            found=self._index[bucket].get(n)
            if isinstance(found,list):
                visible=[self.entries[i] for i in found if self._visible(self.entries.get(i), actor_context)]
                if len(visible)==1: return visible[0]
                if visible: return {"ambiguous": visible}
            elif found and self._visible(self.entries.get(found), actor_context): return self.entries[found]
        for bucket in ("keyword","alias"):
            matches=[]
            for key, ids in self._index[bucket].items():
                if key.startswith(n): matches.extend(ids)
            visible=sorted({i for i in matches if self._visible(self.entries.get(i), actor_context)}, key=lambda i:(self.entries[i].sort_order,self.entries[i].title))
            if len(visible)==1: return self.entries[visible[0]]
            if len(visible)>1: return {"ambiguous":[self.entries[i] for i in visible]}
        ability=self.ability_entry(query)
        if ability: return ability
        results=self.search(query, actor_context)
        if len(results)==1: return results[0]
        if len(results)>1: return {"ambiguous": results[:8]}
        return None
    def ability_entry(self, query):
        svc=self.ability_service
        if not svc: return None
        n=normalize_help_query(query)
        for a in getattr(svc.registry,"abilities",{}).values():
            if n in {normalize_help_query(a.id), normalize_help_query(a.name), normalize_help_query(a.short_name)}:
                body=a.description or "No description has been authored yet."
                facts=[]
                if a.ability_type: facts.append(f"Type: {a.ability_type.title()}")
                if a.category or a.school: facts.append(f"Category: {(a.category or a.school).replace('_',' ').title()}")
                if a.costs: facts.append("Cost: "+", ".join(f"{c.get('amount', c.get('percentage',0))} {c.get('resource_id','resource')}" for c in a.costs))
                mode=(a.targeting or {}).get("mode") or "self"; facts.append(f"Target: {str(mode).replace('_',' ').title()}")
                cd=(a.cooldowns or {}).get("cooldown_duration")
                if cd not in (None, "", 0): facts.append(f"Cooldown: {cd}s")
                if facts: body += "\n\n" + "\n".join(facts)
                verb="cast" if a.ability_type in {"spell","heal","buff","debuff"} else "use"
                return HelpEntry(help_id=f"ability.{_slug(a.name or a.id)}", keywords=(a.name, a.id.replace('_',' ')), aliases=(a.short_name,) if a.short_name else (), title=a.name or a.id.replace('_',' ').title(), summary=a.description, body=body, syntax=(f"{verb} {a.name or a.id}",), category="abilities", source_type="ability", source_id=a.id)
        return None
    def search(self, query, actor_context=None):
        n=normalize_help_query(query); scored=[]
        for e in self.entries.values():
            if not self._visible(e, actor_context): continue
            hay=[e.help_id,e.title,e.summary,e.category,*e.keywords,*e.aliases]
            score=max((3 if normalize_help_query(x)==n else 2 if normalize_help_query(x).startswith(n) else 1 if n in normalize_help_query(x) else 0) for x in hay)
            if score: scored.append((score,e.sort_order,e.title,e))
        return [x[3] for x in sorted(scored, key=lambda t:(-t[0],t[1],t[2]))]
    def suggest(self, query, actor_context=None):
        exact=self._entry_exact(query)
        if exact and self._visible(exact, actor_context): return exact
        names=[]; by={}
        for e in self.entries.values():
            if self._visible(e, actor_context):
                for x in (e.title,*e.keywords,*e.aliases):
                    nx=normalize_help_query(x); names.append(nx); by[nx]=e
        m=get_close_matches(normalize_help_query(query), names, n=1, cutoff=0.78)
        return by[m[0]] if m else None
    def list_topics(self, category=None, actor_context=None):
        rows=[e for e in self.entries.values() if self._visible(e, actor_context) and (not category or e.category==normalize_help_query(category))]
        return sorted(rows, key=lambda e:(e.category,e.sort_order,e.title))
    def categories(self, actor_context=None): return sorted({e.category for e in self.entries.values() if self._visible(e, actor_context)})
    def related(self, query, actor_context=None):
        e=self.get_entry(query, actor_context)
        if not isinstance(e, HelpEntry): return []
        return [r for r in (self.get_entry(x, actor_context) for x in e.related_topics) if isinstance(r, HelpEntry)]
    def load_drafts(self): return self._load_entries(self.draft_path) if self.draft_path.exists() else dict(self.entries)
    def save_drafts(self, entries):
        self.draft_path.parent.mkdir(parents=True, exist_ok=True)
        data={"help_entries":[e.to_dict() for e in sorted(entries.values(), key=lambda e:(e.sort_order,e.help_id))]}
        self.draft_path.write_text(json.dumps(data, indent=2, sort_keys=True)+"\n")
    def publish_drafts(self):
        entries=self.load_drafts(); self.validate_all(entries)
        self.published_path.parent.mkdir(parents=True, exist_ok=True)
        fd,tmp=tempfile.mkstemp(dir=str(self.published_path.parent), prefix="help_entries.", suffix=".tmp")
        Path(tmp).write_text(json.dumps({"help_entries":[e.to_dict() for e in sorted(entries.values(), key=lambda e:(e.sort_order,e.help_id))]}, indent=2, sort_keys=True)+"\n")
        Path(tmp).replace(self.published_path); self.reload(); return len(entries)
