"""Primary launcher for Adventurer Guild AI."""

from __future__ import annotations

import argparse
import traceback

from app.pathing import data_dir, project_root, static_dir


def _print_banner() -> None:
    print("=" * 36)
    print("      Adventurer Guild AI")
    print("=" * 36)


def _initialize_paths() -> None:
    root = project_root()
    resolved_data_dir = data_dir()
    resolved_static = static_dir()
    resolved_data_dir.mkdir(parents=True, exist_ok=True)
    if not resolved_static.exists():
        print(f"Warning: static assets not found at {resolved_static}")
    print(f"Runtime root: {root}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start Adventurer Guild AI")
    parser.add_argument(
        "--mode",
        choices=["terminal", "web"],
        default="terminal",
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

        if args.mode == "web":
            from app.web import run_web_server

            print("Starting web mode...")
            run_web_server(host=args.host, port=args.port)
            return 0

        from app.main import main as terminal_main

        print("Starting terminal mode...")
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
