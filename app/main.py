"""Terminal MVP for the local-first AI campaign engine."""

from __future__ import annotations

from pathlib import Path

from engine.campaign_engine import CampaignEngine
from engine.game_state_manager import GameStateManager
from models.registry import create_model_adapter


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    state_manager = GameStateManager(root / "data")

    if state_manager.can_load("autosave"):
        state = state_manager.load("autosave")
        print(f"Loaded autosave for campaign: {state.campaign_name}")
    else:
        state = state_manager.new_from_sample()
        print(f"Started new campaign: {state.campaign_name}")

    model = create_model_adapter("null")
    engine = CampaignEngine(model)

    print("Type 'help' for commands. Type 'exit' to quit.")
    while True:
        action = input("\n> ").strip()

        if not action:
            print("Enter a command.")
            continue

        lower = action.lower()
        if lower == "save":
            path = state_manager.save(state, "autosave")
            print(f"Saved campaign to {path}")
            continue

        if lower == "load":
            if state_manager.can_load("autosave"):
                state = state_manager.load("autosave")
                print("Loaded autosave.")
            else:
                print("No autosave found.")
            continue

        result = engine.run_turn(state, action)
        for message in result.system_messages:
            print(f"[system] {message}")
        print(f"[narrator] {result.narrative}")

        if result.should_exit:
            state_manager.save(state, "autosave")
            print("Progress saved. Goodbye.")
            break


if __name__ == "__main__":
    main()
