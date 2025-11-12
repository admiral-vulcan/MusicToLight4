# services/device_scheduler.py
import threading
import time
import queue
from typing import Callable, Dict, Any

class DeviceScheduler:
    """Central queue for serialized DMX/LED actions."""
    def __init__(self, devices: Dict[str, Any]):
        self.devices = devices
        self.q = queue.PriorityQueue()
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        self.q.put((9999, None, None))  # wake up

    def enqueue(self, priority: int, device: str, command: str, *args, delay: float = 0.0):
        """Add a device command to the queue."""
        execute_at = time.monotonic() + delay
        self.q.put((priority, execute_at, (device, command, args)))

    def _loop(self):
        while self._running:
            try:
                priority, execute_at, payload = self.q.get(timeout=0.1)
                if not payload:
                    continue
                device_name, command, args = payload
                now = time.monotonic()
                if now < execute_at:
                    time.sleep(execute_at - now)

                dev = self.devices.get(device_name)
                if not dev:
                    print(f"[SCHED] Unknown device {device_name}")
                    continue

                func: Callable = getattr(dev, command, None)
                if func:
                    func(*args)
                    print(f"[SCHED] Executed {device_name}.{command}{args}")
                else:
                    print(f"[SCHED] Missing method {command} on {device_name}")
            except queue.Empty:
                continue
