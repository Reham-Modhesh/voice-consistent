# Voice Consistent

Voice Consistent is a stationary, interactive voice AI assistant built around a classic ESP32. It holds a real-time spoken conversation in Saudi Arabic through the Gemini Live API while displaying live animated facial expressions on an I2C OLED screen.

The ESP32 streams microphone audio with real-time DSP filtering over a WebSocket to a Python FastAPI bridge on your computer, which relays it to a Gemini Live session and streams spoken audio replies back to the speaker.

The device is stationary. It has no vehicle, motor-control or movement functionality, and the bridge rejects any movement-style function call.

> **Status:** Tested and working on real hardware (`FW_VERSION: live-0.3-dsp-stable`). Features real-time audio streaming, Adaptive Gain Control (AGC), DC-blocking filtering, and live OLED facial feedback.

---

## Goals

* Hold a natural, low-latency spoken conversation in Saudi Arabic, including follow-up questions.
* Provide clear visual feedback (connecting, idle, listening, thinking, speaking) via a 0.96" OLED display.
* Keep the hardware compact and inexpensive using common I2S audio modules.
* Keep the Gemini API key off the ESP32 and out of source control.

---

## Features

* **Real-Time Audio & DSP (`live-0.3-dsp-stable`):** Continuous microphone streaming (16 kHz, 16-bit, mono) from an INMP441 with a high-pass DC-blocking filter and Adaptive Gain Control (AGC).
* **Live Visual Facial UI:** An SSD1306 I2C OLED display renders dynamic facial states synced with the conversation (`STATE_CONNECTING`, `STATE_IDLE`, `STATE_LISTENING`, `STATE_THINKING`, `STATE_SPEAKING`).
* **Gemini Live Integration:** One Gemini Live session per device connection with native audio output, session resumption (~10 min limit), and context window compression (>15 min).
* **Smooth Playback & Interruption Handling:** Streamed reply audio (24 kHz, 16-bit, mono) played through a MAX98357A with a jitter prebuffer. Queued audio is flushed immediately upon interruption.
* **Auto-Recovery & Telemetry:** Automatic reconnection for Wi-Fi, WebSocket, and Gemini sessions, plus 1-second serial audio diagnostics (`RMS`, `peak`, `gain`, buffer drops).

---

## Hardware & Wiring (Pinout)

Ensure all modules share a common ground (`GND`) with the ESP32.

| Component | Purpose | ESP32 Pin |
| :--- | :--- | :--- |
| **ESP32 Dev Module** | Main controller & Wi-Fi (no PSRAM required) | — |
| **INMP441** (I2S Mic) | Voice input (`I2S_NUM_0`, Left channel) | `WS` → **GPIO 25**<br>`SD` → **GPIO 32**<br>`SCK` → **GPIO 33**<br>`L/R` → **GND**<br>`VDD` → **3.3V** |
| **MAX98357A** (I2S Amp) | Audio output (`I2S_NUM_1`) | `LRC` (WS) → **GPIO 26**<br>`BCLK` → **GPIO 27**<br>`DIN` → **GPIO 14**<br>`VIN` → **5V (VIN)** |
| **SSD1306 OLED** (128×64) | Interactive facial expressions (`0x3C`) | `SDA` → **GPIO 18**<br>`SCL` → **GPIO 19**<br>`VCC` → **3.3V** |
| **3W, 4Ω Speaker** | Sound output | Connected to `MAX98357A` (`+` / `-`) |
| **Computer** | Runs `server.py` on the exact same 2.4 GHz network | — |

---

## Architecture

```text
INMP441 ──I2S──▶ [ESP32 + FreeRTOS DSP] ══ WebSocket /ws ══▶ server.py ══ Gemini Live (WSS)
SSD1306 ◀─I2C──┤   (Mic & Playback Tasks)   PCM 16 kHz up       │  ▲
MAX98357A ◀I2S─┘                            PCM 24 kHz down ◀═══╝  └══ Streamed Audio Replies
```

The Gemini API key stays strictly on the computer running `server.py`. See [docs/architecture.md](docs/architecture.md) for full protocol details.

---

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

---

## Step-by-Step Setup Guide for Members

### Step 1: Get Your Gemini API Key (Google AI Studio)

You do **not** put the API key inside the ESP32 code. Instead, you generate a free/developer key and run it on your computer's Python server:

