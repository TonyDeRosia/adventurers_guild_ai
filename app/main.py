"""Terminal shell for Smart MUD."""

from __future__ import annotations

from app.pathing import initialize_user_data_paths, project_root
from app.web import WebRuntime


def _print_startup_banner() -> None:
    print("=" * 36)
    print("Smart MUD")
    print("=" * 36)


def main() -> None:
    _print_startup_banner()
    runtime = WebRuntime(project_root())
    worlds = runtime.list_worlds()
    if not worlds:
        print("No worlds are available.")
        return
    world = worlds[0]
    runtime.select_world(str(world["id"]))
    print("World Select")
    print(f"Entering {world.get('name', world['id'])}")
    name = input("Character name: ").strip() or "Player"
    character = runtime.create_character({"name": name})["character"]
    runtime.enter_world(character["character_id"])
    print("Character Select")
    print(runtime.play_view()["text"])
    while True:
        command = input("\n> ").strip()
        if command.lower() in {"quit", "exit"}:
            print("Goodbye.")
            break
        result = runtime.handle_input(command)
        print(result["output"])


if __name__ == "__main__":
    main()
