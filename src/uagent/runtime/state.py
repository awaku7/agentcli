"""Provider-neutral runtime state models extracted from core responsibilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuntimeState:
    """Small state object suitable for CLI, Web, and A2A session adapters."""

    busy: bool = False
    status_label: str = ""
    locale: str = "en"
    correlation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
