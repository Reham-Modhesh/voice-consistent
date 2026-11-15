# Voice Consistent

Voice Consistent is a stationary, interactive voice AI assistant built around a classic ESP32. It holds a real-time spoken conversation in Saudi Arabic through the Gemini Live API while displaying live animated facial expressions on an I2C OLED screen.

The ESP32 streams microphone audio with real-time DSP filtering over a WebSocket to a Python FastAPI bridge on your computer, which relays it to a Gemini Live session and streams spoken audio replies back to the speaker.

The device is stationary. It has no vehicle, motor-control or movement functionality, and the bridge rejects any movement-style function call.

> **Status:** Tested and working on real hardware (`FW_VERSION: live-0.3-dsp-stable`). Features real-time audio streaming, Adaptive Gain Control (AGC), DC-blocking filtering, and live OLED facial feedback.

## Goals

- Hold a natural, low-latency spoken conversation in Saudi Arabic, including follow-up questions.
- Provide clear visual feedback (connecting, idle, listening, thinking, speaking) via a 0.96" OLED display.
- Keep the hardware compact and inexpensive using common I2S audio modules.
- Keep the Gemini API key off the ESP32 and out of source control.

## Features

- **Real-Time Audio & DSP (`live-0.3-dsp-stable`):** Continuous microphone streaming (16 kHz, 16-bit, mono) from an INMP441 with a high-pass DC-blocking filter and Adaptive Gain Control (AGC).
- **Live Visual Facial UI:** An SSD1306 I2C OLED display renders dynamic facial states synced with the conversation (`STATE_CONNECTING`, `STATE_IDLE`, `STATE_LISTENING`, `STATE_THINKING`, `STATE_SPEAKING`).
- **Gemini Live Integration:** One Gemini Live session per device connection with native audio output, session resumption (~10 min limit), and context window compression (>15 min).
- **Smooth Playback & Interruption Handling:** Streamed reply audio (24 kHz, 16-bit, mono) played through a MAX98357A with a jitter prebuffer. Queued audio is flushed immediately upon interruption.
- **Auto-Recovery & Telemetry:** Automatic reconnection for Wi-Fi, WebSocket, and Gemini sessions, plus 1-second serial audio diagnostics (`RMS`, `peak`, `gain`, buffer drops).

## Hardware & Wiring (Pinout)

| Component | Purpose | ESP32 Pin |
|---|---|---|
| **ESP32 Dev Module** | Main controller & Wi-Fi (no PSRAM required) | — |
| **INMP441** (I2S Mic) | Voice input (`I2S_NUM_0`, Left channel) | `WS` → **GPIO 25**<br>`SD` → **GPIO 32**<br>`SCK` → **GPIO 33**<br>`L/R` → **GND**<br>`VDD` → **3.3V** |
| **MAX98357A** (I2S Amp) | Audio output (`I2S_NUM_1`) | `LRC` (WS) → **GPIO 26**<br>`BCLK` → **GPIO 27**<br>`DIN` → **GPIO 14**<br>`VIN` → **5V (VIN)** |
| **SSD1306 OLED** (128×64) | Interactive facial expressions (`0x3C`) | `SDA` → **GPIO 18**<br>`SCL` → **GPIO 19**<br>`VCC` → **3.3V** |
| **3W, 4Ω Speaker** | Sound output | Connected to `MAX98357A` (+/-) |
| **Computer** | Runs `server.py` on the same 2.4 GHz network | — |

## Architecture

```text
INMP441 ──I2S──▶ [ESP32 + FreeRTOS DSP] ══ WebSocket /ws ══▶ server.py ══ Gemini Live (WSS)
SSD1306 ◀─I2C──┤   (Mic & Playback Tasks)   PCM 16 kHz up       │  ▲
MAX98357A ◀I2S─┘                            PCM 24 kHz down ◀═══╝  └══ Streamed Audio Replies
```

The Gemini API key stays on the computer running `server.py`. See [docs/architecture.md](docs/architecture.md) for full protocol details.

