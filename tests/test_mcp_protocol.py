from __future__ import annotations

from uagent.mcp.protocol import MCPProtocolMode, detect_protocol_mode


def test_explicit_legacy_mode_requires_session() -> None:
    info = detect_protocol_mode(
        requested_mode="legacy", protocol_version="2025-11-25"
    )

    assert info.mode is MCPProtocolMode.LEGACY
    assert info.session_required is True
    assert info.detection_reason == "configured_legacy"


def test_explicit_stateless_mode_does_not_require_session() -> None:
    info = detect_protocol_mode(
        requested_mode="stateless", protocol_version="2026-07-28"
    )

    assert info.mode is MCPProtocolMode.STATELESS
    assert info.session_required is False
    assert info.detection_reason == "configured_stateless"


def test_auto_prefers_successful_stateless_probe() -> None:
    info = detect_protocol_mode(
        protocol_version="2026-07-28",
        session_id="unexpected-legacy-id",
        stateless_probe_succeeded=True,
    )

    assert info.mode is MCPProtocolMode.STATELESS
    assert info.session_required is False
    assert info.detection_reason == "stateless_probe"


def test_auto_selects_legacy_when_initialize_is_required() -> None:
    info = detect_protocol_mode(initialize_required=True)

    assert info.mode is MCPProtocolMode.LEGACY
    assert info.session_required is True
    assert info.detection_reason == "initialize_required"


def test_auto_selects_legacy_when_session_id_is_returned() -> None:
    info = detect_protocol_mode(session_id="session-1")

    assert info.mode is MCPProtocolMode.LEGACY
    assert info.session_required is True
    assert info.detection_reason == "session_id_returned"


def test_auto_does_not_guess_from_insufficient_evidence() -> None:
    info = detect_protocol_mode(protocol_version="2026-07-28")

    assert info.mode is MCPProtocolMode.UNKNOWN
    assert info.session_required is False
    assert info.detection_reason == "insufficient_evidence"


def test_invalid_requested_mode_is_structured_as_unknown() -> None:
    info = detect_protocol_mode(requested_mode="n8n")

    assert info.mode is MCPProtocolMode.UNKNOWN
    assert info.detection_reason == "invalid_requested_mode"
