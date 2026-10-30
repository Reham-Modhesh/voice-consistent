# Backend and Gemini Live Tests

> Not run yet.

## Stage 1: Backend Connection

1. Start `server.py` with `GEMINI_API_KEY` set in the environment (see the main README).
2. Open `http://localhost:8000/`. Expect `"status": "ok"` and `"api_key_configured": true`.
3. Start stage 2. The server log should show `Gemini Live session open (model=gemini-3.8-live, resumed=False)`.
   - If it logs a Gemini error about the model, your key may not have access to `gemini-3.8-live`. Set `GEMINI_LIVE_MODEL` to a Live model listed for your key.
4. Start the server once **without** `GEMINI_API_KEY`. A device connection should be rejected with `GEMINI_API_KEY is not set`, and the key should never appear in any log.

## Stage 2: WebSocket Protocol (no ESP32)

[`ws_client_test.py`](ws_client_test.py) acts like the ESP32: it streams a WAV file to `/ws` in 40 ms frames and saves the reply.

1. Record a short question and convert it to 16 kHz mono 16-bit:
   ```bash
   afconvert -f WAVE -d LEI16@16000 -c 1 recording.m4a tests/gemini/question.wav
   ```
2. With the server running:
   ```bash
   python3 tests/gemini/ws_client_test.py tests/gemini/question.wav tests/gemini/reply.wav
   ```
3. Expect `ready`, then reply audio, then `turn_complete`. Play `reply.wav`: it should be a natural Saudi Arabic answer to the question.
4. The server log should show the `User:` and `Gemini:` transcripts.

`.wav` files under `tests/` are ignored by Git.
