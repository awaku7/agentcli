from __future__ import annotations

from types import SimpleNamespace

from uagent.util_cmd_auto import _handle_cmd_auto, _sentinel_judgment


def _core() -> SimpleNamespace:
    return SimpleNamespace(
        auto_pilot_active=False,
        auto_pilot_exit_requested=False,
        auto_pilot_goal="",
        auto_pilot_max_rounds=10,
        auto_pilot_round=0,
    )


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


def test_sentinel_judgment_accepts_case_and_optional_brackets() -> None:
    assert _sentinel_judgment([{"role": "assistant", "content": " Auto_complete "}]) == "COMPLETE"
    assert _sentinel_judgment([{"role": "assistant", "content": "AUTO_CONTINUE"}]) == "CONTINUE"


def test_sentinel_judgment_rejects_extra_text() -> None:
    assert _sentinel_judgment(
        [{"role": "assistant", "content": "AUTO_COMPLETE now"}]
    ) is None
