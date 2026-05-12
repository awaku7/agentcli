from __future__ import annotations

from typing import Any, List

from .env_utils import env_get
from .i18n import _


def _normalize_url(core: Any, url: str) -> str:
    try:
        return core.normalize_url(url)
    except Exception:
        return (url or "").strip().rstrip("/")


def build_startup_banner(*, core: Any, workdir: str, workdir_source: str) -> str:
    """Build startup info lines as a single text block."""

    lines: List[str] = []

    lines.append(f"[INFO] workdir = {workdir} (source: {workdir_source})")

    provider = (env_get("UAGENT_PROVIDER", "(unknown)") or "(unknown)").lower()
    lines.append(f"[INFO] provider = {provider}")

    if provider == "azure":
        lines.append(
            f"[INFO] base_url = {_normalize_url(core, env_get('UAGENT_AZURE_BASE_URL', '(not set)'))}"
        )
        lines.append(
            f"[INFO] api_version = {env_get('UAGENT_AZURE_API_VERSION', '(not set)')}"
        )
    elif provider == "openai":
        val = env_get("UAGENT_OPENAI_BASE_URL") or "https://api.openai.com/v1"
        lines.append(f"[INFO] base_url = {_normalize_url(core, val)}")
    elif provider == "nvidia":
        lines.append(
            f"[INFO] base_url = {_normalize_url(core, env_get('UAGENT_NVIDIA_BASE_URL', 'https://integrate.api.nvidia.com/v1'))}"
        )
    elif provider == "openrouter":
        lines.append(
            f"[INFO] base_url = {_normalize_url(core, env_get('UAGENT_OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1'))}"
        )
    elif provider == "grok":
        lines.append(
            f"[INFO] base_url = {_normalize_url(core, env_get('UAGENT_GROK_BASE_URL', 'https://api.x.ai/v1'))}"
        )
    elif provider == "bedrock":
        lines.append(
            f"[INFO] base_url = {_normalize_url(core, env_get('UAGENT_BEDROCK_BASE_URL', '(not set)'))}"
        )
    elif provider == "ollama":
        lines.append(
            f"[INFO] base_url = {_normalize_url(core, env_get('UAGENT_OLLAMA_BASE_URL', 'http://localhost:11434/v1'))}"
        )
    elif provider == "vertexai":
        lines.append(
            "[INFO] vertexai = "
            f"project={env_get('UAGENT_VERTEXAI_PROJECT', '(not set)')}, "
            f"location={env_get('UAGENT_VERTEXAI_LOCATION', '(not set)')}"
        )

    _use_responses_flag = (env_get("UAGENT_RESPONSES", "") or "").lower() in (
        "1",
        "true",
    )
    _streaming_flag = (env_get("UAGENT_STREAMING", "") or "").lower() in (
        "1",
        "true",
    )
    _responses_supported = provider in (
        "azure",
        "openai",
        "bedrock",
        "openrouter",
        "ollama",
    )
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
        % {"mode": "Responses (UAGENT_RESPONSES is enabled)" if _use_responses_flag and _responses_supported else ("Native Gemini/Vertex AI/Claude API (UAGENT_RESPONSES is ignored)" if provider in ("gemini", "claude", "vertexai") else "ChatCompletions (UAGENT_RESPONSES is disabled)")}
    )

    lines.append(
        "[INFO] "
        + _("LLM streaming = %(state)s")
        % {"state": "enabled" if _streaming_flag else "disabled"}
    )

    return "\n".join(lines) + "\n"
