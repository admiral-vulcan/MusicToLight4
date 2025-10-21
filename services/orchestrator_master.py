# services/orchestrator_master.py
# Minimal orchestrator: subscribes to audio, updates AudioState, and (optionally) logs.
from __future__ import annotations
import time
from core.audio_pipeline import AudioPipeline, AudioFrame
from core.state.audio_state import AudioState

class OrchestratorMaster:
    def __init__(self, samplerate=44100, blocksize=1024, channels=2, device=None, log_every=0.25):
        self.audio = AudioPipeline(samplerate=samplerate, blocksize=blocksize, channels=channels, device=device)
        self.state = AudioState()
        self._last_log = 0.0
        self._log_every = float(log_every)

    def start(self):
        self.audio.subscribe(self._on_audio_frame)
        self.audio.start()

    def stop(self):
        self.audio.stop()

    # Subscriber callback
    def _on_audio_frame(self, frame: AudioFrame):
        self.state.update(frame.rms_left, frame.rms_right)
        now = frame.ts
        if now - self._last_log >= self._log_every:
            self._last_log = now
            l, r = self.state.rms_left, self.state.rms_right
            print(f"[AUDIO] RMS L={l:.3f} R={r:.3f}")

    def run(self):
        try:
            self.start()
            while True:
                time.sleep(0.2)  # idle; future: route to devices based on simple thresholds
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()
