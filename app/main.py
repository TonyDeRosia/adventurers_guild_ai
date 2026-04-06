"""Terminal MVP for the local-first AI campaign engine."""

from __future__ import annotations

from pathlib import Path

from engine.campaign_engine import CampaignEngine
from engine.game_state_manager import GameStateManager
from models.registry import create_model_adapter


def _print_startup_banner() -> None:
    print("=" * 36)
    print("      Adventurer Guild AI")
    print("=" * 36)


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    state_manager = GameStateManager(root / "data")
    _print_startup_banner()
    print("Loading campaign systems...")

    state = _campaign_start_flow(state_manager)

    model = create_model_adapter("null")
    engine = CampaignEngine(model, data_dir=root / "data")

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


def _campaign_start_flow(state_manager: GameStateManager):
    if state_manager.can_load("autosave"):
        print("1) Load autosave")
        print("2) Start new campaign")
        choice = input("Select option [1/2]: ").strip()
        if choice == "1":
            state = state_manager.load("autosave")
            print(f"Loaded autosave for campaign: {state.campaign_name}")
            return state

    print("\n-- Campaign Creation --")
    name = input("Character name: ").strip() or "Aria"
    char_class = input("Class (Ranger/Fighter/Rogue/Mage): ").strip() or "Ranger"
    print("Select campaign profile:")
    print("1) classic fantasy")
    print("2) dark fantasy")
    profile_choice = input("Profile [1/2]: ").strip()
    profile = "dark_fantasy" if profile_choice == "2" else "classic_fantasy"
    mature_enabled = input("Enable mature themes tone? [y/N]: ").strip().lower() == "y"

    state = state_manager.create_new_campaign(
        player_name=name,
        char_class=char_class,
        profile=profile,
        mature_content_enabled=mature_enabled,
    )
    print(
        f"Started new campaign: {state.campaign_name} "
        f"(profile={state.settings.profile}, mature_tone={state.settings.mature_content_enabled})"
    )
    state_manager.save(state, "autosave")
    return state


if __name__ == "__main__":
    main()
