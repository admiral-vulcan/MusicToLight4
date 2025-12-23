# devices/remote/udp_gateway.py

from __future__ import annotations

import logging
import queue
import socket
import threading
from dataclasses import dataclass
from typing import Iterable, Optional, Union

Payload = Union[bytes, bytearray, memoryview, str]

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class UdpEndpoint:
    """Represents a UDP target."""
    host: str
    port: int = 4210

    @property
    def key(self) -> str:
        return f"{self.host}:{self.port}"


class UdpGateway:
    """
    UDP transport gateway.

    - Reuses a single UDP socket.
    - Optional async sending via a worker thread (default).
    - Preserves per-endpoint ordering via per-endpoint locks.
    """

    def __init__(
        self,
        *,
        bind_host: str = "0.0.0.0",
        bind_port: int = 0,
        async_send: bool = True,
        queue_maxsize: int = 4096,
        encoding: str = "utf-8",
    ) -> None:
        self._encoding = encoding
        self._async_send = async_send

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind((bind_host, bind_port))

        self._endpoint_locks: dict[str, threading.Lock] = {}
        self._endpoint_locks_guard = threading.Lock()

        self._q: queue.Queue[tuple[UdpEndpoint, bytes]] = queue.Queue(maxsize=queue_maxsize)
        self._stop = threading.Event()
        self._worker: Optional[threading.Thread] = None

        if self._async_send:
            self._worker = threading.Thread(target=self._run, name="UdpGatewayWorker", daemon=True)
            self._worker.start()

    def close(self) -> None:
        """Stop worker (if any) and close the socket."""
        self._stop.set()
        if self._worker and self._worker.is_alive():
            # Unblock queue.get()
            try:
                self._q.put_nowait((UdpEndpoint("127.0.0.1", 9), b""))
            except queue.Full:
                pass
            self._worker.join(timeout=1.0)

        try:
            self._sock.close()
        except OSError:
            pass

    def __enter__(self) -> "UdpGateway":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def flush(self, timeout: float = 2.0) -> bool:
        """
        Wait until the async queue is empty.
        Returns True if queue drained before timeout.
        """
        if not self._async_send:
            return True

        import time
        end = time.time() + timeout
        while time.time() < end:
            if self._q.empty():
                return True
            time.sleep(0.01)
        return self._q.empty()

    def send(self, endpoint: UdpEndpoint, payload: Payload, *, encoding: Optional[str] = None) -> bool:
        """
        Send payload to endpoint.
        Returns True if accepted for sending (or sent), False if dropped (queue full).
        """
        data = self._to_bytes(payload, encoding=encoding)

        if self._async_send:
            try:
                self._q.put_nowait((endpoint, data))
                return True
            except queue.Full:
                _LOG.debug("UDP queue full, dropping packet for %s", endpoint.key)
                return False

        self._send_now(endpoint, data)
        return True

    def send_many(self, endpoint: UdpEndpoint, payloads: Iterable[Payload], *, encoding: Optional[str] = None) -> int:
        """Send multiple payloads; returns number accepted."""
        accepted = 0
        for p in payloads:
            if self.send(endpoint, p, encoding=encoding):
                accepted += 1
        return accepted

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                endpoint, data = self._q.get(timeout=0.25)
            except queue.Empty:
                continue

            if self._stop.is_set():
                break

            if not data:
                continue

            self._send_now(endpoint, data)

    def _send_now(self, endpoint: UdpEndpoint, data: bytes) -> None:
        lock = self._get_endpoint_lock(endpoint.key)
        with lock:
            try:
                self._sock.sendto(data, (endpoint.host, endpoint.port))
            except OSError as e:
                _LOG.warning("Could not send UDP packet to %s: %s", endpoint.key, e)

    def _get_endpoint_lock(self, key: str) -> threading.Lock:
        with self._endpoint_locks_guard:
            lock = self._endpoint_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._endpoint_locks[key] = lock
            return lock

    def _to_bytes(self, payload: Payload, *, encoding: Optional[str] = None) -> bytes:
        if isinstance(payload, (bytes, bytearray, memoryview)):
            return bytes(payload)
        if isinstance(payload, str):
            return payload.encode(encoding or self._encoding)
        raise TypeError(f"Unsupported payload type: {type(payload)!r}")
