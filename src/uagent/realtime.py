"""Realtime voice I/O mode for the ``uag realtime`` command.

This module keeps the realtime transport separate from the normal text CLI.
It streams microphone audio to OpenAI Realtime, xAI Grok Voice API, or Google
Gemini Multimodal Live API and plays returned PCM audio through the default speaker.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import queue
import ssl
import subprocess
import sys
import threading
import time
from typing import Any

from .i18n import _, detect_lang
from .realtime_audio import EchoProcessor

SAMPLE_RATE = 24_000
CHANNELS = 1
BLOCKSIZE = 240  # 10 ms; required by the WebRTC audio processor


def _openai_realtime_tools() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "name": "get_current_time",
            "description": "Get the current local date and time.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    ]


def _execute_openai_tool(name: str, arguments: dict[str, Any]) -> str:
    del arguments
    if name == "get_current_time":
        from datetime import datetime

        return json.dumps(
            {
                "name": name,
                "datetime": datetime.now().astimezone().isoformat(),
            },
            ensure_ascii=False,
        )
    return json.dumps({"error": f"Tool is not allowed: {name}"}, ensure_ascii=False)


def _provider() -> str:
    return (
        (
            os.getenv("UAGENT_AUDIO_REALTIME_PROVIDER")
            or os.getenv("UAGENT_PROVIDER")
            or "openai"
        )
        .strip()
        .lower()
    )


def _api_key() -> str:
    provider = _provider()
    if provider in {"grok", "xai"}:
        return (
            os.getenv("UAGENT_XAI_API_KEY")
            or os.getenv("UAGENT_GROK_API_KEY")
            or os.getenv("XAI_API_KEY")
            or ""
        ).strip()
    if provider in {"google", "gemini", "vertexai", "vertex"}:
        return (
            os.getenv("UAGENT_GEMINI_API_KEY")
            or os.getenv("UAGENT_GOOGLE_API_KEY")
            or os.getenv("UAGENT_VERTEXAI_API_KEY")
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
            or os.getenv("VERTEXAI_API_KEY")
            or ""
        ).strip()
    return (
        os.getenv("UAGENT_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
    ).strip()


def _openai_language_code(lang: str | None = None) -> str:
    """Normalize the display locale to OpenAI's ISO-639-1 language code."""
    value = (lang or detect_lang()).strip().lower().replace("-", "_")
    return value.split("_", 1)[0] or "en"


def _language_instructions() -> str:
    """Keep Realtime voice replies aligned with the CLI display language."""
    lang = _openai_language_code()
    if lang == "ja":
        return _(
            "Always respond in Japanese. Use Japanese for both speech and "
            "transcription unless the user explicitly requests another language."
        )
    return _(
        "Respond in the display language (%(lang)s) unless the user asks otherwise. "
        "Use the same language for spoken audio and the transcript."
    ) % {"lang": lang}


def _depname(provider: str) -> str:
    aliases = {"xai": "grok", "vertex": "vertexai", "gemini": "google"}
    normalized = aliases.get(provider, provider)
    keys = [
        f"UAGENT_{normalized.upper()}_REALTIME_DEPNAME",
        f"UAGENT_{provider.upper()}_REALTIME_DEPNAME",
    ]
    for key in keys:
        value = (os.getenv(key) or "").strip()
        if value:
            return value
    defaults = {
        "openai": "gpt-realtime-2",
        "azure": "gpt-realtime-2",
        "google": "gemini-3.1-flash-live-preview",
        "vertexai": "gemini-3.1-flash-live-preview",
        "grok": "grok-voice-latest",
    }
    return defaults.get(normalized, "")


def _gemini_setup_message(model: str, voice: str = "Puck") -> dict[str, Any]:
    base_prompt = _("You are a helpful voice assistant.")
    return {
        "setup": {
            "model": f"models/{model}",
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": voice,
                        },
                    },
                },
            },
            "systemInstruction": {
                "parts": [
                    {
                        "text": f"{base_prompt} " + _language_instructions(),
                    }
                ]
            },
        }
    }


