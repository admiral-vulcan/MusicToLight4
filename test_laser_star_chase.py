# Runner-Beispiel
from devices.remote.dmx_gateway import DMXUniverse
from devices.local.laser import Laser34
from services.presets.laser_star_chase import laser_star_chase_legacy
import time

u = DMXUniverse(host="192.168.1.151", port=9090, universe=0, fps=30)
laser = Laser34(u, base_addr=30)

# A) 1:1 alt
time.sleep(1)
laser_star_chase_legacy(laser)
time.sleep(5)

laser.blackout()
time.sleep(1)
laser.stop()
u.stop()
