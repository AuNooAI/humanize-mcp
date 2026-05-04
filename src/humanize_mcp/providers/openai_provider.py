"""OpenAI backend.

Mirrors the new-vs-legacy parameter handling from humanize/backend/llm.py:
GPT-5 / o-series models use max_completion_tokens; o-series doesn't accept temperature.
"""

from __future__ import annotations

import os
import time

from .base import Provider, ProviderError, RewriteResult


class OpenAIProvider(Provider):
    name = "openai"
    default_model = "gpt-4.1"

    def __init__(self) -> None:
        self._client = None

    def is_configured(self) -> bool:
        return bool(os.environ.get("OPENAI_API_KEY"))

    @property
    def client(self):
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as e:
                raise ProviderError(f"openai SDK not installed: {e}") from e
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ProviderError("OPENAI_API_KEY not set")
            self._client = OpenAI(api_key=api_key)
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
        is_new_api = chosen.startswith("gpt-5") or chosen.startswith("o")
        token_param = (
            {"max_completion_tokens": max_tokens} if is_new_api else {"max_tokens": max_tokens}
        )
        # o-series reasoning models don't accept temperature.
        temp_param = {} if chosen.startswith("o") else {"temperature": temperature}

        start = time.time()
        try:
            response = self.client.chat.completions.create(
                model=chosen,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text},
                ],
                **temp_param,
                **token_param,
            )
        except Exception as e:
            raise ProviderError(f"openai call failed: {e}") from e

        latency_ms = int((time.time() - start) * 1000)
        text = response.choices[0].message.content or ""
        usage = response.usage
        return RewriteResult(
            text=text,
            model=chosen,
            latency_ms=latency_ms,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )
