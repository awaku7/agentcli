import sys
import time
from typing import Any, Tuple

try:
    import httpx
except Exception:
    httpx = None


from .i18n import _
from .env_utils import env_get

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


def detect_provider() -> str:
    """UAGENT_PROVIDER から利用プロバイダを判定する。設定されていない場合は終了する。"""
    p = env_get("UAGENT_PROVIDER")
    if not p:
        print(_("Environment variable UAGENT_PROVIDER is not set."), file=sys.stderr)
        sys.exit(1)

    p = p.lower()
    if p not in ("azure", "openai", "openrouter", "gemini", "grok", "claude", "nvidia"):
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
    if provider == "claude":
        return (
            env_get("UAGENT_CLAUDE_DEPNAME", "claude-sonnet-4.5") or "claude-sonnet-4.5"
        )
    if provider == "nvidia":
        return (
            env_get("UAGENT_NVIDIA_DEPNAME", "nvidia/nemotron-3-nano-30b-a3b")
            or "nvidia/nemotron-3-nano-30b-a3b"
        )
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


def make_client(core: Any) -> Tuple[str, Any, str]:
    """利用する LLM プロバイダに応じてクライアントを生成する。"""

    provider = detect_provider()
    model_name = get_model_name()

    # Debug: print the effective provider/base_url/model at client creation time.
    # Enabled when UAGENT_DEBUG_ENDPOINT=1.
    _dbg = (env_get("UAGENT_DEBUG_ENDPOINT", "") or "").strip().lower()
    if _dbg in ("1", "true", "yes", "on"):
        _base = "(not set)"
        try:
            if provider == "azure":
                _base = core.get_env_url("UAGENT_AZURE_BASE_URL")
            elif provider == "openai":
                _base = core.get_env_url(
                    "UAGENT_OPENAI_BASE_URL", "https://api.openai.com/v1"
                )
            elif provider == "openrouter":
                _base = core.get_env_url(
                    "UAGENT_OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
                )
            elif provider == "nvidia":
                _base = core.get_env_url(
                    "UAGENT_NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"
                )
            elif provider == "grok":
                _base = core.get_env_url("UAGENT_GROK_BASE_URL", "https://api.x.ai/v1")
        except Exception:
            pass
        try:
            print(
                f"[INFO] make_client: provider={provider} base_url={_base} model={model_name}",
                file=sys.stderr,
            )
        except Exception:
            pass

    if provider == "azure":
        base_url = core.get_env_url("UAGENT_AZURE_BASE_URL")
        api_key = core.get_env("UAGENT_AZURE_API_KEY")
        api_version = core.get_env("UAGENT_AZURE_API_VERSION")

        http_client = None

        client = AzureOpenAI(
            azure_endpoint=base_url,
            api_key=api_key,
            api_version=api_version,
            http_client=http_client,
        )
        return provider, client, model_name

    if provider == "openai":
        api_key = core.get_env("UAGENT_OPENAI_API_KEY")
        base_url = core.get_env_url(
            "UAGENT_OPENAI_BASE_URL", "https://api.openai.com/v1"
        )

        http_client = None
        if httpx is not None:

            def _hook(resp: Any) -> None:
                try:
                    status = getattr(resp, "status_code", None)
                    if status not in (429, 503):
                        return
                except Exception:
                    pass

            try:
                http_client = httpx.Client(event_hooks={"response": [_hook]})
            except Exception:
                http_client = None

        client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)

        return provider, client, model_name

    if provider == "nvidia":
        api_key = core.get_env("UAGENT_NVIDIA_API_KEY")
        base_url = core.get_env_url(
            "UAGENT_NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"
        )
        client = OpenAI(api_key=api_key, base_url=base_url)

        return provider, client, model_name

    if provider == "openrouter":
        api_key = core.get_env("UAGENT_OPENROUTER_API_KEY")
        base_url = core.get_env_url(
            "UAGENT_OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        )
        # OpenRouter (OpenAI compatible)
        # Recommended headers (fixed values by project policy)
        default_headers = {
            "HTTP-Referer": "https://localhost/agent",
            "X-Title": "scheck-openrouter",
        }
        try:
            client = OpenAI(
                api_key=api_key, base_url=base_url, default_headers=default_headers
            )
        except TypeError:
            # Fallback for older OpenAI SDKs that don't accept default_headers
            client = OpenAI(api_key=api_key, base_url=base_url)
        return provider, client, model_name

    if provider == "grok":
        api_key = core.get_env("UAGENT_GROK_API_KEY")
        base_url = core.get_env_url("UAGENT_GROK_BASE_URL", "https://api.x.ai/v1")
        client = OpenAI(api_key=api_key, base_url=base_url)

        return provider, client, model_name

    if provider == "gemini":
        api_key = core.get_env("UAGENT_GEMINI_API_KEY")
        if genai is None:
            print(
                "[FATAL] " + _("google-genai package is not installed."),
                file=sys.stderr,
            )
            sys.exit(1)
        client = genai.Client(api_key=api_key)
        return provider, client, model_name

    if provider == "claude":
        api_key = core.get_env("UAGENT_CLAUDE_API_KEY")
        if Anthropic is None:
            print(
                "[FATAL] " + _("anthropic package is not installed."),
                file=sys.stderr,
            )
            sys.exit(1)
        client = Anthropic(api_key=api_key)
        return provider, client, model_name

    return provider, None, model_name
