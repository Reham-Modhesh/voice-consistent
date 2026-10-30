# Architecture

> This describes the design of the current code in `firmware/VoiceConsistent/VoiceConsistent.ino` and `server.py`. It has not yet been tested with real hardware or a real Gemini Live session.

## Overview

```text
┌────────────┐ I2S0 ┌──────────────────────────────┐  WebSocket /ws  ┌───────────────────┐  WSS   ┌────────────────┐
│  INMP441   │────▶ │ ESP32                        │ ══ PCM 16k ══▶  │ server.py         │ ═════▶ │ Gemini Live    │
│ microphone │      │  mic task ─▶ mic buffer 8 KB │                 │  device_reader    │        │ gemini-3.8-live│
└────────────┘      │  loop: WebSocket + Wi-Fi     │ ◀═ PCM 24k ═══  │  audio_sender     │ ◀═════ │ (native audio) │
                    │  playback task ◀─ 32 KB buf  │   + control     │  gemini_loop      │        └────────────────┘
                    └──────────────────────────────┘                 └───────────────────┘
                                 │ I2S1
                                 ▼
                    ┌───────────┐      ┌─────────┐
                    │ MAX98357A │ ───▶ │ Speaker │
                    └───────────┘      └─────────┘
```

## Audio Formats

| Path | Format | Source |
|---|---|---|
| INMP441 → ESP32 | 32-bit I2S slots, left channel, 16 kHz; converted with `>> 14` to 16-bit | Kept from the working microphone test |
| ESP32 → bridge → Gemini | 16-bit signed PCM, little-endian, mono, 16 kHz (`audio/pcm;rate=16000`) | Live API input format |
| Gemini → bridge → ESP32 | 16-bit signed PCM, little-endian, mono, 24 kHz | Live API output format |
| ESP32 → MAX98357A | 16-bit I2S, 24 kHz, left slot | Speaker config from the previous firmware |

The ESP32 is little-endian, so no byte swapping is needed.

## Wire Protocol (ESP32 ⇄ bridge)

Defined in the docstring at the top of `server.py`. Summary:

- **ESP32 → bridge, binary:** raw 16 kHz PCM in 1280-byte (40 ms) frames.
- **ESP32 → bridge, text:** `{"type":"hello","fw":"..."}` once after connecting.
- **Bridge → ESP32, binary:** 1 byte playback epoch + up to 2048 bytes of 24 kHz PCM.
- **Bridge → ESP32, text:** `ready`, `reconnecting`, `interrupted` (with the new `epoch`), `turn_complete`, `error`.

## Firmware Design

- **Mic task** (core 1): blocking `i2s_read`, converts to 16-bit, writes into an 8 KB stream buffer. Drops audio if the buffer is full.
- **Loop task** (core 1): runs `webSocket.loop()`, keeps Wi-Fi up, and sends complete 40 ms mic frames. Frames are discarded instead of sent while the server is not ready or while the mic is muted, so stale audio is never sent late.
- **Playback task** (core 1): waits for 150 ms of audio (or the end of a turn), then streams from the 32 KB buffer into I2S with blocking writes. On underrun it stops and waits to prebuffer again; `tx_desc_auto_clear` outputs silence in the meantime.
- **Interruption:** an `interrupted` message updates the expected epoch (so in-flight audio from before is dropped on arrival) and asks the playback task to drain its buffer and clear the I2S DMA buffers.
- **Echo handling:** with `ALLOW_BARGE_IN 0`, mic frames are discarded while audio is buffered or playing, and for 300 ms after.
- **Reconnection:** Wi-Fi is retried every 10 s. The WebSocket library reconnects every 3 s and sends a ping every 15 s, treating 2 missed pongs as a disconnect.

## Bridge Design

- One `DeviceBridge` per ESP32 connection, with three asyncio tasks:
  - `device_reader` forwards mic frames to Gemini with `send_realtime_input`. Frames that arrive while Gemini is reconnecting are dropped.
  - `gemini_loop` opens the Live session, handles responses, and reconnects with exponential backoff (2 s to 30 s). It reopens immediately, with the latest resumption handle, after a `go_away` message.
  - `audio_sender` sends reply audio paced to stay at most 0.35 s ahead of real-time playback. `turn_complete` goes through the same queue, so it arrives after the turn's last audio frame.
- **Session config:** response modality `AUDIO`, a Saudi Arabic system instruction, voice `Kore`, input and output transcription (logged to the console), session resumption, and sliding-window context compression.
- **Function calls:** none are declared. If Gemini sends any, each one is checked against an empty allowlist and answered with an error. Nothing is executed.
- **Interruption:** on `server_content.interrupted`, the epoch increases, all queued audio is discarded, and `interrupted` is sent to the ESP32.

## Session Limits (Gemini Live)

- A connection lasts about 10 minutes. The server sends `go_away` before closing, and the bridge reconnects with the latest resumption handle (handles stay valid for 2 hours).
- An audio-only session is limited to 15 minutes without compression. Sliding-window compression is enabled to lift this limit; the oldest context is dropped as the window fills.
- The context window is 128k tokens for native audio models.

## Open Decisions

- Echo cancellation, or a push-to-talk button, to allow reliable voice interruption.
- A wake word or button instead of always-on streaming.
- Moving Wi-Fi credentials out of the sketch into an ignored `secrets.h`.
- Authentication between the ESP32 and the bridge.
- Migrating to the `ESP_I2S` driver in core 3.x.
