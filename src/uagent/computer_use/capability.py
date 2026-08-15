"""llmcapa-backed Computer Use capability lookup."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from ..llmcapa_util import get_capability


class ComputerUseCapabilityError(RuntimeError):
    """Raised when Computer Use capability metadata is unavailable."""


def get_computer_use_capability(
    model: str,
    provider: str,
) -> Any:
    """Return the llmcapa Computer Use capability for a model.

    llmcapa is the authoritative source. The agentcli runtime does not maintain
    a second model capability registry.
    """
    capability = get_capability(model, provider)
    computer_use = getattr(capability, "computer_use", None)

    # llmcapa may lag newly published OpenAI model IDs. The official
    # Computer Use guide explicitly demonstrates the GPT-5.6 family with the
    # Responses API computer tool, so keep a narrow, auditable compatibility
    # override until the catalog contains these IDs.
    normalized_model = (model or "").strip().lower()
    normalized_provider = (provider or "").strip().lower()
    if normalized_provider == "openai" and normalized_model in {
        "gpt-5.6",
        "gpt-5.6-luna",
    }:
        computer_use = SimpleNamespace(
            supported=True,
            native=True,
            provider="openai",
            model=model,
            api_type="responses",
            tool_type="computer",
            tool_version=None,
            status="ga",
            environments=frozenset({"browser", "desktop"}),
            actions=frozenset(
                {
                    "screenshot",
                    "click",
                    "double_click",
                    "type",
                    "keypress",
                    "scroll",
                    "move",
                    "drag",
                    "wait",
                }
            ),
            requires_beta=False,
            beta_header=None,
            source_url="https://developers.openai.com/api/docs/guides/tools-computer-use",
        )
    if capability is None or computer_use is None:
        raise ComputerUseCapabilityError(
            f"Computer Use capability is unavailable for {provider}/{model}"
        )
    if not getattr(computer_use, "supported", False):
        raise ComputerUseCapabilityError(
            f"Computer Use is not supported for {provider}/{model}"
        )
    return computer_use
