"""Optional Amazon Nova Sonic realtime adapter.

Imported only when UAGENT_AUDIO_REALTIME_PROVIDER=bedrock so existing realtime
providers do not require the experimental Bedrock SDK.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import queue
import sys
import uuid
from typing import Any

INPUT_RATE = 16_000
OUTPUT_RATE = 24_000
CHANNELS = 1
BLOCKSIZE = 1024


def _json_event(event: dict[str, Any]) -> str:
    return json.dumps({"event": event}, ensure_ascii=False)


async def run_session(sd: Any) -> None:
    try:
        from aws_sdk_bedrock_runtime.client import (
            BedrockRuntimeClient,
            InvokeModelWithBidirectionalStreamOperationInput,
        )
        from aws_sdk_bedrock_runtime.config import Config
        from aws_sdk_bedrock_runtime.models import (
            BidirectionalInputPayloadPart,
            InvokeModelWithBidirectionalStreamInputChunk,
        )
        from smithy_aws_core.identity.environment import EnvironmentCredentialsResolver
    except ImportError as exc:
        print(
            "[ERROR] Bedrock realtime requires the optional AWS SDK: "
            "pip install aws_sdk_bedrock_runtime",
            file=sys.stderr,
        )
        raise RuntimeError("Optional Bedrock realtime SDK is not installed") from exc

    region = (os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1").strip()
    model = (os.getenv("UAGENT_BEDROCK_REALTIME_DEPNAME") or "amazon.nova-sonic-v1:0").strip()
    voice = (os.getenv("UAGENT_BEDROCK_REALTIME_VOICE") or "matthew").strip()
    prompt_name = str(uuid.uuid4())
    system_name = str(uuid.uuid4())
    audio_name = str(uuid.uuid4())
    audio_in: queue.Queue[bytes] = queue.Queue(maxsize=80)
    audio_out: queue.Queue[bytes] = queue.Queue(maxsize=120)
    stopping = asyncio.Event()

    def on_input(indata: Any, frames: int, time_info: Any, status: Any) -> None:
        del frames, time_info
        if status:
            print(f"[AUDIO] {status}", file=sys.stderr)
        try:
            audio_in.put_nowait(bytes(indata))
        except queue.Full:
            pass

    output_buffer = bytearray()

    def on_output(outdata: Any, frames: int, time_info: Any, status: Any) -> None:
        del frames, time_info
        if status:
            print(f"[AUDIO] {status}", file=sys.stderr)
        while True:
            try:
                output_buffer.extend(audio_out.get_nowait())
            except queue.Empty:
                break
        n = len(outdata)
        outdata[:] = bytes(output_buffer[:n]).ljust(n, b"\x00")
        del output_buffer[:n]

    config = Config(
        endpoint_uri=f"https://bedrock-runtime.{region}.amazonaws.com",
        region=region,
        aws_credentials_identity_resolver=EnvironmentCredentialsResolver(),
    )
    client = BedrockRuntimeClient(config=config)
    stream = await client.invoke_model_with_bidirectional_stream(
        InvokeModelWithBidirectionalStreamOperationInput(model_id=model)
    )

    async def send_event(event: dict[str, Any]) -> None:
        chunk = InvokeModelWithBidirectionalStreamInputChunk(
            value=BidirectionalInputPayloadPart(bytes_=_json_event(event).encode())
        )
        await stream.input_stream.send(chunk)

    async def receive() -> None:
        try:
            while not stopping.is_set():
                output = await stream.await_output()
                result = await output[1].receive()
                raw = getattr(getattr(result, "value", None), "bytes_", None)
                if not raw:
                    continue
                event = json.loads(raw.decode("utf-8")).get("event", {})
                if "audioOutput" in event:
                    audio_out.put_nowait(base64.b64decode(event["audioOutput"].get("content", "")))
                elif "textOutput" in event:
                    text = str(event["textOutput"].get("content", "")).strip()
                    if text:
                        print(f"\n[assistant] {text}")
        except (asyncio.CancelledError, StopAsyncIteration):
            pass

    async def send_audio() -> None:
        while not stopping.is_set():
            data = await asyncio.to_thread(audio_in.get)
            await send_event({"audioInput": {"promptName": prompt_name, "contentName": audio_name, "content": base64.b64encode(data).decode()}})

    print(f"[INFO] Bedrock Nova Sonic realtime started ({model}, {region}). Press Ctrl+C to exit.")
    receiver = asyncio.create_task(receive())
    sender = asyncio.create_task(send_audio())
    try:
        await send_event({"sessionStart": {"inferenceConfiguration": {"maxTokens": 1024, "topP": 0.9, "temperature": 0.7}}})
        await send_event({"promptStart": {"promptName": prompt_name, "textOutputConfiguration": {"mediaType": "text/plain"}, "audioOutputConfiguration": {"mediaType": "audio/lpcm", "sampleRateHertz": OUTPUT_RATE, "sampleSizeBits": 16, "channelCount": 1, "voiceId": voice, "encoding": "base64", "audioType": "SPEECH"}}})
        await send_event({"contentStart": {"promptName": prompt_name, "contentName": system_name, "type": "TEXT", "interactive": False, "role": "SYSTEM", "textInputConfiguration": {"mediaType": "text/plain"}}})
        await send_event({"textInput": {"promptName": prompt_name, "contentName": system_name, "content": "You are a helpful voice assistant."}})
        await send_event({"contentEnd": {"promptName": prompt_name, "contentName": system_name}})
        await send_event({"contentStart": {"promptName": prompt_name, "contentName": audio_name, "type": "AUDIO", "interactive": True, "role": "USER", "audioInputConfiguration": {"mediaType": "audio/lpcm", "sampleRateHertz": INPUT_RATE, "sampleSizeBits": 16, "channelCount": 1, "audioType": "SPEECH", "encoding": "base64"}}})
        with sd.RawInputStream(samplerate=INPUT_RATE, channels=CHANNELS, dtype="int16", blocksize=BLOCKSIZE, callback=on_input), sd.RawOutputStream(samplerate=OUTPUT_RATE, channels=CHANNELS, dtype="int16", blocksize=BLOCKSIZE, callback=on_output):
            await asyncio.gather(receiver, sender)
    finally:
        stopping.set()
        sender.cancel()
        receiver.cancel()
        await asyncio.gather(sender, receiver, return_exceptions=True)
        try:
            await send_event({"contentEnd": {"promptName": prompt_name, "contentName": audio_name}})
            await send_event({"promptEnd": {"promptName": prompt_name}})
            await send_event({"sessionEnd": {}})
            await stream.input_stream.close()
        except Exception:
            pass
