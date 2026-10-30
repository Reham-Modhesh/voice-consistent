# Voice Consistent

Voice Consistent is a stationary voice assistant built around a classic ESP32. It holds a real-time spoken conversation through the Gemini Live API: the ESP32 streams microphone audio over a WebSocket to a small Python bridge on your computer, the bridge relays it to a Gemini Live session, and Gemini's spoken reply streams back and plays through the speaker as it arrives.

The device is stationary. It has no vehicle, motor-control or movement functionality, and the bridge rejects any movement-style function call.

> **Status:** The Gemini Live firmware and bridge are written. The firmware compiles for an ESP32 Dev Module (core 3.3.12), and the bridge's protocol logic passes tests against a simulated Gemini session. **Nothing has been tested with real hardware or a real Gemini Live session yet.** Follow the [staged test plan](tests/README.md).

## Goals

- Hold a natural, low-latency spoken conversation, including follow-up questions.
- Keep the hardware small and inexpensive, using common I2S audio modules.
- Keep the API key off the device and out of source control.
- Validate each part (microphone, speaker, network, AI) separately before combining them.

## Features

- Continuous microphone streaming (16 kHz, 16-bit, mono) from an INMP441 over a persistent WebSocket.
- One Gemini Live session per device connection, with native audio output and instructions to speak Saudi Arabic.
- Streamed reply audio (24 kHz, 16-bit, mono) played through a MAX98357A as it arrives, with a short jitter buffer.
- Conversation context kept within a session, including across Gemini's ~10 minute connection limit (session resumption) and beyond 15 minutes (context window compression).
- Interruption handling: when Gemini reports an interruption, queued audio is discarded on both the bridge and the ESP32.
- Automatic reconnection of Wi-Fi, the device WebSocket and the Gemini session.

## Hardware

| Component | Purpose |
|---|---|
| ESP32 Dev Module (classic ESP32, no PSRAM required) | Main controller, Wi-Fi |
| INMP441 I2S MEMS microphone | Voice input (I2S port 0) |
| MAX98357A I2S class-D amplifier | Audio output (I2S port 1) |
| 3W, 4Ω speaker | Sound output |
| Suitable power supply | Powers the board and amplifier |
| Computer on the same network | Runs `server.py` |

See [docs/wiring.md](docs/wiring.md) for the wiring used by the firmware.

## Architecture

```text
INMP441 ─I2S─▶ ESP32 ══ WebSocket /ws ══▶ server.py ══ Gemini Live (WSS) ══▶ gemini-3.8-live
                 ▲      PCM 16 kHz up        │  ▲
MAX98357A ◀─I2S──┘      PCM 24 kHz down ◀════┘  └══ streamed audio replies
```

The Gemini API key stays on the computer running `server.py`. The exact wire protocol is documented at the top of [server.py](server.py), and the design is in [docs/architecture.md](docs/architecture.md).

## Repository Layout

```text
firmware/VoiceConsistent/   Main Arduino sketch (VoiceConsistent.ino)
server.py                   Gemini Live WebSocket bridge (FastAPI)
requirements.txt            Python dependencies for server.py
.env.example                Template for GEMINI_API_KEY
config/                     Credential header template (not yet used by the sketch)
tests/                      Staged test plan and a PC-side WebSocket test client
docs/                       Architecture and wiring documentation
```

## Prerequisites

**Backend**
- Python **3.10 or newer** (required by `google-genai`). macOS's built-in Python 3.9 is too old; install a newer one, for example from python.org or with Homebrew.
- A Google Gemini API key with access to the Live API model (`gemini-3.8-live` by default).

**Firmware**
- Arduino IDE 2.x or Arduino CLI.
- Board package **esp32 by Espressif, version 3.x** (developed against 3.3.12).
- Library **WebSockets by Markus Sattler** (links2004), version 2.7.x, from the Library Manager.
- A 2.4 GHz Wi-Fi network shared by the ESP32 and the computer.

## Setup

### Backend (`server.py`)

