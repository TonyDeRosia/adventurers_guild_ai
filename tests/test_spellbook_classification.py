from __future__ import annotations

from pathlib import Path

from app.web import WebRuntime
from engine.entities import CampaignState
from engine.spellbook import classify_spellbook_entry, normalize_abilities_collection, normalize_spellbook_entry


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
    assert "<h4>Abilities</h4>" in content
    assert "grouped[clean.category].push(clean);" not in content


def test_ooc_correction_updates_canonical_category_persistently(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_ooc_category_fix"})
    seeded = [normalize_spellbook_entry({"id": "sb_1", "name": "Bark Shield", "type": "ability"}, index=0)]
    runtime.session.state.structured_state.runtime.abilities = seeded
    runtime.session.state.structured_state.runtime.spellbook = list(seeded)
    assert runtime.session.state.structured_state.runtime.spellbook[0]["category"] == "ability"

    monkeypatch.setattr(runtime.engine.model, "generate", lambda **_: "Noted. I'll treat that as a spell.")
    out = runtime.handle_ooc_input("In my spellbook, Bark Shield should be a spell, not an ability.")
    assert out["metadata"]["ooc_mode"] == "structured_authoring"

    entry = runtime.session.state.structured_state.runtime.spellbook[0]
    assert entry["category"] == "spell"
    assert entry["type"] == "spell"
    assert "corrected_by_gm" in entry["tags"]


def test_old_bucketed_payload_normalizes_to_unified_abilities() -> None:
    normalized = normalize_abilities_collection(
        {
            "spells": [{"name": "Arc Bolt", "type": "spell"}],
            "skills": [{"name": "Blade Dance", "type": "skill"}],
            "passives": [{"name": "Thick Hide", "type": "passive"}],
            "unclassified": [{"name": "Arc Bolt"}],
        }
    )
    assert [entry["name"] for entry in normalized] == ["Arc Bolt", "Blade Dance", "Thick Hide"]


def test_upsert_edit_delete_operate_on_canonical_abilities(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_unified_abilities_manual"})
    created = runtime.upsert_spellbook_entry(
        {"action": "upsert", "id": "ab_1", "name": "Mist Ward", "description": "Protective mist."}
    )
    assert any(entry.get("id") == "ab_1" for entry in created["abilities"])
    edited = runtime.upsert_spellbook_entry(
        {"action": "upsert", "id": "ab_1", "name": "Mist Ward", "description": "Improved protective mist."}
    )
    edited_entry = next(entry for entry in edited["abilities"] if entry.get("id") == "ab_1")
    assert edited_entry["description"] == "Improved protective mist."
    deleted = runtime.upsert_spellbook_entry({"action": "delete", "id": "ab_1"})
    assert all(entry.get("id") != "ab_1" for entry in deleted["abilities"])


def test_ooc_structured_sync_targets_unified_abilities(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_unified_abilities_ooc"})
    monkeypatch.setattr(
        runtime.engine.model,
        "generate",
        lambda **_: '[STRUCTURED_SYNC_PAYLOAD]{"spellbook_entries":[{"name":"Ember Lance","description":"Line of flame."}]}[/STRUCTURED_SYNC_PAYLOAD]',
    )
    out = runtime.handle_ooc_input("Add this learned ability to my spellbook.")
    assert out["metadata"]["ooc_sync"]["spellbook_entries_added"] >= 1
    assert any(entry.get("name") == "Ember Lance" for entry in runtime.session.state.structured_state.runtime.abilities)


def test_narrator_sync_payload_targets_unified_abilities(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_unified_abilities_narrator"})
    summary = runtime._sync_ooc_spellbook_and_sheet(
        runtime.session.state,
        [normalize_spellbook_entry({"name": "Storm Sigil", "source_metadata": {"source_type": "narrator_sync"}}, index=0)],
    )
    assert summary["spellbook_entries_added"] >= 1
    assert any(entry.get("name") == "Storm Sigil" for entry in runtime.session.state.structured_state.runtime.abilities)


def test_gm_sync_payload_targets_unified_abilities(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_unified_abilities_gm"})
    summary = runtime._sync_ooc_spellbook_and_sheet(
        runtime.session.state,
        [normalize_spellbook_entry({"name": "Warden Step", "source_metadata": {"source_type": "gm_sync"}}, index=0)],
    )
    assert summary["spellbook_entries_added"] >= 1
    assert any(entry.get("name") == "Warden Step" for entry in runtime.session.state.structured_state.runtime.abilities)


def test_in_play_learning_updates_unified_abilities(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_unified_abilities_in_play"})
    pending = runtime.engine.PendingAbilityLearning(
        raw_name="ember lance",
        normalized_name="Ember Lance",
        category="magic",
        confidence="high",
        source_verb="cast",
    )
    runtime.engine._learn_ability_from_action(runtime.session.state, pending)
    assert any(entry.get("name") == "Ember Lance" for entry in runtime.session.state.structured_state.runtime.abilities)


def test_persistence_round_trip_keeps_unified_abilities(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_unified_abilities_persist"})
    runtime.upsert_spellbook_entry({"action": "upsert", "id": "ab_2", "name": "Chain Lightning"})
    runtime.save_active_campaign("slot_unified_abilities_persist")

    reloaded = _runtime(tmp_path, monkeypatch)
    reloaded.switch_campaign("slot_unified_abilities_persist")
    assert any(entry.get("name") == "Chain Lightning" for entry in reloaded.session.state.structured_state.runtime.abilities)


def test_missing_type_is_not_dropped_from_abilities() -> None:
    normalized = normalize_abilities_collection([{"name": "Unlabeled Trick", "description": "Still valid."}])
    assert len(normalized) == 1
    assert normalized[0]["name"] == "Unlabeled Trick"


def test_unknown_type_is_preserved_as_hidden_subtype_metadata() -> None:
    entry = normalize_spellbook_entry({"name": "Odd Move", "type": "ancient_art"}, index=0)
    assert entry is not None
    assert entry["subtype"] == "ancient_art"
