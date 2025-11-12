# devices/local/scanner.py
# Smart reactive DMX scanner with threaded control and stepwise color-wheel handling.
from __future__ import annotations
import time, threading
from typing import Literal, Dict
from devices.remote.dmx_gateway import DMXUniverse

# ---- Hardware-specific calibration constants ----
# These limits were empirically measured and map normalized (0–255) input
# to the mechanical servo range for each scanner unit.
FIRST_X_HOME, FIRST_Y_HOME = 155, 30
FIRST_X_MIN, FIRST_X_MAX = 110, 155
FIRST_Y_MIN, FIRST_Y_MAX = 10, 90

SECOND_X_HOME, SECOND_Y_HOME = 12, 145
SECOND_X_MIN, SECOND_X_MAX = 5, 250
SECOND_Y_MIN, SECOND_Y_MAX = 5, 250

# Realistic delay between consecutive DMX writes per channel.
# These numbers model the hardware’s mechanical latency, not network latency.
REACTION_TIMES = {
    "pan": 0.1,
    "tilt": 0.1,
    "gobo": 0.25,
    "rotation": 0.2,
    "shutter": 0.1,
}

# Discrete detent values of the scanner's physical color wheel.
# The wheel cannot stop precisely between them; any intermediate
# DMX value would cause mixed or unstable colors.
COLOR_STEPS = [30, 50, 80, 100, 150, 180, 200, 250]
COLOR_NAMES = {
    "white": 30, "red": 50, "yellow": 80, "purple": 100,
    "green": 150, "orange": 180, "blue": 200, "pink": 250,
}


def _clamp(v: int | float) -> int:
    """Clamp an integer to the valid DMX byte range (0–255)."""
    return max(0, min(255, int(v)))


