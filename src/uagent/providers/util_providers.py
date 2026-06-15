from __future__ import annotations

import sys
import time
import atexit
from typing import Any

try:
    import httpx
except Exception:
    httpx = None


from ..i18n import _
from ..env_utils import env_get

# OpenAI / Azure OpenAI
try:
    from openai import AzureOpenAI, OpenAI
except ImportError:
    AzureOpenAI = None
    OpenAI = None

# Google Gemini (google-genai)
try:
    from google import genai
except Exception:
    genai = None

# Anthropic
try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None

# OpenRouter (official SDK)
try:
    from openrouter import OpenRouter as _OpenRouterSDK
except Exception:
    _OpenRouterSDK = None


_HTTPX_CLIENTS: list[Any] = []
_HTTPX_CLIENTS_REGISTERED = False


def _close_httpx_clients() -> None:
    # Best-effort cleanup for custom httpx clients (OpenAI SDK http_client=...)
    for c in list(_HTTPX_CLIENTS):
        try:
            c.close()
        except Exception:
            pass


def _register_httpx_client(c: Any) -> None:
    global _HTTPX_CLIENTS_REGISTERED
    if c is None:
        return
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

    if httpx is None:
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
    """Create an httpx.Client with timeout from env (best-effort)."""

    if httpx is None:
        return None

    if timeout is None:
        timeout = make_httpx_timeout()

    kwargs: dict[str, Any] = {}
    if timeout is not None:
        kwargs["timeout"] = timeout
    if verify is not None:
        kwargs["verify"] = verify
    if event_hooks is not None:
        kwargs["event_hooks"] = event_hooks

    try:
        c = httpx.Client(**kwargs)
    except Exception:
        # Fallback: drop event_hooks if that caused trouble
        try:
            kwargs.pop("event_hooks", None)
            c = httpx.Client(**kwargs)
        except Exception:
            return None

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
    """UAGENT_PROVIDER から利用プロバイダを判定する。設定されていない場合は終了する。"""
    p = env_get("UAGENT_PROVIDER")
    if not p:
        print(_("Environment variable UAGENT_PROVIDER is not set."), file=sys.stderr)
        sys.exit(1)

    p = p.lower()
    if p not in (
        "azure",
        "openai",
        "bedrock",
        "openrouter",
        "ollama",
        "gemini",
        "vertexai",
        "grok",
        "claude",
        "nvidia",
        "deepseek",
        "alibaba",
        "moonshot",
    ):
        print(_("Unknown provider: %(provider)s") % {"provider": p}, file=sys.stderr)
        sys.exit(1)
    return p


def get_model_name() -> str:
    """利用プロバイダに応じてモデル名を取得する（scheck.py の main ロジックに準拠）"""
    provider = detect_provider()
    if provider == "azure":
        return env_get("UAGENT_AZURE_DEPNAME", "gpt-5.2") or "gpt-5.2"
    if provider == "openai":
        return env_get("UAGENT_OPENAI_DEPNAME", "gpt-5.2") or "gpt-5.2"
    if provider == "bedrock":
        return env_get("UAGENT_BEDROCK_DEPNAME", "gpt-5.2") or "gpt-5.2"
    if provider == "openrouter":
        return env_get("UAGENT_OPENROUTER_DEPNAME", "gpt-5.2") or "gpt-5.2"
    if provider == "grok":
        return (
            env_get("UAGENT_GROK_DEPNAME", "grok-4-1-fast-reasoning")
            or "grok-4-1-fast-reasoning"
        )
    if provider == "gemini":
        return (
            env_get("UAGENT_GEMINI_DEPNAME", "gemini-1.5-flash") or "gemini-1.5-flash"
        )
    if provider == "vertexai":
        return (
            env_get("UAGENT_VERTEXAI_DEPNAME", "gemini-2.5-flash") or "gemini-2.5-flash"
        )
    if provider == "claude":
        return (
            env_get("UAGENT_CLAUDE_DEPNAME", "claude-sonnet-4.5") or "claude-sonnet-4.5"
        )
    if provider == "ollama":
        return env_get("UAGENT_OLLAMA_DEPNAME", "llama3.1") or "llama3.1"
    if provider == "nvidia":
        return (
            env_get("UAGENT_NVIDIA_DEPNAME", "nvidia/nemotron-3-nano-30b-a3b")
            or "nvidia/nemotron-3-nano-30b-a3b"
        )
    if provider == "deepseek":
        return (
            env_get("UAGENT_DEEPSEEK_DEPNAME", "deepseek-v4-flash")
            or "deepseek-v4-flash"
        )
    if provider == "alibaba":
        return env_get("UAGENT_ALIBABA_DEPNAME", "qwen3.5-plus") or "qwen3.5-plus"
    if provider == "moonshot":
        return env_get("UAGENT_MOONSHOT_DEPNAME", "kimi-k2") or "kimi-k2"
    return env_get("UAGENT_OPENAI_DEPNAME", "gpt-5.2") or "gpt-5.2"


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


