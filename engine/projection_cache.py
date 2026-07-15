"""Resident active-character projection cache and entry/autosave helpers."""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Callable


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class CharacterEntryContext:
    entry_id: str
    session_id: str
    account_id: str
    character_id: str
    world_id: str
    character: Any
    actor: Any = None
    room: Any = None
    progression_snapshot: dict[str, Any] = field(default_factory=dict)
    economy_snapshot: dict[str, Any] = field(default_factory=dict)
    inventory_snapshot: tuple[Any, ...] = ()
    equipment_snapshot: tuple[Any, ...] = ()
    effect_snapshot: tuple[Any, ...] = ()
    cooldown_snapshot: tuple[Any, ...] = ()
    ability_grants: tuple[Any, ...] = ()
    source_versions: dict[str, Any] = field(default_factory=dict)
    started_at: float = field(default_factory=time.monotonic)

    def enrich(self, **kwargs: Any) -> "CharacterEntryContext":
        return replace(self, **kwargs)


@dataclass
class ProjectionCacheEntry:
    character_id: str
    world_id: str
    projection_type: str
    source_version_key: tuple[Any, ...]
    value: Any = None
    created_at: str = field(default_factory=utc_now)
    last_accessed_at: str = field(default_factory=utc_now)
    generation: int = 0
    status: str = "pending"
    error: str = ""
    origin: str = "sync"
    size: int = 1


class ProjectionCacheRegistry:
    INVALIDATION_GRAPH: dict[str, set[str]] = {
        "resource_current": {"prompt", "resource_display"},
        "resource_maximum": {"combat_stats", "score", "prompt"},
        "attributes": {"primary_stats", "combat_stats", "score", "combatstats", "attributes"},
        "equipment": {"equipment", "inventory", "carrying", "combat_stats", "score", "combatstats", "ability_availability", "prompt"},
        "inventory": {"inventory", "carrying", "score", "worth"},
        "effects": {"effects", "primary_stats", "combat_stats", "score", "ability_availability", "prompt"},
        "progression": {"progression", "worth", "score", "ability_availability"},
        "progression_identity": {"score", "worth", "ability_availability"},
        "birth_state": {"score"},
        "currency": {"worth", "currency_display"},
        "movement": {"room_render", "location", "prompt", "score"},
        "world_definition": {"*"},
        "stance": {"effects", "body_profile", "combat_profile", "abilities", "equipment", "combat_stats", "score", "prompt"},
        "transformation": {"effects", "body_profile", "combat_profile", "abilities", "equipment", "combat_stats", "score", "prompt"},
        "builder": {"room_render", "location"},
        "world": {"*"},
    }

    def __init__(self, runtime: Any = None, *, max_entries: int = 256, max_entries_per_character: int = 32) -> None:
        self.runtime = runtime
        self.max_entries = max_entries
        self.max_entries_per_character = max_entries_per_character
        self.entries: dict[tuple[str, str], ProjectionCacheEntry] = {}
        self.generations: dict[str, int] = {}
        self.metrics = {k: 0 for k in ["projection_cache_hits", "projection_cache_misses", "projection_invalidations", "warmup_cache_hits", "stale_task_rejected", "warmup_cancelled"]}

    def generation(self, character_id: str) -> int:
        return self.generations.get(character_id, 0)

    def source_key(self, character: Any, projection_type: str, dependencies: tuple[str, ...] = ()) -> tuple[Any, ...]:
        cid = str(getattr(character, "id", getattr(character, "character_id", "")))
        world = str(getattr(self.runtime, "active_world_id", "") or getattr(character, "world_id", ""))
        data = getattr(character, "actor_data", {}) or {}
        versions = data.get("source_versions", {}) if isinstance(data, dict) else {}
        if self.runtime is not None and hasattr(self.runtime, "_source_versions_for_character"):
            try:
                versions = {**self.runtime._source_versions_for_character(character), **(versions if isinstance(versions, dict) else {})}
            except Exception:
                pass
        explicit = tuple((dep, versions.get(dep, getattr(character, f"{dep}_version", None))) for dep in dependencies)
        return (cid, world, projection_type, self.generation(cid), explicit)

    def get(self, character: Any, projection_type: str, source_key: tuple[Any, ...]) -> Any | None:
        cid = str(getattr(character, "id", getattr(character, "character_id", "")))
        entry = self.entries.get((cid, projection_type))
        if entry and entry.status == "ready" and entry.generation == self.generation(cid) and entry.source_version_key == source_key:
            entry.last_accessed_at = utc_now(); self.metrics["projection_cache_hits"] += 1
            return entry.value
        self.metrics["projection_cache_misses"] += 1
        return None

    def put(self, character: Any, projection_type: str, source_key: tuple[Any, ...], value: Any, *, origin: str = "sync") -> ProjectionCacheEntry:
        cid = str(getattr(character, "id", getattr(character, "character_id", "")))
        world = str(getattr(self.runtime, "active_world_id", "") or getattr(character, "world_id", ""))
        entry = ProjectionCacheEntry(cid, world, projection_type, source_key, value=value, generation=self.generation(cid), status="ready", origin=origin, size=len(str(value)) if value is not None else 1)
        self.entries[(cid, projection_type)] = entry
        self._evict_if_needed(cid)
        return entry

    def mark_pending(self, character_id: str, world_id: str, projection_type: str, source_key: tuple[Any, ...]) -> None:
        self.entries[(character_id, projection_type)] = ProjectionCacheEntry(character_id, world_id, projection_type, source_key, generation=self.generation(character_id), status="pending")

    def mark_failed(self, character_id: str, world_id: str, projection_type: str, error: str) -> None:
        entry = self.entries.get((character_id, projection_type))
        if entry and entry.status == "ready":
            return
        self.entries[(character_id, projection_type)] = ProjectionCacheEntry(character_id, world_id, projection_type, (), generation=self.generation(character_id), status="failed", error=str(error)[:240])

    def invalidate(self, character_id: str, reason: str) -> set[str]:
        affected = set(self.INVALIDATION_GRAPH.get(reason, {reason}))
        self.generations[character_id] = self.generation(character_id) + 1
        for key, entry in list(self.entries.items()):
            if key[0] != character_id: continue
            if "*" in affected or entry.projection_type in affected:
                entry.status = "stale"; self.metrics["projection_invalidations"] += 1
        return affected

    def evict_character(self, character_id: str) -> None:
        for key in [k for k in self.entries if k[0] == character_id]:
            self.entries.pop(key, None)
        self.generations.pop(character_id, None)

    def _evict_if_needed(self, character_id: str) -> None:
        char_entries = [e for e in self.entries.values() if e.character_id == character_id]
        for e in sorted(char_entries, key=lambda x: x.last_accessed_at)[:max(0, len(char_entries)-self.max_entries_per_character)]:
            self.entries.pop((e.character_id, e.projection_type), None)
        if len(self.entries) > self.max_entries:
            for e in sorted(self.entries.values(), key=lambda x: x.last_accessed_at)[:len(self.entries)-self.max_entries]:
                self.entries.pop((e.character_id, e.projection_type), None)


