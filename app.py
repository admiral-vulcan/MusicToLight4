# app.py
# Lean entrypoint: just run the minimal audio orchestrator.
from services.orchestrator_master import OrchestratorMaster

if __name__ == "__main__":
    orch = OrchestratorMaster(
        samplerate=44100,
        blocksize=1024,
        channels=2,
        device=None,      # optionally set ALSA/PortAudio device index or name
        log_every=0.5,    # print RMS twice per second
    )
    orch.run()
