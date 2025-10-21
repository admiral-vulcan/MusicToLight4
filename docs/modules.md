# MusicToLight v4 – Modules Reference

> This document describes the *software* modules, their responsibilities, inputs/outputs, and key dependencies. Hardware specifics, channel maps, and wiring are intentionally omitted here and covered in `devices.md`.

---

## 1) Top‑Level Runtime

### `app.py`

**Role:** Process entrypoint. Loads configuration, wires dependencies, and starts the correct orchestrator for the current node role (master vs. DMX slave).

* **Inputs:** `config.py`, environment (role), CLI flags (optional).
* **Outputs:** Starts main loop and graceful shutdown.
* **Depends on:** `bootstrap.py`, `services/*`, `core/*`, `transport/*`.

### `bootstrap.py`

**Role:** Early environment setup and capability toggles.

* Sets SDL/X11/HDMI variables, Python path, logging verbosity.
* Detects node role (`MTL_ROLE=master|dmx-slave`) and initializes optional subsystems (display, audio).

### `config.py`

**Role:** Central configuration registry.

* Holds device registry (logical names → driver classes, IPs, DMX start addresses).
* Audio engine settings (sample rate, frame size, hop length).
* Network endpoints (UDP ports, HTTP base URLs), GUI/Redis settings.
* Mode defaults (panic=off, chill=off, strobe=auto).

---

## 2) Core Logic

### `core/audio_pipeline.py`

**Purpose:** Real‑time audio capture and feature extraction.

* **Inputs:** Audio device/stream (ALSA/PyAudio).
* **Processing:** Windowing, FFT/STFT, band‑energy, onset/beat detection.
* **Outputs:** `AudioState` updates (RMS, spectrum, peaks/BPM) to `state/audio_state.py`.
* **Contracts:** Emits immutable snapshots for consumers; provides pull (latest frame) and push (callbacks) APIs.

### `core/cue_engine.py`

**Purpose:** Translates audio + GUI state into device‑agnostic *cues*.

* **Inputs:** `AudioState`, `GlobalState` (modes from GUI), timers from `timeline`.
* **Outputs:** High‑level cue objects (e.g., `ColorCue`, `StrobeCue`, `ScannerMoveCue`, `LaserPatternCue`, `VideoCue`).
* **Notes:** Contains mapping strategies (e.g., bass → pan sweep; highs → strobe), mode gates (panic/chill/strobe), and color selection.

### `core/state/`

* `global_state.py` — single source of truth for modes (panic, chill, strobe, play_videos), current primary/secondary color, last transitions.
* `audio_state.py` — latest spectrum vectors, peak flags, BPM, confidence.
* `device_state.py` — last committed DMX frame/UDP payload per logical device to minimize redundant sends and enable idempotent updates.

### `core/timeline.py`

**Purpose:** Time‑based coordination.

* **Primitives:** Beat‑aligned tickers, throttled triggers, decay envelopes, ease functions.
* **Use‑case:** Drop detectors, glitch windows, scene durations.

---

## 3) Services (Runtime Coordination)

### `services/orchestrator_master.py`

**Role:** Heart of the system on the master node.

* **Loop:** Pull audio + GUI state → query `cue_engine` → resolve conflicts/priorities → dispatch to transports → update `device_state`.
* **Conflict resolution:** Applies mode safety (panic overrides all), merges concurrent cues, rate‑limits DMX/UDP bursts, snaps values to device limits.
* **Outputs:** DMX frames to `remote/dmx_gateway`; UDP payloads to Arduinos; HDMI calls to `outputs/*`.

### `services/orchestrator_slave_dmx.py`

**Role:** Lightweight executor on the DMX node.

* **Inputs:** HTTP POSTs containing DMX updates or batch frames.
* **Action:** Writes to OLA/`olad`, handles local failsafe (blackout on timeout).

### `services/safety.py`

**Role:** Safe states and recovery.

* Global blackout, per‑device blackout, strobe kill switch.
* Watchdogs for comms timeouts (e.g., if no master heartbeat).

### `services/presets/`

* `dmx_presets.py` — scanner sweeps, laser „slow dance“, T‑36 dimmed wash, etc.
* `led_presets.py` — ambient fades, mirrored/split patterns for 270‑strip, beamer 30‑mirror.
* `video_presets.py` — background loop, cut‑to‑black, fade‑in/out sequences.

---

## 4) Device Abstractions (Software)

### `devices/base_dmx_device.py`

**Contract:** Uniform interface for DMX fixtures.

* `set_channel(offset:int, value:int)`
* `set_block(values:list[int])` (contiguous)
* `commit()`
* `blackout()`

