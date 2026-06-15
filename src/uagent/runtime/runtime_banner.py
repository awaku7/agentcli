from __future__ import annotations

from typing import Any

from ..env_utils import env_get
from ..i18n import _
from ..providers.provider_caps import RESPONSES_PROVIDERS


def _normalize_url(core: Any, url: str) -> str:
    try:
        return core.normalize_url(url)
    except Exception:
        return (url or "").strip().rstrip("/")


def _env(name: str, default: str = "") -> str:
    return (env_get(name, default) or "").strip()


def _env_first(keys: list[str], *, default: str = "") -> str:
    for key in keys:
        value = _env(key)
        if value:
            return value
    return default


def _has_all(keys: list[str]) -> bool:
    return all(_env(key) for key in keys)


def _provider_env(provider: str, suffix: str) -> str:
    return _env(f"UAGENT_{provider.upper()}_{suffix.upper()}")


def _embedding_model_info() -> tuple[str, str] | None:
    provider = _env_first(["UAGENT_EMBEDDING_PROVIDER", "UAGENT_PROVIDER"]).lower()
    if provider not in {"openai", "azure", "bedrock", "openrouter", "ollama", "nvidia"}:
        return None

    depname = _provider_env(provider, "EMBEDDING_DEPNAME")
    if not depname:
        return None

    prefix = f"UAGENT_{provider.upper()}_EMBEDDING"
    if provider == "azure":
        required = [
            f"{prefix}_BASE_URL",
            f"{prefix}_API_KEY",
            f"{prefix}_API_VERSION",
        ]
        if not _has_all(required):
            return None
    elif provider in {"openai", "bedrock", "openrouter", "nvidia"}:
        if not _env(f"{prefix}_API_KEY"):
            return None

    return provider, depname


def _google_audio_credentials_present(provider: str, mode: str) -> bool:
    if mode == "speech":
        return bool(
            _env("UAGENT_GOOGLE_CREDENTIALS") or _env("GOOGLE_APPLICATION_CREDENTIALS")
        )
    if provider == "gemini":
        return bool(_env("UAGENT_GEMINI_API_KEY"))
    if provider == "vertexai":
        return bool(_env("UAGENT_GEMINI_API_KEY") or _env("UAGENT_VERTEXAI_API_KEY"))
    return False


def _audio_model_info(mode: str) -> tuple[str, str] | None:
    if mode == "speech":
        provider = _env_first(
            ["UAGENT_AUDIO_SPEECH_PROVIDER", "UAGENT_PROVIDER"], default="openai"
        ).lower()
        default_model = "gpt-4o-mini-tts"
        default_google_model = "ja-JP-Neural2-B"
    else:
        provider = _env_first(
            ["UAGENT_AUDIO_TRANSCRIBE_PROVIDER", "UAGENT_PROVIDER"], default="openai"
        ).lower()
        default_model = "gpt-4o-mini-transcribe"
        default_google_model = "gemini-1.5-flash"

    if provider not in {"openai", "azure", "gemini", "vertexai"}:
        return None

    if provider == "azure":
        depname = _env(f"UAGENT_AZURE_{mode.upper()}_DEPNAME")
        if not depname or not _has_all(
            [
                "UAGENT_AZURE_BASE_URL",
                "UAGENT_AZURE_API_KEY",
                "UAGENT_AZURE_API_VERSION",
            ]
        ):
            return None
        return provider, depname

    if provider == "openai":
        if not _env("UAGENT_OPENAI_API_KEY"):
            return None
        depname = _env(f"UAGENT_OPENAI_{mode.upper()}_DEPNAME", default_model)
        return provider, depname

    if not _google_audio_credentials_present(provider, mode):
        return None
    depname = _env_first(
        [f"UAGENT_GEMINI_{mode.upper()}_DEPNAME", "UAGENT_GEMINI_MODEL"],
        default=default_google_model,
    )
    return provider, depname


def _img_env(
    provider: str, mode: str, name: str, *, include_global: bool = False
) -> str:
    p = provider.upper()
    m = mode.upper()
    n = name.upper()
    keys: list[str] = []
    if include_global:
        keys.append(f"UAGENT_IMG_{m}_{n}")
    keys.extend([f"UAGENT_{p}_IMG_{m}_{n}", f"UAGENT_{p}_{n}"])
    return _env_first(keys)


