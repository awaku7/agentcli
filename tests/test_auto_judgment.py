from uagent.util_cmd_auto import _parse_reviewer_judgment


def test_complete_only_stops() -> None:
    assert _parse_reviewer_judgment("COMPLETE") == ("COMPLETE", "")
    assert _parse_reviewer_judgment("COMPLETE.") == ("COMPLETE", "")
    assert _parse_reviewer_judgment("The task is COMPLETE!") == ("COMPLETE", "")


def test_continue_only_continues() -> None:
    judgment, feedback = _parse_reviewer_judgment("CONTINUE: more work")
    assert judgment == "CONTINUE"
    assert feedback == "CONTINUE: more work"
    assert _parse_reviewer_judgment("CONTINUE.")[0] == "CONTINUE"


def test_continue_wins_when_both_tokens_are_present() -> None:
    judgment, _ = _parse_reviewer_judgment("COMPLETE\nCONTINUE: unresolved")
    assert judgment == "CONTINUE"


def test_missing_or_embedded_tokens_continue() -> None:
    assert _parse_reviewer_judgment("no decision") == ("CONTINUE", "no decision")
    assert _parse_reviewer_judgment("INCOMPLETE") == ("CONTINUE", "INCOMPLETE")
    assert _parse_reviewer_judgment("not COMPLETE") == ("CONTINUE", "not COMPLETE")


class _Core:
    auto_pilot_goal = "finish the task"

    def set_status(self, *_args) -> None:
        pass


def test_reviewer_judgment_integration_prefers_continue(monkeypatch) -> None:
    from uagent import uagent_llm
    from uagent.util_cmd_auto import _ask_reviewer_judgment

    monkeypatch.setattr(
        uagent_llm,
        "run_llm_rounds",
        lambda **_kwargs: "COMPLETE\nCONTINUE: unresolved",
    )
    judgment, feedback = _ask_reviewer_judgment(
        "provider",
        object(),
        "model",
        [{"role": "user", "content": "work"}],
        _Core(),
        make_client_fn=lambda _core: ("provider", object(), "model"),
    )
    assert judgment == "CONTINUE"
    assert "unresolved" in feedback


def test_reviewer_judgment_integration_stops_on_complete(monkeypatch) -> None:
    from uagent import uagent_llm
    from uagent.util_cmd_auto import _ask_reviewer_judgment

    monkeypatch.setattr(
        uagent_llm,
        "run_llm_rounds",
        lambda **_kwargs: "COMPLETE",
    )
    judgment, feedback = _ask_reviewer_judgment(
        "provider",
        object(),
        "model",
        [{"role": "user", "content": "work"}],
        _Core(),
        make_client_fn=lambda _core: ("provider", object(), "model"),
    )
    assert judgment == "COMPLETE"
    assert feedback == ""
