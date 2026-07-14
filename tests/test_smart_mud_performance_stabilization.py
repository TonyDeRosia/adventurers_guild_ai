from pathlib import Path


def test_frontend_has_no_permanent_full_view_interval() -> None:
    js = Path('app/static/app.js').read_text(encoding='utf-8')
    assert 'setInterval(pollPlayView, 1200)' not in js
    assert 'pollPlayView' not in js
    assert '/api/mud/async-messages' in js
    assert 'mudRefreshController' in js


def test_frontend_commands_do_not_auto_refresh_full_view() -> None:
    js = Path('app/static/app.js').read_text(encoding='utf-8')
    send = js.split('async function sendInput', 1)[1].split('function openSettings', 1)[0]
    assert '/api/mud/input' in send
    assert '/api/mud/play-view' not in send
    assert 'appendMudOutput' in send


def test_frontend_stops_async_on_quit_logout_and_state_changes() -> None:
    js = Path('app/static/app.js').read_text(encoding='utf-8')
    assert 'mudRefreshController.stop(); mudSessionState=state' in js
    assert "mudRefreshController.stop(); await api('/api/mud/account/logout'" in js
    assert "if(d.session_transition==='character_select'){mudRefreshController.stop();" in js
    assert "beforeunload',()=>mudRefreshController.stop()" in js


def test_frontend_prevents_overlapping_async_and_stale_playview() -> None:
    js = Path('app/static/app.js').read_text(encoding='utf-8')
    assert 'if(this.inFlight)' in js
    assert 'AbortController' in js
    assert 'const seq=++mudRefreshSeq' in js
    assert 'if(seq<mudAppliedSeq)return' in js


def test_backend_play_view_uses_resident_character_source() -> None:
    py = Path('engine/mud_runtime.py').read_text(encoding='utf-8')
    play = py.split('def play_view(self, character_id: str)', 1)[1].split('def async_messages', 1)[0]
    assert 'self._resident_character(character_id)' in play
    assert 'state_store.load_character(character_id)' not in play
    web = Path('app/web.py').read_text(encoding='utf-8')
    norm = web.split('def _normalize_mud_view', 1)[1].split('def play_view(self)', 1)[0]
    assert 'state_store.load_character' not in norm


def test_backend_async_messages_are_lightweight() -> None:
    py = Path('engine/mud_runtime.py').read_text(encoding='utf-8')
    async_part = py.split('def async_messages', 1)[1].split('def _builder_visible', 1)[0]
    assert 'render_room' not in async_part
    assert 'load_character' not in async_part
    assert 'message_id' in async_part
