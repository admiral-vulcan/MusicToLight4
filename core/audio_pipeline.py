# core/audio_pipeline.py
# Minimal, headless audio capture for v4 (no GUI/HDMI, no heavy analysis)
from __future__ import annotations
from dataclasses import dataclass
from collections import deque
from typing import Callable, Deque, List, Optional, Tuple
import time
import threading
import numpy as np

try:
    import sounddevice as sd
    from sounddevice import PortAudioError
except Exception as e:
    sd = None
    PortAudioError = Exception

@dataclass(frozen=True)
class AudioFrame:
    ts: float                # monotonic timestamp
    rms_left: float          # 0..1 (approx, not calibrated)
    rms_right: float         # 0..1 (approx, not calibrated)
    buffer_l: np.ndarray     # last block (left)
    buffer_r: np.ndarray     # last block (right)

Subscriber = Callable[[AudioFrame], None]

class AudioPipeline:
    """
    Headless, thread-safe audio input.
    - Double-buffered, callback-driven.
    - Emits simple RMS only (no FFT).
    - No GUI/HDMI dependencies.
    """

    def __init__(
        self,
        samplerate: int = 44100,
        blocksize: int = 1024,
        channels: int = 2,
        device: Optional[int | str] = None,
        history_blocks: int = 8,
    ):
        if channels not in (1, 2):
            raise ValueError("AudioPipeline supports 1 or 2 channels only.")

        self.samplerate = samplerate
        self.blocksize = blocksize
        self.channels = channels
        self.device = device

        # Rolling history of raw blocks (left/right)
        self._hist_l: Deque[np.ndarray] = deque(maxlen=history_blocks)
        self._hist_r: Deque[np.ndarray] = deque(maxlen=history_blocks if channels == 2 else 0)

        # Subscribers receive AudioFrame
        self._subs: List[Subscriber] = []

        self._stream: Optional[sd.InputStream] = None
        self._run_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_err: Optional[str] = None

        # Latest levels (atomic-ish; Python GIL, set/get only)
        self._rms_left: float = 0.0
        self._rms_right: float = 0.0

    # ---------- Public API ----------

    def start(self) -> None:
        if sd is None:
            raise RuntimeError("sounddevice is not available in this environment.")
        if self._thread and self._thread.is_alive():
            return
        self._run_event.set()
        self._thread = threading.Thread(target=self._run, name="AudioPipeline", daemon=True)
        self._thread.start()

    def stop(self, join: bool = True) -> None:
        self._run_event.clear()
        if join and self._thread:
            self._thread.join(timeout=2.0)

    def subscribe(self, fn: Subscriber) -> None:
        self._subs.append(fn)

    def levels(self) -> Tuple[float, float]:
        """Latest RMS (left, right)."""
        return self._rms_left, self._rms_right

    def history(self) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """Concatenate rolling history (left, right?)."""
        l = np.concatenate(list(self._hist_l)) if self._hist_l else np.empty((0,), dtype=float)
        if self.channels == 2:
            r = np.concatenate(list(self._hist_r)) if self._hist_r else np.empty((0,), dtype=float)
            return l, r
        return l, None

    def last_error(self) -> Optional[str]:
        return self._last_err

    # ---------- Internal ----------

    def _run(self) -> None:
        try:
            with sd.InputStream(
                device=self.device,
                channels=self.channels,
                samplerate=self.samplerate,
                blocksize=self.blocksize,
                callback=self._sd_callback,
            ):
                while self._run_event.is_set():
                    time.sleep(0.01)
        except PortAudioError as e:
            self._last_err = f"Audio device error: {e}"
            self._run_event.clear()
        except Exception as e:
            self._last_err = f"Audio thread failed: {e}"
            self._run_event.clear()

    def _sd_callback(self, indata, frames, time_info, status):
        # Shape: (blocksize, channels)
        if self.channels == 1:
            l = indata[:, 0].astype(np.float32, copy=False)
            r = np.zeros_like(l)
        else:
            # keep left/right as-is (no flip)
            l = indata[:, 0].astype(np.float32, copy=False)
            r = indata[:, 1].astype(np.float32, copy=False)

        # Update rolling buffers
        self._hist_l.append(l.copy())
        if self.channels == 2:
            self._hist_r.append(r.copy())

        # Simple RMS
        self._rms_left = float(np.sqrt(np.mean(l * l)) if l.size else 0.0)
        self._rms_right = float(np.sqrt(np.mean(r * r)) if r.size else 0.0)

        frame = AudioFrame(
            ts=time.monotonic(),
            rms_left=self._rms_left,
            rms_right=self._rms_right,
            buffer_l=l.copy(),
            buffer_r=r.copy(),
        )

        # Fan-out to subscribers (no heavy work here)
        for fn in self._subs:
            try:
                fn(frame)
            except Exception:
                # Keep audio flowing; logging is handled by caller
                pass
