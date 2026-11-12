"""Unit coverage for the opt-in CLI startup timeline."""

import pytest

from uagent.runtime import startup_timing


def test_checkpoint_emits_cumulative_and_delta(monkeypatch, capsys):
    monkeypatch.setenv("UAGENT_STARTUP_TIMING", "1")
    monkeypatch.setattr(startup_timing, "_STARTED", 10.0)
    monkeypatch.setattr(startup_timing, "_PREVIOUS", 11.0)
    monkeypatch.setattr(startup_timing, "_CLOCK", lambda: 13.0)

    startup_timing.checkpoint("sandbox_status_displayed")

    assert (
        capsys.readouterr().err
        == "[startup-timing] timeline.sandbox_status_displayed=3.000s "
        "delta=2.000s\n"
    )


def test_checkpoint_silent_when_disabled(monkeypatch, capsys):
    monkeypatch.setenv("UAGENT_STARTUP_TIMING", "0")
    monkeypatch.setattr(startup_timing, "_PREVIOUS", 7.0)
    monkeypatch.setattr(startup_timing, "_CLOCK", lambda: 9.0)

    startup_timing.checkpoint("provider_ready")

    assert capsys.readouterr().err == ""
    assert startup_timing._PREVIOUS == 9.0


def test_checkpoint_uses_current_environment(monkeypatch, capsys):
    monkeypatch.setenv("UAGENT_STARTUP_TIMING", "off")
    monkeypatch.setattr(startup_timing, "_STARTED", 10.0)
    monkeypatch.setattr(startup_timing, "_PREVIOUS", 10.0)
    ticks = iter((11.0, 13.0))
    monkeypatch.setattr(startup_timing, "_CLOCK", lambda: next(ticks))

    startup_timing.checkpoint("before_dotenv")
    monkeypatch.setenv("UAGENT_STARTUP_TIMING", "on")
    startup_timing.checkpoint("after_dotenv")

    assert capsys.readouterr().err == (
        "[startup-timing] timeline.after_dotenv=3.000s delta=2.000s\n"
    )


def test_measure_detail_reports_elapsed_time(monkeypatch, capsys):
    monkeypatch.setenv("UAGENT_STARTUP_TIMING", "1")
    ticks = iter((10.0, 11.25))
    monkeypatch.setattr(startup_timing, "_CLOCK", lambda: next(ticks))

    with startup_timing.measure_detail("llmcapa.catalog_import"):
        pass

    assert capsys.readouterr().err == (
        "[startup-timing] detail.llmcapa.catalog_import=1.250s\n"
    )


def test_measure_detail_is_silent_when_disabled(monkeypatch, capsys):
    monkeypatch.setenv("UAGENT_STARTUP_TIMING", "0")
    monkeypatch.setattr(
        startup_timing,
        "_CLOCK",
        lambda: pytest.fail("clock must not be called when timing is disabled"),
    )

    with startup_timing.measure_detail("llmcapa.scoped_get"):
        pass

    assert capsys.readouterr().err == ""


def test_measure_detail_preserves_exceptions(monkeypatch, capsys):
    monkeypatch.setenv("UAGENT_STARTUP_TIMING", "1")
    ticks = iter((1.0, 2.0))
    monkeypatch.setattr(startup_timing, "_CLOCK", lambda: next(ticks))

    with pytest.raises(ValueError, match="original failure"):
        with startup_timing.measure_detail("llmcapa.prefix_search"):
            raise ValueError("original failure")

    assert capsys.readouterr().err == (
        "[startup-timing] detail.llmcapa.prefix_search=1.000s\n"
    )


def test_measure_detail_output_failure_does_not_change_behavior(monkeypatch):
    monkeypatch.setenv("UAGENT_STARTUP_TIMING", "1")

    def broken_diagnostic(*_args, **_kwargs):
        raise OSError("closed diagnostic pipe")

    monkeypatch.setattr(startup_timing, "print", broken_diagnostic, raising=False)

    with startup_timing.measure_detail("llmcapa.scoped_get"):
        value = 42
    assert value == 42

    with pytest.raises(ValueError, match="original failure"):
        with startup_timing.measure_detail("llmcapa.scoped_get"):
            raise ValueError("original failure")
