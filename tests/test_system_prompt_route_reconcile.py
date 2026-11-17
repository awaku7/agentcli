"""Route reconciliation for the session system prompt.

The system prompt is built once at session start, possibly from
environment-derived route values. These tests pin the round-entry
reconcile: when the round's actual route resolves to a different
prompt variant, the stored and outgoing system entries are swapped
(and a notice is printed); otherwise nothing changes.
"""

from __future__ import annotations

from types import SimpleNamespace

import uagent.core  # noqa: F401  (core first: core_impl.prompt imports it back)
from uagent.core_impl.prompt import (
    _base_system_prompt_for_mode,
    _strip_catalog_steering_text,
)
from uagent.llm_round_helpers import _reconcile_system_prompt_for_route

BASE = _base_system_prompt_for_mode()
STRIPPED = _strip_catalog_steering_text(BASE)

ROUTE = dict(provider="openai", depname="gpt-6-luna", use_responses_api=True)


def _core_returning(text):
    def refresh(*, provider=None, depname=None, use_responses_api=None):
        return text

    return SimpleNamespace(refresh_system_prompt=refresh)


def _messages(prompt_text):
    return [
        {"role": "system", "content": prompt_text},
        {"role": "system", "content": "long-term memory note"},
        {"role": "user", "content": "hi"},
    ]


def test_stale_full_prompt_swapped_for_native_route(capsys):
    call_messages = _messages(BASE)
    stored = _messages(BASE)
    result = _reconcile_system_prompt_for_route(
        call_messages, stored, _core_returning(STRIPPED), **ROUTE
    )
    assert result is True
    assert call_messages[0]["content"] == STRIPPED
    assert stored[0]["content"] == STRIPPED
    # Other system messages are never touched.
    assert call_messages[1]["content"] == "long-term memory note"
    out = capsys.readouterr().out
    assert "openai/gpt-6-luna" in out
    assert "removed" in out


def test_stale_stripped_prompt_restored_for_other_route(capsys):
    call_messages = _messages(STRIPPED)
    stored = _messages(STRIPPED)
    result = _reconcile_system_prompt_for_route(
        call_messages, stored, _core_returning(BASE), **ROUTE
    )
    assert result is True
    assert call_messages[0]["content"] == BASE
    assert stored[0]["content"] == BASE
    assert "restored" in capsys.readouterr().out


def test_matching_prompt_left_alone(capsys):
    call_messages = _messages(STRIPPED)
    result = _reconcile_system_prompt_for_route(
        call_messages, None, _core_returning(STRIPPED), **ROUTE
    )
    assert result is False
    assert call_messages[0]["content"] == STRIPPED
    assert capsys.readouterr().out == ""


def test_non_variant_system_entry_never_swapped():
    call_messages = [
        {"role": "system", "content": "operator role prompt"},
        {"role": "system", "content": BASE},
        {"role": "user", "content": "hi"},
    ]
    result = _reconcile_system_prompt_for_route(
        call_messages, None, _core_returning(STRIPPED), **ROUTE
    )
    assert result is True
    assert call_messages[0]["content"] == "operator role prompt"
    assert call_messages[1]["content"] == STRIPPED


def test_missing_refresh_is_a_noop():
    call_messages = _messages(BASE)
    result = _reconcile_system_prompt_for_route(
        call_messages, None, SimpleNamespace(), **ROUTE
    )
    assert result is False
    assert call_messages[0]["content"] == BASE


def test_refresh_failure_is_a_noop():
    def refresh(**_kwargs):
        raise RuntimeError("boom")

    call_messages = _messages(BASE)
    core = SimpleNamespace(refresh_system_prompt=refresh)
    result = _reconcile_system_prompt_for_route(call_messages, None, core, **ROUTE)
    assert result is False
    assert call_messages[0]["content"] == BASE