## Repository Layout

```text
firmware/VoiceConsistent/   Main Arduino sketch (VoiceConsistent.ino - v0.3-dsp-stable)
server.py                   Gemini Live WebSocket bridge (FastAPI)
requirements.txt            Python dependencies for server.py
.env.example                Template for GEMINI_API_KEY
config/                     Credential header template
tests/                      Staged test plan and PC-side WebSocket test client
docs/                       Architecture and detailed wiring documentation
```

## Prerequisites

**Backend**
- Python **3.10 or newer** (required by `google-genai`).
- A Google Gemini API key with access to the Live API model (`gemini-3.8-live` by default).

**Firmware (Arduino IDE 2.x)**
- Board package: **esp32 by Espressif, version 3.x** (tested on `3.3.12`).
- Required Libraries (install via Arduino Library Manager):
  1. **WebSockets** by Markus Sattler (`links2004`, version `2.7.x`)
  2. **Adafruit GFX Library** by Adafruit
  3. **Adafruit SSD1306** by Adafruit
- A shared **2.4 GHz** Wi-Fi network (or mobile hotspot) for the ESP32 and computer.

## Setup

### 1. Backend (`server.py`)

1. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Configure your API key via `.env` or environment variable:
   ```bash
   cp .env.example .env    # Add your GEMINI_API_KEY inside .env
   set -a; source .env; set +a
   ```
3. Start the FastAPI bridge from the repository root:
   ```bash
   python3 -m uvicorn server:app --host 0.0.0.0 --port 8000
   ```
4. Verify `http://localhost:8000/` returns `"api_key_configured": true`, and note your computer's local LAN IP address (e.g., `192.168.100.9`).

### 2. Firmware (`VoiceConsistent.ino`)

1. Install the three required libraries listed in Prerequisites.
2. Open `firmware/VoiceConsistent/VoiceConsistent.ino`.
3. Update `WIFI_SSID`, `WIFI_PASSWORD`, and `SERVER_HOST` (your computer's LAN IP) at the top of the file. **Do not commit real credentials.**
4. Select **ESP32 Dev Module** and the corresponding USB serial port, then click **Upload**.
5. Open the Serial Monitor at **115200 baud**. Once connected, the OLED face transitions from `Connecting...` to idle/listening, and the monitor prints `Gemini session ready. Start talking.`

## Security

- **Never commit real Wi-Fi credentials or API keys.** Always replace credentials with placeholders before running `git push`.
- `GEMINI_API_KEY` is loaded strictly from environment variables / `.env` (ignored by `.gitignore`).
- The local WebSocket bridge (`ws://`) runs unauthenticated on your LAN; run it only on trusted networks.

## Limitations & Notes

- **Echo Suppression:** Without hardware acoustic echo cancellation, `ALLOW_BARGE_IN` is set to `0` by default. The microphone automatically mutes during speaker playback and for 300 ms afterward to prevent self-triggering.
- **RAM & Prebuffering:** Classic ESP32 boards without PSRAM use a 32 KB playback ring buffer (~0.68 s) with a 7,200-byte prebuffer (~150 ms) to prevent audio underruns over Wi-Fi.
- **I2S Legacy Driver:** Uses `driver/i2s.h` for dual-port I2S stability (`I2S_NUM_0` for Mic, `I2S_NUM_1` for Speaker). Compile-time deprecation warnings on ESP32 core 3.x are expected and safe to ignore.

## Current Status

| Component | Status |
|---|---|
| **Firmware (`live-0.3-dsp-stable`)** | Tested & verified on hardware (FreeRTOS dual-task mic/playback + AGC/DC DSP) |
| **OLED Facial UI (`SSD1306`)** | Tested & working (dynamic eye/mouth states on I2C pins 18/19) |
| **Bridge (`server.py`)** | Tested & working with Gemini Live API |
| **Audio Pipeline (INMP441 + MAX98357A)** | Tuned & verified (16 kHz capture / 24 kHz playback) |
