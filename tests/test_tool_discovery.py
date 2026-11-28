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


def test_catalog_bootstrap_defers_optional_discovery_tools(monkeypatch) -> None:
    from uagent import tools
    from uagent.tools import catalog_tool, local_messaging_tool, markitdown_tool

    monkeypatch.setenv("UAGENT_EMBEDDED", "0")
    monkeypatch.setattr(tools, "_should_preload_lazy_specs", lambda: False)
    monkeypatch.setattr(tools, "TOOL_SPECS", [])
    monkeypatch.setattr(tools, "_RUNNERS", {})
    monkeypatch.setattr(tools, "_BUSY_LABEL_TOOLS", {})
    monkeypatch.setattr(tools, "_TOOL_TRACE_FLAGS", {})
    monkeypatch.setattr(tools, "_TOOL_DESCRIBERS", {})
    monkeypatch.setattr(tools, "_TOOL_SPECS_DIRTY", True)

    for module in (catalog_tool, local_messaging_tool, markitdown_tool):
        assert tools._register_tool_module(module, module.__name__)

    visible_names = {
        spec["function"]["name"]
        for spec in tools.TOOL_SPECS
        if isinstance(spec.get("function"), dict)
    }
    assert visible_names == {"tool_catalog", "tool_load", "unload_tool"}
    assert {"local_messaging", "markitdown"} <= set(tools._RUNNERS)


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


def test_anthropic_messages_search_preloads_tools_and_removes_catalog_steering(
    monkeypatch,
) -> None:
    from uagent import tools
    from uagent.runtime import tool_discovery
    from uagent.tools.llm_tool_narrowing import should_emit_catalog_steering

    monkeypatch.setenv("UAGENT_EMBEDDED", "0")
    monkeypatch.setenv("UAGENT_PROVIDER", "claude")
    monkeypatch.setenv("UAGENT_CLAUDE_MODEL", "documented-model")
    monkeypatch.setattr(
        tool_discovery,
        "anthropic_messages_tool_search_variant_from_environment",
        lambda: "bm25",
    )
    monkeypatch.setattr(
        tool_discovery,
        "anthropic_messages_tool_search_variant",
        lambda *_args, **_kwargs: "bm25",
    )

    assert tools._should_preload_lazy_specs()
    assert not should_emit_catalog_steering(
        provider="claude", depname="documented-model", use_responses_api=False
    )


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
    monkeypatch.setenv("UAGENT_OPENROUTER_DEPNAME", "unknown-openrouter-model")
    monkeypatch.setenv("UAGENT_OPENROUTER_TOOL_SEARCH", "native")
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
            True if feature == "tool_search" and model == "custom-deployment" else None
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


def test_openrouter_responses_search_has_its_own_environment_switch(
    monkeypatch,
) -> None:
    from uagent.runtime import tool_discovery
    from uagent.runtime.tool_discovery import (
        ToolDiscoveryMode,
        resolve_tool_discovery_from_environment,
    )

    monkeypatch.setattr(
        tool_discovery,
        "openrouter_responses_tool_search_variant",
        lambda *_args, **_kwargs: "regex",
    )
    monkeypatch.setenv("UAGENT_OPENROUTER_TOOL_SEARCH", "native")
    monkeypatch.setenv("UAGENT_GPT54_TOOL_SEARCH", "off")

    enabled = resolve_tool_discovery_from_environment(
        provider="openrouter",
        depname="provider/model",
        use_responses_api=True,
        capability_resolver=_tool_search_resolver(),
    )
    assert enabled.mode is ToolDiscoveryMode.NATIVE_SEARCH

    monkeypatch.setenv("UAGENT_OPENROUTER_TOOL_SEARCH", "off")
    disabled = resolve_tool_discovery_from_environment(
        provider="openrouter",
        depname="provider/model",
        use_responses_api=True,
        capability_resolver=_tool_search_resolver(),
    )
    assert disabled.mode is ToolDiscoveryMode.SELECTED_SCHEMAS
    assert disabled.reason == "disabled"

    monkeypatch.setenv("UAGENT_OPENROUTER_TOOL_SEARCH", "legacy")
    legacy = resolve_tool_discovery_from_environment(
        provider="openrouter",
        depname="unknown-openrouter-model",
        use_responses_api=True,
        capability_resolver=None,
    )
    assert legacy.mode is ToolDiscoveryMode.LEGACY_CATALOG


