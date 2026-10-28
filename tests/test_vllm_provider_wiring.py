from __future__ import annotations

import os
import sys
import warnings
from types import ModuleType, SimpleNamespace

import pytest

from uagent.auth.provider_credentials import get_provider_credential
from uagent.env_validate import validate_startup_env
from uagent.providers.provider_caps import (
    ALL_PROVIDERS,
    DEFAULT_PROVIDER_REGISTRY,
    RESPONSES_PROVIDERS,
    supports_structured_output_wire,
    temperature_env_name,
)
from uagent.providers.openai_projection_policy import build_openai_projection
from uagent.providers.runtime_registry import (
    build_provider_runtime_registry,
    supports_provider_runtime,
)
from uagent.runtime.round_contracts import RoundIdentifiers


def test_vllm_is_openai_compatible_responses_provider() -> None:
    assert "vllm" in ALL_PROVIDERS
    assert "vllm" in RESPONSES_PROVIDERS
    spec = DEFAULT_PROVIDER_REGISTRY.resolve("vllm")
    assert spec.name == "vllm"
    assert spec.auth_requirement == "local_endpoint"
    assert spec.supports_streaming
    assert spec.supports_tools
    assert not spec.supports_vision
    assert "chat" in spec.capabilities
    assert "responses" in spec.capabilities
    assert supports_structured_output_wire("vllm", "chat_completions")
    assert supports_structured_output_wire("vllm", "responses")
    assert temperature_env_name("vllm") == "UAGENT_VLLM_TEMPERATURE"
    assert supports_provider_runtime("vllm")


def test_vllm_registry_projection_honors_provider_and_shared_temperature(monkeypatch):
    monkeypatch.setenv("UAGENT_VLLM_TEMPERATURE", "0.65")
    monkeypatch.setenv("UAGENT_TEMPERATURE", "0.4")

    projection = build_openai_projection(
        provider="vllm",
        model="served-model",
        transport="chat_completions",
        messages=[{"role": "user", "content": "hello"}],
        send_tools=False,
        compaction_threshold=1000,
    )
    assert projection.options["temperature"] == 0.65

    monkeypatch.delenv("UAGENT_VLLM_TEMPERATURE")
    projection = build_openai_projection(
        provider="vllm",
        model="served-model",
        transport="chat_completions",
        messages=[{"role": "user", "content": "hello"}],
        send_tools=False,
        compaction_threshold=1000,
    )
    assert projection.options["temperature"] == 0.4

    monkeypatch.delenv("UAGENT_TEMPERATURE")
    projection = build_openai_projection(
        provider="vllm",
        model="served-model",
        transport="chat_completions",
        messages=[{"role": "user", "content": "hello"}],
        send_tools=False,
        compaction_threshold=1000,
    )
    assert projection.options["temperature"] == 0.2


def test_vllm_projection_only_sends_verified_effort(monkeypatch):
    def project(transport="chat_completions", send_tools=True):
        return build_openai_projection(
            provider="vllm",
            model="served-model",
            transport=transport,
            messages=[{"role": "user", "content": "solve this"}],
            send_tools=send_tools,
            compaction_threshold=1000,
        )

    monkeypatch.setenv("UAGENT_REASONING", "high")
    with pytest.warns(RuntimeWarning, match="no verified reasoning_effort"):
        unknown = project()
    assert "reasoning_effort" not in unknown.options
    assert unknown.options["tool_choice"] == "auto"
    assert unknown.effort_used is None

    with pytest.warns(RuntimeWarning, match="no verified reasoning_effort"):
        unknown_responses = project(transport="responses")
    assert "reasoning" not in unknown_responses.options

    seen = []

    def verified_capability(model, provider, *, scoped_only=False):
        seen.append((model, provider, scoped_only))
        return SimpleNamespace(
            supports_reasoning_effort=True,
            reasoning_effort_values=["none", "low", "medium", "high"],
        )

    monkeypatch.setattr(
        "uagent.providers.openai_projection_policy.llmcapa_util.get_capability",
        verified_capability,
    )
    verified = project()
    assert verified.options["reasoning_effort"] == "high"
    assert verified.options["tool_choice"] == "auto"
    assert verified.effort_used == "high"
    assert seen and all(item == ("served-model", "vllm", True) for item in seen)

    verified_responses = project(transport="responses")
    assert verified_responses.options["reasoning"] == {"effort": "high"}

    monkeypatch.delenv("UAGENT_REASONING")
    assert "reasoning_effort" not in project().options

    for disabled in ("off", "false", "none"):
        monkeypatch.setenv("UAGENT_REASONING", disabled)
        for send_tools in (False, True):
            projection = project(send_tools=send_tools)
            assert projection.options["reasoning_effort"] == "none"
            assert ("tool_choice" in projection.options) is send_tools


