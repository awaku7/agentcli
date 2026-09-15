from uagent.runtime.tool_discovery import (
    ToolCandidate,
    ToolDeliveryMode,
    ToolDeliveryStrategy,
    ToolSelectionPolicy,
    ToolSource,
)


def _tool(name: str, *, source: ToolSource = ToolSource.BUILTIN) -> ToolCandidate:
    return ToolCandidate(name, name, source, {"type": "function", "name": name})


def test_selection_preserves_management_tools_but_not_permissions() -> None:
    disabled = ToolCandidate("remote", "remote", ToolSource.MCP, {}, executable=False)
    selection = ToolSelectionPolicy({"tool_catalog"}).select(
        (_tool("tool_catalog"), _tool("read_file"), disabled), {"read_file"}
    )

    assert [item.name for item in selection.selected] == ["tool_catalog", "read_file"]


def test_zero_hit_selection_fails_open_for_legacy_catalog_path() -> None:
    selection = ToolSelectionPolicy().select((_tool("read_file"), _tool("list_dir")), {"missing"})

    assert selection.used_fallback
    assert [item.name for item in selection.selected] == ["read_file", "list_dir"]


def test_delivery_is_separate_from_selection_and_supports_native_search() -> None:
    selection = ToolSelectionPolicy().select((_tool("read_file"),))

    delivery = ToolDeliveryStrategy().deliver(selection, native_search=True)

    assert delivery.mode is ToolDeliveryMode.PROVIDER_NATIVE_SEARCH
    assert delivery.selected_names == ("read_file",)
