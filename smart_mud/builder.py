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
VALID_WEAR_SLOTS = {"head","neck","body","torso","legs","feet","hands","arms","finger","wrist","waist","back","mainhand","offhand","held","wield","shield"}
VALID_ENTITY_TYPES = {"npc", "mob", "merchant", "trainer", "banker", "healer", "critter", "object"}

DRAFT_FILES = {
    "rooms": "rooms.json", "items": "item_templates.json", "entities": "entity_templates.json", "spawns": "spawns.json"
}

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

    def can_build(self, actor: Any) -> bool:
        roles = {str(getattr(actor, "role", "player")).lower(), str(getattr(actor, "account_role", "player")).lower()}
        return bool(roles & BUILDER_ROLES)

    def ensure(self, world_id: str) -> Path:
        root = self.worlds_dir / world_id / "builder"
        for name in ("audit", "history", "snapshots", "exports", "imports", "templates"):
            (root / name).mkdir(parents=True, exist_ok=True)
        for key, filename in DRAFT_FILES.items():
            path = root / filename
            if not path.exists():
                path.write_text("{}\n", encoding="utf-8")
        return root

    def load(self, world_id: str) -> dict[str, Any]:
        root = self.ensure(world_id)
        drafts = {key: self._read(root / filename, {}) for key, filename in DRAFT_FILES.items()}
        changed = self.normalize_drafts(world_id, drafts)
        if changed:
            self.save_drafts(world_id, drafts)
        return drafts

    def normalize_room(self, world_id: str, room_id: str, room: Any) -> tuple[dict[str, Any], bool]:
        original = deepcopy(room) if isinstance(room, dict) else room
        record = deepcopy(room) if isinstance(room, dict) else {}
        record.setdefault("id", room_id)
        record.setdefault("name", "")
        record.setdefault("description", "")
        record.setdefault("world_id", world_id)
        record.setdefault("area_id", "")
        record.setdefault("zone_id", "")
        if not isinstance(record.get("exits"), dict): record["exits"] = {}
        if not isinstance(record.get("features"), dict): record["features"] = {}
        if not isinstance(record.get("flags"), list): record["flags"] = []
        if not isinstance(record.get("tags"), list): record["tags"] = []
        if not isinstance(record.get("plugin_data"), dict): record["plugin_data"] = {}
        ordered = {k: record.get(k) for k in ("id","name","description","world_id","area_id","zone_id","exits","features","flags","tags","plugin_data")}
        for k, v in record.items():
            if k not in ordered: ordered[k] = v
        return ordered, ordered != original

    def normalize_drafts(self, world_id: str, drafts: dict[str, Any], actor: Any | None = None) -> bool:
        changed = False
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
        live_rooms = {str(r.get("id")) for r in _records(self.worlds_dir / world_id, "rooms") if r.get("id")}
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
        for rid, room in drafts["rooms"].items():
            if not str(rid).strip() or any(ch.isspace() for ch in str(rid)) or not re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", str(rid)): errors.append(f"room {rid} has unsafe id")
            if rid in live_rooms: warnings.append(f"room {rid} shadows live room")
            if "world_id" not in room: errors.append(f"room {rid} missing world_id")
            if "area_id" not in room: warnings.append(f"room {rid} missing area_id field")
            if "zone_id" not in room: warnings.append(f"room {rid} missing zone_id field")
            if not isinstance(room.get("exits"), dict): errors.append(f"room {rid} missing exits dictionary")
            if not isinstance(room.get("features"), dict): warnings.append(f"room {rid} missing features dictionary")
            if not isinstance(room.get("flags"), list): warnings.append(f"room {rid} missing flags list")
            if not isinstance(room.get("tags"), list): warnings.append(f"room {rid} missing tags list")
            if not isinstance(room.get("plugin_data"), dict): warnings.append(f"room {rid} missing plugin_data dictionary")
            if not room.get("name"): warnings.append(f"room {rid} missing name")
            if self._looks_like_id(room.get("name", "")): warnings.append(f"room {rid} name looks like a room ID")
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
        for sid, sp in drafts["spawns"].items():
            if sp.get("entity_template_id") not in drafts["entities"]: errors.append(f"spawn {sid} references missing entity template {sp.get('entity_template_id')}")
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
