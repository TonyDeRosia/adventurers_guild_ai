import importlib


def test_backend_dependency_chain_imports_and_app_constructs(tmp_path, monkeypatch):
    monkeypatch.setenv("SMART_MUD_USER_DATA", str(tmp_path / "user_data"))
    modules = [
        "engine.display_themes",
        "engine.mud_displays",
        "engine.mud_commands",
        "engine.mud_runtime",
        "smart_mud.builder",
        "app.web",
    ]
    imported = [importlib.import_module(name) for name in modules]
    web = imported[-1]
    runtime = web.WebRuntime(importlib.import_module("pathlib").Path.cwd())
    app = web.create_web_app(runtime, tmp_path)
    assert app is not None
