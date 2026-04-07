"""Primary launcher for Adventurer Guild AI."""

from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import sys
import threading
import time
import traceback
import webbrowser
from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import urlopen

from app.pathing import initialize_user_data_paths, project_root, static_dir

TERMINAL_ENABLE_ENV = "ADVENTURER_GUILD_AI_ENABLE_TERMINAL"


@dataclass
class BrowserLaunchResult:
    success: bool
    method: str
    reason: str = ""


def _print_banner() -> None:
    print("=" * 36)
    print("      Adventurer Guild AI")
    print("=" * 36)


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


def _try_launch_browser(url: str) -> BrowserLaunchResult:
    if platform.system() == "Windows":
        try:
            os.startfile(url)  # type: ignore[attr-defined]
            return BrowserLaunchResult(success=True, method="os.startfile")
        except OSError as exc:
            return BrowserLaunchResult(success=False, method="os.startfile", reason=str(exc))
    try:
        opened = webbrowser.open(url)
        if opened:
            return BrowserLaunchResult(success=True, method="webbrowser.open")
        return BrowserLaunchResult(success=False, method="webbrowser.open", reason="browser reported open=False")
    except webbrowser.Error as exc:
        return BrowserLaunchResult(success=False, method="webbrowser.open", reason=str(exc))


def _launch_browser_when_ready(host: str, port: int) -> None:
    browser_url = f"http://{_browser_host(host)}:{port}"
    print(f"[startup] Waiting for readiness at {browser_url}/health ...")
    ready, reason = _wait_for_web_health(browser_url)
    if not ready:
        print(f"[startup] Health check failed before browser launch: {reason}")
        print(f"[startup] Open this URL manually: {browser_url}")
        return
    print(f"[startup] Health ready at {browser_url}/health")
    print(f"[startup] Attempting browser launch: {browser_url}")
    result = _try_launch_browser(browser_url)
    if result.success:
        print(f"[startup] Opened browser via {result.method}: {browser_url}")
    else:
        print(f"[startup] Could not auto-open browser ({result.method}): {result.reason}")
        print(f"[startup] Open this URL manually: {browser_url}")


def _is_port_available(host: str, port: int) -> tuple[bool, str]:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError as exc:
            return False, str(exc)
    return True, ""
def main() -> int:
    _print_banner()
    print("[startup] Initializing systems...")

    try:
        args = _parse_args()
        _initialize_paths()

        launch_mode = "terminal" if args.terminal else args.mode
        frozen = bool(getattr(sys, "frozen", False))
        terminal_enabled = os.getenv(TERMINAL_ENABLE_ENV, "").strip().lower() in {"1", "true", "yes", "on"}
        if launch_mode == "terminal" and frozen and not terminal_enabled:
            print("Terminal mode is disabled in standard end-user builds. Launching browser UI instead.")
            launch_mode = "web"

        if launch_mode == "web":
            from app.web import FastAPI, WebRuntime, _resolve_static_root, create_web_app, uvicorn

            if FastAPI is None or uvicorn is None:
                raise RuntimeError("FastAPI/uvicorn is not installed. Install dependencies and try again.")

            available, reason = _is_port_available(args.host, args.port)
            if not available:
                print(
                    f"[startup] Port {args.port} is already in use on host {args.host}. "
                    f"Please stop the other process or choose a different port."
                )
                print(f"[startup] Port check detail: {reason}")
                return 1

            runtime = WebRuntime(project_root())
            app = create_web_app(runtime=runtime, static_root=_resolve_static_root())

            opener_thread = threading.Thread(
                target=_launch_browser_when_ready,
                args=(args.host, args.port),
                daemon=True,
                name="browser-launcher",
            )
            opener_thread.start()

            print(f"[startup] Starting backend (uvicorn) at http://{args.host}:{args.port} ...")
            uvicorn.run(app, host=args.host, port=args.port, log_level="info")
            return 0

        from app.main import main as terminal_main

        print("Starting terminal mode (fallback/debug)...")
        terminal_main()
        return 0
    except KeyboardInterrupt:
        print("\n[startup] Shutdown requested. Goodbye.")
        return 0
    except Exception as exc:  # pragma: no cover - defensive UX fallback
        print("\n[startup] Startup failed. The game could not be started.")
        print(f"[startup] Error: {exc}")
        print("\nDebug trace:")
        print(traceback.format_exc())
        if os.name == "nt":
            try:
                input("Press Enter to close...")
            except EOFError:
                pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
