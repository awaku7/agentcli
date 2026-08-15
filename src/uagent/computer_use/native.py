"""Provider-native Computer Use request preparation."""

from __future__ import annotations

from typing import Any


def prepare_native_computer_use(*, core: Any, provider: str, model: str) -> bool:
    """Populate native tool metadata on ``core`` when llmcapa permits it.

    This is deliberately best-effort: unsupported or unknown models do not
    alter the existing request path.
    """
    # Clear state first so a reused core cannot send a stale tool when the
    # provider/model changes between rounds or sessions.
    for name in (
        "computer_use_native_tool",
        "computer_use_native_headers",
        "computer_use_native_provider",
    ):
        try:
            setattr(core, name, None)
        except Exception:
            pass

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
    }:
        return False
    try:
        from .capability import get_computer_use_capability

        capability = get_computer_use_capability(model, provider)
        if not getattr(capability, "native", False):
            return False
        if provider in {"claude", "anthropic"}:
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
