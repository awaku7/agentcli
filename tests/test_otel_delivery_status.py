"""Private sender-status diagnostics independent of UAG Admin or OTLP networking."""

from __future__ import annotations

import json
import os
from pathlib import Path

from uagent.runtime.observability import delivery_status as delivery


def _isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(delivery, "get_state_dir", lambda: tmp_path)
    delivery._cleanup()
    monkeypatch.setattr(delivery, "_STATUS", None)


def test_disabled_and_sent_delivery_status_are_private(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    delivery.update_delivery_status("disabled", enabled=False)
    files = list((tmp_path / "otel_delivery").glob("*.json"))
    assert len(files) == 1
    status = delivery.local_delivery_statuses()
    assert len(status) == 1
    assert status[0]["enabled"] is False
    assert status[0]["state"] == "disabled"

    delivery.update_delivery_status("awaiting_export")
    delivery.update_delivery_status("failed")
    failed = delivery.local_delivery_statuses()[0]
    assert failed["enabled"] is True
    assert failed["state"] == "failed"
    assert failed["last_failure_at"] is not None
    delivery.update_delivery_status("retry_cooldown")
    assert delivery.local_delivery_statuses()[0]["last_success_at"] is None
    delivery.update_delivery_status("sent")
    sent = delivery.local_delivery_statuses()[0]
    assert sent["state"] == "sent"
    assert sent["last_success_at"] is not None
    assert sent["last_failure_at"] is not None
    assert frozenset(sent) == frozenset(
        {
            "version",
            "pid",
            "create_time",
            "enabled",
            "state",
            "updated_at",
            "last_attempt_at",
            "last_success_at",
            "last_failure_at",
        }
    )
    assert "Bearer" not in files[0].read_text(encoding="utf-8")
    if os.name != "nt":
        assert (tmp_path / "otel_delivery").stat().st_mode & 0o077 == 0
        assert files[0].stat().st_mode & 0o077 == 0
    delivery._cleanup()
    assert delivery.local_delivery_statuses() == []


def test_no_status_directory_when_only_reading(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    assert delivery.local_delivery_statuses() == []
    assert not (tmp_path / "otel_delivery").exists()


def test_status_read_ignores_stale_and_untrusted_files(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    delivery.update_delivery_status("sent")
    directory = tmp_path / "otel_delivery"
    record = delivery.local_delivery_statuses()[0]
    other = directory / "999999-1700000000000000.json"
    other.write_text(json.dumps({**record, "pid": 999999, "create_time": 1700000000}))
    assert len(delivery.local_delivery_statuses()) == 1

    record_path = next(directory.glob(f"{os.getpid()}-*.json"))
    record_path.write_text(
        json.dumps({**record, "state": "sent", "secret": "sensitive"})
    )
    assert delivery.local_delivery_statuses() == []
    delivery._cleanup()


def test_status_write_rejects_symlink_directory(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    target = tmp_path / "elsewhere"
    target.mkdir()
    try:
        (tmp_path / "otel_delivery").symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError):
        return
    delivery.update_delivery_status("sent")
    assert list(target.iterdir()) == []


def test_exporter_status_callbacks_do_not_claim_skipped_batch_is_sent(monkeypatch):
    from enum import Enum
    from types import SimpleNamespace

    from uagent.runtime.observability import otel_backend

    class Result(Enum):
        SUCCESS = 1
        FAILURE = 2

    class Exporter:
        def __init__(self):
            self.calls = 0

        def export(self, batch):
            self.calls += 1
            if self.calls == 1:
                return Result.FAILURE
            return Result.SUCCESS

    tick = [0.0]
    monkeypatch.setattr(
        otel_backend, "time", SimpleNamespace(monotonic=lambda: tick[0])
    )
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
    tick[0] = 1.0
    # SDK sees SUCCESS to avoid retry, but the actual sender is in cooldown.
    assert wrapped.export([2]) is Result.SUCCESS
    assert events == ["failed", "retry_cooldown"]
    assert inner.calls == 1
    tick[0] = 30.0
    assert wrapped.export([3]) is Result.SUCCESS
    assert events == ["failed", "retry_cooldown", "sent"]
    assert inner.calls == 2
    wrapped.shutdown()


def test_sender_status_is_best_effort(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    def fail(*args, **kwargs):
        raise PermissionError("status storage unavailable")

    monkeypatch.setattr(delivery, "_save", fail)
    delivery.update_delivery_status("failed")
    assert not list(Path(tmp_path).glob("otel_delivery/*.json"))


def test_admin_otel_status_command_reads_only_local_processes(monkeypatch, tmp_path, capsys):
    from uagent import admin_pairing
    from uagent.runtime import runtime_init

    _isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(runtime_init, "decide_workdir", lambda **kwargs: None)
    monkeypatch.setattr(runtime_init, "apply_workdir", lambda decision: None)
    monkeypatch.setattr(runtime_init, "load_dotenv_custom", lambda: None)
    delivery.update_delivery_status("failed")
    assert admin_pairing.main(["otel-status"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert len(result["processes"]) == 1
    assert result["processes"][0]["state"] == "failed"
    delivery._cleanup()
