"""Local Gemini Live bridge for the ESP32 INMP441 + MAX98357A voice assistant.

The ESP32 keeps one WebSocket open to this server. The server keeps one Gemini
Live session per ESP32 connection and relays audio both ways in real time.

Install (Python 3.10+ is required by google-genai):
    python3 -m pip install -r requirements.txt
Run:
    export GEMINI_API_KEY="your-key"
    python3 -m uvicorn server:app --host 0.0.0.0 --port 8000

The API key belongs here on your computer, not in the ESP32 firmware.
It is read from the GEMINI_API_KEY environment variable; never paste it into this file.

Wire protocol (ESP32 <-> this server, WebSocket at /ws):

  ESP32 -> server
    binary: raw PCM, 16-bit signed little-endian, mono, 16 kHz.
            Any length; the firmware sends 1280-byte (40 ms) frames.
    text:   JSON control messages:
            {"type": "hello", "fw": "<version>"}   sent once after connecting

  server -> ESP32
    binary: byte 0 = playback epoch (0-255), then raw PCM, 16-bit signed
            little-endian, mono, 24 kHz. At most 1 + MAX_AUDIO_FRAME bytes.
            The ESP32 drops frames whose epoch differs from the last epoch
            announced in an "interrupted" message.
    text:   JSON control messages:
            {"type": "ready"}                         Gemini session is open
            {"type": "reconnecting"}                  Gemini session is being reopened
            {"type": "interrupted", "epoch": N}       stop playback and discard all buffered
                                                      audio, including any earlier turn's tail
            {"type": "turn_complete"}                 sent after the turn's last audio frame
            {"type": "error", "message": "..."}       fatal or non-fatal error
"""

import asyncio
import json
import logging
import os
import time
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types

# Set the GEMINI_API_KEY environment variable before starting the server.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

LIVE_MODEL = os.environ.get("GEMINI_LIVE_MODEL", "gemini-3.8-live")
VOICE_NAME = os.environ.get("GEMINI_VOICE", "Kore")

INPUT_MIME_TYPE = "audio/pcm;rate=16000"  # what the ESP32 sends
OUTPUT_SAMPLE_RATE = 24000                # what Gemini Live returns
OUTPUT_BYTES_PER_SECOND = OUTPUT_SAMPLE_RATE * 2

# Largest audio payload sent to the ESP32 in one WebSocket frame.
MAX_AUDIO_FRAME = 2048
# How far ahead of real-time playback the server may send audio. The ESP32
# playback buffer must be larger than this (it is 32 KB, about 0.68 s).
PLAYBACK_LEAD_SECONDS = 0.35
# Retry delay when the Gemini session cannot be opened or drops; doubles on
# each consecutive failure up to the maximum.
RECONNECT_DELAY_SECONDS = 2.0
RECONNECT_DELAY_MAX_SECONDS = 30.0

# The device is stationary and has no motor driver, so no tools are declared
# and no function call is ever executed. Any call Gemini makes anyway is
# checked against this allowlist and answered with an error.
ALLOWED_TOOLS: set[str] = set()

SYSTEM_INSTRUCTION = """
أنت مساعد صوتي ودود في جهاز ثابت على الطاولة. تكلم باللهجة السعودية بأسلوب طبيعي ومختصر.
افهم كلام المستخدم سواء كان بالعربية أو الإنجليزية، ورد بالعربية السعودية إلا إذا طلب المستخدم لغة ثانية.
خل ردودك قصيرة لأنها تنقال بصوت عالي، وتذكر سياق المحادثة عشان تجاوب على الأسئلة اللي بعدها.
الجهاز ما يتحرك وما عنده محركات، فإذا طلب المستخدم حركة قل له بلطف إنك ما تقدر تتحرك.
إذا ما فهمت الكلام، اطلب من المستخدم يعيده.
""".strip()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("voice-bridge")

app = FastAPI(title="Voice Consistent Gemini Live bridge")


