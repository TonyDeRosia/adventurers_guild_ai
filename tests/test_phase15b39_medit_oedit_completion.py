from tests.test_builder_list_filters_phase4h_hotfix import engine_with_pack, text


def test_phase15b39_medit_visible_menus_do_not_advertise_raw_shells(isolated_builder_world):
    engine, actor = engine_with_pack(isolated_builder_world)
    assert "Mobile Editor" in text(engine, actor, "medit training_master_borik")
    forbidden = ("raw field", "raw add", "raw remove", "serialized", "dictionary")
    for choice in [str(i) for i in range(1, 21)]:
        menu = text(engine, actor, choice)
        lowered = menu.lower()
        assert all(token not in lowered for token in forbidden), (choice, menu)
        assert any(word in menu for word in ("Q. Back", "Commands:", "Preview", "Validate", "read-only", "Diagnostics"))
        text(engine, actor, "back")


def test_phase15b39_oedit_hides_raw_shell_and_unsupported_type_sections(isolated_builder_world):
    engine, actor = engine_with_pack(isolated_builder_world)
    menu = text(engine, actor, "oedit training_sword")
    assert "Object Editor" in menu
    assert "oset <id> <field> <value>" not in menu
    assert "raw field" not in menu.lower()
    assert "Container Data" not in menu
    assert "Light Data" not in menu


def test_phase15b39_completion_matrix_exists_and_documents_all_visible_sections():
    from pathlib import Path
    body = Path("docs/builder/MEDIT_OEDIT_COMPLETION_MATRIX.md").read_text()
    for heading in ("MEDIT matrix", "OEDIT matrix", "Manual acceptance walkthrough"):
        assert heading in body
    for term in ("Equipment", "Spawns", "Wear Flags", "Preview", "Validation"):
        assert term in body
