from tests.test_builder_list_filters_phase4h_hotfix import engine_with_pack, text


def test_medit_equipment_structured_loadout_workflow(isolated_builder_world):
    engine, a = engine_with_pack(isolated_builder_world)
    assert "Mobile Editor" in text(engine, a, "medit training_master_borik")
    menu = text(engine, a, "equipment")
    assert "MEDIT Equipment Loadout" in menu
    assert "Assign equipment slot" in menu
    assert "set <field> <value>" not in menu
    assert "Object search results" in text(engine, a, "search training")
    assert "Invalid equipment slot" in text(engine, a, "assign invalid_slot training_sword")
    assigned = text(engine, a, "assign mainhand training_sword 100 1")
    assert "Equipment slot assigned" in assigned and "training_sword" in assigned
    carried = text(engine, a, "carry field_ration 50 2")
    assert "Carried inventory entry added" in carried and "field_ration" in carried
    assert "Equipment validation" in text(engine, a, "validate")
    assert "Equipment loadout preview" in text(engine, a, "preview")
    assert "Session undo applied" in text(engine, a, "undo")
    assert "Session redo applied" in text(engine, a, "redo")
    assert "Loadout entry removed" in text(engine, a, "remove mainhand")


def test_medit_spawns_structured_reference_workflow(isolated_builder_world):
    engine, a = engine_with_pack(isolated_builder_world)
    text(engine, a, "medit training_master_borik")
    menu = text(engine, a, "spawns")
    assert "MEDIT Spawn References" in menu
    assert "Add spawn reference" in menu
    assert "set <field> <value>" not in menu
    assert "Missing room" in text(engine, a, "add nowhere_room")
    added = text(engine, a, "add guildhall_crossing_square 2 75")
    assert "Spawn reference added" in added and "guildhall_crossing_square" in added
    assert "Spawn reference updated" in text(engine, a, "edit 1 max 3")
    assert "Reset preview" in text(engine, a, "preview")
    assert "Reset trace" in text(engine, a, "trace")
    assert "Spawn validation" in text(engine, a, "validate")
    assert "Spawn reference removed" in text(engine, a, "remove 1")


def test_oedit_conditional_menu_and_help(isolated_builder_world):
    engine, a = engine_with_pack(isolated_builder_world)
    out = text(engine, a, "oedit training_sword")
    assert "Object Editor" in out and "-- Item number" in out
    assert "Container Data" not in out
