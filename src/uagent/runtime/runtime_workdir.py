from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from ..i18n import _


@dataclass(frozen=True)
class WorkdirDecision:
    chosen: str
    chosen_source: str
    chosen_expanded: str


_STARTUP_WORKDIR: str | None = None


def get_startup_workdir() -> str:
    return _STARTUP_WORKDIR or os.getcwd()


def decide_workdir(
    *, cli_workdir: Optional[str] = None, env_workdir: Optional[str] = None
) -> WorkdirDecision:
    """Decide workdir path without side-effects.

    Resolution order (same as CLI):
    1) CLI arg
    2) ENV(UAGENT_WORKDIR)
    3) auto (./)
    """

    if cli_workdir:
        chosen = str(cli_workdir)
        chosen_source = "CLI"
    elif env_workdir:
        chosen = str(env_workdir)
        chosen_source = "ENV(UAGENT_WORKDIR)"
    else:
        chosen = os.path.abspath("./")
        chosen_source = "auto"

    chosen_expanded = os.path.expanduser(str(chosen))

    if os.path.exists(chosen_expanded) and not os.path.isdir(chosen_expanded):
        raise NotADirectoryError(
            _("Specified workdir path is a file: %(path)s") % {"path": chosen_expanded}
        )

    return WorkdirDecision(
        chosen=chosen, chosen_source=chosen_source, chosen_expanded=chosen_expanded
    )


def apply_workdir(decision: WorkdirDecision) -> None:
    """Apply the decided workdir (mkdir + chdir)."""

    global _STARTUP_WORKDIR

    os.makedirs(decision.chosen_expanded, exist_ok=True)
    os.chdir(decision.chosen_expanded)
    if _STARTUP_WORKDIR is None:
        _STARTUP_WORKDIR = decision.chosen_expanded
