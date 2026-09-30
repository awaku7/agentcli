from __future__ import annotations

from uagent.providers.runtime_registry import build_provider_runtime_registry
from uagent.runtime.context_plan_builder import build_context_plan
from uagent.runtime.round_contracts import RoundIdentifiers
from uagent.runtime.round_identity import (
    DeterministicTestWorkspaceKeyProvider,
    RoundIdentityFactory,
)


def test_foundry_registry_strips_reasoning_effort_from_runtime_options() -> None:
    identifiers = RoundIdentifiers(
        "turn",
        "round",
        "attempt",
        "request",
        "stream",
        1,
    )
    registry = build_provider_runtime_registry(
        provider="foundry_local",
        client=object(),
        model="phi-4-mini-reasoning",
        identifiers=identifiers,
        options={"reasoning_effort": "medium", "temperature": 0.2},
    )
    runtime = registry.resolve("foundry_local")
    key_provider = DeterministicTestWorkspaceKeyProvider()
    plan = build_context_plan(
        workspace_id="test-workspace",
        messages=[{"role": "user", "content": "solve this"}],
        policy={"provider": "foundry_local", "model": "phi-4-mini-reasoning"},
        key_provider=key_provider,
    )
    projection = runtime.project(
        plan,
        {
            "identity_factory": RoundIdentityFactory(
                "test-workspace",
                key_provider,
            )
        },
    )

    assert "reasoning_effort" not in projection.options
    assert projection.options["temperature"] == 0.2
