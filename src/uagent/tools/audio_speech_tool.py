from __future__ import annotations

from pathlib import Path
from typing import Any

import requests

from .._pip_auto import install_with_status as _auto_install
from ..env_utils import env_get
from ..llmcapa_util import check_audio_output_support
from .openers import open_image_with_default_app
from .arg_util import get_float, get_str
from .context import get_callbacks
from .i18n_helper import make_tool_translator
from .response_util import make_response
from .safe_file_ops_extras import ensure_within_workdir

_ = make_tool_translator(__file__)

BUSY_LABEL = True

# xAI TTS limits / defaults (https://docs.x.ai)
_GROK_TTS_URL_DEFAULT = "https://api.x.ai/v1/tts"
_GROK_TEXT_MAX = 15000
_GROK_SPEED_MIN = 0.7
_GROK_SPEED_MAX = 1.5
_GROK_CODECS = frozenset({"mp3", "wav", "pcm", "mulaw", "alaw"})
_GROK_SAMPLE_RATES = frozenset({8000, 16000, 22050, 24000, 44100, 48000})
_OPENAI_FORMATS = frozenset({"mp3", "opus", "aac", "flac", "wav", "pcm"})

TOOL_SPEC: dict[str, Any] = {
    "load_order": 8000,
    "type": "function",
    "tool_genre": "media",
    "x_parallel_safe": True,
    "function": {
        "name": "audio_speech",
        "description": _(
            "tool.description",
            default=(
                "Convert text to speech, save the audio as a file, and return the saved path."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "audio_speech",
                "audio speech",
                "audio",
                "voice",
                "speech",
                "sound",
            ],
        ),
        "x_search_terms_en": [
            "audio_speech",
            "audio speech",
            "audio",
            "voice",
            "speech",
            "sound",
            "tts",
            "text to speech",
            "grok tts",
            "xai tts",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": _(
                        "param.text.description",
                        default="Text to synthesize into speech.",
                    ),
                },
                "output_path": {
                    "type": "string",
                    "description": _(
                        "param.output_path.description",
                        default="Path where the generated audio file will be saved.",
                    ),
                },
                "model": {
                    "type": "string",
                    "description": _(
                        "param.model.description",
                        default=(
                            "Speech model name. If omitted, the provider default or configured deployment name is used."
                        ),
                    ),
                },
                "voice": {
                    "type": "string",
                    "description": _(
                        "param.voice.description",
                        default=(
                            "Voice id/name. OpenAI default: alloy. Grok/xAI default: eve."
                        ),
                    ),
                    "default": "alloy",
                },
                "language": {
                    "type": "string",
                    "description": _(
                        "param.language.description",
                        default=(
                            "BCP-47 language tag for Grok/xAI TTS (e.g. en, ja, auto). Ignored by other providers."
                        ),
                    ),
                    "default": "auto",
                },
                "response_format": {
                    "type": "string",
                    "enum": ["mp3", "opus", "aac", "flac", "wav", "pcm", "mulaw", "alaw"],
                    "default": "mp3",
                    "description": _(
                        "param.response_format.description",
                        default=(
                            "Audio file format. OpenAI: mp3/opus/aac/flac/wav/pcm. "
                            "Grok/xAI: mp3/wav/pcm/mulaw/alaw."
                        ),
                    ),
                },
                "speed": {
                    "type": "number",
                    "description": _(
                        "param.speed.description",
                        default=(
                            "Playback speed multiplier (e.g. 1.0). Grok/xAI range: 0.7-1.5."
                        ),
                    ),
                    "default": 1.0,
                },
                "instructions": {
                    "type": "string",
                    "description": _(
                        "param.instructions.description",
                        default="Optional instructions for the speech style.",
                    ),
                },
            },
            "required": ["text", "output_path"],
            "additionalProperties": False,
        },
    },
}


def _env_first(keys: list[str], *, required: bool = False, default: str = "") -> str:
    for key in keys:
        value = (env_get(key) or "").strip()
        if value:
            return value
    if required:
        raise RuntimeError(f"Missing required env var(s): {', '.join(keys)}")
    return default


