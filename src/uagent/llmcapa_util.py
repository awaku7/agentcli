"""Shared llmcapa lookup helpers for uagent.

Normalizes uag provider keys to llmcapa provider names, resolves model
capabilities offline, and exposes small helpers used by chat vision gating,
shrink thresholds, max-token clamping, and :model display.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from .env_utils import env_get
from .i18n import _

# uag provider key -> ordered llmcapa provider candidates.
# llmcapa already accepts some aliases (gemini/grok/bedrock/...), but we keep
# an explicit list so lookups stay stable across llmcapa versions.
_PROVIDER_CANDIDATES: dict[str, tuple[str, ...]] = {
    "openai": ("openai", "azure-openai", "openrouter"),
    "meta": ("meta", "openrouter"),
    "azure": ("azure-openai", "azure-foundry", "openai"),
    "bedrock": ("amazon", "bedrock"),
    "openrouter": ("openrouter", "openai"),
    "ollama": ("ollama",),
    # llama-server and Ollama can expose the same OpenAI-compatible model
    # names. Prefer llama.cpp-specific rows, then transparently fall back to
    # Ollama's catalog when llmcapa has no llama.cpp row for the model.
    "llama_cpp": ("llama.cpp", "llama_cpp", "ollama"),
    "gemini": ("google", "gemini"),
    # NOTE: vertexai must not include "google": the Developer API catalog
    # and the Vertex AI catalog differ per model. Mixing them merges
    # google(76 rows) + vertex-ai(4956 rows) in list_models() and risks
    # wrong thinking/budget decisions. Unscoped get() still falls back to
    # the native row when no vertex-ai row exists.
    "vertexai": ("vertex-ai", "vertexai"),
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
    "pfn": ("pfn",),
    "novita": ("novita",),
    "inception": ("inception",),
}


# Provider aliases that are safe for strict provider/model capability lookup.
# In particular, an Azure deployment must never silently resolve to an OpenAI
# catalog row with the same name.
_STRICT_PROVIDER_CANDIDATES: dict[str, tuple[str, ...]] = {
    "openai": ("openai",),
    "azure": ("azure-openai", "azure-foundry"),
    "openrouter": ("openrouter",),
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
    model_id: str, provider_key: str, scoped_only: bool = False
) -> Any | None:
    """Cached llmcapa.get with provider/model candidate fallbacks."""
    try:
        import llmcapa
    except Exception:
        return None

    model_ids = model_id_candidates(model_id)
    if provider_key and scoped_only:
        providers = list(
            _STRICT_PROVIDER_CANDIDATES.get(
                provider_key, tuple(provider_candidates(provider_key)[:1])
            )
        )
    else:
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

    if scoped_only:
        return None

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
    scoped_only: bool = False,
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
    return _get_capability_cached(mid, prov, scoped_only)


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
        value = cap.supports(feature)
        return None if value is None else bool(value)
    except Exception:
        # Fall back to attribute-style flags when supports() is unavailable.
        attr = f"supports_{feature}" if not feature.startswith("supports_") else feature
        val = getattr(cap, attr, None)
        if val is None:
            return default
        return bool(val)


def _supports_structured_output_feature(
    feature: str,
    model_id: str | None = None,
    provider: str | None = None,
) -> bool | None:
    """Return tri-state Structured Output support for one provider/model."""
    try:
        cap = get_capability(model_id, provider, scoped_only=True)
    except TypeError:
        # Compatibility with test doubles and older integrations.
        cap = get_capability(model_id, provider)
    if cap is None:
        return None
    try:
        value = cap.supports(feature)
        if value is not None:
            return bool(value)
    except Exception:
        pass
    value = getattr(cap, f"supports_{feature}", None)
    return None if value is None else bool(value)


def supports_json_mode(
    model_id: str | None = None, provider: str | None = None
) -> bool | None:
    """Return tri-state JSON Object mode support for provider + model."""
    return _supports_structured_output_feature("json_mode", model_id, provider)


def supports_json_schema(
    model_id: str | None = None, provider: str | None = None
) -> bool | None:
    """Return tri-state JSON Schema support for provider + model."""
    return _supports_structured_output_feature("json_schema", model_id, provider)


def structured_output_provenance(
    model_id: str | None = None, provider: str | None = None
) -> dict[str, Any] | None:
    """Return capability evidence recorded for the resolved provider/model."""
    try:
        cap = get_capability(model_id, provider, scoped_only=True)
    except TypeError:
        cap = get_capability(model_id, provider)
    if cap is None:
        return None
    evidence = getattr(cap, "extra", None)
    evidence = evidence.get("structured_output") if isinstance(evidence, dict) else None
    result = {
        "provider": getattr(cap, "provider", provider),
        "model_id": getattr(cap, "model_id", model_id),
        "json_mode": supports_json_mode(model_id, provider),
        "json_schema": supports_json_schema(model_id, provider),
    }
    if isinstance(evidence, dict):
        result["evidence"] = evidence
    return result


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
    context, _source = get_context_window_details(model_id, provider)
    return context


def get_context_window_details(
    model_id: str | None = None,
    provider: str | None = None,
) -> tuple[int | None, str]:
    """Return the resolved context window and its source label."""
    if normalize_provider(provider) == "llama_cpp":
        props_ctx = _get_llama_cpp_props_context(model_id)
        if props_ctx is not None:
            return props_ctx, "/props"
    if normalize_provider(provider) == "ollama":
        show_ctx = _get_ollama_show_context(model_id)
        if show_ctx is not None:
            return show_ctx, "/api/show"
    if normalize_provider(provider) == "lmstudio":
        lmstudio_ctx = _get_lmstudio_v1_context(model_id)
        if lmstudio_ctx is not None:
            return lmstudio_ctx, "/api/v1/models"
    cap = get_capability(model_id, provider)
    if cap is None:
        return None, "unavailable"
    try:
        ctx = int(getattr(cap, "context_window", 0) or 0)
    except Exception:
        return None, "unavailable"
    return (ctx, "llmcapa") if ctx > 0 else (None, "unavailable")


@lru_cache(maxsize=128)
def _get_llama_cpp_props_context(model_id: str | None) -> int | None:
    """Read llama-server's effective ``n_ctx`` before offline catalog data."""
    model = (model_id or "").strip()
    base = (env_get("UAGENT_LLAMA_CPP_BASE_URL", "") or "").strip()
    if not model or not base:
        return None
    try:
        parts = urlsplit(base)
        path = parts.path.rstrip("/")
        if path.endswith("/v1"):
            path = path[:-3].rstrip("/")
        props_url = urlunsplit((parts.scheme, parts.netloc, path + "/props", "", ""))
        url = f"{props_url}?model={quote(model, safe='')}"
        timeout = float(env_get("UAGENT_LLAMA_CPP_PROPS_TIMEOUT_SEC", "5") or "5")
        with urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        value = payload.get("default_generation_settings", {}).get("n_ctx")
        context = int(value or 0)
        return context if context > 0 else None
    except Exception:
        return None


