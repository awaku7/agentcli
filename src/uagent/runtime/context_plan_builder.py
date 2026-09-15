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


def build_context_plan(
    *,
    workspace_id: str,
    messages: Sequence[Mapping[str, Any]],
    tool_specs: Sequence[Mapping[str, Any]] = (),
    decisions: Sequence[Mapping[str, Any]] = (),
    policy: Mapping[str, Any] | None = None,
    telemetry: Mapping[str, Any] | None = None,
    key_provider: WorkspaceKeyProvider | None = None,
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
        "schema_version": 1,
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
    )


__all__ = ["build_context_plan"]
