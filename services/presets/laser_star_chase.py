# services/presets/laser_star_chase.py
# Straight 1:1 port of your old MusicToLight3 "laser_star_chase" preset
# Updated for corrected 34-CH map (base address = 30)
# This keeps the same DMX values as before, just aligned to the new channel order.

from devices.local.laser import Laser34

def laser_star_chase_legacy(laser: Laser34) -> None:
    """Exact MTL3 behavior, pushed by the worker thread."""
    laser.apply_raw_legacy_star_chase()
