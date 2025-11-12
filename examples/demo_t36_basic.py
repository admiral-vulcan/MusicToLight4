"""
examples/demo_t36_basic.py

Demonstrates controlling an EUROLITE LED T-36 RGB Spot with the threaded
EuroliteT36 class. This script focuses on practical, production-style usage:
- color changes (instant + timed fades)
- dimmer ramps
- strobe on/off
- blackout and graceful shutdown

It is safe to run in parallel with the scanner demo because the T-36 occupies
its own DMX address block (default base addr 24 → channels 24..28), while the
scanners use channels 1..12. The DMXUniverse merges these regions on send.
"""

import time
from devices.remote.dmx_gateway import DMXUniverse
from devices.local.eurolite_t36 import EuroliteT36


def main():
    # --------------------------------------------------------------------
    # 1) Universe setup
    # --------------------------------------------------------------------
    # Connect to the DMX gateway on the DMX Pi (musictolight-dmx).
    # Universe 0 at 30 FPS matches our other fixtures and keeps timing simple.
    u = DMXUniverse(host="192.168.1.151", port=9090, universe=0, fps=30)

    # The T-36 uses 5 DMX channels starting at base address 24.
    # This does not overlap with the scanners (1..12), so concurrency is safe.
    t36 = EuroliteT36(u, base_addr=24, name="t36")

    try:
        # ----------------------------------------------------------------
        # 2) Basic color: instant jumps
        # ----------------------------------------------------------------
        print("→ Step 1: Instant color changes (auto-dimmer on non-black)")
        t36.set_color((255, 0, 0), duration=0.0)   # Red
        time.sleep(1.0)
        t36.set_color((0, 255, 0), duration=0.0)   # Green
        time.sleep(1.0)
        t36.set_color((0, 0, 255), duration=0.0)   # Blue
        time.sleep(1.0)

        # ----------------------------------------------------------------
        # 3) Smooth fades between colors
        # ----------------------------------------------------------------
        print("→ Step 2: Timed color fades")
        t36.set_color((255, 0, 255), duration=2.0)  # Magenta fade-in
        time.sleep(2.2)
        t36.set_color((0, 255, 255), duration=2.0)  # Cyan fade-in
        time.sleep(2.2)
        t36.set_color((255, 255, 0), duration=2.0)  # Yellow fade-in
        time.sleep(2.2)

        # ----------------------------------------------------------------
        # 4) Dimmer ramp (keeps current color)
        # ----------------------------------------------------------------
        print("→ Step 3: Dimmer ramp up/down")
        t36.set_dimmer(255, duration=1.5)  # Full brightness
        time.sleep(1.6)
        t36.set_dimmer(40, duration=1.5)   # Low level
        time.sleep(1.6)
        t36.set_dimmer(180, duration=1.5)  # Medium-high
        time.sleep(1.6)

        # ----------------------------------------------------------------
        # 5) Strobe test (rate changes are latched, no interpolation)
        # ----------------------------------------------------------------
        print("→ Step 4: Strobe on/off")
        t36.set_strobe(180)   # Fast strobe
        time.sleep(1.5)
        t36.set_strobe(60)    # Slower strobe
        time.sleep(1.5)
        t36.set_strobe(0)     # Strobe off
        time.sleep(0.8)

        # ----------------------------------------------------------------
        # 6) Combined: color fade while dimmer fades (cross-fade look)
        # ----------------------------------------------------------------
        print("→ Step 5: Cross-fade (color + dimmer)")
        t36.set_color((0, 128, 255), duration=2.5)  # cool blue
        t36.set_dimmer(255, duration=2.5)           # brighten up
        time.sleep(2.7)
        t36.set_color((255, 64, 0), duration=2.0)   # warm amber
        t36.set_dimmer(80, duration=2.0)            # fade down
        time.sleep(2.2)

        # ----------------------------------------------------------------
        # 7) Flash and blackout
        # ----------------------------------------------------------------
        print("→ Step 6: Quick flash and blackout")
        t36.set_color((255, 255, 255), duration=0.0)  # instant white
        t36.set_dimmer(255, duration=0.0)
        time.sleep(0.35)
        t36.blackout()
        time.sleep(0.8)

        print("✅ T-36 demo sequence complete.")

    finally:
        # Clean shutdown so the worker thread stops and the universe closes.
        t36.stop()
        u.stop()


if __name__ == "__main__":
    main()
