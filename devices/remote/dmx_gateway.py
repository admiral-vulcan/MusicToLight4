# devices/remote/dmx_gateway.py
from __future__ import annotations
import threading
import time
import requests

class DMXUniverse:
    """
    Shared, thread-safe DMX universe with a single TX thread.
    Devices call write_region(); the worker sends the merged frame at a steady fps.
    """
    def __init__(self, host="192.168.1.151", port=9090, universe=0, fps=30, timeout=0.5):
        self.base_url = f"http://{host}:{port}"
        self.universe = int(universe)
        self.timeout = timeout

        self._frame = [0] * 512
        self._lock = threading.Lock()
        self._dirty = False

        self._running = True
        self._tick = 1.0 / float(max(1, fps))
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    # --- public API ---
    def write_region(self, start_1_based: int, values: list[int]) -> None:
        """Write a contiguous slice (1-based DMX address)."""
        start = max(1, int(start_1_based)) - 1
        end = min(512, start + len(values))
        vals = [max(0, min(255, int(v))) for v in values]
        with self._lock:
            self._frame[start:end] = vals[: end - start]
            self._dirty = True

    def blackout(self) -> None:
        with self._lock:
            self._frame = [0] * 512
            self._dirty = True

    def stop(self) -> None:
        self._running = False
        self._thread.join(timeout=1.0)

    # --- internal ---
    def _worker(self):
        sess = requests.Session()
        url = f"{self.base_url}/set_dmx"
        while self._running:
            t0 = time.monotonic()
            payload = None
            with self._lock:
                if self._dirty:
                    payload = {
                        "u": self.universe,
                        "d": ",".join(str(x) for x in self._frame),
                    }
                    self._dirty = False
            if payload:
                try:
                    r = sess.post(url, data=payload, timeout=self.timeout)
                    if r.status_code != 200:
                        # optional: print(f"[DMX] HTTP {r.status_code}: {r.text}")
                        pass
                except Exception:
                    # optional: print(f"[DMX] send error")
                    pass
            # pace
            dt = time.monotonic() - t0
            time.sleep(max(0.0, self._tick - dt))
