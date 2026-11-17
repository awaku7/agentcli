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


class _CapturedDispatch(Exception):
    """Raised by the fake dispatcher to stop the round at dispatch time."""


def _drive_round_to_dispatch(monkeypatch, messages, *, transform=None):
    """Drive _run_one_round to dispatch with a capturing dispatcher.

    Returns the call_messages the dispatcher received. The round is
    stopped at dispatch by raising _CapturedDispatch.
    """
    import pytest

    import uagent.runtime.provider_round_dispatcher as dispatcher_module
    import uagent.uagent_llm as llm

    seen: dict[str, object] = {}

    def fake_dispatch(**kwargs):
        seen["call_messages"] = kwargs["registry_kwargs"]["call_messages"]
        raise _CapturedDispatch

    core = SimpleNamespace(
        responses_state={},
        responses_runtime=SimpleNamespace(clear_continuation=lambda _reason: None),
        memory_projection_snapshot=None,
        refresh_system_prompt=lambda **_kwargs: STRIPPED,
    )

    monkeypatch.setattr(llm._core_module, "interrupt_requested", False)
    monkeypatch.setattr(llm, "load_translate_config", lambda: None)
    monkeypatch.setattr(llm, "memory_projection_access_is_current", lambda *_: True)
    monkeypatch.setattr(
        llm,
        "_build_call_messages",
        lambda **_: [dict(message) for message in messages],
    )
    monkeypatch.setattr(llm, "apply_memory_projection", lambda m, *_: m)
    monkeypatch.setattr(llm, "_resolve_round_runtime_flags", lambda **_: (True, False))
    monkeypatch.setattr(
        llm.RoundTransportSelection,
        "from_flags",
        staticmethod(
            lambda **_: SimpleNamespace(
                use_responses_api=True,
                stream_responses=False,
            )
        ),
    )
    monkeypatch.setattr(
        llm, "build_structured_auto_shrink_projection", lambda **_: None
    )
    monkeypatch.setattr(
        llm,
        "build_auto_shrink_projection",
        lambda **_: SimpleNamespace(changed=False),
    )
    monkeypatch.setattr(llm, "_record_round_context_plan", lambda **_: None)
    monkeypatch.setattr(
        llm,
        "_apply_semantic_message_transforms",
        transform if transform is not None else (lambda msgs, _: msgs),
    )
    monkeypatch.setattr(llm, "project_messages_for_provider", lambda msgs, **_: msgs)
    monkeypatch.setattr(llm, "_begin_responses_runtime", lambda **_: None)
    monkeypatch.setattr(
        llm, "plan_provider_cache", lambda **_: SimpleNamespace(to_dict=lambda: {})
    )
    monkeypatch.setattr(dispatcher_module, "dispatch_provider_round", fake_dispatch)

    with pytest.raises(_CapturedDispatch):
        llm._run_one_round(
            "openai",
            None,
            "gpt-6-luna",
            messages,
            core=core,
            make_client_fn=lambda: None,
            append_result_to_outfile_fn=lambda *_: None,
            try_open_images_from_text_fn=lambda *_: None,
            round_count=1,
            max_tool_rounds=3,
            empty_no_tool_rounds=0,
            empty_no_tool_max=2,
            cache_mgr=None,
            gemini_cache_name=None,
            use_llm_thread=False,
        )

    return seen["call_messages"]


def test_registry_round_receives_reconciled_prompt(monkeypatch, capsys):
    """The reconcile must run before provider dispatch.

    The default-on registry runner returns before the OpenAI-compatible
    fallback is invoked, so a hook inside the fallback never sees those
    rounds. Drive _run_one_round with a capturing dispatcher and check
    the messages it receives already carry the reconciled prompt.
    """
    messages = _messages(BASE)
    dispatched = _drive_round_to_dispatch(monkeypatch, messages)
    assert dispatched[0]["content"] == STRIPPED
    assert messages[0]["content"] == STRIPPED
    assert "removed" in capsys.readouterr().out


def test_reconcile_runs_before_semantic_translation(monkeypatch, capsys):
    """A translating semantic transform must not hide the stale prompt.

    With translation on, the semantic transform rewrites the system
    entry's text, so a reconcile after it would no longer recognize
    the entry: the outgoing copy would keep the stale guidance while
    the stored copy is swapped and the notice printed anyway. The
    reconcile therefore runs before the transform, and the dispatched
    entry carries the reconciled text (plus the translation marker).
    """

    def translating_transform(msgs, _cfg):
        return [
            (
                {**message, "content": message["content"] + " [T]"}
                if message.get("role") == "system"
                else message
            )
            for message in msgs
        ]

    messages = _messages(BASE)
    dispatched = _drive_round_to_dispatch(
        monkeypatch, messages, transform=translating_transform
    )
    assert dispatched[0]["content"] == STRIPPED + " [T]"
    assert "tool_catalog" not in dispatched[0]["content"]
    assert messages[0]["content"] == STRIPPED
    assert "removed" in capsys.readouterr().out
