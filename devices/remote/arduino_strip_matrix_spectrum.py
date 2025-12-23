# devices/remote/arduino_strip_matrix_spectrum.py

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Optional, Sequence

from .udp_gateway import UdpEndpoint, UdpGateway


def _clamp_u8(x: int) -> int:
    # Clamp to 0..255 to keep the Arduino protocol stable.
    return 0 if x < 0 else 255 if x > 255 else int(x)


def _pack_spectrum_message(
    mode: int,
    intensity: int,
    color_start: int,
    color_end: int,
    num_leds_list: Sequence[int],
) -> bytes:
    """
    Exact legacy packet format:
      struct.pack('BBBB12B', mode, intensity, color_start, color_end, *num_leds_list)
    """
    if len(num_leds_list) != 12:
        raise ValueError("num_leds_list must contain exactly 12 values")

    m = _clamp_u8(mode)
    i = _clamp_u8(intensity)
    cs = _clamp_u8(color_start)
    ce = _clamp_u8(color_end)
    cols = [_clamp_u8(v) for v in num_leds_list]

    return struct.pack("BBBB12B", m, i, cs, ce, *cols)


@dataclass
class ArduinoStripMatrixSpectrum:
    """
    Spectrum matrix driver (binary UDP protocol, identical to MusicToLight3).

    Target:
      - Arduino: 192.168.1.154
      - UDP port: 4210

    Modes seen in legacy code:
      0 = all off
      1 = all on (panic-style)
      2 = spectrum analyzer
      3 = snowfall
      4 = breath (legacy comment says "could be")
    """

    ip: str = "192.168.1.154"
    port: int = 4210
    gateway: Optional[UdpGateway] = None

    # Mode constants (purely convenience; the Arduino decides behavior)
    MODE_OFF: int = 0
    MODE_ALL_ON: int = 1
    MODE_SPECTRUM: int = 2
    MODE_SNOWFALL: int = 3
    MODE_BREATH: int = 4

    def __post_init__(self) -> None:
        self._owns_gateway = self.gateway is None
        if self.gateway is None:
            self.gateway = UdpGateway(async_send=True)
        self._endpoint = UdpEndpoint(self.ip, self.port)

    def close(self) -> None:
        # Close only if we created the gateway ourselves.
        if self._owns_gateway and self.gateway is not None:
            self.gateway.close()

    def send(
        self,
        mode: int,
        intensity: int,
        color_start: int,
        color_end: int,
        num_leds_list: Sequence[int],
    ) -> bool:
        """
        Send a raw spectrum message to the Arduino (exact legacy format).
        """
        payload = _pack_spectrum_message(mode, intensity, color_start, color_end, num_leds_list)
        assert self.gateway is not None
        return self.gateway.send(self._endpoint, payload)

    # ---- Convenience wrappers (still generic: you pass the parameters) ----

    def off(self) -> bool:
        # Legacy off example used white channels but ignored in off-mode.
        return self.send(
            mode=self.MODE_OFF,
            intensity=255,
            color_start=7,
            color_end=7,
            num_leds_list=[0] * 12,
        )

    def all_on(
        self,
        intensity: int = 255,
        color_start: int = 7,
        color_end: int = 7,
        num_leds_list: Optional[Sequence[int]] = None,
    ) -> bool:
        # Legacy panic used mode=1 and a zeroed list.
        return self.send(
            mode=self.MODE_ALL_ON,
            intensity=intensity,
            color_start=color_start,
            color_end=color_end,
            num_leds_list=list(num_leds_list) if num_leds_list is not None else [0] * 12,
        )

    def spectrum(
        self,
        intensity: int,
        color_start: int,
        color_end: int,
        num_leds_list: Sequence[int],
    ) -> bool:
        return self.send(
            mode=self.MODE_SPECTRUM,
            intensity=intensity,
            color_start=color_start,
            color_end=color_end,
            num_leds_list=num_leds_list,
        )

    def snowfall(
        self,
        intensity: int = 255,
        color_start: int = 7,
        color_end: int = 7,
        num_leds_list: Optional[Sequence[int]] = None,
    ) -> bool:
        return self.send(
            mode=self.MODE_SNOWFALL,
            intensity=intensity,
            color_start=color_start,
            color_end=color_end,
            num_leds_list=list(num_leds_list) if num_leds_list is not None else [0] * 12,
        )

    def breath(
        self,
        intensity: int = 255,
        color_start: int = 7,
        color_end: int = 7,
        num_leds_list: Optional[Sequence[int]] = None,
    ) -> bool:
        # Mode 4 was marked as "could be breath" in old notes.
        return self.send(
            mode=self.MODE_BREATH,
            intensity=intensity,
            color_start=color_start,
            color_end=color_end,
            num_leds_list=list(num_leds_list) if num_leds_list is not None else [0] * 12,
        )
