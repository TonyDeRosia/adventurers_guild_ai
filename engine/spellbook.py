"""Canonical abilities model and deterministic normalization helpers.

This module is the single authority for learned ability entry typing.
Creation/edit/load paths should normalize through :func:`normalize_spellbook_entry`.
UI should render from persisted ``category`` (mirrored to ``type`` for compatibility),
and must not re-infer categories from tags.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

SpellbookCategory = Literal[
    "spell",
    "skill",
    "ability",
    "passive",
    "technique",
    "trait",
    "item_power",
    "unclassified",
]
ClassifierConfidence = Literal["high", "medium", "low"]

CANONICAL_SPELLBOOK_CATEGORIES: set[str] = {
    "spell",
    "skill",
    "ability",
    "passive",
    "technique",
    "trait",
    "item_power",
}
DISPLAY_SPELLBOOK_CATEGORIES: tuple[str, ...] = ("spell", "skill", "ability", "passive", "unclassified")
SPELLBOOK_CATEGORY_ALIASES: dict[str, str] = {
    "magic": "spell",
    "martial": "skill",
    "talent": "ability",
}
SOURCE_METADATA_KEYS: tuple[str, ...] = ("source_type", "source_category", "category_hint", "type_hint")
SOURCE_ONLY_TAG_PREFIXES: tuple[str, ...] = ("learned_", "corrected_", "source_")


@dataclass(frozen=True)
class SpellbookClassification:
    category: SpellbookCategory
    confidence: ClassifierConfidence
    reason: str


def _normalize_supported_category(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    mapped = SPELLBOOK_CATEGORY_ALIASES.get(raw, raw)
    if mapped in CANONICAL_SPELLBOOK_CATEGORIES:
        return mapped
    return ""


def classify_spellbook_entry(entry: dict[str, Any]) -> SpellbookClassification:
    """Classify one spellbook entry using strict, deterministic priority order.

    Priority A: explicit structured type/category
    Priority B: source system metadata hints
    Priority C: deterministic property rules
    Priority D: controlled fallback
    """

    # Priority A: explicit structured type/category.
    explicit_category = _normalize_supported_category(entry.get("category"))
    if explicit_category:
        return SpellbookClassification(category=explicit_category, confidence="high", reason="explicit_category_field")
    explicit_type = _normalize_supported_category(entry.get("type"))
    if explicit_type:
        return SpellbookClassification(category=explicit_type, confidence="high", reason="explicit_type_field")
    explicit_raw = str(entry.get("category", entry.get("type", ""))).strip()
    explicit_invalid = bool(explicit_raw)

    # Priority B: source system metadata.
    source_metadata = entry.get("source_metadata")
    if isinstance(source_metadata, dict):
        for key in SOURCE_METADATA_KEYS:
            source_hint = _normalize_supported_category(source_metadata.get(key))
            if source_hint:
                return SpellbookClassification(category=source_hint, confidence="medium", reason=f"source_metadata_{key}")
    for key in SOURCE_METADATA_KEYS:
        source_hint = _normalize_supported_category(entry.get(key))
        if source_hint:
            return SpellbookClassification(category=source_hint, confidence="medium", reason=f"entry_{key}")

    # Priority C: deterministic content rules.
    text_fields = [
        str(entry.get("name", "")),
        str(entry.get("description", "")),
        str(entry.get("notes", "")),
        str(entry.get("cost_or_resource", "")),
    ]
    lowered_text = " ".join(text_fields).lower()
    tags = {str(tag).strip().lower() for tag in entry.get("tags", []) if str(tag).strip()}
    flags = {str(tag).strip().lower() for tag in entry.get("flags", []) if str(tag).strip()}
    combined_markers = tags | flags | {token for token in lowered_text.replace("-", "_").split() if token}

    passive_markers = {"passive", "sustained", "inherent", "always_on", "aura_only", "always-on"}
    if combined_markers.intersection(passive_markers) or "always on" in lowered_text:
        return SpellbookClassification(category="passive", confidence="high", reason="passive_markers")
    activation = str(entry.get("activation", "")).strip().lower()
    if activation in {"none", "passive", "always"} and not str(entry.get("cost_or_resource", "")).strip():
        return SpellbookClassification(category="passive", confidence="high", reason="no_activation_with_no_direct_cost")

    spell_markers = {
        "spell",
        "magic",
        "arcane",
        "mana",
        "cast",
        "casting",
        "school",
        "domain",
        "rune",
        "sigil",
        "hex",
        "enchant",
    }
    if any(marker in lowered_text for marker in ("mana", "spell slot", "cast", "arcane", "magical")):
        return SpellbookClassification(category="spell", confidence="high", reason="explicit_magic_resource_or_casting_text")
    if combined_markers.intersection(spell_markers):
        return SpellbookClassification(category="spell", confidence="medium", reason="magic_markers")

    skill_markers = {
        "skill",
        "trained",
        "practiced",
        "martial",
        "weapon",
        "movement",
        "technique",
        "stance",
        "strike",
        "slash",
    }
    if combined_markers.intersection(skill_markers):
        return SpellbookClassification(category="skill", confidence="medium", reason="martial_or_trained_markers")

    if explicit_invalid:
        return SpellbookClassification(category="unclassified", confidence="low", reason="invalid_explicit_category")

    # Priority D: controlled fallback.
    return SpellbookClassification(category="ability", confidence="low", reason="controlled_fallback_active_nonmagical")


def normalize_spellbook_entry(entry: Any, *, index: int = 0, default_name: str = "") -> dict[str, Any] | None:
    if isinstance(entry, dict):
        name = str(entry.get("name", "")).strip()
    else:
        name = str(entry).strip()
        entry = {"name": name}
    if not name:
        return None

    classification = classify_spellbook_entry(entry)
    tags = [str(tag).strip() for tag in entry.get("tags", []) if str(tag).strip()]
    flags = [str(flag).strip() for flag in entry.get("flags", []) if str(flag).strip()]
    source_metadata = dict(entry.get("source_metadata", {})) if isinstance(entry.get("source_metadata"), dict) else {}
    if not source_metadata:
        source_tags = [tag for tag in tags if tag.lower().startswith(SOURCE_ONLY_TAG_PREFIXES)]
        if source_tags:
            source_metadata = {"source_tags": source_tags}

    category = classification.category
    explicit_category = str(entry.get("category", "")).strip().lower()
    explicit_type = str(entry.get("type", "")).strip().lower()
    hidden_subtype = str(entry.get("subtype", "")).strip()
    if not hidden_subtype:
        if explicit_type and explicit_type != category:
            hidden_subtype = explicit_type
        elif explicit_category and explicit_category != category:
            hidden_subtype = explicit_category
    normalized = {
        "id": str(entry.get("id", "")).strip() or f"sb_{index}_{(name or default_name).lower().replace(' ', '_')}",
        "name": name,
        "category": category,
        # Backward-compatible mirror for legacy code and saves.
        "type": category,
        "description": str(entry.get("description", "")).strip(),
        "cost_or_resource": str(entry.get("cost_or_resource", "")).strip(),
        "cooldown": str(entry.get("cooldown", "")).strip(),
        "tags": tags,
        "flags": flags,
        "notes": str(entry.get("notes", "")).strip(),
        "source_metadata": source_metadata,
        "classifier_confidence": classification.confidence,
        "classifier_reason": classification.reason,
    }
    if hidden_subtype:
        normalized["subtype"] = hidden_subtype
    return normalized


def normalize_abilities_collection(raw_entries: Any) -> list[dict[str, Any]]:
    """Normalize old/new spellbook payload shapes into one canonical abilities list.

    Supported inputs:
    - list[entry]
    - dict with "abilities" list
    - dict with "spellbook" list
    - dict with legacy categorized buckets (spells/skills/passives/unclassified)
    """

    if isinstance(raw_entries, list):
        candidate_entries = list(raw_entries)
    elif isinstance(raw_entries, dict):
        candidate_entries = []
        for key in ("abilities", "spellbook", "spells", "skills", "passives", "unclassified"):
            values = raw_entries.get(key, [])
            if isinstance(values, list):
                candidate_entries.extend(values)
    else:
        candidate_entries = []

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, entry in enumerate(candidate_entries):
        clean = normalize_spellbook_entry(entry, index=index)
        if not clean:
            continue
        name_key = str(clean.get("name", "")).strip().lower()
        dedupe_key = name_key
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        normalized.append(clean)
    return normalized
