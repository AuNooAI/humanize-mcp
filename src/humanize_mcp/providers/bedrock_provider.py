"""AWS Bedrock backend (Converse API).

Adapted from socmedia/services/llm.py::_converse(). Honors the standard AWS
credential chain plus an optional AWS_BEARER_TOKEN_BEDROCK env var.
"""

from __future__ import annotations

import os
import time

from .base import Provider, ProviderError, RewriteResult


class BedrockProvider(Provider):
    name = "bedrock"
    default_model = "us.amazon.nova-pro-v1:0"

    def __init__(self) -> None:
        self._client = None

    def is_configured(self) -> bool:
        if os.environ.get("AWS_BEARER_TOKEN_BEDROCK"):
            return True
        if os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY"):
            return True
        try:
            import boto3

            session = boto3.Session(region_name=os.environ.get("AWS_REGION", "us-east-1"))
            return session.get_credentials() is not None
        except Exception:
            return False

    @property
    def client(self):
        if self._client is None:
            try:
                import boto3
            except ImportError as e:
                raise ProviderError(f"boto3 not installed: {e}") from e
            region = os.environ.get("AWS_REGION", "us-east-1")
            kwargs: dict = {"region_name": region}
            ak = os.environ.get("AWS_ACCESS_KEY_ID")
            sk = os.environ.get("AWS_SECRET_ACCESS_KEY")
            if ak and sk:
                kwargs["aws_access_key_id"] = ak
                kwargs["aws_secret_access_key"] = sk
            self._client = boto3.client("bedrock-runtime", **kwargs)
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
            response = self.client.converse(
                modelId=chosen,
                system=[{"text": system_prompt}],
                messages=[{"role": "user", "content": [{"text": user_text}]}],
                inferenceConfig={"temperature": temperature, "maxTokens": max_tokens},
            )
        except Exception as e:
            raise ProviderError(f"bedrock call failed: {e}") from e

        latency_ms = int((time.time() - start) * 1000)
        blocks = response["output"]["message"]["content"]
        text = "".join(b.get("text", "") for b in blocks)
        usage = response.get("usage") or {}
        return RewriteResult(
            text=text,
            model=chosen,
            latency_ms=latency_ms,
            input_tokens=usage.get("inputTokens", 0),
            output_tokens=usage.get("outputTokens", 0),
        )
