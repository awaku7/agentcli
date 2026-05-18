from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from ..env_utils import env_get
from .arg_util import get_path, get_str
from .i18n_helper import get_locale, make_tool_translator
from .response_util import make_response
from .safe_file_ops_extras import ensure_within_workdir

_ = make_tool_translator(__file__)

BUSY_LABEL = True

TOOL_SPEC: Dict[str, Any] = {
    "load_order": 8000,
    "type": "function",
    "function": {
        "name": "audio_transcribe",
        "description": _(
            "tool.description",
            default=(
                "Transcribe an audio file to text. Useful for meetings, interviews, and voice notes."
            ),
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "Transcribe the given audio file and return a JSON response only. "
                "If output_format=text, include the transcript text in the response. "
                "If output_format=json, include basic metadata as well."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Path to the input audio file.",
                    ),
                },
                "model": {
                    "type": "string",
                    "description": _(
                        "param.model.description",
                        default=(
                            "Transcription model name. If omitted, the provider default or configured deployment name is used."
                        ),
                    ),
                },
                "language": {
                    "type": "string",
                    "description": _(
                        "param.language.description",
                        default=(
                            "Optional language hint (e.g. 'ja', 'en'). If omitted, the current display language is used."
                        ),
                    ),
                },
                "prompt": {
                    "type": "string",
                    "description": _(
                        "param.prompt.description",
                        default="Optional context prompt to improve transcription quality.",
                    ),
                },
                "output_format": {
                    "type": "string",
                    "enum": ["text", "json"],
                    "default": "json",
                    "description": _(
                        "param.output_format.description",
                        default=(
                            "How much detail to return in the JSON response: text or json."
                        ),
                    ),
                },
            },
            "required": ["path"],
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
        ["UAGENT_AUDIO_TRANSCRIBE_PROVIDER", "UAGENT_PROVIDER"], default="openai"
    )
    provider = provider.strip().lower()
    if provider not in ("openai", "azure", "gemini", "vertexai"):
        raise RuntimeError(
            _(
                "err.unsupported_provider",
                default="Unsupported provider for audio transcription: {provider!r}",
            ).format(provider=provider)
        )
    return provider


def _model(provider: str) -> str:
    if provider == "azure":
        return _env_first(
            ["UAGENT_AZURE_TRANSCRIBE_DEPNAME"],
            required=True,
        )
    if provider in ("gemini", "vertexai"):
        return _env_first(
            ["UAGENT_GEMINI_TRANSCRIBE_DEPNAME", "UAGENT_GEMINI_MODEL"],
            default="gemini-1.5-flash",
        )
    return _env_first(
        ["UAGENT_OPENAI_TRANSCRIBE_DEPNAME"],
        default="gpt-4o-mini-transcribe",
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
    raw_path = get_path(args, "path", "")
    if not raw_path:
        return make_response(False, _("err.path_empty", default="path is required"))

    output_format = get_str(args, "output_format", "json").lower()
    if output_format not in ("text", "json"):
        return make_response(
            False,
            _(
                "err.invalid_output_format",
                default="Invalid output_format: {output_format}",
            ).format(output_format=output_format),
        )

    provider = _provider()
    model = get_str(args, "model", "") or _model(provider)
    language = get_str(args, "language", "") or get_locale()
    prompt = get_str(args, "prompt", "")

    try:
        safe_path = ensure_within_workdir(raw_path)
    except Exception as exc:
        return make_response(False, str(exc))

    if not Path(safe_path).is_file():
        return make_response(
            False,
            _(
                "err.file_not_found",
                default="audio file not found: {path}",
            ).format(path=safe_path),
        )

    text: str = ""
    resp_language: str = ""
    duration: Any = None

    if provider in ("gemini", "vertexai"):
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            return make_response(False, "google-genai package is not installed.")

        try:
            if provider == "vertexai":
                # Try with Gemini API Key if VertexAI API Key fails or for better compatibility with Audio
                api_key = env_get("UAGENT_GEMINI_API_KEY") or env_get(
                    "UAGENT_VERTEXAI_API_KEY"
                )
                # When using Gemini API Key, we should NOT set vertexai=True
                use_vertex = env_get("UAGENT_GEMINI_API_KEY") is None
                client = genai.Client(vertexai=use_vertex, api_key=api_key)
            else:
                api_key = env_get("UAGENT_GEMINI_API_KEY")
                client = genai.Client(api_key=api_key)
        except Exception as e:
            return make_response(
                False, f"Failed to initialize Gemini/VertexAI client: {e}"
            )

        try:
            with open(safe_path, "rb") as f:
                audio_bytes = f.read()

            suffix = Path(safe_path).suffix.lower()
            mime_type = "audio/mpeg"
            if suffix == ".wav":
                mime_type = "audio/wav"
            elif suffix == ".ogg":
                mime_type = "audio/ogg"
            elif suffix == ".aac":
                mime_type = "audio/aac"
            elif suffix == ".flac":
                mime_type = "audio/flac"

            final_prompt = "Transcribe the following audio accurately."
            if prompt:
                final_prompt = f"{prompt}\n\n{final_prompt}"
            if language:
                final_prompt += f" The language is {language}."

            resp = client.models.generate_content(
                model=model,
                contents=[
                    types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                    final_prompt,
                ],
            )
            text = resp.text or ""
            resp_language = language
            duration = None
        except Exception as exc:
            return make_response(
                False,
                _(
                    "err.transcribe_failed",
                    default="Audio transcription failed: {err}",
                ).format(err=repr(exc)),
                data={"path": safe_path, "provider": provider, "model": model},
            )
    else:
        client = _make_client(provider)

        transcribe_kwargs: Dict[str, Any] = {
            "file": open(safe_path, "rb"),
            "model": model,
        }
        if language:
            transcribe_kwargs["language"] = language
        if prompt:
            transcribe_kwargs["prompt"] = prompt
        if output_format == "json":
            transcribe_kwargs["response_format"] = "verbose_json"

        try:
            with transcribe_kwargs["file"] as fin:
                transcribe_kwargs["file"] = fin
                resp = client.audio.transcriptions.create(**transcribe_kwargs)
        except Exception as exc:
            return make_response(
                False,
                _(
                    "err.transcribe_failed",
                    default="Audio transcription failed: {err}",
                ).format(err=repr(exc)),
                data={"path": safe_path, "provider": provider, "model": model},
            )

        if isinstance(resp, str):
            text = resp.strip()
        else:
            text = str(getattr(resp, "text", "") or "").strip()
            resp_language = str(getattr(resp, "language", "") or "").strip()
            duration = getattr(resp, "duration", None)
            if not text:
                try:
                    payload = resp.model_dump()  # type: ignore[attr-defined]
                    if isinstance(payload, dict):
                        text = str(payload.get("text") or "").strip()
                        resp_language = str(
                            payload.get("language") or resp_language or ""
                        ).strip()
                        duration = payload.get("duration", duration)
                except Exception:
                    pass

    if not text:
        text = _("warn.empty_transcript", default="[WARN] empty transcript")

    data: Dict[str, Any] = {
        "path": safe_path,
        "provider": provider,
        "model": model,
        "output_format": output_format,
        "text": text,
    }
    if language:
        data["language_hint"] = language
    if resp_language:
        data["language"] = resp_language
    if duration is not None:
        data["duration"] = duration

    return make_response(
        True, _("ok.transcribed", default="Transcription completed"), data=data
    )


if __name__ == "__main__":
    print(run_tool({"path": ""}))