def _provider() -> str:
    provider = _env_first(
        ["UAGENT_AUDIO_SPEECH_PROVIDER", "UAGENT_PROVIDER"], default="openai"
    )
    provider = provider.strip().lower()
    if provider in ("xai",):
        provider = "grok"
    if provider not in ("openai", "azure", "gemini", "vertexai", "grok"):
        raise RuntimeError(
            _(
                "err.unsupported_provider",
                default="Unsupported provider for audio speech: {provider!r}",
            ).format(provider=provider)
        )
    return provider


def _model(provider: str) -> str:
    if provider == "azure":
        return _env_first(
            ["UAGENT_AZURE_SPEECH_DEPNAME"],
            required=True,
        )
    if provider in ("gemini", "vertexai"):
        return _env_first(
            ["UAGENT_GEMINI_SPEECH_DEPNAME", "UAGENT_GEMINI_MODEL"],
            default="ja-JP-Neural2-B",
        )
    if provider == "grok":
        return _env_first(
            ["UAGENT_GROK_SPEECH_DEPNAME", "UAGENT_GROK_TTS_MODEL"],
            default="grok-tts",
        )
    return _env_first(
        ["UAGENT_OPENAI_SPEECH_DEPNAME"],
        default="gpt-4o-mini-tts",
    )


def _ssl_verify_enabled() -> bool:
    """Match Grok HTTP SSL policy: honor util_providers + UAGENT_SSL_VERIFY."""
    try:
        from ..providers.util_providers import is_ssl_verify_disabled

        if is_ssl_verify_disabled():
            return False
    except Exception:
        pass
    v = (env_get("UAGENT_SSL_VERIFY") or "").strip().lower()
    # Default: verify on unless explicitly disabled (or util flag set above).
    if v in ("0", "false", "no", "off"):
        return False
    if v in ("1", "true", "yes", "on"):
        return True
    return True


def _make_client(provider: str):
    if provider in ("gemini", "vertexai", "grok"):
        return None
    try:
        from openai import AzureOpenAI, OpenAI
    except Exception as exc:
        raise RuntimeError(
            _(
                "err.openai_import",
                default="Failed to import openai package: {err}",
            ).format(err=repr(exc))
        )

    if provider == "azure":
        base_url = _env_first(["UAGENT_AZURE_BASE_URL"], required=True)
        api_key = _env_first(["UAGENT_AZURE_API_KEY"], required=True)
        api_version = _env_first(["UAGENT_AZURE_API_VERSION"], required=True)
        return AzureOpenAI(
            azure_endpoint=base_url.rstrip("/"),
            api_key=api_key,
            api_version=api_version,
        )

    api_key = _env_first(["UAGENT_OPENAI_API_KEY"], required=True)
    base_url = _env_first(
        ["UAGENT_OPENAI_BASE_URL"], default="https://api.openai.com/v1"
    )
    return OpenAI(api_key=api_key, base_url=base_url.rstrip("/"))


def _clamp_grok_speed(speed: float) -> float:
    try:
        s = float(speed)
    except Exception:
        s = 1.0
    if s < _GROK_SPEED_MIN:
        return _GROK_SPEED_MIN
    if s > _GROK_SPEED_MAX:
        return _GROK_SPEED_MAX
    return s


def _grok_tts_bytes(
    *,
    text: str,
    voice_id: str,
    language: str,
    speed: float,
    codec: str,
    sample_rate: int = 24000,
) -> bytes:
    """POST https://api.x.ai/v1/tts and return raw audio bytes."""
    api_key = _env_first(
        ["UAGENT_GROK_API_KEY", "XAI_API_KEY"],
        required=True,
    )
    # Optional session mirror: UAGENT_GROK_API_KEY -> XAI_API_KEY (do not persist).
    if api_key and not (env_get("XAI_API_KEY") or "").strip():
        try:
            import os

            os.environ["XAI_API_KEY"] = api_key
        except Exception:
            pass

    base = _env_first(
        ["UAGENT_GROK_BASE_URL", "UAGENT_GROK_TTS_BASE_URL"],
        default="https://api.x.ai/v1",
    ).rstrip("/")
    if base.endswith("/tts"):
        url = base
    else:
        url = f"{base}/tts"

    if sample_rate not in _GROK_SAMPLE_RATES:
        sample_rate = 24000

    body: dict[str, Any] = {
        "text": text,
        "language": language or "auto",
        "voice_id": voice_id or "eve",
        "speed": _clamp_grok_speed(speed),
        "output_format": {
            "codec": codec,
            "sample_rate": int(sample_rate),
        },
    }
    if codec == "mp3":
        body["output_format"]["bit_rate"] = 128000

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/octet-stream, application/json",
    }
    verify = _ssl_verify_enabled()
    resp = requests.post(url, json=body, headers=headers, timeout=120, verify=verify)
    if resp.status_code >= 400:
        detail = (resp.text or "")[:500]
        raise RuntimeError(f"xAI TTS HTTP {resp.status_code}: {detail}")

    ctype = (resp.headers.get("Content-Type") or "").lower()
    if "application/json" in ctype:
        data = resp.json()
        # timestamps mode returns base64 audio
        audio_b64 = data.get("audio") or data.get("audio_content")
        if not audio_b64:
            raise RuntimeError(f"xAI TTS JSON response missing audio: {list(data)[:20]}")
        import base64

        return base64.b64decode(audio_b64)
    return resp.content


