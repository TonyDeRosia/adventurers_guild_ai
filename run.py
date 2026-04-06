"""Primary launcher for Adventurer Guild AI."""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time
import traceback
import webbrowser
from urllib.error import URLError
from urllib.request import urlopen

from app.pathing import initialize_user_data_paths, project_root, static_dir

TERMINAL_ENABLE_ENV = "ADVENTURER_GUILD_AI_ENABLE_TERMINAL"


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
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open a browser tab automatically in web mode.",
    )
    return parser.parse_args()


def _browser_host(host: str) -> str:
    clean = host.strip().lower()
    if clean in {"0.0.0.0", "::", "[::]", ""}:
        return "127.0.0.1"
    return host


def _wait_for_web_health(url: str, timeout_seconds: float = 20.0) -> tuple[bool, str]:
    health_url = f"{url.rstrip('/')}/health"
    deadline = time.time() + timeout_seconds
    last_reason = "no health response received"
    while time.time() < deadline:
        try:
            with urlopen(health_url, timeout=1.0) as response:
                payload = response.read().decode("utf-8", errors="replace")
                compact_payload = payload.replace("\n", "")
                if response.status == 200 and '"status": "ok"' in compact_payload:
                    return True, "ready"
                if response.status != 200:
                    last_reason = f"health returned HTTP {response.status}"
                else:
                    last_reason = "health response did not include status ok"
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            last_reason = f"{type(exc).__name__}: {exc}"
        time.sleep(0.2)
    return False, last_reason


def _open_browser_when_ready(url: str) -> None:
    print("Waiting for browser readiness...")
    ready, reason = _wait_for_web_health(url)
    if ready:
        print("Opening browser...")
        webbrowser.open(url)
    else:
        print(f"Warning: browser readiness check failed: {reason}")
        print(f"Warning: server health endpoint at {url}/health was not ready; browser not auto-opened.")


def main() -> int:
    _print_banner()
    print("Initializing systems...")

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
            from app.web import run_web_server

            browser_url = f"http://{_browser_host(args.host)}:{args.port}"
            print("Starting backend (web mode default)...")
            print(f"Waiting for browser readiness at {browser_url}/health")
            if not args.no_browser:
                threading.Thread(target=_open_browser_when_ready, args=(browser_url,), daemon=True).start()
            run_web_server(host=args.host, port=args.port)
            return 0

        from app.main import main as terminal_main

        print("Starting terminal mode (fallback/debug)...")
        terminal_main()
        return 0
    except KeyboardInterrupt:
        print("\nShutdown requested. Goodbye.")
        return 0
    except Exception as exc:  # pragma: no cover - defensive UX fallback
        print("\nThe game could not be started.")
        print(f"Error: {exc}")
        print("\nDebug trace:")
        print(traceback.format_exc())
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
