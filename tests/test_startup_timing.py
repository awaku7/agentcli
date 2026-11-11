"""Unit coverage for the opt-in CLI startup timeline."""

from uagent.runtime import startup_timing


def test_checkpoint_emits_cumulative_and_delta(monkeypatch, capsys):
    monkeypatch.setenv("UAGENT_STARTUP_TIMING", "1")
    monkeypatch.setattr(startup_timing, "_STARTED", 10.0)
    monkeypatch.setattr(startup_timing, "_PREVIOUS", 11.0)
    monkeypatch.setattr(startup_timing.time, "perf_counter", lambda: 13.0)

    startup_timing.checkpoint("sandbox_status_displayed")

    assert (
        capsys.readouterr().err
        == "[startup-timing] timeline.sandbox_status_displayed=3.000s "
        "delta=2.000s\n"
    )


def test_checkpoint_silent_when_disabled(monkeypatch, capsys):
    monkeypatch.setenv("UAGENT_STARTUP_TIMING", "0")
    monkeypatch.setattr(startup_timing, "_PREVIOUS", 7.0)
    monkeypatch.setattr(startup_timing.time, "perf_counter", lambda: 9.0)

    startup_timing.checkpoint("provider_ready")

    assert capsys.readouterr().err == ""
    assert startup_timing._PREVIOUS == 9.0


def test_checkpoint_uses_current_environment(monkeypatch, capsys):
    monkeypatch.setenv("UAGENT_STARTUP_TIMING", "off")
    monkeypatch.setattr(startup_timing, "_STARTED", 10.0)
    monkeypatch.setattr(startup_timing, "_PREVIOUS", 10.0)
    ticks = iter((11.0, 13.0))
    monkeypatch.setattr(startup_timing.time, "perf_counter", lambda: next(ticks))

    startup_timing.checkpoint("before_dotenv")
    monkeypatch.setenv("UAGENT_STARTUP_TIMING", "on")
    startup_timing.checkpoint("after_dotenv")

    assert capsys.readouterr().err == (
        "[startup-timing] timeline.after_dotenv=3.000s delta=2.000s\n"
    )
