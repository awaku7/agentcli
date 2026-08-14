from __future__ import annotations

import os
from collections.abc import Callable, Mapping

from .credential_store import Credential, CredentialKind, CredentialStore

_PROVIDER_ENV_NAMES: dict[str, tuple[str, ...]] = {
    "openai": ("UAGENT_OPENAI_API_KEY", "OPENAI_API_KEY"),
    "azure": ("UAGENT_AZURE_API_KEY", "AZURE_OPENAI_API_KEY"),
    "grok": ("UAGENT_GROK_API_KEY", "UAGENT_XAI_API_KEY", "XAI_API_KEY"),
    "xai": ("UAGENT_XAI_API_KEY", "UAGENT_GROK_API_KEY", "XAI_API_KEY"),
    "gemini": ("UAGENT_GEMINI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "vertexai": ("UAGENT_VERTEXAI_API_KEY", "VERTEXAI_API_KEY"),
    "vertex": ("UAGENT_VERTEXAI_API_KEY", "VERTEXAI_API_KEY"),
    "google": (
        "UAGENT_GEMINI_API_KEY",
        "UAGENT_GOOGLE_API_KEY",
        "UAGENT_VERTEXAI_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "VERTEXAI_API_KEY",
    ),
    "deepseek": ("UAGENT_DEEPSEEK_API_KEY",),
    "zai": ("UAGENT_ZAI_API_KEY",),
    "nvidia": ("UAGENT_NVIDIA_API_KEY",),
    "openrouter": ("UAGENT_OPENROUTER_API_KEY", "OPENROUTER_API_KEY"),
    "anthropic": ("UAGENT_CLAUDE_API_KEY", "ANTHROPIC_API_KEY"),
    "claude": ("UAGENT_CLAUDE_API_KEY", "ANTHROPIC_API_KEY"),
}


def get_provider_credential(
    provider: str,
    *,
    store: CredentialStore | None = None,
    environ: Mapping[str, str] | None = None,
    env_getter: Callable[[str], str | None] | None = None,
) -> Credential | None:
    """Resolve a provider API key from CredentialStore, then environment."""
    normalized = str(provider or "").strip().lower()
    if not normalized:
        return None

    name = f"provider/{normalized}"
    if store is not None:
        try:
            credential = store.get(name)
        except Exception:
            credential = None
        if (
            credential is not None
            and credential.kind is CredentialKind.API_KEY
            and credential.secret
        ):
            return credential

    env = environ if environ is not None else os.environ
    names = _PROVIDER_ENV_NAMES.get(
        normalized,
        (f"UAGENT_{normalized.upper()}_API_KEY",),
    )
    for env_name in names:
        if env_getter is not None:
            value = str(env_getter(env_name) or "").strip()
        else:
            value = str(env.get(env_name, "") or "").strip()
        if value:
            return Credential(
                name=name,
                kind=CredentialKind.API_KEY,
                secret=value,
                metadata={"source": "environment", "environment": env_name},
            )
    return None


def get_provider_api_key(
    provider: str,
    *,
    store: CredentialStore | None = None,
    environ: Mapping[str, str] | None = None,
    env_getter: Callable[[str], str | None] | None = None,
) -> str | None:
    credential = get_provider_credential(
        provider,
        store=store,
        environ=environ,
        env_getter=env_getter,
    )
    return credential.secret if credential is not None else None
