from types import SimpleNamespace

from engine.display_themes import resolve_effective_display_theme
from engine.mud_displays import build_score_document, build_affects_document, build_prompt_document, render_display_plain
from engine.mud_commands import MudCommandEngine
from smart_mud.builder import BuilderWorkspace


def _char(**prefs):
    return SimpleNamespace(id="c", name="Hero", role="builder", account_role="builder", world_id="shattered_realms", room_id="guildhall_crossing", hp=9, max_hp=10, mana=4, max_mana=5, stamina=3, max_stamina=6, level=2, xp=1, gold=7, attributes={"strength":{"final":11}}, calculated_stats={"armor":2}, inventory=[], equipment={}, affects={}, preferences=prefs)


def test_scope_precedence_from_builder_world_zone_area(tmp_path):
    bw=BuilderWorkspace(worlds_dir=tmp_path); drafts=bw.load("shattered_realms")
    drafts["world"]["shattered_realms"]={"id":"shattered_realms","default_display_theme_id":"classic_adventurer"}
    drafts["areas"]["a"]={"id":"a","name":"A","world_id":"shattered_realms","display_theme_id":"minimal_modern"}
    drafts["zones"]["z"]={"id":"z","name":"Z","world_id":"shattered_realms","area_id":"a","room_ids":["r"],"display_theme_id":"classic_adventurer"}
    bw.save_drafts("shattered_realms", drafts)
    c=_char(); c.room_id="r"
    theme=resolve_effective_display_theme(c, world_root=tmp_path/"shattered_realms")
    assert theme.theme_id == "minimal_modern" and theme.source_scope == "area"
    c.preferences={"display_theme":"classic_adventurer", "no_color": True, "high_contrast": True, "colorblind": True, "reduced_decoration": True}
    theme=resolve_effective_display_theme(c, world_root=tmp_path/"shattered_realms")
    assert theme.source_scope == "player" and not theme.color_enabled and "no_color" in theme.accessibility and theme.frame_style == "minimal"


def test_score_section_order_visibility_and_empty_policy():
    c=_char()
    theme=SimpleNamespace(width=60, frame_style="classic_single", title_alignment="left", labels={}, border_characters={}, divider_characters={}, section_order=("currency","identity","resources"), visible_sections=("currency","identity","resources"), empty_section_policy="show_empty_message")
    out=render_display_plain(build_score_document(c, theme=theme))
    assert out.find("Gold") < out.find("Name") < out.find("HP")
    assert "Armor" not in out


def test_themed_affects_hides_secret_and_shows_roles():
    theme=SimpleNamespace(width=60, frame_style="classic_single", title_alignment="center", labels={}, border_characters={}, divider_characters={}, empty_section_policy="show_empty_message")
    out=render_display_plain(build_affects_document([{"name":"bless","type":"beneficial","duration":"1 minute","stacks":2,"description":"Bright."},{"name":"curse","hidden":True}], theme=theme))
    assert "Bless" in out and "1 minute" in out and "Stacks: 2" in out and "curse" not in out.lower()


def test_displaytheme_assignment_persists_to_builder_drafts(tmp_path):
    e=MudCommandEngine(); e.builder=BuilderWorkspace(worlds_dir=tmp_path); c=_char()
    drafts=e.builder.load("shattered_realms"); drafts["areas"]["a"]={"id":"a","name":"A","world_id":"shattered_realms"}; drafts["zones"]["z"]={"id":"z","name":"Z","area_id":"a","world_id":"shattered_realms"}; e.builder.save_drafts("shattered_realms", drafts)
    assert e._cmd_displaytheme(c, ["assign","world","classic_adventurer"], "").ok
    assert e._cmd_displaytheme(c, ["assign","zone","z","score","minimal_modern"], "").ok
    saved=e.builder.load("shattered_realms")
    assert saved["world"]["shattered_realms"]["default_display_theme_id"] == "classic_adventurer"
    assert saved["zones"]["z"]["display_theme_ids"]["score"] == "minimal_modern"


def test_prompt_theme_default_template_is_used():
    c=_char()
    theme=SimpleNamespace(prompt_presets={"classic":"[%n %h/%H]"})
    assert "Hero 9/10" in render_display_plain(build_prompt_document(c, theme=theme))
