from uagent.util_cmd_auto import _parse_reviewer_judgment


def test_complete_only_stops() -> None:
    assert _parse_reviewer_judgment("COMPLETE") == ("COMPLETE", "")


def test_continue_only_continues() -> None:
    judgment, feedback = _parse_reviewer_judgment("CONTINUE: more work")
    assert judgment == "CONTINUE"
    assert feedback == "CONTINUE: more work"


def test_continue_wins_when_both_tokens_are_present() -> None:
    judgment, _ = _parse_reviewer_judgment("COMPLETE\nCONTINUE: unresolved")
    assert judgment == "CONTINUE"


def test_missing_or_embedded_tokens_continue() -> None:
    assert _parse_reviewer_judgment("no decision") == ("CONTINUE", "no decision")
    assert _parse_reviewer_judgment("INCOMPLETE") == ("CONTINUE", "INCOMPLETE")
    assert _parse_reviewer_judgment("not COMPLETE") == ("CONTINUE", "not COMPLETE")
