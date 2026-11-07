"""Reviewed image-generation telemetry on the existing execute_tool span.

Only the built-in generator constructs this projection. Image bytes, paths,
URLs, credentials and raw exception messages never enter the projection.
"""

from __future__ import annotations

import json
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
from typing import Any

from . import content_capture as content
from .settings import get_observability_settings

content._REVIEWED_ADAPTERS.update(
    {
        "tool.generate_image.arguments.v1": (
            "tool_arguments",
            "tool_argument",
            "execute_tool",
        ),
        "tool.generate_image.result.v1": (
            "tool_result",
            "ordinary_tool_result",
            "execute_tool",
        ),
    }
)


@dataclass
class _Observation:
    active: Any
    buffer: Any = None
    succeeded: bool = False
    usage: dict[str, int] = field(default_factory=dict)


_CURRENT: ContextVar[_Observation | None] = ContextVar(
    "uag_image_observation", default=None
)


def _text(value: object) -> str | None:
    if (
        type(value) is str
        and 0 < len(value) <= 512
        and not any(
            ord(c) < 32 or ord(c) == 127 or 0xD800 <= ord(c) <= 0xDFFF for c in value
        )
    ):
        return value
    return None


def _capture(state: _Observation, category: str, value: object, ordinal: int) -> None:
    if state.buffer is None:
        return
    provenance = (
        "tool_argument" if category == "tool_arguments" else "ordinary_tool_result"
    )
    root = content.ProvenanceNode(provenance=provenance)
    if type(value) is dict:
        root = content.ProvenanceNode(
            provenance=provenance,
            entries=tuple(
                (
                    content.ProvenanceNode(provenance=provenance),
                    content.ProvenanceNode(provenance=provenance),
                )
                for _ in value
            ),
        )
    state.buffer.admit(
        content.CaptureCandidate(
            ordinal=ordinal,
            value=value,
            meta=content.CaptureCandidateMeta(
                category=category,
                root_provenance=provenance,
                owner_kind="execute_tool",
                source_adapter_id="tool.generate_image."
                + ("arguments.v1" if ordinal == 1 else "result.v1"),
                root=root,
            ),
        )
    )


def observe_image_generation(runner):
    @wraps(runner)
    def observed(args):
        from .runtime import _ACTIVE_TOOL_SPANS

        stack = _ACTIVE_TOOL_SPANS.get()
        if not stack or stack[-1].tool_name != "generate_image":
            return runner(args)
        state = _Observation(stack[-1])
        try:
            policy = content.ContentCapturePolicy.from_settings(
                get_observability_settings()
            )
            if policy.enabled:
                state.buffer = content.ContentCaptureBuffer(policy)
                if (
                    "tool_arguments" in policy.categories
                    and type(args) is dict
                    and type(args.get("prompt")) is str
                ):
                    _capture(state, "tool_arguments", {"prompt": args["prompt"]}, 1)
        except Exception:
            state.buffer = None
        token = _CURRENT.set(state)
        try:
            return runner(args)
        finally:
            try:
                if not state.succeeded:
                    state.active.failed = True
                    state.active.span.set_attribute("uag.status", "error")
                    state.active.span.set_status("error", "image generation failed")
                    _capture(state, "tool_result", '{"ok":false}', 2)
                if state.buffer is not None:
                    state.buffer.emit_to(state.active.span)
            except Exception:
                pass
            _CURRENT.reset(token)

    return observed


def record_image_request(**values: object) -> None:
    state = _CURRENT.get()
    if state is None:
        return
    names = {
        "provider": "uag.llm.provider",
        "model": "gen_ai.request.model",
        "size": "uag.image.size",
        "output_format": "uag.image.output_format",
        "quality": "uag.image.quality",
    }
    try:
        for key, attribute in names.items():
            value = _text(values.get(key))
            if value:
                state.active.span.set_attribute(attribute, value)
        count = values.get("n")
        if type(count) is int and 1 <= count <= 10:
            state.active.span.set_attribute("uag.image.requested_count", count)
    except Exception:
        pass


def record_image_usage(usage: object) -> None:
    state = _CURRENT.get()
    if state is None or usage is None:
        return
    try:
        if not isinstance(usage, dict):
            dump = getattr(usage, "model_dump", None)
            usage = (
                dump()
                if callable(dump)
                else {
                    key: getattr(usage, key, None)
                    for key in (
                        "input_tokens",
                        "output_tokens",
                        "prompt_token_count",
                        "candidates_token_count",
                    )
                }
            )
        if type(usage) is not dict:
            return
        for name, aliases in {
            "input_tokens": ("input_tokens", "prompt_token_count"),
            "output_tokens": ("output_tokens", "candidates_token_count"),
        }.items():
            value = next((usage[k] for k in aliases if k in usage), None)
            if type(value) is int and 0 <= value <= 10**12:
                total = state.usage.get(name, 0) + value
                if total <= 10**12:
                    state.usage[name] = total
                    state.active.span.set_attribute("gen_ai.usage." + name, total)
    except Exception:
        pass


def record_image_success(count: int, artifacts: object) -> None:
    state = _CURRENT.get()
    if state is None:
        return
    try:
        if type(count) is not int or count < 1:
            return
        state.succeeded = True
        if count > 10:
            return
        state.active.span.set_attribute("uag.image.generated_count", count)
        ids = []
        if type(artifacts) is list:
            for artifact in artifacts[:10]:
                identifier = (
                    artifact.get("artifact_id") if type(artifact) is dict else None
                )
                if (
                    type(identifier) is str
                    and len(identifier) == 32
                    and all(c in "0123456789abcdef" for c in identifier)
                ):
                    ids.append(identifier)
        _capture(
            state,
            "tool_result",
            json.dumps(
                {"ok": True, "generated_count": count, "artifact_ids": ids},
                separators=(",", ":"),
            ),
            2,
        )
    except Exception:
        pass


def record_image_response_usage(response: object, *, field: str = "usage") -> None:
    """Accept SDK model objects and compatibility-provider dictionaries alike."""
    try:
        usage = (
            response.get(field)
            if type(response) is dict
            else getattr(response, field, None)
        )
        record_image_usage(usage)
    except Exception:
        pass
