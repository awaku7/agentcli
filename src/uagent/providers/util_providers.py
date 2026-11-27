from __future__ import annotations

import time
import atexit
import os
from typing import Any, Callable, Iterator

from ..i18n import _
from ..env_utils import env_get
from ..auth.provider_credentials import get_provider_api_key
from ..auth.credential_store import get_default_credential_store
from ..runtime.startup_timing import measure_detail
from .provider_caps import ALL_PROVIDERS


def provider_sdk_module(provider: str) -> str | None:
    """Return the importable SDK module required by a provider, if known.

    ``None`` means the provider has its own lazy dependency handling, so the
    CLI should not try to preload it in the background.
    """
    # These providers already perform their own provider-specific lazy
    # installation/fallback handling in make_client(). Do not pre-install a
    # second SDK here.
    if provider in {"grok", "zai", "together", "openrouter"}:
        return None

    if provider == "lmstudio":
        transport = (env_get("UAGENT_LMSTUDIO_TRANSPORT", "") or "").strip().lower()
        return "lmstudio" if transport == "sdk" else "openai"

    if provider in {"gemini", "vertexai"}:
        # Configure the SDK's HTTP backend before cli_startup preloads it.
        _google_genai_http_backend()
        return "google.genai"

    return {
        "claude": "anthropic",
    }.get(provider, "openai")


def _ensure_provider_dependency(provider: str) -> None:
    """Install a provider SDK only when that provider is actually selected."""
    module_name = provider_sdk_module(provider)
    if module_name is None:
        return

    if provider == "claude":
        package_name = "anthropic"
    elif provider in {"gemini", "vertexai"}:
        package_name = "google-genai"
    elif provider == "lmstudio" and module_name == "lmstudio":
        package_name = "lmstudio"
    else:
        package_name = "openai"
    try:
        from .._pip_auto import install_with_status

        if not install_with_status(package_name, module_name=module_name):
            raise ImportError(f"{package_name} is unavailable")
    except ImportError:
        raise
    except Exception as exc:
        raise ImportError(f"Failed to prepare {package_name}: {exc}") from exc


from threading import Lock

_HTTPX_CLIENTS: list[Any] = []
_HTTPX_CLIENTS_LOCK = Lock()
_HTTPX_CLIENTS_REGISTERED = False

# Optional OpenRouter SDK class. Tests may inject a stub via this name.
# Runtime import is attempted lazily inside make_client when still None.
_OpenRouterSDK: Any = None


def _google_genai_http_backend() -> str:
    """Select an SDK HTTP backend compatible with UAG's custom httpx client.

    google-genai 3.x defaults to httpx2. UAG builds standard httpx.Client
    instances for shared timeout and TLS handling, so prefer the SDK's httpx
    backend when available. Respect an explicit user selection; callers must
    not pass a standard httpx.Client when httpx2 is active.
    """
    configured = (env_get("GOOGLE_GENAI_HTTP_CLIENT") or "").strip().lower()
    if configured:
        return configured
    try:
        import httpx  # noqa: F401
    except Exception:
        # Keep the SDK's default backend when the optional httpx extra is not
        # installed (for example, a minimal install using httpx2).
        return ""
    os.environ["GOOGLE_GENAI_HTTP_CLIENT"] = "httpx"
    return "httpx"


def _gemini_tool_retrieval_supported(model_name: str, provider: str) -> bool:
    """Return whether the selected Google model needs the v1beta preview API."""
    try:
        from ..runtime.tool_discovery import (
            gemini_interactions_tool_retrieval_enabled,
        )

        return gemini_interactions_tool_retrieval_enabled(provider, model_name)
    except Exception:
        return False


# OpenRouter app attribution. These headers are intentionally scoped to the
# OpenRouter provider below; they must not be sent to unrelated OpenAI-
# compatible endpoints.
_OPENROUTER_HTTP_REFERER = "https://github.com/awaku7/agentcli"
_OPENROUTER_APP_TITLE = "UAG"
_OPENROUTER_USER_AGENT = "uag"

# ---------------------------------------------------------------------------
# SSL certificate verification auto-fallback
# ---------------------------------------------------------------------------

_ssl_verify_disabled: bool = False
_ssl_verify_lock = Lock()


def is_ssl_verify_disabled() -> bool:
    """Return True if SSL verification has been globally disabled."""
    with _ssl_verify_lock:
        return _ssl_verify_disabled


def set_ssl_verify_disabled(val: bool = True) -> None:
    """Globally disable SSL certificate verification."""
    with _ssl_verify_lock:
        global _ssl_verify_disabled
        _ssl_verify_disabled = val


def is_ssl_cert_error(e: BaseException) -> bool:
    """Detect whether *e* (or its chain) is an SSL certificate verification error."""
    err_text = ""
    try:
        err_text = f"{type(e).__name__}: {e}".lower()
    except Exception:
        pass
    # Common SSL cert error signatures
    ssl_keywords = (
        "certificate verify failed",
        "ssl: certificate_verify_failed",
        "self-signed certificate",
        "certificate has expired",
        "unable to get local issuer certificate",
        "ssl error",
        "tls error",
        "certificate verify",
        "ssl_certificate",
    )
    if any(kw in err_text for kw in ssl_keywords):
        return True
    # Walk the exception chain
    cause = e
    seen: set[int] = set()
    while True:
        try:
            cause = cause.__cause__ or cause.__context__
        except Exception:
            break
        if cause is None:
            break
        try:
            cid = id(cause)
            if cid in seen:
                break
            seen.add(cid)
            cause_text = f"{type(cause).__name__}: {cause}".lower()
            if any(kw in cause_text for kw in ssl_keywords):
                return True
        except Exception:
            break
    return False


def _close_httpx_clients() -> None:
    # Best-effort cleanup for custom httpx clients (OpenAI SDK http_client=...)
    with _HTTPX_CLIENTS_LOCK:
        clients = list(_HTTPX_CLIENTS)
    for c in clients:
        try:
            c.close()
        except Exception:
            pass


