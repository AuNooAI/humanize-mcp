"""Provider abstraction for the humanize rewrite call."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class ProviderError(RuntimeError):
    """Raised when a provider can't be configured or a call fails."""


@dataclass
class RewriteResult:
    text: str
    model: str
    latency_ms: int
    input_tokens: int
    output_tokens: int


class Provider(ABC):
    """Common interface for LLM backends used by humanize_text."""

    name: str = ""
    default_model: str = ""

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True iff credentials/config are present to call this provider."""

    @abstractmethod
    def rewrite(
        self,
        system_prompt: str,
        user_text: str,
        model: str | None = None,
        temperature: float = 0.4,
        max_tokens: int = 4000,
    ) -> RewriteResult:
        """Run the rewrite. Raise ProviderError on failure."""
