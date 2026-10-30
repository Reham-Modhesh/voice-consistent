# Microphone Streaming Test

> Stage 3. Not run yet. Complete stages 1 and 2 first.

1. Upload the firmware with your Wi-Fi details and `SERVER_HOST` filled in, and open the Serial Monitor at 115200 baud.
2. Expect `Wi-Fi connected`, `Connected to server`, then `Gemini session ready. Start talking.`
3. Speak a short question. The bridge log should show a `User:` transcript that matches what you said.
   - If the transcript is empty or nonsense, check the INMP441 wiring (L/R to GND for the left channel) and the `>> 14` sample conversion.
4. Watch the `[status]` line every 15 s. `mic_dropped` should stay at 0. If it grows, Wi-Fi is too slow or the loop task is being blocked.
5. Check `heap=` in the status line stays roughly stable over several minutes (no memory leak).
