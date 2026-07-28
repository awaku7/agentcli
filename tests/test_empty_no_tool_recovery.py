"""Tests for empty assistant / no-tool recovery helpers."""

from __future__ import annotations

from typing import Any

import pytest

from uagent.llm_flow_helpers import (
    _consume_empty_no_tool_recovery,
    _default_empty_no_tool_max,
    _drop_trailing_empty_assistant,
    _handle_openai_empty_no_tool,
    _resolve_empty_no_tool_max,
    _should_keep_assistant_message,
)


class _CoreStub:
    def __init__(self) -> None:
        self.logged: list[dict[str, Any]] = []
        self._empty_no_tool_recovery_pending = False

    def log_message(self, message: dict[str, Any]) -> None:
        self.logged.append(message)


class TestDefaultEmptyNoToolMax:
    def test_grok_and_xai_higher(self) -> None:
        assert _default_empty_no_tool_max("grok") == 5
        assert _default_empty_no_tool_max("xai") == 5
        assert _default_empty_no_tool_max("GROK") == 5

    def test_others_default_two(self) -> None:
        assert _default_empty_no_tool_max("openai") == 2
        assert _default_empty_no_tool_max("claude") == 2
        assert _default_empty_no_tool_max("") == 2


class TestResolveEmptyNoToolMax:
    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("UAGENT_EMPTY_NO_TOOL_MAX", "7")
        assert _resolve_empty_no_tool_max("grok") == 7
        assert _resolve_empty_no_tool_max("openai") == 7

    def test_env_empty_uses_provider_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("UAGENT_EMPTY_NO_TOOL_MAX", raising=False)
        assert _resolve_empty_no_tool_max("grok") == 5
        assert _resolve_empty_no_tool_max("openai") == 2

    def test_invalid_env_falls_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("UAGENT_EMPTY_NO_TOOL_MAX", "nope")
        assert _resolve_empty_no_tool_max("grok") == 5
        monkeypatch.setenv("UAGENT_EMPTY_NO_TOOL_MAX", "-1")
        assert _resolve_empty_no_tool_max("openai") == 2


class TestDropTrailingEmptyAssistant:
    def test_drops_empty_assistant(self) -> None:
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": ""},
        ]
        assert _drop_trailing_empty_assistant(messages) is True
        assert messages == [{"role": "user", "content": "hi"}]

    def test_keeps_tool_call_assistant(self) -> None:
        messages: list[dict[str, Any]] = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "1", "function": {"name": "x", "arguments": "{}"}}
                ],
            }
        ]
        assert _drop_trailing_empty_assistant(messages) is False
        assert len(messages) == 1

    def test_keeps_non_empty(self) -> None:
        messages: list[dict[str, Any]] = [
            {"role": "assistant", "content": "hello"},
        ]
        assert _drop_trailing_empty_assistant(messages) is False
        assert messages[0]["content"] == "hello"


class TestShouldKeepAssistantMessage:
    def test_empty_without_tools_dropped(self) -> None:
        assert _should_keep_assistant_message("", []) is False
        assert _should_keep_assistant_message("   ", None) is False

    def test_tools_or_text_kept(self) -> None:
        assert _should_keep_assistant_message("", [{"id": "1"}]) is True
        assert _should_keep_assistant_message("hi", []) is True


