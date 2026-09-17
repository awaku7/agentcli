"""Build immutable provider-neutral ContextPlan instances."""

from __future__ import annotations

import copy
from typing import Any, Mapping, Sequence

from .round_contracts import ContextPlan
from .round_identity import (
    CredentialStoreWorkspaceKeyProvider,
    RoundIdentityFactory,
    WorkspaceKeyProvider,
    canonical_json,
)


def context_plan_matches(
    plan: ContextPlan | None,
    messages: Sequence[Mapping[str, Any]],
    tool_specs: Sequence[Mapping[str, Any]] = (),
) -> bool:
    """Return whether a prepared plan matches the hand-off inputs exactly."""

    if not isinstance(plan, ContextPlan):
        return False
    return plan.messages == tuple(dict(message) for message in messages) and plan.tool_specs == tuple(
        dict(spec) for spec in tool_specs
    )


def build_context_plan(
    *,
    workspace_id: str,
    messages: Sequence[Mapping[str, Any]],
    tool_specs: Sequence[Mapping[str, Any]] = (),
    decisions: Sequence[Mapping[str, Any]] = (),
    policy: Mapping[str, Any] | None = None,
    telemetry: Mapping[str, Any] | None = None,
    key_provider: WorkspaceKeyProvider | None = None,
    history_revision: str = "",
    schema_revision: str = "1",
) -> ContextPlan:
    """Create a plan without mutating messages, schemas, or telemetry."""

    frozen_messages = tuple(copy.deepcopy(dict(message)) for message in messages)
    frozen_tools = tuple(copy.deepcopy(dict(spec)) for spec in tool_specs)
    frozen_decisions = tuple(copy.deepcopy(dict(item)) for item in decisions)
    identity_payload = {
        "messages": frozen_messages,
        "tool_specs": frozen_tools,
        "decisions": frozen_decisions,
        "policy": copy.deepcopy(dict(policy or {})),
        "history_revision": str(history_revision or ""),
        "schema_revision": str(schema_revision or "1"),
    }
    factory = RoundIdentityFactory(
        workspace_id=workspace_id,
        key_provider=key_provider or CredentialStoreWorkspaceKeyProvider(),
    )
    return ContextPlan(
        plan_id=factory.plan_id(canonical_json(identity_payload)),
        messages=frozen_messages,
        tool_specs=frozen_tools,
        decisions=frozen_decisions,
        telemetry=copy.deepcopy(dict(telemetry or {})),
        input_fingerprint=factory.input_fingerprint(canonical_json(identity_payload)),
        history_revision=str(history_revision or ""),
        schema_revision=str(schema_revision or "1"),
    )


__all__ = ["build_context_plan", "context_plan_matches"]
