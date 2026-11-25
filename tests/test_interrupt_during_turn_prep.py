"""A Stop/F12 pressed while a turn is being prepared must stop the turn (INT-01).

run_llm_rounds used to clear the interrupt flag *after* the per-turn
preparation, so an interrupt raised during preparation was dropped and the
LLM call ran to completion.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import uagent.uagent_llm as llm


def _core(**extra) -> SimpleNamespace:
    return SimpleNamespace(
        responses_state={},
        set_status=lambda *_args, **_kwargs: None,
        memory_projection_snapshot=None,
        log_message=lambda *_args, **_kwargs: None,
        **extra,
    )


def _run(core, messages) -> None:
    llm.run_llm_rounds(
        "openai",
        object(),
        "test-model",
        messages,
        core=core,
        make_client_fn=lambda *_a: None,
        append_result_to_outfile_fn=lambda *_a, **_k: None,
        try_open_images_from_text_fn=lambda *_a, **_k: None,
    )


@pytest.fixture
def no_llm(monkeypatch):
    """Stub everything around the round so only the interrupt logic runs."""

    def must_not_dispatch(*_args, **_kwargs):
        raise AssertionError("the LLM must not be called after Stop")

    monkeypatch.setattr(llm, "_dispatch_round", must_not_dispatch)
    monkeypatch.setattr(llm, "_execute_round_tools", must_not_dispatch)
    monkeypatch.setattr(llm, "memory_projection_access_is_current", lambda *_a: True)
    monkeypatch.setattr(llm, "_refresh_context_tool_specs", lambda *_a: None)
    monkeypatch.setattr(llm, "_init_gemini_cache", lambda **_k: (None, None))
    monkeypatch.setattr(llm, "_spinner_stop_quietly", lambda: None)
    monkeypatch.setattr(llm._core_module, "interrupt_requested", False)


def test_interrupt_raised_during_turn_prep_stops_before_the_llm_call(
    monkeypatch, no_llm
) -> None:
    def prep_with_stop(messages, core):
        # F12 / Web Stop arrives while memory/context/tools are prepared.
        with llm._core_module.interrupt_lock:
            llm._core_module.interrupt_requested = True

    monkeypatch.setattr(llm, "_prepare_turn_context", prep_with_stop)
    core = _core()
    messages = [{"role": "user", "content": "hello"}]

    _run(core, messages)

    assert core._last_round_reason == "interrupted"
    assert llm._core_module.interrupt_requested is False  # consumed once
    assert not any(m.get("role") == "assistant" for m in messages)


def test_stale_interrupt_from_before_the_turn_is_still_dropped(
    monkeypatch, no_llm
) -> None:
    rounds: list[bool] = []

    def fake_round(**kwargs):
        rounds.append(bool(llm._core_module.interrupt_requested))
        return llm._RoundOutcome(
            status=llm._RS_BREAK,
            client=kwargs["client"],
            gemini_cache_name=None,
            empty_no_tool_rounds=0,
            assistant_text="done",
        )

    monkeypatch.setattr(llm, "_prepare_turn_context", lambda *_a: None)
    monkeypatch.setattr(llm, "_run_one_round", fake_round)
    # Left over from an earlier turn, before run_llm_rounds starts.
    monkeypatch.setattr(llm._core_module, "interrupt_requested", True)

    _run(_core(), [{"role": "user", "content": "hello"}])

    assert rounds == [False]


def test_pending_interrupt_skips_computer_use_direct_navigation(
    monkeypatch, no_llm
) -> None:
    import uagent.computer_use.integration as integration
    import uagent.computer_use.native as native

    navigated: list[bool] = []

    def prep_with_stop(messages, core):
        with llm._core_module.interrupt_lock:
            llm._core_module.interrupt_requested = True

    monkeypatch.setattr(llm, "_prepare_turn_context", prep_with_stop)
    monkeypatch.setattr(
        llm, "_computer_use_enabled_for_current_execution", lambda *_a: True
    )
    monkeypatch.setattr(
        llm,
        "_maybe_navigate_computer_runtime",
        lambda *_a: navigated.append(True) or True,
    )
    monkeypatch.setattr(integration, "install_computer_use_handler", lambda **_k: None)
    monkeypatch.setattr(native, "prepare_native_computer_use", lambda **_k: None)
    core = _core(
        get_computer_use_policy=lambda: SimpleNamespace(),
        # An existing runtime whose page is open: no new runtime is created.
        computer_use_runtime=SimpleNamespace(page=None),
    )

    _run(core, [{"role": "user", "content": "open https://example.com"}])

    assert navigated == []
    assert core._last_round_reason == "interrupted"
