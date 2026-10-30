"""Acts like the ESP32: streams a WAV file to server.py and saves the spoken reply.

Usage (with server.py running):
    python3 tests/gemini/ws_client_test.py question.wav reply.wav [ws://localhost:8000/ws]

question.wav must be 16 kHz, 16-bit, mono PCM. On macOS you can convert a
recording with:
    afconvert -f WAVE -d LEI16@16000 -c 1 recording.m4a question.wav

Uses the websockets package, which uvicorn[standard] installs.
"""

import asyncio
import json
import sys
import wave

import websockets

FRAME_BYTES = 1280            # 40 ms, same as the firmware
FRAME_SECONDS = 0.04
REPLY_IDLE_SECONDS = 4.0      # stop waiting after this long without a reply frame


async def main(question_path: str, reply_path: str, url: str) -> None:
    with wave.open(question_path, "rb") as source:
        if (source.getnchannels(), source.getsampwidth(), source.getframerate()) != (1, 2, 16000):
            sys.exit("question.wav must be mono, 16-bit, 16 kHz")
        pcm = source.readframes(source.getnframes())

    reply = bytearray()
    epoch = 0
    async with websockets.connect(url, max_size=None) as ws:
        await ws.send(json.dumps({"type": "hello", "fw": "ws_client_test"}))

        while True:  # wait for the Gemini session
            message = json.loads(await ws.recv())
            print("server:", message)
            if message["type"] == "ready":
                break
            if message["type"] == "error":
                sys.exit(1)

        async def stream_question():
            for start in range(0, len(pcm), FRAME_BYTES):
                await ws.send(pcm[start:start + FRAME_BYTES])
                await asyncio.sleep(FRAME_SECONDS)  # real-time pace, like the microphone
            silence = bytes(FRAME_BYTES)
            for _ in range(50):  # 2 s of silence so voice activity detection ends the turn
                await ws.send(silence)
                await asyncio.sleep(FRAME_SECONDS)

        sender = asyncio.create_task(stream_question())
        try:
            while True:
                message = await asyncio.wait_for(ws.recv(), timeout=REPLY_IDLE_SECONDS + len(pcm) / 32000)
                if isinstance(message, bytes):
                    if message[0] == epoch:
                        reply.extend(message[1:])
                    continue
                control = json.loads(message)
                print("server:", control)
                if control["type"] == "interrupted":
                    epoch = control["epoch"]
                    reply.clear()
                elif control["type"] == "turn_complete" and reply:
                    break
        except asyncio.TimeoutError:
            print("No more data from server.")
        sender.cancel()

    with wave.open(reply_path, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(24000)
        out.writeframes(bytes(reply))
    print(f"Saved {len(reply) / 48000:.1f} s of reply audio to {reply_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    asyncio.run(main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "ws://localhost:8000/ws"))
