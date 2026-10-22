# Architecture

> This document describes the **intended** design. None of these components are implemented yet.

## Overview

```text
┌────────────┐  I2S   ┌──────────┐  Wi-Fi / HTTPS  ┌────────────────────┐
│  INMP441   │ ─────▶ │          │ ──────────────▶ │  Gemini API        │
│ microphone │        │ ESP32-S3 │                 │  (AI response)     │
└────────────┘        │          │ ◀────────────── │                    │
                      └──────────┘                 └────────────────────┘
                           │ I2S
                           ▼
                      ┌───────────┐      ┌─────────┐
                      │ MAX98357A │ ───▶ │ Speaker │
                      │ amplifier │      │ 3W, 4Ω  │
                      └───────────┘      └─────────┘
```

## Planned Flow

1. **Audio capture:** The ESP32-S3 reads audio samples from the INMP441 over I2S and buffers them, using PSRAM if needed.
2. **Speech-to-text (planned):** The recorded audio is turned into text, or sent as audio directly to a model that accepts audio input.
3. **AI response (planned):** The request is sent to Google Gemini over Wi-Fi, and the ESP32-S3 receives a text response.
4. **Text-to-speech (planned):** The response text is converted into audio.
5. **Playback:** The ESP32-S3 streams the audio over I2S to the MAX98357A, which drives the speaker.

## Components

| Component | Role | Status |
|---|---|---|
| I2S microphone input | Capture user speech | Planned |
| Speech-to-text | Convert speech to text | Planned (approach not chosen) |
| Gemini request/response | Generate the reply | Planned |
| Text-to-speech | Convert the reply to audio | Planned (approach not chosen) |
| I2S speaker output | Play the reply | Planned |
| Wi-Fi | Network access | Planned |

## Open Decisions

The final API and audio pipeline will be selected and validated during implementation. Open questions include:

- Whether to send raw audio to Gemini or to run a separate speech-to-text step first.
- Which text-to-speech service or method to use, and its output format (sample rate, encoding).
- Audio formats and sample rates for capture and playback.
- How to start an interaction (button, wake word or another trigger).
- Buffer sizes and memory use within the ESP32-S3's RAM and PSRAM.
- Latency, error handling and recovery when the network is lost.