class ProjectionWarmupService:
    PRIORITY = ("score", "worth", "equipment", "abilities", "inventory", "effects", "combatstats", "attributes")
    def __init__(self, runtime: Any, registry: ProjectionCacheRegistry, *, max_queue_depth: int = 64, max_concurrent: int = 2) -> None:
        self.runtime = runtime; self.registry = registry; self.max_queue_depth = max_queue_depth
        self._tasks: dict[tuple[str, int], asyncio.Task[Any]] = {}
        self._sem = asyncio.Semaphore(max_concurrent)

    def schedule(self, character: Any, session_id: str) -> None:
        cid = character.id; gen = self.registry.generation(cid); key = (cid, gen)
        if key in self._tasks or len(self._tasks) >= self.max_queue_depth or cid not in getattr(self.runtime, "active_characters", {}): return
        try: loop = asyncio.get_running_loop()
        except RuntimeError: return
        self._tasks[key] = loop.create_task(self._run(cid, session_id, gen))

    async def _run(self, cid: str, session_id: str, gen: int) -> None:
        queued = time.monotonic()
        async with self._sem:
            self.runtime.performance_counters.setdefault("warmup_queue_ms", 0); self.runtime.performance_counters["warmup_queue_ms"] += int((time.monotonic()-queued)*1000)
            char = getattr(self.runtime, "active_characters", {}).get(cid)
            if not char or self.registry.generation(cid) != gen or getattr(self.runtime, "character_session_ids", {}).get(cid, session_id) != session_id:
                self.registry.metrics["stale_task_rejected"] += 1; return
            for proj in self.PRIORITY:
                if cid not in getattr(self.runtime, "active_characters", {}) or self.registry.generation(cid) != gen: self.registry.metrics["stale_task_rejected"] += 1; return
                try: self.runtime.build_projection(char, proj, origin="background")
                except Exception as exc: self.runtime.event_bus.publish("projection_warmup_failed", {"character_id": cid, "projection_type": proj, "error": str(exc)[:160]}, source_system="projection_warmup")
        self._tasks.pop((cid, gen), None)

    def cancel(self, character_id: str) -> None:
        for key, task in list(self._tasks.items()):
            if key[0] == character_id:
                task.cancel(); self._tasks.pop(key, None); self.registry.metrics["warmup_cancelled"] += 1


class ActiveCharacterAutosaveService:
    def __init__(self, runtime: Any, interval_seconds: float = 30.0) -> None:
        self.runtime = runtime; self.interval_seconds = interval_seconds; self.last_success: dict[str, str] = {}; self.last_failure: dict[str, str] = {}

    def scan_once(self) -> dict[str, Any]:
        attempted = saved = skipped = failed = 0
        for cid, char in list(getattr(self.runtime, "active_characters", {}).items()):
            if not getattr(self.runtime, "_dirty_characters", {}).get(cid):
                skipped += 1; self.runtime.performance_counters.setdefault("autosave_skipped_clean", 0); self.runtime.performance_counters["autosave_skipped_clean"] += 1; continue
            attempted += 1
            try:
                st = self.runtime.save_character_if_dirty(char, "autosave")
                saved += 1 if st.get("saved") else 0; self.last_success[cid] = utc_now()
            except Exception as exc:
                failed += 1; self.last_failure[cid] = str(exc)[:160]
        pc = self.runtime.performance_counters
        for k, v in {"autosave_attempts": attempted, "autosave_successes": saved, "autosave_failures": failed}.items(): pc.setdefault(k, 0); pc[k] += v
        return {"attempted": attempted, "saved": saved, "skipped_clean": skipped, "failed": failed}
