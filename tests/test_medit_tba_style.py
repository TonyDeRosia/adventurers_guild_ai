import re

from smart_mud.builder import BuilderService, BuilderWorkspace, _medit_wrap

class Actor:
    id = "builder"
    role = "admin"
    account_id = "acct"


def svc(tmp_path):
    service = BuilderService(BuilderWorkspace(tmp_path))
    rec = {
        "id": "hired_muscle", "vnum": 32, "name": "the hired muscle",
        "keywords": ["hired", "muscle"], "gender": "male",
        "short_description": "the hired muscle",
        "room_description": "Some hired muscle is willing to do just about anything for the right price.",
        "look_description": "This grisly mercenary is covered in scars from numerous fights. His eyes show an intense hatred and a blankness of intelligence that seems to convey the truth about brawn without brains.",
        "mobile_flags": ["isnpc", "stay_zone"],
    }
    assert service.create_or_update_mobile(Actor(), "hired_muscle", rec).ok
    opened = service.start_editor(Actor(), "medit", "entities", "hired_muscle")
    assert opened.ok
    return service, service.sessions.active["builder"], opened.message


def test_live_start_editor_medit_screen_is_tba_record_menu(tmp_path):
    _, _, text = svc(tmp_path)
    for needle in ["1) Sex:", "2) Keywords:", "3) S-Desc:", "4) L-Desc:-", "5) D-Desc:-", "6) Position", "7) Default", "8) Attack", "9) Stats Menu...", "I) Identity / Traits", "A) NPC Flags", "B) AFF Flags", "P) Pet Price", "R) Loadout / Loot", "S) Script", "U) Combat Abilities", "V) Event Reactions", "W) Copy mob", "X) Delete mob", "Q) Quit", "Enter choice :"]:
        assert needle in text
    assert "1. Identity" not in text
    assert "20. Diagnostics" not in text
    assert "MOBILE EDITOR" not in text


def test_medit_single_key_submenus(tmp_path):
    service, sess, _ = svc(tmp_path)
    outputs = {cmd: service.handle_session_input(Actor(), sess, cmd).message for cmd in ["A"]}
    service.handle_session_input(Actor(), sess, "q")
    outputs["B"] = service.handle_session_input(Actor(), sess, "B").message
    service.handle_session_input(Actor(), sess, "q")
    outputs["9"] = service.handle_session_input(Actor(), sess, "9").message
    service.handle_session_input(Actor(), sess, "q")
    outputs["I"] = service.handle_session_input(Actor(), sess, "I").message
    assert "Enter mob flags (0 to quit) :" in outputs["A"]
    assert "Current flags : ISNPC STAY-ZONE" in outputs["A"]
    assert "Enter aff flags (0 to quit) :" in outputs["B"]
    assert "Current flags : NOBITS" in outputs["B"]
    assert "MOB BUILD: [32] the hired muscle" in outputs["9"]
    assert "-- Mob Identity / Traits: [32] the hired muscle" in outputs["I"]


def test_description_wrapping_visible_width_plain_text():
    lines = _medit_wrap("one two three four five six seven eight nine ten " * 4, 60, indent="   ")
    assert all(len(line) <= 60 for line in lines)
    assert lines[0].startswith("   ")
