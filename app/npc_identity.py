"""Helpers for persistent NPC identity records and NPC speech routing."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class NPCIdentityRegistry:
    """Campaign-scoped registry for NPC identity and portrait metadata."""

    def __init__(self, state: Any) -> None:
        self.state = state
        runtime = self.state.structured_state.runtime
        if not isinstance(getattr(runtime, "npc_identity_registry", None), dict):
            runtime.npc_identity_registry = {}

    @property
    def records(self) -> dict[str, dict[str, Any]]:
        return self.state.structured_state.runtime.npc_identity_registry

    def ensure_for_state(self) -> None:
        for npc_id, npc in self.state.npcs.items():
            self.ensure_record(
                npc_id=npc_id,
                display_name=npc.name,
                role_hint=(npc.personality_nodes.role if npc.personality_nodes else "") or npc.personality_archetype or "",
                personality_summary=(
                    npc.personality_profile.conversational_tone
                    if npc.personality_profile is not None
                    else ""
                ),
                source="state_npc",
                important=self._is_notable_npc(npc),
            )

        scene_state = self.state.structured_state.runtime.scene_state
        for lite in scene_state.get("lightweight_npcs", []):
            if not isinstance(lite, dict):
                continue
            npc_id = str(lite.get("npc_id", "")).strip()
            if not npc_id:
                continue
            profile = lite.get("personality_profile", {}) if isinstance(lite.get("personality_profile"), dict) else {}
            role_hint = str(lite.get("role_hint", "")).strip() or str(profile.get("archetype", "")).strip()
            personality_summary = str(profile.get("conversational_tone", "")).strip()
            self.ensure_record(
                npc_id=npc_id,
                display_name=str(lite.get("display_name", npc_id)).strip() or npc_id,
                role_hint=role_hint,
                personality_summary=personality_summary,
                source="lightweight_npc",
                important=bool(lite.get("important", False)),
            )

    def ensure_record(
        self,
        *,
        npc_id: str,
        display_name: str,
        role_hint: str = "",
        personality_summary: str = "",
        appearance_summary: str = "",
        source: str = "unknown",
        important: bool = False,
        turn_index: int | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        turn = int(turn_index if turn_index is not None else self.state.turn_count)
        existing = self.records.get(npc_id)
        if existing is not None:
            existing["display_name"] = existing.get("display_name") or display_name
            existing["role_or_archetype"] = existing.get("role_or_archetype") or role_hint
            existing["personality_summary"] = existing.get("personality_summary") or personality_summary
            existing["appearance_summary"] = existing.get("appearance_summary") or appearance_summary
            existing["important"] = bool(existing.get("important", False) or important)
            existing["last_seen_at"] = now
            existing["last_seen_turn"] = turn
            print(f"[npc-identity] record_reused npc_id={npc_id} source={source}")
            return existing

        created = {
            "npc_id": npc_id,
            "display_name": display_name,
            "role_or_archetype": role_hint,
            "appearance_summary": appearance_summary,
            "personality_summary": personality_summary,
            "portrait_status": "none",
            "portrait_path": "",
            "portrait_prompt": "",
            "first_seen_at": now,
            "last_seen_at": now,
            "first_seen_turn": turn,
            "last_seen_turn": turn,
            "relationship_affinity": "",
            "memory_notes": "",
            "visual_locked": False,
            "important": bool(important),
        }
        self.records[npc_id] = created
        print(f"[npc-identity] record_created npc_id={npc_id} source={source}")
        return created

    def mark_seen(self, npc_id: str, turn_index: int | None = None) -> None:
        record = self.records.get(npc_id)
        if record is None:
            return
        record["last_seen_at"] = datetime.now(timezone.utc).isoformat()
        record["last_seen_turn"] = int(turn_index if turn_index is not None else self.state.turn_count)

    def should_generate_portrait(self, npc_id: str) -> tuple[bool, str]:
        record = self.records.get(npc_id)
        if record is None:
            return False, "missing_record"
        if not bool(record.get("important", False)):
            return False, "not_important"
        if bool(record.get("visual_locked", False)):
            return False, "visual_locked"
        status = str(record.get("portrait_status", "none")).strip().lower()
        if status in {"queued", "ready", "requested"}:
            return False, f"portrait_{status}"
        return True, "eligible"

    def portrait_prompt(self, npc_id: str) -> str:
        record = self.records.get(npc_id) or {}
        traits = [
            f"fantasy RPG character portrait, bust framing, clean face lighting",
            f"name: {record.get('display_name', 'unknown')}",
        ]
        role = str(record.get("role_or_archetype", "")).strip()
        if role:
            traits.append(f"role: {role}")
        appearance = str(record.get("appearance_summary", "")).strip()
        if appearance:
            traits.append(f"appearance: {appearance}")
        personality = str(record.get("personality_summary", "")).strip()
        if personality:
            traits.append(f"demeanor: {personality}")
        traits.append("neutral background, high detail, readable identity, no text")
        return ", ".join(traits)

    def bind_portrait_success(self, npc_id: str, *, portrait_path: str, prompt: str) -> None:
        record = self.records.get(npc_id)
        if record is None:
            return
        record["portrait_status"] = "ready"
        record["portrait_path"] = portrait_path
        record["portrait_prompt"] = prompt
        record["visual_locked"] = True

    def bind_portrait_failure(self, npc_id: str, reason: str) -> None:
        record = self.records.get(npc_id)
        if record is None:
            return
        record["portrait_status"] = "failed"
        record["portrait_error"] = reason

    def route_npc_dialogue_message(self, message: dict[str, Any]) -> dict[str, Any]:
        if str(message.get("type", "")).lower() != "npc":
            return message
        text = str(message.get("text", "")).strip()
        if not text or self._looks_like_non_dialogue_npc_message(text):
            return message
        npc_id = self.state.active_dialogue_npc_id or ""
        if not npc_id and len(self.records) == 1:
            npc_id = next(iter(self.records.keys()))
        record = self.records.get(npc_id)
        if record is None:
            return message
        self.mark_seen(npc_id)
        print(f"[npc-dialogue-card] routed npc_id={npc_id}")
        enriched = dict(message)
        enriched["speaker_npc_id"] = npc_id
        enriched["speaker_name"] = str(record.get("display_name", npc_id)).strip() or npc_id
        portrait_path = str(record.get("portrait_path", "")).strip()
        enriched["portrait_url"] = portrait_path
        enriched["portrait_status"] = str(record.get("portrait_status", "none"))
        return enriched

    def _is_notable_npc(self, npc: Any) -> bool:
        relationship = str(getattr(npc, "relationship_tier", "")).strip().lower()
        if relationship in {"friendly", "loyal", "hostile"}:
            return True
        return abs(int(getattr(npc, "disposition", 0))) >= 20

    @staticmethod
    def _looks_like_non_dialogue_npc_message(text: str) -> bool:
        lowered = text.lower()
        prefixes = (
            "relationship tier",
            "disposition lens",
            "type 'choose <number>'",
            "no active dialogue",
            "invalid choice",
        )
        if any(lowered.startswith(prefix) for prefix in prefixes):
            return True
        return lowered[:3].isdigit() and lowered[1:2] == ")"