def _register_httpx_client(c: Any) -> None:
    global _HTTPX_CLIENTS_REGISTERED
    if c is None:
        return
    with _HTTPX_CLIENTS_LOCK:
        _HTTPX_CLIENTS.append(c)
    if not _HTTPX_CLIENTS_REGISTERED:
        _HTTPX_CLIENTS_REGISTERED = True
        try:
            atexit.register(_close_httpx_clients)
        except Exception:
            pass


def _env_float(name: str, default: float) -> float:
    v = (env_get(name, "") or "").strip()
    if not v:
        return float(default)
    try:
        return float(v)
    except Exception:
        return float(default)


def _env_int(name: str, default: int) -> int:
    v = (env_get(name, "") or "").strip()
    if not v:
        return int(default)
    try:
        return int(float(v))
    except Exception:
        return int(default)


def make_httpx_timeout() -> Any:
    """Build httpx.Timeout from env.

    Env (seconds):
      - UAGENT_LLM_TIMEOUT_CONNECT_SEC (default 10)
      - UAGENT_LLM_TIMEOUT_READ_SEC (default 300)
      - UAGENT_LLM_TIMEOUT_WRITE_SEC (default 300)
      - UAGENT_LLM_TIMEOUT_POOL_SEC (default 10)
    """
    try:
        import httpx
    except Exception:
        return None

    connect = _env_float("UAGENT_LLM_TIMEOUT_CONNECT_SEC", 10)
    read = _env_float("UAGENT_LLM_TIMEOUT_READ_SEC", 300)
    write = _env_float("UAGENT_LLM_TIMEOUT_WRITE_SEC", 300)
    pool = _env_float("UAGENT_LLM_TIMEOUT_POOL_SEC", 10)

    try:
        return httpx.Timeout(connect=connect, read=read, write=write, pool=pool)
    except Exception:
        try:
            return httpx.Timeout(read)
        except Exception:
            return None


def make_httpx_client(
    *, verify: Any = None, event_hooks: Any = None, timeout: Any = None
) -> Any:
    """Create an httpx.Client with timeout from env (best-effort).

    If ``is_ssl_verify_disabled()`` returns True, ``verify`` is forced to False
    regardless of the caller's value.
    """
    if is_ssl_verify_disabled():
        verify = False
    with measure_detail("provider.httpx.import"):
        try:
            import httpx
        except Exception:
            return None

    if timeout is None:
        with measure_detail("provider.httpx.timeout"):
            timeout = make_httpx_timeout()

    kwargs: dict[str, Any] = {}
    if timeout is not None:
        kwargs["timeout"] = timeout
    if verify is not None:
        kwargs["verify"] = verify
    if event_hooks is not None:
        kwargs["event_hooks"] = event_hooks

    with measure_detail("provider.httpx.client"):
        try:
            c = httpx.Client(**kwargs)
        except Exception:
            # Fallback: drop event_hooks if that caused trouble
            try:
                kwargs.pop("event_hooks", None)
                c = httpx.Client(**kwargs)
            except Exception:
                return None

    with measure_detail("provider.httpx.register"):
        _register_httpx_client(c)
    return c


class _OpenRouterChatCompletionsFacade:
    def __init__(self, chat: Any):
        self._chat = chat

    def create(self, **kwargs: Any) -> Any:
        return self._chat.send(**_normalize_openrouter_send_kwargs(kwargs))


class _OpenRouterChatFacade:
    def __init__(self, chat: Any):
        self._chat = chat
        self.completions = _OpenRouterChatCompletionsFacade(chat)

    def send(self, **kwargs: Any) -> Any:
        return self._chat.send(**_normalize_openrouter_send_kwargs(kwargs))

    def __getattr__(self, name: str) -> Any:
        return getattr(self._chat, name)


class _OpenRouterResponsesFacade:
    def __init__(self, responses: Any):
        self._responses = responses

    def create(self, **kwargs: Any) -> Any:
        return self._responses.send(**_normalize_openrouter_send_kwargs(kwargs))

    def send(self, **kwargs: Any) -> Any:
        return self._responses.send(**_normalize_openrouter_send_kwargs(kwargs))

    def __getattr__(self, name: str) -> Any:
        return getattr(self._responses, name)


class _OpenRouterBetaFacade:
    def __init__(self, responses: Any):
        self.responses = responses


class _OpenRouterCompatClient:
    def __init__(self, client: Any):
        self._client = client
        self.chat = _OpenRouterChatFacade(client.chat)
        self.responses = _OpenRouterResponsesFacade(client.beta.responses)
        self.beta = _OpenRouterBetaFacade(self.responses)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


def _normalize_openrouter_send_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    out = dict(kwargs)
    # OpenRouter Responses API does not support context_management.
    out.pop("context_management", None)
    # OpenRouter Responses rejects previous_response_id (schema expects null).
    out.pop("previous_response_id", None)
    extra_body = out.pop("extra_body", None)
    if not isinstance(extra_body, dict):
        return out

    reasoning = extra_body.get("reasoning")
    if isinstance(reasoning, dict):
        current_reasoning = out.get("reasoning")
        if not isinstance(current_reasoning, dict):
            current_reasoning = {}

        if reasoning.get("enabled") is False:
            out.pop("reasoning", None)
        else:
            merged_reasoning = dict(current_reasoning)
            for key in ("effort", "summary", "enabled", "max_tokens"):
                value = reasoning.get(key)
                if value is not None:
                    merged_reasoning[key] = value

            enabled = merged_reasoning.pop("enabled", None)
            if enabled is False:
                out.pop("reasoning", None)
            elif merged_reasoning:
                out["reasoning"] = merged_reasoning

    provider = extra_body.get("provider")
    if isinstance(provider, dict):
        current_provider = out.get("provider")
        if isinstance(current_provider, dict):
            merged_provider = dict(current_provider)
            merged_provider.update({k: v for k, v in provider.items() if v is not None})
            out["provider"] = merged_provider
        elif current_provider is None:
            out["provider"] = {k: v for k, v in provider.items() if v is not None}

    return out


