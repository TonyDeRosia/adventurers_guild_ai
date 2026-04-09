from __future__ import annotations

from pathlib import Path

from app.web import WebRuntime
from engine.entities import CampaignState
from engine.spellbook import classify_spellbook_entry, normalize_spellbook_entry


def _runtime(tmp_path: Path, monkeypatch) -> WebRuntime:
    monkeypatch.setenv("ADVENTURER_GUILD_AI_USER_DATA_DIR", str(tmp_path / "user_data"))
    return WebRuntime(Path.cwd())


def test_explicit_type_preserved_without_override() -> None:
    entry = normalize_spellbook_entry(
        {"name": "Bark Shield", "type": "skill", "tags": ["magic", "learned_from_action"]},
        index=0,
    )
    assert entry is not None
    assert entry["category"] == "skill"
    assert entry["type"] == "skill"
    assert entry["classifier_reason"] == "explicit_type_field"


def test_magical_active_effect_classifies_as_spell() -> None:
    result = classify_spellbook_entry({"name": "Mana Barrier", "description": "Cast a magical barrier.", "cost_or_resource": "4 mana"})
    assert result.category == "spell"


def test_martial_trained_action_classifies_as_skill() -> None:
    result = classify_spellbook_entry({"name": "Dual Strike", "tags": ["weapon", "trained", "martial"]})
    assert result.category == "skill"


def test_always_on_effect_classifies_as_passive() -> None:
    result = classify_spellbook_entry({"name": "Thick Hide", "tags": ["always_on", "defensive"]})
    assert result.category == "passive"


def test_unknown_active_nonmagical_effect_falls_back_to_ability() -> None:
    result = classify_spellbook_entry({"name": "Bark Shield", "description": "Raise a temporary guard stance."})
    assert result.category == "ability"


def test_tags_do_not_override_explicit_category() -> None:
    result = classify_spellbook_entry({"name": "Storm Kick", "type": "skill", "tags": ["magic", "school", "domain"]})
    assert result.category == "skill"


def test_legacy_entries_missing_category_are_normalized_on_load(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_legacy_normalize"})
    payload = runtime.session.state.to_dict()
    payload["structured_state"]["runtime"]["spellbook"] = [
        {"name": "Mana Barrier", "description": "Cast a barrier.", "cost_or_resource": "2 mana"},
        {"name": "Thick Hide", "tags": ["always_on"]},
    ]
    state = CampaignState.from_dict(payload)
    categories = [entry.get("category") for entry in state.structured_state.runtime.spellbook]
    assert categories == ["spell", "passive"]


def test_invalid_category_routes_to_unclassified() -> None:
    entry = normalize_spellbook_entry({"name": "Odd Move", "type": "unknown_custom_bucket"}, index=0)
    assert entry is not None
    assert entry["category"] == "unclassified"
    assert entry["type"] == "unclassified"


def test_frontend_spellbook_sections_are_category_driven() -> None:
    content = Path("app/static/app.js").read_text(encoding="utf-8")
    assert "grouped[clean.category].push(clean);" in content
    assert "['spell', 'skill', 'ability', 'passive', 'unclassified']" in content


def test_ooc_correction_updates_canonical_category_persistently(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_ooc_category_fix"})
    runtime.session.state.structured_state.runtime.spellbook = [
        normalize_spellbook_entry({"id": "sb_1", "name": "Bark Shield", "type": "ability"}, index=0)
    ]
    assert runtime.session.state.structured_state.runtime.spellbook[0]["category"] == "ability"

    monkeypatch.setattr(runtime.engine.model, "generate", lambda **_: "Noted. I'll treat that as a spell.")
    out = runtime.handle_ooc_input("In my spellbook, Bark Shield should be a spell, not an ability.")
    assert out["metadata"]["ooc_mode"] == "structured_authoring"

    entry = runtime.session.state.structured_state.runtime.spellbook[0]
    assert entry["category"] == "spell"
    assert entry["type"] == "spell"
    assert "corrected_by_gm" in entry["tags"]
