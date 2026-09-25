"""Shared product-level observability settings resolution."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Mapping, Sequence

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def _parse_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    return default


def consume_otel_cli_flags(arguments: Sequence[str]) -> tuple[bool | None, list[str]]:
    """Consume ``--otel`` / ``--no-otel`` while preserving other arguments.

    The last explicit OTel flag wins, matching normal argparse behavior. This is
    intentionally separate from environment resolution because project dotenv
    files are loaded only after the working directory has been selected.
    """

    explicit_enabled: bool | None = None
    remaining: list[str] = []
    for argument in arguments:
        if argument == "--otel":
            explicit_enabled = True
            continue
        if argument == "--no-otel":
            explicit_enabled = False
            continue
        remaining.append(argument)
    return explicit_enabled, remaining


@dataclass(frozen=True)
class ObservabilitySettings:
    """Resolved UAG observability policy.

    Entry-point configuration is authoritative over environment fallback.
    Browser/message input must never construct this object directly in Web mode.
    """

    enabled: bool = False
    capture_content: bool = False
    enabled_source: str = "default"
    capture_content_source: str = "default"

    @classmethod
    def resolve(
        cls,
        *,
        explicit_enabled: bool | None = None,
        explicit_capture_content: bool | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> "ObservabilitySettings":
        env = os.environ if environ is None else environ

        if explicit_enabled is None:
            enabled = _parse_bool(env.get("UAGENT_OTEL_ENABLED"), default=False)
            enabled_source = (
                "environment" if "UAGENT_OTEL_ENABLED" in env else "default"
            )
        else:
            enabled = bool(explicit_enabled)
            enabled_source = "explicit"

        if explicit_capture_content is None:
            capture_content = _parse_bool(
                env.get("UAGENT_OTEL_CAPTURE_CONTENT"), default=False
            )
            capture_content_source = (
                "environment"
                if "UAGENT_OTEL_CAPTURE_CONTENT" in env
                else "default"
            )
        else:
            capture_content = bool(explicit_capture_content)
            capture_content_source = "explicit"

        return cls(
            enabled=enabled,
            capture_content=capture_content,
            enabled_source=enabled_source,
            capture_content_source=capture_content_source,
        )


def resolve_observability_settings(
    *,
    explicit_enabled: bool | None = None,
    explicit_capture_content: bool | None = None,
    environ: Mapping[str, str] | None = None,
) -> ObservabilitySettings:
    """Resolve settings consistently for CLI, GUI, Web, A2A, and library callers."""

    return ObservabilitySettings.resolve(
        explicit_enabled=explicit_enabled,
        explicit_capture_content=explicit_capture_content,
        environ=environ,
    )


_ENTRYPOINT_ENABLED_OVERRIDE: bool | None = None
_CURRENT_SETTINGS = ObservabilitySettings()


def set_observability_entrypoint_override(enabled: bool | None) -> None:
    """Remember an explicit launcher override until dotenv loading completes."""

    global _ENTRYPOINT_ENABLED_OVERRIDE
    _ENTRYPOINT_ENABLED_OVERRIDE = enabled


def consume_process_otel_cli_flags(argv: list[str] | None = None) -> bool | None:
    """Strip OTel flags from a process argv and retain their explicit override.

    Launchers call this before their own argument parsers. Environment fallback is
    deliberately not resolved here; ``reload_dotenv_custom()`` refreshes the final
    settings after the selected project's ``.env`` / ``.env.sec`` are loaded.
    """

    target = sys.argv if argv is None else argv
    if not target:
        set_observability_entrypoint_override(None)
        return None

    explicit_enabled, remaining = consume_otel_cli_flags(target[1:])
    target[:] = [target[0], *remaining]
    set_observability_entrypoint_override(explicit_enabled)
    return explicit_enabled


def refresh_observability_settings(
    *, environ: Mapping[str, str] | None = None
) -> ObservabilitySettings:
    """Resolve and publish process settings after dotenv loading."""

    global _CURRENT_SETTINGS
    _CURRENT_SETTINGS = resolve_observability_settings(
        explicit_enabled=_ENTRYPOINT_ENABLED_OVERRIDE,
        environ=environ,
    )
    return _CURRENT_SETTINGS


def get_observability_settings() -> ObservabilitySettings:
    """Return the latest process-level settings snapshot."""

    return _CURRENT_SETTINGS


def _reset_observability_settings_for_tests() -> None:
    global _ENTRYPOINT_ENABLED_OVERRIDE, _CURRENT_SETTINGS
    _ENTRYPOINT_ENABLED_OVERRIDE = None
    _CURRENT_SETTINGS = ObservabilitySettings()
