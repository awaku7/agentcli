from types import SimpleNamespace

from uagent.cli_impl.main import _exit_code_for_round_outcome
from uagent.uagent_llm import _public_round_status


def test_public_round_status_marks_final_assistant_break_completed():
    assert (
        _public_round_status("break", reason="", assistant_text="done") == "completed"
    )


def test_public_round_status_keeps_loop_guard_failed():
    assert (
        _public_round_status("break", reason="loop_guard", assistant_text="")
        == "failed"
    )


def test_public_round_status_marks_continue_rounds():
    assert _public_round_status("ok", reason="", assistant_text="") == "continue"


def test_noninteractive_exit_code_maps_public_status():
    assert (
        _exit_code_for_round_outcome(
            SimpleNamespace(_last_round_outcome={"status": "completed"})
        )
        == 0
    )
    assert (
        _exit_code_for_round_outcome(
            SimpleNamespace(_last_round_outcome={"status": "failed"})
        )
        == 1
    )
    assert (
        _exit_code_for_round_outcome(
            SimpleNamespace(_last_round_outcome={"status": "interrupted"})
        )
        == 130
    )
