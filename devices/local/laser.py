# devices/local/laser.py
# Threaded 34-channel RGB animation laser (club-style control, no cheesy text/auto)
from __future__ import annotations
import threading, time
from typing import Optional, Tuple, Literal, Dict, List
from devices.remote.dmx_gateway import DMXUniverse

# Notes on this class:
# - Focus on "manual" DMX control (no auto/sound), static or gently animated club patterns.
# - Many rebranded 34CH lasers share near-identical DMX tables but CH1 varies by firmware.
#   We therefore make CH1 configurable via `ch1_mode` and default to a "DMX manual ON" value.
#   See e.g. eHAHO L2600 manuals and clones; always test your unit. (Sources in README/docs.)

class Laser34:
    """
    34-channel laser abstraction with a small, composable API:
      - enable()/blackout()
      - select_group()/select_pattern()
      - set_color() via CH29
      - set_zoom()/set_rotation() (coarse + fine)
      - set_motion() for X/Y (coarse + fine)
      - set_grating() (CH17/CH34)
      - set_dots()/set_twist()

    Thread model:
      - One worker thread pushes the current 34-channel frame at `fps` (default 30 Hz).
      - Public setters are thread-safe; they update the desired frame immediately.
      - Interpolation is minimal (lasers expect jumps); timing-sensitive effects use dwell times.
    """

    # ---- Channel indices (0-based offset inside our 34-value frame) ----
    CH = {
        "ON1": 0,  # CH1   (abs = base+0)
        "BOUND": 1,  # CH2
        "GROUP": 2,  # CH3
        "UNKNOWN": 3,       # CH4  <-- NICHT nutzen für Pattern (bei dir wirkungslos)
        "ZOOM": 4,  # CH5
        "ROT": 5,  # CH6
        "XMV": 6,  # CH7
        "YMV": 7,  # CH8
        "XZM": 8,  # CH9
        "YZM": 9,  # CH10
        "COL_FIX": 10,  # CH11
        "COL_MODE": 11,  # CH12  (Color-Engine A; bei dir evtl. ohne Effekt)
        "DOTS": 12,  # CH13
        "DRAW_A": 13,  # CH14
        "DRAW_B": 14,  # CH15
        "TWIST": 15,  # CH16
        "GRATING": 16,  # CH17
        "ON2": 17,  # CH18  (bei dir >0 = „irgendwie an“, aber ohne feine Wirkung)
        "BOUND2": 18,  # CH19
        "RESERVED": 19,  # CH20
        "PAT": 20,  # CH21  **KORREKT: Pattern-Auswahl**
        "ZOOM_FINE": 21,  # CH22  **bestätigt**: 0..127 statisch; 127 ≈ Punkt
        "ROT_FINE": 22,  # CH23  **bestätigt**: 0..127 statisch; >127 dynamisch
        "XMV_FINE": 23,  # CH24  **bestätigt**: 32..95 ≈ links→rechts
        "YMV_FINE": 24,  # CH25  **bestätigt**: 32..95 ≈ unten→oben
        "XZM_FINE": 25,  # CH26
        "YZM_FINE": 26,  # CH27
        "COL_FIX2": 27,  # CH28
        "COL_MODE2": 28,  # CH29  **Wahrscheinlich deine Farb-Engine** (testen)
        "DOTS2": 29,  # CH30
        "DRAW_ASSIST": 30,  # CH31
        "DRAW_CD": 31,  # CH32
        "TWIST2": 32,  # CH33
        "GRATING2": 33,  # CH34
    }

    def __init__(
            self,
            universe: DMXUniverse,
            base_addr: int = 30,
            name: str = "laser",
            fps: float = 30.0,
            # Important: do NOT default into the AUTO band here
            ch1_mode: int = 0,  # safe manual/off band for clones
            ch18_mode: Optional[int] = 0,  # mirror for safety; None to skip
    ):
        self.universe = universe
        self.base = base_addr
        self.name = name
        self.fps = max(5.0, float(fps))

        # Internal frame (34 channels)
        self._frame: List[int] = [0] * 34
        self._lock = threading.Lock()

        # ---- Phase 1: pre-prime blackout BEFORE any worker starts ----
        # Push an all-zero frame so the fixture never sees an AUTO-ish CH1 first.
        # Some firmwares briefly show "WELCOME" until first valid DMX; this kills it.
        self.universe.write_region(self.base, [0] * 34)
        time.sleep(0.10)  # ~3 frames at 30 Hz, let the node transmit

        # ---- Phase 2: pre-arm manual hold (still no worker) ----
        # Program a safe manual/off state directly into the internal buffer
        # and push it once, so the device latches manual control.
        with self._lock:
            self._frame[self.CH["ON1"]] = int(ch1_mode)  # 255 keeps AUTO off
            if ch18_mode is not None:
                self._frame[self.CH["ON2"]] = int(ch18_mode)
        # Push once before starting the worker
        self.universe.write_region(self.base, list(self._frame))
        time.sleep(0.05)

        # ---- Phase 3: start worker AFTER we established manual state ----
        self._running = True
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    # ---------- Core I/O ----------

    def _apply(self) -> None:
        """Push the whole 34-channel frame to DMX."""
        with self._lock:
            vals = list(self._frame)
        self.universe.write_region(self.base, vals)

    def _worker(self) -> None:
        """Send frames at a steady rate; lasers expect stable holding values."""
        tick = 1.0 / self.fps
        while self._running:
            start = time.monotonic()
            self._apply()
            time.sleep(max(0.0, tick - (time.monotonic() - start)))

    def stop(self) -> None:
        """Stop thread (call on exit). Ensures full blackout before shutdown."""
        # 1. Force blackout frame first
        with self._lock:
            self._frame[self.CH["ON1"]] = 0
            self._frame[self.CH["ON2"]] = 0
        self._apply()  # push immediately
        time.sleep(0.1)  # 100 ms to ensure DMX node transmits it

        # 2. Stop worker
        self._running = False
        self._thread.join(timeout=1.0)

        # 3. Final safety blackout (one more frame, just in case)
        with self._lock:
            self._frame = [0] * 34
        self._apply()
        time.sleep(0.05)

    # ---------- Safety / power ----------

    def enable(self, ch1_mode: Optional[int] = None, ch18_mode: Optional[int] = None, delay_s: float = 0.5) -> None:
        """
        Put the laser into a DMX-controlled *on* state (no auto/sound),
        optionally delayed (default 0.5 s) to avoid the startup 'WELCOME' flash.
        """

        def _delayed_enable():
            time.sleep(delay_s)
            with self._lock:
                if ch1_mode is not None:
                    self._frame[self.CH["ON1"]] = int(ch1_mode)
                if ch18_mode is not None:
                    self._frame[self.CH["ON2"]] = int(ch18_mode)
            self._apply()  # push after delay

        # Start tiny background thread so the call returns immediately
        threading.Thread(target=_delayed_enable, daemon=True).start()

    def blackout(self) -> None:
        """
        Make the output dark without changing pattern selections.
        Many firmwares guarantee OFF for CH1 in [250..255] (or exactly 255).
        """
        with self._lock:
            self._frame[self.CH["ON1"]] = 0  # common OFF on clones
            # optionally also kill secondary engine
            self._frame[self.CH["ON2"]] = 0

    # ---------- Pattern / group ----------

    def select_group(self, group_value: int) -> None:
        """Select program group (firmware-defined bands, often 0..223 / 244..255)."""
        gv = max(0, min(255, int(group_value)))
        with self._lock:
            self._frame[self.CH["GROUP"]] = gv

    def select_pattern(self, pattern_index: int, bank: Literal["main", "alt"] = "main") -> None:
        """
        Choose a specific pattern index (0..255).
        For some firmwares, CH21 is a second pattern bank.
        """
        pv = max(0, min(255, int(pattern_index)))
        ch = self.CH["PAT"] if bank == "main" else self.CH["PAT2"]
        with self._lock:
            self._frame[ch] = pv

    # ---------- Color control ----------

    def set_color(self, name: str, speed: float = 0.0) -> None:
        """
        Set or animate color using CH29 (COL_MODE2).
        name: fixed color ('red','yellow','green','cyan','blue','pink','white')
              or animation ('rgb','ycp','rgbycpw','7color','sine','cosine')
        speed: 0..1 → lower = slower (for animated bands)
        """
        # --- Color bands mapping (start, width) ---
        bands = {
            # fixed colors (8-step bands)
            "red": (8, 7),
            "yellow": (16, 7),
            "green": (24, 7),
            "cyan": (32, 7),
            "blue": (40, 7),
            "pink": (48, 7),
            "white": (56, 7),
            # animated / dynamic bands (32-step ranges)
            "rgb": (64, 31),
            "ycp": (96, 31),
            "rgbycpw": (128, 31),
            "7color": (160, 31),
            "sine": (192, 31),
            "cosine": (224, 31),
        }

        if name not in bands:
            raise ValueError(f"Unknown color name '{name}'")

        start, span = bands[name]
        # Clamp speed 0..1; translate into offset within the band
        offset = int(round(max(0.0, min(1.0, speed)) * span))
        value = start + offset

        with self._lock:
            self._frame[self.CH["COL_MODE2"]] = value
        self._apply()

    # ---------- Geometry / motion ----------

    def set_zoom(self, coarse: int = 0, fine: int = 0) -> None:
        """Zoom in/out bands; pairs CH5/CH22 (coarse/fine)."""
        with self._lock:
            self._frame[self.CH["ZOOM"]] = max(0, min(255, int(coarse)))
            self._frame[self.CH["ZOOM_FINE"]] = max(0, min(255, int(fine)))

    def set_rotation(self, coarse: int = 0, fine: int = 0) -> None:
        """Rotation bands; pairs CH6/CH23. Keep modest speeds for scan safety."""
        with self._lock:
            self._frame[self.CH["ROT"]] = max(0, min(255, int(coarse)))
            self._frame[self.CH["ROT_FINE"]] = max(0, min(255, int(fine)))

    def set_motion(self, x_move: int = 0, y_move: int = 0, x_fine: int = 0, y_fine: int = 0) -> None:
        """X/Y moving bands; pairs CH7/CH24 and CH8/CH25."""
        with self._lock:
            self._frame[self.CH["XMV"]] = max(0, min(255, int(x_move)))
            self._frame[self.CH["YMV"]] = max(0, min(255, int(y_move)))
            self._frame[self.CH["XMV_FINE"]] = max(0, min(255, int(x_fine)))
            self._frame[self.CH["YMV_FINE"]] = max(0, min(255, int(y_fine)))

    def set_axis_zoom(self, x_zoom: int = 0, y_zoom: int = 0, x_fine: int = 0, y_fine: int = 0) -> None:
        """X/Y zoom (distortion) bands; pairs CH9/CH26 and CH10/CH27."""
        with self._lock:
            self._frame[self.CH["XZM"]] = max(0, min(255, int(x_zoom)))
            self._frame[self.CH["YZM"]] = max(0, min(255, int(y_zoom)))
            self._frame[self.CH["XZM_FINE"]] = max(0, min(255, int(x_fine)))
            self._frame[self.CH["YZM_FINE"]] = max(0, min(255, int(y_fine)))

    # ---------- Grating / dots / twist / draw ----------

    def set_grating(self, index: int, fine_index: Optional[int] = None) -> None:
        """Pick grating (CH17) and optionally fine (CH34)."""
        with self._lock:
            self._frame[self.CH["GRATING"]] = max(0, min(255, int(index)))
            if fine_index is not None:
                self._frame[self.CH["GRATING2"]] = max(0, min(255, int(fine_index)))

    def set_dots(self, v: int, second: bool = False) -> None:
        """Dots / line blanking selection (CH13, optionally CH30)."""
        ch = self.CH["DOTS2"] if second else self.CH["DOTS"]
        with self._lock:
            self._frame[ch] = max(0, min(255, int(v)))

    def set_twist(self, v: int, second: bool = False) -> None:
        """Twist / warp amount (CH16/CH33)."""
        ch = self.CH["TWIST2"] if second else self.CH["TWIST"]
        with self._lock:
            self._frame[ch] = max(0, min(255, int(v)))

    def set_drawing(self, a: int = 0, b: int = 0, assist: int = 0, cd: int = 0) -> None:
        """Drawing A/B and helpers (CH14/CH15/CH31/CH32)."""
        with self._lock:
            self._frame[self.CH["DRAW_A"]] = max(0, min(255, int(a)))
            self._frame[self.CH["DRAW_B"]] = max(0, min(255, int(b)))
            self._frame[self.CH["DRAW_ASSIST"]] = max(0, min(255, int(assist)))
            self._frame[self.CH["DRAW_CD"]] = max(0, min(255, int(cd)))

    # ---------- Bounds / size (safety-like trims, firmware-dependent) ----------

    def set_bounds(self, v1: int = 0, v2: int = 0) -> None:
        """Out-of-bounds / size bands (CH2 + CH19); exact semantics vary by firmware."""
        with self._lock:
            self._frame[self.CH["BOUND"]] = max(0, min(255, int(v1)))
            self._frame[self.CH["BOUND2"]] = max(0, min(255, int(v2)))

    # ---------- Motion automation helpers ----------
    def animate_y(self, mode: str = "up", speed: float = 0.5) -> None:
        """
        Engage built-in Y-axis auto movement (CH25).
        mode ∈ {"up", "down", "sinus_right", "sinus_left", "manual"}
        speed ∈ [0..1] → 0=langsam, 1=schnell.
        """
        spd = max(0.0, min(1.0, speed))
        with self._lock:
            if mode == "manual":
                # restore manual/static control zone
                self._frame[self.CH["YMV_FINE"]] = 64
            elif mode == "down":
                # 192..223 (downward scan)
                self._frame[self.CH["YMV_FINE"]] = int(192 + spd * 31)
            elif mode == "up":
                # 224..255 (upward scan)
                self._frame[self.CH["YMV_FINE"]] = int(224 + spd * 31)
            elif mode == "sinus_right":
                # 128..159 (wave right)
                self._frame[self.CH["YMV_FINE"]] = int(128 + spd * 31)
            elif mode == "sinus_left":
                # 160..191 (wave left)
                self._frame[self.CH["YMV_FINE"]] = int(160 + spd * 31)
            else:
                raise ValueError(f"Unknown Y animation mode: {mode}")

    # ---------- Legacy star chase ----------
    def clear_frame(self) -> None:
        """Set all 34 channels to 0 in the internal frame."""
        with self._lock:
            self._frame = [0]*34

    def enable_auto(self) -> None:
        """Put CH1 (and optionally CH18) into the 'AUTO' zone like legacy MTL3."""
        with self._lock:
            self._frame[self.CH["ON1"]] = 1   # AUTO range (1..99)
            # Some firmwares like ON2 mirrored; keep safe but not required
            # self._frame[self.CH["ON2"]] = 1

    def enable_manual(self) -> None:
        """Hard 'manual/kill-auto' state (no auto/sound)."""
        with self._lock:
            self._frame[self.CH["ON1"]] = 255
            self._frame[self.CH["ON2"]] = 255

    def _delayed_set_ch1(self, value: int, delay_s: float) -> None:
        """Set CH1 after a delay without blocking the caller."""

        def _go():
            time.sleep(delay_s)
            with self._lock:
                self._frame[self.CH["ON1"]] = int(value)
            self._apply()  # push after delay

        threading.Thread(target=_go, daemon=True).start()

    def apply_raw_legacy_star_chase(self) -> None:
        """
        Reproduce old MTL3 Star Chase without 'WELCOME' by:
        1) programming all channels with CH1 held at 0,
        2) sending a short frame-burst (CH1=0),
        3) arming CH1=1 a bit later (non-blocking).
        """
        # 1) Build frame with CH1=0 and everything else ready
        with self._lock:
            f = [0] * 34
            f[self.CH["ON1"]] = 0  # keep output logically off
            f[self.CH["GROUP"]] = 255  # Group 0 (manual cluster)
            f[3] = 78  # CH4 legacy quirk (leave as-is)
            f[5] = 128  # CH6 rotation coarse legacy
            f[6] = 178  # CH7 X move → auto wave zone
            f[11] = 36  # CH12 color band (~cyan/white-ish)
            self._frame = f

        # 2) Burst a few frames with CH1=0 so fixture latches the preset state
        #    (no welcome, because output is still dark)
        for _ in range(4):  # ~4 frames ≈ 130 ms @30 Hz
            self._apply()
            time.sleep(0.03)

        # 3) Arm CH1=1 slightly later (non-blocking) so when it turns on,
        #    group/pattern/pos/color are already stable on the line
        self._delayed_set_ch1(1, delay_s=0.18)