from __future__ import annotations

from types import SimpleNamespace

import pytest

from uagent.llm_round_helpers import _resolve_round_runtime_flags
from uagent.runtime.capability_resolver import CapabilityResolver


def _core() -> SimpleNamespace:
    return SimpleNamespace(set_status=lambda *args: None)


def test_explicit_responses_request_respects_model_false_capability(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_RESPONSES", "1")
    monkeypatch.setenv("UAGENT_STREAMING", "0")
    resolver = CapabilityResolver(
        feature_lookup=lambda feature, *_: False if feature == "responses_api" else None
    )

    assert _resolve_round_runtime_flags(
        tr_cfg=None,
        core=_core(),
        provider="foundry_local",
        depname="phi-4-mini",
        capability_resolver=resolver,
    ) == (False, False)


def test_explicit_responses_request_allows_positive_model_capability(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_RESPONSES", "1")
    monkeypatch.setenv("UAGENT_STREAMING", "0")
    resolver = CapabilityResolver(
        feature_lookup=lambda feature, *_: True if feature == "responses_api" else None
    )

    assert _resolve_round_runtime_flags(
        tr_cfg=None,
        core=_core(),
        provider="openai",
        depname="example-model",
        capability_resolver=resolver,
    ) == (True, False)


def test_streaming_false_model_capability_disables_streaming_for_any_provider(
    monkeypatch,
) -> None:
    monkeypatch.setenv("UAGENT_RESPONSES", "0")
    monkeypatch.setenv("UAGENT_STREAMING", "1")

    def lookup(feature: str, *_args):
        if feature == "streaming":
            return False
        return None

    resolver = CapabilityResolver(feature_lookup=lookup)

    assert _resolve_round_runtime_flags(
        tr_cfg=None,
        core=_core(),
        provider="foundry_local",
        depname="phi-4-mini",
        capability_resolver=resolver,
    ) == (False, False)
