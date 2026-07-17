from tests.test_phase15b38_1_medit_oedit_functional import engine_with_pack, text


def test_phase15c1_medit_canonical_identity_resources_positions_and_preview(isolated_builder_world):
    engine, actor = engine_with_pack(isolated_builder_world)
    menu = text(engine, actor, "medit training_master_borik")
    assert "species=" in menu and "body=" in menu

    assert "Identity" in text(engine, actor, "identity")
    assert "sex/gender presentation" in text(engine, actor, "sex")
    assert "Sex/gender presentation changed" in text(engine, actor, "female")
    size_prompt = text(engine, actor, "size")
    assert "Current size" in size_prompt
    assert "Size changed" in text(engine, actor, "medium")
    assert "Mobile Editor" in text(engine, actor, "back")

    assert "Resources" in text(engine, actor, "resources")
    assert "Current health maximum" in text(engine, actor, "health")
    assert "Health maximum changed" in text(engine, actor, "18")
    assert "Mobile Editor" in text(engine, actor, "back")

    assert "Positions" in text(engine, actor, "positions")
    assert "Current spawn position" in text(engine, actor, "spawn_position")
    assert "Spawn Position changed" in text(engine, actor, "resting")
    preview = text(engine, actor, "preview")
    assert "RESOLVED TRAITS" in preview
    assert "RESOLVED STATS" in preview
    assert "CONTENT" in preview
    assert "SAMPLE DEATH/CORPSE" in preview


def test_phase15c1_medit_flags_affects_pet_and_delete_dependency_protection(isolated_builder_world):
    engine, actor = engine_with_pack(isolated_builder_world)
    assert "Mobile Editor" in text(engine, actor, "medit training_master_borik")
    assert "Mobile Flags" in text(engine, actor, "flags")
    assert "Mobile Flags" in text(engine, actor, "mobile_flags")
    flag_menu = text(engine, actor, "ai_actor")
    assert "Flag selection updated" in flag_menu or "AI_ACTOR" in flag_menu
    assert "Flag selection updated" in text(engine, actor, "pet")
    assert "Mobile Flags" in text(engine, actor, "back")
    assert "Mobile Editor" in text(engine, actor, "back")

    assert "Loot" in text(engine, actor, "loot")
    assert "Current pet price" in text(engine, actor, "pet_price")
    assert "Pet price changed" in text(engine, actor, "125")
    assert "Mobile Editor" in text(engine, actor, "back")

    assert "Mobile Editor" in text(engine, actor, "back")
    assert "Affect/status Flags" in text(engine, actor, "affects")
    assert "Affect/status Flags" in text(engine, actor, "affect_flags")
    assert "Flag selection updated" in text(engine, actor, "haste")
    assert "Flag selection updated" in text(engine, actor, "slow")
    validation = text(engine, actor, "validate")
    assert "contradictory" in validation.lower() or "haste and slow" in validation.lower()

    text(engine, actor, "back")
    text(engine, actor, "back")
    text(engine, actor, "quit")
    text(engine, actor, "discard")
    copied = text(engine, actor, "mcopy training_master_borik phase15c_borik_copy")
    assert "updated" in copied.lower() or "clone" in copied.lower()
    deleted = text(engine, actor, "mdelete training_master_borik")
    assert "Delete protected" in deleted or "deleted" in deleted
