from pathlib import Path

from engine.abilities import AbilityRuntimeGateway


class _Actor:
    actor_id = "actor_1"


class _Actors:
    def get(self, character_id):
        return _Actor() if character_id == "char_1" else None


class _Ability:
    id = "recall"
    name = "Recall"
    short_name = "Recall"
    plugin_data = {"aliases": ["recall"], "command": "recall"}


class _Registry:
    abilities = {"recall": _Ability()}


class _Service:
    actor_registry = _Actors()
    registry = _Registry()

    def get_actor_abilities(self, actor_id):
        assert actor_id == "actor_1"
        return [{"id": "recall", "name": "Recall", "ability_type": "spell"}]


def test_recall_command_forms_resolve_same_canonical_ability():
    gateway = AbilityRuntimeGateway(_Service())
    forms = ["recall", "cast recall", "use recall", "invoke recall", "perform recall", "Recall", "cast Recall"]
    assert {gateway.resolve_ability("actor_1", form) for form in forms} == {"recall"}


def test_static_shell_removes_status_bar_and_adds_account_panel():
    html = Path("app/static/index.html").read_text()
    js = Path("app/static/app.js").read_text()
    css = Path("app/static/styles.css").read_text()
    assert 'id="status-line"' not in html
    assert "status-stack" not in html
    assert 'id="mud-account-panel"' in html
    assert "function isPlaying()" in js
    assert "not_playing" not in js  # client uses human transient; server owns structured errors
    assert ".mud-account-panel" in css
    assert "lower-left" in css or "bottom: 12px" in css

from tests.test_phase12b2_starter_runtime import make_rt, text


def test_recall_aliases_share_world_time_cooldown(tmp_path):
    rt, cid = make_rt(tmp_path)
    assert "silver light" in text(rt, cid, "cast recall").lower()
    assert "Ready in 5 game minutes" in text(rt, cid, "recall")
    rt.advance_world_time("shattered_realms", 1)
    assert "Ready in 4 game minutes" in text(rt, cid, "cast recall")
    rt.advance_world_time("shattered_realms", 4)
    assert "silver light" in text(rt, cid, "use recall").lower()