def detect_provider() -> str:
    """UAGENT_PROVIDER から利用プロバイダを判定する。未設定/未知は ValueError。"""
    p = env_get("UAGENT_PROVIDER")
    if not p:
        raise ValueError(_("Environment variable UAGENT_PROVIDER is not set."))

    p = p.lower()
    if p not in ALL_PROVIDERS:
        raise ValueError(_("Unknown provider: %(provider)s") % {"provider": p})
    return p


def get_model_name() -> str:
    """利用プロバイダに応じてモデル名を取得する（scheck.py の main ロジックに準拠）"""
    provider = detect_provider()
    if provider == "azure":
        return env_get("UAGENT_AZURE_DEPNAME", "gpt-6.2-sol") or "gpt-6.2-sol"
    if provider == "openai":
        return env_get("UAGENT_OPENAI_DEPNAME", "gpt-6-luna") or "gpt-6-luna"
    if provider == "meta":
        return env_get("UAGENT_META_DEPNAME", "muse-spark-1.3") or "muse-spark-1.3"
    if provider == "pfn":
        return env_get("UAGENT_PFN_DEPNAME", "plamo-3.0-prime") or "plamo-3.0-prime"
    if provider == "bedrock":
        return (
            env_get("UAGENT_BEDROCK_DEPNAME", "openai.gpt-oss-120b")
            or "openai.gpt-oss-120b"
        )
    if provider == "openrouter":
        return (
            env_get("UAGENT_OPENROUTER_DEPNAME", "openai/gpt-6-luna")
            or "openai/gpt-6-luna"
        )
    if provider == "perplexity":
        return (
            env_get("UAGENT_PERPLEXITY_DEPNAME", "perplexity/kimi-k3")
            or "perplexity/kimi-k3"
        )
    if provider == "inception":
        return env_get("UAGENT_INCEPTION_DEPNAME", "mercury-3") or "mercury-3"
    if provider == "grok":
        return env_get("UAGENT_GROK_DEPNAME", "grok-4.7") or "grok-4.7"
    if provider == "gemini":
        return (
            env_get("UAGENT_GEMINI_DEPNAME", "gemini-4-hydrogen") or "gemini-4-hydrogen"
        )
    if provider == "vertexai":
        return (
            env_get("UAGENT_VERTEXAI_DEPNAME", "gemini-4-hydrogen")
            or "gemini-4-hydrogen"
        )
    if provider == "claude":
        return (
            env_get("UAGENT_CLAUDE_DEPNAME", "claude-sonnet-5-5") or "claude-sonnet-5-5"
        )
    if provider == "ollama":
        return env_get("UAGENT_OLLAMA_DEPNAME", "llama3.3") or "llama3.3"
    if provider == "llama_cpp":
        return env_get("UAGENT_LLAMA_CPP_DEPNAME", "local-model") or "local-model"
    if provider == "vllm":
        # vLLM requires the request's model value to match the model it serves.
        # Startup validation reports a missing name rather than guessing one.
        return (env_get("UAGENT_VLLM_DEPNAME", "") or "").strip()
    if provider == "nvidia":
        return (
            env_get("UAGENT_NVIDIA_DEPNAME", "nvidia/nemotron-3-nano-30b-a3b")
            or "nvidia/nemotron-3-nano-30b-a3b"
        )
    if provider == "deepseek":
        return env_get("UAGENT_DEEPSEEK_DEPNAME", "deepseek-flash") or "deepseek-flash"
    if provider == "zai":
        return env_get("UAGENT_ZAI_DEPNAME", "glm-5.3") or "glm-5.3"
    if provider == "alibaba":
        return env_get("UAGENT_ALIBABA_DEPNAME", "qwen3.7-plus") or "qwen3.7-plus"
    if provider == "moonshot":
        return env_get("UAGENT_MOONSHOT_DEPNAME", "kimi-k3.1-pro") or "kimi-k3.1-pro"
    if provider == "mimo":
        return env_get("UAGENT_MIMO_DEPNAME", "mimo-v2.6-pro") or "mimo-v2.6-pro"
    if provider == "lmstudio":
        return env_get("UAGENT_LMSTUDIO_DEPNAME", "local-model") or "local-model"
    if provider == "foundry_local":
        return env_get("UAGENT_FOUNDRY_LOCAL_DEPNAME", "phi-4-mini") or "phi-4-mini"
    if provider == "minimax":
        return env_get("UAGENT_MINIMAX_DEPNAME", "MiniMax-M3") or "MiniMax-M3"
    if provider == "hf":
        return (
            env_get("UAGENT_HF_DEPNAME", "openai/gpt-oss-120b") or "openai/gpt-oss-120b"
        )
    if provider == "sakana":
        return env_get("UAGENT_SAKANA_DEPNAME", "fugu") or "fugu"
    if provider == "novita":
        return env_get("UAGENT_NOVITA_DEPNAME", "tencent/hy3") or "tencent/hy3"
    if provider == "sakura":
        return env_get("UAGENT_SAKURA_DEPNAME", "llm") or "llm"
    if provider == "sarashina":
        return (
            env_get("UAGENT_SARASHINA_DEPNAME", "sarashina3.2-mini-thinking")
            or "sarashina3.2-mini-thinking"
        )
    if provider == "together":
        return (
            env_get("UAGENT_TOGETHER_DEPNAME", "MiniMaxAI/MiniMax-M3")
            or "MiniMaxAI/MiniMax-M3"
        )
    if provider == "vercel":
        return (
            env_get("UAGENT_VERCEL_DEPNAME", "openai/gpt-6-luna") or "openai/gpt-6-luna"
        )
    return env_get("UAGENT_OPENAI_DEPNAME", "gpt-6-luna") or "gpt-6-luna"


