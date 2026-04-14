"""Primary launcher for Adventurer Guild AI."""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import platform
import socket
import subprocess
import sys
import time
import traceback
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from app.pathing import initialize_user_data_paths, project_root, static_dir

TERMINAL_ENABLE_ENV = "ADVENTURER_GUILD_AI_ENABLE_TERMINAL"
BACKEND_READY_TIMEOUT_SECONDS = 30.0


def _print_banner() -> None:
    print("=" * 36)
    print("      Adventurer Guild AI")
    print("=" * 36)


def _startup_log_file() -> Path:
    try:
        return initialize_user_data_paths().logs / "startup.log"
    except Exception:
        return Path.cwd() / "logs" / "startup.log"


def _log_startup(message: str) -> None:
    try:
        log_path = _startup_log_file()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        stamp = _dt.datetime.now().isoformat(timespec="seconds")
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"[{stamp}] {message}\n")
    except Exception:
        return


def _can_prompt_for_exit() -> bool:
    stdin = getattr(sys, "stdin", None)
    if stdin is None:
        return False
    if getattr(stdin, "closed", False):
        return False
    isatty = getattr(stdin, "isatty", None)
    if callable(isatty):
        try:
            return bool(isatty())
        except OSError:
            return False
    return False


def _initialize_paths() -> None:
    root = project_root()
    paths = initialize_user_data_paths()
    resolved_static = static_dir()
    if not resolved_static.exists():
        print(f"Warning: static assets not found at {resolved_static}")
    print(f"Runtime root: {root}")
    print(f"Content data: {paths.content_data}")
    print(f"User data: {paths.user_data}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start Adventurer Guild AI")
    parser.add_argument(
        "--terminal",
        action="store_true",
        help="Launch terminal mode (fallback/debug interface).",
    )
    parser.add_argument(
        "--mode",
        choices=["terminal", "web"],
        default="web",
        help="Choose interface mode",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Web host (web mode only)")
    parser.add_argument("--port", type=int, default=8000, help="Web port (web mode only)")
    parser.add_argument("--backend-only", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args()


def _browser_host(host: str) -> str:
    return "127.0.0.1" if host in {"0.0.0.0", "::"} else host


def _wait_for_web_health(base_url: str, timeout_seconds: float = 15.0) -> tuple[bool, str]:
    deadline = time.time() + timeout_seconds
    last_reason = "health endpoint unavailable"
    while time.time() < deadline:
        try:
            with urlopen(f"{base_url}/health", timeout=1.0) as response:
                payload = response.read().decode("utf-8", errors="replace")
                if response.status == 200:
                    try:
                        parsed = json.loads(payload)
                    except json.JSONDecodeError:
                        parsed = {}
                    if isinstance(parsed, dict) and str(parsed.get("status", "")).lower() == "ok":
                        return True, "ready"
                    last_reason = "health response did not include status ok"
                else:
                    last_reason = f"health returned HTTP {response.status}"
        except URLError as exc:
            last_reason = str(exc.reason) if getattr(exc, "reason", None) else str(exc)
        except OSError as exc:
            last_reason = str(exc)
        time.sleep(0.2)
    return False, last_reason


def _build_backend_command(host: str, port: int) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--backend-only", "--host", host, "--port", str(port)]
    launcher = Path(__file__).resolve()
    return [sys.executable, str(launcher), "--backend-only", "--host", host, "--port", str(port)]


def _spawn_backend_process(host: str, port: int) -> subprocess.Popen[bytes]:
    command = _build_backend_command(host, port)
    print(f"[startup] Launching backend process: {' '.join(command)}")
    creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP if platform.system() == "Windows" else 0
    return subprocess.Popen(command, creationflags=creation_flags)


def _wait_for_backend_ready(process: subprocess.Popen[bytes], base_url: str, timeout_seconds: float) -> tuple[bool, str]:
    deadline = time.time() + timeout_seconds
    last_reason = "health endpoint unavailable"
    while time.time() < deadline:
        code = process.poll()
        if code is not None:
            return False, f"backend process exited with code {code} before readiness"
        ready, reason = _wait_for_web_health(base_url, timeout_seconds=1.0)
        if ready:
            return True, "ready"
        last_reason = reason
        time.sleep(0.2)
    return False, f"timed out after {timeout_seconds:.0f}s: {last_reason}"


def _stop_backend_process(process: subprocess.Popen[bytes], timeout_seconds: float = 8.0) -> None:
    if process.poll() is not None:
        return
    print("[shutdown] Stopping backend process...")
    process.terminate()
    try:
        process.wait(timeout=timeout_seconds)
        print("[shutdown] Backend process stopped.")
    except subprocess.TimeoutExpired:
        print("[shutdown] Backend process did not exit in time; forcing termination.")
        process.kill()
        process.wait(timeout=2.0)


def _launch_webview_window(url: str) -> None:
    try:
        import webview
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "PyWebView is required for desktop launch but is not installed. "
            "Install dependencies (pip install -r requirements.txt) and try again."
        ) from exc

    webview.create_window("Adventurers Guild AI", url, width=1280, height=800, resizable=True)
    webview.start()


def _is_port_available(host: str, port: int) -> tuple[bool, str]:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError as exc:
            return False, str(exc)
    return True, ""


def _run_backend_server(host: str, port: int) -> int:
    from app.web import FastAPI, WebRuntime, _resolve_static_root, create_web_app, uvicorn

    if FastAPI is None or uvicorn is None:
        raise RuntimeError("FastAPI/uvicorn is not installed. Install dependencies and try again.")

    runtime = WebRuntime(project_root())
    app = create_web_app(runtime=runtime, static_root=_resolve_static_root())
    print(f"[startup] Starting backend (uvicorn) at http://{host}:{port} ...")
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0
def main() -> int:
    _print_banner()
    print("[startup] Initializing systems...")
    _log_startup("Startup sequence started.")

    try:
        args = _parse_args()
        _log_startup(f"Launch args parsed: mode={args.mode} terminal={args.terminal} host={args.host} port={args.port}")
        _initialize_paths()

        launch_mode = "terminal" if args.terminal else args.mode
        if args.backend_only:
            return _run_backend_server(args.host, args.port)

        frozen = bool(getattr(sys, "frozen", False))
        terminal_enabled = os.getenv(TERMINAL_ENABLE_ENV, "").strip().lower() in {"1", "true", "yes", "on"}
        if launch_mode == "terminal" and frozen and not terminal_enabled:
            print("Terminal mode is disabled in standard end-user builds. Launching browser UI instead.")
            launch_mode = "web"

        if launch_mode == "web":
            available, reason = _is_port_available(args.host, args.port)
            if not available:
                print(
                    f"[startup] Port {args.port} is already in use on host {args.host}. "
                    f"Please stop the other process or choose a different port."
                )
                print(f"[startup] Port check detail: {reason}")
                _log_startup(f"Port check failed: host={args.host} port={args.port} detail={reason}")
                return 1

            browser_url = f"http://{_browser_host(args.host)}:{args.port}"
            backend_process = _spawn_backend_process(args.host, args.port)
            print(f"[startup] Waiting for readiness at {browser_url}/health ...")
            ready, reason = _wait_for_backend_ready(
                backend_process, browser_url, timeout_seconds=BACKEND_READY_TIMEOUT_SECONDS
            )
            if not ready:
                print(f"[startup] Backend failed to become ready: {reason}")
                _log_startup(f"Backend readiness failed: {reason}")
                _stop_backend_process(backend_process)
                return 1

            print(f"[startup] Health ready at {browser_url}/health")
            print(f"[startup] Opening desktop window at {browser_url}")
            try:
                _launch_webview_window(browser_url)
            finally:
                _stop_backend_process(backend_process)
            _log_startup("Web mode exited cleanly.")
            return 0

        from app.main import main as terminal_main

        print("Starting terminal mode (fallback/debug)...")
        terminal_main()
        _log_startup("Terminal mode exited cleanly.")
        return 0
    except KeyboardInterrupt:
        print("\n[startup] Shutdown requested. Goodbye.")
        return 0
    except Exception as exc:  # pragma: no cover - defensive UX fallback
        print("\n[startup] Startup failed. The game could not be started.")
        print(f"[startup] Error: {exc}")
        print("\nDebug trace:")
        trace = traceback.format_exc()
        print(trace)
        log_file = _startup_log_file()
        _log_startup(f"Startup failed: {exc}\n{trace}")
        print(f"[startup] Failure details were written to: {log_file}")
        if os.name == "nt" and _can_prompt_for_exit():
            try:
                input("Press Enter to close...")
            except (EOFError, OSError, RuntimeError):
                pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
