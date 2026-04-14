from __future__ import annotations

from pathlib import Path

from app.web import WebRuntime
from engine.campaign_engine import CampaignEngine


def _runtime(tmp_path: Path, monkeypatch) -> WebRuntime:
    monkeypatch.setenv("ADVENTURER_GUILD_AI_USER_DATA_DIR", str(tmp_path / "user_data"))
    return WebRuntime(Path.cwd())


def test_inventory_manual_upsert_edit_delete_and_persist(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_inventory_manual"})

    created = runtime.upsert_inventory_entry({"action": "upsert", "id": "inv_1", "name": "Healing Potion", "category": "consumables", "quantity": 2, "notes": "Emergency"})
    assert any(entry.get("id") == "inv_1" for entry in created["inventory"]["entries"])

    edited = runtime.upsert_inventory_entry({"action": "upsert", "id": "inv_1", "name": "Healing Potion", "category": "consumables", "quantity": 3, "notes": "Updated"})
    entry = next(entry for entry in edited["inventory"]["entries"] if entry.get("id") == "inv_1")
    assert entry["quantity"] == 3
    assert entry["notes"] == "Updated"

    deleted = runtime.upsert_inventory_entry({"action": "delete", "id": "inv_1"})
    assert all(entry.get("id") != "inv_1" for entry in deleted["inventory"]["entries"])

    runtime.upsert_inventory_entry({"action": "upsert", "id": "inv_2", "name": "Rope", "category": "items", "quantity": 1})
    runtime.save_active_campaign("slot_inventory_manual")
    reloaded = _runtime(tmp_path, monkeypatch)
    reloaded.switch_campaign("slot_inventory_manual")
    assert any(entry.get("name") == "Rope" for entry in reloaded.get_inventory_state().get("entries", []))


def test_spellbook_no_longer_auto_learns_from_normal_gameplay(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_no_auto_spellbook"})
    runtime.session.state.settings.play_style.auto_update_character_sheet_from_actions = True
    runtime.engine = CampaignEngine(runtime.engine.model, data_dir=Path("data"))

    runtime.engine.run_turn(runtime.session.state, "cast rain spell")
    names = [entry.get("name") for entry in runtime.session.state.structured_state.runtime.spellbook]
    assert "Rain Spell" not in names


def test_ooc_structured_updates_can_write_inventory_and_spellbook(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch)
    runtime.create_campaign({"slot": "slot_ooc_writes"})
    monkeypatch.setattr(
        runtime.engine.model,
        "generate",
        lambda **_: '[STRUCTURED_SYNC_PAYLOAD]{"inventory_entries":[{"name":"Lantern","category":"key_items","quantity":1}],"spellbook_entries":[{"name":"Firebolt","description":"Bolt of flame."}]}[/STRUCTURED_SYNC_PAYLOAD]',
    )

    out = runtime.handle_ooc_input("OOC add a lantern to inventory and add Firebolt to my spellbook.")
    sync = out["metadata"]["ooc_sync"]
    assert sync["inventory_entries_added"] >= 1
    assert sync["spellbook_entries_added"] >= 1
    assert any(entry.get("name") == "Lantern" for entry in runtime.get_inventory_state().get("entries", []))
    assert any(entry.get("name") == "Firebolt" for entry in runtime.get_spellbook_state())
