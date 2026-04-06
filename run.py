"""Primary launcher for Adventurer Guild AI."""

from __future__ import annotations

import argparse
import os
import sys
import traceback

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
    return parser.parse_args()


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
            from app.web import FastAPI, WebRuntime, _resolve_static_root, create_web_app, uvicorn

            if FastAPI is None or uvicorn is None:
                raise RuntimeError("FastAPI/uvicorn is not installed. Install dependencies and try again.")

            print("Starting backend...")
            print("Initializing app...")
            runtime = WebRuntime(project_root())
            app = create_web_app(runtime=runtime, static_root=_resolve_static_root())
            print(f"Launching server on http://{args.host}:{args.port}")
            print(f"Open your browser at: http://{args.host}:{args.port}")
            uvicorn.run(app, host=args.host, port=args.port, log_level="info")
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
        if os.name == "nt":
            try:
                input("Press Enter to close...")
            except EOFError:
                pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
