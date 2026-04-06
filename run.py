"""Root launcher for Adventurer Guild AI."""

from __future__ import annotations



def main() -> int:
    print("Loading game engine...")

    try:
        from app.main import main as app_main

        print("Starting game loop...")
        app_main()
        return 0
    except KeyboardInterrupt:
        print("\nShutdown requested. Goodbye.")
        return 0
    except Exception as exc:  # pragma: no cover - defensive UX fallback
        print("\nThe game could not be started.")
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