def _mime_for_format(fmt: str) -> str:
    f = (fmt or "mp3").lower()
    if f == "mp3":
        return "audio/mpeg"
    if f == "pcm":
        return "audio/L16"
    if f == "mulaw":
        return "audio/basic"
    if f == "alaw":
        return "audio/PCMA"
    return f"audio/{f}"


def run_tool(args: dict[str, Any]) -> str:
    text = get_str(args, "text", "")
    output_path = get_str(args, "output_path", "")
    if not text:
        return make_response(False, _("err.text_empty", default="text is required"))
    if not output_path:
        return make_response(
            False, _("err.output_path_empty", default="output_path is required")
        )

    try:
        provider = _provider()
    except Exception as exc:
        return make_response(False, str(exc))

    model = get_str(args, "model", "") or _model(provider)
    default_voice = "eve" if provider == "grok" else "alloy"
    voice = get_str(args, "voice", default_voice) or default_voice
    response_format = (get_str(args, "response_format", "mp3") or "mp3").lower()
    speed = get_float(args, "speed", 1.0)
    instructions = get_str(args, "instructions", "")
    language = get_str(args, "language", "auto") or "auto"

    # llmcapa audio gate (catalog miss => allow; do not use completion max_tokens)
    gate_err = check_audio_output_support(model, provider)
    if gate_err:
        return make_response(False, gate_err)

    try:
        safe_out = ensure_within_workdir(output_path)
    except Exception as exc:
        return make_response(False, str(exc))

    Path(safe_out).parent.mkdir(parents=True, exist_ok=True)

    if provider == "grok":
        if len(text) > _GROK_TEXT_MAX:
            return make_response(
                False,
                _(
                    "err.grok_text_too_long",
                    default="text exceeds Grok TTS limit of {max} characters (got {n})",
                ).format(max=_GROK_TEXT_MAX, n=len(text)),
            )
        if response_format not in _GROK_CODECS:
            return make_response(
                False,
                _(
                    "err.grok_unsupported_format",
                    default=(
                        "Grok/xAI TTS does not support format {fmt!r}. "
                        "Use one of: mp3, wav, pcm, mulaw, alaw."
                    ),
                ).format(fmt=response_format),
            )
        try:
            audio = _grok_tts_bytes(
                text=text,
                voice_id=voice,
                language=language,
                speed=speed,
                codec=response_format,
            )
            Path(safe_out).write_bytes(audio)
        except Exception as exc:
            return make_response(
                False,
                _(
                    "err.speech_failed",
                    default="Audio speech generation failed: {err}",
                ).format(err=repr(exc)),
                data={"path": safe_out, "provider": provider, "model": model},
            )
    elif provider in ("gemini", "vertexai"):
        if not _auto_install(
            "google-cloud-texttospeech",
            "google.cloud.texttospeech",
            version_spec=">=2.36.0",
        ):
            return make_response(
                False, "google-cloud-texttospeech or certifi package is not installed."
            )
        from google.cloud import texttospeech

        try:
            # Use REST transport to avoid gRPC/ALPN issues with Python 3.14 on Windows
            from google.cloud.texttospeech_v1.services.text_to_speech.transports.rest import (
                TextToSpeechRestTransport,
            )
            from google.api_core import client_options
            import json

            # Handle credentials from UAGENT_GOOGLE_CREDENTIALS or standard env
            creds_data = _env_first(
                ["UAGENT_GOOGLE_CREDENTIALS", "GOOGLE_APPLICATION_CREDENTIALS"]
            )
            credentials = None
            if creds_data:
                if creds_data.strip().startswith("{"):
                    from google.oauth2 import service_account

                    credentials = service_account.Credentials.from_service_account_info(
                        json.loads(creds_data)
                    )
                elif Path(creds_data).exists():
                    from google.oauth2 import service_account

                    credentials = service_account.Credentials.from_service_account_file(
                        creds_data
                    )

            # Handle location-based endpoint
            location = _env_first(
                ["UAGENT_GOOGLE_LOCATION", "UAGENT_LOCATION", "GOOGLE_LOCATION"],
                default="global",
            )
            c_opts = None
            if location and location != "global":
                endpoint = f"{location}-texttospeech.googleapis.com"
                c_opts = client_options.ClientOptions(api_endpoint=endpoint)

            transport = TextToSpeechRestTransport(credentials=credentials)
            client = texttospeech.TextToSpeechClient(
                transport=transport, client_options=c_opts
            )

            synthesis_input = texttospeech.SynthesisInput(text=text)

            language_code = "ja-JP"
            if voice.lower() in (
                "alloy",
                "echo",
                "fable",
                "onyx",
                "nova",
                "shimmer",
                "puck",
                "aoede",
            ):
                voice = "ja-JP-Neural2-B"

            voice_params = texttospeech.VoiceSelectionParams(
                language_code=language_code, name=voice
            )

            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3, speaking_rate=speed
            )

            resp = client.synthesize_speech(
                input=synthesis_input, voice=voice_params, audio_config=audio_config
            )

            with open(safe_out, "wb") as f:
                f.write(resp.audio_content)
        except Exception as exc:
            return make_response(
                False,
                _(
                    "err.speech_failed",
                    default="Audio speech generation failed: {err}",
                ).format(err=repr(exc)),
                data={"path": safe_out, "provider": provider, "model": model},
            )
    else:
        if response_format not in _OPENAI_FORMATS:
            return make_response(
                False,
                _(
                    "err.openai_unsupported_format",
                    default=(
                        "OpenAI/Azure TTS does not support format {fmt!r}. "
                        "Use one of: mp3, opus, aac, flac, wav, pcm."
                    ),
                ).format(fmt=response_format),
            )
        try:
            client = _make_client(provider)
        except Exception as exc:
            return make_response(False, str(exc))

        speech_kwargs: dict[str, Any] = {
            "input": text,
            "model": model,
            "voice": voice,
            "response_format": response_format,
        }
        if instructions:
            speech_kwargs["instructions"] = instructions
        if speed and speed != 1.0:
            speech_kwargs["speed"] = speed

        try:
            resp = client.audio.speech.create(**speech_kwargs)
            resp.write_to_file(safe_out)
        except Exception as exc:
            return make_response(
                False,
                _(
                    "err.speech_failed",
                    default="Audio speech generation failed: {err}",
                ).format(err=repr(exc)),
                data={"path": safe_out, "provider": provider, "model": model},
            )

    mime = _mime_for_format(response_format)
    data = {
        "path": safe_out,
        "saved_path": safe_out,
        "saved_files": [safe_out],
        "attachments": [
            {
                "type": "audio",
                "mime": mime,
                "name": Path(safe_out).name,
                "path": safe_out,
                "saved_path": safe_out,
            }
        ],
        "provider": provider,
        "model": model,
        "voice": voice,
        "response_format": response_format,
        "language": language if provider == "grok" else None,
    }

    open_flag = (env_get("UAGENT_AUDIO_OPEN") or "").strip().lower()
    cb = get_callbacks()
    should_open = not bool(getattr(cb, "is_gui", False)) and open_flag not in (
        "0",
        "false",
        "no",
        "off",
    )
    if should_open and open_image_with_default_app(safe_out):
        pass

    return make_response(True, _("ok.saved", default="Audio file saved"), data=data)


if __name__ == "__main__":
    pass
