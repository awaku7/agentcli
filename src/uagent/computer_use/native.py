"""Provider-native and local Computer Use request preparation."""

from __future__ import annotations

from typing import Any

from ..i18n import _


def local_computer_tool_spec() -> dict[str, Any]:
    """Return the provider-neutral function tool for the local runtime."""
    action = {
        "type": "object",
        "properties": {
            "action": {"type": "string"},
            "x": {"type": "integer"},
            "y": {"type": "integer"},
            "coordinate": {"type": "array", "items": {"type": "integer"}},
            "text": {"type": "string"},
            "key": {"type": "string"},
            "scroll_x": {"type": "integer"},
            "scroll_y": {"type": "integer"},
            "region": {
                "type": "array",
                "items": {"type": "integer"},
                "minItems": 4,
                "maxItems": 4,
            },
        },
        "required": ["action"],
    }
    return {
        "type": "function",
        "function": {
            "name": "computer",
            "description": _(
                "Control the local desktop through the guarded Computer Use runtime."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "actions": {"type": "array", "items": action},
                    "action": {"type": "string"},
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "coordinate": {"type": "array", "items": {"type": "integer"}},
                    "text": {"type": "string"},
                    "key": {"type": "string"},
                    "scroll_x": {"type": "integer"},
                    "scroll_y": {"type": "integer"},
                    "region": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 4,
                        "maxItems": 4,
                    },
                },
                "anyOf": [{"required": ["actions"]}, {"required": ["action"]}],
            },
        },
    }


def prepare_native_computer_use(*, core: Any, provider: str, model: str) -> bool:
    """Prepare provider-native metadata subject to local Runtime safety."""
    for name in (
        "computer_use_native_tool",
        "computer_use_native_headers",
        "computer_use_native_provider",
        "computer_use_native_active",
    ):
        try:
            setattr(core, name, None)
        except Exception:
            pass

    runtime_bound = getattr(core, "computer_use_runtime", None) is not None
    # The Anthropic client toolset is a protocol declaration; its calls still
    # execute through agentcli's guarded local handler. Meta uses the same
    # boundary around Responses computer_call batches. Other native tools
    # remain disabled when a local Runtime is already bound.
    guarded_native_candidate = provider in {"claude", "anthropic", "meta"}
    if runtime_bound and not guarded_native_candidate:
        core.computer_use_native_diagnostic = (
            "native Computer Use disabled because a local runtime is bound"
        )
        return False

    if provider not in {
        "claude",
        "anthropic",
        "openai",
        "azure",
        "azure-openai",
        "azure_foundry",
        "azure-foundry",
        "gemini",
        "vertexai",
        "meta",
    }:
        return False
    try:
        from .capability import get_computer_use_capability

        capability = get_computer_use_capability(model, provider)
        if not getattr(capability, "native", False):
            return False
        if provider in {"claude", "anthropic"}:
            if runtime_bound and getattr(capability, "tool_type", None) != (
                "computer_toolset_20260801"
            ):
                core.computer_use_native_diagnostic = "legacy Anthropic native Computer Use disabled because a local runtime is bound"
                return False
            from .adapters.anthropic import AnthropicComputerAdapter

            width = int(getattr(core, "computer_use_width", 1280))
            height = int(getattr(core, "computer_use_height", 720))
            adapter = AnthropicComputerAdapter()
            core.computer_use_native_tool = adapter.build_tool(
                capability, width=width, height=height
            )
            core.computer_use_native_headers = adapter.beta_headers(capability)
        elif provider in {
            "openai",
            "azure",
            "azure-openai",
            "azure_foundry",
            "azure-foundry",
        }:
            from .adapters.openai import OpenAIComputerAdapter

            core.computer_use_native_tool = OpenAIComputerAdapter().build_tool(
                capability
            )
            core.computer_use_native_headers = []
        elif provider == "meta":
            from .adapters.meta import MetaComputerAdapter

            core.computer_use_native_tool = MetaComputerAdapter().build_tool(capability)
            core.computer_use_native_headers = []
        else:
            from .adapters.gemini import GeminiComputerAdapter

            core.computer_use_native_tool = GeminiComputerAdapter().build_tool(
                capability,
                environment=getattr(core, "computer_use_environment", "browser"),
            )
            core.computer_use_native_headers = []
        core.computer_use_native_provider = provider
        return True
    except Exception as exc:
        core.computer_use_native_diagnostic = str(exc)
        return False