def test_vllm_unverified_effort_never_uses_provider_defaults(monkeypatch):
    monkeypatch.setenv("UAGENT_REASONING", "off")

    monkeypatch.setattr(
        "uagent.providers.openai_projection_policy.llmcapa_util.get_capability",
        lambda *_args, **_kwargs: SimpleNamespace(
            supports_reasoning_effort=True,
            reasoning_effort_values=None,
        ),
    )
    with pytest.warns(RuntimeWarning, match="no verified reasoning_effort"):
        projection = build_openai_projection(
            provider="vllm",
            model="served-model",
            transport="chat_completions",
            messages=[],
            send_tools=False,
            compaction_threshold=1000,
        )
    assert "reasoning_effort" not in projection.options
    assert projection.effort_used is None


def test_vllm_auto_does_not_warn_for_unverified_effort(monkeypatch):
    monkeypatch.setenv("UAGENT_REASONING", "auto")
    monkeypatch.setattr(
        "uagent.providers.openai_projection_policy._is_thinking_task",
        lambda *_: True,
    )
    monkeypatch.setattr(
        "uagent.providers.openai_projection_policy._choose_auto_effort",
        lambda *_: "high",
    )
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        projection = build_openai_projection(
            provider="vllm",
            model="served-model",
            transport="chat_completions",
            messages=[{"role": "user", "content": "reason about this"}],
            send_tools=False,
            compaction_threshold=1000,
        )
    assert not recorded
    assert "reasoning_effort" not in projection.options


def test_vllm_auto_selects_responses_when_llmcapa_confirms_support(monkeypatch):
    from uagent.llm_round_helpers import _resolve_round_runtime_flags
    from uagent.runtime.capability_resolver import CapabilityResolver

    monkeypatch.setenv("UAGENT_RESPONSES", "auto")
    monkeypatch.setenv("UAGENT_STREAMING", "0")
    resolver = CapabilityResolver(
        feature_lookup=lambda feature, *_: True if feature == "responses_api" else None
    )

    use_responses, streaming = _resolve_round_runtime_flags(
        tr_cfg=None,
        core=SimpleNamespace(),
        provider="vllm",
        depname="Qwen/Qwen3.6-35B-A3B",
        capability_resolver=resolver,
    )

    assert use_responses is True
    assert streaming is False


def test_vllm_auto_keeps_chat_when_llmcapa_capability_is_unknown(monkeypatch):
    from uagent.llm_round_helpers import _resolve_round_runtime_flags
    from uagent.runtime.capability_resolver import CapabilityResolver

    monkeypatch.setenv("UAGENT_RESPONSES", "auto")
    resolver = CapabilityResolver(feature_lookup=lambda *_: None)

    use_responses, _streaming = _resolve_round_runtime_flags(
        tr_cfg=None,
        core=SimpleNamespace(),
        provider="vllm",
        depname="unlisted-model",
        capability_resolver=resolver,
    )

    assert use_responses is False


def test_vllm_explicit_responses_respects_llmcapa_negative(monkeypatch):
    from uagent.llm_round_helpers import _resolve_round_runtime_flags
    from uagent.runtime.capability_resolver import CapabilityResolver

    monkeypatch.setenv("UAGENT_RESPONSES", "1")
    resolver = CapabilityResolver(
        feature_lookup=lambda feature, *_: False if feature == "responses_api" else None
    )

    use_responses, _streaming = _resolve_round_runtime_flags(
        tr_cfg=None,
        core=SimpleNamespace(),
        provider="vllm",
        depname="unsupported-model",
        capability_resolver=resolver,
    )

    assert use_responses is False


def test_vllm_credential_is_optional_and_uses_namespaced_key() -> None:
    credential = get_provider_credential(
        "vllm", environ={"UAGENT_VLLM_API_KEY": "test-key"}
    )
    assert credential is not None
    assert credential.secret == "test-key"
    assert (
        get_provider_credential("vllm", environ={"VLLM_API_KEY": "server-key"}).secret
        == "server-key"
    )
    assert get_provider_credential("vllm", environ={}) is None


