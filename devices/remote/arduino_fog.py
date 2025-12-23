# devices/remote/arduino_fog.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .udp_gateway import UdpEndpoint, UdpGateway


@dataclass
class ArduinoFogMachine:
    """
    Fog machine driver (string protocol, identical to MusicToLight3).

    Protocol:
      - On:  "smoke_on"
      - Off: "smoke_off"
    """

    ip: str = "192.168.1.152"
    port: int = 4210
    gateway: Optional[UdpGateway] = None

    def __post_init__(self) -> None:
        self._owns_gateway = self.gateway is None
        if self.gateway is None:
            self.gateway = UdpGateway(async_send=True)
        self._endpoint = UdpEndpoint(self.ip, self.port)

    def close(self) -> None:
        if self._owns_gateway and self.gateway is not None:
            self.gateway.close()

    def on(self) -> bool:
        assert self.gateway is not None
        return self.gateway.send(self._endpoint, "smoke_on")

    def off(self) -> bool:
        assert self.gateway is not None
        return self.gateway.send(self._endpoint, "smoke_off")