def _realtime_config(provider: str, key: str) -> tuple[str, dict[str, str]]:
    """Return the provider WebSocket URL and authentication headers."""
    normalized = {"xai": "grok", "vertex": "vertexai", "gemini": "google"}.get(
        provider, provider
    )
    if normalized in {"google", "vertexai"}:
        host = "generativelanguage.googleapis.com"
        return (
            f"wss://{host}/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key={key}",
            {},
        )
    host = "api.x.ai" if normalized == "grok" else "api.openai.com"
    return (
        f"wss://{host}/v1/realtime?model={_depname(normalized)}",
        {"Authorization": f"Bearer {key}"},
    )


def _voice(provider: str) -> str:
    if provider in {"grok", "xai"}:
        return (os.getenv("UAGENT_GROK_REALTIME_VOICE") or "Ara").strip()
    if provider in {"google", "gemini", "vertexai", "vertex"}:
        return (
            os.getenv("UAGENT_GEMINI_REALTIME_VOICE")
            or os.getenv("UAGENT_GOOGLE_REALTIME_VOICE")
            or "Puck"
        ).strip()
    return (os.getenv("UAGENT_OPENAI_REALTIME_VOICE") or "alloy").strip()


def _ssl_context() -> ssl.SSLContext | None:
    verify = (os.getenv("UAGENT_SSL_VERIFY") or "1").strip().lower()
    try:
        from .providers.util_providers import is_ssl_verify_disabled

        if is_ssl_verify_disabled():
            verify = "0"
    except Exception:
        pass
    if verify in {"0", "false", "no", "off", "disable", "disabled"}:
        msg = _("Disabling Realtime TLS certificate verification.")
        print(f"[WARN] {msg}", file=sys.stderr)
        return ssl._create_unverified_context()
    return None


def _ensure_realtime_dependencies() -> tuple[Any, Any] | None:
    """Load realtime dependencies, installing missing packages on demand."""
    packages = ("sounddevice", "websockets")
    for package in packages:
        try:
            __import__(package)
        except ImportError:
            msg = _("Auto-installing %(package)s...") % {"package": package}
            print(f"[INFO] {msg}", file=sys.stderr)
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", package],
                check=False,
            )
            if result.returncode != 0:
                msg = _("Failed to auto-install %(package)s.") % {"package": package}
                print(f"[ERROR] {msg}", file=sys.stderr)
                return None
    try:
        import sounddevice as sd  # type: ignore
        import websockets  # type: ignore
    except ImportError as exc:
        msg = _("Cannot load realtime dependencies: %(exc)s") % {"exc": exc}
        print(f"[ERROR] {msg}", file=sys.stderr)
        return None

    try:
        __import__("pywebrtc_audio")
    except ImportError:
        msg = _("Auto-installing AEC3 backend...")
        print(f"[INFO] {msg}", file=sys.stderr)
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "pywebrtc-audio"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            msg = _("Cannot install AEC3 backend, continuing with passthrough.")
            print(f"[WARN] {msg}", file=sys.stderr)
            details = (result.stderr or result.stdout or "").strip().splitlines()
            if details:
                detail_msg = (
                    details[-1].decode()
                    if isinstance(details[-1], bytes)
                    else str(details[-1])
                )
                print(f"[WARN] AEC3 install detail: {detail_msg}", file=sys.stderr)
    return sd, websockets


