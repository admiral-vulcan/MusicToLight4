# test_strip_main.py
#
# Full test suite for ArduinoStripMain
# Visual, slow, explicit – meant for humans, not CI.

import random
import time
import math

from devices.remote.udp_gateway import UdpGateway
from devices.remote.arduino_strip_main import ArduinoStripMain


def sleep(sec: float):
    time.sleep(sec)


def random_color():
    return (
        random.randint(0, 255),
        random.randint(0, 255),
        random.randint(0, 255),
    )


def main():
    print("=== Main LED Strip Test ===")

    gateway = UdpGateway(async_send=True)

    strip = ArduinoStripMain(
        led_count=270,
        mirror_halves=False,   # switch to True to test mirroring
        gateway=gateway,
    )

    try:
        # ------------------------------------------------------------
        print("\n[1] CLEAR / OFF")
        strip.clear()
        sleep(2)

        # ------------------------------------------------------------
        print("\n[2] FULL COLOR TESTS")
        for color, name in [
            ((255, 0, 0), "RED"),
            ((0, 255, 0), "GREEN"),
            ((0, 0, 255), "BLUE"),
            ((255, 255, 255), "WHITE"),
            ((255, 120, 0), "ORANGE"),
            ((180, 0, 255), "PURPLE"),
        ]:
            print(f"  -> {name}")
            strip.led_set_all_pixels_color(*color)
            sleep(1.2)

        # ------------------------------------------------------------
        print("\n[3] HALF STRIP TEST (visual split)")
        strip.clear()
        half = strip.numPixels() // 2
        for i in range(half):
            strip.setPixelColor(i, (0, 0, 255))
        for i in range(half, strip.numPixels()):
            strip.setPixelColor(i, (255, 0, 0))
        strip.show()
        sleep(2)

        # ------------------------------------------------------------
        print("\n[4] SINGLE PIXEL WALK")
        strip.clear()
        for i in range(strip.numPixels()):
            strip.clear()
            strip.setPixelColor(i, (255, 255, 255))
            strip.show()
            sleep(0.01)

        # ------------------------------------------------------------
        print("\n[5] STAR CHASE EFFECT")
        strip.clear()
        strip.led_star_chase((255, 255, 255), wait_ms=35)
        sleep(1)

        # ------------------------------------------------------------
        print("\n[6] RANDOM COLOR NOISE")
        for _ in range(20):
            for i in range(strip.numPixels()):
                if random.random() < 0.05:
                    strip.setPixelColor(i, random_color())
            strip.show()
            sleep(0.15)

        # ------------------------------------------------------------
        print("\n[7] MUSIC VISUALIZER – FAKE DATA (SINE)")
        strip.clear()
        for step in range(120):
            fake_audio = (math.sin(step / 10) + 1) / 2  # 0..1
            strip.led_music_visualizer(
                data=fake_audio,
                first_rgb=(0, 0, 255),
                second_rgb=(255, 0, 0),
            )
            sleep(0.05)

        # ------------------------------------------------------------
        print("\n[8] MUSIC VISUALIZER – RANDOM PULSES")
        strip.clear()
        for _ in range(40):
            fake_audio = random.random()
            strip.led_music_visualizer(
                data=fake_audio,
                first_rgb=(0, 255, 120),
                second_rgb=(255, 0, 255),
            )
            sleep(0.1)

        # ------------------------------------------------------------
        print("\n[9] FINAL CLEAR")
        strip.clear()
        sleep(1)

    finally:
        gateway.flush(timeout=1.0)
        strip.close()
        print("\n=== TEST FINISHED ===")


if __name__ == "__main__":
    main()
