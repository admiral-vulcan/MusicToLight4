# simple demo: switch between Y animation modes
from devices.remote.dmx_gateway import DMXUniverse
from devices.local.laser import Laser34
import time

u = DMXUniverse(host="192.168.1.151", port=9090, universe=0)
laser = Laser34(u, base_addr=30)
laser.enable(ch1_mode=255, ch18_mode=255)
laser.select_group(255)
laser.select_pattern(43)
laser.set_zoom(fine=0)
laser.set_color("blue")
laser.set_motion(0, 0, 0, 64)   # center X/Y


modes = [
    ("up", 0.3),
    ("down", 0.3),
    ("sinus_right", 0.4),
    ("sinus_left", 0.4),
    ("manual", 0)
]

for m, spd in modes:
    print(f"→ animate_y({m}, {spd})")
    laser.animate_y(m, spd)
    time.sleep(4.0)

print("→ stop and blackout")
laser.blackout()
time.sleep(0.5)
laser.stop()
u.stop()
