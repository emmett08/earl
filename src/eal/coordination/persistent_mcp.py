"""A synchronous owner of one MCP session on one dedicated event-loop task.

Requests are serialized. Broken connections are terminal: no uncertain tool
call is retried or moved to a replacement server implicitly.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import Future
import threading

from mcp import ClientSession
from mcp.client.stdio import stdio_client


class PersistentMCP:
    def __init__(self, parameters, timeout):
        self.parameters = parameters
        self.timeout = timeout
        self.thread = None
        self.loop = None
        self.task = None
        self.requests = None
        self.closed = False
        self.starts = 0
        self._lock = threading.RLock()
        self._ready = Future()

    async def _serve(self):
        self.loop = asyncio.get_running_loop()
        self.task = asyncio.current_task()
        self.requests = asyncio.Queue()
        current = None
        try:
            async with stdio_client(self.parameters) as (reader, writer):
                async with ClientSession(reader, writer, read_timeout_seconds=self.timeout) as session:
                    async with asyncio.timeout(self.timeout):
                        await session.initialize()
                    self._ready.set_result(None)
                    while True:
                        name, arguments, current = await self.requests.get()
                        try:
                            async with asyncio.timeout(self.timeout):
                                result = await session.call_tool(name, arguments)
                        except BaseException:
                            # Tool transport errors may occur after a durable effect.
                            # Let cleanup complete before releasing the caller.
                            raise
                        else:
                            current.set_result(result)
                            current = None
        except BaseException as error:
            self.closed = True
            failure = TimeoutError("Persistent MCP operation timed out; reconcile before reopening") if isinstance(error, TimeoutError) else RuntimeError("Persistent MCP connection failed; no operation was retried")
            if not self._ready.done():
                self._ready.set_exception(failure)
            if current is not None and not current.done():
                current.set_exception(failure)
        finally:
            self.closed = True
            if self.requests is not None:
                while not self.requests.empty():
                    _, _, pending = self.requests.get_nowait()
                    if not pending.done():
                        pending.set_exception(RuntimeError("Persistent MCP connection closed"))

    def _run(self):
        asyncio.run(self._serve())

    def call(self, name, arguments):
        with self._lock:
            if self.closed:
                raise RuntimeError("Persistent MCP transport is closed; reopen explicitly")
            try:
                if self.thread is None:
                    self.thread = threading.Thread(target=self._run, name="eal-lab-mcp", daemon=True)
                    self.starts += 1
                    self.thread.start()
                    self._ready.result(timeout=self.timeout + 5)
                pending = Future()
                self.loop.call_soon_threadsafe(self.requests.put_nowait, (name, arguments, pending))
                return pending.result(timeout=self.timeout + 5)
            except BaseException:
                self.close()
                raise

    def close(self):
        with self._lock:
            self.closed = True
            if self.loop is not None and not self.loop.is_closed() and self.task is not None:
                self.loop.call_soon_threadsafe(self.task.cancel)
            if self.thread is not None and threading.current_thread() is not self.thread:
                self.thread.join(timeout=5)
