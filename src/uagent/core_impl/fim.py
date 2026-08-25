"""Fill-in-the-Middle completion (split from core.py)."""

from __future__ import annotations


def _normalize_fim_base_url(provider: str, base_url: str) -> str:
    """Normalize FIM base URL for the given provider.

    Strips trailing slashes and provider-specific path suffixes
    (e.g. ``/v1`` for Ollama) so the FIM implementation can safely
    append its own endpoint path.

    Returns the normalized URL (may be empty).
    """
    raw = base_url.rstrip("/")
    if not raw:
        return ""

    provider_lower = provider.lower()

    if provider_lower == "ollama" and raw.endswith("/v1"):
        raw = raw[:-3]

    return raw


def fim(
    prefix: str,
    suffix: str,
    language: str = "",
    max_tokens: int = 512,
) -> str:
    """Fill-in-the-Middle code completion.

    Uses ``UAGENT_FIM_PROVIDER`` / ``UAGENT_FIM_DEPNAME`` / ``UAGENT_FIM_API_KEY``
    if set, otherwise falls back to the main provider/depname/api-key.

    Returns the completed text (the ``middle`` part).
    """
    from ..env_utils import env_get as _env_get

    provider = _env_get("UAGENT_FIM_PROVIDER") or _env_get("UAGENT_PROVIDER") or ""
    depname = (
        _env_get("UAGENT_FIM_DEPNAME")
        or _env_get(f"UAGENT_{provider.upper()}_DEPNAME")
        or ""
    )
    from ..auth.provider_credentials import get_provider_api_key

    api_key = _env_get("UAGENT_FIM_API_KEY") or get_provider_api_key(
        provider,
        env_getter=_env_get,
    )

    try:
        from ..llmcapa_util import clamp_max_tokens

        max_tokens = clamp_max_tokens(max_tokens, depname, provider)
    except Exception:
        pass

    if not provider or not depname:
        raise ValueError(
            "FIM requires a provider and model. Set UAGENT_FIM_PROVIDER "
            "and UAGENT_FIM_DEPNAME, or set the main UAGENT_PROVIDER and "
            "UAGENT_{PROVIDER}_DEPNAME."
        )

    provider_lower = provider.strip().lower()

    # ---- Resolve base URL (common for all providers) ----
    fim_base_url = (
        _env_get("UAGENT_FIM_BASE_URL")
        or _env_get(f"UAGENT_{provider.upper()}_BASE_URL")
        or ""
    )

    # ---- Dispatch to provider-specific FIM implementation ----
    if provider_lower == "ollama":
        from ..providers.llm_ollama import ollama_fim_generate

        return ollama_fim_generate(
            base_url=_normalize_fim_base_url(provider_lower, fim_base_url),
            model=depname,
            prefix=prefix,
            suffix=suffix,
            language=language,
            max_tokens=max_tokens,
        )

    if provider_lower == "deepseek":
        from ..providers.llm_deepseek import deepseek_fim_generate

        return deepseek_fim_generate(
            base_url=_normalize_fim_base_url(provider_lower, fim_base_url)
            or "https://api.deepseek.com",
            model=depname,
            prefix=prefix,
            suffix=suffix,
            language=language,
            max_tokens=max_tokens,
            api_key=api_key,
        )

    # Provider/model FIM capability gate (static provider list + llmcapa when known)
    from ..llmcapa_util import provider_allows_fim
    from ..providers.provider_caps import FIM_SUPPORTED_PROVIDERS

    if not provider_allows_fim(provider_lower, depname):
        if provider_lower not in FIM_SUPPORTED_PROVIDERS:
            raise ValueError(
                f"FIM is not supported for provider '{provider}'. "
                f"Supported providers: {', '.join(sorted(FIM_SUPPORTED_PROVIDERS))}"
            )
        raise ValueError(
            f"FIM is not supported for model '{depname}' on provider '{provider}'."
        )

    raise ValueError(f"FIM provider '{provider}' is known but not yet implemented.")