async def _run_gemini_session(websockets: Any, sd: Any, key: str) -> None:
    provider = _provider()
    depname = _depname(provider)
    url, headers = _realtime_config(provider, key)
    tls_context = _ssl_context()

    gemini_rate = SAMPLE_RATE  # 24,000 Hz for 24kHz mono PCM16
    gemini_blocksize = BLOCKSIZE  # 10ms at 24kHz (240 samples)
    audio_in: queue.Queue[bytes] = queue.Queue(maxsize=50)
    audio_out: queue.Queue[bytes] = queue.Queue(maxsize=100)
    stopping = threading.Event()
    echo = EchoProcessor(gemini_rate)
    output_buffer = bytearray()
    output_buffer_lock = threading.Lock()
    last_assistant_text = ""
    last_assistant_print_at = 0.0

    aec_status = _("Enabled") if echo.enabled else _("Disabled (passthrough)")
    print(f"[INFO] AEC: {aec_status}", file=sys.stderr)

    def on_input(indata: Any, frames: int, time_info: Any, status: Any) -> None:
        del frames, time_info
        try:
            audio_in.put_nowait(echo.capture(bytes(indata)))
        except queue.Full:
            pass

    def on_output(outdata: Any, frames: int, time_info: Any, status: Any) -> None:
        del frames, time_info
        with output_buffer_lock:
            try:
                while True:
                    output_buffer.extend(audio_out.get_nowait())
            except queue.Empty:
                pass
            output_size = len(outdata)
            data = output_buffer[:output_size]
            del output_buffer[:output_size]
        played = data + b"\x00" * (len(outdata) - len(data))
        if data:
            echo.reference(played)
        else:
            echo.clear_reference()
        outdata[:] = played

    connect_kwargs: dict[str, Any] = {"additional_headers": headers}
    if tls_context is not None:
        connect_kwargs["ssl"] = tls_context

    async with websockets.connect(url, **connect_kwargs) as ws:
        voice_name = _voice(provider)
        setup_msg = _gemini_setup_message(depname, voice=voice_name)
        await ws.send(json.dumps(setup_msg))
        msg = _(
            "Started Realtime (Gemini/Google) voice I/O mode. Press Ctrl+C to exit."
        )
        print(f"[INFO] {msg}")

        with (
            sd.InputStream(
                samplerate=gemini_rate,
                channels=CHANNELS,
                dtype="int16",
                blocksize=gemini_blocksize,
                callback=on_input,
            ),
            sd.RawOutputStream(
                samplerate=gemini_rate,
                channels=CHANNELS,
                dtype="int16",
                blocksize=gemini_blocksize,
                callback=on_output,
            ),
        ):

            async def send_audio() -> None:
                while not stopping.is_set():
                    try:
                        chunk = await asyncio.to_thread(audio_in.get, True, 0.1)
                    except queue.Empty:
                        continue
                    payload = {
                        "realtimeInput": {
                            "audio": {
                                "mimeType": f"audio/pcm;rate={gemini_rate}",
                                "data": base64.b64encode(chunk).decode("ascii"),
                            }
                        }
                    }
                    await ws.send(json.dumps(payload))

            sender = asyncio.create_task(send_audio())
            try:
                async for raw in ws:
                    event = json.loads(raw)
                    server_content = event.get("serverContent", {})
                    model_turn = server_content.get("modelTurn", {})
                    parts = model_turn.get("parts", [])
                    for part in parts:
                        inline_data = part.get("inlineData", {})
                        if inline_data.get("mimeType", "").startswith("audio/pcm"):
                            pcm_data = base64.b64decode(inline_data.get("data", ""))
                            try:
                                audio_out.put_nowait(pcm_data)
                            except queue.Full:
                                pass
                        text = (part.get("text") or "").strip()
                        now = time.monotonic()
                        if text and not (
                            text == last_assistant_text
                            and now - last_assistant_print_at < 2.0
                        ):
                            print(f"\n[assistant] {text}")
                            last_assistant_text = text
                            last_assistant_print_at = now
            finally:
                stopping.set()
                sender.cancel()
                await asyncio.gather(sender, return_exceptions=True)


