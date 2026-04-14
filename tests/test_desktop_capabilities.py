from __future__ import annotations

import platform
import sys
from types import SimpleNamespace

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


def test_pick_file_uses_parented_foreground_dialog_on_windows(monkeypatch) -> None:
    integration = DesktopIntegration()
    monkeypatch.setattr(
        integration,
        "_capabilities",
        integration.capabilities.__class__(**{**integration.capabilities.to_dict(), "native_file_dialogs": True}),
    )
    monkeypatch.setattr("platform.system", lambda: "Windows")
    monkeypatch.setattr(integration, "_capture_windows_foreground_window", lambda: 123)
    restored: list[int | None] = []
    monkeypatch.setattr(integration, "_restore_windows_foreground_window", lambda hwnd: restored.append(hwnd))
    prepared: list[bool] = []
    monkeypatch.setattr(integration, "_prepare_dialog_root", lambda _root: prepared.append(True))

    class _FakeRoot:
        def withdraw(self):  # noqa: D401 - test shim
            return None

        def destroy(self):
            return None

    called = {}

    def _askopenfilename(**kwargs):
        called.update(kwargs)
        return "C:/ComfyUI.zip"

    fake_dialog = SimpleNamespace(askopenfilename=_askopenfilename)
    fake_tk = SimpleNamespace(Tk=lambda: _FakeRoot(), filedialog=fake_dialog)
    monkeypatch.setitem(sys.modules, "tkinter", fake_tk)
    monkeypatch.setitem(sys.modules, "tkinter.filedialog", fake_dialog)

    result = integration.pick_file("Pick file", "", filters=[".zip"])
    assert result["ok"] is True
    assert "parent" in called
    assert prepared == [True]
    assert restored == [123]
