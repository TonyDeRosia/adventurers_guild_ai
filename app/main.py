"""Terminal MVP for the local-first AI campaign engine."""

from __future__ import annotations

from pathlib import Path

from engine.campaign_engine import CampaignEngine
from engine.game_state_manager import GameStateManager
from models.registry import create_model_adapter
from app.terminal_presenter import TerminalPresenter


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
    presenter = TerminalPresenter()

    print("Type 'help' for commands. Type 'exit' to quit.")
    while True:
        action = input("\n> ").strip()

        if not action:
            print("Enter a command.")
            continue

        lower = action.lower()
        if lower == "save":
            print(presenter.format_player(action))
            path = state_manager.save(state, "autosave")
            print(f"⚙️ System: Saved campaign to {path}")
            continue

        if lower == "load":
            print(presenter.format_player(action))
            if state_manager.can_load("autosave"):
                state = state_manager.load("autosave")
                print("⚙️ System: Loaded autosave.")
            else:
                print("⚙️ System: No autosave found.")
            continue

        print(presenter.format_player(action))
        result = engine.run_turn(state, action)
        for line in presenter.render_turn(result):
            print(line)

        if result.should_exit:
            state_manager.save(state, "autosave")
            print("⚙️ System: Progress saved. Goodbye.")
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
    default_tone = "grim" if profile == "dark_fantasy" else "heroic"
    content_settings_enabled = input("Enable custom content settings? [Y/n]: ").strip().lower() != "n"
    if content_settings_enabled:
        selected_tone = input(f"Campaign tone [{default_tone}]: ").strip().lower() or default_tone
        maturity_level = input("Maturity level [standard/mature] (default: standard): ").strip().lower() or "standard"
        themes_input = input("Thematic flags (comma-separated, e.g. intrigue,horror,romance): ").strip()
        thematic_flags = [theme.strip().lower() for theme in themes_input.split(",") if theme.strip()]
        mature_enabled = maturity_level == "mature"
    else:
        selected_tone = default_tone
        maturity_level = "standard"
        thematic_flags = []
        mature_enabled = False

    state = state_manager.create_new_campaign(
        player_name=name,
        char_class=char_class,
        profile=profile,
        mature_content_enabled=mature_enabled,
        content_settings_enabled=content_settings_enabled,
        campaign_tone=selected_tone,
        maturity_level=maturity_level,
        thematic_flags=thematic_flags,
    )
    print(
        f"Started new campaign: {state.campaign_name} "
        f"(profile={state.settings.profile}, tone={state.settings.content_settings.tone}, "
        f"maturity={state.settings.content_settings.maturity_level}, "
        f"themes={state.settings.content_settings.thematic_flags})"
    )
    state_manager.save(state, "autosave")
    return state


if __name__ == "__main__":
    main()