def build_live_config(resume_handle: Optional[str]) -> types.LiveConnectConfig:
    return types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        system_instruction=SYSTEM_INSTRUCTION,
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=VOICE_NAME)
            )
        ),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        # Resumption keeps the conversation context across the ~10 minute
        # connection limit; compression lifts the 15 minute session limit.
        session_resumption=types.SessionResumptionConfig(handle=resume_handle),
        context_window_compression=types.ContextWindowCompressionConfig(
            sliding_window=types.SlidingWindow()
        ),
    )


class DeviceBridge:
    """Relays audio between one ESP32 WebSocket and one Gemini Live session."""

    def __init__(self, ws: WebSocket, client: genai.Client):
        self.ws = ws
        self.client = client
        self.session = None  # the open Gemini Live session, or None
        self.resume_handle: Optional[str] = None
        self.epoch = 0
        # Audio waiting to be sent to the ESP32, as (epoch, pcm) tuples. A pcm of
        # None marks the end of a turn, so turn_complete arrives after the audio.
        self.audio_out: asyncio.Queue = asyncio.Queue()
        # Serializes all writes to the ESP32 WebSocket.
        self.send_lock = asyncio.Lock()
        self.dropped_mic_frames = 0

    async def send_control(self, message: dict) -> None:
        async with self.send_lock:
            await self.ws.send_text(json.dumps(message))

    def clear_audio_out(self) -> None:
        while not self.audio_out.empty():
            self.audio_out.get_nowait()

    async def run(self) -> None:
        tasks = [
            asyncio.create_task(self.device_reader(), name="device_reader"),
            asyncio.create_task(self.audio_sender(), name="audio_sender"),
            asyncio.create_task(self.gemini_loop(), name="gemini_loop"),
        ]
        try:
            # Any task ending (normally only device_reader, on disconnect) ends the bridge.
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                if not task.cancelled() and task.exception():
                    raise task.exception()
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def device_reader(self) -> None:
        """Forwards microphone audio from the ESP32 to Gemini."""
        while True:
            message = await self.ws.receive()
            if message["type"] == "websocket.disconnect":
                return
            if message.get("bytes"):
                session = self.session
                if session is None:
                    # Gemini is (re)connecting; drop audio rather than buffer stale speech.
                    self.dropped_mic_frames += 1
                    continue
                try:
                    await session.send_realtime_input(
                        audio=types.Blob(data=message["bytes"], mime_type=INPUT_MIME_TYPE)
                    )
                except Exception as exc:  # session closing; gemini_loop will reconnect
                    log.warning("Could not forward mic audio: %s", type(exc).__name__)
            elif message.get("text"):
                try:
                    control = json.loads(message["text"])
                except json.JSONDecodeError:
                    log.warning("Ignoring non-JSON text frame from device")
                    continue
                if control.get("type") == "hello":
                    log.info("Device hello: firmware %s", control.get("fw", "?"))

    async def audio_sender(self) -> None:
        """Sends queued reply audio to the ESP32, paced close to real time."""
        play_until = time.monotonic()  # when the ESP32 will finish what it has
        last_epoch = self.epoch
        while True:
            epoch, pcm = await self.audio_out.get()
            if epoch != self.epoch:
                continue  # interrupted while queued
            if pcm is None:
                await self.send_control({"type": "turn_complete"})
                continue
            now = time.monotonic()
            if epoch != last_epoch:
                play_until = now  # the ESP32 cleared its buffer on interruption
                last_epoch = epoch
            play_until = max(play_until, now)
            lead = play_until - now
            if lead > PLAYBACK_LEAD_SECONDS:
                await asyncio.sleep(lead - PLAYBACK_LEAD_SECONDS)
                if epoch != self.epoch:
                    continue
            async with self.send_lock:
                await self.ws.send_bytes(bytes([epoch]) + pcm)
            play_until += len(pcm) / OUTPUT_BYTES_PER_SECOND

    async def gemini_loop(self) -> None:
        """Keeps a Gemini Live session open, reconnecting with resumption."""
        delay = RECONNECT_DELAY_SECONDS
        while True:
            try:
                config = build_live_config(self.resume_handle)
                async with self.client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
                    self.session = session
                    delay = RECONNECT_DELAY_SECONDS
                    log.info("Gemini Live session open (model=%s, resumed=%s)",
                             LIVE_MODEL, self.resume_handle is not None)
                    await self.send_control({"type": "ready"})
                    await self.receive_from_gemini(session)
                log.info("Gemini Live connection ended; reconnecting")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                # Log the exception type and message only; the SDK does not include the key.
                log.error("Gemini Live error: %s: %s", type(exc).__name__, exc)
                await self.send_control({"type": "error", "message": f"Gemini: {type(exc).__name__}"})
                await asyncio.sleep(delay)
                delay = min(delay * 2, RECONNECT_DELAY_MAX_SECONDS)
            finally:
                self.session = None
            await self.send_control({"type": "reconnecting"})

    async def receive_from_gemini(self, session) -> None:
        # session.receive() ends after each completed turn, so loop over turns.
        while True:
            async for message in session.receive():
                if message.session_resumption_update:
                    update = message.session_resumption_update
                    if update.resumable and update.new_handle:
                        self.resume_handle = update.new_handle

                if message.go_away is not None:
                    log.info("Gemini GoAway received (time left: %s); reconnecting",
                             message.go_away.time_left)
                    return

                if message.tool_call:
                    await self.reject_tool_calls(session, message.tool_call)

                content = message.server_content
                if content is None:
                    continue

                if content.interrupted:
                    self.epoch = (self.epoch + 1) % 256
                    self.clear_audio_out()
                    log.info("Interrupted by user (epoch %d)", self.epoch)
                    await self.send_control({"type": "interrupted", "epoch": self.epoch})

                if content.model_turn and content.model_turn.parts:
                    for part in content.model_turn.parts:
                        blob = part.inline_data
                        if blob and blob.data:
                            for start in range(0, len(blob.data), MAX_AUDIO_FRAME):
                                self.audio_out.put_nowait((self.epoch, blob.data[start:start + MAX_AUDIO_FRAME]))

                if content.input_transcription and content.input_transcription.text:
                    log.info("User: %s", content.input_transcription.text)
                if content.output_transcription and content.output_transcription.text:
                    log.info("Gemini: %s", content.output_transcription.text)

                if content.turn_complete:
                    self.audio_out.put_nowait((self.epoch, None))

    async def reject_tool_calls(self, session, tool_call: types.LiveServerToolCall) -> None:
        responses = []
        for call in tool_call.function_calls or []:
            if call.name in ALLOWED_TOOLS:
                # Nothing is allowlisted today; add a handler here if that changes.
                result = {"error": f"{call.name} has no handler"}
            else:
                result = {"error": f"{call.name} is not supported by this device"}
            log.warning("Rejected function call %r", call.name)
            responses.append(types.FunctionResponse(id=call.id, name=call.name, response=result))
        if responses:
            await session.send_tool_response(function_responses=responses)


@app.get("/")
def health_check():
    return {
        "status": "ok",
        "message": "Gemini Live bridge is running",
        "model": LIVE_MODEL,
        "api_key_configured": bool(GEMINI_API_KEY),
    }


@app.websocket("/ws")
async def device_socket(ws: WebSocket):
    await ws.accept()
    peer = f"{ws.client.host}:{ws.client.port}" if ws.client else "unknown"
    log.info("Device connected from %s", peer)

    if not GEMINI_API_KEY:
        await ws.send_text(json.dumps({"type": "error", "message": "GEMINI_API_KEY is not set on the server"}))
        await ws.close(code=1011)
        log.error("Rejected device: GEMINI_API_KEY is not set")
        return

    bridge = DeviceBridge(ws, genai.Client(api_key=GEMINI_API_KEY))
    try:
        await bridge.run()
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        log.error("Bridge error: %s: %s", type(exc).__name__, exc)
    finally:
        if bridge.dropped_mic_frames:
            log.info("Dropped %d mic frames while Gemini was reconnecting", bridge.dropped_mic_frames)
        log.info("Device disconnected from %s", peer)