### `devices/local/eurolite_t36.py`

* Encodes the EUROLITE LED T‑36 Spot’s 5‑channel map (RGB, dimmer, strobe).
* Produces DMX blocks; sends via `remote/dmx_gateway`.

### `devices/local/laser_scanner.py`

* Scanner control (pan/tilt constrained ranges, color/gobo/shutter/rotation) and laser patterns.
* Exposes intent‑level methods (e.g., `sweep(pan, tilt)`, `set_color(name)`, `strobe(rate)`, `pattern(code, speed)`).

### `devices/local/led_strip.py`

* Logic for 270‑pixel main strip and 30‑pixel mirrored beamer strip (mode‑aware: mirrored vs. independent sections).
* Builds binary UDP payloads compatible with Arduino firmware.

### `devices/local/spectrum_analyzer.py`

* Packs 12×25 matrix frames from spectral data; provides bar/column renderers and falloff.

### `devices/remote/dmx_gateway.py`

* Node‑agnostic DMX sender.
* **API:** `send(universe:int, csv_values:str) → HTTP 200` to DMX node.
* Retries, back‑pressure, and change‑only optimization.

### `devices/remote/arduino_*`

* `arduino_strip.py` — 270‑strip & beamer strip.
* `arduino_matrix.py` — 12×25 spectrum matrix.
* `arduino_fog.py` — fog on/off RF codes; ensures OFF on boot.

---

## 5) Transport Layer

### `transport/gui_bridge.py`

**Role:** Polls GUI/Redis, normalizes commands into `GlobalState` deltas.

* Keys include: `panic_mode`, `strobe_mode`, `chill_mode`, `play_videos_mode`, `st_color_name`, `nd_color_name`, calibration flags.

### `transport/redis_bridge.py`

* Thin wrapper for Redis get/set with type coercion and defaults.

### `transport/udp_client.py`

* Thread‑safe, non‑blocking UDP sender with queueing and burst control.
* Packet header: `mls_` + device id + payload.

### `transport/http_client.py`

* Minimal POST helper with session reuse, timeouts, retries.

---

## 6) Outputs (Visuals)

### `outputs/hdmi_display.py`

* Pygame based renderer (single or dual display). Provides text overlay, glitch layers, and spectrum draws independent of matrix device.

### `outputs/video_player.py`

* Background video playback/playlist, controllable via `VideoCue` and presets.

### `outputs/render_manager.py`

* Orchestrates composition order between HDMI layers and video.

---

## 7) Shared Utilities

### `utils/logging.py`

* Structured, colorized logs with component tags (`[DMX]`, `[UDP]`, `[AUDIO]`, `[GUI]`).

### `utils/math_helpers.py`

* Linear/exponential mappings, clamps, smoothing filters, easing functions.

### `utils/timing.py`

* Beat‑aligned delays, throttlers, monotonic timers, frame pacers.

---

## 8) Data Contracts (Core Types)

### Cue Objects (examples)

* `ColorCue(device, rgb, dimmer=None, strobe=None)`
* `ScannerMoveCue(device, pan, tilt, speed=None)`
* `LaserPatternCue(device, code, color, speed=None)`
* `StripFrameCue(device, frame_bytes)`
* `MatrixFrameCue(device, frame_bytes)`
* `VideoCue(action, clip=None, opacity=None)`

### DMX Frame

* `universe:int`, `values:list[int] (len ≤ 512)`; gateway encodes to CSV string for HTTP POST.

### UDP Payload (to Arduinos)

* `header='mls_'` + `device_id:1B` + `payload:bytes`; device‑specific packing handled in the respective `arduino_*` module.

---

## 9) Lifecycle & Error Handling

* **Startup:** `bootstrap` → `app` → orchestrator; devices created from `config`.
* **Watchdogs:** DMX slave blackouts on master timeout; UDP sender drops or coalesces bursts under back‑pressure.
* **Graceful Shutdown:** Presets invoke global blackout; transports flush queues; HDMI fades to black.

---

## 10) Testing Hooks

* Mock transports (`DummyUDP`, `DummyHTTP`) for offline tests.
* Fixture simulators for DMX and strips; golden‑frame comparisons for matrix.
* Deterministic audio replays (WAV fixtures) to validate cue generation.

---

**Scope Note:** This document focuses on software responsibilities and contracts. For channel maps, IPs, wiring, and power, see `devices.md`. For system layout and data flow, see `architecture.md`.

---

**Revision:** 2025‑10‑21
**Author:** Felix Rau
**License:** GPL‑3.0
