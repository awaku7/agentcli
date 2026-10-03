from __future__ import annotations

import os

import pytest

from uagent.auth.credential_store import get_default_credential_store
from uagent.auth.provider_credentials import get_provider_api_key
from uagent.decision import (
    DecisionQuestion,
    DecisionRequest,
    DecisionSettings,
    create_decision_provider,
)

_LIVE_ENABLED = (os.getenv("UAGENT_DECISION_LIVE_TEST") or "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def _live_request() -> DecisionRequest:
    return DecisionRequest(
        state={
            "goal": "Verify that the decision-provider API contract is working.",
            "status": "All requested verification work is complete.",
            "remaining_work": [],
        },
        questions=(
            DecisionQuestion(
                id="goal_status",
                kind="choice",
                instruction="Is the described verification work complete?",
                choices=("COMPLETE", "CONTINUE"),
                metadata={
                    "criteria": {
                        "COMPLETE": "All requested verification work is finished.",
                        "CONTINUE": "Material verification work remains.",
                    }
                },
            ),
        ),
        metadata={"site": "decision_provider_live_smoke"},
    )


@pytest.mark.skipif(
    not _LIVE_ENABLED,
    reason="set UAGENT_DECISION_LIVE_TEST=1 to run live decision-provider smoke tests",
)
@pytest.mark.parametrize("provider_name", ["typesafe", "openrouter"])
def test_live_remote_decision_provider_choice_contract(provider_name):
    try:
        store = get_default_credential_store()
    except Exception:
        store = None

    dedicated_name = (
        "UAGENT_DECISION_TYPESAFE_API_KEY"
        if provider_name == "typesafe"
        else "UAGENT_DECISION_OPENROUTER_API_KEY"
    )
    has_key = bool(
        (os.getenv(dedicated_name) or "").strip()
        or get_provider_api_key(provider_name, store=store)
    )
    if not has_key:
        pytest.skip(f"{provider_name} API key is not configured")

    provider = create_decision_provider(
        DecisionSettings(provider=provider_name, source="test")
    )
    assert provider is not None
    try:
        result = provider.decide(_live_request())
    finally:
        provider.close()

    answer = result.answers["goal_status"]
    assert answer.value in {"COMPLETE", "CONTINUE"}
    assert answer.confidence is not None
    assert 0.0 <= float(answer.confidence) <= 1.0
    assert isinstance(answer.metadata.get("probabilities"), dict)
