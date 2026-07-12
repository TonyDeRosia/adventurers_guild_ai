from types import SimpleNamespace

from engine.mud_displays import (
    DisplayDocument,
    DisplayIntent,
    DisplaySection,
    build_equipment_document,
    build_inventory_document,
    build_prompt_document,
    normalize_sentence,
    render_display_html,
    render_display_mud,
    render_display_plain,
)
from engine.mud_rendering import render_semantic_plain


def test_display_intent_vocabulary_and_structured_rendering():
    doc = DisplayDocument(
        DisplayIntent.SCORE,
        title="Score",
        semantic_role="system",
        sections=[DisplaySection(title="Resources", fields=[("Health", "85 / 100"), ("Mana", "42 / 50")])],
    )
    plain = render_display_plain(doc)
    assert doc.intent == DisplayIntent.SCORE
    assert plain.splitlines() == ["Score", "", "Resources", "Health: 85 / 100", "Mana: 42 / 50"]
    assert "\n\n\n" not in plain
    assert render_semantic_plain(render_display_mud(doc)) == plain
    html = render_display_html(doc)
    assert '<span role="system">' in html
    assert "Score" in html


def test_inventory_groups_duplicates_without_losing_instance_metadata():
    items = [
        {"instance_id": "a", "name": "trail ration", "stack_count": 1, "condition": "normal"},
        {"instance_id": "b", "name": "trail ration", "stack_count": 2, "condition": "normal"},
        {"instance_id": "c", "name": "dented flask", "stack_count": 1, "condition": "worn"},
    ]
    doc = build_inventory_document(items, carrying="3 / 50 weight")
    text = render_display_plain(doc)
    assert "Inventory" in text
    assert "3x trail ration" in text
    assert "dented flask" in text
    assert "Carrying\n3 / 50 weight" in text
    ration = doc.sections[0].entries[0]
    assert ration.metadata["instance_ids"] == ["a", "b"]


def test_equipment_slots_and_prompt_are_canonical():
    eq = build_equipment_document(
        [{"name": "a chipped longsword", "equipped_slot": "main_hand"}],
        ["head", "main_hand", "off_hand"],
    )
    text = render_display_plain(eq)
    assert text.startswith("Equipment")
    assert "Head: nothing" in text
    assert "Main hand: a chipped longsword" in text
    assert "Off hand: nothing" in text

    character = SimpleNamespace(hp=85, max_hp=100, mana=42, max_mana=50, stamina=91, max_stamina=100)
    prompt = render_display_plain(build_prompt_document(character))
    assert prompt == "[85/100 HP 42/50 MP 91/100 ST]"


def test_punctuation_normalization_for_engine_fallbacks():
    assert normalize_sentence("You see nothing special..") == "You see nothing special."
    assert normalize_sentence("What do you want??") == "What do you want?"
    assert normalize_sentence("You cannot do that") == "You cannot do that."


def test_phase13c1c_room_content_equipment_and_prompt_roles():
    from engine.mud_displays import build_room_document

    room = SimpleNamespace(
        title="Training Yard",
        description="Packed dirt fills the yard.",
        players=[{"entity_type": "player", "name": "Scout"}],
        npcs=[{"entity_type": "npc", "name": "Training Master Borik", "room_description": "Training Master Borik watches the yard with his arms folded."}],
        mobs=[{"entity_type": "mob", "name": "cellar rat", "room_description": "A cellar rat skitters here."}],
        objects=[{"entity_type": "object", "name": "Old Gate Shard", "room_description": "An Old Gate Shard rests here."}, {"entity_type": "object", "name": "Fountain", "room_description": "A Fountain burbles here."}, {"entity_type": "campfire", "name": "campfire", "room_description": "A campfire crackles here."}],
        exits=[{"direction": "north"}],
    )
    doc = build_room_document(room)
    assert doc.title_role == "room_name"
    assert doc.paragraphs[0].role == "room_description"
    visible = doc.sections[0]
    assert visible.title == "You see:"
    assert visible.title_role == "contents_heading"
    assert {e.role for e in visible.entries} == {"content"}
    assert doc.sections[-1].lines[0].role == "exit"
    html = render_display_html(doc)
    assert 'role="contents_heading">You see:' in html
    assert 'role="content">Training Master Borik watches the yard with his arms folded.' in html
    assert 'role="content">Old Gate Shard' in html
    assert 'role="content">Fountain' in html
    assert 'role="content">campfire' in html
    assert 'role="exit">[ Exits: north ]' in html

    eq = build_equipment_document(
        [{"name": "&Ya legendary golden sword&n", "equipped_slot": "main_hand", "trusted_markup": True}],
        ["main_hand", "off_hand"],
    )
    fields = eq.sections[0].fields
    assert fields[0].label_role == "equipment_slot"
    assert fields[0].value_role == "equipment_item"
    assert fields[0].trusted_markup is True and fields[0].occupied is True
    assert fields[1].value_role == "equipment_empty"
    eq_html = render_display_html(eq)
    assert 'role="equipment_item"' in eq_html and 'mud-color-yellow' in eq_html
    assert 'role="equipment_empty">nothing</span>' in eq_html
    assert "<script" not in eq_html

    character = SimpleNamespace(hp=46, max_hp=100, mana=50, max_mana=50, stamina=100, max_stamina=100)
    prompt_doc = build_prompt_document(character)
    assert [s.role for s in prompt_doc.lines[0].segments] == ["prompt_marker", "prompt_hp", "prompt", "prompt_mana", "prompt", "prompt_stamina", "prompt_marker"]
    assert render_display_plain(prompt_doc) == "[46/100 HP 50/50 MP 100/100 ST]"
    prompt_html = render_display_html(prompt_doc)
    assert prompt_html.count('role="prompt_hp"') == 1
    assert prompt_html.count('role="prompt_mana"') == 1
    assert prompt_html.count('role="prompt_stamina"') == 1