class ScannerDevice:
    """
    Thread-safe DMX scanner abstraction.

    Each scanner parameter (pan, tilt, gobo, rotation, shutter) runs its own worker
    thread that always applies the *latest* known command.
    This makes the device responsive without flooding the DMX universe.

    The color wheel is treated specially:
    - It can only rest on discrete mechanical detents.
    - Rapid updates would physically desync the motor.
    Therefore it uses a dedicated worker that steps sequentially
    through the color positions, waiting long enough for the wheel
    to settle between steps.
    """

    def __init__(
        self,
        universe: DMXUniverse,
        base_addr: int = 1,
        name: str = "scanner",
        profile: Literal["first", "second"] = "first",
    ):
        self.universe = universe
        self.base = base_addr
        self.name = name
        self._lock = threading.Lock()

        # ---- Apply mechanical limits for selected profile ----
        if profile == "first":
            self.x_min, self.x_max = FIRST_X_MIN, FIRST_X_MAX
            self.y_min, self.y_max = FIRST_Y_MIN, FIRST_Y_MAX
            self.x_home, self.y_home = FIRST_X_HOME, FIRST_Y_HOME
        else:
            self.x_min, self.x_max = SECOND_X_MIN, SECOND_X_MAX
            self.y_min, self.y_max = SECOND_Y_MIN, SECOND_Y_MAX
            self.x_home, self.y_home = SECOND_X_HOME, SECOND_Y_HOME

        # ---- Current cached DMX state ----
        self.pan = self.x_home
        self.tilt = self.y_home
        self.color = COLOR_NAMES["white"]
        self.gobo = 30
        self.shutter = 0
        self.rotation = 4

        # ---- Async mailboxes (for all non-color options) ----
        # Each key holds only the most recent target value;
        # older queued updates are discarded to stay real-time.
        self._latest: Dict[str, int | None] = {
            "pan": None,
            "tilt": None,
            "gobo": None,
            "rotation": None,
            "shutter": None,
        }

        # ---- Dedicated color-wheel state ----
        self._color_lock = threading.Lock()
        self._color_target: int | None = None      # latest requested color value
        self._color_current: int = self.color      # last physically confirmed detent
        self._color_dwell = 1.0                    # dwell time (s) between color steps

        # Spawn worker threads for continuous async updates.
        for key in self._latest.keys():
            threading.Thread(target=self._option_worker, args=(key,), daemon=True).start()
        threading.Thread(target=self._color_worker, daemon=True).start()

    # -------------------------------------------------
    # Generic worker loop for non-color parameters
    # -------------------------------------------------
    def _option_worker(self, key: str):
        """
        Periodically check if a new value for this parameter is pending.
        If so, apply it immediately and wait a short reaction time
        before allowing another update.
        """
        while True:
            with self._lock:
                val = self._latest[key]
                if val is not None:
                    self._latest[key] = None
            if val is not None:
                self._apply_single(key, val)
                time.sleep(REACTION_TIMES.get(key, 0.2))
            else:
                time.sleep(0.01)

    # -------------------------------------------------
    # Color-wheel worker (mechanical stepping)
    # -------------------------------------------------
    def _color_worker(self):
        """
        Drive the mechanical color wheel step by step.

        The wheel must traverse intermediate detents physically.
        Sending a large jump (e.g. red→green) directly would make
        the motor overshoot or stall. This loop guarantees safe,
        incremental travel and allows mid-flight retargeting:
        if a new color is requested, the next step recalculates
        the direction immediately.
        """
        while True:
            with self._color_lock:
                target = self._color_target
                current = self._color_current

            if target is None or target == current:
                time.sleep(0.02)
                continue

            # Determine direction (clockwise/counter-clockwise)
            path = COLOR_STEPS
            try:
                ci = path.index(current)
            except ValueError:
                # Recover gracefully if current not exactly on a detent
                ci = min(range(len(path)), key=lambda i: abs(path[i] - current))
            ti = path.index(target)
            step = 1 if ti > ci else -1
            next_i = ci + step
            next_val = path[next_i]

            # Apply this single step to DMX universe
            with self._lock:
                self.color = int(next_val)
                vals = [
                    int(self.pan),
                    int(self.tilt),
                    int(self.color),
                    int(self.gobo),
                    int(self.shutter),
                    int(self.rotation),
                ]
                self.universe.write_region(self.base, vals)

            # Update cached state for next iteration
            with self._color_lock:
                self._color_current = next_val

            # Wait for the motor to physically reach the next detent
            time.sleep(self._color_dwell)

    # -------------------------------------------------
    # Low-level DMX write helper
    # -------------------------------------------------
    def _apply_single(self, key: str, value: int):
        """
        Push one parameter update to the DMX universe.

        This function always writes the *entire* six-channel frame,
        not only the changed value, to ensure consistent output
        when multiple workers operate concurrently.
        """
        with self._lock:
            setattr(self, key, int(value))
            vals = [
                int(self.pan),
                int(self.tilt),
                int(self.color),
                int(self.gobo),
                int(self.shutter),
                int(self.rotation),
            ]
            self.universe.write_region(self.base, vals)

    def _set_latest(self, key: str, value: int):
        """Store latest command for this parameter, replacing any pending one."""
        with self._lock:
            self._latest[key] = int(value)

    # -------------------------------------------------
    # Calibration routine
    # -------------------------------------------------
    def calibrate_full_reset(self):
        """
        Perform a safe startup calibration sequence.

        The scanner briefly drives all channels to their absolute extremes
        to re-synchronize its DMX decoder with the fixture’s servos.
        Afterwards it returns to the defined home position.
        """
        def _task():
            u = self.universe
            b = self.base

            # Full-range sweeps help the internal stepper drivers resync.
            u.write_region(b, [255, 255, 255, 255, 255, 255])
            time.sleep(2.5)
            u.write_region(b, [0, 0, 0, 0, 0, 0])
            time.sleep(2.5)

            # Return to neutral home position and reset caches.
            u.write_region(b, [self.x_home, self.y_home, 30, 30, 29, 4])
            time.sleep(2.5)
            self.pan, self.tilt = self.x_home, self.y_home
            self.color, self.gobo, self.shutter, self.rotation = 30, 30, 29, 4
            with self._color_lock:
                self._color_current = 30
                self._color_target = None

        threading.Thread(target=_task, daemon=True).start()

    # -------------------------------------------------
    # Public API — movement & effect control
    # -------------------------------------------------
    def move_to_raw(self, pan: int, tilt: int):
        """Set absolute raw DMX pan/tilt values (0–255)."""
        self._set_latest("pan", _clamp(pan))
        self._set_latest("tilt", _clamp(tilt))

    def move_to_norm(self, x: int, y: int):
        """Map normalized 0–255 coordinates to the unit’s mechanical range."""
        x = max(0, min(255, int(x)))
        y = max(0, min(255, int(y)))
        px = int(self.x_min + (self.x_max - self.x_min) * (x / 255.0))
        py = int(self.y_min + (self.y_max - self.y_min) * (y / 255.0))
        self.move_to_raw(px, py)

    def go_home(self):
        """Return pan/tilt to predefined home coordinates."""
        self.move_to_raw(self.x_home, self.y_home)

    def set_color_step(self, value_or_name: int | str):
        """
        Queue a new color target for the wheel.

        The actual transition is handled asynchronously by `_color_worker()`.
        This design prevents over-driving the motor and ensures that each
        intermediate color detent is physically reached.
        """
        if isinstance(value_or_name, str):
            val = COLOR_NAMES.get(value_or_name.lower(), COLOR_NAMES["white"])
        else:
            raw = _clamp(value_or_name)
            val = min(COLOR_STEPS, key=lambda v: abs(v - raw))
        with self._color_lock:
            self._color_target = val

    def set_gobo(self, value: int):
        """Set gobo wheel position (fast, electronic)."""
        self._set_latest("gobo", _clamp(value))

    def set_rotation_legacy(self, rotation: int):
        """
        Apply legacy rotation mapping.

        Converts human-readable −255…+255 values to DMX wheel speed ranges
        used by older fixtures.
        """
        r = int(rotation)
        if r > 0:
            out = int((r / 2.2) + 5)
        elif r < 0:
            out = int(((-r) / 2.2) + 140)
        else:
            out = 0
        self._set_latest("rotation", _clamp(out))

    # -------------------------------------------------
    # Shutter control
    # -------------------------------------------------
    def open(self, legacy_level: int = 20):
        """Open the shutter to a given brightness level."""
        self._set_latest("shutter", _clamp(legacy_level))

    def close(self):
        """Close the shutter completely (blackout)."""
        self._set_latest("shutter", 0)

    def strobe(self, on: bool, strength: int = 250):
        """Toggle strobe effect by adjusting shutter speed."""
        self._set_latest("shutter", _clamp(strength if on else 20))
