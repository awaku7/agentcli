"""Realtime voice I/O mode for the ``uag realtime`` command.

This module intentionally keeps the realtime transport separate from the normal
text CLI.  It streams microphone audio to OpenAI Realtime or xAI's Grok Voice
Agent API and plays returned PCM audio through the default speaker.
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
from typing import Any

from .i18n import detect_lang
from .realtime_audio import EchoProcessor


SAMPLE_RATE = 24_000
CHANNELS = 1
BLOCKSIZE = 240  # 10 ms; required by the WebRTC audio processor


def _api_key() -> str:
    provider = _provider()
    if provider in {"grok", "xai"}:
        return (
            os.getenv("UAGENT_XAI_API_KEY")
            or os.getenv("UAGENT_GROK_API_KEY")
            or os.getenv("XAI_API_KEY")
            or ""
        ).strip()
    return (
        os.getenv("UAGENT_OPENAI_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or ""
    ).strip()


def _provider() -> str:
    return (
        os.getenv("UAGENT_AUDIO_REALTIME_PROVIDER")
        or os.getenv("UAGENT_PROVIDER")
        or "openai"
    ).strip().lower()


def _openai_language_code(lang: str | None = None) -> str:
    """Normalize the display locale to OpenAI's ISO-639-1 language code."""
    value = (lang or detect_lang()).strip().lower().replace("-", "_")
    # Display locales may include a region (for example zh_CN or pt_BR),
    # while OpenAI's language fields expect the two-letter base code.
    return value.split("_", 1)[0] or "en"


def _language_instructions() -> str:
    """Keep Realtime voice replies aligned with the CLI display language."""
    lang = _openai_language_code()
    return (
        f"Respond in the display language ({lang}) unless the user asks otherwise. "
        "Use the same language for spoken audio and the transcript."
    )


def _depname(provider: str) -> str:
    # Realtime has its own deployment setting, with provider-specific fallbacks.
    aliases = {"xai": "grok", "vertex": "vertexai"}
    normalized = aliases.get(provider, provider)
    keys = [f"UAGENT_{normalized.upper()}_REALTIME_DEPNAME"]
    for key in keys:
        value = (os.getenv(key) or "").strip()
        if value:
            return value
    defaults = {
        "openai": "gpt-realtime-2",
        "azure": "gpt-realtime-2",
        "gemini": "gemini-2.0-flash-live-001",
        "vertexai": "gemini-2.0-flash-live-001",
        "grok": "grok-voice-latest",
    }
    return defaults.get(normalized, "")


def _realtime_config(provider: str, key: str) -> tuple[str, dict[str, str]]:
    """Return the provider WebSocket URL and authentication headers."""
    normalized = {"xai": "grok"}.get(provider, provider)
    host = "api.x.ai" if normalized == "grok" else "api.openai.com"
    return (
        f"wss://{host}/v1/realtime?model={_depname(normalized)}",
        {"Authorization": f"Bearer {key}"},
    )


def _voice(provider: str) -> str:
    if provider in {"grok", "xai"}:
        return (os.getenv("UAGENT_GROK_REALTIME_VOICE") or "Ara").strip()
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
        print("[WARN] Realtime TLS証明書検証を無効化しています。", file=sys.stderr)
        return ssl._create_unverified_context()
    return None


def _ensure_realtime_dependencies() -> tuple[Any, Any] | None:
    """Load realtime dependencies, installing missing packages on demand."""
    packages = ("sounddevice", "websockets")
    for package in packages:
        try:
            __import__(package)
        except ImportError:
            print(f"[INFO] {package} を自動インストールしています...", file=sys.stderr)
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", package],
                check=False,
            )
            if result.returncode != 0:
                print(f"[ERROR] {package} の自動インストールに失敗しました。", file=sys.stderr)
                return None
    try:
        import sounddevice as sd  # type: ignore
        import websockets  # type: ignore
    except ImportError as exc:
        print(f"[ERROR] realtime依存関係を読み込めません: {exc}", file=sys.stderr)
        return None

    # AEC is optional at runtime, but try to install its backend automatically.
    try:
        __import__("webrtc_audio_processing")
    except ImportError:
        print("[INFO] AECバックエンドを自動インストールしています...", file=sys.stderr)
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "webrtc-audio-processing"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(
                "[WARN] AECバックエンドをインストールできないため、passthroughで続行します。",
                file=sys.stderr,
            )
    return sd, websockets


