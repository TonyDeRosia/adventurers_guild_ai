from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from app.comfy_manager import ComfyProcessManager


def _long_running_process() -> subprocess.Popen[str]:
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])


def test_manager_register_and_snapshot_running() -> None:
    manager = ComfyProcessManager()
    process = _long_running_process()
    try:
        manager.register(process, launch_target="python main.py", startup_log_file=Path("startup.log"))
        snap = manager.snapshot()
        assert snap.managed is True
        assert snap.running is True
        assert snap.pid == process.pid
        assert snap.launch_target == "python main.py"
    finally:
        manager.shutdown(timeout_seconds=1.0)


def test_manager_clear_if_exited() -> None:
    manager = ComfyProcessManager()
    process = subprocess.Popen([sys.executable, "-c", "print('done')"])
    process.wait(timeout=5)

    manager.register(process, launch_target="python quick.py", startup_log_file=Path("startup.log"))
    manager.clear_if_exited()

    snap = manager.snapshot()
    assert snap.managed is False
    assert snap.running is False
    assert snap.pid is None


def test_manager_shutdown_stops_process() -> None:
    manager = ComfyProcessManager()
    process = _long_running_process()
    manager.register(process, launch_target="python main.py", startup_log_file=Path("startup.log"))

    stopped = manager.shutdown(timeout_seconds=1.0)
    assert stopped is True

    time.sleep(0.05)
    assert process.poll() is not None
    snap = manager.snapshot()
    assert snap.running is False