def test_vllm_startup_requires_served_model_but_not_api_key(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_PROVIDER", "vllm")
    monkeypatch.setenv("UAGENT_VLLM_DEPNAME", "served-model")
    monkeypatch.delenv("UAGENT_VLLM_API_KEY", raising=False)

    provider, missing, warnings = validate_startup_env()

    assert provider == "vllm"
    assert not missing
    assert not warnings

    monkeypatch.delenv("UAGENT_VLLM_DEPNAME")
    _, missing, _ = validate_startup_env()
    assert [item.name for item in missing] == ["UAGENT_VLLM_DEPNAME"]


def test_vllm_is_available_in_setup_wizard() -> None:
    from uagent.setup_cli import PROVIDERS, PROVIDER_FIELDS

    assert ("vllm", "vLLM (OpenAI-compatible)") in PROVIDERS
    fields = {name: required for name, required, _label in PROVIDER_FIELDS["vllm"]}
    assert fields["UAGENT_VLLM_DEPNAME"]
    assert not fields["UAGENT_VLLM_API_KEY"]


def test_vllm_openai_client_uses_configured_endpoint_and_optional_auth(monkeypatch):
    from uagent.providers import util_providers

    captured: dict[str, object] = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    openai_module = ModuleType("openai")
    openai_module.OpenAI = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", openai_module)
    monkeypatch.setattr(
        util_providers, "_ensure_provider_dependency", lambda _name: None
    )
    monkeypatch.setattr(util_providers, "_provider_api_key", lambda *_args: None)

    def fake_httpx_client(**kwargs):
        captured["httpx_options"] = kwargs
        return "fake-http-client"

    monkeypatch.setattr(util_providers, "make_httpx_client", fake_httpx_client)
    monkeypatch.setenv("UAGENT_PROVIDER", "vllm")
    monkeypatch.setenv("UAGENT_VLLM_DEPNAME", "Qwen/Qwen3.5-8B")
    monkeypatch.setenv("UAGENT_VLLM_BASE_URL", "http://127.0.0.1:8123/v1")
    monkeypatch.setenv("UAGENT_VLLM_TIMEOUT_SEC", "45")

    core = SimpleNamespace(
        get_env_url=lambda name, default="": os.environ.get(name) or default
    )
    provider, client, model = util_providers.make_client(core)

    assert provider == "vllm"
    assert model == "Qwen/Qwen3.5-8B"
    assert client.kwargs["api_key"] == "dummy"
    assert client.kwargs["base_url"] == "http://127.0.0.1:8123/v1"
    assert client.kwargs["http_client"] == "fake-http-client"
    assert captured["httpx_options"] == {"timeout": 45.0}


def test_vllm_runtime_uses_generic_chat_completions_adapter() -> None:
    from uagent.providers.openai_compatible_runtime import OpenAICompatibleRuntime

    registry = build_provider_runtime_registry(
        provider="vllm",
        client=SimpleNamespace(),
        model="served-model",
        identifiers=RoundIdentifiers(
            "turn", "round", "attempt", "request", "stream", 1
        ),
    )

    runtime = registry.resolve("vllm")
    assert isinstance(runtime, OpenAICompatibleRuntime)
    assert runtime.capabilities.transport == "chat_completions"


def test_vllm_runtime_preserves_reasoning_content_in_both_chat_modes() -> None:
    registry = build_provider_runtime_registry(
        provider="vllm",
        client=SimpleNamespace(),
        model="served-model",
        identifiers=RoundIdentifiers(
            "turn", "round", "attempt", "request", "stream", 1
        ),
    )
    runtime = registry.resolve("vllm")
    cancellation = SimpleNamespace(is_cancelled=lambda: False)

    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    reasoning_content="non-streamed reasoning",
                    content="final answer",
                    tool_calls=[],
                )
            )
        ]
    )
    response_events = list(runtime._chat_response_events(response, cancellation))
    assert [event.type for event in response_events] == [
        "ReasoningDelta",
        "TextDelta",
        "ResponseCompleted",
    ]
    assert response_events[0].data["text"] == "non-streamed reasoning"

    chunks = [
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(
                        reasoning_content="streamed reasoning",
                        content=None,
                        tool_calls=[],
                    )
                )
            ]
        ),
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(
                        reasoning_content=None,
                        content="final answer",
                        tool_calls=[],
                    )
                )
            ]
        ),
    ]
    stream_events = list(runtime._chat_events(iter(chunks), cancellation))
    assert [event.type for event in stream_events] == [
        "ReasoningDelta",
        "TextDelta",
        "ResponseCompleted",
    ]
    assert stream_events[0].data["text"] == "streamed reasoning"


def test_vllm_startup_banner_displays_default_base_url(monkeypatch) -> None:
    from uagent.runtime import runtime_banner

    monkeypatch.setenv("UAGENT_PROVIDER", "vllm")
    monkeypatch.delenv("UAGENT_VLLM_BASE_URL", raising=False)
    monkeypatch.setenv("UAGENT_VLLM_DEPNAME", "served-model")
    monkeypatch.setattr(runtime_banner, "_startup_optional_model_infos", lambda: [])
    monkeypatch.setattr(runtime_banner, "_", lambda text: text)

    banner = runtime_banner.build_startup_banner(
        core=SimpleNamespace(), workdir="workspace", workdir_source="test"
    )

    assert "[INFO] base_url = http://localhost:8000/v1" in banner
