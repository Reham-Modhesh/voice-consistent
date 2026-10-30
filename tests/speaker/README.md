# Speaker Playback Test

> Stage 4. Not run yet. Read the safety notes in [docs/wiring.md](../../docs/wiring.md) before powering the amplifier.

1. Start with the speaker at a safe distance and the amplifier supply checked.
2. Ask a question. The reply should play smoothly, without clicks, gaps or a chipmunk/slow-motion sound.
   - Wrong pitch or speed means a sample-rate mismatch: the firmware plays at 24 kHz, the Live API output rate.
   - Gaps mean underruns: check `spk_overflow` and Wi-Fi signal strength.
3. Watch the `[status]` line. `spk_overflow` should stay at 0. If it grows, the bridge is sending faster than the ESP32 plays; lower `PLAYBACK_LEAD_SECONDS` in `server.py`.
4. With `ALLOW_BARGE_IN 0`, the status line should show `mic=muted` while the reply plays and `mic=live` shortly after it ends.
5. Listen for noise at power-up; GPIO 14 and 27 can toggle briefly at boot.