def _parse_wait_seconds_from_headers(headers: Any, cap: float = 65.0) -> float | None:
    """Compute conservative wait seconds from common rate-limit headers.

    We intentionally avoid returning raw header values.
    """

    def _get(name: str) -> Any:
        try:
            if headers is None:
                return None
            # httpx.Headers supports .get
            return headers.get(name)
        except Exception:
            try:
                if isinstance(headers, dict):
                    return headers.get(name) or headers.get(name.lower())
            except Exception:
                return None
        return None

    def _to_float(v: Any) -> float | None:
        try:
            if v is None:
                return None
            if isinstance(v, (int, float)):
                fv = float(v)
                return fv if fv >= 0 else None
            s = str(v).strip()
            if s.endswith("s"):
                s = s[:-1].strip()
            fv = float(s)
            return fv if fv >= 0 else None
        except Exception:
            return None

    # Retry-After (seconds)
    ra = _to_float(_get("retry-after"))
    if ra is None:
        ra = _to_float(_get("x-ms-retry-after-ms"))
        if ra is not None:
            ra = ra / 1000.0
    if ra is not None:
        return min(cap, ra)

    waits: list[float] = []
    for k in ("x-ratelimit-reset-requests", "x-ratelimit-reset-tokens"):
        fv = _to_float(_get(k))
        if fv is None:
            continue

        # Heuristic: large -> epoch seconds; small -> delta seconds
        if fv > 10_000:
            delta = fv - time.time()
            if delta >= 0:
                waits.append(delta)
        else:
            waits.append(fv)

    if waits:
        return min(cap, max(waits))

    return None


def _provider_api_key(core: Any, provider: str) -> str | None:
    store = getattr(core, "credential_store", None) or get_default_credential_store()
    getter = getattr(core, "get_env", None)
    return get_provider_api_key(
        provider,
        store=store,
        env_getter=getter if callable(getter) else None,
    )


_VERTEXAI_LOCATION_ENV_NAMES = (
    "UAGENT_VERTEXAI_LOCATION",
    "UAGENT_GOOGLE_LOCATION",
    "GOOGLE_CLOUD_LOCATION",
)


def _vertexai_explicit_location() -> str | None:
    for name in _VERTEXAI_LOCATION_ENV_NAMES:
        location = env_get(name)
        if location:
            return location
    return None


def _vertexai_cached_location(core: Any, model_name: str) -> str | None:
    try:
        cache = getattr(core, "_vertexai_auto_location_cache", {})
        value = cache.get(model_name) if isinstance(cache, dict) else None
        return str(value).strip() if value else None
    except Exception:
        return None


