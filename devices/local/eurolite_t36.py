# devices/local/eurolite_t36.py
# Threaded EUROLITE LED T-36 RGB Spot (5 channels)
from __future__ import annotations
import threading
import time
from typing import Tuple
from devices.remote.dmx_gateway import DMXUniverse


class EuroliteT36:
    """
    Threaded DMX abstraction for the EUROLITE LED T-36 RGB Spot.

    DMX Map (default base address 24):
        1: Red
        2: Green
        3: Blue
        4: Dimmer
        5: Strobe

    Design notes (why):
    - Runs its own worker thread at ~30 Hz to interpolate RGB/Dimmer smoothly.
    - Uses a per-instance lock so public setters are race-free.
    - Writes only to its own address range, so it can operate safely
      in parallel with other fixtures (e.g., scanners) as long as
      DMXUniverse aggregates regions and is (or is treated as) thread-safe.
    """

    def __init__(self, universe: DMXUniverse, base_addr: int = 24, name: str = "t36"):
        self.universe = universe
        self.base = base_addr
        self.name = name
        self.channels = 5

        # Current state (floats for interpolation).
        # Why floats? Prevents quantization jitter during fades.
        self._rgb = [0.0, 0.0, 0.0]
        self._dimmer = 0.0
        self._strobe = 0.0

        # Target state with simple time-based interpolation.
        self._target_rgb = [0.0, 0.0, 0.0]
        self._target_dimmer = 0.0
        self._target_strobe = 0.0
        self._target_duration = 0.0
        self._target_timestamp = 0.0

        # Concurrency primitives.
        self._lock = threading.Lock()
        self._running = True
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    # -------------------------------------------------
    # Public API
    # -------------------------------------------------
    def set_color(self, rgb: Tuple[int, int, int], duration: float = 0.0):
        """
        Change RGB color instantly or smoothly over <duration> seconds.

        Why auto-enable dimmer?
        - If a color is requested while dimmer is 0, the user expectation is
          "turn the light on in that color". We bump dimmer to 255 implicitly
          (can still be overridden by a subsequent set_dimmer()).
        """
        with self._lock:
            self._target_rgb = [self._clamp(v) for v in rgb]
            if any(v > 0 for v in self._target_rgb) and self._target_dimmer == 0:
                self._target_dimmer = 255
            self._target_duration = float(duration)
            self._target_timestamp = time.monotonic()

    def set_dimmer(self, value: int, duration: float = 0.0):
        """
        Change brightness instantly or smoothly over <duration> seconds.

        Why clamp <2 to 0?
        - Many fixtures treat very low dimmer values as "still visibly on".
          We snap values below 2 to true blackout for deterministic behavior.
        """
        with self._lock:
            self._target_dimmer = 0 if value < 2 else self._clamp(value)
            self._target_duration = float(duration)
            self._target_timestamp = time.monotonic()

    def set_strobe(self, value: int):
        """Set strobe speed (0–255, 0 = off)."""
        with self._lock:
            self._target_strobe = self._clamp(value)

    def blackout(self):
        """
        Immediately turn all channels off and push to DMX.

        Why immediate apply?
        - Avoids lingering intermediate frames from the worker loop and guarantees
          a true blackout even if a fade was in progress.
        """
        with self._lock:
            self._target_rgb = [0, 0, 0]
            self._target_dimmer = 0
            self._target_strobe = 0
            self._rgb = [0, 0, 0]
            self._dimmer = 0
            self._strobe = 0
            self._apply()  # push now to avoid a 1-frame delay

    def stop(self):
        """
        Stop the internal worker thread cleanly.

        Why join?
        - Ensures no further DMX writes are attempted after teardown,
          useful in test harnesses or when unloading devices dynamically.
        """
        self._running = False
        self._thread.join(timeout=1.0)

    # -------------------------------------------------
    # Worker thread
    # -------------------------------------------------
    def _worker(self):
        """
        Interpolates toward target values and updates the DMX universe (~30 Hz).

        Why time-based alpha instead of fixed step sizes?
        - Gives duration-based fades independent of CPU load and tick jitter.
        """
        tick = 1 / 30.0  # match typical DMX sender FPS to avoid overscheduling
        while self._running:
            start = time.monotonic()
            with self._lock:
                elapsed = start - self._target_timestamp
                # Guard duration to avoid div-by-zero and to get snappy immediate jumps.
                dur = max(0.01, self._target_duration)
                alpha = min(1.0, elapsed / dur) if dur > 0 else 1.0

                # Linear interpolation for RGB + Dimmer.
                for i in range(3):
                    self._rgb[i] += (self._target_rgb[i] - self._rgb[i]) * alpha
                self._dimmer += (self._target_dimmer - self._dimmer) * alpha

                # Strobe is not interpolated (fixtures typically latch rate changes).
                self._strobe = self._target_strobe

                # Push one consolidated frame to the universe.
                self._apply()

            # Maintain loop timing without drift.
            sleep_t = max(0.0, tick - (time.monotonic() - start))
            time.sleep(sleep_t)

    # -------------------------------------------------
    # DMX write helper
    # -------------------------------------------------
    def _apply(self):
        """
        Write current channel values to the shared DMX universe.

        Thread-safety note:
        - If DMXUniverse exposes a `.lock`, we use it here to serialize writes
          across multiple fixtures (scanners, spots, etc.). This avoids races
          in universes that aggregate a full frame from partial regions.
        """
        r, g, b = map(int, self._rgb)
        dim = int(self._dimmer)
        if dim < 2:
            dim = 0

        vals = [r, g, b, dim, int(self._strobe)]

        # Optional cross-device serialization (plays nice with parallel scanners).
        lock = getattr(self.universe, "lock", None)
        if lock is not None:
            with lock:
                try:
                    self.universe.write_region(self.base, vals)
                except Exception as e:
                    # Fail-safe: never kill the worker thread on DMX hiccups.
                    print(f"[{self.name}] DMX write failed: {e}")
        else:
            # Assume DMXUniverse is internally thread-safe.
            try:
                self.universe.write_region(self.base, vals)
            except Exception as e:
                print(f"[{self.name}] DMX write failed: {e}")

    # -------------------------------------------------
    # Utility
    # -------------------------------------------------
    @staticmethod
    def _clamp(v: int | float) -> int:
        """Clamp any numeric to a valid DMX byte (0–255)."""
        return max(0, min(255, int(v)))
