"""MCP protocol-mode classification.

The classifier is deliberately transport-independent. It consumes facts
observed by an adapter and returns a stable result for public tools and tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


DEFAULT_PROTOCOL_VERSION = "2026-07-28"


def select_protocol_version(
    supported_versions: list[str] | tuple[str, ...] | None,
    *,
    preferred: str = DEFAULT_PROTOCOL_VERSION,
) -> str:
    """Select a server-supported version without trusting unknown values."""
    versions = [str(version).strip() for version in (supported_versions or [])]
    versions = [version for version in versions if version]
    if preferred in versions:
        return preferred
    # The server controls ordering; use its first advertised version when the
    # preferred version is unavailable so negotiation remains forward-compatible.
    return versions[0] if versions else preferred


class MCPProtocolMode(StrEnum):
    AUTO = "auto"
    LEGACY = "legacy"
    STATELESS = "stateless"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class MCPProtocolInfo:
    mode: MCPProtocolMode
    version: str | None
    session_required: bool
    detection_reason: str


def detect_protocol_mode(
    *,
    requested_mode: str = "auto",
    protocol_version: str | None = None,
    session_id: str | None = None,
    initialize_required: bool = False,
    stateless_probe_succeeded: bool = False,
) -> MCPProtocolInfo:
    """Classify an MCP endpoint from adapter-observed facts.

    Explicit configuration wins. In auto mode, a successful stateless probe
    wins over a session identifier; otherwise an initialize/session requirement
    selects legacy mode. Ambiguous observations remain ``unknown`` rather than
    being silently treated as stateless.
    """
    requested = (requested_mode or "auto").strip().lower()
    if requested not in {mode.value for mode in MCPProtocolMode}:
        return MCPProtocolInfo(
            MCPProtocolMode.UNKNOWN,
            protocol_version,
            bool(session_id) or initialize_required,
            "invalid_requested_mode",
        )

    if requested == MCPProtocolMode.LEGACY:
        return MCPProtocolInfo(
            MCPProtocolMode.LEGACY,
            protocol_version,
            True,
            "configured_legacy",
        )
    if requested == MCPProtocolMode.STATELESS:
        return MCPProtocolInfo(
            MCPProtocolMode.STATELESS,
            protocol_version,
            False,
            "configured_stateless",
        )

    if stateless_probe_succeeded:
        return MCPProtocolInfo(
            MCPProtocolMode.STATELESS,
            protocol_version,
            False,
            "stateless_probe",
        )
    if initialize_required or session_id:
        return MCPProtocolInfo(
            MCPProtocolMode.LEGACY,
            protocol_version,
            True,
            "initialize_required" if initialize_required else "session_id_returned",
        )

    return MCPProtocolInfo(
        MCPProtocolMode.UNKNOWN,
        protocol_version,
        False,
        "insufficient_evidence",
    )
