from uagent.runtime.tool_discovery import (
    ToolCandidate,
    ToolDeliveryMode,
    ToolDeliveryStrategy,
    ToolSelectionPolicy,
    ToolSource,
)


def test_startup_preload_uses_central_native_search_decision(monkeypatch) -> None:
    from uagent.tools import _should_preload_lazy_specs

    monkeypatch.setenv("UAGENT_PROVIDER", "openai")
    monkeypatch.setenv("UAGENT_OPENAI_DEPNAME", "gpt-5.4")
    monkeypatch.setenv("UAGENT_RESPONSES", "1")
    monkeypatch.setenv("UAGENT_GPT54_TOOL_SEARCH", "native")

    assert _should_preload_lazy_specs()


def test_startup_preload_rejects_nano_and_legacy_modes(monkeypatch) -> None:
    from uagent.tools import _should_preload_lazy_specs

    monkeypatch.setenv("UAGENT_PROVIDER", "openai")
    monkeypatch.setenv("UAGENT_OPENAI_DEPNAME", "gpt-5.4-nano")
    monkeypatch.setenv("UAGENT_RESPONSES", "1")
    monkeypatch.setenv("UAGENT_GPT54_TOOL_SEARCH", "native")
    assert not _should_preload_lazy_specs()

    monkeypatch.setenv("UAGENT_OPENAI_DEPNAME", "gpt-5.4")
    monkeypatch.setenv("UAGENT_GPT54_TOOL_SEARCH", "legacy")
    assert not _should_preload_lazy_specs()


def test_startup_preload_rejects_responses_disabled_and_other_provider(
    monkeypatch,
) -> None:
    from uagent.tools import _should_preload_lazy_specs

    monkeypatch.setenv("UAGENT_PROVIDER", "openai")
    monkeypatch.setenv("UAGENT_OPENAI_DEPNAME", "gpt-5.4")
    monkeypatch.setenv("UAGENT_GPT54_TOOL_SEARCH", "native")
    monkeypatch.setenv("UAGENT_RESPONSES", "0")
    assert not _should_preload_lazy_specs()

    monkeypatch.setenv("UAGENT_RESPONSES", "1")
    monkeypatch.setenv("UAGENT_PROVIDER", "openrouter")
    assert not _should_preload_lazy_specs()


def _tool(name: str, *, source: ToolSource = ToolSource.BUILTIN) -> ToolCandidate:
    return ToolCandidate(name, name, source, {"type": "function", "name": name})


def test_selection_preserves_management_tools_but_not_permissions() -> None:
    disabled = ToolCandidate("remote", "remote", ToolSource.MCP, {}, executable=False)
    selection = ToolSelectionPolicy({"tool_catalog"}).select(
        (_tool("tool_catalog"), _tool("read_file"), disabled), {"read_file"}
    )

    assert [item.name for item in selection.selected] == ["tool_catalog", "read_file"]


def test_zero_hit_selection_fails_open_for_legacy_catalog_path() -> None:
    selection = ToolSelectionPolicy().select(
        (_tool("read_file"), _tool("list_dir")), {"missing"}
    )

    assert selection.used_fallback
    assert [item.name for item in selection.selected] == ["read_file", "list_dir"]


def test_delivery_is_separate_from_selection_and_supports_native_search() -> None:
    selection = ToolSelectionPolicy().select((_tool("read_file"),))

    delivery = ToolDeliveryStrategy().deliver(selection, native_search=True)

    assert delivery.mode is ToolDeliveryMode.PROVIDER_NATIVE_SEARCH
    assert delivery.selected_names == ("read_file",)


def test_discovery_resolver_selects_native_search_for_known_target() -> None:
    from uagent.runtime.tool_discovery import (
        ToolDiscoveryMode,
        resolve_tool_discovery,
    )

    decision = resolve_tool_discovery(
        provider="openai",
        depname="gpt-5.4",
        use_responses_api=True,
        configured_mode="native",
    )

    assert decision.mode is ToolDiscoveryMode.NATIVE_SEARCH
    assert decision.uses_native_search


def test_discovery_resolver_keeps_legacy_mode_on_catalog_path() -> None:
    from uagent.runtime.tool_discovery import (
        ToolDiscoveryMode,
        resolve_tool_discovery,
    )

    decision = resolve_tool_discovery(
        provider="azure",
        depname="gpt-5.5",
        use_responses_api=True,
        configured_mode="legacy",
    )

    assert decision.mode is ToolDiscoveryMode.LEGACY_CATALOG
    assert decision.uses_legacy_catalog


def test_discovery_resolver_fails_closed_for_unknown_capability() -> None:
    from uagent.runtime.tool_discovery import (
        ToolDiscoveryMode,
        resolve_tool_discovery,
    )

    decision = resolve_tool_discovery(
        provider="openai",
        depname="future-model",
        use_responses_api=True,
        configured_mode="native",
    )

    assert decision.mode is ToolDiscoveryMode.SELECTED_SCHEMAS
    assert decision.reason == "capability_unknown"


def test_discovery_resolver_does_not_treat_gemini_as_native_search() -> None:
    from uagent.runtime.tool_discovery import (
        ToolDiscoveryMode,
        resolve_tool_discovery,
    )

    decision = resolve_tool_discovery(
        provider="gemini",
        depname="gemini-3-flash",
        use_responses_api=True,
        configured_mode="native",
    )

    assert decision.mode is ToolDiscoveryMode.SELECTED_SCHEMAS
    assert not decision.uses_native_search
