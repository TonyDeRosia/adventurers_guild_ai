"""Terminal MVP for the local-first AI campaign engine."""

from __future__ import annotations

from engine.campaign_engine import CampaignEngine
from engine.game_state_manager import GameStateManager
from models.ollama_adapter import OllamaAdapter
from models.registry import create_model_adapter
from app.runtime_config import ModelRuntimeConfig, RuntimeConfigStore
from app.pathing import initialize_user_data_paths
from app.terminal_presenter import TerminalPresenter


def _print_startup_banner() -> None:
    print("=" * 36)
    print("      Adventurer Guild AI")
    print("=" * 36)


def main() -> None:
    paths = initialize_user_data_paths()
    state_manager = GameStateManager(paths.content_data, paths.saves, paths.user_data)
    config_store = RuntimeConfigStore(paths.config / "app_config.json")
    _print_startup_banner()
    print("Loading campaign systems...")

    state = _campaign_start_flow(state_manager)
    model_config = _choose_model_config(config_store)
    model = create_model_adapter(
        model_config.provider,
        model=model_config.model_name,
        base_url=model_config.base_url,
        timeout_seconds=model_config.timeout_seconds,
    )
    engine = CampaignEngine(model, data_dir=paths.content_data)
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
            if state is not None:
                print(f"Loaded autosave for campaign: {state.campaign_name}")
                return state
            print("Autosave could not be read. Starting a new campaign instead.")

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
    suggested_moves_enabled = input("Enable suggested next moves? [Y/n]: ").strip().lower() != "n"
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
        suggested_moves_enabled=suggested_moves_enabled,
    )
    print(
        f"Started new campaign: {state.campaign_name} "
        f"(profile={state.settings.profile}, tone={state.settings.content_settings.tone}, "
        f"maturity={state.settings.content_settings.maturity_level}, "
        f"themes={state.settings.content_settings.thematic_flags})"
    )
    state_manager.save(state, "autosave")
    return state


def _choose_model_config(config_store: RuntimeConfigStore) -> ModelRuntimeConfig:
    config = config_store.load()
    print(f"Model provider: {config.provider} (model: {config.model_name})")
    provider = input("Model provider [null/ollama] (Enter keeps current): ").strip().lower() or config.provider
    if provider not in {"null", "ollama"}:
        print("Unknown provider selected; using null provider.")
        provider = "null"

    if provider == "ollama":
        ollama = OllamaAdapter(model=config.model_name, base_url=config.base_url)
        detected_models = ollama.list_local_models()
        if detected_models:
            print("Detected Ollama models:")
            for model_name in detected_models[:12]:
                print(f" - {model_name}")
        else:
            print("No Ollama models detected yet (run `ollama pull <model>` first).")

        model_name = input(f"Ollama model [{config.model_name}]: ").strip() or config.model_name
        base_url = input(f"Ollama base URL [{config.base_url}]: ").strip() or config.base_url
        config = ModelRuntimeConfig(provider="ollama", model_name=model_name, base_url=base_url)
    else:
        config = ModelRuntimeConfig(provider="null", model_name=config.model_name, base_url=config.base_url)

    config_store.save(config)
    return config


if __name__ == "__main__":
    main()
