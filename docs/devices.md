# MusicToLight v4 Device Documentation

## 1. Overview

This document provides a detailed description of all hardware devices used in the **MusicToLight v4** ecosystem. It includes DMX fixtures, UDP-driven LED systems, the fog machine, and the physical node specifications for the distributed setup.

---

## 2. System Nodes

| Hostname             | Model                          | IP Address    | Role                                                                       |
| -------------------- | ------------------------------ | ------------- | -------------------------------------------------------------------------- |
| **musictolight**     | Raspberry Pi 4 Model B Rev 1.1 | 192.168.1.150 | Master Node: audio analysis, HDMI output, orchestration, UDP/HTTP dispatch |
| **musictolight-dmx** | Raspberry Pi 3 Model B Rev 1.2 | 192.168.1.151 | DMX Node: runs OLA service, receives HTTP packets and drives DMX fixtures  |
| **Arduino #1**       | Custom (Nano/Uno)              | 192.168.1.152 | Fog machine and mirrored 30‑LED strip near projector                       |
| **Arduino #2**       | Custom (Nano/Uno)              | 192.168.1.153 | 270‑LED main strip (above the screen, dual physical segments)              |
| **Arduino #3**       | Custom (Nano/Uno)              | 192.168.1.154 | 12×25 LED matrix (spectrum analyzer)                                       |

All Arduinos communicate via **UDP port 4210**, receiving binary payloads prefixed with `mls_`.

---

## 3. DMX Hardware (via musictolight-dmx)

### 3.1 Interface

* **Adapter:** FTDI FT232 (ID 0403:6001) USB–DMX dongle (FT232 UART-based)
* **Universe:** 0 only
* **OLA Service:** `olad` running on port 9090 (HTTP receiver for DMX data)
* **Transport Path:** `HTTP POST` from `musictolight` → `musictolight-dmx:9090/set_dmx` → OLA → DMX512 line

### 3.2 DMX Chain

```
EUROLITE T‑36 → Scanner #1 → Scanner #2 → Laser Show (no terminator)
```

> A terminator caused unstable behavior and is therefore omitted.

### 3.3 DMX Devices

| Device Name  | Model                            | Address Range | Channels | Description                               |
| ------------ | -------------------------------- | ------------- | -------- | ----------------------------------------- |
| `scanner_1`  | Moving Mirror / Scanner          | 1–6           | 6        | Pan, Tilt, Color, Gobo, Shutter, Rotation |
| `scanner_2`  | Moving Mirror / Scanner          | 7–12          | 6        | Same as scanner_1 (independent unit)      |
| `t36_spot`   | EUROLITE LED T‑36 RGB 10 mm Spot | 24–28         | 5        | RGB + Master Dimmer + Strobe              |
| `laser_show` | DMX Laser Projector              | 30–44         | 15       | Pattern, X/Y, Zoom, Rotation, Color, etc. |

### 3.4 DMX Failsafe

At boot, the DMX node executes:

```
/usr/bin/ola_set_dmx -u 0 -d 255,255,255,255,0,0,255,255,255,255,0
```

This initializes all connected fixtures to an **"off/safe"** state.

---

## 4. UDP‑Controlled LED Devices

### 4.1 Main LED Strip (`strip_main`)

* **Controller:** Arduino at `192.168.1.153`
* **Type:** WS281x RGB
* **LED Count:** 270 logical pixels (split into two physical strips)
* **Behavior:** Not always mirrored; can operate symmetrically or independently by mode.
* **Power Supply:** External 5 V PSU
* **UDP Port:** 4210

### 4.2 Beamer LED Strip (`strip_beamer`)

* **Controller:** Same Arduino as fog machine (`192.168.1.152`)
* **Type:** WS281x RGB
* **LED Count:** 30 (two mirrored 30‑LED strips, 60 physical)
* **Behavior:** Always mirrored; only 30 LEDs are sent.
* **Power Supply:** External 5 V PSU
* **UDP Port:** 4210

### 4.3 LED Matrix (`matrix_spectrum`)

* **Controller:** Arduino at `192.168.1.154`
* **Configuration:** 12 columns × 25 LEDs = 300 LEDs total
* **Type:** WS281x RGB
* **Purpose:** Spectrum analyzer visualization
* **Power:** 4 separate 5 V rails from a PC power supply
* **UDP Port:** 4210

---

## 5. Fog Machine (`fog_controller`)

* **Controller:** Arduino at `192.168.1.152` (shared with beamer LEDs)
* **Trigger System:** 422 MHz RF transmitter hack
* **Commands:**

  * **Smoke ON:** `codeSmokeOn = 4543756`
  * **Smoke OFF:** `codeSmokeOff = 4543792`
* **Boot Behavior:** Default state OFF

---

## 6. Power and Wiring Notes

| Component    | Power Source   | Voltage       | Notes                              |
| ------------ | -------------- | ------------- | ---------------------------------- |
| DMX Fixtures | Shared DMX PSU | 230 V AC      | Connected via power splitter       |
| LED Strips   | Dedicated PSU  | 5 V           | Rated for 10 A minimum             |
| Matrix       | PC PSU         | 5 V (4 rails) | High current draw, separated rails |
| Fog Machine  | Own PSU        | 230 V AC      | Controlled by Arduino via RF       |

---

## 7. Internal Device Naming (for config.py)

| Logical Name      | Type | IP / Address       | Role                      |
| ----------------- | ---- | ------------------ | ------------------------- |
| `scanner_1`       | DMX  | 1–6                | Primary moving light      |
| `scanner_2`       | DMX  | 7–12               | Secondary moving light    |
| `t36_spot`        | DMX  | 24–28              | RGB spot light            |
| `laser_show`      | DMX  | 30–44              | Laser projector           |
| `strip_main`      | UDP  | 192.168.1.153:4210 | Main ambient LEDs         |
| `strip_beamer`    | UDP  | 192.168.1.152:4210 | Projector LEDs (mirrored) |
| `matrix_spectrum` | UDP  | 192.168.1.154:4210 | Spectrum analyzer matrix  |
| `fog_controller`  | UDP  | 192.168.1.152      | RF fog trigger            |

---

## 8. Future Device Expansion

* **Additional DMX Universe:** possible via second FTDI dongle on Pi 4.
* **Wireless UDP Bridge:** for remote LED zones or battery-powered devices.
* **Optional Sensors:** microphone array for localized beat detection.

---

**Revision:** 2025‑10‑21
**Author:** Felix Rau
**License:** GPL‑3.0
