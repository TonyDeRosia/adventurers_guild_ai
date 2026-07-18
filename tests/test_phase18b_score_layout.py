from __future__ import annotations

import re
from pathlib import Path

from app.web import WebRuntime
from smart_mud.transport import TelnetTransportAdapter, TransportMessage, WebTransportAdapter


def _entered_runtime(tmp_path: Path, monkeypatch, *, name: str = "Kraevok"):
    monkeypatch.setenv("SMART_MUD_USER_DATA_DIR", str(tmp_path / "user_data"))
    runtime = WebRuntime(Path.cwd())
    runtime.select_world("shattered_realms")
    created = runtime.create_character({"name": name, "race_id": "human", "class_id": "mage"})
    character_id = created["character"]["character_id"]
    runtime.enter_world(character_id)
    return runtime, character_id


def _plain_score(runtime: WebRuntime, command: str = "score") -> str:
    return runtime.mud_input({"text": command})["command_result_text"]


def _assert_score_layout(text: str, alignment: int = 0) -> None:
    assert "CHARACTER STATUS" in text
    assert text.index("Name:") < text.index("Alignment:")
    assert text.index("Race:") < text.index("Alignment:")
    assert text.index("Level:") < text.index("Alignment:")
    assert text.index("Title:") < text.index("Alignment:")
    assert text.index("Class:") < text.index("Alignment:")
    assert text.index("Age:") < text.index("Alignment:")
    assert text.index(f"Alignment: {alignment}") < text.index("Exp:") < text.index("TNL:")
    score_only = text.split("Currencies", 1)[0]
    assert "HP:" not in score_only
    assert "Mana:" not in score_only
    assert "Move:" not in score_only


def _assert_borders_preserved(text: str) -> None:
    frame_lines = [line for line in text.splitlines() if line.startswith(("╔", "║", "╠", "╚"))]
    assert frame_lines
    widths = {len(line) for line in frame_lines}
    assert len(widths) == 1
    assert all(line.endswith(("╗", "║", "╣", "╝")) for line in frame_lines)


def test_score_identity_alignment_progression_order_and_no_resource_duplication(tmp_path: Path, monkeypatch) -> None:
    runtime, _ = _entered_runtime(tmp_path, monkeypatch)
    text = _plain_score(runtime, "score")
    _assert_score_layout(text, 0)


def test_sc_alias_uses_same_score_renderer(tmp_path: Path, monkeypatch) -> None:
    runtime, _ = _entered_runtime(tmp_path, monkeypatch)
    score = _plain_score(runtime, "score")
    sc = _plain_score(runtime, "sc")
    assert score == sc
    _assert_score_layout(sc, 0)


def test_prompt_keeps_hp_mana_move_resources(tmp_path: Path, monkeypatch) -> None:
    runtime, _ = _entered_runtime(tmp_path, monkeypatch)
    preview = runtime.mud_input({"text": "prompt preview compact"})["command_result_text"]
    assert re.search(r"\d+/\d+ HP", preview)
    assert re.search(r"\d+/\d+ MP", preview)
    assert re.search(r"\d+/\d+ ST", preview)


def test_alignment_zero_positive_and_negative_render_after_identity(tmp_path: Path, monkeypatch) -> None:
    runtime, cid = _entered_runtime(tmp_path, monkeypatch)
    char = runtime.mud_runtime.active_characters[cid]
    for alignment in (0, 896, -312):
        char.alignment = alignment
        char.actor_data["alignment"] = alignment
        runtime.mud_runtime.projection_cache.invalidate(cid, "phase18b_score_layout")
        text = _plain_score(runtime, "score")
        _assert_score_layout(text, alignment)


def test_narrow_and_long_title_class_values_preserve_score_borders(tmp_path: Path, monkeypatch) -> None:
    runtime, cid = _entered_runtime(tmp_path, monkeypatch)
    char = runtime.mud_runtime.active_characters[cid]
    char.title = "Keeper of the Very Long Production Reference Title"
    char.class_name = "Battle Mage of the Scholar Necromancer Circle"
    char.actor_data["class_name"] = char.class_name
    char.preferences = {"display_width": 40}
    runtime.mud_runtime.projection_cache.invalidate(cid, "phase18b_score_layout")
    text = _plain_score(runtime, "score")
    _assert_score_layout(text, 0)
    _assert_borders_preserved(text)


def test_api_mud_input_score_layout(tmp_path: Path, monkeypatch) -> None:
    runtime, _ = _entered_runtime(tmp_path, monkeypatch)
    data = runtime.mud_input({"text": "score"})
    _assert_score_layout(data["command_result_text"], 0)
    assert data["output_text"].startswith("> score\n")


def test_web_and_telnet_score_outputs_match_layout(tmp_path: Path, monkeypatch) -> None:
    runtime, cid = _entered_runtime(tmp_path, monkeypatch)
    web = WebTransportAdapter(runtime.mud_runtime)
    telnet = TelnetTransportAdapter(runtime.mud_runtime)
    web_session = web.create_session("web"); web_session.character_id = cid
    telnet_session = telnet.create_session("telnet"); telnet_session.character_id = cid

    web_response = web.handle_message(TransportMessage(web_session, "score"))
    telnet_response = telnet.handle_message(TransportMessage(telnet_session, "score"))

    _assert_score_layout(web_response.output, 0)
    _assert_score_layout(telnet_response.output, 0)
    assert "<span" not in telnet_response.output
