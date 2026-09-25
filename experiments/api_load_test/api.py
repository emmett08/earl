"""Controlled loopback HTTP API and client-side measurements.

These are real requests to an experimental service, not production traffic.
Fault injection varies the task; acceptance always uses measured results.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_id():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


@contextmanager
def serve(profile: dict, run_id: str):
    events = []
    lock = threading.Lock()
    identity = build_id()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"

        def do_GET(self):
            parsed = urlsplit(self.path)
            try:
                index = int(parse_qs(parsed.query)["request_id"][0])
                if parsed.path != "/orders/quote" or index < 0:
                    raise ValueError("Invalid request")
            except (ValueError, KeyError):
                self.send_error(400)
                return
            # A small order calculation, with predeclared latency/error controls.
            total_pence = sum(price * quantity for price, quantity in ((199, 2), (350, 1)))
            delay = profile["delay_ms"] + (index % 5) * profile["jitter_ms"]
            time.sleep(delay / 1000)
            every = profile["error_every"]
            status = 503 if every and (index + 1) % every == 0 else 200
            body = json.dumps({"request_id": index, "total_pence": total_pence,
                               "build_id": identity, "run_id": run_id}).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Build-ID", identity)
            self.send_header("X-Run-ID", run_id)
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass
            with lock:
                events.append({"request_id": index, "status_code": status,
                               "build_id": identity, "run_id": run_id})

        def log_message(self, *_):
            pass

    class Server(ThreadingHTTPServer):
        request_queue_size = 128
        daemon_threads = True

    server = Server(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield {"port": server.server_port, "build_id": identity, "events": events}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def measure(config: dict) -> dict:
    """Execute the host-selected workload. No external target or model code."""
    workload = config["input"]
    if not (type(config["port"]) is int and 1 <= config["port"] <= 65535):
        raise ValueError("Invalid loopback port")
    count, clients = workload["request_count"], workload["concurrent_clients"]
    if type(count) is not int or not 1 <= count <= 1000:
        raise ValueError("Request count must be between 1 and 1000")
    if type(clients) is not int or not 1 <= clients <= 20:
        raise ValueError("Concurrent clients must be between 1 and 20")
    timeout = workload["timeout_seconds"]
    if type(timeout) not in (int, float) or not 0 < timeout <= 10:
        raise ValueError("Request timeout must be at most ten seconds")

    def one(index):
        connection = http.client.HTTPConnection("127.0.0.1", config["port"], timeout=timeout)
        started = time.perf_counter_ns()
        status, matches, error = 0, False, None
        try:
            connection.request("GET", f"/orders/quote?request_id={index}")
            response = connection.getresponse()
            body = response.read(65537)
            if len(body) > 65536:
                raise ValueError("Response exceeded the body limit")
            payload = json.loads(body)
            status = response.status
            matches = (response.getheader("X-Build-ID") == workload["build_id"]
                       and response.getheader("X-Run-ID") == workload["run_id"]
                       and payload.get("build_id") == workload["build_id"]
                       and payload.get("run_id") == workload["run_id"]
                       and payload.get("request_id") == index
                       and payload.get("total_pence") == 748)
        except (OSError, http.client.HTTPException, ValueError, AttributeError) as exc:
            error = type(exc).__name__
        finally:
            elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
            connection.close()
        return {"request_id": index, "status_code": status, "elapsed_ms": elapsed_ms,
                "identity_matches": matches, "error": error}

    started_at = utc_now()
    with ThreadPoolExecutor(max_workers=clients) as pool:
        rows = list(pool.map(one, range(count)))
    return {"schema": "eal-live-api-report/1", "dataset": "measured_controlled_api",
            "started_at": started_at, "observed_at": utc_now(),
            "input": workload, "context": config["context"], "requests": rows}
