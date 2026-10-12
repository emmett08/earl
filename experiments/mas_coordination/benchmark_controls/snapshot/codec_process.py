"""Bounded, serial requests to a persistent Rust codec; no Python wire parser.

Also imported directly by the isolated Lab server, without importing EAL.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import selectors
import subprocess
import threading
import time


class CodecUnavailable(RuntimeError):
    pass


class CodecProcess:
    output_limit = 65536 * 4 + 4096

    def __init__(self, binary, *, timeout=10, environment=None):
        self.binary = str(Path(binary))
        self.timeout = timeout
        self.environment = environment
        self.process = None
        self.starts = 0
        self.closed = False
        self._lock = threading.RLock()

    def close(self):
        with self._lock:
            self.closed = True
            process = self.process
            if process is not None:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=3)
                for stream in (process.stdin, process.stdout):
                    if stream is not None:
                        stream.close()

    @staticmethod
    def _wait(fd, event, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise CodecUnavailable("Rust codec request timed out")
        with selectors.DefaultSelector() as selector:
            selector.register(fd, event)
            if not selector.select(remaining):
                raise CodecUnavailable("Rust codec request timed out")

    def call(self, operation, source, max_bytes=65536, max_depth=32):
        if operation not in {"encode", "parse", "admit"} or type(source) is not str:
            raise ValueError("Invalid codec operation or source")
        if type(max_bytes) is not int or not 1 <= max_bytes <= 65536:
            raise ValueError("Invalid codec byte limit")
        if type(max_depth) is not int or not 1 <= max_depth <= 32:
            raise ValueError("Invalid codec depth limit")
        allowance = 256 if operation in {"encode", "admit"} else 0
        if len(source.encode("utf-8")) > max_bytes + allowance:
            raise ValueError("Codec source exceeds its byte limit")
        request = (json.dumps({"operation": operation, "source": source,
                               "max_bytes": max_bytes, "max_depth": max_depth},
                              ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
        with self._lock:
            if self.closed:
                raise CodecUnavailable("Rust codec connection is closed; reopen explicitly")
            deadline = time.monotonic() + self.timeout
            try:
                if self.process is None:
                    self.process = subprocess.Popen([self.binary, "serve"], stdin=subprocess.PIPE,
                                                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                                    bufsize=0, env=self.environment)
                    self.starts += 1
                    os.set_blocking(self.process.stdin.fileno(), False)
                    os.set_blocking(self.process.stdout.fileno(), False)
                if self.process.poll() is not None:
                    raise CodecUnavailable("Rust codec process exited")
                write_fd = self.process.stdin.fileno()
                read_fd = self.process.stdout.fileno()
                offset = 0
                while offset < len(request):
                    self._wait(write_fd, selectors.EVENT_WRITE, deadline)
                    try:
                        offset += os.write(write_fd, request[offset:])
                    except BlockingIOError:
                        continue
                output = bytearray()
                while True:
                    self._wait(read_fd, selectors.EVENT_READ, deadline)
                    try:
                        chunk = os.read(read_fd, min(65536, self.output_limit + 1 - len(output)))
                    except BlockingIOError:
                        continue
                    if not chunk:
                        raise CodecUnavailable("Rust codec closed its response stream")
                    output.extend(chunk)
                    if len(output) > self.output_limit:
                        raise CodecUnavailable("Rust codec exceeded its result limit")
                    if b"\n" in output:
                        if not output.endswith(b"\n") or output.count(b"\n") != 1:
                            raise CodecUnavailable("Rust codec returned an invalid response frame")
                        break
                def unique_pairs(items):
                    result = {}
                    for key, value in items:
                        if key in result:
                            raise CodecUnavailable("Rust codec returned duplicate response fields")
                        result[key] = value
                    return result
                value = json.loads(output, object_pairs_hook=unique_pairs,
                                   parse_constant=lambda value: (_ for _ in ()).throw(
                                       CodecUnavailable("Rust codec returned nonfinite JSON")))
                if type(value) is not dict or type(value.get("ok")) is not bool:
                    raise CodecUnavailable("Rust codec returned an invalid response envelope")
                expected = "text" if operation == "encode" else "message"
                if value["ok"]:
                    if set(value) != {"ok", expected} or type(value[expected]) is not (str if expected == "text" else dict):
                        raise CodecUnavailable("Rust codec returned an invalid success envelope")
                elif (set(value) != {"ok", "error"} or type(value["error"]) is not dict
                      or type(value["error"].get("code")) is not str
                      or type(value["error"].get("message")) is not str):
                    raise CodecUnavailable("Rust codec returned an invalid diagnostic")
                return value
            except (OSError, UnicodeError, ValueError, RecursionError, CodecUnavailable) as exc:
                self.close()
                raise CodecUnavailable("Rust codec connection failed; no request was retried") from exc
