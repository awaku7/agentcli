from __future__ import annotations

import os
import sys
from types import ModuleType, SimpleNamespace

from uagent.auth.provider_credentials import get_provider_credential
from uagent.env_validate import validate_startup_env
from uagent.providers.provider_caps import (
    ALL_PROVIDERS,
    DEFAULT_PROVIDER_REGISTRY,
    RESPONSES_PROVIDERS,
    temperature_env_name,
)
from uagent.providers.openai_projection_policy import build_openai_projection
from uagent.providers.runtime_registry import (
    build_provider_runtime_registry,
    supports_provider_runtime,
)
from uagent.runtime.round_contracts import RoundIdentifiers


def test_vllm_is_local_chat_only_openai_compatible_provider() -> None:
    assert "vllm" in ALL_PROVIDERS
    assert "vllm" not in RESPONSES_PROVIDERS
    spec = DEFAULT_PROVIDER_REGISTRY.resolve("vllm")
    assert spec.name == "vllm"
    assert spec.auth_requirement == "local_endpoint"
    assert spec.supports_streaming
    assert spec.supports_tools
    assert not spec.supports_vision
    assert "chat" in spec.capabilities
    assert "responses" not in spec.capabilities
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


def test_vllm_tool_projection_preserves_configured_reasoning_effort(monkeypatch):
    monkeypatch.setenv("UAGENT_REASONING", "high")
    projection = build_openai_projection(
        provider="vllm",
        model="served-model",
        transport="chat_completions",
        messages=[{"role": "user", "content": "solve this"}],
        send_tools=True,
        compaction_threshold=1000,
    )
    assert projection.options["reasoning_effort"] == "high"
    assert projection.options["tool_choice"] == "auto"

    monkeypatch.delenv("UAGENT_REASONING")
    projection = build_openai_projection(
        provider="vllm",
        model="served-model",
        transport="chat_completions",
        messages=[{"role": "user", "content": "solve this"}],
        send_tools=True,
        compaction_threshold=1000,
    )
    assert "reasoning_effort" not in projection.options


def test_vllm_forces_chat_completions_even_when_responses_are_requested(monkeypatch):
    from uagent.llm_round_helpers import _resolve_round_runtime_flags

    monkeypatch.setenv("UAGENT_RESPONSES", "1")

    use_responses, _streaming = _resolve_round_runtime_flags(
        tr_cfg=None,
        core=SimpleNamespace(),
        provider="vllm",
        depname="served-model",
    )

    assert not use_responses


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