def test_openrouter_search_variant_uses_llmcapa_server_responses_metadata() -> None:
    from uagent.runtime.tool_discovery import (
        openrouter_responses_tool_search_variant,
    )

    assert (
        openrouter_responses_tool_search_variant(
            "openrouter", "anthropic/claude-opus-5.5"
        )
        == "regex"
    )
    assert (
        openrouter_responses_tool_search_variant("openai", "anthropic/claude-opus-5.5")
        is None
    )


def test_gemini_interactions_search_normalizes_provider_name(
    monkeypatch,
) -> None:
    import uagent.llmcapa_util as llmcapa_util
    import uagent.providers.gemini_api_mode as gemini_api_mode_module
    from uagent.runtime.tool_discovery import (
        gemini_interactions_tool_retrieval_enabled,
    )

    monkeypatch.setattr(
        gemini_api_mode_module,
        "gemini_api_mode",
        lambda _model, _provider: "interactions",
    )
    monkeypatch.setattr(
        llmcapa_util,
        "supports_feature",
        lambda _feature, _model, _provider, default=None: True,
    )

    assert gemini_interactions_tool_retrieval_enabled(
        "Gemini", "gemini-3-flash-preview"
    )


def test_deepseek_client_tool_search_is_responses_only_and_model_gated(
    monkeypatch,
) -> None:
    from uagent.runtime.tool_discovery import (
        ToolDiscoveryMode,
        resolve_tool_discovery_from_environment,
    )

    monkeypatch.setenv("UAGENT_DEEPSEEK_TOOL_SEARCH", "native")
    supported = resolve_tool_discovery_from_environment(
        provider="deepseek",
        depname="deepseek-flash",
        use_responses_api=True,
    )
    unsupported_model = resolve_tool_discovery_from_environment(
        provider="deepseek",
        depname="deepseek-v4-pro",
        use_responses_api=True,
    )
    chat_completions = resolve_tool_discovery_from_environment(
        provider="deepseek",
        depname="deepseek-flash",
        use_responses_api=False,
    )
    monkeypatch.setenv("UAGENT_DEEPSEEK_TOOL_SEARCH", "off")
    disabled = resolve_tool_discovery_from_environment(
        provider="deepseek",
        depname="deepseek-flash",
        use_responses_api=True,
    )
    monkeypatch.setenv("UAGENT_DEEPSEEK_TOOL_SEARCH", "legacy")
    legacy = resolve_tool_discovery_from_environment(
        provider="deepseek",
        depname="deepseek-v4-pro",
        use_responses_api=True,
    )
    monkeypatch.setenv("UAGENT_DEEPSEEK_TOOL_SEARCH", "native")
    monkeypatch.setenv("UAGENT_EMBEDDED", "1")
    embedded = resolve_tool_discovery_from_environment(
        provider="deepseek",
        depname="deepseek-flash",
        use_responses_api=True,
    )

    assert supported.mode is ToolDiscoveryMode.NATIVE_SEARCH
    assert unsupported_model.mode is ToolDiscoveryMode.SELECTED_SCHEMAS
    assert chat_completions.mode is ToolDiscoveryMode.SELECTED_SCHEMAS
    assert disabled.mode is ToolDiscoveryMode.SELECTED_SCHEMAS
    assert legacy.mode is ToolDiscoveryMode.LEGACY_CATALOG
    assert embedded.mode is ToolDiscoveryMode.SELECTED_SCHEMAS


def test_deepseek_native_search_preloads_lazy_schemas_and_drops_catalog_steering(
    monkeypatch,
) -> None:
    from uagent import tools
    from uagent.tools.llm_tool_narrowing import should_emit_catalog_steering

    monkeypatch.setenv("UAGENT_EMBEDDED", "0")
    monkeypatch.setenv("UAGENT_PROVIDER", "deepseek")
    monkeypatch.setenv("UAGENT_DEEPSEEK_DEPNAME", "deepseek-flash")
    monkeypatch.setenv("UAGENT_RESPONSES", "1")
    monkeypatch.setenv("UAGENT_DEEPSEEK_TOOL_SEARCH", "native")

    assert tools._should_preload_lazy_specs()
    assert not should_emit_catalog_steering(
        provider="deepseek",
        depname="deepseek-flash",
        use_responses_api=True,
    )
