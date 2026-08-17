"""llmcapa-backed Computer Use capability lookup."""

from __future__ import annotations

from typing import Any

from ..llmcapa_util import get_capability
from ..i18n import _


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

    if capability is None or computer_use is None:
        raise ComputerUseCapabilityError(
            _("Computer Use capability is unavailable for %(provider)s/%(model)s") % {"provider": provider, "model": model}
        )
    if not getattr(computer_use, "supported", False):
        raise ComputerUseCapabilityError(
            _("Computer Use is not supported for %(provider)s/%(model)s") % {"provider": provider, "model": model}
        )
    return computer_use
