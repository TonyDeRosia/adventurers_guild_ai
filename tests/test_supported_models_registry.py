from models.supported_models import get_supported_model, get_supported_models


def test_supported_models_include_requested_entries() -> None:
    models = {model.id: model for model in get_supported_models()}
    assert "openhermes-2.5-mistral-7b" in models
    assert "nous-hermes-2-mistral-7b-dpo" in models
    assert "synatra-7b-v0.3-rp" in models
    assert "utena-7b-nsfw-v2" in models


def test_guided_models_are_not_marked_one_click() -> None:
    synatra = get_supported_model("synatra-7b-v0.3-rp")
    utena = get_supported_model("utena-7b-nsfw-v2")
    assert synatra is not None and synatra.install_type == "guided_import"
    assert utena is not None and utena.install_type == "guided_import"
    assert synatra.install_supported is False
    assert utena.install_supported is False
