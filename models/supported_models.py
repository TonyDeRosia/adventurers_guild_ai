"""Supported local model registry and install metadata."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class SupportedModel:
    id: str
    display_name: str
    family: str
    provider: str
    install_type: str
    ollama_name: str = ""
    source_url: str = ""
    source_hint: str = ""
    description: str = ""
    default_context: int = 4096
    mature_or_roleplay_note: str = ""
    install_supported: bool = True
    activate_supported: bool = True
    namespace_verified: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


SUPPORTED_MODELS: tuple[SupportedModel, ...] = (
    SupportedModel(
        id="llama3",
        display_name="Llama 3",
        family="llama",
        provider="ollama",
        install_type="ollama_pull",
        ollama_name="llama3",
        description="Default local narration model with broad compatibility.",
        source_hint="Local Ollama library",
    ),
    SupportedModel(
        id="openhermes-2.5-mistral-7b",
        display_name="OpenHermes 2.5 Mistral 7B",
        family="mistral",
        provider="ollama",
        install_type="ollama_pull",
        ollama_name="openhermes",
        description="Instruction-tuned Mistral 7B often used for roleplay and creative writing.",
        mature_or_roleplay_note="Creative roleplay friendly; verify local policy before mature use.",
        source_hint="Local Ollama library",
    ),
    SupportedModel(
        id="nous-hermes-2-mistral-7b-dpo",
        display_name="Nous-Hermes-2-Mistral-7B-DPO",
        family="mistral",
        provider="ollama",
        install_type="guided_or_ollama_pull",
        ollama_name="nous-hermes2",
        description="DPO-tuned Mistral variant. Namespace can vary by environment.",
        source_hint="Try Ollama pull first; fallback to custom import.",
        namespace_verified=False,
    ),
    SupportedModel(
        id="synatra-7b-v0.3-rp",
        display_name="Synatra-7B-v0.3-RP",
        family="roleplay",
        provider="ollama",
        install_type="guided_import",
        source_url="https://huggingface.co/",
        source_hint="Download GGUF, then import with a Modelfile.",
        description="Roleplay-focused model typically distributed outside the default Ollama library.",
        mature_or_roleplay_note="Roleplay-oriented responses may require mature-content policy checks.",
        install_supported=False,
    ),
    SupportedModel(
        id="utena-7b-nsfw-v2",
        display_name="UTENA-7B-NSFW-V2",
        family="roleplay",
        provider="ollama",
        install_type="guided_import",
        source_url="https://huggingface.co/",
        source_hint="Download GGUF, then import with a Modelfile.",
        description="Unrestricted/NSFW-oriented model expected to require custom local import.",
        mature_or_roleplay_note="Contains mature/NSFW tendencies; handle with explicit safeguards.",
        install_supported=False,
    ),
)


def get_supported_models() -> list[SupportedModel]:
    return list(SUPPORTED_MODELS)


def get_supported_model(model_id: str) -> SupportedModel | None:
    clean = model_id.strip().lower()
    for model in SUPPORTED_MODELS:
        if model.id == clean:
            return model
    return None
