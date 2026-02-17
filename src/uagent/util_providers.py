import os
import sys
from typing import Any, Tuple

from .i18n import _

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
    p = os.environ.get("UAGENT_PROVIDER")
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
        return os.environ.get("UAGENT_AZURE_DEPNAME", "gpt-5.2")
    if provider == "openai":
        return os.environ.get("UAGENT_OPENAI_DEPNAME", "gpt-5.2")
    if provider == "openrouter":
        return os.environ.get("UAGENT_OPENROUTER_DEPNAME", "gpt-5.2")
    if provider == "grok":
        return os.environ.get("UAGENT_GROK_DEPNAME", "grok-4-1-fast-reasoning")
    if provider == "gemini":
        return os.environ.get("UAGENT_GEMINI_DEPNAME", "gemini-1.5-flash")
    if provider == "claude":
        return os.environ.get("UAGENT_CLAUDE_DEPNAME", "claude-sonnet-4.5")
    if provider == "nvidia":
        return os.environ.get("UAGENT_NVIDIA_DEPNAME", "nvidia/nemotron-3-nano-30b-a3b")
    return os.environ.get("UAGENT_OPENAI_DEPNAME", "gpt-5.2")


def make_client(core: Any) -> Tuple[str, Any, str]:
    """利用する LLM プロバイダに応じてクライアントを生成する。"""

    provider = detect_provider()
    model_name = get_model_name()

    if provider == "azure":
        base_url = core.get_env_url("UAGENT_AZURE_BASE_URL")
        api_key = core.get_env("UAGENT_AZURE_API_KEY")
        api_version = core.get_env("UAGENT_AZURE_API_VERSION")
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
        client = OpenAI(api_key=api_key, base_url=base_url)

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
                "[FATAL] google-genai パッケージがインストールされていません",
                file=sys.stderr,
            )
            sys.exit(1)
        client = genai.Client(api_key=api_key)
        return provider, client, model_name

    if provider == "claude":
        api_key = core.get_env("UAGENT_CLAUDE_API_KEY")
        if Anthropic is None:
            print(
                "[FATAL] anthropic パッケージがインストールされていません",
                file=sys.stderr,
            )
            sys.exit(1)
        client = Anthropic(api_key=api_key)
        return provider, client, model_name

    return provider, None, model_name
