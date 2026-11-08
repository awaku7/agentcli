"""Shared product-level observability settings resolution."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, replace
from typing import Any, Mapping, Sequence

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}
_CAPTURE_CATEGORIES = frozenset(
    {"user_input", "assistant_output", "tool_arguments", "tool_result"}
)
_PROVIDER_SELECTORS = frozenset({"openai", "claude"})
_DEFAULT_CAPTURE_MAX_FIELD_CHARS = 2048
_DEFAULT_CAPTURE_MAX_SPAN_CHARS = 8192


def _ascii_lower(value: str) -> str:
    chars: list[str] = []
    for char in value:
        code = ord(char)
        if 65 <= code <= 90:
            chars.append(chr(code + 32))
        else:
            chars.append(char)
    return "".join(chars)


def _strip_ascii_space_tab(value: str) -> str:
    return value.strip(" \t")


def _parse_env_bool(value: object, *, default: bool = False) -> tuple[bool, bool]:
    if value is None:
        return default, True
    if type(value) is not str or len(value) > 16:
        return False, False
    normalized = _ascii_lower(_strip_ascii_space_tab(value))
    if normalized in _TRUE_VALUES:
        return True, True
    if normalized in _FALSE_VALUES:
        return False, True
    return False, False


def _parse_programmatic_bool(
    value: object, *, default: bool = False
) -> tuple[bool, bool]:
    if value is None:
        return default, True
    if type(value) is bool:
        return value, True
    return False, False


def _parse_cli_bool(value: object, *, default: bool = False) -> tuple[bool, bool]:
    if value is None:
        return default, True
    if type(value) is bool:
        return value, True
    return False, False


def _parse_ascii_integer(value: object) -> tuple[int | None, bool]:
    if type(value) is not str or not 1 <= len(value) <= 5:
        return None, False
    if value == "0":
        return 0, True
    if value[0] == "0":
        return None, False
    if any(char < "0" or char > "9" for char in value):
        return None, False
    return int(value), True


def _parse_programmatic_integer(value: object) -> tuple[int | None, bool]:
    if type(value) is not int:
        return None, False
    return value, True


def _parse_csv(
    value: object, *, valid_tokens: frozenset[str]
) -> tuple[frozenset[str], bool]:
    if value is None:
        return frozenset(), True
    if type(value) is not str or len(value) > 256:
        return frozenset(), False
    if value == "":
        return frozenset(), True

    tokens: list[str] = []
    for raw_token in value.split(","):
        token = _strip_ascii_space_tab(raw_token)
        if not token or token not in valid_tokens:
            return frozenset(), False
        tokens.append(token)
    return frozenset(tokens), True


def _parse_provider_csv(value: object) -> frozenset[str]:
    if value is None:
        return frozenset()
    if type(value) is not str or len(value) > 256 or value == "":
        return frozenset()

    selected: set[str] = set()
    for raw_token in value.split(","):
        token = _strip_ascii_space_tab(raw_token)
        if token in _PROVIDER_SELECTORS:
            selected.add(token)
    return frozenset(selected)


def _resolve_raw_string(
    *,
    explicit: object,
    cli: object,
    env_present: bool,
    env_value: object,
    default: str | None,
) -> tuple[str | None, str]:
    if explicit is not None:
        if type(explicit) is str:
            return explicit, "explicit"
        return None, "explicit-invalid"
    if cli is not None:
        if type(cli) is str:
            return cli, "cli"
        return None, "cli-invalid"
    if env_present:
        if type(env_value) is str:
            return env_value, "environment"
        return None, "environment-invalid"
    return default, "default"


@dataclass(frozen=True)
class ObservabilityCliOverrides:
    enabled: object = None
    capture_content: object = None


@dataclass(frozen=True)
class ObservabilitySettings:
    """Resolved UAG observability policy.

    Entry-point configuration is authoritative over environment fallback.
    Browser/message input must never construct this object directly in Web mode.
    """

    enabled: bool = False
    capture_content: bool = False
    capture_categories: frozenset[str] = frozenset()
    capture_max_field_chars: int = _DEFAULT_CAPTURE_MAX_FIELD_CHARS
    capture_max_span_chars: int = _DEFAULT_CAPTURE_MAX_SPAN_CHARS
    pseudonymous_correlation: bool = False
    deployment_scope: str | None = None
    correlation_key_name: str | None = "observability/correlation"
    correlation_key_version: str | None = "v1"
    provider_instrumentation: frozenset[str] = frozenset()
    trace_query_enabled: bool = False
    enabled_source: str = "default"
    capture_content_source: str = "default"

    @classmethod
    def resolve(
        cls,
        *,
        explicit_enabled: bool | None = None,
        explicit_capture_content: bool | None = None,
        explicit_capture_categories: str | None = None,
        explicit_capture_max_field_chars: int | None = None,
        explicit_capture_max_span_chars: int | None = None,
        explicit_pseudonymous_correlation: bool | None = None,
        explicit_deployment_scope: str | None = None,
        explicit_correlation_key_name: str | None = None,
        explicit_correlation_key_version: str | None = None,
        explicit_provider_instrumentation: str | None = None,
        explicit_trace_query_enabled: bool | None = None,
        cli_overrides: ObservabilityCliOverrides | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> "ObservabilitySettings":
        env = os.environ if environ is None else environ
        cli = cli_overrides or ObservabilityCliOverrides()

        enabled, enabled_source = _resolve_bool_setting(
            explicit=explicit_enabled,
            cli=cli.enabled,
            env=env,
            env_name="UAGENT_OTEL_ENABLED",
            default=False,
        )
        capture_requested, capture_source = _resolve_bool_setting(
            explicit=explicit_capture_content,
            cli=cli.capture_content,
            env=env,
            env_name="UAGENT_OTEL_CAPTURE_CONTENT",
            default=False,
        )

        categories_raw, _ = _resolve_value_setting(
            explicit=explicit_capture_categories,
            cli=None,
            env=env,
            env_name="UAGENT_OTEL_CAPTURE_CATEGORIES",
        )
        # The single CLI content opt-in always requests all four reviewed
        # categories. The advanced environment/programmatic selectors remain
        # separate from the public launcher flags.
        if cli.capture_content is True and explicit_capture_categories is None:
            capture_categories, categories_valid = _CAPTURE_CATEGORIES, True
        else:
            capture_categories, categories_valid = _parse_csv(
                categories_raw, valid_tokens=_CAPTURE_CATEGORIES
            )

        field_raw, field_origin = _resolve_value_setting(
            explicit=explicit_capture_max_field_chars,
            cli=None,
            env=env,
            env_name="UAGENT_OTEL_CAPTURE_MAX_FIELD_CHARS",
        )
        max_field, field_valid = _resolve_integer_value(
            field_raw,
            origin=field_origin,
            default=_DEFAULT_CAPTURE_MAX_FIELD_CHARS,
        )

        span_raw, span_origin = _resolve_value_setting(
            explicit=explicit_capture_max_span_chars,
            cli=None,
            env=env,
            env_name="UAGENT_OTEL_CAPTURE_MAX_SPAN_CHARS",
        )
        max_span, span_valid = _resolve_integer_value(
            span_raw,
            origin=span_origin,
            default=_DEFAULT_CAPTURE_MAX_SPAN_CHARS,
        )

        bounds_valid = (
            field_valid
            and span_valid
            and 64 <= max_field <= 16384
            and 256 <= max_span <= 65536
            and max_span >= max_field
        )

        pseudonymous_correlation, _ = _resolve_bool_setting(
            explicit=explicit_pseudonymous_correlation,
            cli=None,
            env=env,
            env_name="UAGENT_OTEL_PSEUDONYMOUS_CORRELATION",
            default=False,
        )
        deployment_scope, _ = _resolve_raw_string(
            explicit=explicit_deployment_scope,
            cli=None,
            env_present="UAGENT_OTEL_DEPLOYMENT_SCOPE" in env,
            env_value=env.get("UAGENT_OTEL_DEPLOYMENT_SCOPE"),
            default=None,
        )
        correlation_key_name, _ = _resolve_raw_string(
            explicit=explicit_correlation_key_name,
            cli=None,
            env_present="UAGENT_OTEL_CORRELATION_KEY_NAME" in env,
            env_value=env.get("UAGENT_OTEL_CORRELATION_KEY_NAME"),
            default="observability/correlation",
        )
        correlation_key_version, _ = _resolve_raw_string(
            explicit=explicit_correlation_key_version,
            cli=None,
            env_present="UAGENT_OTEL_CORRELATION_KEY_VERSION" in env,
            env_value=env.get("UAGENT_OTEL_CORRELATION_KEY_VERSION"),
            default="v1",
        )

        provider_raw, _ = _resolve_value_setting(
            explicit=explicit_provider_instrumentation,
            cli=None,
            env=env,
            env_name="UAGENT_OTEL_PROVIDER_INSTRUMENTATION",
        )
        provider_instrumentation = _parse_provider_csv(provider_raw)

        trace_query_enabled, _ = _resolve_bool_setting(
            explicit=explicit_trace_query_enabled,
            cli=None,
            env=env,
            env_name="UAGENT_OTEL_TRACE_QUERY_ENABLED",
            default=False,
        )

        capture_effective = (
            enabled and capture_requested and categories_valid and bounds_valid
        )
        if not enabled:
            pseudonymous_correlation = False
            provider_instrumentation = frozenset()
            trace_query_enabled = False

        return cls(
            enabled=enabled,
            capture_content=capture_effective,
            capture_categories=capture_categories,
            capture_max_field_chars=max_field,
            capture_max_span_chars=max_span,
            pseudonymous_correlation=pseudonymous_correlation,
            deployment_scope=deployment_scope,
            correlation_key_name=correlation_key_name,
            correlation_key_version=correlation_key_version,
            provider_instrumentation=provider_instrumentation,
            trace_query_enabled=trace_query_enabled,
            enabled_source=enabled_source,
            capture_content_source=capture_source,
        )


def _resolve_bool_setting(
    *,
    explicit: object,
    cli: object,
    env: Mapping[str, str],
    env_name: str,
    default: bool,
) -> tuple[bool, str]:
    if explicit is not None:
        value, valid = _parse_programmatic_bool(explicit, default=default)
        return (
            value if valid else False,
            "explicit" if valid else "explicit-invalid",
        )
    if cli is not None:
        value, valid = _parse_cli_bool(cli, default=default)
        return (value if valid else False), ("cli" if valid else "cli-invalid")
    if env_name in env:
        value, valid = _parse_env_bool(env.get(env_name), default=default)
        return (
            value if valid else False,
            "environment" if valid else "environment-invalid",
        )
    return default, "default"


def _resolve_value_setting(
    *,
    explicit: object,
    cli: object,
    env: Mapping[str, str],
    env_name: str,
) -> tuple[object, str]:
    if explicit is not None:
        return explicit, "explicit"
    if cli is not None:
        return cli, "cli"
    if env_name in env:
        return env.get(env_name), "environment"
    return None, "default"


def _resolve_integer_value(
    raw: object, *, origin: str, default: int
) -> tuple[int, bool]:
    if origin == "default":
        return default, True
    if origin == "explicit":
        value, valid = _parse_programmatic_integer(raw)
    else:
        value, valid = _parse_ascii_integer(raw)
    return (value if valid and value is not None else default), valid


_BOOL_FLAGS = {
    "--otel": ("enabled", True),
    "--no-otel": ("enabled", False),
    "--otel-content": ("capture_content", True),
}


def consume_observability_cli_flags(
    arguments: Sequence[str],
) -> tuple[ObservabilityCliOverrides, list[str]]:
    """Consume the three supported OTel launcher flags and reject retired flags."""

    overrides = ObservabilityCliOverrides()
    remaining: list[str] = []
    for argument in arguments:
        bool_flag = _BOOL_FLAGS.get(argument)
        if bool_flag is not None:
            field_name, value = bool_flag
            overrides = replace(overrides, **{field_name: value})
        elif argument.startswith(("--otel-", "--no-otel-")):
            raise ValueError(f"Unsupported OTel option: {argument}")
        else:
            remaining.append(argument)
    return overrides, remaining


def resolve_observability_settings(
    *,
    explicit_enabled: bool | None = None,
    explicit_capture_content: bool | None = None,
    explicit_capture_categories: str | None = None,
    explicit_capture_max_field_chars: int | None = None,
    explicit_capture_max_span_chars: int | None = None,
    explicit_pseudonymous_correlation: bool | None = None,
    explicit_deployment_scope: str | None = None,
    explicit_correlation_key_name: str | None = None,
    explicit_correlation_key_version: str | None = None,
    explicit_provider_instrumentation: str | None = None,
    explicit_trace_query_enabled: bool | None = None,
    cli_overrides: ObservabilityCliOverrides | None = None,
    environ: Mapping[str, str] | None = None,
) -> ObservabilitySettings:
    """Resolve settings consistently for CLI, GUI, Web, A2A, and library callers."""

    return ObservabilitySettings.resolve(
        explicit_enabled=explicit_enabled,
        explicit_capture_content=explicit_capture_content,
        explicit_capture_categories=explicit_capture_categories,
        explicit_capture_max_field_chars=explicit_capture_max_field_chars,
        explicit_capture_max_span_chars=explicit_capture_max_span_chars,
        explicit_pseudonymous_correlation=explicit_pseudonymous_correlation,
        explicit_deployment_scope=explicit_deployment_scope,
        explicit_correlation_key_name=explicit_correlation_key_name,
        explicit_correlation_key_version=explicit_correlation_key_version,
        explicit_provider_instrumentation=explicit_provider_instrumentation,
        explicit_trace_query_enabled=explicit_trace_query_enabled,
        cli_overrides=cli_overrides,
        environ=environ,
    )


_ENTRYPOINT_CLI_OVERRIDES = ObservabilityCliOverrides()
_CURRENT_SETTINGS = ObservabilitySettings()


def set_observability_entrypoint_override(enabled: bool | None) -> None:
    """Remember an explicit launcher core-OTel override until dotenv loads."""

    global _ENTRYPOINT_CLI_OVERRIDES
    _ENTRYPOINT_CLI_OVERRIDES = replace(_ENTRYPOINT_CLI_OVERRIDES, enabled=enabled)


def set_observability_content_entrypoint_override(enabled: bool) -> None:
    """Enable reviewed content categories for an explicit A2A argv launch."""

    global _ENTRYPOINT_CLI_OVERRIDES
    _ENTRYPOINT_CLI_OVERRIDES = replace(
        _ENTRYPOINT_CLI_OVERRIDES, capture_content=enabled
    )


def consume_process_otel_cli_flags(argv: list[str] | None = None) -> bool | None:
    """Strip UAG observability flags and retain overrides until dotenv resolution."""

    global _ENTRYPOINT_CLI_OVERRIDES

    target = sys.argv if argv is None else argv
    if not target:
        return None

    overrides, remaining = consume_observability_cli_flags(target[1:])
    target[:] = [target[0], *remaining]
    _ENTRYPOINT_CLI_OVERRIDES = _merge_cli_overrides(
        _ENTRYPOINT_CLI_OVERRIDES, overrides
    )
    enabled = overrides.enabled
    return enabled if type(enabled) is bool else None


def _merge_cli_overrides(
    earlier: ObservabilityCliOverrides, later: ObservabilityCliOverrides
) -> ObservabilityCliOverrides:
    values: dict[str, Any] = {}
    for field_name in ObservabilityCliOverrides.__dataclass_fields__:
        new_value = getattr(later, field_name)
        values[field_name] = (
            new_value if new_value is not None else getattr(earlier, field_name)
        )
    return ObservabilityCliOverrides(**values)


def _without_enabled(
    overrides: ObservabilityCliOverrides,
) -> ObservabilityCliOverrides:
    return replace(overrides, enabled=None)


def refresh_observability_settings(
    *, environ: Mapping[str, str] | None = None
) -> ObservabilitySettings:
    """Resolve and publish process settings after dotenv loading."""

    global _CURRENT_SETTINGS

    entrypoint_enabled = _ENTRYPOINT_CLI_OVERRIDES.enabled
    explicit_enabled = entrypoint_enabled if type(entrypoint_enabled) is bool else None
    _CURRENT_SETTINGS = resolve_observability_settings(
        explicit_enabled=explicit_enabled,
        cli_overrides=_without_enabled(_ENTRYPOINT_CLI_OVERRIDES),
        environ=environ,
    )
    return _CURRENT_SETTINGS


def get_observability_settings() -> ObservabilitySettings:
    """Return the latest process-level settings snapshot."""

    return _CURRENT_SETTINGS


def _reset_observability_settings_for_tests() -> None:
    global _ENTRYPOINT_CLI_OVERRIDES, _CURRENT_SETTINGS
    _ENTRYPOINT_CLI_OVERRIDES = ObservabilityCliOverrides()
    _CURRENT_SETTINGS = ObservabilitySettings()
