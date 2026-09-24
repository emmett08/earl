"""OpenAI embeddings adapter: bounded transport, response and usage contracts."""

from __future__ import annotations

import hashlib
import json
import math

import httpx
import pytest

from eal.embeddings import OpenAIEmbeddingAdapter
from eal.providers import ProviderError
from test_rag import _families, _index, _search


def _response(*, model="text-embedding-3-small", embedding=None, usage=None):
    return {"object": "list", "model": model, "data": [
        {"object": "embedding", "index": 0,
         "embedding": [0.25, 0.75, -0.5] if embedding is None else embedding}],
        "usage": {"prompt_tokens": 4, "total_tokens": 4} if usage is None else usage}


def _adapter(monkeypatch, handler, **kwargs):
    monkeypatch.setenv("EAL_TEST_EMBEDDING_KEY", "test-credential-only")
    return OpenAIEmbeddingAdapter(model="text-embedding-3-small", dimensions=3,
                                  api_key_env="EAL_TEST_EMBEDDING_KEY",
                                  transport=httpx.MockTransport(handler), **kwargs)


def test_exact_request_vector_and_usage_are_recorded_without_secret(monkeypatch):
    attempts, requests = [], []
    def handler(request):
        assert request.method == "POST"
        assert str(request.url) == "https://api.openai.com/v1/embeddings"
        assert request.headers["Authorization"] == "Bearer test-credential-only"
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=_response())
    adapter = _adapter(monkeypatch, handler, usage_callback=attempts.append)
    assert adapter("The field rig breaker passed inspection.") == (
        "text-embedding-3-small", (0.25, 0.75, -0.5))
    assert requests == [{"model": "text-embedding-3-small",
                         "input": "The field rig breaker passed inspection.",
                         "dimensions": 3, "encoding_format": "float"}]
    assert len(attempts) == 1 and attempts[0].token_usage_complete
    assert (attempts[0].prompt_tokens, attempts[0].total_tokens,
            attempts[0].outcome) == (4, 4, "succeeded")
    assert attempts[0].input_sha256 == hashlib.sha256(requests[0]["input"].encode()).hexdigest()
    assert "test-credential-only" not in repr(attempts[0])
    assert requests[0]["input"] not in repr(attempts[0])


def test_missing_key_rejects_before_transport_or_accounting(monkeypatch):
    monkeypatch.delenv("EAL_TEST_EMBEDDING_KEY", raising=False)
    calls, attempts = [], []
    adapter = OpenAIEmbeddingAdapter(
        model="text-embedding-3-small", dimensions=3,
        api_key_env="EAL_TEST_EMBEDDING_KEY",
        usage_callback=attempts.append,
        transport=httpx.MockTransport(lambda request: calls.append(request)))
    with pytest.raises(ProviderError, match="credential variable"):
        adapter("field rig")
    assert calls == attempts == []


@pytest.mark.parametrize("response,expected", [
    (_response(model="text-embedding-3-large"), "different model"),
    (_response(embedding=[0.5, 0.5]), "vector dimension"),
    (_response(embedding=[0.0, 0.0, 0.0]), "invalid vector"),
    (_response(embedding=[True, 0.1, 0.2]), "invalid vector"),
    (_response(usage={"prompt_tokens": 3, "total_tokens": False}), "invalid usage"),
    ({"object": "list", "model": "text-embedding-3-small", "data": []}, "invalid usage"),
])
def test_model_dimension_vector_and_usage_drift_fail_closed(monkeypatch, response, expected):
    attempts = []
    adapter = _adapter(monkeypatch, lambda request: httpx.Response(200, json=response),
                       usage_callback=attempts.append)
    with pytest.raises(ProviderError, match=expected):
        adapter("field rig")
    assert len(attempts) == 1 and attempts[0].outcome == "failed"
    assert attempts[0].token_usage_complete == ("invalid usage" not in expected)


def test_duplicate_keys_nonfinite_and_oversized_response_are_rejected(monkeypatch):
    for payload, expected in ((b'{"usage":{},"usage":{}}', "malformed UTF-8 JSON"),
                              (b'{"embedding":NaN}', "malformed UTF-8 JSON"),
                              (b"x" * 1025, "byte limit")):
        attempts = []
        adapter = _adapter(monkeypatch,
                           lambda request: httpx.Response(200, content=payload),
                           max_response_bytes=1024, usage_callback=attempts.append)
        with pytest.raises(ProviderError, match=expected):
            adapter("field rig")
        assert len(attempts) == 1 and not attempts[0].token_usage_complete


def test_http_failure_and_timeout_account_for_unknown_billed_usage(monkeypatch):
    attempts = []
    adapter = _adapter(monkeypatch,
                       lambda request: httpx.Response(429, text="secret body"),
                       usage_callback=attempts.append)
    with pytest.raises(ProviderError, match="HTTP 429") as error:
        adapter("field rig")
    assert "secret body" not in str(error.value)
    adapter = _adapter(monkeypatch,
                       lambda request: (_ for _ in ()).throw(httpx.ReadTimeout("body")),
                       usage_callback=attempts.append)
    with pytest.raises(ProviderError, match="transport failed"):
        adapter("field rig")
    assert len(attempts) == 2 and all(not row.token_usage_complete for row in attempts)


def test_embedding_configuration_and_input_bounds(monkeypatch):
    with pytest.raises(ValueError, match="dimensions"):
        OpenAIEmbeddingAdapter(model="text-embedding-3-small", dimensions=513)
    with pytest.raises(ValueError, match="does not support dimensions"):
        OpenAIEmbeddingAdapter(model="text-embedding-ada-002", dimensions=3)
    for endpoint in ("http://example.com/v1/embeddings",
                     "https://api.openai.com/v1/embeddings?key=secret",
                     "https://user:pass@api.openai.com/v1/embeddings",
                     "https://api.openai.com/v1/responses"):
        with pytest.raises(ValueError, match="endpoint"):
            OpenAIEmbeddingAdapter(model="text-embedding-3-small", dimensions=3,
                                   endpoint=endpoint)
    attempts = []
    adapter = _adapter(monkeypatch, lambda request: pytest.fail("bad input sent"),
                       endpoint="http://localhost:8000/v1/embeddings",
                       usage_callback=attempts.append)
    for input_text in ("", " " * 4, "a" * 4097):
        with pytest.raises(ValueError, match="input"):
            adapter(input_text)
    assert attempts == []


def test_index_load_is_offline_and_query_embedding_only_after_grants(monkeypatch, tmp_path):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=_response())
    adapter = _adapter(monkeypatch, handler)
    families = _families(tmp_path)
    index, _ = _index(tmp_path, families, vectors=True, embedder=adapter)
    assert requests == []
    assert _search(index, "unrelated", authorised_families={"rig"},
                   authorised_artifacts={"rig_pilot"}) == []
    assert _search(index, "unrelated", authorised_families={"rig"},
                   authorised_claims={"rig_field": set()}) == []
    assert requests == []
    # The reviewed manifest deliberately uses a different vector model ID;
    # the authorised request calls the provider but cannot compare vectors.
    assert _search(index, "unrelated", authorised_families={"rig"}) == []
    assert len(requests) == 1
