from types import SimpleNamespace

from uagent.cli_impl.main import (
    _auto_initial_round_completed,
    _exit_code_for_round_outcome,
    _set_status_for_command_result,
)
from uagent.uagent_llm import _public_round_status


def test_auto_initial_round_accepts_only_completed_outcome():
    assert _auto_initial_round_completed(
        SimpleNamespace(_last_round_outcome={"status": "completed"})
    )
    for status in ("failed", "cancelled", "interrupted", "continue", ""):
        assert not _auto_initial_round_completed(
            SimpleNamespace(_last_round_outcome={"status": status})
        )
    assert not _auto_initial_round_completed(SimpleNamespace(_last_round_outcome=None))
    assert not _auto_initial_round_completed(SimpleNamespace())


def test_run_llm_command_transitions_directly_to_busy_status():
    calls = []
    core = SimpleNamespace(set_status=lambda busy, label: calls.append((busy, label)))
    should_run_llm = _set_status_for_command_result(core, SimpleNamespace(run_llm=True))
    assert should_run_llm is True
    assert calls == [(True, "LLM")]


def test_non_llm_command_returns_to_idle_status():
    calls = []
    core = SimpleNamespace(set_status=lambda busy, label: calls.append((busy, label)))
    should_run_llm = _set_status_for_command_result(
        core, SimpleNamespace(run_llm=False)
    )
    assert should_run_llm is False
    assert calls == [(False, "")]


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


def test_startup_responses_continuation_uses_provider_capability():
    from uagent.cli_impl.main import _reset_startup_responses_continuation

    for provider in ("openai", "azure", "lmstudio", "meta"):
        core = SimpleNamespace(
            responses_state={
                "previous_response_id": "resp_old",
                "active_response_id": "resp_active",
                "keep": "value",
            }
        )

        _reset_startup_responses_continuation(core, provider, "model-a")

        assert core.responses_state == {
            "provider": provider,
            "model": "model-a",
            "keep": "value",
        }


def test_startup_responses_continuation_leaves_stateless_provider_untouched():
    from uagent.cli_impl.main import _reset_startup_responses_continuation

    for provider in ("openrouter", "foundry_local"):
        original = {
            "provider": "old-provider",
            "model": "old-model",
            "previous_response_id": "resp_old",
            "active_response_id": "resp_active",
        }
        core = SimpleNamespace(responses_state=dict(original))

        _reset_startup_responses_continuation(core, provider, "model-a")

        assert core.responses_state == original
