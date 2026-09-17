from types import SimpleNamespace

from uagent.runtime.provider_round_dispatcher import (
    RegistryRoundRoute,
    dispatch_provider_round,
    registry_result_to_legacy_tuple,
    registry_round_allowed,
    resolve_registry_round_route,
)


def test_dispatcher_prefers_registry_result() -> None:
    calls: list[str] = []

    def registry(**kwargs):
        calls.append("registry")
        assert kwargs == {"value": 1}
        return (True, "registry")

    def legacy(**kwargs):
        calls.append("legacy")
        return (True, "legacy")

    def openai(**kwargs):
        calls.append("openai")
        return (True, "openai")

    result = dispatch_provider_round(
        registry_runner=registry,
        legacy_runner=legacy,
        openai_runner=openai,
        registry_kwargs={"value": 1},
        legacy_kwargs={},
        openai_kwargs={},
    )

    assert result.source == "registry"
    assert result.result == (True, "registry")
    assert calls == ["registry"]


def test_dispatcher_skips_registry_when_route_is_not_allowed() -> None:
    calls: list[str] = []

    def registry(**kwargs):
        calls.append("registry")
        return "registry-result"

    def legacy(**kwargs):
        calls.append("legacy")
        return "legacy-result"

    def openai(**kwargs):
        calls.append("openai")
        return "openai-result"

    result = dispatch_provider_round(
        registry_runner=registry,
        registry_allowed=False,
        legacy_runner=legacy,
        openai_runner=openai,
        registry_kwargs={},
        legacy_kwargs={},
        openai_kwargs={},
    )

    assert result.source == "legacy"
    assert result.result == "legacy-result"
    assert calls == ["legacy"]


def test_dispatcher_falls_back_in_order_and_preserves_falsy_results() -> None:
    calls: list[str] = []

    def registry(**kwargs):
        calls.append("registry")
        return None

    def legacy(**kwargs):
        calls.append("legacy")
        return None

    def openai(**kwargs):
        calls.append("openai")
        return ()

    result = dispatch_provider_round(
        registry_runner=registry,
        legacy_runner=legacy,
        openai_runner=openai,
        registry_kwargs={},
        legacy_kwargs={},
        openai_kwargs={},
    )

    assert result.source == "openai_compatible"
    assert result.result == ()
    assert calls == ["registry", "legacy", "openai"]


def test_dispatcher_can_disable_registry_for_judgment_mode() -> None:
    calls: list[str] = []

    def legacy(**kwargs):
        calls.append("legacy")
        return "legacy-result"

    def openai(**kwargs):
        calls.append("openai")
        return "openai-result"

    result = dispatch_provider_round(
        registry_runner=None,
        legacy_runner=legacy,
        openai_runner=openai,
        registry_kwargs={},
        legacy_kwargs={},
        openai_kwargs={},
    )

    assert result.source == "legacy"
    assert result.result == "legacy-result"
    assert calls == ["legacy"]


def test_dispatcher_treats_any_non_none_registry_result_as_owned() -> None:
    """A falsy provider result must not accidentally trigger a fallback."""

    for registry_result in (False, "", ()):
        calls: list[str] = []

        def registry(**kwargs):
            calls.append("registry")
            return registry_result

        def legacy(**kwargs):
            calls.append("legacy")
            return "legacy-result"

        def openai(**kwargs):
            calls.append("openai")
            return "openai-result"

        result = dispatch_provider_round(
            registry_runner=registry,
            legacy_runner=legacy,
            openai_runner=openai,
            registry_kwargs={},
            legacy_kwargs={},
            openai_kwargs={},
        )

        assert result.source == "registry"
        assert result.result == registry_result
        assert calls == ["registry"]


def _registry_gate_defaults() -> dict[str, object]:
    return {
        "provider": "openai",
        "use_responses_api": False,
        "responses_enabled": False,
        "send_tools": False,
        "tools_enabled": False,
        "has_context_tools": False,
        "uses_legacy_catalog": False,
    }


def test_registry_round_gate_centralizes_route_policy() -> None:
    assert registry_round_allowed(**_registry_gate_defaults()) is True

    disabled = _registry_gate_defaults()
    disabled["configured_providers"] = "off"
    assert registry_round_allowed(**disabled) is False

    wrong_provider = _registry_gate_defaults()
    wrong_provider["configured_providers"] = "azure"
    assert registry_round_allowed(**wrong_provider) is False

    responses_without_flag = _registry_gate_defaults()
    responses_without_flag["use_responses_api"] = True
    assert registry_round_allowed(**responses_without_flag) is False

    legacy_catalog = _registry_gate_defaults()
    legacy_catalog["uses_legacy_catalog"] = True
    assert registry_round_allowed(**legacy_catalog) is False


def test_registry_route_contract_exposes_a_stable_reason() -> None:
    route = resolve_registry_round_route(**_registry_gate_defaults())
    assert route == RegistryRoundRoute(True, "eligible")

    disabled = _registry_gate_defaults()
    disabled["configured_providers"] = "off"
    route = resolve_registry_round_route(**disabled)
    assert route == RegistryRoundRoute(False, "disabled_by_configuration")
    assert registry_round_allowed(**disabled) is False


def test_dispatcher_prefers_explicit_registry_route_contract() -> None:
    calls: list[str] = []

    def registry(**kwargs):
        calls.append("registry")
        return "registry-result"

    def legacy(**kwargs):
        calls.append("legacy")
        return "legacy-result"

    result = dispatch_provider_round(
        registry_runner=registry,
        registry_allowed=True,
        registry_route=RegistryRoundRoute(False, "legacy_catalog_conflict"),
        legacy_runner=legacy,
        openai_runner=lambda **kwargs: "openai-result",
        registry_kwargs={},
        legacy_kwargs={},
        openai_kwargs={},
    )

    assert result.source == "legacy"
    assert calls == ["legacy"]


def test_registry_round_gate_requires_context_tools_when_tools_are_sent() -> None:
    gate = _registry_gate_defaults()
    gate.update(send_tools=True, tools_enabled=True)
    assert registry_round_allowed(**gate) is False

    gate["has_context_tools"] = True
    assert registry_round_allowed(**gate) is True


def test_registry_result_adapter_preserves_legacy_tool_call_shape() -> None:
    result = SimpleNamespace(
        status="completed",
        assistant_text="tool answer",
        reasoning_text="thinking",
        continuation_update={},
        tool_calls=(
            {
                "tool_call_id": "call-1",
                "name": "read_file",
                "arguments": '{"path":"a.txt"}',
            },
        ),
    )

    assert registry_result_to_legacy_tuple(result) == (
        True,
        "tool answer",
        "thinking",
        [
            {
                "tool_call_id": "call-1",
                "name": "read_file",
                "arguments": '{"path":"a.txt"}',
                "function": {
                    "name": "read_file",
                    "arguments": '{"path":"a.txt"}',
                },
                "id": "call-1",
                "type": "function",
            }
        ],
    )


def test_registry_result_adapter_rejects_non_terminal_or_empty_results() -> None:
    assert registry_result_to_legacy_tuple(
        SimpleNamespace(status="failed", assistant_text="error")
    ) is None
    assert registry_result_to_legacy_tuple(
        SimpleNamespace(
            status="completed",
            assistant_text="",
            reasoning_text="",
            tool_calls=(),
            continuation_update={},
        )
    ) is None