def _image_generation_depname(provider: str) -> str:
    """Resolve the startup display model for image generation.

    Match generate_image_tool: image generation must not fall back to
    UAGENT_<PROVIDER>_DEPNAME because that is commonly the chat model.
    """
    p = provider.upper()
    depname = _env(f"UAGENT_{p}_IMG_GENERATE_DEPNAME")
    if depname:
        return depname
    if provider == "openai":
        return "gpt-image-1"
    if provider in {"gemini", "vertexai"}:
        return "imagen-4.0-generate-001"
    return ""


def _image_generation_model_info() -> tuple[str, str] | None:
    provider = _env_first(
        ["UAGENT_IMG_GENERATE_PROVIDER", "UAGENT_PROVIDER"], default="azure"
    ).lower()
    if provider not in {
        "azure",
        "openai",
        "bedrock",
        "openrouter",
        "gemini",
        "nvidia",
        "vertexai",
    }:
        return None

    depname = _image_generation_depname(provider)
    if not depname:
        return None

    if provider == "azure":
        if not (
            _img_env("azure", "generate", "base_url")
            and _img_env("azure", "generate", "api_key")
            and _img_env("azure", "generate", "api_version")
        ):
            return None
    elif provider == "bedrock":
        if not (
            _img_env("bedrock", "generate", "base_url")
            and _img_env("bedrock", "generate", "api_key")
        ):
            return None
    elif provider in {"openai", "openrouter", "gemini", "nvidia"}:
        if not _img_env(provider, "generate", "api_key"):
            return None

    return provider, depname


def _image_analysis_model_info() -> tuple[str, str] | None:
    provider = _env_first(["UAGENT_IMG_ANALYSIS_PROVIDER", "UAGENT_PROVIDER"]).lower()
    if provider not in {"openai", "azure", "gemini", "vertexai", "ollama"}:
        return None

    if provider == "ollama":
        if _env("UAGENT_PROVIDER").lower() != "ollama":
            return None
        return provider, _env("UAGENT_OLLAMA_DEPNAME", "llama3.1") or "llama3.1"

    include_global = provider in {"openai", "azure"}
    depname = _img_env(provider, "analysis", "depname", include_global=include_global)
    if provider in {"gemini", "vertexai"} and not depname:
        depname = "gemini-1.5-flash"
    if not depname:
        return None

    if provider == "azure":
        if not (
            _img_env("azure", "analysis", "base_url", include_global=True)
            and _img_env("azure", "analysis", "api_key", include_global=True)
            and _img_env("azure", "analysis", "api_version", include_global=True)
        ):
            return None
    elif provider == "openai":
        if not _img_env("openai", "analysis", "api_key", include_global=True):
            return None
    elif provider == "gemini":
        if not (
            _img_env("gemini", "analysis", "api_key") or _env("UAGENT_GEMINI_API_KEY")
        ):
            return None
    elif provider == "vertexai":
        if not (
            _img_env("vertexai", "analysis", "api_key")
            or _env("UAGENT_VERTEXAI_API_KEY")
        ):
            return None

    return provider, depname


def _startup_optional_model_infos() -> list[tuple[str, str, str]]:
    infos: list[tuple[str, str, str]] = []
    resolvers = [
        (_("embedding"), _embedding_model_info),
        (_("audio speech"), lambda: _audio_model_info("speech")),
        (_("audio transcribe"), lambda: _audio_model_info("transcribe")),
        (_("image generation"), _image_generation_model_info),
        (_("image analysis"), _image_analysis_model_info),
    ]
    for label, resolver in resolvers:
        try:
            resolved = resolver()
        except Exception:
            resolved = None
        if resolved:
            provider, model = resolved
            infos.append((label, provider, model))
    return infos


