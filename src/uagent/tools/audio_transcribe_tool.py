from __future__ import annotations

from pathlib import Path
from typing import Any

import requests

from ..auth.provider_credentials import get_provider_api_key
from ..env_utils import env_get
from ..llmcapa_util import check_audio_input_support
from .arg_util import get_bool, get_list, get_path, get_str
from .i18n_helper import get_locale, make_tool_translator
from .response_util import make_response
from .safe_file_ops_extras import ensure_within_workdir

_ = make_tool_translator(__file__)

BUSY_LABEL = True

# xAI batch STT (https://docs.x.ai)
_GROK_STT_URL_DEFAULT = "https://api.x.ai/v1/stt"
_GROK_FILE_MAX_BYTES = 500 * 1024 * 1024  # 500 MB
_GROK_KEYTERM_MAX = 100
_GROK_KEYTERM_LEN = 50

TOOL_SPEC: dict[str, Any] = {
    "load_order": 8000,
    "type": "function",
    "x_parallel_safe": True,
    "tool_genre": "media",
    "function": {
        "name": "audio_transcribe",
        "description": _(
            "tool.description",
            default=(
                "Transcribe an audio file to text. Useful for meetings, interviews, and voice notes."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "audio_transcribe",
                "audio transcribe",
                "audio",
                "voice",
                "speech",
                "sound",
            ],
        ),
        "x_search_terms_en": [
            "audio_transcribe",
            "audio transcribe",
            "audio",
            "voice",
            "speech",
            "sound",
            "transcribe",
            "speech to text",
            "stt",
            "grok stt",
            "xai stt",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default=(
                            "Path to the input audio file. "
                            "Required unless url is set (Grok/xAI)."
                        ),
                    ),
                },
                "url": {
                    "type": "string",
                    "description": _(
                        "param.url.description",
                        default=(
                            "Remote audio URL for Grok/xAI STT (alternative to path). "
                            "Ignored by other providers."
                        ),
                    ),
                },
                "model": {
                    "type": "string",
                    "description": _(
                        "param.model.description",
                        default=(
                            "Transcription model name. If omitted, the provider default "
                            "or configured deployment name is used. "
                            "Grok/xAI default: grok-stt-batch."
                        ),
                    ),
                },
                "language": {
                    "type": "string",
                    "description": _(
                        "param.language.description",
                        default=(
                            "Optional language hint (e.g. 'ja', 'en'). "
                            "If omitted, the current display language is used."
                        ),
                    ),
                },
                "prompt": {
                    "type": "string",
                    "description": _(
                        "param.prompt.description",
                        default=(
                            "Optional context prompt to improve transcription quality. "
                            "Ignored by Grok/xAI batch STT."
                        ),
                    ),
                },
                "fmt": {
                    "type": "string",
                    "enum": ["text", "json"],
                    "default": "json",
                    "description": _(
                        "param.fmt.description",
                        default=(
                            "How much detail to return in the JSON response: text or json."
                        ),
                    ),
                },
                "diarize": {
                    "type": "boolean",
                    "description": _(
                        "param.diarize.description",
                        default=(
                            "Grok/xAI only: enable speaker diarization when true."
                        ),
                    ),
                },
                "keyterm": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": _(
                        "param.keyterm.description",
                        default=(
                            "Grok/xAI only: bias terms (max 100, each <= 50 chars). "
                            "A single string is also accepted."
                        ),
                    ),
                },
                "filler_words": {
                    "type": "boolean",
                    "description": _(
                        "param.filler_words.description",
                        default=("Grok/xAI only: keep filler words (um/uh) when true."),
                    ),
                },
                "itn_format": {
                    "type": "boolean",
                    "description": _(
                        "param.itn_format.description",
                        default=(
                            "Grok/xAI only: enable inverse text normalization "
                            "(numbers/dates as digits) when true."
                        ),
                    ),
                },
            },
            "required": [],
            "additionalProperties": False,
        },
    },
}