class TestHandleOpenAIEmptyNoTool:
    def test_nudge_and_drop_empty_on_first_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("UAGENT_EMPTY_NO_TOOL_NUDGE", "1")
        monkeypatch.delenv("UAGENT_EMPTY_NO_TOOL_RECOVERY", raising=False)
        core = _CoreStub()
        messages: list[dict[str, Any]] = [
            {"role": "tool", "content": "tool-result"},
            {"role": "assistant", "content": ""},
        ]
        action, rounds = _handle_openai_empty_no_tool(
            assistant_text="",
            tool_calls_list=[],
            empty_no_tool_rounds=0,
            empty_no_tool_max=2,
            provider="grok",
            depname="grok-4.5",
            messages=messages,
            core=core,
        )
        assert action == "continue"
        assert rounds == 1
        assert messages[0]["role"] == "tool"
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"].strip()
        assert not any(
            m.get("role") == "assistant" and not (m.get("content") or "").strip()
            for m in messages
        )

    def test_warn_break_defers_recovery_and_logs_ui_only(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("UAGENT_EMPTY_NO_TOOL_NUDGE", "1")
        monkeypatch.setenv("UAGENT_EMPTY_NO_TOOL_RECOVERY", "1")
        core = _CoreStub()
        messages: list[dict[str, Any]] = [
            {"role": "tool", "content": "tool-result"},
            {"role": "assistant", "content": "   "},
        ]
        action, rounds = _handle_openai_empty_no_tool(
            assistant_text="   ",
            tool_calls_list=[],
            empty_no_tool_rounds=2,
            empty_no_tool_max=2,
            provider="grok",
            depname="grok-4.5",
            messages=messages,
            core=core,
        )
        assert action == "break"
        assert rounds == 3
        # no empty/warn assistant left in model history
        assert all(m.get("role") != "assistant" for m in messages)
        # recovery is deferred, not appended immediately
        assert messages[-1]["role"] == "tool"
        assert core._empty_no_tool_recovery_pending is True
        err = capsys.readouterr().err
        assert "[WARN] LLM returned an empty assistant message" in err
        assert any(
            m.get("role") == "assistant"
            and m.get("_uagent_ui_only")
            and "[WARN]" in str(m.get("content") or "")
            for m in core.logged
        )

    def test_tool_calls_pass_resets(self) -> None:
        core = _CoreStub()
        messages: list[dict[str, Any]] = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "1", "function": {"name": "x", "arguments": "{}"}}
                ],
            }
        ]
        action, rounds = _handle_openai_empty_no_tool(
            assistant_text="",
            tool_calls_list=messages[0]["tool_calls"],
            empty_no_tool_rounds=3,
            empty_no_tool_max=2,
            provider="grok",
            depname="grok-4.5",
            messages=messages,
            core=core,
        )
        assert action == "pass"
        assert rounds == 0
        assert len(messages) == 1


class TestConsumeEmptyNoToolRecovery:
    def test_merges_into_latest_real_user(self) -> None:
        core = _CoreStub()
        core._empty_no_tool_recovery_pending = True
        messages: list[dict[str, Any]] = [
            {"role": "tool", "content": "result"},
            {"role": "user", "content": "続けて"},
        ]
        assert _consume_empty_no_tool_recovery(messages=messages, core=core) is True
        assert core._empty_no_tool_recovery_pending is False
        assert messages[-1]["role"] == "user"
        assert "続けて" in messages[-1]["content"]
        assert messages[-1]["content"].strip() != "続けて"
        # only one user message
        assert sum(1 for m in messages if m.get("role") == "user") == 1

    def test_no_stack_on_repeated_consume(self) -> None:
        core = _CoreStub()
        core._empty_no_tool_recovery_pending = True
        messages: list[dict[str, Any]] = [{"role": "user", "content": "続けて"}]
        assert _consume_empty_no_tool_recovery(messages=messages, core=core) is True
        # second consume with flag already cleared does nothing
        assert _consume_empty_no_tool_recovery(messages=messages, core=core) is False
        assert sum(1 for m in messages if m.get("role") == "user") == 1

    def test_repeated_warn_then_continue_does_not_stack_users(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("UAGENT_EMPTY_NO_TOOL_RECOVERY", "1")
        core = _CoreStub()
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": "task"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "1", "function": {"name": "x", "arguments": "{}"}}
                ],
            },
            {"role": "tool", "tool_call_id": "1", "content": "result"},
            {"role": "assistant", "content": ""},
        ]
        _handle_openai_empty_no_tool(
            assistant_text="",
            tool_calls_list=[],
            empty_no_tool_rounds=5,
            empty_no_tool_max=5,
            provider="grok",
            depname="g",
            messages=messages,
            core=core,
        )
        messages.append({"role": "user", "content": "続けて"})
        _consume_empty_no_tool_recovery(messages=messages, core=core)
        # second empty warn
        messages.append({"role": "assistant", "content": ""})
        _handle_openai_empty_no_tool(
            assistant_text="",
            tool_calls_list=[],
            empty_no_tool_rounds=5,
            empty_no_tool_max=5,
            provider="grok",
            depname="g",
            messages=messages,
            core=core,
        )
        messages.append({"role": "user", "content": "続けて"})
        _consume_empty_no_tool_recovery(messages=messages, core=core)
        user_msgs = [m for m in messages if m.get("role") == "user"]
        # original task + two real continue turns (recovery merged, not extra users)
        assert len(user_msgs) == 3
        assert not any(m.get("_uagent_internal") for m in user_msgs)
