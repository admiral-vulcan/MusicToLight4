# devices/remote/arduino_strip_beamer.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from .udp_gateway import UdpEndpoint, UdpGateway

RGB = Tuple[int, int, int]


def _clamp_u8(x: int) -> int:
    # Clamp to 0..255 to avoid breaking the Arduino parser with invalid values.
    return 0 if x < 0 else 255 if x > 255 else int(x)


@dataclass
class ArduinoStripBeamer:
    """
    Beamer LED strip driver (string protocol, identical to MusicToLight3).

    Protocol examples (must stay exactly like this):
      - Panic white:  "led_45_255_255_255_255_255_255_255"
      - Off:          "led_0_0_0_0_0_0_0_0"
      - Normal:       "led_<count>_<intensity>_<sr>_<sg>_<sb>_<er>_<eg>_<eb>"
    """

    ip: str = "192.168.1.152"
    port: int = 4210
    led_count: int = 45

    gateway: Optional[UdpGateway] = None

    def __post_init__(self) -> None:
        self._owns_gateway = self.gateway is None
        if self.gateway is None:
            self.gateway = UdpGateway(async_send=True)
        self._endpoint = UdpEndpoint(self.ip, self.port)

    def close(self) -> None:
        # Close only if we created the gateway ourselves.
        if self._owns_gateway and self.gateway is not None:
            self.gateway.close()

    def off(self) -> bool:
        return self._send_raw("led_0_0_0_0_0_0_0_0")

    def panic_white(self) -> bool:
        c = _clamp_u8(self.led_count)
        return self._send_raw(f"led_{c}_255_255_255_255_255_255_255")

    def set_gradient(
        self,
        start_rgb: RGB,
        end_rgb: RGB,
        intensity: int = 255,
        led_count: Optional[int] = None,
    ) -> bool:
        c = _clamp_u8(self.led_count if led_count is None else led_count)
        i = _clamp_u8(intensity)

        sr, sg, sb = (_clamp_u8(start_rgb[0]), _clamp_u8(start_rgb[1]), _clamp_u8(start_rgb[2]))
        er, eg, eb = (_clamp_u8(end_rgb[0]), _clamp_u8(end_rgb[1]), _clamp_u8(end_rgb[2]))

        msg = f"led_{c}_{i}_{sr}_{sg}_{sb}_{er}_{eg}_{eb}"
        return self._send_raw(msg)

    def _send_raw(self, message: str) -> bool:
        assert self.gateway is not None
        return self.gateway.send(self._endpoint, message)
