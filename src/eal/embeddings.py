"""Opt-in OpenAI embeddings adapter for reviewed candidate retrieval.

Import and construction perform no network request. An application supplies
this callable to RagCandidateIndex.load only when remote query embedding is
authorised; the index checks document grants before invoking it.
"""

from __future__ import annotations

import hashlib
import math
import os
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlsplit

import httpx

from .providers import ProviderError
from .rag import _vector
from .runtime import strict_json


@dataclass(frozen=True)
class EmbeddingAttempt:
    """One request's billed usage, or unknown usage after an attempted call."""

    model: str
    dimensions: int
    input_sha256: str
    outcome: str
    prompt_tokens: int | None
    total_tokens: int | None

    @property
    def token_usage_complete(self) -> bool:
        return self.prompt_tokens is not None and self.total_tokens is not None


class OpenAIEmbeddingAdapter:
    """Synchronous, byte-bounded `/v1/embeddings` callable.

    `usage_callback` receives an EmbeddingAttempt after every sent request,
    including failures whose billed token usage is unknown. It is responsible
    for persistence and any pricing calculation; this object retains no key.
    """

    def __init__(self, *, model: str, dimensions: int,
                 endpoint: str = "https://api.openai.com/v1/embeddings",
                 api_key_env: str = "OPENAI_API_KEY",
                 timeout_seconds: float = 30.0,
                 max_response_bytes: int = 131_072,
                 usage_callback: Callable[[EmbeddingAttempt], None] | None = None,
                 transport: httpx.BaseTransport | None = None):
        if (not isinstance(model, str) or not model.strip()
                or len(model.encode("utf-8")) > 128):
            raise ValueError("Embedding model requires a bounded explicit identity")
        if model == "text-embedding-ada-002":
            raise ValueError("The selected embedding model does not support dimensions")
        if type(dimensions) is not int or not 2 <= dimensions <= 512:
            raise ValueError("Embedding dimensions must be an integer from 2 through 512")
        if not isinstance(endpoint, str):
            raise ValueError("Embedding endpoint must be an HTTPS or local HTTP URL")
        try:
            url = urlsplit(endpoint)
            hostname = url.hostname
            port = url.port
        except ValueError as exc:
            raise ValueError("Embedding endpoint is invalid") from exc
        if (url.scheme not in {"https", "http"} or not hostname
                or url.username or url.password or url.query or url.fragment
                or url.path != "/v1/embeddings"
                or (url.scheme == "http" and hostname not in {"localhost", "127.0.0.1", "::1"})):
            raise ValueError("Embedding endpoint must be HTTPS or local HTTP /v1/embeddings")
        if port is not None and not 1 <= port <= 65535:
            raise ValueError("Embedding endpoint has an invalid port")
        if not isinstance(api_key_env, str) or not api_key_env.isidentifier():
            raise ValueError("api_key_env must name an environment variable")
        if (type(timeout_seconds) not in (int, float)
                or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 120):
            raise ValueError("Embedding timeout must be finite, positive and at most 120 seconds")
        if type(max_response_bytes) is not int or not 1024 <= max_response_bytes <= 1_048_576:
            raise ValueError("Embedding response byte limit must be from 1024 to one MiB")
        if usage_callback is not None and not callable(usage_callback):
            raise ValueError("Embedding usage callback must be callable")
        self.model, self.dimensions = model, dimensions
        self.endpoint, self.api_key_env = endpoint, api_key_env
        self.timeout_seconds, self.max_response_bytes = float(timeout_seconds), max_response_bytes
        self.usage_callback, self.transport = usage_callback, transport

    def __call__(self, value: str) -> tuple[str, tuple[float, ...]]:
        if (not isinstance(value, str) or not value.strip()
                or not 1 <= len(value.encode("utf-8")) <= 4096):
            raise ValueError("Embedding input must contain one to 4096 UTF-8 bytes")
        credential = os.environ.get(self.api_key_env)
        if not credential:
            raise ProviderError(f"Configured credential variable {self.api_key_env} is absent")
        prompt_tokens: int | None = None
        total_tokens: int | None = None
        outcome = "failed"
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        try:
            payload = {"model": self.model, "input": value, "dimensions": self.dimensions,
                       "encoding_format": "float"}
            headers = {"Content-Type": "application/json", "Authorization": "Bearer " + credential}
            try:
                with httpx.Client(timeout=self.timeout_seconds, follow_redirects=False,
                                  transport=self.transport) as client:
                    with client.stream("POST", self.endpoint, headers=headers, json=payload) as response:
                        if response.status_code != 200:
                            raise ProviderError(f"Embedding endpoint returned HTTP {response.status_code}")
                        chunks, size = [], 0
                        for chunk in response.iter_bytes():
                            size += len(chunk)
                            if size > self.max_response_bytes:
                                raise ProviderError("Embedding response exceeded its byte limit")
                            chunks.append(chunk)
                data = strict_json(b"".join(chunks).decode("utf-8"))
            except httpx.HTTPError as exc:
                raise ProviderError("Embedding endpoint transport failed") from exc
            except (UnicodeError, ValueError) as exc:
                raise ProviderError("Embedding endpoint returned malformed UTF-8 JSON") from exc
            if not isinstance(data, dict):
                raise ProviderError("Embedding endpoint returned a non-object response")
            usage = data.get("usage")
            if (not isinstance(usage, dict)
                    or type(usage.get("prompt_tokens")) is not int
                    or type(usage.get("total_tokens")) is not int
                    or usage["prompt_tokens"] < 0
                    or usage["total_tokens"] < usage["prompt_tokens"]):
                raise ProviderError("Embedding endpoint returned invalid usage")
            prompt_tokens, total_tokens = usage["prompt_tokens"], usage["total_tokens"]
            rows = data.get("data")
            if (data.get("object") != "list" or data.get("model") != self.model
                    or not isinstance(rows, list) or len(rows) != 1
                    or not isinstance(rows[0], dict) or rows[0].get("object") != "embedding"
                    or type(rows[0].get("index")) is not int or rows[0]["index"] != 0):
                raise ProviderError("Embedding endpoint returned a different model or malformed data")
            try:
                vector = _vector(rows[0].get("embedding"))
            except ValueError as exc:
                raise ProviderError("Embedding endpoint returned an invalid vector") from exc
            if len(vector) != self.dimensions:
                raise ProviderError("Embedding endpoint returned a different vector dimension")
            outcome = "succeeded"
            return self.model, vector
        finally:
            if self.usage_callback is not None:
                self.usage_callback(EmbeddingAttempt(
                    self.model, self.dimensions, digest, outcome,
                    prompt_tokens, total_tokens))
