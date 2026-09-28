"""Optional Responses API adapter for pinned text model versions.

The study protocol uses a subprocess boundary so other providers implement the
same JSON contract without changing the allocation or analysis code.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def respond(request: dict) -> dict:
    if request.get("schema") != "EAL/transfer-model-request/1":
        raise ValueError("Expected a transfer-study model request")
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise ValueError("OPENAI_API_KEY is required")
    messages = request["messages"]
    if (not isinstance(messages, list) or not messages or
            any(not isinstance(message, dict) or
                message.get("role") not in ("system", "developer", "user", "assistant") or
                not isinstance(message.get("content"), str) for message in messages)):
        raise ValueError("Only text messages with known roles are supported")
    payload = json.dumps({"model": request["model_version"], "input": messages,
                          "store": False}, ensure_ascii=False).encode("utf-8")
    http = urllib.request.Request(
        "https://api.openai.com/v1/responses", data=payload, method="POST",
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(http, timeout=540) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Responses API returned HTTP {exc.code}") from exc
    if result.get("status") != "completed" or result.get("error") is not None:
        raise RuntimeError(f"Responses API returned status {result.get('status')!r}")
    content = "".join(part["text"] for item in result.get("output", [])
                      if item.get("type") == "message"
                      for part in item.get("content", [])
                      if part.get("type") == "output_text")
    usage = result.get("usage") or {}
    if not content or not all(type(usage.get(key)) is int
                              for key in ("input_tokens", "output_tokens")):
        raise RuntimeError("Responses API did not return complete text and token usage")
    return {"schema": "EAL/transfer-model-response/1",
            "model_version": request["model_version"],
            "reported_model": result.get("model"),
            "provider_response_id": result.get("id"),
            "content": content,
            "usage": {"input_tokens": usage["input_tokens"],
                      "output_tokens": usage["output_tokens"]}}


def main() -> None:
    try:
        request = json.load(sys.stdin)
        print(json.dumps(respond(request), ensure_ascii=False, allow_nan=False))
    except (ValueError, KeyError, TypeError, RuntimeError, urllib.error.URLError) as exc:
        print(f"Model adapter failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