def _remember_vertexai_location(core: Any, model_name: str, location: str) -> None:
    try:
        cache = getattr(core, "_vertexai_auto_location_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            setattr(core, "_vertexai_auto_location_cache", cache)
        cache[model_name] = location
    except Exception:
        pass


def make_vertexai_client(
    core: Any,
    model_name: str,
    *,
    location_override: str | None = None,
) -> Any:
    """Create a Vertex AI client, optionally pinned to a fallback location."""
    http_backend = _google_genai_http_backend()
    from google import genai  # lazy

    if genai is None:
        raise RuntimeError("[FATAL] " + _("google-genai package is not installed."))

    api_key = _provider_api_key(core, "VERTEXAI")
    project = (
        env_get("UAGENT_VERTEXAI_PROJECT") or env_get("GOOGLE_CLOUD_PROJECT") or None
    )
    credentials_path = env_get("UAGENT_GOOGLE_CREDENTIALS") or None
    credentials = None
    if credentials_path and not api_key:
        try:
            import google.auth  # type: ignore[import-not-found]

            credentials, detected_project = google.auth.load_credentials_from_file(
                credentials_path,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
            if not project and detected_project:
                project = detected_project
        except Exception as exc:
            raise RuntimeError(
                "[FATAL] "
                + _(
                    "Failed to load Vertex AI credentials file %(path)s: %(err)s",
                    default="Failed to load Vertex AI credentials file %(path)s: %(err)s",
                )
                % {"path": credentials_path, "err": str(exc)}
            ) from exc

    explicit_location = _vertexai_explicit_location()
    if location_override:
        location = location_override
    elif explicit_location:
        location = explicit_location
    elif api_key and not project:
        # API-key-only Vertex AI Express mode must not use a
        # project-scoped location with an empty project.
        location = None
    else:
        location = _vertexai_cached_location(core, model_name) or "global"

    http_options: dict[str, Any] = {}
    if http_backend == "httpx":
        try:
            httpx_client = make_httpx_client()
            if httpx_client is not None:
                http_options["httpx_client"] = httpx_client
        except Exception:
            pass

    kwargs: dict[str, Any] = {"vertexai": True}
    if api_key:
        kwargs["api_key"] = api_key
    if credentials is not None:
        kwargs["credentials"] = credentials
    if project:
        kwargs["project"] = project
    if location:
        kwargs["location"] = location
    if http_options:
        kwargs["http_options"] = http_options

    try:
        client = genai.Client(**kwargs)
    except Exception:
        kwargs.pop("http_options", None)
        try:
            client = genai.Client(**kwargs)
        except Exception:
            fallback_kwargs: dict[str, Any] = {"vertexai": True}
            if api_key:
                fallback_kwargs["api_key"] = api_key
            elif credentials is not None:
                fallback_kwargs["credentials"] = credentials
            if project:
                fallback_kwargs["project"] = project
            if location:
                fallback_kwargs["location"] = location
            client = genai.Client(**fallback_kwargs)

    try:
        from google.genai import models as gm

        gm.Models._logged_afc_warning = True
        if hasattr(gm, "AsyncModels"):
            gm.AsyncModels._logged_afc_warning = True
    except Exception:
        pass
    return client


def _vertexai_auto_location_enabled(core: Any) -> bool:
    if _vertexai_explicit_location():
        return False
    api_key = _provider_api_key(core, "VERTEXAI")
    project = (
        env_get("UAGENT_VERTEXAI_PROJECT") or env_get("GOOGLE_CLOUD_PROJECT") or None
    )
    return not (api_key and not project)


def _vertexai_region_candidates(
    model_name: str, current_location: str | None
) -> list[str]:
    """Return catalogued alternative locations for a Vertex model."""
    try:
        import llmcapa

        regions = llmcapa.list_regions(
            provider="vertex-ai",
            model_id=model_name,
            include_global=True,
        )
    except Exception:
        return []
    current = (current_location or "").strip().casefold()
    result: list[str] = []
    for region in regions or []:
        value = str(region).strip()
        if value and value.casefold() != current and value not in result:
            result.append(value)
    return result


def _is_vertexai_not_found(error: BaseException) -> bool:
    text = str(error).casefold()
    code = getattr(error, "code", None)
    if callable(code):
        try:
            code = code()
        except Exception:
            code = None
    response = getattr(error, "response", None)
    status_code = getattr(response, "status_code", None)
    is_404 = code == 404 or status_code == 404 or "404" in text
    is_not_found = (
        "not_found" in text
        or "not found" in text
        or str(code).casefold().endswith("not_found")
    )
    return bool(is_404 and is_not_found)


def call_vertexai_with_region_fallback(
    core: Any,
    client: Any,
    model_name: str,
    request: Callable[[Any], Any],
    *,
    provider: str,
) -> Any:
    """Retry a Vertex AI request in catalogued regions after a 404."""
    if provider != "vertexai" or not _vertexai_auto_location_enabled(core):
        return request(client)
    original_error: Exception | None = None
    try:
        return request(client)
    except Exception as error:
        if not _is_vertexai_not_found(error):
            raise
        original_error = error
    current_location = _vertexai_cached_location(core, model_name) or "global"
    for location in _vertexai_region_candidates(model_name, current_location):
        retry_client = make_vertexai_client(
            core, model_name, location_override=location
        )
        try:
            response = request(retry_client)
        except Exception as retry_error:
            if _is_vertexai_not_found(retry_error):
                continue
            raise
        _remember_vertexai_location(core, model_name, location)
        return response
    if original_error is not None:
        raise original_error
    raise RuntimeError("Vertex AI region fallback ended without a response")


def iter_vertexai_stream_with_region_fallback(
    core: Any,
    client: Any,
    model_name: str,
    request: Callable[[Any], Any],
    *,
    provider: str,
) -> Iterator[Any]:
    """Stream a Vertex response; retry only if a 404 occurs before any chunk."""
    if provider != "vertexai" or not _vertexai_auto_location_enabled(core):
        yield from request(client)
        return

    current_location = _vertexai_cached_location(core, model_name) or "global"
    candidates: list[str] | None = None
    tried = {current_location.casefold()}
    original_error: Exception | None = None
    active_client = client
    active_location = current_location
    while True:
        yielded = False
        try:
            for chunk in request(active_client):
                if not yielded:
                    yielded = True
                    if active_client is not client:
                        _remember_vertexai_location(core, model_name, active_location)
                yield chunk
            if active_client is not client:
                _remember_vertexai_location(core, model_name, active_location)
            return
        except Exception as error:
            if yielded or not _is_vertexai_not_found(error):
                raise
            if original_error is None:
                original_error = error
            if candidates is None:
                candidates = _vertexai_region_candidates(model_name, current_location)
            next_location = next(
                (item for item in candidates if item.casefold() not in tried),
                None,
            )
            if next_location is None:
                raise original_error
            tried.add(next_location.casefold())
            active_location = next_location
            active_client = make_vertexai_client(
                core, model_name, location_override=next_location
            )


def make_client(core: Any) -> tuple[str, Any, str]:
    """利用する LLM プロバイダに応じてクライアントを生成する。"""

    with measure_detail("provider.detect"):
        provider = detect_provider()
    if provider in {"gemini", "vertexai"}:
        # Select google-genai 3.x's HTTP backend before dependency preloading
        # imports the SDK; its backend choice is initialized with the module.
        _google_genai_http_backend()
    with measure_detail("provider.dependency"):
        _ensure_provider_dependency(provider)
    with measure_detail("provider.model"):
        model_name = get_model_name()

    if provider == "azure":
        from openai import AzureOpenAI  # lazy

        base_url = core.get_env_url("UAGENT_AZURE_BASE_URL")
        api_key = _provider_api_key(core, "AZURE")
        api_version = core.get_env("UAGENT_AZURE_API_VERSION")

        http_client = make_httpx_client()

        try:
            client = AzureOpenAI(
                azure_endpoint=base_url,
                api_key=api_key,
                api_version=api_version,
                http_client=http_client,
            )
        except TypeError:
            client = AzureOpenAI(
                azure_endpoint=base_url,
                api_key=api_key,
                api_version=api_version,
            )

        return provider, client, model_name

    if provider in {"openai", "meta"}:
        with measure_detail("provider.openai.sdk_import"):
            from openai import OpenAI  # lazy

        credential_provider = "META" if provider == "meta" else "OPENAI"
        with measure_detail("provider.openai.credentials"):
            api_key = _provider_api_key(core, credential_provider)
        with measure_detail("provider.openai.base_url"):
            base_url = core.get_env_url(
                (
                    "UAGENT_META_BASE_URL"
                    if provider == "meta"
                    else "UAGENT_OPENAI_BASE_URL"
                ),
                (
                    "https://api.meta.ai/v1"
                    if provider == "meta"
                    else "https://api.openai.com/v1"
                ),
            )

        def _hook(resp: Any) -> None:
            try:
                status = getattr(resp, "status_code", None)
                if status not in (429, 503):
                    return
            except Exception:
                return

        with measure_detail("provider.openai.http_client"):
            http_client = make_httpx_client(event_hooks={"response": [_hook]})

        with measure_detail("provider.openai.sdk_client"):
            try:
                client = OpenAI(
                    api_key=api_key, base_url=base_url, http_client=http_client
                )
            except TypeError:
                client = OpenAI(api_key=api_key, base_url=base_url)

        return provider, client, model_name

    if provider == "perplexity":
        from openai import OpenAI  # lazy

        api_key = _provider_api_key(core, "PERPLEXITY")
        base_url = core.get_env_url(
            "UAGENT_PERPLEXITY_BASE_URL",
            "https://api.perplexity.ai/orchestrator/v1",
        )
        http_client = make_httpx_client()
        try:
            client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)
        except TypeError:
            client = OpenAI(api_key=api_key, base_url=base_url)

        return provider, client, model_name

    if provider == "pfn":
        from openai import OpenAI  # lazy

        api_key = _provider_api_key(core, "PFN")
        base_url = core.get_env_url(
            "UAGENT_PFN_BASE_URL",
            "https://api.platform.preferredai.jp/v1",
        )

        http_client = make_httpx_client()

        try:
            client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)
        except TypeError:
            client = OpenAI(api_key=api_key, base_url=base_url)

        return provider, client, model_name

    if provider == "bedrock":
        from openai import OpenAI  # lazy

        api_key = _provider_api_key(core, "BEDROCK") or "dummy"
        base_url = core.get_env_url("UAGENT_BEDROCK_BASE_URL")

        def _hook(resp: Any) -> None:
            try:
                status = getattr(resp, "status_code", None)
                if status not in (429, 503):
                    return
            except Exception:
                return

        http_client = make_httpx_client(event_hooks={"response": [_hook]})

        try:
            client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)
        except TypeError:
            client = OpenAI(api_key=api_key, base_url=base_url)

        return provider, client, model_name

    if provider == "nvidia":
        from openai import OpenAI  # lazy

        api_key = _provider_api_key(core, "NVIDIA") or "dummy"
        base_url = core.get_env_url(
            "UAGENT_NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"
        )

        http_client = make_httpx_client()

        try:
            client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)
        except TypeError:
            client = OpenAI(api_key=api_key, base_url=base_url)

        return provider, client, model_name

    if provider == "ollama":
        from openai import OpenAI  # lazy

        api_key = _provider_api_key(core, "OLLAMA") or "dummy"
        base_url = core.get_env_url(
            "UAGENT_OLLAMA_BASE_URL", "http://localhost:11434/v1"
        )
        timeout_sec = _env_float("UAGENT_OLLAMA_TIMEOUT_SEC", 60.0)

        http_client = make_httpx_client(timeout=timeout_sec)

        try:
            client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)
        except TypeError:
            client = OpenAI(api_key=api_key, base_url=base_url)

        return provider, client, model_name

    if provider == "llama_cpp":
        from openai import OpenAI  # llama-server exposes an OpenAI-compatible API

        api_key = env_get("UAGENT_LLAMA_CPP_API_KEY") or "dummy"
        base_url = core.get_env_url(
            "UAGENT_LLAMA_CPP_BASE_URL", "http://localhost:8080/v1"
        )
        timeout_sec = _env_float("UAGENT_LLAMA_CPP_TIMEOUT_SEC", 120.0)
        http_client = make_httpx_client(timeout=timeout_sec)
        try:
            client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)
        except TypeError:
            client = OpenAI(api_key=api_key, base_url=base_url)
        return provider, client, model_name

    if provider == "vllm":
        from openai import OpenAI  # vLLM exposes an OpenAI-compatible Chat API

        api_key = _provider_api_key(core, "VLLM") or "dummy"
        base_url = core.get_env_url("UAGENT_VLLM_BASE_URL", "http://localhost:8000/v1")
        timeout_sec = _env_float("UAGENT_VLLM_TIMEOUT_SEC", 120.0)
        http_client = make_httpx_client(timeout=timeout_sec)
        try:
            client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)
        except TypeError:
            client = OpenAI(api_key=api_key, base_url=base_url)
        return provider, client, model_name

    if provider == "openrouter":
        from openai import OpenAI  # lazy (fallback)

        # Prefer test/module injection, then optional official SDK.
        # Local import must not shadow the module attribute used by tests.
        sdk_cls = _OpenRouterSDK
        if sdk_cls is None:
            try:
                from openrouter import OpenRouter as sdk_cls  # type: ignore
            except Exception:
                try:
                    from .._pip_auto import install_with_status as _install_openrouter

                    if _install_openrouter(
                        "openrouter", "openrouter", display_name="OpenRouter SDK"
                    ):
                        from openrouter import OpenRouter as sdk_cls  # type: ignore
                except Exception:
                    sdk_cls = None

        api_key = _provider_api_key(core, "OPENROUTER") or "dummy"
        base_url = core.get_env_url(
            "UAGENT_OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        )

        http_client = make_httpx_client()
        if http_client is not None:
            try:
                http_client.headers["User-Agent"] = _OPENROUTER_USER_AGENT
            except Exception:
                pass

        if sdk_cls is not None:
            try:
                raw_client = sdk_cls(
                    api_key=api_key,
                    http_referer=_OPENROUTER_HTTP_REFERER,
                    x_open_router_title=_OPENROUTER_APP_TITLE,
                    server_url=base_url,
                    client=http_client,
                )
            except TypeError:
                try:
                    raw_client = sdk_cls(
                        api_key=api_key,
                        http_referer=_OPENROUTER_HTTP_REFERER,
                        x_open_router_title=_OPENROUTER_APP_TITLE,
                        server_url=base_url,
                    )
                except TypeError:
                    raw_client = sdk_cls(api_key=api_key)

            client = _OpenRouterCompatClient(raw_client)
            return provider, client, model_name

        # Fallback for environments without the official OpenRouter SDK.
        default_headers = {
            "HTTP-Referer": _OPENROUTER_HTTP_REFERER,
            "X-OpenRouter-Title": _OPENROUTER_APP_TITLE,
            "User-Agent": _OPENROUTER_USER_AGENT,
        }

        try:
            client = OpenAI(
                api_key=api_key,
                base_url=base_url,
                default_headers=default_headers,
                http_client=http_client,
            )
        except TypeError:
            try:
                # Fallback for older OpenAI SDKs that don't accept default_headers / http_client
                client = OpenAI(
                    api_key=api_key,
                    base_url=base_url,
                    default_headers=default_headers,
                )
            except TypeError:
                client = OpenAI(api_key=api_key, base_url=base_url)

        return provider, client, model_name

    if provider == "inception":
        # Inception's Mercury API is OpenAI Chat Completions compatible.
        from openai import OpenAI  # lazy

        api_key = _provider_api_key(core, "INCEPTION")
        base_url = core.get_env_url(
            "UAGENT_INCEPTION_BASE_URL", "https://api.inceptionlabs.ai/v1"
        )
        http_client = make_httpx_client()
        try:
            client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)
        except TypeError:
            client = OpenAI(api_key=api_key, base_url=base_url)
        return provider, client, model_name

    if provider == "grok":
        api_key = (_provider_api_key(core, "GROK") or "").strip()

        # UAGENT_GROK_USE_XAI_SDK: "1" (default) uses xai_sdk (gRPC), "0" uses OpenAI SDK (REST).
        # Zscaler/proxy environments may need "0" because gRPC/HTTP2 is blocked.
        _use_xai_sdk = env_get("UAGENT_GROK_USE_XAI_SDK", "1") or "1"
        _use_xai_sdk = str(_use_xai_sdk).strip().lower() not in (
            "0",
            "false",
            "no",
            "off",
        )

        if not _use_xai_sdk:
            _ensure_provider_dependency("openai")
            from openai import OpenAI

            base_url = core.get_env_url("UAGENT_GROK_BASE_URL", "https://api.x.ai/v1")
            client = OpenAI(api_key=api_key, base_url=base_url)
            return provider, client, model_name

        # Auto-install xai-sdk if missing; fallback to OpenAI SDK
        XAIClient = None
        try:
            from .._pip_auto import install_with_status as _install_xai_sdk

            if _install_xai_sdk("xai-sdk", "xai_sdk", display_name="xai-sdk"):
                from xai_sdk import Client as XAIClient
        except Exception:
            pass

        if XAIClient is not None:
            client = XAIClient(
                api_key=api_key,
                use_insecure_channel=is_ssl_verify_disabled(),
            )
        else:
            _ensure_provider_dependency("openai")
            from openai import OpenAI

            base_url = core.get_env_url("UAGENT_GROK_BASE_URL", "https://api.x.ai/v1")
            client = OpenAI(api_key=api_key, base_url=base_url)

        return provider, client, model_name

    if provider == "deepseek":
        from openai import OpenAI  # lazy

        api_key = _provider_api_key(core, "DEEPSEEK")
        base_url = core.get_env_url(
            "UAGENT_DEEPSEEK_BASE_URL", "https://api.deepseek.com"
        )

        http_client = make_httpx_client()

        try:
            client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)
        except TypeError:
            client = OpenAI(api_key=api_key, base_url=base_url)

        return provider, client, model_name

    if provider == "zai":
        # Auto-install zai-sdk if missing
        from .._pip_auto import install_with_status as _install_zai_sdk

        ZaiClient = None
        if _install_zai_sdk("zai-sdk", "zai", display_name="zai-sdk"):
            from zai import ZaiClient

        api_key = _provider_api_key(core, "ZAI")
        base_url = core.get_env_url(
            "UAGENT_ZAI_BASE_URL", "https://api.z.ai/api/paas/v4/"
        )

        http_client = make_httpx_client()

        if ZaiClient is not None:
            try:
                client = ZaiClient(
                    api_key=api_key, base_url=base_url, http_client=http_client
                )
            except TypeError:
                client = ZaiClient(api_key=api_key, base_url=base_url)
        else:
            from openai import OpenAI  # fallback to OpenAI-compatible

            try:
                client = OpenAI(
                    api_key=api_key, base_url=base_url, http_client=http_client
                )
            except TypeError:
                client = OpenAI(api_key=api_key, base_url=base_url)

        return provider, client, model_name

    if provider == "alibaba":
        from openai import OpenAI  # lazy

        api_key = _provider_api_key(core, "ALIBABA")
        base_url = core.get_env_url(
            "UAGENT_ALIBABA_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

        http_client = make_httpx_client()

        try:
            client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)
        except TypeError:
            client = OpenAI(api_key=api_key, base_url=base_url)

        return provider, client, model_name

    if provider == "moonshot":
        from openai import OpenAI  # lazy

        api_key = _provider_api_key(core, "MOONSHOT")
        base_url = core.get_env_url(
            "UAGENT_MOONSHOT_BASE_URL", "https://api.moonshot.cn/v1"
        )

        http_client = make_httpx_client()

        try:
            client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)
        except TypeError:
            client = OpenAI(api_key=api_key, base_url=base_url)

        return provider, client, model_name

    if provider == "mimo":
        from openai import OpenAI  # lazy

        api_key = _provider_api_key(core, "MIMO")
        base_url = core.get_env_url(
            "UAGENT_MIMO_BASE_URL", "https://api.xiaomimimo.com/v1"
        )

        http_client = make_httpx_client()

        try:
            client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)
        except TypeError:
            client = OpenAI(api_key=api_key, base_url=base_url)

        return provider, client, model_name

    if provider == "lmstudio":
        from .llm_lmstudio import make_lmstudio_client

        return provider, make_lmstudio_client(core), model_name

    if provider == "foundry_local":
        from .llm_foundry_local import make_foundry_local_client

        client, effective_model = make_foundry_local_client(core, model_name)
        return provider, client, effective_model

    if provider == "minimax":
        from openai import OpenAI  # lazy

        api_key = _provider_api_key(core, "MINIMAX")
        base_url = core.get_env_url("UAGENT_MINIMAX_BASE_URL", "https://api.minimax.io")

        http_client = make_httpx_client()

        try:
            client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)
        except TypeError:
            client = OpenAI(api_key=api_key, base_url=base_url)

        return provider, client, model_name

    if provider == "hf":
        from openai import OpenAI  # lazy

        api_key = _provider_api_key(core, "HF")
        base_url = core.get_env_url(
            "UAGENT_HF_BASE_URL",
            "https://router.huggingface.co/v1",
        )

        http_client = make_httpx_client()

        try:
            client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)
        except TypeError:
            client = OpenAI(api_key=api_key, base_url=base_url)

        return provider, client, model_name

    if provider == "novita":
        from openai import OpenAI  # lazy

        api_key = _provider_api_key(core, "NOVITA")
        base_url = core.get_env_url(
            "UAGENT_NOVITA_BASE_URL",
            "https://api.novita.ai/openai",
        )

        http_client = make_httpx_client()

        try:
            client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)
        except TypeError:
            client = OpenAI(api_key=api_key, base_url=base_url)

        return provider, client, model_name

    if provider == "sakura":
        from openai import OpenAI  # lazy

        api_key = _provider_api_key(core, "SAKURA")
        base_url = core.get_env_url(
            "UAGENT_SAKURA_BASE_URL",
            "https://api.ai.sakura.ad.jp/v1",
        )

        http_client = make_httpx_client()

        try:
            client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)
        except TypeError:
            client = OpenAI(api_key=api_key, base_url=base_url)

        return provider, client, model_name

    if provider == "sarashina":
        from openai import OpenAI  # lazy

        api_key = _provider_api_key(core, "SARASHINA")
        base_url = core.get_env_url(
            "UAGENT_SARASHINA_BASE_URL", "https://api.sarashina.ai/v1"
        )
        http_client = make_httpx_client()
        try:
            client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)
        except TypeError:
            client = OpenAI(api_key=api_key, base_url=base_url)
        return provider, client, model_name

    if provider == "sakana":
        from openai import OpenAI  # lazy

        api_key = _provider_api_key(core, "SAKANA")
        base_url = core.get_env_url(
            "UAGENT_SAKANA_BASE_URL",
            "https://api.sakana.ai/v1",
        )

        http_client = make_httpx_client()

        try:
            client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)
        except TypeError:
            client = OpenAI(api_key=api_key, base_url=base_url)

        return provider, client, model_name

    if provider == "together":
        # Auto-install together SDK if missing; fallback to OpenAI-compatible
        try:
            from together import Together as TogetherClient
        except Exception:
            from .._pip_auto import install_with_status as _install_together

            if _install_together(
                "together", "together", display_name="Together AI SDK"
            ):
                from together import Together as TogetherClient
            else:
                _ensure_provider_dependency("openai")
                from openai import OpenAI as TogetherClient

        api_key = _provider_api_key(core, "TOGETHER")
        base_url = core.get_env_url(
            "UAGENT_TOGETHER_BASE_URL",
            "https://api.together.ai/v1",
        )

        http_client = make_httpx_client()

        try:
            client = TogetherClient(
                api_key=api_key, base_url=base_url, http_client=http_client
            )
        except TypeError:
            client = TogetherClient(api_key=api_key, base_url=base_url)

        return provider, client, model_name

    if provider == "vercel":
        from openai import OpenAI  # lazy

        api_key = _provider_api_key(core, "VERCEL")
        base_url = core.get_env_url(
            "UAGENT_VERCEL_BASE_URL",
            "https://gateway.vercel.ai/v1",
        )

        http_client = make_httpx_client()

        try:
            client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)
        except TypeError:
            client = OpenAI(api_key=api_key, base_url=base_url)

        return provider, client, model_name

    if provider == "gemini":
        http_backend = _google_genai_http_backend()
        from google import genai  # lazy

        api_key = _provider_api_key(core, "GEMINI")
        if genai is None:
            raise RuntimeError("[FATAL] " + _("google-genai package is not installed."))

        # SDK v3 defaults to API v1; Tool Retrieval is preview-only on v1beta.
        http_options: dict[str, Any] = {}
        if _gemini_tool_retrieval_supported(model_name, "gemini"):
            http_options["api_version"] = "v1beta"

        if http_backend == "httpx":
            try:
                httpx_client = make_httpx_client()
                if httpx_client is not None:
                    http_options["httpx_client"] = httpx_client
            except Exception:
                pass

        try:
            client = genai.Client(api_key=api_key, http_options=http_options)
        except TypeError:
            if http_options.get("api_version") == "v1beta":
                raise RuntimeError(
                    "Gemini Tool Retrieval requires google-genai 3.6.1 or newer "
                    "with per-client v1beta support."
                )
            client = genai.Client(api_key=api_key)

        try:
            from google.genai import models as gm

            gm.Models._logged_afc_warning = True
            if hasattr(gm, "AsyncModels"):
                gm.AsyncModels._logged_afc_warning = True
        except Exception:
            pass

        return provider, client, model_name

    if provider == "vertexai":
        client = make_vertexai_client(core, model_name)
        return provider, client, model_name

    if provider == "claude":
        from anthropic import Anthropic  # lazy

        api_key = _provider_api_key(core, "CLAUDE")
        if Anthropic is None:
            raise RuntimeError("[FATAL] " + _("anthropic package is not installed."))

        timeout = make_httpx_timeout()
        http_client = make_httpx_client(timeout=timeout)

        try:
            client = Anthropic(
                api_key=api_key, timeout=timeout, http_client=http_client
            )
        except TypeError:
            try:
                # Fallback for older SDKs that don't accept http_client/timeout
                if timeout is not None:
                    client = Anthropic(api_key=api_key, timeout=timeout)
                else:
                    client = Anthropic(api_key=api_key)
            except TypeError:
                client = Anthropic(api_key=api_key)

        return provider, client, model_name

    return provider, None, model_name
