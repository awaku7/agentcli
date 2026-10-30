"""In-process read-only :otel command and exporter delivery state."""

from __future__ import annotations

from enum import Enum
from types import SimpleNamespace

from uagent.runtime.observability import delivery_status as delivery


def _reset(monkeypatch):
    monkeypatch.setattr(
        delivery,
        "_CURRENT",
        {
            "enabled": False,
            "state": "disabled",
            "last_attempt_utc": None,
            "last_success_utc": None,
            "last_failure_utc": None,
        },
    )


def test_delivery_state_reports_true_attempts_without_secrets(monkeypatch):
    _reset(monkeypatch)
    assert delivery.delivery_status_snapshot()["state"] == "disabled"

    delivery.update_delivery_status("awaiting_export")
    assert delivery.delivery_status_snapshot()["last_attempt_utc"] is None
    delivery.update_delivery_status("failed")
    failed = delivery.delivery_status_snapshot()
    assert failed["state"] == "failed"
    assert failed["enabled"] is True
    assert failed["last_failure_utc"] is not None
    delivery.update_delivery_status("retry_cooldown")
    assert delivery.delivery_status_snapshot()["last_success_utc"] is None
    delivery.update_delivery_status("sent")
    sent = delivery.delivery_status_snapshot()
    assert sent["last_success_utc"] is not None
    assert "Bearer" not in delivery.format_delivery_status()
    assert "http:" not in delivery.format_delivery_status()
    assert "Last success (UTC)" in delivery.format_delivery_status()
    delivery.update_delivery_status("disabled", enabled=False)
    disabled = delivery.delivery_status_snapshot()
    assert disabled["enabled"] is False
    assert disabled["last_failure_utc"] is None
    assert disabled["last_success_utc"] is None


def test_status_snapshot_cannot_mutate_underlying_state(monkeypatch):
    _reset(monkeypatch)
    copy = delivery.delivery_status_snapshot()
    copy["state"] = "sent"
    assert delivery.delivery_status_snapshot()["state"] == "disabled"
    delivery.update_delivery_status("made_up_state")
    assert delivery.delivery_status_snapshot()["state"] == "disabled"


def test_exporter_cooldown_is_not_misreported_as_sent(monkeypatch):
    from uagent.runtime.observability import otel_backend

    class Result(Enum):
        SUCCESS = 1
        FAILURE = 2

    class Exporter:
        def __init__(self):
            self.calls = 0

        def export(self, _batch):
            self.calls += 1
            if self.calls == 1:
                return Result.FAILURE
            return Result.SUCCESS

    now = [0.0]
    monkeypatch.setattr(otel_backend, "time", SimpleNamespace(monotonic=lambda: now[0]))
    events = []
    inner = Exporter()
    wrapped = otel_backend._FailStopExporter(
        inner,
        success_result=Result.SUCCESS,
        failure_result=Result.FAILURE,
        retry_interval=30.0,
        status_callback=events.append,
    )
    assert wrapped.export([1]) is Result.FAILURE
    now[0] = 1.0
    assert wrapped.export([2]) is Result.SUCCESS
    assert events == ["failed", "retry_cooldown"]
    assert inner.calls == 1
    now[0] = 30.0
    assert wrapped.export([3]) is Result.SUCCESS
    assert events == ["failed", "retry_cooldown", "sent"]
    assert inner.calls == 2
    wrapped.shutdown()


def test_colon_otel_command_is_read_only_even_in_sandbox(monkeypatch, capsys):
    from uagent.util_tools import handle_command

    _reset(monkeypatch)
    delivery.update_delivery_status("sent")
    core = SimpleNamespace(tr=lambda text: text, _sandbox_enabled=True)
    messages = [{"role": "user", "content": "unrelated"}]
    result = handle_command(":otel", messages, None, "", core=core)
    assert result is not False
    assert not getattr(result, "run_llm", False)
    assert messages == [{"role": "user", "content": "unrelated"}]
    output = capsys.readouterr().out
    assert "OTel: ON" in output
    assert "Delivery: sent" in output
    assert "Last success" in output


def test_colon_otel_uses_ui_translator_and_rejects_arguments(monkeypatch, capsys):
    from uagent.util_tools import handle_command

    _reset(monkeypatch)
    core = SimpleNamespace(tr=lambda msg: "TRANSLATED " + msg)
    assert handle_command(":otel", [], None, "", core=core) is not False
    output = capsys.readouterr().out
    assert "TRANSLATED Delivery: disabled" in output
    assert "TRANSLATED Local exporter observation;" in output
    assert handle_command(":otel --extra", [], None, "", core=core) is not False
    assert capsys.readouterr().out.strip() == "Usage: :otel"