def run() -> int:
    """Run the realtime microphone/speaker loop."""
    provider = _provider()
    key = _api_key()
    if not key:
        env_names = (
            "UAGENT_XAI_API_KEY または XAI_API_KEY"
            if provider in {"grok", "xai"}
            else "UAGENT_OPENAI_API_KEY または OPENAI_API_KEY"
        )
        print(f"[ERROR] {env_names} が必要です。", file=sys.stderr)
        return 2

    dependencies = _ensure_realtime_dependencies()
    if dependencies is None:
        return 2
    sd, websockets = dependencies

    async def session() -> None:
        if provider not in {"openai", "grok", "xai"}:
            print(
                f"[ERROR] realtime の {provider} アダプターは未実装です。",
                file=sys.stderr,
            )
            return
        url, headers = _realtime_config(provider, key)
        tls_context = _ssl_context()
        audio_in: queue.Queue[bytes] = queue.Queue(maxsize=50)
        audio_out: queue.Queue[bytes] = queue.Queue(maxsize=100)
        stopping = threading.Event()
        echo = EchoProcessor(SAMPLE_RATE)
        print(
            "[INFO] AEC: " + ("有効" if echo.enabled else "無効（passthrough）"),
            file=sys.stderr,
        )

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
            try:
                data = audio_out.get_nowait()
            except queue.Empty:
                data = b""
            outdata[:] = b"\x00" * len(outdata)
            if data:
                outdata[: min(len(outdata), len(data))] = data[: len(outdata)]

        connect_kwargs: dict[str, Any] = {"additional_headers": headers}
        # websockets rejects an explicit ssl=None for wss:// URLs; omit it
        # when certificate verification is enabled so the library uses its
        # default verified TLS context.
        if tls_context is not None:
            connect_kwargs["ssl"] = tls_context
        async with websockets.connect(url, **connect_kwargs) as ws:
            await ws.send(json.dumps({
                "type": "session.update",
                "session": {
                    "type": "realtime",
                    "output_modalities": ["audio"],
                    "instructions": (
                        "You are a helpful voice assistant. "
                        + _language_instructions()
                    ),
                    "audio": {
                        "input": {
                            "format": {"type": "audio/pcm", "rate": SAMPLE_RATE},
                            "turn_detection": {"type": "server_vad"},
                        },
                        "output": {
                            "format": {"type": "audio/pcm"},
                            "voice": _voice(provider),
                        },
                    },
                },
            }))
            print("[INFO] Realtime 音声入出力モードを開始しました。終了: Ctrl+C")

            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                blocksize=BLOCKSIZE,
                callback=on_input,
            ), sd.RawOutputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                blocksize=BLOCKSIZE,
                callback=on_output,
            ):
                async def send_audio() -> None:
                    while not stopping.is_set():
                        try:
                            chunk = await asyncio.to_thread(audio_in.get, True, 0.1)
                        except queue.Empty:
                            continue
                        await ws.send(json.dumps({
                            "type": "input_audio_buffer.append",
                            "audio": base64.b64encode(chunk).decode("ascii"),
                        }))

                sender = asyncio.create_task(send_audio())
                try:
                    async for raw in ws:
                        event = json.loads(raw)
                        kind = event.get("type", "")
                        if kind == "response.output_audio.delta":
                            for frame in echo.reverse(base64.b64decode(event["delta"])):
                                try:
                                    audio_out.put_nowait(frame)
                                except queue.Full:
                                    pass
                        elif kind == "response.output_audio_transcript.done":
                            text = (event.get("transcript") or "").strip()
                            if text:
                                print(f"\n[assistant] {text}")
                        elif kind == "conversation.item.input_audio_transcription.completed":
                            text = (event.get("transcript") or "").strip()
                            if text:
                                print(f"\n[user] {text}")
                        elif kind == "error":
                            print(f"[ERROR] Realtime API: {event.get('error')}", file=sys.stderr)
                finally:
                    stopping.set()
                    sender.cancel()
                    await asyncio.gather(sender, return_exceptions=True)

    try:
        asyncio.run(session())
    except KeyboardInterrupt:
        print("\n[INFO] Realtime モードを終了しました。")
    except Exception as exc:
        print(f"[ERROR] Realtime モードを開始できませんでした: {exc}", file=sys.stderr)
        return 1
    return 0
