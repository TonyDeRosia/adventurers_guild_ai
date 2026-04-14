"""Desktop integration capability helpers.

This module centralizes runtime capability detection so packaged desktop mode
can be handled cleanly without scattering platform checks across web runtime
handlers.
"""

from __future__ import annotations

import os
import platform
import sys
import webbrowser
import ctypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.pathing import install_dir, user_data_dir


@dataclass(frozen=True)
class DesktopCapabilities:
    mode: str
    is_frozen: bool
    install_root: str
    user_data_root: str
    native_file_dialogs: bool
    can_open_external_browser: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "is_frozen": self.is_frozen,
            "install_root": self.install_root,
            "user_data_root": self.user_data_root,
            "native_file_dialogs": self.native_file_dialogs,
            "can_open_external_browser": self.can_open_external_browser,
        }


class DesktopIntegration:
    """Own desktop-specific behaviors used by setup/runtime orchestration."""

    def __init__(self) -> None:
        self._capabilities = DesktopCapabilities(
            mode=self._detect_mode(),
            is_frozen=bool(getattr(sys, "frozen", False)),
            install_root=str(install_dir()),
            user_data_root=str(user_data_dir()),
            native_file_dialogs=self._supports_native_file_dialogs(),
            can_open_external_browser=True,
        )

    @property
    def capabilities(self) -> DesktopCapabilities:
        return self._capabilities

    def open_external_url(self, url: str) -> dict[str, Any]:
        target = str(url or "").strip()
        if not target.startswith(("http://", "https://")):
            return {"ok": False, "message": "Only http(s) URLs are allowed."}
        system = platform.system().lower()
        if system == "windows":
            try:
                os.startfile(target)  # type: ignore[attr-defined]
                return {"ok": True, "method": "os.startfile", "url": target}
            except OSError as exc:
                return {"ok": False, "message": f"Could not open browser: {exc}", "method": "os.startfile", "url": target}
        try:
            opened = webbrowser.open(target)
        except webbrowser.Error as exc:
            return {"ok": False, "message": f"Could not open browser: {exc}", "method": "webbrowser.open", "url": target}
        if not opened:
            return {"ok": False, "message": "Browser launch was rejected by the host environment.", "method": "webbrowser.open", "url": target}
        return {"ok": True, "method": "webbrowser.open", "url": target}

    def open_local_path(self, path: str) -> dict[str, Any]:
        target = Path(str(path or "").strip())
        if not str(target):
            return {"ok": False, "message": "Path is required."}
        if not target.exists():
            return {"ok": False, "message": "Path was not found.", "path": str(target)}
        system = platform.system().lower()
        if system == "windows":
            try:
                os.startfile(str(target))  # type: ignore[attr-defined]
                return {"ok": True, "method": "os.startfile", "path": str(target)}
            except OSError as exc:
                return {"ok": False, "message": f"Could not open path: {exc}", "method": "os.startfile", "path": str(target)}
        try:
            opened = webbrowser.open(target.as_uri())
        except (ValueError, webbrowser.Error) as exc:
            return {"ok": False, "message": f"Could not open path: {exc}", "method": "webbrowser.open", "path": str(target)}
        if not opened:
            return {"ok": False, "message": "Path launch was rejected by the host environment.", "method": "webbrowser.open", "path": str(target)}
        return {"ok": True, "method": "webbrowser.open", "path": str(target)}

    def pick_folder(self, title: str, initial_path: str = "") -> dict[str, Any]:
        if not self.capabilities.native_file_dialogs:
            return {"ok": False, "message": "Folder picker is unavailable in this environment."}
        try:
            import tkinter as tk
            from tkinter import filedialog
        except Exception as exc:  # pragma: no cover - import environment specific
            return {"ok": False, "message": "Folder picker is unavailable in this environment.", "error": str(exc)}
        try:
            root = tk.Tk()
            root.withdraw()
            previous_window = self._capture_windows_foreground_window()
            self._prepare_dialog_root(root)
            selected = filedialog.askdirectory(
                title=title,
                initialdir=initial_path or self.capabilities.user_data_root,
                parent=root,
            )
            self._restore_windows_foreground_window(previous_window)
            root.destroy()
        except Exception as exc:  # pragma: no cover - OS GUI behavior specific
            return {"ok": False, "message": "Folder picker could not be opened.", "error": str(exc)}
        if not selected:
            return {"ok": False, "message": "No folder selected."}
        return {"ok": True, "path": selected}

    def pick_file(self, title: str, initial_path: str = "", filters: list[str] | None = None) -> dict[str, Any]:
        if not self.capabilities.native_file_dialogs:
            return {"ok": False, "message": "File picker is unavailable in this environment."}
        try:
            import tkinter as tk
            from tkinter import filedialog
        except Exception as exc:  # pragma: no cover - import environment specific
            return {"ok": False, "message": "File picker is unavailable in this environment.", "error": str(exc)}
        filter_list = filters or [".json"]
        file_types = [("Allowed files", " ".join(f"*{suffix}" for suffix in filter_list)), ("All files", "*.*")]
        initial_dir = str(Path(initial_path).parent) if initial_path else self.capabilities.user_data_root
        try:
            root = tk.Tk()
            root.withdraw()
            previous_window = self._capture_windows_foreground_window()
            self._prepare_dialog_root(root)
            selected = filedialog.askopenfilename(
                title=title,
                initialdir=initial_dir,
                filetypes=file_types,
                parent=root,
            )
            self._restore_windows_foreground_window(previous_window)
            root.destroy()
        except Exception as exc:  # pragma: no cover - OS GUI behavior specific
            return {"ok": False, "message": "File picker could not be opened.", "error": str(exc)}
        if not selected:
            return {"ok": False, "message": "No file selected."}
        return {"ok": True, "path": selected}

    def _detect_mode(self) -> str:
        if getattr(sys, "frozen", False):
            if (install_dir() / "runtime_bundle").exists():
                return "desktop_packaged"
            return "desktop_frozen"
        return "source"

    def _supports_native_file_dialogs(self) -> bool:
        if not self.capabilities_safe_for_gui():
            return False
        try:
            import tkinter  # noqa: F401

            return True
        except Exception:
            return False

    def capabilities_safe_for_gui(self) -> bool:
        if platform.system().lower() == "windows":
            return True
        return bool(os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY"))

    @staticmethod
    def _prepare_dialog_root(root: Any) -> None:
        try:
            root.update_idletasks()
            root.attributes("-topmost", True)
            root.deiconify()
            root.lift()
            root.focus_force()
            root.update()
            root.attributes("-topmost", False)
        except Exception:
            pass

    @staticmethod
    def _capture_windows_foreground_window() -> int | None:
        if platform.system().lower() != "windows":
            return None
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            return int(hwnd) if hwnd else None
        except Exception:
            return None

    @staticmethod
    def _restore_windows_foreground_window(previous_window: int | None) -> None:
        if platform.system().lower() != "windows" or not previous_window:
            return
        try:
            ctypes.windll.user32.SetForegroundWindow(previous_window)
        except Exception:
            return
