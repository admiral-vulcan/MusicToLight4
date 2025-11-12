# devices/local/laser_point_fine.py
from devices.local.laser import Laser34

class Laser34FinePoint(Laser34):
    """Optimized for units where point control is on CH22–CH25 (fine geometry)."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        # Override default safe startup
        self.enable(ch1_mode=255, ch18_mode=255)
        self.select_group(250)
        self.select_pattern(0)
        self.set_zoom(fine=127)  # smallest possible dot

    def set_point(self, x: float, y: float) -> None:
        """Directly move beam using CH24/CH25 (fine X/Y)."""
        x = max(-1.0, min(1.0, x))
        y = max(-1.0, min(1.0, y))
        # map -1..+1 → 32..95  (your discovered usable range)
        def m(v): return int(round(64 + v * 31))
        xv, yv = m(x), m(y)
        with self._lock:
            self._frame[self.CH["XMV_FINE"]] = xv
            self._frame[self.CH["YMV_FINE"]] = yv

    def set_size(self, v: float) -> None:
        """Set zoom fine (CH22) for point size 0..1."""
        vv = int(round(127 * max(0.0, min(1.0, v))))
        with self._lock:
            self._frame[self.CH["ZOOM_FINE"]] = vv
