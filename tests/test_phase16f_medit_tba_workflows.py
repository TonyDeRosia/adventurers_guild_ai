from tests.test_builder_list_filters_phase4h_hotfix import engine_with_pack, text


def test_phase16f_loadout_unified_input_isolated_and_navigation(isolated_builder_world):
    engine, actor = engine_with_pack(isolated_builder_world)
    assert "Enter choice :" in text(engine, actor, "medit training_master_borik")
    out = text(engine, actor, "R")
    for needle in ["EQUIPPED ITEMS", "INVENTORY ITEMS", "LOOT TABLE", "A) Equip object", "B) Add inventory item", "C) Add loot item", "D) Remove equipped item", "E) Remove inventory item", "F) Remove loot item", "Q) Quit"]:
        assert needle in out
    assert "E) Equipment" not in out and "L) Loot / Corpse" not in out
    bad = text(engine, actor, "1")
    assert "Invalid choice. Use A, B, C, D, E, F, or Q." in bad
    assert "You cannot go that way" not in bad
    prompt = text(engine, actor, "A")
    assert "Enter object ID, VNUM, or search term to equip" in prompt
    assert "EQUIPPED ITEMS" in text(engine, actor, "Q")
    assert "Mob ID" in text(engine, actor, "Q")


def test_phase16f_loadout_mutates_and_persists(isolated_builder_world):
    engine, actor = engine_with_pack(isolated_builder_world)
    text(engine, actor, "medit training_master_borik")
    text(engine, actor, "R")
    text(engine, actor, "A")
    assigned = text(engine, actor, "training_sword")
    assert "Equipped training_sword" in assigned and "[training_sword]" in assigned
    text(engine, actor, "B")
    inv = text(engine, actor, "field_ration")
    assert "Added field_ration" in inv and "[field_ration]" in inv
    text(engine, actor, "C")
    loot = text(engine, actor, "field_ration")
    assert "Added field_ration to loot" in loot and "LOOT TABLE" in loot
    text(engine, actor, "Q")
    assert "Draft entities training_master_borik updated" in text(engine, actor, "save")
    loadout = text(engine, actor, "R")
    assert "[training_sword]" in loadout and "[field_ration]" in loadout


def test_phase16f_combat_reactions_scripts_visible_workflows(isolated_builder_world):
    engine, actor = engine_with_pack(isolated_builder_world)
    text(engine, actor, "medit training_master_borik")
    combat = text(engine, actor, "U")
    assert "Combat Abilities" in combat and "A) Add   E) Edit   D) Delete   T) Toggle   Q) Quit" in combat
    slot = text(engine, actor, "A")
    assert "Combat Ability Editor (slot 1)" in slot and "1) Type:" in slot
    assert "Combat Abilities" in text(engine, actor, "Q")
    assert "Mob ID" in text(engine, actor, "Q")
    reactions = text(engine, actor, "V")
    assert "Event Reactions" in reactions and "A) Add   E) Edit   D) Delete   T) Toggle   Q) Quit" in reactions
    rslot = text(engine, actor, "A")
    assert "Event Reaction Editor (slot 1)" in rslot and "1) Event type:" in rslot
    assert "Event Reactions" in text(engine, actor, "Q")
    assert "Mob ID" in text(engine, actor, "Q")
    scripts = text(engine, actor, "S")
    assert "-- Scripts:" in scripts and "A) Add" in scripts and "D) Delete" in scripts and "V) View" in scripts
    assert "Mob ID" in text(engine, actor, "Q")
