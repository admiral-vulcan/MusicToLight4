# core/state/audio_state.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Deque
from collections import deque

@dataclass
class AudioState:
    """Lightweight snapshot cache; not a bus. Updated by orchestrator/subscriber."""
    rms_left: float = 0.0
    rms_right: float = 0.0
    # Optional short history to allow basic smoothing later (no FFT here)
    rms_hist_left: Deque[float] = field(default_factory=lambda: deque(maxlen=32))
    rms_hist_right: Deque[float] = field(default_factory=lambda: deque(maxlen=32))

    def update(self, l: float, r: float) -> None:
        self.rms_left = l
        self.rms_right = r
        self.rms_hist_left.append(l)
        self.rms_hist_right.append(r)
