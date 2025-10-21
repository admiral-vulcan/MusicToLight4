# MusicToLight v4 Architecture Overview

## 1. System Overview

MusicToLight v4 is a distributed audio‑reactive visual system designed to translate real‑time music features into synchronized light, video, and DMX outputs. The system runs across multiple devices in a local network:

| Device         | Hostname / IP                    | Role                                                                                |
| -------------- | -------------------------------- | ----------------------------------------------------------------------------------- |
| Raspberry Pi 1 | musictolight / 192.168.1.150     | **Master Node**: audio analysis, orchestration, GUI, HDMI output, UDP/HTTP dispatch |
| Raspberry Pi 2 | musictolight‑dmx / 192.168.1.151 | **DMX Node**: controls OLA‑based DMX devices via FT232 USB–DMX interface            |
| Arduino 1      | 192.168.1.152                    | **Fog controller + mirrored 30‑LED strip near projector**                           |
| Arduino 2      | 192.168.1.153                    | **Main LED strip (270 logical LEDs, dual segment above screen)**                    |
| Arduino 3      | 192.168.1.154                    | **12×25 LED matrix (spectrum analyzer)**                                            |

All Arduino nodes communicate via **UDP port 4210**, receiving binary payloads prefixed with `mls_`.

---

## 2. Core Design Principles

* **Separation of Concerns**: Audio, device control, and GUI logic are fully modular.
* **Distributed Control**: Master node computes cues, slaves execute them via UDP/HTTP.
* **Real‑time Responsiveness**: Thread‑safe and latency‑optimized communication pipelines.
* **Device Independence**: All hardware is abstracted through unified device interfaces.

---

## 3. Directory Structure

```
/
├── app.py                   # Entry point, launches orchestrator and main loop
├── config.py                # All device/network/audio configuration values
├── bootstrap.py             # Initializes environment (SDL, HDMI, role detection)
│
├── core/
│   ├── audio_pipeline.py    # Real‑time audio capture and FFT analysis
│   ├── cue_engine.py        # Maps analyzed audio & GUI states to output cues
│   └── state/
│       ├── global_state.py  # Global runtime state (modes: panic, chill, strobe)
│       ├── audio_state.py   # Current beat/BPM/spectral features
│       └── device_state.py  # Per‑device DMX or LED state buffers
│
├── devices/
│   ├── base_dmx_device.py   # Abstract DMX device class with address/channel logic
│   ├── local/
│   │   ├── eurolite_t36.py  # EUROLITE LED T‑36 RGB Spot (5 ch)
│   │   ├── laser_scanner.py # Moving mirror/laser control logic
│   │   ├── led_strip.py     # LED strip (UDP)
│   │   └── spectrum_analyzer.py # LED matrix visualizer
│   └── remote/
│       ├── dmx_gateway.py   # Sends DMX data to musictolight‑dmx via HTTP
│       ├── arduino_strip.py # Handles main LED strip
│       ├── arduino_fog.py   # Handles fog machine + projector strip
│       └── arduino_matrix.py# Handles spectrum analyzer matrix
│
├── outputs/
│   ├── hdmi_display.py      # Renders Pygame visual matrix & glitch effects
│   ├── video_player.py      # Plays background videos on HDMI display
│   └── render_manager.py    # Coordinates display & video playback
│
├── transport/
│   ├── gui_bridge.py        # Connects to the Flask/Redis GUI for live control
│   ├── redis_bridge.py      # Shared key‑value state sync between GUI and core
│   ├── udp_client.py        # Thread‑safe UDP sender for Arduino devices
│   └── http_client.py       # HTTP POST client for DMX Pi communication
│
├── services/
│   ├── orchestrator_master.py   # Central event loop: combines audio + GUI + device cues
│   ├── orchestrator_slave_dmx.py# Secondary node: receives cues, writes to OLA
│   ├── safety.py                # Safe‑state transitions (panic/off)
│   └── presets/
│       ├── dmx_presets.py       # DMX scenes (laser fade, scanner sweep)
│       ├── led_presets.py       # LED color transitions
│       └── video_presets.py     # Video/HDMI animation sequences
│
├── utils/
│   ├── logging.py           # Unified log formatting and colored output
│   ├── math_helpers.py      # Value mapping, normalization, clamping
│   └── timing.py            # Beat‑aligned timers and async‑safe delays
│
└── vids/                    # Local video library for HDMI playback
```

---

## 4. Data Flow Overview

```
Audio Input → Audio Pipeline → Cue Engine → Orchestrator
                              │
                              ├──> DMX Gateway → OLA → Eurolite T‑36 Spot / Scanners / Laser
                              ├──> UDP Client  → Arduinos (LEDs, Fog, Matrix)
                              └──> HDMI Output → Render Manager / Video Player
```

### Event Flow

1. **Audio pipeline** analyzes spectrum, peaks, and beat timing.
2. **Cue engine** generates lighting/video cues based on audio and GUI modes.
3. **Orchestrator** merges cues, applies presets, and dispatches updates.
4. **Remote devices** execute updates via UDP/HTTP.
5. **State model** tracks the last known DMX and LED states to minimize redundancy.

---

## 5. Device Mapping Summary

| Device             | Channels | Address Range | Function                       |
| ------------------ | -------- | ------------- | ------------------------------ |
| Scanner #1         | 6        | 1–6           | Pan/Tilt, Color, Gobo, Shutter |
| Scanner #2         | 6        | 7–12          | Pan/Tilt, Color, Gobo, Shutter |
| EUROLITE T‑36 Spot | 5        | 24–28         | RGB + Dimmer + Strobe          |
| Laser Show         | 15       | 30–44         | Pattern, Rotation, Color, Zoom |

---

## 6. Deployment Roles

Each node runs a subset of the codebase:

| Role                | Components                                                                     |
| ------------------- | ------------------------------------------------------------------------------ |
| **Master (Pi 1)**   | `app.py`, `core/`, `outputs/`, `transport/`, `services/orchestrator_master.py` |
| **DMX Node (Pi 2)** | `devices/remote/dmx_gateway.py`, `services/orchestrator_slave_dmx.py`          |
| **Arduino Nodes**   | UDP firmware receiving pixel/color/fog commands on port 4210                   |

---

## 7. Future Extensions

* MQTT integration for cloud monitoring.
* Timeline scripting API for deterministic show playback.
* Dynamic device discovery and auto‑addressing.
* Expanded preset engine with cross‑device synchronization.

---

**Revision:** 2025‑10‑21
**Author:** Felix Rau
**License:** GPL‑3.0
