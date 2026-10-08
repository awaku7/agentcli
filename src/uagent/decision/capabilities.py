"""llmcapa integration for typed Decision API model capabilities."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..llmcapa_util import get_capability
from .models import DecisionRequest


def validate_model_decision_request(
    *,
    provider: str,
    model: str,
    request: DecisionRequest,
    question_kinds: Mapping[str, str],
    required_answer_fields: Mapping[str, tuple[str, ...]],
    error_type: type[Exception],
) -> Any | None:
    """Reject requests contradicted by a documented llmcapa decision record.

    Unknown models remain usable (for custom deployments and newer models),
    while explicit capability records constrain supported decision kinds and
    answer fields. Returns the capability record when one is available.
    """
    capability = get_capability(model, provider, scoped_only=True)
    decision = getattr(capability, "decision", None) if capability is not None else None
    if decision is None:
        return None

    if getattr(decision, "decision", None) is False:
        raise error_type(
            f"Model '{model}' on provider '{provider}' is not documented as "
            "supporting typed Decision API output by llmcapa."
        )

    supported_kinds = {
        str(value).strip().lower()
        for value in (getattr(decision, "question_kinds", ()) or ())
        if str(value).strip()
    }
    answer_fields = {
        str(value).strip().lower()
        for value in (getattr(decision, "answer_fields", ()) or ())
        if str(value).strip()
    }

    for question in request.questions:
        kind = question.kind.value
        wire_kind = question_kinds.get(kind)
        if wire_kind is None:
            continue
        if supported_kinds and wire_kind.lower() not in supported_kinds:
            raise error_type(
                f"Model '{model}' on provider '{provider}' does not support "
                f"'{wire_kind}' Decision API questions according to llmcapa."
            )
        required = {value.lower() for value in required_answer_fields.get(kind, ())}
        missing = required - answer_fields if answer_fields else set()
        if missing:
            fields = ", ".join(sorted(missing))
            raise error_type(
                f"Model '{model}' on provider '{provider}' does not document "
                f"required answer field(s) for '{wire_kind}': {fields}."
            )

    return decision
