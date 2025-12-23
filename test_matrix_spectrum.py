# test_matrix_spectrum.py
#
# Manual test for the Arduino spectrum matrix.
# Sequence:
# 1. OFF
# 2. ALL ON (panic-style)
# 3. SPECTRUM with random values
# 4. SNOWFALL (hold)
# 5. BREATH (hold)
# 6. OFF again

import random
import time

from devices.remote.udp_gateway import UdpGateway
from devices.remote.arduino_strip_matrix_spectrum import ArduinoStripMatrixSpectrum


def random_columns(min_val: int = 0, max_val: int = 25) -> list[int]:
    # 12 spectrum columns, each 0..25 LEDs
    return [random.randint(min_val, max_val) for _ in range(12)]


def main() -> None:
    gateway = UdpGateway(async_send=True)

    matrix = ArduinoStripMatrixSpectrum(
        gateway=gateway,
        # ip defaults to 192.168.1.154
    )

    try:
        print("MODE 0: OFF")
        matrix.off()
        time.sleep(1.5)

        print("MODE 1: ALL ON (panic-style white)")
        matrix.all_on(intensity=255, color_start=7, color_end=7)
        time.sleep(2.0)

        print("MODE 2: SPECTRUM (random data)")
        for i in range(12):
            cols = random_columns()
            intensity = random.randint(80, 180)
            color_start = random.randint(0, 7)
            color_end = random.randint(0, 7)

            print(
                f"  spectrum {i+1}/12 | "
                f"intensity={intensity} "
                f"colors={color_start}->{color_end} "
                f"cols={cols}"
            )

            matrix.spectrum(
                intensity=intensity,
                color_start=color_start,
                color_end=color_end,
                num_leds_list=cols,
            )
            time.sleep(0.4)

        print("MODE 3: SNOWFALL (hold animation)")
        matrix.snowfall(
            intensity=255,
            color_start=7,
            color_end=7,
        )
        time.sleep(4.0)

        print("MODE 4: BREATH (hold animation)")
        matrix.breath(
            intensity=255,
            color_start=7,
            color_end=7,
        )
        time.sleep(4.0)

        print("Back to OFF")
        matrix.off()
        time.sleep(1.0)

    finally:
        # Allow async UDP sender to flush remaining packets
        gateway.flush(timeout=1.0)
        matrix.close()
        print("Matrix spectrum test finished.")


if __name__ == "__main__":
    main()
