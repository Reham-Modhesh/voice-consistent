# Voice Consistent

Voice Consistent is a stationary voice interaction system built around an ESP32-S3. A user speaks to the device, the device gets a response from Google Gemini over Wi-Fi, and the response is played back through a speaker.

The device is stationary. It has no vehicle, motor-control or movement functionality.

> **Status:** Early setup. This repository only contains the project structure, documentation and a placeholder firmware sketch. None of the hardware or API integrations below have been implemented or tested yet.

## Goals

- Build a self-contained device that can hold a simple spoken conversation.
- Keep the hardware small and inexpensive, using common I2S audio modules.
- Keep credentials out of source control.
- Validate each part (microphone, speaker, network, AI) separately before combining them.

## Planned Features

- Capture speech through an I2S MEMS microphone.
- Send the user's request to Google Gemini over Wi-Fi.
- Convert the AI response into audio.
- Play the response through an I2S amplifier and speaker.

## Hardware

| Component | Purpose |
|---|---|
| ESP32-S3 development board (N16R8: 16MB Flash, 8MB PSRAM) | Main controller, Wi-Fi |
| INMP441 I2S MEMS microphone | Voice input |
| MAX98357A I2S class-D amplifier | Audio output |
| 3W, 4Ω speaker | Sound output |
| Suitable power supply | Powers the board and amplifier |

See [docs/wiring.md](docs/wiring.md) for the proposed (provisional, untested) wiring.

## Architecture

```text
Microphone (INMP441) → ESP32-S3 → Wi-Fi → Gemini API → response → ESP32-S3 → MAX98357A → Speaker
```

The speech-to-text, AI response and text-to-speech stages are planned, not implemented. See [docs/architecture.md](docs/architecture.md) for details.

## Repository Layout

```text
firmware/VoiceConsistent/   Main Arduino sketch (placeholder only)
tests/microphone/           Planned microphone tests
tests/speaker/              Planned speaker/amplifier tests
tests/gemini/               Planned network and Gemini API tests
config/                     Credential template (secrets.example.h)
docs/                       Architecture and wiring documentation
```

## Roadmap

1. **Hardware checks:** Confirm the board pinout and module datasheets, check the power supply, and flash a basic sketch to the ESP32-S3.
2. **Microphone input:** Initialize I2S for the INMP441 and verify that real audio samples arrive.
3. **Speaker output:** Initialize the MAX98357A and play a test tone safely at low volume.
4. **Gemini connectivity:** Connect to Wi-Fi and get a valid response from the Gemini API.
5. **Voice interaction:** Combine capture, AI response and playback into one end-to-end flow.

## Prerequisites

- [Arduino IDE](https://www.arduino.cc/en/software) 2.x or [Arduino CLI](https://arduino.github.io/arduino-cli/)
- The ESP32 board package by Espressif, installed through the Boards Manager
- A USB cable that supports data
- A Google Gemini API key (from Google AI Studio)
- A 2.4 GHz Wi-Fi network

## Setup

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd voice-consistent
   ```
2. Copy the credential template into the sketch folder and fill in your own values locally. The Arduino IDE only compiles files inside the sketch folder, so the file must go there:
   ```bash
   cp config/secrets.example.h firmware/VoiceConsistent/secrets.h
   ```
3. Open `firmware/VoiceConsistent/VoiceConsistent.ino` in the Arduino IDE.
4. Select the ESP32-S3 board that matches your hardware and the correct serial port.
5. Upload the sketch and open the Serial Monitor at 115200 baud. The current sketch only prints a startup message.

## Security

- Never commit real Wi-Fi credentials or API keys.
- Keep real values in `firmware/VoiceConsistent/secrets.h`, which is listed in `.gitignore`. Only `config/secrets.example.h`, which holds placeholders, is meant to be committed.
- Run `git status` before committing and check that no secrets file is staged.
- If a key is ever committed or shared by mistake, revoke it and create a new one right away. Removing it from a later commit is not enough.
- Credentials compiled into firmware can be read from the device's flash, so do not give the device to others while it holds your keys.

## Current Status

| Area | Status |
|---|---|
| Repository structure and documentation | Done |
| Firmware | Placeholder sketch only (prints a startup message) |
| Wiring | Proposed, not physically tested |
| Microphone input | Not started |
| Speaker output | Not started |
| Wi-Fi / Gemini integration | Not started |
| Speech-to-text (STT) | Not started |
| Text-to-speech (TTS) | Not started |
| Voice interaction | Not started |
