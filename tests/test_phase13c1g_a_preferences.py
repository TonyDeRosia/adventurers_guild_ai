from types import SimpleNamespace

from engine.player_preferences import PlayerPresentationPreferenceService


def test_player_presentation_preferences_persist_and_reset(tmp_path):
    db = tmp_path / "prefs.db"
    svc = PlayerPresentationPreferenceService(db)
    svc.save("hero", prompt_preset="classic", display_theme="default", display_width=100)

    reloaded = PlayerPresentationPreferenceService(db)
    prefs = reloaded.load("hero")
    assert prefs.prompt_preset == "classic"
    assert prefs.display_theme == "default"
    assert prefs.display_width == 100

    reloaded.save("hero", prompt_template="[%h/%H HP]", prompt_preset=None)
    ch = SimpleNamespace(id="hero", preferences={})
    reloaded.apply_to_character(ch)
    assert ch.prompt_template == "[%h/%H HP]"
    assert ch.display_width == 100

    reset = reloaded.reset_prompt("hero")
    assert reset.prompt_preset is None
    assert reset.prompt_template is None
    assert reset.display_theme == "default"


def test_player_presentation_preferences_repair_invalid_values(tmp_path):
    svc = PlayerPresentationPreferenceService(tmp_path / "prefs.db")
    svc.save("hero", prompt_preset="<script>", display_theme="bad<script>", display_width=999)
    prefs = svc.load("hero")
    assert prefs.prompt_preset is None
    assert prefs.display_theme is None
    assert prefs.display_width is None
