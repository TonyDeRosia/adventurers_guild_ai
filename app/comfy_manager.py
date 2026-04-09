"""Managed ComfyUI subprocess lifecycle helpers.

This module isolates process ownership so the UI/runtime can safely start
and stop a local image backend in packaged desktop mode.
"""

from __future__ import annotations

import os
import subprocess
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO


@dataclass
class ManagedProcessSnapshot:
    managed: bool
    running: bool
    pid: int | None
    launch_target: str
    startup_log_file: str
    started_at: str


class ComfyProcessManager:
    """Track and control a ComfyUI child process started by this app."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None
        self._log_handle: TextIO | None = None
        self._launch_target: str = ""
        self._startup_log_file: str = ""
        self._started_at: str = ""

    def is_managed_running(self) -> bool:
        with self._lock:
            return self._process is not None and self._process.poll() is None

    def register(self, process: subprocess.Popen[str], *, launch_target: str, startup_log_file: Path) -> None:
        with self._lock:
            self._process = process
            self._launch_target = launch_target
            self._startup_log_file = str(startup_log_file)
            self._started_at = datetime.now(timezone.utc).isoformat()

    def bind_log_handle(self, handle: TextIO | None) -> None:
        with self._lock:
            self._log_handle = handle

    def clear_if_exited(self) -> None:
        with self._lock:
            if self._process is None:
                return
            if self._process.poll() is None:
                return
            self._process = None
            self._close_log_handle_locked()

    def snapshot(self) -> ManagedProcessSnapshot:
        with self._lock:
            running = self._process is not None and self._process.poll() is None
            pid = self._process.pid if self._process else None
            return ManagedProcessSnapshot(
                managed=self._process is not None,
                running=running,
                pid=pid,
                launch_target=self._launch_target,
                startup_log_file=self._startup_log_file,
                started_at=self._started_at,
            )

    def shutdown(self, timeout_seconds: float = 8.0) -> bool:
        with self._lock:
            process = self._process
            if process is None:
                return True
            if process.poll() is not None:
                self._process = None
                self._close_log_handle_locked()
                return True

            try:
                if os.name == "nt":
                    process.terminate()
                else:
                    process.terminate()
                process.wait(timeout=timeout_seconds)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    process.kill()
                    process.wait(timeout=2.0)
                except (OSError, subprocess.TimeoutExpired):
                    return False
            finally:
                self._process = None
                self._close_log_handle_locked()
            return True

    def _close_log_handle_locked(self) -> None:
        if self._log_handle:
            try:
                self._log_handle.flush()
                self._log_handle.close()
            except OSError:
                pass
        self._log_handle = None
