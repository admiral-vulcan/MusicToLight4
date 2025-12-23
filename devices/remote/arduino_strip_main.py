# devices/remote/arduino_strip_main.py
#
# MusicToLight4 – Main LED Strip
# Full logical port of MusicToLight3 UDPNeoPixel + LED effects

from __future__ import annotations

import random
import time
from collections import deque
from dataclasses import dataclass
from typing import List, Tuple, Optional

import numpy as np

from .udp_gateway import UdpEndpoint, UdpGateway

RGB = Tuple[int, int, int]


def _clamp_u8(x: int) -> int:
    return 0 if x < 0 else 255 if x > 255 else int(x)


# ----------------------------------------------------------------------
# Helper math / color functions (ported)
# ----------------------------------------------------------------------

def smooth_transition(current: RGB, target: RGB, step: int = 5) -> RGB:
    r = int(current[0] + min(max(target[0] - current[0], -step), step))
    g = int(current[1] + min(max(target[1] - current[1], -step), step))
    b = int(current[2] + min(max(target[2] - current[2], -step), step))
    return r, g, b


def wheel(pos: int, reduce: int = 2) -> Tuple[int, int]:
    if pos < 128:
        return (pos * 2) // reduce, (255 - pos * 2) // reduce
    pos -= 128
    return (255 - pos * 2) // reduce, (pos * 2) // reduce


def adjust_brightness(color: int, factor: float) -> int:
    return max(0, min(255, int(color * factor)))


def exp_lerp(a: int, b: int, t: float) -> int:
    return int(a + (b - a) * (t * t))


# ----------------------------------------------------------------------
# Main class
# ----------------------------------------------------------------------

@dataclass
class ArduinoStripMain:
    """
    Full-featured main LED strip controller.

    - Binary UDP protocol identical to MusicToLight3
    - Implements all LED-only effects from legacy code
    """

    led_count: int = 270
    ip: str = "192.168.1.153"
    port: int = 4210
    mirror_halves: bool = False
    gateway: Optional[UdpGateway] = None

    def __post_init__(self) -> None:
        self._owns_gateway = self.gateway is None
        if self.gateway is None:
            self.gateway = UdpGateway(async_send=True)

        self.endpoint = UdpEndpoint(self.ip, self.port)

        self.half = self.led_count // 2
        self.pixels: List[RGB] = [(0, 0, 0)] * self.led_count

        # State copied from legacy globals
        self.global_led_state: List[RGB] = [(0, 0, 0)] * self.led_count
        self.current_colors: List[RGB] = [(0, 0, 0)] * self.led_count
        self.recent_audio_inputs = deque(maxlen=3)

    # ------------------------------------------------------------------
    # NeoPixel-like API
    # ------------------------------------------------------------------

    def numPixels(self) -> int:
        return self.led_count

    def setPixelColor(self, i: int, color: RGB | int) -> None:
        if not (0 <= i < self.led_count):
            return

        if isinstance(color, int):
            r = (color >> 16) & 0xFF
            g = (color >> 8) & 0xFF
            b = color & 0xFF
        else:
            r, g, b = color

        self.pixels[i] = (_clamp_u8(r), _clamp_u8(g), _clamp_u8(b))

    def show(self) -> bool:
        payload = bytearray(b"mls_")
        payload.extend(self.led_count.to_bytes(2, "little"))

        if self.mirror_halves:
            for i in range(self.half):
                payload.extend(self.pixels[i])
            for i in reversed(range(self.half)):
                payload.extend(self.pixels[i])
        else:
            for r, g, b in self.pixels:
                payload.extend([r, g, b])

        return self.gateway.send(self.endpoint, payload)

    # ------------------------------------------------------------------
    # Legacy LED helpers
    # ------------------------------------------------------------------

    def led_set_all_pixels_color(self, r: int, g: int, b: int) -> None:
        for i in range(self.led_count):
            self.setPixelColor(i, (r, g, b))
        self.show()

    def clear(self) -> None:
        self.led_set_all_pixels_color(0, 0, 0)

    # ------------------------------------------------------------------
    # Effects (ported)
    # ------------------------------------------------------------------

    def led_star_chase(self, color: RGB, wait_ms: int) -> None:
        num_chases = 30
        for chase in range(num_chases):
            start = int(self.half / num_chases * chase) - random.randint(5, 15)
            stop = int(self.half / num_chases * (chase + 1)) + random.randint(5, 15)
            start = max(0, start)
            stop = min(self.half, stop)

            for offset in range(3):
                pos = start
                while pos < stop:
                    self.setPixelColor(pos + offset, color)
                    pos += random.randint(1, 15)
                self.show()
                time.sleep(wait_ms / 1000)

                for i in range(0, self.half, 3):
                    self.setPixelColor(i + offset, (0, 0, 0))

            self.show()
            for i in range(self.half):
                self.setPixelColor(i, (0, 0, 0))
            self.show()

    def led_music_visualizer(self, data: float, first_rgb: RGB, second_rgb: RGB) -> None:
        brightness_factor = 0.5
        pre_rate = 0.8

        mid = self.half // 2
        data = int(data * mid)

        self.global_led_state = [
            (int(r * pre_rate), int(g * pre_rate), int(b * pre_rate))
            for r, g, b in self.global_led_state
        ]

        for pos in range(data):
            t = pos / mid
            r = adjust_brightness(exp_lerp(first_rgb[0], second_rgb[0], t), brightness_factor)
            g = adjust_brightness(exp_lerp(first_rgb[1], second_rgb[1], t), brightness_factor)
            b = adjust_brightness(exp_lerp(first_rgb[2], second_rgb[2], t), brightness_factor)

            for idx in (
                mid - pos,
                mid + pos,
                self.half + mid - pos,
                self.half + mid + pos,
            ):
                if 0 <= idx < self.led_count:
                    self.setPixelColor(idx, (r, g, b))

        self.show()

    def close(self) -> None:
        if self._owns_gateway:
            self.gateway.close()
