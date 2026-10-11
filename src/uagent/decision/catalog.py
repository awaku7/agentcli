"""Capability-driven routing for catalogued typed Decision models."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import replace
from typing import Any
from urllib.parse import urlsplit

from ..auth.credential_store import get_default_credential_store
from ..auth.provider_credentials import get_provider_api_key
from ..llmcapa_util import get_capability
from .base import DecisionProvider
from .capabilities import validate_model_decision_request
from .models import DecisionRequest, DecisionResult
from .settings import DecisionSettings


class CatalogDecisionError(RuntimeError):
    """Base error raised when llmcapa-based routing cannot be completed."""


class CatalogDecisionConfigurationError(CatalogDecisionError):
    """Raised when automatic model or endpoint configuration is incomplete."""


def _decision_extra(decision: Any) -> Mapping[str, Any]:
    value = getattr(decision, "extra", None)
    return value if isinstance(value, Mapping) else {}


def _decision_endpoints(decision: Any) -> tuple[str, ...]:
    raw = getattr(decision, "endpoints", ()) or ()
    if isinstance(raw, str):
        raw = (raw,)
    return tuple(str(item).strip() for item in raw if str(item).strip())


def _select_adapter(
    *, provider: str, protocol: str, endpoint: str, extra: Mapping[str, Any]
) -> str:
    """Map documented llmcapa protocol metadata to an implemented wire adapter."""
    normalized_protocol = protocol.strip().lower()
    path = urlsplit(endpoint).path.rstrip("/").lower()

    if normalized_protocol == "openai-decisions-v1":
        return "openai"
    if normalized_protocol == "openrouter-alpha-decisions":
        return "openrouter"
    if normalized_protocol == "openai-compatible-chat-completions":
        raise CatalogDecisionConfigurationError(
            "This model is catalogued as an OpenAI-compatible Chat Completions "
            "decision model, but UAG does not yet implement that model's typed "
            "decision response protocol. Select a supported Decisions/System One "
            "endpoint or provide the protocol details."
        )

    systemone_compatible = extra.get("systemone_schema_compatible") is True
    if (
        systemone_compatible
        or provider == "typesafe"
        or (provider == "microsoft" and path.endswith("/systemone"))
    ):
        return "systemone"

    if provider == "openai" and path.endswith("/v1/decisions"):
        return "openai"
    if provider == "openrouter" and "/alpha/decisions" in path:
        return "openrouter"

    label = normalized_protocol or "unspecified protocol"
    raise CatalogDecisionConfigurationError(
        f"llmcapa identifies '{provider}' as using '{label}', which UAG does not "
        "yet have a typed Decision adapter for."
    )


def _resolve_endpoint(
    *, endpoint: str, environ: Mapping[str, str], provider: str
) -> str:
    resolved = str(environ.get("UAGENT_DECISION_ENDPOINT") or endpoint).strip()
    if not resolved:
        raise CatalogDecisionConfigurationError(
            "The selected llmcapa model has no Decision API endpoint; set "
            "UAGENT_DECISION_ENDPOINT to the full endpoint URL."
        )

    if "{azure_endpoint}" in resolved:
        azure_endpoint = (
            str(
                environ.get("UAGENT_AZURE_BASE_URL")
                or environ.get("AZURE_ENDPOINT")
                or ""
            )
            .strip()
            .rstrip("/")
        )
        if not azure_endpoint:
            raise CatalogDecisionConfigurationError(
                "Microsoft Decision models require UAGENT_AZURE_BASE_URL or "
                "AZURE_ENDPOINT, unless UAGENT_DECISION_ENDPOINT supplies the "
                "full /providers/microsoft/v1/systemone URL."
            )
        azure_host = azure_endpoint.removeprefix("https://").removeprefix("http://")
        resolved = resolved.replace("{azure_endpoint}", azure_host)

    parsed = urlsplit(resolved)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise CatalogDecisionConfigurationError(
            f"Invalid Decision endpoint for llmcapa provider '{provider}'."
        )
    if parsed.username or parsed.password:
        raise CatalogDecisionConfigurationError(
            "Decision endpoint URLs must not contain embedded credentials."
        )
    if "{" in resolved or "}" in resolved:
        raise CatalogDecisionConfigurationError(
            f"Decision endpoint for provider '{provider}' contains an unresolved "
            "template value. Set UAGENT_DECISION_ENDPOINT explicitly."
        )
    return resolved.rstrip("/")


def _resolve_api_key(
    *,
    provider: str,
    adapter: str,
    environ: Mapping[str, str],
    use_credential_store: bool,
) -> str:
    names = [
        "UAGENT_DECISION_API_KEY",
        f"UAGENT_DECISION_{provider.upper().replace('-', '_')}_API_KEY",
        f"UAGENT_DECISION_{adapter.upper()}_API_KEY",
    ]
    if provider == "microsoft":
        names.extend(("AZURE_API_KEY", "UAGENT_AZURE_API_KEY"))
    for name in names:
        value = str(environ.get(name) or "").strip()
        if value:
            return value

    store = None
    if use_credential_store:
        try:
            store = get_default_credential_store()
        except Exception:
            store = None
    key = get_provider_api_key(provider, store=store, environ=environ)
    if key:
        return key
    if provider == "microsoft":
        key = get_provider_api_key("azure", store=store, environ=environ)
        if key:
            return key

    env_hint = (
        "UAGENT_AZURE_API_KEY or AZURE_API_KEY"
        if provider == "microsoft"
        else f"the stored '{provider}' credential or its provider API-key environment variable"
    )
    raise CatalogDecisionConfigurationError(
        f"No API key is available for llmcapa provider '{provider}'. Configure "
        f"{env_hint}, or set UAGENT_DECISION_API_KEY."
    )


class CatalogDecisionProvider:
    """Route to a supported API adapter using a model's llmcapa metadata.

    Configure ``UAGENT_DECISION_MODEL`` with the llmcapa model ID. For hosted
    deployments whose request model name differs from that catalog ID, set
    ``UAGENT_DECISION_DEPLOYMENT``. The model's catalog record selects a
    supported Decisions API/System One wire protocol; unknown protocols fail
    closed rather than being guessed.
    """

    def __init__(
        self,
        *,
        settings: DecisionSettings,
        environ: Mapping[str, str] | None = None,
        client: Any = None,
    ) -> None:
        if settings.provider != "auto":
            raise CatalogDecisionConfigurationError(
                "CatalogDecisionProvider requires provider='auto'."
            )
        env = os.environ if environ is None else environ
        self._environ = env
        self._owns_environment = environ is None
        self._catalog_model = str(env.get("UAGENT_DECISION_MODEL") or "").strip()
        if not self._catalog_model:
            raise CatalogDecisionConfigurationError(
                "UAGENT_DECISION_MODEL is required when "
                "UAGENT_DECISION_PROVIDER=auto."
            )

        provider_hint = str(env.get("UAGENT_DECISION_MODEL_PROVIDER") or "").strip()
        capability = get_capability(
            self._catalog_model,
            provider_hint or None,
            scoped_only=bool(provider_hint),
        )
        if capability is None:
            raise CatalogDecisionConfigurationError(
                f"llmcapa has no catalog entry for Decision model "
                f"'{self._catalog_model}'. Check UAGENT_DECISION_MODEL_PROVIDER "
                "or use one of the explicit Decision providers for custom models."
            )
        decision = getattr(capability, "decision", None)
        if decision is None or getattr(decision, "decision", None) is False:
            raise CatalogDecisionConfigurationError(
                f"llmcapa does not document Decision API support for model "
                f"'{self._catalog_model}'."
            )

        self._catalog_provider = (
            str(getattr(capability, "provider", "") or provider_hint).strip().lower()
        )
        if not self._catalog_provider:
            raise CatalogDecisionConfigurationError(
                f"llmcapa did not identify a provider for model "
                f"'{self._catalog_model}'. Set UAGENT_DECISION_MODEL_PROVIDER."
            )
        extra = _decision_extra(decision)
        protocol = str(extra.get("endpoint_protocol") or "").strip()
        endpoints = _decision_endpoints(decision)
        endpoint = _resolve_endpoint(
            endpoint=endpoints[0] if endpoints else "",
            environ=env,
            provider=self._catalog_provider,
        )
        adapter = _select_adapter(
            provider=self._catalog_provider,
            protocol=protocol,
            endpoint=endpoint,
            extra=extra,
        )
        self._decision = decision
        self._protocol = protocol
        self._adapter = adapter
        self._model = (
            str(env.get("UAGENT_DECISION_DEPLOYMENT") or "").strip()
            or self._catalog_model
        )
        api_key = _resolve_api_key(
            provider=self._catalog_provider,
            adapter=adapter,
            environ=env,
            use_credential_store=self._owns_environment,
        )

        adapter_env = dict(env)
        if adapter == "openai":
            adapter_env.update(
                {
                    "UAGENT_DECISION_OPENAI_DEPNAME": self._model,
                    "UAGENT_DECISION_OPENAI_BASE_URL": endpoint,
                    "UAGENT_DECISION_OPENAI_API_KEY": api_key,
                }
            )
            adapter_provider = "openai"
        elif adapter == "openrouter":
            adapter_env.update(
                {
                    "UAGENT_DECISION_OPENROUTER_DEPNAME": self._model,
                    "UAGENT_DECISION_OPENROUTER_BASE_URL": endpoint,
                    "UAGENT_DECISION_OPENROUTER_API_KEY": api_key,
                }
            )
            adapter_provider = "openrouter"
        else:
            adapter_env.update(
                {
                    "UAGENT_DECISION_TYPESAFE_DEPNAME": self._model,
                    "UAGENT_DECISION_TYPESAFE_API_KEY": api_key,
                    "UAGENT_DECISION_TYPESAFE_ENDPOINT": endpoint,
                    "UAGENT_DECISION_TYPESAFE_AUTH_HEADER": (
                        "api-key" if self._catalog_provider == "microsoft" else "bearer"
                    ),
                }
            )
            adapter_provider = "typesafe"

        from .openai import OpenAIDecisionProvider
        from .openrouter import OpenRouterDecisionProvider
        from .typesafe import TypeSafeDecisionProvider

        adapters = {
            "openai": OpenAIDecisionProvider,
            "openrouter": OpenRouterDecisionProvider,
            "typesafe": TypeSafeDecisionProvider,
        }
        self._delegate: DecisionProvider = adapters[adapter_provider](
            settings=DecisionSettings(provider=adapter_provider, source="auto"),
            environ=adapter_env,
            client=client,
        )
        self._closed = False

    @property
    def name(self) -> str:
        return self._catalog_provider

    @property
    def model(self) -> str:
        return self._model

    @property
    def catalog_model(self) -> str:
        """Return the llmcapa ID used to select and validate this deployment."""
        return self._catalog_model

    @property
    def uses_catalog_metadata(self) -> bool:
        return True

    def decide(self, request: DecisionRequest) -> DecisionResult:
        if self._closed:
            raise CatalogDecisionError("Automatic Decision provider is closed.")

        if self._adapter == "openai":
            question_kinds = {
                "boolean": "predicate",
                "choice": "choice",
                "score": "score",
            }
            required_fields = {
                "boolean": ("probability",),
                "choice": ("choice",),
                "score": ("score",),
            }
        else:
            question_kinds = {
                "boolean": "noul",
                "choice": "choice",
                "score": "score",
            }
            required_fields = {
                "boolean": ("noul",),
                "choice": ("choice", "probabilities", "confidence"),
                "score": ("score", "probabilities", "confidence"),
            }
        validate_model_decision_request(
            provider=self._catalog_provider,
            model=self._catalog_model,
            request=request,
            question_kinds=question_kinds,
            required_answer_fields=required_fields,
            error_type=CatalogDecisionError,
        )

        result = self._delegate.decide(request)
        return replace(
            result,
            provider=self._catalog_provider,
            model=result.model or self._model,
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._delegate.close()
