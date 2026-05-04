"""Anthropic Claude backend."""

from __future__ import annotations

import os
import time

from .base import Provider, ProviderError, RewriteResult


class AnthropicProvider(Provider):
    name = "anthropic"
    default_model = "claude-sonnet-4-6"

    def __init__(self) -> None:
        self._client = None

    def is_configured(self) -> bool:
        return bool(os.environ.get("ANTHROPIC_API_KEY"))

    @property
    def client(self):
        if self._client is None:
            try:
                from anthropic import Anthropic
            except ImportError as e:
                raise ProviderError(f"anthropic SDK not installed: {e}") from e
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise ProviderError("ANTHROPIC_API_KEY not set")
            self._client = Anthropic(api_key=api_key)
        return self._client

    def rewrite(
        self,
        system_prompt: str,
        user_text: str,
        model: str | None = None,
        temperature: float = 0.4,
        max_tokens: int = 4000,
    ) -> RewriteResult:
        chosen = model or self.default_model
        start = time.time()
        try:
            response = self.client.messages.create(
                model=chosen,
                system=system_prompt,
                messages=[{"role": "user", "content": user_text}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as e:
            raise ProviderError(f"anthropic call failed: {e}") from e

        latency_ms = int((time.time() - start) * 1000)
        text = "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        )
        usage = getattr(response, "usage", None)
        return RewriteResult(
            text=text,
            model=chosen,
            latency_ms=latency_ms,
            input_tokens=getattr(usage, "input_tokens", 0) if usage else 0,
            output_tokens=getattr(usage, "output_tokens", 0) if usage else 0,
        )
