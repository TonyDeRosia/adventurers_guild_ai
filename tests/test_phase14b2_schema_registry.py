from engine.abilities import AbilityDefinition, AbilityEffectOperationRegistry, LegacyAbilityDefinitionAdapter


def test_legacy_adapter_promotes_plugin_data_canonical_effects_deterministically():
    raw = {
        "id": "legacy_spell",
        "name": "Legacy Spell",
        "ability_type": "spell",
        "targeting": {"mode": "self"},
        "plugin_data": {
            "canonical_effects": [{"effect_id": "spark", "operation": "send_message", "messages": {"actor_success": "Spark."}}],
            "materials": [{"template_id": "ruby_dust", "quantity": 1}],
            "proficiency_policy": {"maximum": 100},
            "legacy_note": "kept",
        },
    }
    first = AbilityDefinition.from_dict(raw)
    second = LegacyAbilityDefinitionAdapter.adapt(raw)
    assert first.to_dict() == second.to_dict()
    assert first.canonical_effects == [{"effect_id": "spark", "operation": "send_message", "messages": {"actor_success": "Spark."}}]
    assert first.ordered_effects == first.canonical_effects
    assert first.materials == [{"template_id": "ruby_dust", "quantity": 1}]
    assert first.proficiency_policy == {"maximum": 100}
    assert first.plugin_data == {"legacy_note": "kept"}


def test_advanced_operation_registry_operations_are_executable_not_reserved():
    registry = AbilityEffectOperationRegistry()
    for operation in [
        "aura", "stance", "transform", "summon", "dismiss_summon",
        "create_item", "destroy_item", "alter_item", "create_room_effect", "remove_room_effect",
    ]:
        registry.validate(operation)
        assert not registry.is_reserved(operation)
        spec = registry.specs[operation]
        assert spec.executable is True
        assert spec.builder_field_schema["operation"]["const"] == operation