def make_client(core: Any) -> tuple[str, Any, str]:
    """利用する LLM プロバイダに応じてクライアントを生成する。"""

    provider = detect_provider()
    model_name = get_model_name()

    if provider == "azure":
        base_url = core.get_env_url("UAGENT_AZURE_BASE_URL")
        api_key = core.get_env("UAGENT_AZURE_API_KEY")
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

    if provider == "openai":
        api_key = core.get_env("UAGENT_OPENAI_API_KEY")
        base_url = core.get_env_url(
            "UAGENT_OPENAI_BASE_URL", "https://api.openai.com/v1"
        )

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

    if provider == "bedrock":
        api_key = env_get("UAGENT_BEDROCK_API_KEY") or "dummy"
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
        api_key = env_get("UAGENT_NVIDIA_API_KEY") or "dummy"
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
        api_key = env_get("UAGENT_OLLAMA_API_KEY") or "dummy"
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

    if provider == "openrouter":
        api_key = env_get("UAGENT_OPENROUTER_API_KEY") or "dummy"
        base_url = core.get_env_url(
            "UAGENT_OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        )

        http_client = make_httpx_client()

        if _OpenRouterSDK is not None:
            try:
                raw_client = _OpenRouterSDK(
                    api_key=api_key,
                    http_referer="https://localhost/agent",
                    x_open_router_title="scheck-openrouter",
                    server_url=base_url,
                    client=http_client,
                )
            except TypeError:
                try:
                    raw_client = _OpenRouterSDK(
                        api_key=api_key,
                        http_referer="https://localhost/agent",
                        x_open_router_title="scheck-openrouter",
                        server_url=base_url,
                    )
                except TypeError:
                    raw_client = _OpenRouterSDK(api_key=api_key)

            client = _OpenRouterCompatClient(raw_client)
            return provider, client, model_name

        # Fallback for environments without the official OpenRouter SDK.
        default_headers = {
            "HTTP-Referer": "https://localhost/agent",
            "X-Title": "scheck-openrouter",
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

    if provider == "grok":
        api_key = core.get_env("UAGENT_GROK_API_KEY")
        base_url = core.get_env_url("UAGENT_GROK_BASE_URL", "https://api.x.ai/v1")

        http_client = make_httpx_client()

        try:
            client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)
        except TypeError:
            client = OpenAI(api_key=api_key, base_url=base_url)

        return provider, client, model_name

    if provider == "deepseek":
        api_key = core.get_env("UAGENT_DEEPSEEK_API_KEY")
        base_url = core.get_env_url(
            "UAGENT_DEEPSEEK_BASE_URL", "https://api.deepseek.com"
        )

        http_client = make_httpx_client()

        try:
            client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)
        except TypeError:
            client = OpenAI(api_key=api_key, base_url=base_url)

        return provider, client, model_name

    if provider == "alibaba":
        api_key = core.get_env("UAGENT_ALIBABA_API_KEY")
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
        api_key = core.get_env("UAGENT_MOONSHOT_API_KEY")
        base_url = core.get_env_url(
            "UAGENT_MOONSHOT_BASE_URL", "https://api.moonshot.cn/v1"
        )

        http_client = make_httpx_client()

        try:
            client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)
        except TypeError:
            client = OpenAI(api_key=api_key, base_url=base_url)

        return provider, client, model_name

    if provider == "gemini":
        api_key = core.get_env("UAGENT_GEMINI_API_KEY")
        if genai is None:
            print(
                "[FATAL] " + _("google-genai package is not installed."),
                file=sys.__stderr__,
            )
            sys.exit(1)

        # google-genai supports per-client HTTP options (custom httpx client, etc.).
        # Keep timeout handling on the shared httpx client to avoid SDK-side timeout quirks.
        http_options: dict[str, Any] = {}

        try:
            httpx_client = make_httpx_client()
            if httpx_client is not None:
                http_options["httpx_client"] = httpx_client
        except Exception:
            pass

        try:
            client = genai.Client(api_key=api_key, http_options=http_options)
        except TypeError:
            client = genai.Client(api_key=api_key)

        return provider, client, model_name

    if provider == "vertexai":
        if genai is None:
            print(
                "[FATAL] " + _("google-genai package is not installed."),
                file=sys.stderr,
            )
            sys.exit(1)

        api_key = core.get_env("UAGENT_VERTEXAI_API_KEY")
        project = env_get("UAGENT_VERTEXAI_PROJECT")
        location = env_get("UAGENT_VERTEXAI_LOCATION")

        http_options: dict[str, Any] = {}
        try:
            httpx_client = make_httpx_client()
            if httpx_client is not None:
                http_options["httpx_client"] = httpx_client
        except Exception:
            pass

        kwargs: dict[str, Any] = {"vertexai": True, "api_key": api_key}
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
                client = genai.Client(vertexai=True, api_key=api_key)

        return provider, client, model_name

    if provider == "claude":
        api_key = core.get_env("UAGENT_CLAUDE_API_KEY")
        if Anthropic is None:
            print(
                "[FATAL] " + _("anthropic package is not installed."),
                file=sys.stderr,
            )
            sys.exit(1)

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