1. Go to **[Google AI Studio](https://aistudio.google.com/)** and sign in with your Google account.
2. Click on **"Get API key"** in the left sidebar (or top menu).
3. Click **"Create API key"** and select a Google Cloud project (or create a new one).
4. Copy the generated key (`AIzaSy...`) and save it safely—you will paste it into your `.env` file in Step 3.

---

### Step 2: Network Requirements (CRITICAL ⚠️)

For the ESP32 and your computer to talk to each other over WebSockets, **they MUST follow these rules**:

1. **Same Network:** Both your computer (running `server.py`) and the ESP32 **must be connected to the exact same Wi-Fi network** (or mobile hotspot).
2. **2.4 GHz Band Only:** The classic ESP32 only supports **2.4 GHz Wi-Fi** (it cannot see 5 GHz networks). If using a mobile hotspot (e.g., iPhone), make sure **"Maximize Compatibility"** is turned ON.
3. **Find Your Computer's Local IP Address:**
   * **macOS:** Open Terminal and run `ipconfig getifaddr en0` (usually looks like `192.168.x.x` or `172.20.10.x`).
   * **Windows:** Open Command Prompt (`cmd`) and run `ipconfig`, then look for the **IPv4 Address** under your Wi-Fi adapter.
   * *Note: This IP address can change if you switch networks, so always double-check it before uploading code to the ESP32!*

---

### Step 3: Backend Setup (`server.py`)

**Prerequisites:** Python **3.10 or newer** installed on your computer.

1. Open your terminal in the root folder of this repository, create a virtual environment, and install the dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate        # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Create your `.env` file from the example template and add your Google AI Studio API key:
   ```bash
   cp .env.example .env
   ```
   Open `.env` in any text editor and paste your key:
   ```env
   GEMINI_API_KEY="AIzaSyYourActualKeyFromGoogleAIStudio"
   ```
3. Load the environment variables and start the FastAPI WebSocket bridge:
   ```bash
   set -a; source .env; set +a
   python3 -m uvicorn server:app --host 0.0.0.0 --port 8000
   ```
4. Verify it is running by opening `http://localhost:8000/` in your browser. It should display `"api_key_configured": true`.
   *(If macOS or Windows Firewall asks to allow incoming network connections for Python, click **Allow**).*

---

### Step 4: Firmware Setup (`VoiceConsistent.ino`)

**Prerequisites (Arduino IDE 2.x):**
* Board package: **esp32 by Espressif, version 3.x** (tested on `3.3.12`).
* Install these 3 libraries via **Arduino Library Manager**:
  1. **WebSockets** by Markus Sattler (`links2004`, version `2.7.x`)
  2. **Adafruit GFX Library** by Adafruit
  3. **Adafruit SSD1306** by Adafruit

**Flashing the Code:**
1. Open `firmware/VoiceConsistent/VoiceConsistent.ino` in Arduino IDE.
2. **Edit the Network & Server credentials** at the top of the file (around lines 22–28) to match your network and the computer IP you found in Step 2:
   ```cpp
   // ---- Wi-Fi Details (Must be 2.4 GHz & same network as PC) ----
   const char* WIFI_SSID     = "YOUR_2.4GHZ_WIFI_NAME";
   const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

   // ---- FastAPI Server Address (Your Computer's Local IPv4) ----
   const char* SERVER_HOST   = "192.168.100.9"; // <-- Replace with your PC's IP!
   const uint16_t SERVER_PORT = 8000;
   ```
3. Select **ESP32 Dev Module** and your USB serial port, then click **Upload**.
4. Open the **Serial Monitor** at **115200 baud**. Once connected, the OLED screen will switch from `Connecting...` to an animated face, and the monitor will print:
   `Gemini session ready. Start talking.`

---

## Security Rules for Contributors

* **Never commit real Wi-Fi passwords, personal IPs, or API keys.** Always reset `WIFI_SSID`, `WIFI_PASSWORD`, and `SERVER_HOST` back to placeholders before running `git push`.
* `GEMINI_API_KEY` is loaded strictly from `.env` (which is ignored by `.gitignore`).
* The local WebSocket bridge (`ws://`) runs unauthenticated on your local network; run it only on trusted networks.

---

## Troubleshooting & Limitations

* **ESP32 stuck on `Connecting...`:**
  * Check that `SERVER_HOST` in the Arduino sketch matches your computer's current IP address.
  * Ensure your Wi-Fi is **2.4 GHz** and both devices are on the exact same network (public/university Wi-Fi often blocks device-to-device communication; use a phone hotspot instead).
  * Confirm `uvicorn` is running with `--host 0.0.0.0` and your firewall isn't blocking port `8000`.
* **Echo Suppression (`ALLOW_BARGE_IN 0`):** Without hardware acoustic echo cancellation, the microphone automatically mutes while the speaker is playing and for 300 ms afterward so the robot doesn't hear itself.
* **I2S Legacy Driver Warnings:** Compile-time deprecation warnings for `driver/i2s.h` on ESP32 core 3.x are normal and safe to ignore.

---

## Current Status

| Component | Status |
| :--- | :--- |
| **Firmware (`live-0.3-dsp-stable`)** | Tested & verified on hardware (FreeRTOS dual-task mic/playback + AGC/DC DSP) |
| **OLED Facial UI (`SSD1306`)** | Tested & working (dynamic eye/mouth states on I2C pins 18/19) |
| **Bridge (`server.py`)** | Tested & working with Gemini Live API |
| **Audio Pipeline (INMP441 + MAX98357A)** | Tuned & verified (16 kHz capture / 24 kHz playback) |
