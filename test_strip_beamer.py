# test_strip_beamer.py
#
# Simple manual test for the Arduino beamer LED strip.
# Sequence:
# 1. Panic white
# 2. Off
# 3. Random gradients

import random
import time

from devices.remote.udp_gateway import UdpGateway
from devices.remote.arduino_strip_beamer import ArduinoStripBeamer


def random_rgb() -> tuple[int, int, int]:
    # Generate a random RGB color (0..255)
    return (
        random.randint(0, 255),
        random.randint(0, 255),
        random.randint(0, 255),
    )


def main() -> None:
    # One shared gateway, like in the real system
    gateway = UdpGateway(async_send=True)

    strip = ArduinoStripBeamer(
        gateway=gateway,
        # ip and port default to the known Arduino
        # led_count defaults to 30
    )

    try:
        print("Panic white ON")
        strip.panic_white()
        time.sleep(2.0)

        print("OFF")
        strip.off()
        time.sleep(1.0)

        print("Random color gradients")
        for i in range(10):
            start = random_rgb()
            end = random_rgb()
            intensity = random.randint(64, 255)

            print(f"  {i+1}/10  start={start} end={end} intensity={intensity}")
            strip.set_gradient(
                start_rgb=start,
                end_rgb=end,
                intensity=intensity,
            )
            time.sleep(0.7)

    finally:
        # Give async UDP sender a moment to flush
        gateway.flush(timeout=1.0)
        strip.close()
        print("Test finished.")


if __name__ == "__main__":
    main()
