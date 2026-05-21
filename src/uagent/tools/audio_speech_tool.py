from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from ..env_utils import env_get
from .openers import open_image_with_default_app
from .arg_util import get_float, get_str
from .context import get_callbacks
from .i18n_helper import make_tool_translator
from .response_util import make_response
from .safe_file_ops_extras import ensure_within_workdir

_ = make_tool_translator(__file__)

BUSY_LABEL = True

TOOL_SPEC: Dict[str, Any] = {
    "load_order": 8000,
    "type": "function",
    "function": {
        "name": "audio_speech",
        "description": _(
            "tool.description",
            default=(
                "Convert text to speech, save the audio as a file, and return the saved path."
            ),
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "Generate speech audio from the given text and save it to the specified output path. "
                "Return a JSON response only."
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
                        default="Voice name to use for speech synthesis.",
                    ),
                    "default": "alloy",
                },
                "response_format": {
                    "type": "string",
                    "enum": ["mp3", "opus", "aac", "flac", "wav", "pcm"],
                    "default": "mp3",
                    "description": _(
                        "param.response_format.description",
                        default="Audio file format to generate.",
                    ),
                },
                "speed": {
                    "type": "number",
                    "description": _(
                        "param.speed.description",
                        default="Playback speed multiplier (e.g. 1.0).",
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
    if provider not in ("openai", "azure", "gemini", "vertexai"):
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
    return _env_first(
        ["UAGENT_OPENAI_SPEECH_DEPNAME"],
        default="gpt-4o-mini-tts",
    )


def _make_client(provider: str):
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


def run_tool(args: Dict[str, Any]) -> str:
    text = get_str(args, "text", "")
    output_path = get_str(args, "output_path", "")
    if not text:
        return make_response(False, _("err.text_empty", default="text is required"))
    if not output_path:
        return make_response(
            False, _("err.output_path_empty", default="output_path is required")
        )

    provider = _provider()
    model = get_str(args, "model", "") or _model(provider)
    voice = get_str(args, "voice", "alloy") or "alloy"
    response_format = get_str(args, "response_format", "mp3") or "mp3"
    speed = get_float(args, "speed", 1.0)
    instructions = get_str(args, "instructions", "")

    try:
        safe_out = ensure_within_workdir(output_path)
    except Exception as exc:
        return make_response(False, str(exc))

    Path(safe_out).parent.mkdir(parents=True, exist_ok=True)

    if provider in ("gemini", "vertexai"):
        try:
            from google.cloud import texttospeech
        except ImportError:
            return make_response(
                False, "google-cloud-texttospeech or certifi package is not installed."
            )

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

            transport = TextToSpeechRestTransport(
                client_options=c_opts, credentials=credentials
            )
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
        client = _make_client(provider)

        speech_kwargs: Dict[str, Any] = {
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

    mime = "audio/mpeg" if response_format == "mp3" else f"audio/{response_format}"
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
