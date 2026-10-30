# Staged Test Plan

Run the stages in order. Each stage only adds one new part, so a failure points at that part. None of these stages has been run yet. Record results here as you go.

| Stage | What it checks | Needs | Details |
|---|---|---|---|
| 1. Backend connection | `server.py` starts and opens a Gemini Live session | Mac, API key | [gemini/](gemini/README.md) |
| 2. WebSocket protocol | A full spoken turn through the bridge, without the ESP32 | Mac, API key, a WAV file | [gemini/](gemini/README.md) |
| 3. Microphone streaming | The ESP32 streams real mic audio and Gemini hears it | ESP32 + INMP441 | [microphone/](microphone/README.md) |
| 4. Speaker playback | Streamed replies play cleanly through the MAX98357A | ESP32 + MAX98357A | [speaker/](speaker/README.md) |
| 5. Full conversation | Follow-ups, interruptions, reconnection, long sessions | Everything | Below |

## Stage 5: Full Conversation

1. Ask a question, then a follow-up that depends on it (for example "What's the capital of Japan?" then "What's its population?"). The second answer should use the context.
2. Talk for more than 10 minutes. The bridge log should show `GoAway received` and `resumed=True`, and the conversation should keep its context.
3. Stop and restart `server.py` while the ESP32 is running. The ESP32 should print `Server disconnected` and later `Gemini session ready` again, without a reset.
4. Turn the Wi-Fi router off and on. The ESP32 should print `Wi-Fi lost` and reconnect on its own.
5. Optional: set `ALLOW_BARGE_IN 1`, upload, and speak while Gemini is answering. The bridge should log `Interrupted by user` and playback should stop within about half a second. Note whether the speaker's own sound triggers false interruptions.
6. Ask the device to move. It should say it can't, and the bridge should not log any executed action.