def _env_first(keys: list[str], *, required: bool = False, default: str = "") -> str:
    for key in keys:
        value = (env_get(key) or "").strip()
        if value:
            return value
        if key.startswith("UAGENT_") and key.endswith("_API_KEY"):
            provider = key[len("UAGENT_") : -len("_API_KEY")].lower()
            value = (get_provider_api_key(provider) or "").strip()
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
    if provider in ("xai",):
        provider = "grok"
    if provider not in ("openai", "azure", "gemini", "vertexai", "grok"):
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
    if provider == "grok":
        return _env_first(
            ["UAGENT_GROK_TRANSCRIBE_DEPNAME", "UAGENT_GROK_STT_MODEL"],
            default="grok-stt-batch",
        )
    return _env_first(
        ["UAGENT_OPENAI_TRANSCRIBE_DEPNAME"],
        default="gpt-4o-mini-transcribe",
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


def _normalize_keyterms(raw: Any) -> list[str]:
    if raw is None or raw == "" or raw == []:
        return []
    if isinstance(raw, str):
        items = [raw]
    elif isinstance(raw, list):
        items = raw
    else:
        items = [raw]
    out: list[str] = []
    for it in items:
        s = str(it).strip()
        if not s:
            continue
        if len(s) > _GROK_KEYTERM_LEN:
            s = s[:_GROK_KEYTERM_LEN]
        out.append(s)
        if len(out) >= _GROK_KEYTERM_MAX:
            break
    return out


def _grok_stt(
    *,
    path: str | None,
    url: str | None,
    language: str,
    diarize: bool,
    keyterms: list[str],
    filler_words: bool,
    itn_format: bool,
) -> dict[str, Any]:
    """POST https://api.x.ai/v1/stt (multipart). Return parsed JSON dict."""
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
        ["UAGENT_GROK_BASE_URL", "UAGENT_GROK_STT_BASE_URL"],
        default="https://api.x.ai/v1",
    ).rstrip("/")
    if base.endswith("/stt"):
        endpoint = base
    else:
        endpoint = f"{base}/stt"

    # Build multipart fields. xAI requires file last when both present; we send
    # either url or file (prefer file when path is set).
    data_fields: list[tuple[str, str]] = []
    if language:
        data_fields.append(("language", language))
    if diarize:
        data_fields.append(("diarize", "true"))
    if filler_words:
        data_fields.append(("filler_words", "true"))
    if itn_format:
        # xAI param name is "format" (ITN). Avoid colliding with tool arg "fmt".
        data_fields.append(("format", "true"))
    for term in keyterms:
        data_fields.append(("keyterm", term))

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    verify = _ssl_verify_enabled()

    files_arg = None
    fh = None
    try:
        if path:
            p = Path(path)
            size = p.stat().st_size
            if size > _GROK_FILE_MAX_BYTES:
                raise RuntimeError(
                    _(
                        "err.grok_file_too_large",
                        default=(
                            "audio file exceeds Grok STT limit of {max_mb} MB "
                            "(got {size_mb:.1f} MB)"
                        ),
                    ).format(
                        max_mb=_GROK_FILE_MAX_BYTES // (1024 * 1024),
                        size_mb=size / (1024 * 1024),
                    )
                )
            fh = open(path, "rb")
            # filename + content-type guess from suffix
            suffix = p.suffix.lower().lstrip(".")
            mime = "application/octet-stream"
            mime_map = {
                "wav": "audio/wav",
                "mp3": "audio/mpeg",
                "mpeg": "audio/mpeg",
                "ogg": "audio/ogg",
                "opus": "audio/opus",
                "flac": "audio/flac",
                "aac": "audio/aac",
                "mp4": "audio/mp4",
                "m4a": "audio/mp4",
                "mkv": "video/x-matroska",
            }
            if suffix in mime_map:
                mime = mime_map[suffix]
            # file must be last among multipart parts for some gateways
            files_arg = {"file": (p.name, fh, mime)}
        elif url:
            data_fields.append(("url", url))
        else:
            raise RuntimeError(
                _(
                    "err.path_or_url_required",
                    default="path or url is required for Grok/xAI STT",
                )
            )

        resp = requests.post(
            endpoint,
            headers=headers,
            data=data_fields,
            files=files_arg,
            timeout=600,
            verify=verify,
        )
    finally:
        if fh is not None:
            try:
                fh.close()
            except Exception:
                pass

    if resp.status_code >= 400:
        detail = (resp.text or "")[:500]
        raise RuntimeError(f"xAI STT HTTP {resp.status_code}: {detail}")

    try:
        payload = resp.json()
    except Exception as exc:
        raise RuntimeError(
            f"xAI STT response is not JSON: {exc!r}; body={(resp.text or '')[:200]}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"xAI STT unexpected JSON type: {type(payload).__name__}")
    return payload


def run_tool(args: dict[str, Any]) -> str:
    raw_path = get_path(args, "path", "")
    remote_url = get_str(args, "url", "")
    output_format = get_str(args, "fmt", "json").lower()
    if output_format not in ("text", "json"):
        return make_response(
            False,
            _(
                "err.invalid_output_format",
                default="Invalid output_format: {output_format}",
            ).format(output_format=output_format),
        )

    try:
        provider = _provider()
    except Exception as exc:
        return make_response(False, str(exc))

    model = get_str(args, "model", "") or _model(provider)
    language = get_str(args, "language", "") or get_locale()
    prompt = get_str(args, "prompt", "")
    diarize = get_bool(args, "diarize", False)
    filler_words = get_bool(args, "filler_words", False)
    itn_format = get_bool(args, "itn_format", False)
    keyterms = _normalize_keyterms(
        args.get("keyterm") if "keyterm" in args else get_list(args, "keyterm", [])
    )

    gate_err = check_audio_input_support(model, provider)
    if gate_err:
        return make_response(False, gate_err)

    safe_path = ""
    if raw_path:
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
    elif provider != "grok" or not remote_url:
        return make_response(
            False,
            (
                _(
                    "err.path_empty",
                    default="path is required",
                )
                if provider != "grok"
                else _(
                    "err.path_or_url_required",
                    default="path or url is required for Grok/xAI STT",
                )
            ),
        )

    text: str = ""
    resp_language: str = ""
    duration: Any = None
    words: Any = None
    channels: Any = None

    if provider == "grok":
        try:
            payload = _grok_stt(
                path=safe_path or None,
                url=remote_url or None,
                language=language,
                diarize=diarize,
                keyterms=keyterms,
                filler_words=filler_words,
                itn_format=itn_format,
            )
        except Exception as exc:
            return make_response(
                False,
                _(
                    "err.transcribe_failed",
                    default="Audio transcription failed: {err}",
                ).format(err=repr(exc)),
                data={
                    "path": safe_path or None,
                    "url": remote_url or None,
                    "provider": provider,
                    "model": model,
                },
            )
        text = str(payload.get("text") or "").strip()
        resp_language = str(payload.get("language") or "").strip()
        duration = payload.get("duration")
        words = payload.get("words")
        channels = payload.get("channels")
        # Multichannel: concatenate channel texts if top-level text empty
        if not text and isinstance(channels, list):
            parts = []
            for ch in channels:
                if isinstance(ch, dict) and ch.get("text"):
                    parts.append(str(ch.get("text")).strip())
            text = "\n".join(p for p in parts if p)

    elif provider in ("gemini", "vertexai"):
        if not safe_path:
            return make_response(False, _("err.path_empty", default="path is required"))
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
        if not safe_path:
            return make_response(False, _("err.path_empty", default="path is required"))
        try:
            client = _make_client(provider)
        except Exception as exc:
            return make_response(False, str(exc))

        transcribe_kwargs: dict[str, Any] = {
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

    data: dict[str, Any] = {
        "path": safe_path or None,
        "provider": provider,
        "model": model,
        "fmt": output_format,
        "text": text,
    }
    if remote_url:
        data["url"] = remote_url
    if language:
        data["language_hint"] = language
    if resp_language:
        data["language"] = resp_language
    if duration is not None:
        data["duration"] = duration
    if output_format == "json":
        if words is not None:
            data["words"] = words
        if channels is not None:
            data["channels"] = channels

    return make_response(
        True, _("ok.transcribed", default="Transcription completed"), data=data
    )


if __name__ == "__main__":
    print(run_tool({"path": ""}))
