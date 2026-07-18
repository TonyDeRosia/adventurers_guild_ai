from smart_mud.builder_rendering.medit import strip_ansi, visible_len, render_medit_main, render_medit_flags
from smart_mud.builder import MEDIT_MOBILE_FLAGS, MEDIT_AFFECT_FLAGS
from tests.test_builder_list_filters_phase4h_hotfix import engine_with_pack, text, runtime_with_pack, runtime_text


def test_phase16e_live_medit_main_uses_tba_shape(isolated_builder_world):
    engine, actor = engine_with_pack(isolated_builder_world)
    out = text(engine, actor, "medit training_master_borik")
    for needle in ["1) Sex:", "2) Keywords:", "3) S-Desc:", "4) L-Desc:-", "5) D-Desc:-", "6) Position", "7) Default", "8) Attack", "9) Stats Menu...", "I) Identity / Traits", "A) NPC Flags", "B) AFF Flags", "P) Pet Price", "R) Loadout / Loot", "S) Script", "U) Combat Abilities", "V) Event Reactions", "W) Copy mob", "X) Delete mob", "Q) Quit", "Enter choice :"]:
        assert needle in out
    assert "Mobile Editor" not in out
    assert "1. Identity" not in out
    assert "20. Diagnostics" not in out


def test_phase16e_live_medit_single_key_submenus(isolated_builder_world):
    engine, actor = engine_with_pack(isolated_builder_world)
    text(engine, actor, "medit training_master_borik")
    assert "Enter mob flags (0 to quit) :" in text(engine, actor, "A")
    assert "Enter choice :" in text(engine, actor, "0")
    assert "Enter aff flags (0 to quit) :" in text(engine, actor, "B")
    assert "Enter choice :" in text(engine, actor, "0")
    assert "MOB BUILD:" in text(engine, actor, "9")
    assert "Enter choice :" in text(engine, actor, "q")
    assert "Combat Abilities" in text(engine, actor, "U")
    assert "Event Reactions" in (text(engine, actor, "q") and text(engine, actor, "V"))
    assert "Mob Identity / Traits" in (text(engine, actor, "q") and text(engine, actor, "I"))
    assert "Loadout / Loot" in (text(engine, actor, "q") and text(engine, actor, "R"))
    assert "Scripts:" in (text(engine, actor, "q") and text(engine, actor, "S"))


def test_phase16e_runtime_path_medit_main(isolated_builder_world):
    rt, cid = runtime_with_pack(isolated_builder_world)
    out = runtime_text(rt, cid, "medit training_master_borik")
    assert "1) Sex:" in out and "A) NPC Flags" in out and "Enter choice :" in out
    assert "1. Identity" not in out


def test_phase16e_width_helpers_and_flag_columns():
    ansi = "\033[32m1)\033[0m Sex: \033[33mmale\033[0m"
    assert visible_len(ansi) == len("1) Sex: male")
    class S: pass
    s=S(); s.working_record={"mobile_flags":["stay_zone"], "affect_flags":[]}; s.object_id="mob"
    mob = render_medit_flags(s, "mobile_flags", MEDIT_MOBILE_FLAGS, 80)
    aff = render_medit_flags(s, "affect_flags", MEDIT_AFFECT_FLAGS, 140)
    assert "1) SENTINEL" in mob and "2) STAY-ZONE" in mob
    assert "Current flags : STAY-ZONE" in mob
    assert "Current flags : NOBITS" in aff
    assert max(len(line) for line in strip_ansi(mob).splitlines()) <= 80
