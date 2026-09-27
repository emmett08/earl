"""Bounded, sanitized billing/access check before a live study cohort.

This operational request is outside the assigned coding and decision units.
It tests the same model, credential, proxy route and outer filesystem mount.
Only allowlisted status and token counts leave the runner; provider responses,
errors and the credential itself are never retained as artifacts.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from runner_capture import bwrap_prefix, json_write


MODEL = "gpt-6-sol"
MAX_OUTPUT_TOKENS = 64
REQUEST_TIMEOUT_SECONDS = 25
PROCESS_TIMEOUT_SECONDS = 40

PROBE = r'''
import json, os, sys
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        # Never forward an Authorization header to another URL or issue a
        # second request. HTTPError below classifies all 3xx as a failure.
        return None

payload = {"model": "gpt-6-sol", "input": "Reply READY.",
           "reasoning": {"effort": "medium"}, "max_output_tokens": 64,
           "store": False}
request = Request("https://api.openai.com/v1/responses",
                  data=json.dumps(payload).encode("utf-8"),
                  headers={"Authorization": "Bearer " + os.environ["CODEX_API_KEY"],
                           "Content-Type": "application/json"},
                  method="POST")
try:
    with build_opener(NoRedirect).open(request, timeout=25) as response:
        body = response.read(65537)
        if len(body) > 65536:
            raise ValueError("oversized response")
        result = json.loads(body)
except HTTPError as error:
    # Do not print a provider error body: it may contain account information.
    body = error.read(4096)
    try:
        detail = json.loads(body).get("error", {})
    except (ValueError, AttributeError):
        detail = {}
    code = detail.get("code") if isinstance(detail, dict) else None
    message = detail.get("message", "") if isinstance(detail, dict) else ""
    if code in ("insufficient_quota", "billing_hard_limit_reached") or "no credits remaining" in str(message).lower():
        category = "credit_exhausted"
    elif error.code in (401, 403):
        category = "credential_rejected"
    elif error.code == 429:
        category = "rate_limited"
    else:
        category = "provider_http_error"
    print(json.dumps({"status": "fail", "category": category}))
    sys.exit(2)
except (URLError, TimeoutError, OSError):
    print(json.dumps({"status": "fail", "category": "transport_error"}))
    sys.exit(2)
except Exception:
    print(json.dumps({"status": "fail", "category": "unexpected_error"}))
    sys.exit(2)

usage = result.get("usage") if isinstance(result, dict) else None
if (not isinstance(usage, dict) or
        any(type(usage.get(field)) is not int or usage[field] < 0
            for field in ("input_tokens", "output_tokens"))):
    print(json.dumps({"status": "fail", "category": "usage_missing"}))
    sys.exit(2)
print(json.dumps({"status": "pass", "category": "completed_request",
                  "input_tokens": usage["input_tokens"],
                  "output_tokens": usage["output_tokens"],
                  "response_status": result.get("status")}))
'''


def sanitized_result(returncode: int, stdout: bytes, elapsed: float) -> dict[str, object]:
    """Reject arbitrary subprocess output before creating the retained record."""
    record: dict[str, object] = {
        "schema": "architecture-extension-v4/credential-gate/1",
        "model": MODEL,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "actual_wall_seconds": elapsed,
        "exit_code": returncode,
        "status": "fail",
        "category": "invalid_probe_output",
        "input_tokens": None,
        "output_tokens": None,
    }
    if len(stdout) > 1024:
        return record
    try:
        value = json.loads(stdout.decode("utf-8"))
    except (ValueError, UnicodeError):
        return record
    if not isinstance(value, dict):
        return record
    if (returncode == 0 and value.get("status") == "pass" and
            value.get("category") == "completed_request" and
            value.get("response_status") in ("completed", "incomplete") and
            all(type(value.get(field)) is int and value[field] >= 0
                for field in ("input_tokens", "output_tokens")) and
            0 < value["input_tokens"] <= 1000 and
            0 < value["output_tokens"] <= MAX_OUTPUT_TOKENS):
        record.update(status="pass", category="completed_request",
                      input_tokens=value["input_tokens"],
                      output_tokens=value["output_tokens"])
    elif returncode != 0 and value.get("status") == "fail" and value.get("category") in {
            "credit_exhausted", "credential_rejected", "rate_limited",
            "provider_http_error", "transport_error", "unexpected_error",
            "usage_missing"}:
        record["category"] = value["category"]
    return record


def main() -> int:
    output = Path(os.environ["RUNNER_TEMP"]) / "v4-credential-gate" / "status.json"
    key = os.environ.get("CODEX_API_KEY", "")
    if not key:
        json_write(output, {"schema": "architecture-extension-v4/credential-gate/1",
                            "model": MODEL, "status": "fail", "category": "secret_missing",
                            "input_tokens": None, "output_tokens": None,
                            "actual_wall_seconds": 0.0, "exit_code": None,
                            "max_output_tokens": MAX_OUTPUT_TOKENS})
        print("authenticated provider gate: secret_missing")
        return 1
    with tempfile.TemporaryDirectory(prefix="v4-credential-check-") as location:
        root = Path(location)
        trial, home = root / "trial", root / "home"
        trial.mkdir()
        home.mkdir()
        (trial / "FEATURE.md").write_text("Operational credential probe only.\n", encoding="utf-8")
        environment = {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
                       "HOME": str(home), "LANG": os.environ.get("LANG", "C.UTF-8"),
                       "CODEX_API_KEY": key}
        for name in ("HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY"):
            if os.environ.get(name):
                environment[name] = os.environ[name]
        started = time.monotonic()
        try:
            result = subprocess.run(
                bwrap_prefix(trial, home) + ["/usr/bin/python3", "-c", PROBE],
                env=environment, cwd=trial, capture_output=True,
                timeout=PROCESS_TIMEOUT_SECONDS, check=False)
            record = sanitized_result(result.returncode, result.stdout,
                                      time.monotonic() - started)
        except subprocess.TimeoutExpired:
            record = sanitized_result(124, b"", time.monotonic() - started)
            record["category"] = "timeout"
        except Exception:
            record = sanitized_result(1, b"", time.monotonic() - started)
            record["category"] = "preflight_error"
    json_write(output, record)
    print("authenticated provider gate: " + str(record["status"]) +
          " (" + str(record["category"]) + ")")
    return 0 if record["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
