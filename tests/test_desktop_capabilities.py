from __future__ import annotations

import platform

from app.desktop_capabilities import DesktopIntegration


def test_open_external_url_rejects_non_http_scheme() -> None:
    integration = DesktopIntegration()
    result = integration.open_external_url("file:///tmp/test")
    assert result["ok"] is False
    assert "http(s)" in result["message"]


def test_detect_mode_source_when_not_frozen(monkeypatch) -> None:
    monkeypatch.setattr("sys.frozen", False, raising=False)
    integration = DesktopIntegration()
    assert integration.capabilities.mode == "source"


def test_capabilities_can_be_serialized() -> None:
    integration = DesktopIntegration()
    payload = integration.capabilities.to_dict()
    assert payload["mode"] in {"source", "desktop_packaged", "desktop_frozen"}
    assert isinstance(payload["is_frozen"], bool)
    assert isinstance(payload["can_open_external_browser"], bool)


def test_gui_capability_respects_non_windows_display(monkeypatch) -> None:
    integration = DesktopIntegration()
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    assert integration.capabilities_safe_for_gui() is False
