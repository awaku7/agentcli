"""Shared llmcapa lookup helpers for uagent.

Normalizes uag provider keys to llmcapa provider names, resolves model
capabilities offline, and exposes small helpers used by chat vision gating,
shrink thresholds, max-token clamping, and :model display.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from .env_utils import env_get

# uag provider key -> ordered llmcapa provider candidates.
# llmcapa already accepts some aliases (gemini/grok/bedrock/...), but we keep
# an explicit list so lookups stay stable across llmcapa versions.
_PROVIDER_CANDIDATES: dict[str, tuple[str, ...]] = {
    "openai": ("openai", "azure-openai", "openrouter"),
    "azure": ("azure-openai", "azure-foundry", "openai"),
    "bedrock": ("amazon", "bedrock"),
    "openrouter": ("openrouter", "openai"),
    "ollama": ("ollama",),
    "gemini": ("google", "gemini"),
    "vertexai": ("google", "vertexai"),
    "grok": ("xai", "grok"),
    "claude": ("anthropic", "claude"),
    "nvidia": ("nvidia",),
    "deepseek": ("deepseek",),
    "zai": ("zai",),
    "alibaba": ("qwen", "alibaba"),
    "moonshot": ("moonshot", "moonshotai"),
    "mimo": ("xiaomi", "mimo"),
    "lmstudio": ("lmstudio", "ollama"),
    "minimax": ("minimax",),
    "hf": ("huggingface", "hf"),
    "sakana": ("sakana",),
    "sakura": ("sakura",),
    "novita": ("novita",),
}


def normalize_provider(provider: str | None) -> str:
    """Return a normalized uag provider key (lower/strip)."""
    return (provider or "").strip().lower()


def provider_candidates(provider: str | None) -> list[str]:
    """Return llmcapa provider names to try for a uag provider key."""
    prov = normalize_provider(provider)
    if not prov:
        return []
    out: list[str] = []
    for name in (prov,) + _PROVIDER_CANDIDATES.get(prov, ()):
        if name and name not in out:
            out.append(name)
    return out


def model_id_candidates(model_id: str | None) -> list[str]:
    """Return model id variants to try (full id, bare id)."""
    mid = (model_id or "").strip()
    if not mid:
        return []
    out = [mid]
    if "/" in mid:
        bare = mid.split("/", 1)[1].strip()
        if bare and bare not in out:
            out.append(bare)
    # Common deployment suffixes: keep original first; bare without date tags is
    # left to llmcapa aliases.
    return out


def current_provider() -> str:
    return normalize_provider(env_get("UAGENT_PROVIDER"))


def current_model(provider: str | None = None) -> str:
    """Best-effort current deployment/model name from env."""
    prov = normalize_provider(provider) or current_provider()
    if prov:
        specific = (env_get(f"UAGENT_{prov.upper()}_DEPNAME") or "").strip()
        if specific:
            return specific
    return (env_get("UAGENT_DEPNAME") or "").strip()


@lru_cache(maxsize=256)
def _get_capability_cached(
    model_id: str, provider_key: str
) -> Any | None:
    """Cached llmcapa.get with provider/model candidate fallbacks."""
    try:
        import llmcapa
    except Exception:
        return None

    model_ids = model_id_candidates(model_id)
    providers = provider_candidates(provider_key) if provider_key else [None]

    # 1) Scoped lookups
    for prov in providers:
        for mid in model_ids:
            try:
                if prov is None:
                    cap = llmcapa.get(mid)
                else:
                    cap = llmcapa.get(mid, provider=prov)
                if cap is not None:
                    return cap
            except Exception:
                continue

    # 2) Unscoped lookup (native/first-registered)
    if provider_key:
        for mid in model_ids:
            try:
                cap = llmcapa.get(mid)
                if cap is not None:
                    return cap
            except Exception:
                continue

    # 3) Prefix search as last resort (prefer requested provider family)
    try:
        search = getattr(llmcapa, "search", None)
        if callable(search):
            for mid in model_ids:
                needle = mid.split("/")[-1]
                if len(needle) < 3:
                    continue
                hits = search(needle, limit=8) or []
                if not hits:
                    continue
                if provider_key:
                    cand_set = set(provider_candidates(provider_key))
                    for hit in hits:
                        if getattr(hit, "provider", None) in cand_set:
                            return hit
                return hits[0]
    except Exception:
        pass
    return None


def get_capability(
    model_id: str | None = None,
    provider: str | None = None,
    *,
    use_env_defaults: bool = False,
) -> Any | None:
    """Resolve a llmcapa Capability or return None.

    When ``use_env_defaults`` is True, missing model/provider are filled from
    UAGENT_PROVIDER / UAGENT_*_DEPNAME.
    """
    prov = normalize_provider(provider)
    mid = (model_id or "").strip()
    if use_env_defaults:
        if not prov:
            prov = current_provider()
        if not mid:
            mid = current_model(prov)
    if not mid:
        return None
    return _get_capability_cached(mid, prov)


def clear_capability_cache() -> None:
    """Drop cached capability lookups (tests / model switch)."""
    _get_capability_cached.cache_clear()


def supports_feature(
    feature: str,
    model_id: str | None = None,
    provider: str | None = None,
    *,
    default: bool | None = None,
) -> bool | None:
    """Return whether the model supports ``feature``, or ``default`` if unknown."""
    cap = get_capability(model_id, provider)
    if cap is None:
        return default
    try:
        return bool(cap.supports(feature))
    except Exception:
        # Fall back to attribute-style flags when supports() is unavailable.
        attr = f"supports_{feature}" if not feature.startswith("supports_") else feature
        val = getattr(cap, attr, None)
        if val is None:
            return default
        return bool(val)


def supports_vision(
    model_id: str | None = None,
    provider: str | None = None,
    *,
    default: bool | None = None,
) -> bool | None:
    """Vision / image-input support for a model."""
    cap = get_capability(model_id, provider)
    if cap is None:
        return default
    try:
        if cap.supports("vision") or cap.supports("image_input"):
            return True
        # Explicit false when flags are present and negative.
        if getattr(cap, "supports_vision", None) is False:
            return False
        mods = set(getattr(cap, "input_modalities", None) or [])
        if "image" in mods:
            return True
        if mods and "image" not in mods:
            return False
    except Exception:
        pass
    return default


def get_context_window(
    model_id: str | None = None,
    provider: str | None = None,
) -> int | None:
    cap = get_capability(model_id, provider)
    if cap is None:
        return None
    try:
        ctx = int(getattr(cap, "context_window", 0) or 0)
    except Exception:
        return None
    return ctx if ctx > 0 else None


def get_max_output_tokens(
    model_id: str | None = None,
    provider: str | None = None,
) -> int | None:
    cap = get_capability(model_id, provider)
    if cap is None:
        return None
    try:
        out = int(getattr(cap, "max_output_tokens", 0) or 0)
    except Exception:
        return None
    return out if out > 0 else None


def clamp_max_tokens(
    value: int,
    model_id: str | None = None,
    provider: str | None = None,
) -> int:
    """Clamp a requested max-token value to the model max_output_tokens when known."""
    try:
        n = int(value)
    except Exception:
        return value
    if n <= 0:
        return n
    limit = get_max_output_tokens(model_id, provider)
    if limit is not None and limit > 0:
        return min(n, limit)
    return n


def get_reasoning_effort_values(
    model_id: str | None = None,
    provider: str | None = None,
) -> list[str] | None:
    cap = get_capability(model_id, provider)
    if cap is None:
        return None
    try:
        if not getattr(cap, "supports_reasoning_effort", False):
            # Still return values if present; some rows omit the flag.
            vals = cap.get_reasoning_effort_values()
            return list(vals) if vals else None
        vals = cap.get_reasoning_effort_values()
        return list(vals) if vals else None
    except Exception:
        return None


def estimate_cost(
    input_tokens: int = 0,
    output_tokens: int = 0,
    model_id: str | None = None,
    provider: str | None = None,
) -> dict[str, Any] | None:
    cap = get_capability(model_id, provider)
    if cap is None:
        return None
    try:
        return dict(cap.estimate_cost(input_tokens, output_tokens))
    except Exception:
        return None



def resolve_model_id_for_tokenizer(
    model_id: str | None = None,
    provider: str | None = None,
) -> str | None:
    """Return a model id suitable for llmcapa token counting.

    Prefers the resolved Capability.model_id when lookup succeeds; otherwise
    returns the original non-empty model_id.
    """
    mid = (model_id or "").strip()
    cap = get_capability(mid or None, provider)
    if cap is not None:
        resolved = (getattr(cap, "model_id", None) or "").strip()
        if resolved:
            return resolved
    return mid or None


def count_messages_tokens(
    messages: list[dict[str, Any]],
    model_id: str | None = None,
    provider: str | None = None,
) -> int | None:
    """Count message tokens via llmcapa, or None if unavailable/failed."""
    mid = resolve_model_id_for_tokenizer(model_id, provider)
    if not mid:
        return None
    try:
        import llmcapa

        n = llmcapa.count_messages_tokens(messages, mid)
        return int(n)
    except Exception:
        # Retry with the raw id if resolved id failed.
        raw = (model_id or "").strip()
        if raw and raw != mid:
            try:
                import llmcapa

                return int(llmcapa.count_messages_tokens(messages, raw))
            except Exception:
                return None
        return None


def supports_responses_api(
    model_id: str | None = None,
    provider: str | None = None,
    *,
    default: bool | None = None,
) -> bool | None:
    """Model-level Responses API support, or ``default`` when unknown."""
    return supports_feature(
        "responses_api", model_id, provider, default=default
    )


def supports_fim(
    model_id: str | None = None,
    provider: str | None = None,
    *,
    default: bool | None = None,
) -> bool | None:
    """Model-level FIM support, or ``default`` when unknown."""
    return supports_feature("fim", model_id, provider, default=default)


def provider_allows_responses_api(
    provider: str | None,
    model_id: str | None = None,
) -> bool:
    """Whether Responses API may be used for this provider/model.

    Provider must be in RESPONSES_PROVIDERS. When model capability is known,
    ``supports_responses_api`` must not be explicitly false.
    """
    from .providers.provider_caps import RESPONSES_PROVIDERS

    prov = normalize_provider(provider)
    if prov not in RESPONSES_PROVIDERS:
        return False
    mid = (model_id or "").strip() or current_model(prov)
    if not mid:
        return True
    flag = supports_responses_api(mid, prov, default=None)
    if flag is None:
        return True
    return bool(flag)


def provider_allows_fim(
    provider: str | None,
    model_id: str | None = None,
) -> bool:
    """Whether FIM may be attempted for this provider/model.

    Provider must be in FIM_SUPPORTED_PROVIDERS (implementation exists).
    When model capability is known, ``supports_fim`` must not be false.
    """
    from .providers.provider_caps import FIM_SUPPORTED_PROVIDERS

    prov = normalize_provider(provider)
    if prov not in FIM_SUPPORTED_PROVIDERS:
        return False
    mid = (model_id or "").strip() or current_model(prov)
    if not mid:
        return True
    flag = supports_fim(mid, prov, default=None)
    if flag is None:
        return True
    return bool(flag)



def check_vision_support(
    model_id: str | None = None,
    provider: str | None = None,
) -> str | None:
    """Return an error message if the model is known not to support vision.

    Returns None when support is true or unknown (so callers can proceed).
    """
    mid = (model_id or "").strip()
    if not mid:
        return None
    flag = supports_vision(mid, provider, default=None)
    if flag is False:
        prov = normalize_provider(provider) or "?"
        return (
            f"Model '{mid}' (provider={prov}) does not support vision/image input "
            "according to llmcapa. Choose a vision-capable model."
        )
    return None


def vision_completion_max_tokens(
    model_id: str | None = None,
    provider: str | None = None,
    *,
    default: int = 1024,
) -> int:
    """Default max tokens for one-shot vision describe calls, clamped when known."""
    try:
        base = int(default)
    except Exception:
        base = 1024
    if base <= 0:
        base = 1024
    return clamp_max_tokens(base, model_id, provider)


def deprecated_model_warning(
    model_id: str | None = None,
    provider: str | None = None,
) -> str | None:
    """Return a short deprecation warning line, or None."""
    cap = get_capability(model_id, provider)
    if cap is None or not getattr(cap, "deprecated", False):
        return None
    mid = getattr(cap, "model_id", model_id) or model_id or "?"
    repl = None
    try:
        repl = cap.can_be_replaced_by()
    except Exception:
        repl = None
    if repl:
        return f"Model '{mid}' is deprecated; consider '{repl}'."
    return f"Model '{mid}' is deprecated."


def format_capability_lines(cap: Any) -> list[str]:
    """Format a Capability into human-readable detail lines."""
    if cap is None:
        return []
    lines: list[str] = []
    try:
        lines.append(f"    model_id: {getattr(cap, 'model_id', '?')}")
        lines.append(f"    provider: {getattr(cap, 'provider', '?')}")
        lines.append(f"    Display Name:  {getattr(cap, 'display_name', '')}")
        ctx = int(getattr(cap, "context_window", 0) or 0)
        out = int(getattr(cap, "max_output_tokens", 0) or 0)
        lines.append(f"    Context Window: {ctx:,} tokens")
        lines.append(f"    Max Output:    {out:,} tokens")
        lines.append(f"    Tokenizer:     {getattr(cap, 'tokenizer_name', None) or '?'}")
        lines.append(f"    License:       {getattr(cap, 'license_type', None) or '?'}")
        lines.append(
            f"    Knowledge Cutoff: {getattr(cap, 'knowledge_cutoff', None) or '?'}"
        )
        lines.append(f"    Deprecated:    {getattr(cap, 'deprecated', False)}")
        repl = None
        try:
            repl = cap.can_be_replaced_by()
        except Exception:
            repl = getattr(cap, "can_be_replaced_by", None)
            if callable(repl):
                try:
                    repl = repl()
                except Exception:
                    repl = None
        if repl:
            lines.append(f"    Replaced By:   {repl}")
        in_mods = getattr(cap, "input_modalities", None) or []
        out_mods = getattr(cap, "output_modalities", None) or []
        if in_mods:
            lines.append(f"    Input:         {', '.join(in_mods)}")
        if out_mods:
            lines.append(f"    Output:        {', '.join(out_mods)}")
        feats: list[str] = []
        for name in (
            "function_calling",
            "json_mode",
            "streaming",
            "vision",
            "reasoning",
            "chat_completion",
            "responses_api",
            "reasoning_effort",
            "thinking_budget",
            "anthropic_api",
            "google_api",
            "fim",
        ):
            try:
                if cap.supports(name):
                    feats.append(name)
            except Exception:
                if getattr(cap, f"supports_{name}", False):
                    feats.append(name)
        if feats:
            lines.append(f"    Features:      {', '.join(feats)}")
        pricing = getattr(cap, "pricing", None) or {}
        if pricing:
            inp = pricing.get("input_per_1m")
            outp = pricing.get("output_per_1m")
            cur = pricing.get("currency", "USD")
            if inp is not None and outp is not None:
                lines.append(
                    f"    Pricing:       ${float(inp):.2f}/{cur}M in, "
                    f"${float(outp):.2f}/{cur}M out"
                )
                try:
                    sample = cap.estimate_cost(1_000_000, 1_000_000)
                    cost = sample.get("cost")
                    if cost is not None:
                        lines.append(
                            f"    Est. 1M in+out: ${float(cost):.2f} {sample.get('currency', cur)}"
                        )
                except Exception:
                    pass
        efforts = None
        try:
            efforts = cap.get_reasoning_effort_values()
        except Exception:
            efforts = getattr(cap, "reasoning_effort_values", None)
        if efforts:
            lines.append(f"    Reasoning Efforts: {', '.join(str(v) for v in efforts)}")
        budgets = None
        try:
            budgets = cap.get_thinking_budget_values()
        except Exception:
            budgets = getattr(cap, "thinking_budget_values", None)
        if budgets:
            lines.append(
                f"    Thinking Budgets: {', '.join(str(v) for v in budgets)}"
            )
    except Exception:
        return lines
    return lines