@lru_cache(maxsize=128)
def _get_ollama_show_context(model_id: str | None) -> int | None:
    """Read Ollama's model-specific context length from ``/api/show``."""
    model = (model_id or "").strip()
    base = (env_get("UAGENT_OLLAMA_BASE_URL", "") or "").strip()
    if not model or not base:
        return None
    try:
        parts = urlsplit(base)
        path = parts.path.rstrip("/")
        if path.endswith("/v1"):
            path = path[:-3].rstrip("/")
        show_url = urlunsplit((parts.scheme, parts.netloc, path + "/api/show", "", ""))
        request = Request(
            show_url,
            data=json.dumps({"name": model}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        timeout = float(env_get("UAGENT_OLLAMA_PROPS_TIMEOUT_SEC", "5") or "5")
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        model_info = payload.get("model_info") or {}
        for value in (
            value
            for key, value in model_info.items()
            if str(key).endswith(".context_length")
        ):
            context = int(value or 0)
            if context > 0:
                return context
    except Exception:
        pass
    return None


@lru_cache(maxsize=32)
def _get_lmstudio_v1_context(model_id: str | None) -> int | None:
    """Read LM Studio's native v1 model metadata."""
    model = (model_id or "").strip()
    base = (env_get("UAGENT_LMSTUDIO_BASE_URL", "") or "").strip()
    if not model or not base:
        return None
    try:
        parts = urlsplit(base)
        path = parts.path.rstrip("/")
        if path.endswith("/v1"):
            path = path[:-3].rstrip("/")
        models_url = urlunsplit(
            (parts.scheme, parts.netloc, path + "/api/v1/models", "", "")
        )
        timeout = float(env_get("UAGENT_LMSTUDIO_PROPS_TIMEOUT_SEC", "5") or "5")
        with urlopen(models_url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        models = payload.get("models", []) if isinstance(payload, dict) else payload
        if not isinstance(models, list):
            return None
        for item in models:
            if not isinstance(item, dict):
                continue
            identifiers = {
                str(item.get(key) or "").strip()
                for key in ("id", "key", "name", "model")
            }
            if model not in identifiers:
                continue
            # LM Studio exposes the model's advertised maximum separately from
            # the context length of the currently loaded instance. The latter
            # is the effective limit for requests sent to the running server.
            loaded_instances = item.get("loaded_instances") or []
            if isinstance(loaded_instances, list):
                for instance in loaded_instances:
                    if not isinstance(instance, dict):
                        continue
                    config = instance.get("config") or {}
                    if not isinstance(config, dict):
                        continue
                    context = int(config.get("context_length") or 0)
                    if context > 0:
                        return context
            for key in ("max_context_length", "context_length"):
                context = int(item.get(key) or 0)
                if context > 0:
                    return context
    except Exception:
        pass
    return None


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
    return supports_feature("responses_api", model_id, provider, default=default)


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
    from .providers.provider_caps import DEFAULT_PROVIDER_REGISTRY

    prov = normalize_provider(provider)
    if (
        "responses"
        not in DEFAULT_PROVIDER_REGISTRY.resolve(prov, model_id).capabilities
    ):
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
    from .providers.provider_caps import DEFAULT_PROVIDER_REGISTRY

    prov = normalize_provider(provider)
    if "fim" not in DEFAULT_PROVIDER_REGISTRY.resolve(prov, model_id).capabilities:
        return False
    mid = (model_id or "").strip() or current_model(prov)
    if not mid:
        return True
    flag = supports_fim(mid, prov, default=None)
    if flag is None:
        return True
    return bool(flag)


def supports_image_output(
    model_id: str | None = None,
    provider: str | None = None,
    *,
    default: bool | None = None,
) -> bool | None:
    """Whether the model can generate images."""
    cap = get_capability(model_id, provider)
    if cap is None:
        return default
    try:
        if cap.supports("image_output"):
            return True
        mods = set(getattr(cap, "output_modalities", None) or [])
        if "image" in mods:
            return True
        if mods and "image" not in mods:
            return False
    except Exception:
        pass
    return default


def check_image_output_support(
    model_id: str | None = None,
    provider: str | None = None,
) -> str | None:
    """Error string if model is known not to generate images; else None."""
    mid = (model_id or "").strip()
    if not mid:
        return None
    flag = supports_image_output(mid, provider, default=None)
    if flag is False:
        prov = normalize_provider(provider) or "?"
        return (
            f"Model '{mid}' (provider={prov}) does not support image generation "
            "according to llmcapa. Choose an image-capable model."
        )
    return None


def get_image_capability(
    model_id: str | None = None,
    provider: str | None = None,
) -> Any | None:
    """Return the structured image capability when llmcapa provides it.

    This helper intentionally uses ``getattr`` so UAG remains compatible with
    older llmcapa releases that only expose the generic image modality flags.
    """
    cap = get_capability(model_id, provider)
    return getattr(cap, "image", None) if cap is not None else None


def image_capability_values(
    field: str,
    model_id: str | None = None,
    provider: str | None = None,
) -> tuple[str, ...]:
    """Return a normalized image capability enum, or empty if unknown."""
    image = get_image_capability(model_id, provider)
    values = getattr(image, field, None) if image is not None else None
    if not values or isinstance(values, (str, bytes)):
        return ()
    try:
        return tuple(str(value) for value in values if str(value))
    except TypeError:
        return ()


def image_capability_max_outputs(
    model_id: str | None = None,
    provider: str | None = None,
    *,
    default: int = 4,
) -> int:
    """Return the model-specific image output limit with a safe fallback."""
    image = get_image_capability(model_id, provider)
    value = getattr(image, "max_outputs", None) if image is not None else None
    try:
        limit = int(value)
    except (TypeError, ValueError):
        limit = int(default)
    return max(1, limit)


def check_image_capability_value(
    field: str,
    value: str | None,
    model_id: str | None = None,
    provider: str | None = None,
) -> str | None:
    """Return an error when a known image enum does not contain *value*.

    Unknown capabilities are allowed for backward compatibility and provider
    extensions; only an explicitly known non-empty enum is enforced.
    """
    candidate = str(value or "").strip()
    if not candidate:
        return None
    allowed = image_capability_values(field, model_id, provider)
    if allowed and candidate not in allowed:
        return (
            f"Image capability '{field}' does not support '{candidate}' for "
            f"model '{model_id or '?'}' (provider={normalize_provider(provider) or '?'})"
        )
    return None


def check_image_size(
    size: str,
    model_id: str | None = None,
    provider: str | None = None,
) -> str | None:
    """Validate a WxH image size against known image capability limits."""
    value = str(size or "").strip().lower()
    if value == "auto":
        return None
    import re

    match = re.fullmatch(r"(\d+)x(\d+)", value)
    if not match:
        return f"Invalid image size '{size}'; expected WIDTHxHEIGHT"
    width, height = (int(part) for part in match.groups())
    image = get_image_capability(model_id, provider)
    if image is None:
        return None
    supported = image_capability_values("supported_sizes", model_id, provider)
    if supported and value not in {item.lower() for item in supported}:
        return f"Image size '{size}' is not supported for model '{model_id or '?'}'"
    for attr, actual, label in (
        ("min_width", width, "width"),
        ("max_width", width, "width"),
        ("min_height", height, "height"),
        ("max_height", height, "height"),
    ):
        limit = getattr(image, attr, None)
        if limit is not None and (
            (attr.startswith("min_") and actual < limit)
            or (attr.startswith("max_") and actual > limit)
        ):
            return f"Image {label} {actual} violates capability limit {attr}={limit}"
    divisible = getattr(image, "size_divisible_by", None)
    if divisible and (width % int(divisible) or height % int(divisible)):
        return f"Image size '{size}' must be divisible by {divisible}"
    pixels = width * height
    max_pixels = getattr(image, "max_input_pixels", None)
    if max_pixels and pixels > int(max_pixels):
        return f"Image size '{size}' exceeds max pixels {max_pixels}"
    ratio = width / height
    for attr, violates in (
        ("min_aspect_ratio", lambda limit: ratio < float(limit)),
        ("max_aspect_ratio", lambda limit: ratio > float(limit)),
    ):
        limit = getattr(image, attr, None)
        if limit is not None and violates(limit):
            return f"Image size '{size}' violates capability limit {attr}={limit}"
    return None


def responses_image_mainline_required(
    model_id: str | None = None,
    provider: str | None = None,
) -> bool | None:
    """Return whether Responses image generation needs a mainline model."""
    image = get_image_capability(model_id, provider)
    endpoints = getattr(image, "endpoints", None) if image is not None else None
    value = getattr(endpoints, "responses_mainline_model_required", None)
    return value if value is None else bool(value)


def supports_responses_image_tool(
    model_id: str | None = None,
    provider: str | None = None,
) -> bool | None:
    """Return whether the model exposes image generation through Responses."""
    image = get_image_capability(model_id, provider)
    endpoints = getattr(image, "endpoints", None) if image is not None else None
    value = getattr(endpoints, "responses_image_tool", None)
    return value if value is None else bool(value)


def check_image_streaming(
    stream: bool,
    partial_images: int | None,
    model_id: str | None = None,
    provider: str | None = None,
) -> str | None:
    """Validate streaming parameters against known image capabilities."""
    if partial_images is not None and not stream:
        return "partial_images requires stream=true"
    image = get_image_capability(model_id, provider)
    if image is None:
        return None
    supported = getattr(image, "supports_streaming", None)
    if stream and supported is False:
        return f"Model '{model_id or '?'}' does not support image streaming"
    if partial_images is not None:
        minimum = getattr(image, "partial_images_min", None)
        maximum = getattr(image, "partial_images_max", None)
        if minimum is not None and partial_images < int(minimum):
            return f"partial_images must be at least {minimum}"
        if maximum is not None and partial_images > int(maximum):
            return f"partial_images must be at most {maximum}"
    return None


def supports_embedding(
    model_id: str | None = None,
    provider: str | None = None,
    *,
    default: bool | None = None,
) -> bool | None:
    """Whether the model is an embedding model."""
    cap = get_capability(model_id, provider)
    if cap is None:
        return default
    try:
        mods = set(getattr(cap, "output_modalities", None) or [])
        if "embedding" in mods or "embeddings" in mods:
            return True
        mid = (getattr(cap, "model_id", None) or model_id or "").lower()
        if "embed" in mid:
            return True
        # Known text chat models are not embeddings when modalities are text-only.
        if mods and not ({"embedding", "embeddings"} & mods):
            if "embed" not in mid:
                return False
    except Exception:
        pass
    return default


def check_embedding_support(
    model_id: str | None = None,
    provider: str | None = None,
) -> str | None:
    """Error string if model is known not to be an embedding model; else None."""
    mid = (model_id or "").strip()
    if not mid:
        return None
    flag = supports_embedding(mid, provider, default=None)
    if flag is False:
        prov = normalize_provider(provider) or "?"
        return (
            f"Model '{mid}' (provider={prov}) does not look like an embedding model "
            "according to llmcapa."
        )
    return None


def supports_audio_output(
    model_id: str | None = None,
    provider: str | None = None,
    *,
    default: bool | None = None,
) -> bool | None:
    """Whether the model can generate audio / TTS output.

    Catalog miss (e.g. gpt-4o-mini-tts not listed) returns ``default`` so callers
    may proceed. Do not treat TTS as completion max_tokens.
    """
    cap = get_capability(model_id, provider)
    if cap is None:
        return default
    try:
        if cap.supports("audio_output") or cap.supports("audio"):
            return True
        mods = set(getattr(cap, "output_modalities", None) or [])
        if "audio" in mods:
            return True
        if mods and "audio" not in mods:
            return False
    except Exception:
        pass
    return default


def check_audio_output_support(
    model_id: str | None = None,
    provider: str | None = None,
) -> str | None:
    """Error string if model is known not to produce audio; else None.

    Unknown / missing catalog rows return None (allow).
    """
    mid = (model_id or "").strip()
    if not mid:
        return None
    flag = supports_audio_output(mid, provider, default=None)
    if flag is False:
        prov = normalize_provider(provider) or "?"
        return (
            f"Model '{mid}' (provider={prov}) does not support audio/TTS output "
            "according to llmcapa. Choose a speech-capable model."
        )
    return None


def supports_audio_input(
    model_id: str | None = None,
    provider: str | None = None,
    *,
    default: bool | None = None,
) -> bool | None:
    """Whether the model can accept audio / STT input.

    Catalog miss (e.g. provider-specific whisper deploy not listed) returns
    ``default`` so callers may proceed. Do not treat STT as completion max_tokens.
    """
    cap = get_capability(model_id, provider)
    if cap is None:
        return default
    try:
        if cap.supports("audio_input"):
            return True
        mods = set(getattr(cap, "input_modalities", None) or [])
        if "audio" in mods:
            return True
        if mods and "audio" not in mods:
            return False
    except Exception:
        pass
    return default


def check_audio_input_support(
    model_id: str | None = None,
    provider: str | None = None,
) -> str | None:
    """Error string if model is known not to accept audio input; else None.

    Unknown / missing catalog rows return None (allow).
    """
    mid = (model_id or "").strip()
    if not mid:
        return None
    flag = supports_audio_input(mid, provider, default=None)
    if flag is False:
        prov = normalize_provider(provider) or "?"
        return (
            f"Model '{mid}' (provider={prov}) does not support audio/STT input "
            "according to llmcapa. Choose a speech-to-text capable model."
        )
    return None


def apply_shared_max_tokens(
    kwargs: dict[str, Any],
    *,
    model_id: str | None,
    provider: str | None,
    key: str = "max_tokens",
) -> dict[str, Any]:
    """If UAGENT_MAX_TOKENS is set, clamp and set kwargs[key]."""
    raw = (env_get("UAGENT_MAX_TOKENS") or "").strip()
    if not raw:
        return kwargs
    try:
        n = clamp_max_tokens(int(raw), model_id, provider)
        kwargs[key] = n
    except Exception:
        pass
    return kwargs


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
    return _("Model '%(model_id)s' is deprecated.") % {"model_id": mid}


def format_capability_lines(
    cap: Any,
    *,
    context_window_override: int | None = None,
    context_source: str | None = None,
) -> list[str]:
    """Format a Capability into human-readable detail lines."""
    if cap is None:
        return []
    lines: list[str] = []
    try:
        lines.append(
            _("    model_id: %(value)s") % {"value": getattr(cap, "model_id", "?")}
        )
        lines.append(
            _("    provider: %(value)s") % {"value": getattr(cap, "provider", "?")}
        )
        lines.append(
            _("    Display Name:  %(value)s")
            % {"value": getattr(cap, "display_name", "")}
        )
        ctx = int(
            context_window_override
            if context_window_override is not None
            else getattr(cap, "context_window", 0) or 0
        )
        out = int(getattr(cap, "max_output_tokens", 0) or 0)
        lines.append(_("    Context Window: %(value)s tokens") % {"value": f"{ctx:,}"})
        if context_source:
            lines.append(_("    Context Source: %(value)s") % {"value": context_source})
        lines.append(_("    Max Output:    %(value)s tokens") % {"value": f"{out:,}"})
        lines.append(
            _("    Tokenizer:     %(value)s")
            % {"value": getattr(cap, "tokenizer_name", None) or "?"}
        )
        lines.append(
            _("    License:       %(value)s")
            % {"value": getattr(cap, "license_type", None) or "?"}
        )
        lines.append(
            _("    Knowledge Cutoff: %(value)s")
            % {"value": getattr(cap, "knowledge_cutoff", None) or "?"}
        )
        lines.append(
            _("    Deprecated:    %(value)s")
            % {"value": getattr(cap, "deprecated", False)}
        )
        in_mods = getattr(cap, "input_modalities", None) or []
        out_mods = getattr(cap, "output_modalities", None) or []
        if in_mods:
            lines.append(
                _("    Input:         %(value)s") % {"value": ", ".join(in_mods)}
            )
        if out_mods:
            lines.append(
                _("    Output:        %(value)s") % {"value": ", ".join(out_mods)}
            )
        # Prefer the complete feature list exposed by llmcapa 0.5.x. Keep the
        # explicit probes as a compatibility fallback for older Capability
        # objects that do not implement ``features()``.
        feats: list[str] = []
        try:
            raw_features = cap.features()
            if raw_features:
                feats = sorted({str(feature) for feature in raw_features})
        except Exception:
            pass
        if not feats:
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
            lines.append(
                _("    Features:      %(value)s") % {"value": ", ".join(feats)}
            )
        pricing = getattr(cap, "pricing", None) or {}
        if pricing:
            inp = pricing.get("input_per_1m")
            outp = pricing.get("output_per_1m")
            cur = pricing.get("currency", "USD")
            if inp is not None and outp is not None:
                lines.append(
                    _(
                        "    Pricing:       $%(inp).2f/%(cur)sM in, "
                        "$%(outp).2f/%(cur)sM out"
                    )
                    % {"inp": float(inp), "outp": float(outp), "cur": cur}
                )
                try:
                    sample = cap.estimate_cost(1_000_000, 1_000_000)
                    cost = sample.get("cost")
                    if cost is not None:
                        lines.append(
                            _("    Est. 1M in+out: $%(cost).2f %(currency)s")
                            % {
                                "cost": float(cost),
                                "currency": sample.get("currency", cur),
                            }
                        )
                except Exception:
                    pass
        efforts = None
        try:
            efforts = cap.get_reasoning_effort_values()
        except Exception:
            efforts = getattr(cap, "reasoning_effort_values", None)
        if efforts:
            lines.append(
                _("    Reasoning Efforts: %(value)s")
                % {"value": ", ".join(str(v) for v in efforts)}
            )
        budgets = None
        try:
            budgets = cap.get_thinking_budget_values()
        except Exception:
            budgets = getattr(cap, "thinking_budget_values", None)
        if budgets:
            lines.append(
                _("    Thinking Budgets: %(value)s")
                % {"value": ", ".join(str(v) for v in budgets)}
            )
        levels = None
        try:
            levels = cap.get_thinking_level_values()
        except Exception:
            levels = getattr(cap, "thinking_level_values", None)
        if levels:
            lines.append(
                _("    Thinking Levels: %(value)s")
                % {"value": ", ".join(str(v) for v in levels)}
            )
        control = None
        try:
            control = cap.get_thinking_control()
        except Exception:
            control = getattr(cap, "thinking_control", None)
        if isinstance(control, dict) and control:
            kind = str(control.get("kind") or "?")
            param = str(control.get("parameter") or "?")
            desc = f"{kind} ({param})"
            for key in ("min", "max", "type"):
                if control.get(key) is not None:
                    desc += f" {key}={control.get(key)}"
            lines.append(_("    Thinking Control: %(value)s") % {"value": desc})
        try:
            realtime = cap.supports("realtime")
        except Exception:
            realtime = getattr(cap, "supports_realtime", None)
        if realtime is True:
            lines.append(_("    Realtime:        supported"))
        elif realtime is False:
            lines.append(_("    Realtime:        not supported"))
    except Exception:
        return lines
    return lines


def list_provider_names() -> list[str]:
    """Return sorted llmcapa provider/catalog names, or empty on failure."""
    try:
        import llmcapa

        names = llmcapa.providers()
        return sorted({str(name) for name in (names or []) if str(name)})
    except Exception:
        return []


def list_models(
    provider: str | None = None,
    *,
    include_deprecated: bool = True,
) -> list[Any]:
    """List llmcapa capabilities, provider-scoped when possible.

    Falls back across :func:`provider_candidates` so uag keys such as
    ``gemini``/``grok`` resolve to their canonical catalogs.
    """
    try:
        import llmcapa
    except Exception:
        return []
    prov = normalize_provider(provider)
    if not prov:
        try:
            return list(llmcapa.list_models(include_deprecated=include_deprecated))
        except Exception:
            return []
    seen: set[tuple[str, str]] = set()
    out: list[Any] = []
    for cand in provider_candidates(prov):
        try:
            rows = llmcapa.list_models(
                provider=cand, include_deprecated=include_deprecated
            )
        except Exception:
            continue
        for cap in rows or []:
            key = (
                str(getattr(cap, "provider", cand)),
                str(getattr(cap, "model_id", "")),
            )
            if key not in seen:
                seen.add(key)
                out.append(cap)
    return sorted(
        out,
        key=lambda c: (
            str(getattr(c, "provider", "")),
            str(getattr(c, "model_id", "")),
        ),
    )


def search_models(
    prefix: str,
    provider: str | None = None,
    *,
    include_deprecated: bool = False,
    limit: int | None = None,
) -> list[Any]:
    """Prefix-search llmcapa models (model_id/display_name/aliases)."""
    needle = (prefix or "").strip()
    if not needle:
        return []
    try:
        import llmcapa
    except Exception:
        return []
    prov = normalize_provider(provider)
    cands = provider_candidates(prov) if prov else [None]
    out: list[Any] = []
    for cand in cands:
        try:
            if cand is None:
                hits = llmcapa.search(
                    needle, include_deprecated=include_deprecated, limit=limit
                )
            else:
                hits = llmcapa.search(
                    needle,
                    provider=cand,
                    include_deprecated=include_deprecated,
                    limit=limit,
                )
        except Exception:
            continue
        if hits:
            out.extend(hits)
            break
    if limit is not None and limit >= 0:
        return list(out)[: int(limit)]
    return list(out)


def find_models(**conditions: Any) -> list[Any]:
    """Filter llmcapa models via ``llmcapa.find`` (vision/context/etc.)."""
    try:
        import llmcapa

        rows = llmcapa.find(**conditions)
        return list(rows or [])
    except Exception:
        return []


def find_model_across_providers(model_id: str) -> list[tuple[str, Any]]:
    """Return every ``(provider, Capability)`` matching a model id."""
    mid = (model_id or "").strip()
    if not mid:
        return []
    try:
        import llmcapa

        rows = llmcapa.find_model(mid)
        out: list[tuple[str, Any]] = []
        for item in rows or []:
            try:
                prov, cap = item
                out.append((str(prov), cap))
            except Exception:
                continue
        return out
    except Exception:
        return []


def count_text_tokens(
    text: str,
    model_id: str | None = None,
    provider: str | None = None,
) -> int | None:
    """Count tokens for a single text via llmcapa, or None if unavailable."""
    mid = resolve_model_id_for_tokenizer(model_id, provider)
    if not mid:
        return None
    try:
        import llmcapa

        return int(llmcapa.count_tokens(str(text or ""), mid))
    except Exception:
        raw = (model_id or "").strip()
        if raw and raw != mid:
            try:
                import llmcapa

                return int(llmcapa.count_tokens(str(text or ""), raw))
            except Exception:
                return None
        return None


def get_thinking_control(
    model_id: str | None = None,
    provider: str | None = None,
) -> dict[str, Any] | None:
    """Return normalized thinking control (kind/budget/level/toggle)."""
    cap = get_capability(model_id, provider)
    if cap is None:
        return None
    try:
        control = cap.get_thinking_control()
        return dict(control) if isinstance(control, dict) else None
    except Exception:
        control = getattr(cap, "thinking_control", None)
        return dict(control) if isinstance(control, dict) else None


def get_thinking_level_values(
    model_id: str | None = None,
    provider: str | None = None,
) -> list[str] | None:
    """Return discrete thinking levels (e.g. Gemini) when present."""
    cap = get_capability(model_id, provider)
    if cap is None:
        return None
    try:
        vals = cap.get_thinking_level_values()
        return list(vals) if vals else None
    except Exception:
        vals = getattr(cap, "thinking_level_values", None)
        return list(vals) if vals else None


def supports_thinking_level(
    model_id: str | None = None,
    provider: str | None = None,
    *,
    default: bool | None = None,
) -> bool | None:
    """Discrete thinking-level support, or ``default`` when unknown."""
    return supports_feature("thinking_level", model_id, provider, default=default)


def supports_realtime(
    model_id: str | None = None,
    provider: str | None = None,
    *,
    default: bool | None = None,
) -> bool | None:
    """Realtime API support, or ``default`` when unknown."""
    return supports_feature("realtime", model_id, provider, default=default)


def get_llm_computer_use_capability(
    model_id: str | None = None,
    provider: str | None = None,
) -> Any | None:
    """Return llmcapa Computer Use capability object, or None if unsupported."""
    cap = get_capability(model_id, provider)
    if cap is None:
        return None
    return getattr(cap, "computer_use", None)


def supports_computer_use(
    model_id: str | None = None,
    provider: str | None = None,
    *,
    default: bool | None = None,
) -> bool | None:
    """Computer Use support for a model, or ``default`` when unknown."""
    cap = get_capability(model_id, provider)
    if cap is None:
        return default
    computer_use = getattr(cap, "computer_use", None)
    if computer_use is None:
        return default
    try:
        return bool(getattr(computer_use, "supported", False))
    except Exception:
        return default
