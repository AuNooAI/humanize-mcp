"""Environment-variable configuration for the MCP server."""

from __future__ import annotations

import os
from dataclasses import dataclass


DEFAULT_PRESETS_PATH = "~/.humanize-mcp/presets.json"
DEFAULT_OLLAMA_MODEL = "gemma3:4b"
VALID_PROVIDERS = ("anthropic", "openai", "bedrock")


@dataclass
class Config:
    default_provider: str
    default_model: str | None
    presets_path: str
    ollama_url: str | None
    ollama_model: str

    @classmethod
    def from_env(cls) -> "Config":
        provider = (os.environ.get("HUMANIZE_DEFAULT_PROVIDER") or "anthropic").strip().lower()
        if provider not in VALID_PROVIDERS:
            raise ValueError(
                f"HUMANIZE_DEFAULT_PROVIDER={provider!r} is not one of {VALID_PROVIDERS}"
            )
        model = os.environ.get("HUMANIZE_DEFAULT_MODEL") or None
        presets_path = os.environ.get("HUMANIZE_PRESETS_PATH") or DEFAULT_PRESETS_PATH
        ollama_url = os.environ.get("HUMANIZE_OLLAMA_URL") or None
        ollama_model = os.environ.get("HUMANIZE_OLLAMA_MODEL") or DEFAULT_OLLAMA_MODEL
        return cls(
            default_provider=provider,
            default_model=model,
            presets_path=presets_path,
            ollama_url=ollama_url,
            ollama_model=ollama_model,
        )
