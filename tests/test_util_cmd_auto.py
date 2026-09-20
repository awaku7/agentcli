from __future__ import annotations

from types import SimpleNamespace

from uagent.util_cmd_auto import (
    _build_judgment_messages,
    _handle_cmd_auto,
    _parse_auto_goal_options,
    _sentinel_judgment,
)


def _core() -> SimpleNamespace:
    return SimpleNamespace(
        auto_pilot_active=False,
        auto_pilot_exit_requested=False,
        auto_pilot_goal="",
        auto_pilot_max_rounds=10,
        auto_pilot_round=0,
    )


def test_auto_parser_preserves_goal_text_and_apostrophes() -> None:
    goal = 'Do not change "quoted" text. Don\'t collapse lines.\nSecond line.'

    parsed_goal, rounds, infinite, error = _parse_auto_goal_options(
        goal + " --max-rounds 3"
    )

    assert parsed_goal == goal
    assert rounds == 3
    assert infinite is False
    assert error is None


def test_auto_parser_rejects_unbalanced_round_option_without_shlex() -> None:
    goal = "Don't do this --max-rounds 2"
    parsed_goal, rounds, infinite, error = _parse_auto_goal_options(goal)

    assert parsed_goal == "Don't do this"
    assert rounds == 2
    assert infinite is False
    assert error is None


def test_auto_infinite_prefix_sets_unbounded_mode() -> None:
    core = _core()

    result = _handle_cmd_auto(
        "INFINITE inspect the repository",
        [],
        None,
        "",
        core=core,
        tr=lambda text, **kwargs: text,
    )

    assert result.run_llm is True
    assert result.prompt == "inspect the repository"
    assert core.auto_pilot_max_rounds is None
    assert core.auto_pilot_active is True


def test_auto_infinite_flag_sets_unbounded_mode() -> None:
    core = _core()

    result = _handle_cmd_auto(
        "inspect the repository --infinite",
        [],
        None,
        "",
        core=core,
        tr=lambda text, **kwargs: text,
    )

    assert result.run_llm is True
    assert result.prompt == "inspect the repository"
    assert core.auto_pilot_max_rounds is None


def test_auto_max_rounds_infinite_alias_sets_unbounded_mode() -> None:
    core = _core()

    _handle_cmd_auto(
        "inspect the repository --max-rounds INFINITE",
        [],
        None,
        "",
        core=core,
        tr=lambda text, **kwargs: text,
    )

    assert core.auto_pilot_max_rounds is None


def test_auto_rejects_non_positive_max_rounds() -> None:
    core = _core()

    result = _handle_cmd_auto(
        "inspect the repository --max-rounds 0",
        [],
        None,
        "",
        core=core,
        tr=lambda text, **kwargs: text,
    )

    assert result.run_llm is False
    assert core.auto_pilot_active is False


def test_auto_keeps_numeric_max_rounds() -> None:
    core = _core()

    _handle_cmd_auto(
        "inspect the repository --max-rounds 25",
        [],
        None,
        "",
        core=core,
        tr=lambda text, **kwargs: text,
    )

    assert core.auto_pilot_max_rounds == 25


def test_auto_off_stops_infinite_mode() -> None:
    core = _core()
    core.auto_pilot_active = True
    core.auto_pilot_max_rounds = None

    result = _handle_cmd_auto(
        "off",
        [],
        None,
        "",
        core=core,
        tr=lambda text, **kwargs: text,
    )

    assert result.run_llm is False
    assert core.auto_pilot_active is False
    assert core.auto_pilot_exit_requested is False


def test_reviewer_judgment_includes_masked_tool_result_summaries() -> None:
    messages = [
        {"role": "user", "content": "inspect the result"},
        {
            "role": "tool",
            "name": "demo",
            "tool_call_id": "call-1",
            "content": '{"ok": true, "result": {"text": "token: secret-value"}}',
        },
    ]

    judgment = _build_judgment_messages(messages, "inspect the result")
    summary_messages = [
        item
        for item in judgment
        if item.get("role") == "user"
        and "Recent tool results" in str(item.get("content"))
    ]
    assert len(summary_messages) == 1
    content = str(summary_messages[0]["content"])
    assert "[TOOL-RESULT] tool=demo status=success call_id=call-1" in content
    assert "secret-value" not in content
    assert "********" in content


def test_reviewer_judgment_includes_failed_tool_status() -> None:
    judgment = _build_judgment_messages(
        [
            {
                "role": "tool",
                "name": "demo",
                "tool_call_id": "call-2",
                "content": '{"ok": false, "error": {"code": "NOPE", "message": "failed"}}',
            }
        ],
        "inspect",
    )
    content = "\n".join(str(item.get("content")) for item in judgment)
    assert "tool=demo status=failed call_id=call-2" in content
    assert "failed" in content


def test_sentinel_judgment_accepts_case_and_optional_brackets() -> None:
    assert (
        _sentinel_judgment([{"role": "assistant", "content": " Auto_complete "}])
        == "COMPLETE"
    )
    assert (
        _sentinel_judgment([{"role": "assistant", "content": "AUTO_CONTINUE"}])
        == "CONTINUE"
    )


def test_sentinel_judgment_rejects_extra_text() -> None:
    assert (
        _sentinel_judgment([{"role": "assistant", "content": "AUTO_COMPLETE now"}])
        is None
    )


def test_sentinel_judgment_continues_for_tool_call_only_response() -> None:
    assert (
        _sentinel_judgment(
            [
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{"id": "call-1", "type": "function"}],
                }
            ]
        )
        == "CONTINUE"
    )


def test_sentinel_judgment_does_not_use_older_marker_after_tool_call() -> None:
    assert (
        _sentinel_judgment(
            [
                {"role": "assistant", "content": "<AUTO_COMPLETE>"},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{"id": "call-1"}],
                },
            ]
        )
        == "CONTINUE"
    )


def test_reviewer_prompt_uses_configured_feedback_language(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_AUTO_REVIEW_LANGUAGE", "ja")

    judgment = _build_judgment_messages([], "inspect")
    system = str(judgment[0]["content"])

    assert "requested review language: ja" in system
    assert "Keep COMPLETE/CONTINUE unchanged" in system
