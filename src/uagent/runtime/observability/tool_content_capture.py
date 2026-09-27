"""Reviewed Phase 4A tool-content adapters and bounded capture buffer."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import import_module

from . import content_capture as _content
from .content_capture import (
    CaptureCandidate,
    CaptureCandidateMeta,
    ContentCapturePolicy,
    MAX_CAPTURE_CANDIDATES_PER_SPAN,
    MAX_COLLECTION_ITEMS,
    PreparedContentEvent,
    ProvenanceNode,
)

_INVALID_SCHEMA = object()


def _schema_fingerprint(value: object) -> object:
    """Normalize JSON-schema metadata while ignoring localized descriptions only."""

    if type(value) is dict:
        items: list[tuple[str, object]] = []
        for key in sorted(value):
            if type(key) is not str:
                return _INVALID_SCHEMA
            if key == "description":
                continue
            child = _schema_fingerprint(value[key])
            if child is _INVALID_SCHEMA:
                return _INVALID_SCHEMA
            items.append((key, child))
        return ("dict", tuple(items))
    if type(value) is list:
        children: list[object] = []
        for item in value:
            child = _schema_fingerprint(item)
            if child is _INVALID_SCHEMA:
                return _INVALID_SCHEMA
            children.append(child)
        return ("list", tuple(children))
    if value is None:
        return ("none",)
    if type(value) is str:
        return ("str", value)
    if type(value) is bool:
        return ("bool", value)
    if type(value) is int:
        return ("int", value)
    if type(value) is float:
        return ("float", value)
    return _INVALID_SCHEMA


@dataclass(frozen=True)
class _ReviewedToolAdapter:
    module_name: str
    argument_adapter_id: str
    result_adapter_id: str
    argument_keys: tuple[str, ...]
    argument_types: tuple[str, ...]
    required_keys: tuple[str, ...]
    parameter_schema_fingerprint: object
    result_type: type


_REVIEWED_TOOL_ADAPTERS: dict[str, _ReviewedToolAdapter] = {
    "get_current_time": _ReviewedToolAdapter(
        module_name="uagent.tools.get_current_time_tool",
        argument_adapter_id="tool.get_current_time.arguments.v1",
        result_adapter_id="tool.get_current_time.result.v1",
        argument_keys=(),
        argument_types=(),
        required_keys=(),
        parameter_schema_fingerprint=_schema_fingerprint(
            {
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        result_type=str,
    ),
    "calculator": _ReviewedToolAdapter(
        module_name="uagent.tools.calculator_tool",
        argument_adapter_id="tool.calculator.arguments.v1",
        result_adapter_id="tool.calculator.result.v1",
        argument_keys=("expression",),
        argument_types=("string",),
        required_keys=("expression",),
        parameter_schema_fingerprint=_schema_fingerprint(
            {
                "type": "object",
                "properties": {"expression": {"type": "string"}},
                "required": ["expression"],
            },
        ),
        result_type=str,
    ),
}

# Keep the policy module authoritative for provenance/category/owner validation.
# These are static reviewed adapter identifiers, not runtime/plugin-provided data.
_content._REVIEWED_ADAPTERS.update(  # type: ignore[attr-defined]
    {
        adapter.argument_adapter_id: (
            "tool_arguments",
            "tool_argument",
            "execute_tool",
        )
        for adapter in _REVIEWED_TOOL_ADAPTERS.values()
    }
)
_content._REVIEWED_ADAPTERS.update(  # type: ignore[attr-defined]
    {
        adapter.result_adapter_id: (
            "tool_result",
            "ordinary_tool_result",
            "execute_tool",
        )
        for adapter in _REVIEWED_TOOL_ADAPTERS.values()
    }
)


def _argument_meta(adapter: _ReviewedToolAdapter) -> CaptureCandidateMeta:
    entries = tuple(
        (
            ProvenanceNode(provenance="tool_argument"),
            ProvenanceNode(provenance="tool_argument"),
        )
        for _key in adapter.argument_keys
    )
    return CaptureCandidateMeta(
        category="tool_arguments",
        root_provenance="tool_argument",
        owner_kind="execute_tool",
        source_adapter_id=adapter.argument_adapter_id,
        root=ProvenanceNode(provenance="tool_argument", entries=entries),
    )


def _result_meta(adapter: _ReviewedToolAdapter) -> CaptureCandidateMeta:
    return CaptureCandidateMeta(
        category="tool_result",
        root_provenance="ordinary_tool_result",
        owner_kind="execute_tool",
        source_adapter_id=adapter.result_adapter_id,
        root=ProvenanceNode(provenance="ordinary_tool_result"),
    )


def make_tool_candidate(
    *,
    tool_name: str,
    category: str,
    value: object,
    ordinal: int,
) -> CaptureCandidate | None:
    """Create a candidate from static adapter metadata without inspecting its value."""

    if type(tool_name) is not str:
        return None
    adapter = _REVIEWED_TOOL_ADAPTERS.get(tool_name)
    if adapter is None:
        return None
    if category == "tool_arguments":
        meta = _argument_meta(adapter)
    elif category == "tool_result":
        meta = _result_meta(adapter)
    else:
        return None
    return CaptureCandidate(ordinal=ordinal, value=value, meta=meta)


def is_reviewed_tool_runner(tool_name: str, runner: object) -> bool:
    """Require the currently dispatched runner to be the reviewed built-in function."""

    if type(tool_name) is not str:
        return False
    adapter = _REVIEWED_TOOL_ADAPTERS.get(tool_name)
    if adapter is None:
        return False
    try:
        module = import_module(adapter.module_name)
        reviewed_runner = getattr(module, "run_tool", None)
        return (
            runner is reviewed_runner
            and getattr(reviewed_runner, "__module__", None) == adapter.module_name
        )
    except Exception:
        return False


def _schema_matches(tool_name: str, adapter: _ReviewedToolAdapter) -> bool:
    """Fail closed when the current static tool schema no longer matches review."""

    try:
        module = import_module(adapter.module_name)
        spec = getattr(module, "TOOL_SPEC", None)
        if type(spec) is not dict:
            return False
        function = spec.get("function")
        if type(function) is not dict or function.get("name") != tool_name:
            return False
        parameters = function.get("parameters")
        if type(parameters) is not dict or parameters.get("type") != "object":
            return False
        if _schema_fingerprint(parameters) != adapter.parameter_schema_fingerprint:
            return False
        properties = parameters.get("properties")
        required = parameters.get("required")
        if type(properties) is not dict or type(required) is not list:
            return False
        if tuple(properties.keys()) != adapter.argument_keys:
            return False
        if tuple(required) != adapter.required_keys:
            return False
        actual_types: list[str] = []
        for key in adapter.argument_keys:
            definition = properties.get(key)
            if type(definition) is not dict:
                return False
            value_type = definition.get("type")
            if type(value_type) is not str:
                return False
            actual_types.append(value_type)
        return tuple(actual_types) == adapter.argument_types
    except Exception:
        return False


def _adapter_for_candidate(
    candidate: CaptureCandidate,
) -> tuple[str, _ReviewedToolAdapter, str] | None:
    try:
        meta = candidate.meta
        if type(meta) is not CaptureCandidateMeta:
            return None
        for tool_name, reviewed in _REVIEWED_TOOL_ADAPTERS.items():
            if meta.source_adapter_id == reviewed.argument_adapter_id:
                return tool_name, reviewed, "arguments"
            if meta.source_adapter_id == reviewed.result_adapter_id:
                return tool_name, reviewed, "result"
        return None
    except Exception:
        return None


def _matches_schema_scalar(value: object, schema_type: str) -> bool:
    value_type = type(value)
    if schema_type == "string":
        return value_type is str
    if schema_type == "integer":
        return value_type is int
    if schema_type == "number":
        return value_type in {int, float}
    if schema_type == "boolean":
        return value_type is bool
    if schema_type == "object":
        return value_type is dict
    if schema_type == "array":
        return value_type is list
    if schema_type == "null":
        return value is None
    return False


def _matches_reviewed_shape(candidate: CaptureCandidate) -> bool:
    """Validate adapter/schema/value shape only after candidate admission."""

    try:
        matched = _adapter_for_candidate(candidate)
        if matched is None:
            return False
        tool_name, adapter, direction = matched
        if not _schema_matches(tool_name, adapter):
            return False
        if direction == "arguments":
            value = candidate.value
            if type(value) is not dict:
                return False
            if len(value) > MAX_COLLECTION_ITEMS:
                return False
            if len(value) != len(adapter.argument_keys):
                return False
            keys = tuple(value.keys())
            if any(type(key) is not str for key in keys):
                return False
            if keys != adapter.argument_keys:
                return False
            return all(
                _matches_schema_scalar(value[key], schema_type)
                for key, schema_type in zip(
                    adapter.argument_keys,
                    adapter.argument_types,
                )
            )
        return type(candidate.value) is adapter.result_type
    except Exception:
        return False


def _json_scalar_tokens_fit(value: object, max_field_chars: int) -> bool:
    """Bound every scalar exactly as it appears inside rendered JSON."""

    try:
        value_type = type(value)
        if value_type in {str, bool, int, float} or value is None:
            token = json.dumps(
                value,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=False,
            )
            return len(token) <= max_field_chars
        if value_type is list:
            return all(_json_scalar_tokens_fit(item, max_field_chars) for item in value)
        if value_type is dict:
            for key, item in value.items():
                if type(key) is not str:
                    return False
                key_token = json.dumps(
                    key,
                    ensure_ascii=False,
                    allow_nan=False,
                    separators=(",", ":"),
                    sort_keys=False,
                )
                if len(key_token) > max_field_chars:
                    return False
                if not _json_scalar_tokens_fit(item, max_field_chars):
                    return False
            return True
        return False
    except Exception:
        return False


def _argument_event_respects_rendered_field_limit(
    event: PreparedContentEvent,
    max_field_chars: int,
) -> bool:
    """Validate the sanitized argument JSON after escaping/serialization."""

    try:
        value = json.loads(event.value)
    except Exception:
        return False
    if type(value) is not dict:
        return False
    return _json_scalar_tokens_fit(value, max_field_chars)


def _candidate_order_key(candidate: CaptureCandidate) -> tuple[int, int] | None:
    try:
        meta = candidate.meta
        if type(meta) is not CaptureCandidateMeta:
            return None
        order = {"tool_arguments": 0, "tool_result": 1}
        category_order = order.get(meta.category)
        if category_order is None:
            return None
        if type(candidate.ordinal) is not int:
            return None
        return category_order, candidate.ordinal
    except Exception:
        return None


class ToolContentCaptureBuffer:
    """Per-``execute_tool`` buffer with reviewed-adapter shape validation.

    Candidate count and ordinal admission occur before adapter-specific value
    inspection. Unsupported tools never create a candidate. A reviewed adapter
    must match its static schema revision and exact value shape before the shared
    Phase 4A policy is allowed to inspect/render the value.
    """

    def __init__(self, policy: ContentCapturePolicy) -> None:
        self._policy = policy
        self._admitted: list[CaptureCandidate] = []
        self._seen_ordinals: set[int] = set()
        self._candidate_count = 0

    def admit(self, candidate: CaptureCandidate) -> bool:
        self._candidate_count += 1
        if self._candidate_count > MAX_CAPTURE_CANDIDATES_PER_SPAN:
            return False
        if type(candidate) is not CaptureCandidate:
            return False
        ordinal = candidate.ordinal
        if type(ordinal) is not int or not 1 <= ordinal <= 32:
            return False
        if ordinal in self._seen_ordinals:
            return False
        self._seen_ordinals.add(ordinal)
        self._admitted.append(candidate)
        return True

    def prepared_events(self) -> tuple[PreparedContentEvent, ...]:
        if not self._policy.enabled:
            return ()

        orderable: list[tuple[tuple[int, int], CaptureCandidate]] = []
        for candidate in self._admitted:
            key = _candidate_order_key(candidate)
            if key is not None:
                orderable.append((key, candidate))
        ordered = [candidate for _key, candidate in sorted(orderable)]

        used_chars = 0
        events: list[PreparedContentEvent] = []
        for candidate in ordered:
            try:
                meta = candidate.meta
                if type(meta) is not CaptureCandidateMeta:
                    continue
                if meta.category not in self._policy.categories:
                    continue
            except Exception:
                continue
            if not _matches_reviewed_shape(candidate):
                continue
            event = _content.prepare_content_event(candidate, self._policy)
            if event is None:
                continue
            if meta.category == "tool_arguments" and not (
                _argument_event_respects_rendered_field_limit(
                    event,
                    self._policy.max_field_chars,
                )
            ):
                continue
            cost = len(event.value)
            if used_chars + cost > self._policy.max_span_chars:
                continue
            used_chars += cost
            events.append(event)
        return tuple(events)

    def emit_to(self, span: object) -> int:
        emitted = 0
        try:
            add_content_event = getattr(span, "add_content_event")
        except Exception:
            return 0
        try:
            events = self.prepared_events()
        except Exception:
            return 0
        for event in events:
            try:
                accepted = add_content_event(event)
            except Exception:
                continue
            if accepted is False:
                continue
            emitted += 1
        return emitted


__all__ = [
    "ToolContentCaptureBuffer",
    "is_reviewed_tool_runner",
    "make_tool_candidate",
]
