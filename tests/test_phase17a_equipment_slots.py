from engine.equipment_slots import CANONICAL_EQUIPMENT_SLOT_IDS, EQUIPMENT_SLOT_LABELS, normalize_equipment_slot
from engine.mud_displays import build_equipment_document, render_display_plain
from engine.mud_runtime import MudRuntime
from tests.test_builder_list_filters_phase4h_hotfix import engine_with_pack, text

CANONICAL_LABELS = [EQUIPMENT_SLOT_LABELS[s] for s in CANONICAL_EQUIPMENT_SLOT_IDS]
BANNED = ["Ammo", "Body", "Held", "Offhand", "Primary Weapon", "Quiver", "Ranged", "Secondary Weapon", "Shield", "Torso", "Wield", "Wrist"]


def test_player_eq_and_medit_share_registry_source():
    assert MudRuntime.EQUIPMENT_SLOTS == list(CANONICAL_EQUIPMENT_SLOT_IDS)
    doc = build_equipment_document([], MudRuntime.EQUIPMENT_SLOTS)
    rendered = render_display_plain(doc)
    assert [label for label in CANONICAL_LABELS if label in rendered] == CANONICAL_LABELS


def test_medit_loadout_renders_canonical_labels_only(isolated_builder_world):
    engine, actor = engine_with_pack(isolated_builder_world)
    text(engine, actor, "medit training_master_borik")
    out = text(engine, actor, "R")
    positions = [out.index(label) for label in CANONICAL_LABELS]
    assert positions == sorted(positions)
    rendered_labels = [line[:16].strip() for line in out.splitlines() if "[NOTHING]" in line or "[training_sword]" in line]
    assert rendered_labels == CANONICAL_LABELS
    for banned in BANNED:
        assert banned not in rendered_labels


def test_aliases_normalize_and_collisions_validate(isolated_builder_world):
    assert normalize_equipment_slot("wield") == "main_hand"
    assert normalize_equipment_slot("primary weapon") == "main_hand"
    assert normalize_equipment_slot("offhand") == "off_hand"
    assert normalize_equipment_slot("held") == "off_hand"
    assert normalize_equipment_slot("wrist") == "wrists"
    assert normalize_equipment_slot("body") == "chest"
    engine, actor = engine_with_pack(isolated_builder_world)
    text(engine, actor, "medit training_master_borik")
    sess = next(iter(engine.builder_service.sessions.active.values()))
    sess.working_record.setdefault("equipment_loadout", {})["equipped"] = {
        "wield": {"item_template_id": "training_sword", "quantity": 1, "chance": 100},
        "main_hand": {"item_template_id": "training_sword", "quantity": 1, "chance": 100},
    }
    errors = engine.builder_service._equipment_validate(actor, sess)
    assert any("wield" in err and "main_hand" in err for err in errors)


def test_medit_equip_picker_uses_canonical_slots_for_ring(isolated_builder_world):
    engine, actor = engine_with_pack(isolated_builder_world)
    drafts = engine.builder.load(engine.builder.world_id(actor))
    drafts.setdefault("items", {})["test_ring"] = {"id": "test_ring", "name": "Test Ring", "item_type": "trinket", "wear_slots": ["finger", "finger_left", "finger_right"]}
    engine.builder.save_drafts(engine.builder.world_id(actor), drafts)
    text(engine, actor, "medit training_master_borik")
    text(engine, actor, "R")
    text(engine, actor, "A")
    picker = text(engine, actor, "test_ring")
    assert "1) Finger left" in picker and "2) Finger right" in picker
    assert "Finger\n" not in picker


def test_medit_sword_assigns_main_hand_and_persists(isolated_builder_world):
    engine, actor = engine_with_pack(isolated_builder_world)
    text(engine, actor, "medit training_master_borik")
    text(engine, actor, "R")
    text(engine, actor, "A")
    out = text(engine, actor, "training_sword")
    assert "Equipped training_sword in Main hand" in out
    text(engine, actor, "Q")
    assert "updated" in text(engine, actor, "save")
    reopened = text(engine, actor, "R")
    assert "Main hand" in reopened and "[training_sword]" in reopened