1. Create a virtual environment with Python 3.10+ and install the dependencies:
   ```bash
   python3.12 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Provide your API key through the environment, either directly:
   ```bash
   export GEMINI_API_KEY="your-key"
   ```
   or from a local `.env` file:
   ```bash
   cp .env.example .env    # then edit .env
   set -a; source .env; set +a
   ```
3. Start the bridge from the repository root:
   ```bash
   python3 -m uvicorn server:app --host 0.0.0.0 --port 8000
   ```
4. Check `http://localhost:8000/`. It should report `"api_key_configured": true`.
5. Find your computer's LAN IP address (for example `192.168.1.20`). macOS may ask whether to allow incoming connections for Python; allow it.

Optional environment variables: `GEMINI_LIVE_MODEL` (default `gemini-3.8-live`) and `GEMINI_VOICE` (default `Kore`).

### Firmware

1. Install the **WebSockets** library (Markus Sattler) from the Arduino Library Manager.
2. Open `firmware/VoiceConsistent/VoiceConsistent.ino`.
3. Edit `WIFI_SSID`, `WIFI_PASSWORD` and `SERVER_HOST` at the top of the sketch. **Do not commit these local edits** (see Security).
4. Select **ESP32 Dev Module** and the correct serial port, then upload.
5. Open the Serial Monitor at 115200 baud. When it prints `Gemini session ready. Start talking.`, speak normally.

## Security

- Never commit real Wi-Fi credentials or API keys.
- The Gemini API key is read only from the `GEMINI_API_KEY` environment variable and is never logged. Keep it in your shell or in `.env`, which is listed in `.gitignore`. Only `.env.example` is meant to be committed.
- The sketch holds Wi-Fi placeholders in the source file itself. After filling in real values, check `git diff` before committing and do not commit them.
- If a key is ever committed or shared by mistake, revoke it and create a new one right away. Removing it from a later commit is not enough.
- The bridge listens on your local network over plain `ws://` with no authentication, and anyone who can reach it can use your Gemini quota. Run it only on a trusted network.
- The bridge logs transcripts of both sides of the conversation to its console.

## Limitations

- **Echo / barge-in:** the speaker is close to the microphone and there is no echo cancellation. By default (`ALLOW_BARGE_IN 0`) the microphone is muted while a reply plays and for 300 ms after, so you cannot interrupt Gemini by voice. Setting it to `1` enables voice interruption, but the speaker's own sound may then interrupt replies.
- **RAM (classic ESP32, no PSRAM):** the playback buffer is 32 KB (about 0.68 s). The bridge therefore paces reply audio to stay at most 0.35 s ahead of playback instead of sending it as fast as Gemini produces it.
- **Latency:** a 150 ms prebuffer plus about 170 ms of I2S DMA buffering is added before replies are heard, on top of network and Gemini latency.
- **I2S driver:** the firmware uses the legacy `driver/i2s.h` API, which is deprecated in ESP32 core 3.x and prints compile warnings. It must not be combined with the `ESP_I2S` library in the same sketch.
- **Bandwidth:** about 32 KB/s up and 48 KB/s down. Weak Wi-Fi will cause dropped mic audio or playback gaps; the firmware prints counters for both every 15 seconds.
- **Model availability:** `gemini-3.8-live` is the model named in the current Live API guide, but availability depends on your API key. Set `GEMINI_LIVE_MODEL` if you need another model.
- **Trigger:** there is no wake word or button; the microphone streams whenever the device is connected and not playing.

## Current Status

| Area | Status |
|---|---|
| Firmware (streaming mic, streaming playback, reconnection) | Written; compiles for ESP32 Dev Module with core 3.3.12; not tested on hardware |
| Bridge (`server.py`) | Written; protocol logic passes tests against a simulated Gemini session; not tested against real Gemini Live |
| Wiring | Unchanged from the previous firmware; microphone pins from an earlier working test |
| Speech understanding and reply (Gemini Live native audio) | Written; not tested |
| Tests | Staged plan and PC-side test client written; not yet run |