def run() -> int:
    """Run the realtime microphone/speaker loop."""
    provider = _provider()
    key = _api_key()
    if not key:
        if provider in {"grok", "xai"}:
            env_names = "UAGENT_XAI_API_KEY or XAI_API_KEY"
        elif provider in {"google", "gemini", "vertexai", "vertex"}:
            env_names = "UAGENT_GEMINI_API_KEY or GEMINI_API_KEY"
        else:
            env_names = "UAGENT_OPENAI_API_KEY or OPENAI_API_KEY"
        msg = _("%(env_names)s is required.") % {"env_names": env_names}
        print(f"[ERROR] {msg}", file=sys.stderr)
        return 2

    dependencies = _ensure_realtime_dependencies()
    if dependencies is None:
        return 2
    sd, websockets = dependencies

    async def session() -> None:
        if provider in {"google", "gemini", "vertexai", "vertex"}:
            await _run_gemini_session(websockets, sd, key)
            return
        if provider not in {"openai", "grok", "xai"}:
            msg = _("Realtime adapter for %(provider)s is not implemented.") % {
                "provider": provider
            }
            print(f"[ERROR] {msg}", file=sys.stderr)
            return
        url, headers = _realtime_config(provider, key)
        tls_context = _ssl_context()
        audio_in: queue.Queue[bytes] = queue.Queue(maxsize=50)
        audio_out: queue.Queue[bytes] = queue.Queue(maxsize=100)
        stopping = threading.Event()
        echo = EchoProcessor(SAMPLE_RATE)
        output_buffer = bytearray()
        output_buffer_lock = threading.Lock()
        last_assistant_text = ""
        last_assistant_print_at = 0.0
        aec_status = _("Enabled") if echo.enabled else _("Disabled (passthrough)")
        print(f"[INFO] AEC: {aec_status}", file=sys.stderr)

        def on_input(indata: Any, frames: int, time_info: Any, status: Any) -> None:
            del frames, time_info
            if status:
                print(f"[AUDIO] {status}", file=sys.stderr)
            try:
                audio_in.put_nowait(echo.capture(bytes(indata)))
            except queue.Full:
                pass

        def on_output(outdata: Any, frames: int, time_info: Any, status: Any) -> None:
            del frames, time_info
            if status:
                print(f"[AUDIO] {status}", file=sys.stderr)
            with output_buffer_lock:
                try:
                    while True:
                        output_buffer.extend(audio_out.get_nowait())
                except queue.Empty:
                    pass
                output_size = len(outdata)
                data = output_buffer[:output_size]
                del output_buffer[:output_size]
            played = data + b"\x00" * (len(outdata) - len(data))
            if data:
                echo.reference(played)
            else:
                echo.clear_reference()
            outdata[:] = played

        connect_kwargs: dict[str, Any] = {"additional_headers": headers}
        if tls_context is not None:
            connect_kwargs["ssl"] = tls_context
        async with websockets.connect(url, **connect_kwargs) as ws:
            base_prompt = _("You are a helpful voice assistant.")
            await ws.send(
                json.dumps(
                    {
                        "type": "session.update",
                        "session": {
                            "type": "realtime",
                            "output_modalities": ["audio"],
                            "tools": (
                                _openai_realtime_tools() if provider == "openai" else []
                            ),
                            "instructions": (
                                f"{base_prompt} " + _language_instructions()
                            ),
                            "audio": {
                                "input": {
                                    "format": {
                                        "type": "audio/pcm",
                                        "rate": SAMPLE_RATE,
                                    },
                                    "transcription": {
                                        "model": "gpt-4o-mini-transcribe",
                                        "language": _openai_language_code(),
                                    },
                                    "turn_detection": {
                                        "type": "server_vad",
                                        "threshold": 0.5,
                                        "prefix_padding_ms": 300,
                                        "silence_duration_ms": 700,
                                    },
                                },
                                "output": {
                                    "format": {
                                        "type": "audio/pcm",
                                        "rate": SAMPLE_RATE,
                                    },
                                    "voice": _voice(provider),
                                },
                            },
                        },
                    }
                )
            )
            msg = _("Started Realtime voice I/O mode. Press Ctrl+C to exit.")
            print(f"[INFO] {msg}")

            with (
                sd.InputStream(
                    samplerate=SAMPLE_RATE,
                    channels=CHANNELS,
                    dtype="int16",
                    blocksize=BLOCKSIZE,
                    callback=on_input,
                ),
                sd.RawOutputStream(
                    samplerate=SAMPLE_RATE,
                    channels=CHANNELS,
                    dtype="int16",
                    blocksize=BLOCKSIZE,
                    callback=on_output,
                ),
            ):

                async def send_audio() -> None:
                    while not stopping.is_set():
                        try:
                            chunk = await asyncio.to_thread(audio_in.get, True, 0.1)
                        except queue.Empty:
                            continue
                        await ws.send(
                            json.dumps(
                                {
                                    "type": "input_audio_buffer.append",
                                    "audio": base64.b64encode(chunk).decode("ascii"),
                                }
                            )
                        )

                sender = asyncio.create_task(send_audio())
                audio_debug = (
                    os.getenv("UAGENT_REALTIME_AUDIO_DEBUG") or ""
                ).strip().lower() in {"1", "true", "yes", "on"}

                async def debug_audio() -> None:
                    while not stopping.is_set():
                        await asyncio.sleep(1.0)
                        print(
                            f"[AUDIO DEBUG] {echo.debug_snapshot()}",
                            file=sys.stderr,
                        )

                debugger = asyncio.create_task(debug_audio()) if audio_debug else None
                try:
                    async for raw in ws:
                        event = json.loads(raw)
                        kind = event.get("type", "")
                        if kind == "response.output_audio.delta":
                            try:
                                audio_out.put_nowait(base64.b64decode(event["delta"]))
                            except queue.Full:
                                pass
                        elif (
                            kind == "response.function_call_arguments.done"
                            and provider == "openai"
                        ):
                            name = str(event.get("name") or "")
                            call_id = str(event.get("call_id") or "")
                            try:
                                arguments = json.loads(event.get("arguments") or "{}")
                                if not isinstance(arguments, dict):
                                    arguments = {}
                                result = _execute_openai_tool(name, arguments)
                            except Exception as exc:
                                result = json.dumps(
                                    {"error": str(exc)}, ensure_ascii=False
                                )
                            await ws.send(
                                json.dumps(
                                    {
                                        "type": "conversation.item.create",
                                        "item": {
                                            "type": "function_call_output",
                                            "call_id": call_id,
                                            "output": result,
                                        },
                                    }
                                )
                            )
                            await ws.send(json.dumps({"type": "response.create"}))
                        elif kind == "response.output_audio_transcript.done":
                            text = (event.get("transcript") or "").strip()
                            now = time.monotonic()
                            if text and not (
                                text == last_assistant_text
                                and now - last_assistant_print_at < 2.0
                            ):
                                print(f"\n[assistant] {text}")
                                last_assistant_text = text
                                last_assistant_print_at = now
                        elif (
                            kind
                            == "conversation.item.input_audio_transcription.completed"
                        ):
                            text = (event.get("transcript") or "").strip()
                            if text:
                                print(f"\n[user] {text}")
                        elif kind == "error":
                            print(
                                f"[ERROR] Realtime API: {event.get('error')}",
                                file=sys.stderr,
                            )
                finally:
                    stopping.set()
                    sender.cancel()
                    tasks = [sender]
                    if debugger is not None:
                        debugger.cancel()
                        tasks.append(debugger)
                    await asyncio.gather(*tasks, return_exceptions=True)

    try:
        asyncio.run(session())
    except KeyboardInterrupt:
        msg = _("Realtime mode exited.")
        print(f"\n[INFO] {msg}")
    except Exception as exc:
        msg = _("Could not start Realtime mode: %(exc)s") % {"exc": exc}
        print(f"[ERROR] {msg}", file=sys.stderr)
        return 1
    return 0
