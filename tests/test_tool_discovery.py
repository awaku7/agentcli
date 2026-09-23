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


def test_environment_resolver_and_spec_selection_share_one_policy(monkeypatch) -> None:
    from uagent.runtime.tool_discovery import (
        ToolDiscoveryMode,
        resolve_tool_discovery_from_environment,
        select_tool_specs_for_discovery,
    )

    monkeypatch.setenv("UAGENT_PROVIDER", "openai")
    monkeypatch.setenv("UAGENT_OPENAI_DEPNAME", "gpt-5.4")
    monkeypatch.setenv("UAGENT_RESPONSES", "1")
    monkeypatch.setenv("UAGENT_GPT54_TOOL_SEARCH", "native")

    native = resolve_tool_discovery_from_environment()
    legacy_specs = [{"name": "legacy"}]
    native_specs = [{"name": "native"}]
    selected_specs = [{"name": "selected"}]

    assert native.mode is ToolDiscoveryMode.NATIVE_SEARCH
    assert (
        select_tool_specs_for_discovery(
            native,
            legacy_specs=legacy_specs,
            native_specs=native_specs,
            selected_specs=selected_specs,
        )
        is native_specs
    )

    monkeypatch.setenv("UAGENT_GPT54_TOOL_SEARCH", "off")
    selected = resolve_tool_discovery_from_environment()
    assert selected.mode is ToolDiscoveryMode.SELECTED_SCHEMAS
    assert (
        select_tool_specs_for_discovery(
            selected,
            legacy_specs=legacy_specs,
            native_specs=native_specs,
            selected_specs=selected_specs,
        )
        is selected_specs
    )


def test_environment_resolver_uses_capability_resolver_in_auto_mode(
    monkeypatch,
) -> None:
    from uagent.runtime.capability_resolver import CapabilityResolver
    from uagent.runtime.tool_discovery import (
        ToolDiscoveryMode,
        resolve_tool_discovery_from_environment,
    )

    monkeypatch.setenv("UAGENT_PROVIDER", "openai")
    monkeypatch.setenv("UAGENT_OPENAI_DEPNAME", "gpt-5.4")
    monkeypatch.delenv("UAGENT_RESPONSES", raising=False)
    monkeypatch.setenv("UAGENT_GPT54_TOOL_SEARCH", "native")

    enabled = resolve_tool_discovery_from_environment(
        capability_resolver=CapabilityResolver(
            feature_lookup=lambda feature, *_: (
                feature in {"responses_api", "tool_search"}
            )
        )
    )
    unknown = resolve_tool_discovery_from_environment(
        capability_resolver=CapabilityResolver(feature_lookup=lambda *_: None)
    )

    assert enabled.mode is ToolDiscoveryMode.NATIVE_SEARCH
    assert unknown.mode is ToolDiscoveryMode.SELECTED_SCHEMAS


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


def test_management_bootstrap_policy_is_owned_by_discovery_decision() -> None:
    from uagent.runtime.tool_discovery import (
        ToolDiscoveryDecision,
        ToolDiscoveryMode,
    )

    legacy = ToolDiscoveryDecision(ToolDiscoveryMode.LEGACY_CATALOG, "legacy_mode")
    native = ToolDiscoveryDecision(ToolDiscoveryMode.NATIVE_SEARCH, "native_mode")
    selected = ToolDiscoveryDecision(
        ToolDiscoveryMode.SELECTED_SCHEMAS, "capability_unknown"
    )

    assert legacy.uses_management_bootstrap(use_responses_api=True)
    assert native.uses_management_bootstrap(use_responses_api=False)
    assert not native.uses_management_bootstrap(use_responses_api=True)
    assert not selected.uses_management_bootstrap(use_responses_api=False)
    assert legacy.needs_catalog_steering()
    assert not native.needs_catalog_steering()
    assert selected.needs_catalog_steering()


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
        capability_resolver=_tool_search_resolver(),
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
        capability_resolver=_tool_search_resolver(),
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
    assert decision.reason == "tool_search_unavailable"


def test_llmcapa_tool_search_flag_enables_openai_gpt54_mini() -> None:
    from uagent.runtime.tool_discovery import (
        ToolDiscoveryMode,
        resolve_tool_discovery,
    )

    decision = resolve_tool_discovery(
        provider="openai",
        depname="gpt-5.4-mini",
        use_responses_api=True,
        configured_mode="native",
    )

    assert decision.mode is ToolDiscoveryMode.NATIVE_SEARCH


def _tool_search_resolver():
    from uagent.runtime.capability_resolver import CapabilityResolver

    return CapabilityResolver(
        feature_lookup=lambda feature, *_: True if feature == "tool_search" else None
    )


def test_discovery_uses_llmcapa_capability_instead_of_model_name_heuristics() -> None:
    from uagent.runtime.capability_resolver import CapabilityResolver
    from uagent.runtime.tool_discovery import (
        ToolDiscoveryMode,
        resolve_tool_discovery,
    )

    resolver = CapabilityResolver(
        feature_lookup=lambda feature, model, *_: (
            True
            if feature == "tool_search" and model == "custom-deployment"
            else None
        )
    )
    supported = resolve_tool_discovery(
        provider="openai",
        depname="custom-deployment",
        use_responses_api=True,
        capability_resolver=resolver,
    )
    unknown = resolve_tool_discovery(
        provider="openai",
        depname="future-model",
        use_responses_api=True,
        capability_resolver=resolver,
    )

    assert supported.mode is ToolDiscoveryMode.NATIVE_SEARCH
    assert unknown.mode is ToolDiscoveryMode.SELECTED_SCHEMAS


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
