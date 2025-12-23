import time, math
from devices.remote.dmx_gateway import DMXUniverse
from devices.local.laser_point_fine import Laser34FinePoint

u = DMXUniverse(host="192.168.1.151", port=9090, universe=0, fps=30)
laser = Laser34FinePoint(u, base_addr=30)

print("→ Fine-point mode initialized (Group 250, white point)")

try:
    # kleiner Kreis
    fps = 120
    for i in range(int(fps*6)):
        t = i / fps
        x = math.cos(t) * 0.7
        y = math.sin(t) * 0.7
        laser.set_point(x, y)
        time.sleep(1.0/fps)

finally:
    laser.blackout()
    time.sleep(0.5)
    laser.stop()
    u.stop()
    print("✅ fine-point demo done.")