def build_startup_banner(*, core: Any, workdir: str, workdir_source: str) -> str:
    """Build startup info lines as a single text block."""

    lines: list[str] = []

    lines.append(
        _("[INFO] workdir = %(workdir)s (source: %(source)s)")
        % {"workdir": workdir, "source": workdir_source}
    )

    provider = (env_get("UAGENT_PROVIDER", "(unknown)") or "(unknown)").lower()

    if provider == "azure":
        lines.append(
            _("[INFO] base_url = %(base_url)s")
            % {
                "base_url": _normalize_url(
                    core, env_get("UAGENT_AZURE_BASE_URL", "(not set)")
                )
            }
        )
        lines.append(
            _("[INFO] api_version = %(api_version)s")
            % {"api_version": env_get("UAGENT_AZURE_API_VERSION", "(not set)")}
        )
    elif provider == "openai":
        val = env_get("UAGENT_OPENAI_BASE_URL") or "https://api.openai.com/v1"
        lines.append(
            _("[INFO] base_url = %(base_url)s")
            % {"base_url": _normalize_url(core, val)}
        )
    elif provider == "nvidia":
        lines.append(
            _("[INFO] base_url = %(base_url)s")
            % {
                "base_url": _normalize_url(
                    core,
                    env_get(
                        "UAGENT_NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"
                    ),
                )
            }
        )
    elif provider == "openrouter":
        lines.append(
            _("[INFO] base_url = %(base_url)s")
            % {
                "base_url": _normalize_url(
                    core,
                    env_get(
                        "UAGENT_OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
                    ),
                )
            }
        )
    elif provider == "grok":
        lines.append(
            _("[INFO] base_url = %(base_url)s")
            % {
                "base_url": _normalize_url(
                    core, env_get("UAGENT_GROK_BASE_URL", "https://api.x.ai/v1")
                )
            }
        )
    elif provider == "deepseek":
        lines.append(
            _("[INFO] base_url = %(base_url)s")
            % {
                "base_url": _normalize_url(
                    core,
                    env_get("UAGENT_DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                )
            }
        )
    elif provider == "alibaba":
        lines.append(
            _("[INFO] base_url = %(base_url)s")
            % {
                "base_url": _normalize_url(
                    core,
                    env_get(
                        "UAGENT_ALIBABA_BASE_URL",
                        "https://dashscope.aliyuncs.com/compatible-mode/v1",
                    ),
                )
            }
        )
    elif provider == "bedrock":
        lines.append(
            _("[INFO] base_url = %(base_url)s")
            % {
                "base_url": _normalize_url(
                    core, env_get("UAGENT_BEDROCK_BASE_URL", "(not set)")
                )
            }
        )
    elif provider == "ollama":
        lines.append(
            _("[INFO] base_url = %(base_url)s")
            % {
                "base_url": _normalize_url(
                    core, env_get("UAGENT_OLLAMA_BASE_URL", "http://localhost:11434/v1")
                )
            }
        )
    elif provider == "vertexai":
        lines.append(
            _("[INFO] vertexai = project=%(project)s, location=%(location)s")
            % {
                "project": env_get("UAGENT_VERTEXAI_PROJECT", "(not set)"),
                "location": env_get("UAGENT_VERTEXAI_LOCATION", "(not set)"),
            }
        )

    for label, opt_provider, model in _startup_optional_model_infos():
        lines.append(
            _("[INFO] %(label)s = %(provider)s; model = %(model)s")
            % {"label": label, "provider": opt_provider, "model": model}
        )

    _use_responses_flag = (env_get("UAGENT_RESPONSES", "") or "").lower() in (
        "1",
        "true",
    )
    _streaming_flag = (env_get("UAGENT_STREAMING", "") or "").lower() in (
        "1",
        "true",
    )
    _responses_supported = provider in RESPONSES_PROVIDERS
    if (
        _use_responses_flag
        and not _responses_supported
        and provider not in ("gemini", "claude", "vertexai")
    ):
        lines.append(
            "[WARN] "
            + _(
                "UAGENT_RESPONSES=1 is set, but provider '%(provider)s' does not support Responses API. Falling back to ChatCompletions."
            )
            % {"provider": provider}
        )

    lines.append(
        "[INFO] "
        + _("LLM API mode = %(mode)s")
        % {
            "mode": (
                _("Responses (UAGENT_RESPONSES is enabled)")
                if _use_responses_flag and _responses_supported
                else (
                    _(
                        "Native Gemini/Vertex AI/Claude API (UAGENT_RESPONSES is ignored)"
                    )
                    if provider in ("gemini", "claude", "vertexai")
                    else _("ChatCompletions (UAGENT_RESPONSES is disabled)")
                )
            )
        }
    )

    lines.append(
        "[INFO] "
        + _("LLM streaming = %(state)s")
        % {"state": _("enabled") if _streaming_flag else _("disabled")}
    )

    return "\n".join(lines) + "\n"
