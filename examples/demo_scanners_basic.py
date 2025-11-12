"""
examples/demo_scanners_basic.py

Demonstrates how to control two DMX scanners using the threaded ScannerDevice class.

This script performs a full end-to-end exercise:
1. Initializes the DMX universe via OLA.
2. Runs a safe calibration sweep.
3. Tests color-wheel transitions, gobo selection, pan/tilt movement,
   rotation speed, and shutter/strobe effects.

Intended as both a hardware diagnostic and a usage example
for developers integrating the scanner into the MusicToLight orchestrator.
"""

import time
from devices.remote.dmx_gateway import DMXUniverse
from devices.local.scanner import ScannerDevice


def main():
    # --------------------------------------------------------------------
    # 1. Universe setup
    # --------------------------------------------------------------------
    # The DMX gateway lives on the secondary Raspberry Pi ("musictolight-dmx").
    # We connect via HTTP on port 9090, Universe 0.
    u = DMXUniverse(host="192.168.1.151", port=9090, universe=0, fps=30)

    # Two scanners are daisy-chained on Universe 0:
    #   Scanner 1 at base address 1
    #   Scanner 2 at base address 7
    s1 = ScannerDevice(u, base_addr=1, name="scanner1", profile="first")
    s2 = ScannerDevice(u, base_addr=7, name="scanner2", profile="second")

    print("→ Step 1: Full calibration of both scanners")
    # The calibration sweeps all DMX channels to resync internal stepper motors.
    # It runs asynchronously; we wait long enough to ensure both are done.
    s1.calibrate_full_reset()
    s2.calibrate_full_reset()
    time.sleep(7.5)

    # --------------------------------------------------------------------
    # 2. Color wheel stepping
    # --------------------------------------------------------------------
    # Each color change is executed gradually by the color worker.
    # We only set target colors; the class handles timing internally.
    print("→ Step 2: Color wheel test")
    for c in ["red", "yellow", "green", "blue", "pink"]:
        print(f"   Switching to {c}")
        s1.set_color_step(c)
        s2.set_color_step(c)
        # Sleep gives enough time for the wheel to traverse the steps
        time.sleep(6.0)

    # --------------------------------------------------------------------
    # 3. Gobo wheel movement
    # --------------------------------------------------------------------
    # Gobo channels react faster — mechanical but less inertia than the color wheel.
    print("→ Step 3: Gobo pattern cycling")
    for g in [30, 80, 160, 230]:
        print(f"   Gobo value {g}")
        s1.set_gobo(g)
        s2.set_gobo(g)
        time.sleep(1.5)
    time.sleep(3)

    # --------------------------------------------------------------------
    # 4. Pan/Tilt range test
    # --------------------------------------------------------------------
    # Move both scanners across their full mechanical range.
    # They are mirrored intentionally for visual contrast.
    print("→ Step 4: Pan/Tilt motion test")
    for p in [0, 64, 128, 192, 255]:
        print(f"   Moving P={p}")
        s1.move_to_raw(p, 255 - p)
        s2.move_to_raw(255 - p, p)
        time.sleep(2.0)
    time.sleep(3)

    # --------------------------------------------------------------------
    # 5. Rotation speed test
    # --------------------------------------------------------------------
    # Rotation is continuous and maps to positive/negative DMX speed ranges.
    print("→ Step 5: Rotation test")
    for r in [30, 64, 128, 192, 230]:
        print(f"   Rotating speed {r}")
        s1.set_rotation_legacy(r)
        s2.set_rotation_legacy(-r)
        time.sleep(2.0)
    time.sleep(3)

    # --------------------------------------------------------------------
    # 6. Shutter / Strobe / Blackout
    # --------------------------------------------------------------------
    # This verifies the fixture’s dimmer channel and strobe mode.
    print("→ Step 6: Shutter open/close sequence")
    s1.open()
    s2.open()
    time.sleep(1.0)

    print("   Strobe ON")
    s1.strobe(True)
    s2.strobe(True)
    time.sleep(1.0)

    print("   Closing shutter (blackout)")
    s1.close()
    s2.close()
    time.sleep(1.0)

    # --------------------------------------------------------------------
    # 7. Wrap-up
    # --------------------------------------------------------------------
    print("✅ Scanner diagnostic sequence complete.")
    u.stop()


if __name__ == "__main__":
    main()
