# -*- coding: utf-8 -*-
"""Verify :shrink_llm / compress_history_with_llm after first success.

Focus:
- first compress produces exactly one history-summary system message
- second compress merges prior summary (no stacking)
- auto-shrink hysteresis avoids immediate re-trigger after a summary exists
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest import mock

import pytest

from uagent import core
from uagent import llm_message_helpers as lmh


class _FakeChoiceMsg:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeChoiceMsg(content)


class _FakeResp:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, contents: list[str]) -> None:
        self._contents = list(contents)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _FakeResp:
        self.calls.append(kwargs)
        if not self._contents:
            raise AssertionError("unexpected extra LLM call")
        return _FakeResp(self._contents.pop(0))


class _FakeChat:
    def __init__(self, contents: list[str]) -> None:
        self.completions = _FakeCompletions(contents)


class _FakeClient:
    def __init__(self, contents: list[str]) -> None:
        self.chat = _FakeChat(contents)


class _RejectTemperatureCompletions(_FakeCompletions):
    def create(self, **kwargs: Any) -> _FakeResp:
        self.calls.append(kwargs)
        if "temperature" in kwargs:
            raise RuntimeError(
                "Unsupported value: 'temperature' does not support 0.0; "
                "only the default (1) value is supported."
            )
        if not self._contents:
            raise AssertionError("unexpected extra LLM call")
        return _FakeResp(self._contents.pop(0))


class _RejectTemperatureClient:
    def __init__(self, contents: list[str]) -> None:
        self.chat = SimpleNamespace(completions=_RejectTemperatureCompletions(contents))


def _make_dialog(n_user: int = 6) -> list[dict[str, Any]]:
    msgs: list[dict[str, Any]] = [
        {"role": "system", "content": "SYSTEM_PROMPT"},
    ]
    for i in range(n_user):
        msgs.append({"role": "user", "content": f"user-{i} fact-{i}"})
        msgs.append({"role": "assistant", "content": f"assistant-{i} answer-{i}"})
    return msgs


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("UAGENT_PROVIDER", "openai")
    monkeypatch.delenv("UAGENT_RESPONSES", raising=False)
    monkeypatch.delenv("UAGENT_SHRINK_SINGLE_SHOT", raising=False)
    monkeypatch.setenv("UAGENT_SHRINK_CHUNK_SIZE", "50")
    monkeypatch.setattr(
        "uagent.providers.util_providers.detect_provider", lambda: "openai"
    )
    monkeypatch.setattr(core, "log_message", lambda m: None)
    yield


def test_history_summary_helpers_detect_and_strip():
    prefix = "Summary of the conversation so far:\n"
    body = "Decided to use X. Pending Y."
    msg = {"role": "system", "content": prefix + body}
    assert lmh._is_history_summary_message(msg) is True
    assert (
        lmh._is_history_summary_message({"role": "system", "content": "other"}) is False
    )
    assert lmh._strip_history_summary_prefix(prefix + body) == body
    assert lmh._messages_have_history_summary([msg]) is True
    assert lmh._messages_have_history_summary(_make_dialog(1)) is False


def test_compress_first_run_single_summary(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("UAGENT_LANG", "ja")
    msgs = _make_dialog(6)
    client = _FakeClient(["FIRST_SUMMARY about user-0..5"])

    out = core.compress_history_with_llm(
        client=client,
        depname="gpt-test",
        messages=msgs,
        keep_last=4,
        use_responses_api=False,
    )

    assert client.chat.completions.calls, "LLM should be called once"
    system_prompt = client.chat.completions.calls[0]["messages"][0]["content"]
    assert "in English" not in system_prompt
    assert "ja" in system_prompt
    summaries = [m for m in out if lmh._is_history_summary_message(m)]
    assert len(summaries) == 1
    assert "FIRST_SUMMARY" in summaries[0]["content"]
    assert out[0]["role"] == "system"
    assert out[0]["content"] == "SYSTEM_PROMPT"
    assert lmh._is_history_summary_message(out[1])
    others = out[2:]
    assert len(others) == 4


def test_compress_emit_log_false_is_quiet(capsys):
    client = _FakeClient(["QUIET_SUMMARY"])
    core.compress_history_with_llm(
        client=client,
        depname="gpt-test",
        messages=_make_dialog(3),
        keep_last=2,
        emit_log=False,
    )
    captured = capsys.readouterr()
    assert "shrink_llm" not in captured.out
    assert "shrink_llm" not in captured.err


def test_compress_retries_without_unsupported_temperature():
    msgs = _make_dialog(3)
    client = _RejectTemperatureClient(["SUMMARY_WITH_DEFAULT_TEMPERATURE"])

    out = core.compress_history_with_llm(
        client=client,
        depname="gpt-5-test",
        messages=msgs,
        keep_last=2,
        use_responses_api=False,
    )

    calls = client.chat.completions.calls
    assert len(calls) == 2
    assert calls[0]["temperature"] == 0.0
    assert "temperature" not in calls[1]
    assert any("SUMMARY_WITH_DEFAULT_TEMPERATURE" in m["content"] for m in out)


def test_compress_second_run_merges_prior_summary_no_stack():
    prefix = "Summary of the conversation so far:\n"
    msgs: list[dict[str, Any]] = [
        {"role": "system", "content": "SYSTEM_PROMPT"},
        {"role": "system", "content": prefix + "PRIOR_SUMMARY keep-me"},
        {"role": "user", "content": "new-user-a"},
        {"role": "assistant", "content": "new-asst-a"},
        {"role": "user", "content": "new-user-b"},
        {"role": "assistant", "content": "new-asst-b"},
        {"role": "user", "content": "new-user-c"},
        {"role": "assistant", "content": "new-asst-c"},
        {"role": "user", "content": "new-user-d"},
        {"role": "assistant", "content": "new-asst-d"},
    ]
    client = _FakeClient(["MERGED_SUMMARY prior+new"])

    out = core.compress_history_with_llm(
        client=client,
        depname="gpt-test",
        messages=msgs,
        keep_last=2,
        use_responses_api=False,
    )

    assert len(client.chat.completions.calls) == 1
    call = client.chat.completions.calls[0]
    sent = call["messages"]
    user_payload = sent[1]["content"]
    assert "PRIOR_SUMMARY keep-me" in user_payload

    summaries = [m for m in out if lmh._is_history_summary_message(m)]
    assert len(summaries) == 1, f"stacked summaries: {summaries!r}"
    assert "MERGED_SUMMARY" in summaries[0]["content"]
    system_after_lead = [m for m in out[1:] if m.get("role") == "system"]
    assert len(system_after_lead) == 1
    assert out[-2]["content"] == "new-user-d"
    assert out[-1]["content"] == "new-asst-d"


def test_compress_second_run_with_two_prior_summaries_folds_both():
    prefix = "Summary of the conversation so far:\n"
    msgs = [
        {"role": "system", "content": "SYSTEM_PROMPT"},
        {"role": "system", "content": prefix + "SUM_A"},
        {"role": "system", "content": prefix + "SUM_B"},
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "u2"},
        {"role": "assistant", "content": "a2"},
        {"role": "user", "content": "u3"},
        {"role": "assistant", "content": "a3"},
    ]
    client = _FakeClient(["SUM_AB_MERGED"])

    out = core.compress_history_with_llm(
        client=client,
        depname="gpt-test",
        messages=msgs,
        keep_last=2,
        use_responses_api=False,
    )
    user_payload = client.chat.completions.calls[0]["messages"][1]["content"]
    assert "SUM_A" in user_payload
    assert "SUM_B" in user_payload
    summaries = [m for m in out if lmh._is_history_summary_message(m)]
    assert len(summaries) == 1
    assert "SUM_AB_MERGED" in summaries[0]["content"]


def test_auto_shrink_hysteresis_skips_right_after_summary(
    monkeypatch: pytest.MonkeyPatch,
):
    prefix = "Summary of the conversation so far:\n"
    msgs = [
        {"role": "system", "content": "SYSTEM_PROMPT"},
        {"role": "system", "content": prefix + "already done"},
    ]
    for i in range(5):
        msgs.append({"role": "user", "content": f"u{i}"})
        msgs.append({"role": "assistant", "content": f"a{i}"})

    monkeypatch.setenv("UAGENT_SHRINK_KEEP_LAST", "5")
    monkeypatch.setenv("UAGENT_SHRINK_CNT", "6")
    monkeypatch.setenv("UAGENT_SHRINK_MAX_TOKENS", "0")

    called = {"n": 0}

    def _fake_compress(**kwargs):
        called["n"] += 1
        return list(kwargs["messages"])

    core_obj = SimpleNamespace(compress_history_with_llm=_fake_compress)

    out_cache = lmh._maybe_auto_shrink_messages(
        provider="openai",
        client=object(),
        depname="gpt-test",
        messages=msgs,
        core=core_obj,
        cache_mgr=SimpleNamespace(clear_cache=lambda c: None),
        gemini_cache_name=None,
        call_maybe_thread_fn=lambda fn: fn(),
        use_responses_api=False,
    )
    assert called["n"] == 0
    assert out_cache is None


def test_auto_shrink_hysteresis_fires_after_enough_growth(
    monkeypatch: pytest.MonkeyPatch,
):
    prefix = "Summary of the conversation so far:\n"
    msgs = [
        {"role": "system", "content": "SYSTEM_PROMPT"},
        {"role": "system", "content": prefix + "already done"},
    ]
    # Summary is treated as a leading system message for others_count, so only
    # dialog messages count. keep_last=5 -> re_cnt = max(10, 15) = 15.
    # Need others_count >= 15 dialog messages to re-trigger.
    for i in range(8):
        msgs.append({"role": "user", "content": f"u{i}"})
        msgs.append({"role": "assistant", "content": f"a{i}"})

    monkeypatch.setenv("UAGENT_SHRINK_KEEP_LAST", "5")
    monkeypatch.setenv("UAGENT_SHRINK_CNT", "6")
    monkeypatch.setenv("UAGENT_SHRINK_MAX_TOKENS", "0")

    called = {"n": 0}

    def _fake_compress(**kwargs):
        called["n"] += 1
        return [
            {"role": "system", "content": "SYSTEM_PROMPT"},
            {"role": "system", "content": prefix + "new"},
            {"role": "user", "content": "tail-u"},
            {"role": "assistant", "content": "tail-a"},
        ]

    core_obj = SimpleNamespace(
        compress_history_with_llm=_fake_compress,
        rewrite_current_log_from_messages=lambda m: None,
    )

    with mock.patch.object(lmh, "get_callbacks", return_value=SimpleNamespace()):
        lmh._maybe_auto_shrink_messages(
            provider="openai",
            client=object(),
            depname="gpt-test",
            messages=msgs,
            core=core_obj,
            cache_mgr=SimpleNamespace(clear_cache=lambda c: None),
            gemini_cache_name=None,
            call_maybe_thread_fn=lambda fn: fn(),
            use_responses_api=False,
        )
    assert called["n"] == 1
    assert lmh._messages_have_history_summary(msgs)
    assert any(m.get("content") == "tail-u" for m in msgs)


def test_auto_shrink_first_time_by_cnt(monkeypatch: pytest.MonkeyPatch):
    msgs = _make_dialog(5)
    monkeypatch.setenv("UAGENT_SHRINK_KEEP_LAST", "4")
    monkeypatch.setenv("UAGENT_SHRINK_CNT", "8")
    monkeypatch.setenv("UAGENT_SHRINK_MAX_TOKENS", "0")

    called = {"n": 0}

    def _fake_compress(**kwargs):
        called["n"] += 1
        return [
            {"role": "system", "content": "SYSTEM_PROMPT"},
            {
                "role": "system",
                "content": "Summary of the conversation so far:\nS",
            },
            {"role": "user", "content": "u"},
            {"role": "assistant", "content": "a"},
        ]

    core_obj = SimpleNamespace(
        compress_history_with_llm=_fake_compress,
        rewrite_current_log_from_messages=lambda m: None,
    )
    with mock.patch.object(lmh, "get_callbacks", return_value=SimpleNamespace()):
        lmh._maybe_auto_shrink_messages(
            provider="openai",
            client=object(),
            depname="gpt-test",
            messages=msgs,
            core=core_obj,
            cache_mgr=SimpleNamespace(clear_cache=lambda c: None),
            gemini_cache_name=None,
            call_maybe_thread_fn=lambda fn: fn(),
            use_responses_api=False,
        )
    assert called["n"] == 1


def test_manual_cmd_shrink_llm_uses_compress(monkeypatch: pytest.MonkeyPatch):
    from uagent import util_tools as ut

    msgs = _make_dialog(4)
    captured: dict[str, Any] = {}

    def _fake_compress(**kwargs):
        captured.update(kwargs)
        return [
            {"role": "system", "content": "SYSTEM_PROMPT"},
            {
                "role": "system",
                "content": "Summary of the conversation so far:\nM",
            },
            {"role": "user", "content": "tail"},
        ]

    core_obj = SimpleNamespace(
        compress_history_with_llm=_fake_compress,
        rewrite_current_log_from_messages=lambda m: None,
    )
    monkeypatch.setattr(ut, "_persist_messages_with_warn", lambda *a, **k: None)
    monkeypatch.setenv("UAGENT_PROVIDER", "openai")
    monkeypatch.delenv("UAGENT_RESPONSES", raising=False)

    ok = ut._handle_cmd_shrink_llm(
        "3",
        msgs,
        client=object(),
        depname="gpt-test",
        core=core_obj,
    )
    assert ok is True
    assert captured.get("keep_last") == 3
    assert lmh._messages_have_history_summary(msgs)
    assert msgs[-1]["content"] == "tail"
