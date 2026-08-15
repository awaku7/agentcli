"""Safe runtime bootstrap shared by CLI, GUI, Web, and A2A entrypoints."""

from __future__ import annotations

from typing import Any

from .config import computer_use_policy_from_env
from .integration import install_computer_use_handler


def configure_computer_use(
    core: Any, *, provider: str, model: str, runtime: Any | None
) -> Any | None:
    """Attach an entrypoint-created runtime and install the round-loop handler.

    Runtime creation remains owned by the caller because browser and desktop
    sessions have different lifecycles and permissions.
    """
    policy = computer_use_policy_from_env()
    if runtime is None:
        core.computer_use_runtime = None
        return None
    core.computer_use_runtime = runtime
    return install_computer_use_handler(
        core=core,
        provider=provider,
        model=model,
        policy=policy,
        runtime=runtime,
    )
