from __future__ import annotations

from types import SimpleNamespace

import pytest

from uagent.llm_round_helpers import _resolve_round_runtime_flags
from uagent.runtime.capability_resolver import CapabilityResolver


class _FailingResolver:
    def resolve(self, *args, **kwargs):
        raise RuntimeError("catalog unavailable")


def _core() -> SimpleNamespace:
    return SimpleNamespace(set_status=lambda *args: None)


def _resolve(monkeypatch: pytest.MonkeyPatch, resolver, *, provider="openai"):
    monkeypatch.delenv("UAGENT_RESPONSES", raising=False)
    monkeypatch.setenv("UAGENT_STREAMING", "0")
    return _resolve_round_runtime_flags(
        tr_cfg=None,
        core=_core(),
        provider=provider,
        depname="example-model",
        capability_resolver=resolver,
    )


def test_auto_selection_uses_resolver_true_evidence(monkeypatch) -> None:
    resolver = CapabilityResolver(
        feature_lookup=lambda feature, *_: feature == "responses_api"
    )

    assert _resolve(monkeypatch, resolver) == (True, False)


def test_auto_selection_uses_resolver_false_evidence(monkeypatch) -> None:
    resolver = CapabilityResolver(feature_lookup=lambda *_: False)

    assert _resolve(monkeypatch, resolver) == (False, False)


def test_auto_selection_unknown_fails_closed(monkeypatch) -> None:
    resolver = CapabilityResolver(feature_lookup=lambda *_: None)

    assert _resolve(monkeypatch, resolver) == (False, False)


def test_auto_selection_resolver_failure_fails_closed(monkeypatch) -> None:
    assert _resolve(monkeypatch, _FailingResolver()) == (False, False)


def test_explicit_responses_flag_respects_negative_capability(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_STREAMING", "0")
    monkeypatch.setenv("UAGENT_RESPONSES", "1")
    resolver = CapabilityResolver(
        feature_lookup=lambda feature, *_: False if feature == "responses_api" else None
    )

    assert _resolve_round_runtime_flags(
        tr_cfg=None,
        core=_core(),
        provider="openai",
        depname="example-model",
        capability_resolver=resolver,
    ) == (False, False)


def test_explicit_responses_flag_preserves_unknown_compatibility(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_STREAMING", "0")
    monkeypatch.setenv("UAGENT_RESPONSES", "1")

    assert _resolve_round_runtime_flags(
        tr_cfg=None,
        core=_core(),
        provider="openai",
        depname="unknown-model",
        capability_resolver=_FailingResolver(),
    ) == (True, False)

    monkeypatch.setenv("UAGENT_RESPONSES", "0")
    assert _resolve_round_runtime_flags(
        tr_cfg=None,
        core=_core(),
        provider="openai",
        depname="unknown-model",
        capability_resolver=_FailingResolver(),
    ) == (False, False)


def test_streaming_false_capability_disables_streaming_for_any_provider(
    monkeypatch,
) -> None:
    monkeypatch.setenv("UAGENT_RESPONSES", "0")
    monkeypatch.setenv("UAGENT_STREAMING", "1")
    resolver = CapabilityResolver(
        feature_lookup=lambda feature, *_: False if feature == "streaming" else None
    )

    assert _resolve_round_runtime_flags(
        tr_cfg=None,
        core=_core(),
        provider="openai",
        depname="example-model",
        capability_resolver=resolver,
    ) == (False, False)


def test_unknown_streaming_capability_preserves_requested_setting(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_RESPONSES", "0")
    monkeypatch.setenv("UAGENT_STREAMING", "1")

    assert _resolve_round_runtime_flags(
        tr_cfg=None,
        core=_core(),
        provider="openai",
        depname="unknown-model",
        capability_resolver=_FailingResolver(),
    ) == (False, True)
