"""LLM provider backends for the humanize rewrite step."""

from .base import Provider, ProviderError, RewriteResult
from .anthropic_provider import AnthropicProvider
from .openai_provider import OpenAIProvider
from .bedrock_provider import BedrockProvider


_REGISTRY: dict[str, type[Provider]] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "bedrock": BedrockProvider,
}


def get_provider(name: str) -> Provider:
    """Instantiate a provider by name. Raises ProviderError for unknown names."""
    cls = _REGISTRY.get(name.lower())
    if cls is None:
        raise ProviderError(f"unknown provider: {name!r} (valid: {sorted(_REGISTRY)})")
    return cls()


def available_providers() -> list[str]:
    return sorted(_REGISTRY)


__all__ = [
    "Provider",
    "ProviderError",
    "RewriteResult",
    "AnthropicProvider",
    "OpenAIProvider",
    "BedrockProvider",
    "get_provider",
    "available_providers",
]
