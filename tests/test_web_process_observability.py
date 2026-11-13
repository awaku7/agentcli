from __future__ import annotations

from types import SimpleNamespace

from uagent.runtime.observability import bootstrap, delivery_status
from uagent.web_impl import process_workers


def test_worker_observability_initializes_from_parent_snapshot(monkeypatch) -> None:
    settings = SimpleNamespace(enabled=True)
    initialized = []
    monkeypatch.setattr(
        bootstrap, "initialize_observability", lambda value: initialized.append(value)
    )

    assert process_workers._initialize_worker_observability(settings) is True
    assert initialized == [settings]
    assert process_workers._initialize_worker_observability(None) is False


def test_worker_shutdown_flushes_and_reports_status(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        bootstrap,
        "get_observability_backend",
        lambda: SimpleNamespace(shutdown=lambda: calls.append("shutdown")),
    )
    monkeypatch.setattr(
        delivery_status,
        "delivery_status_snapshot",
        lambda: {"enabled": True, "state": "sent"},
    )

    sent = []
    process_workers._finish_worker_observability(sent.append, initialized=True)

    assert calls == ["shutdown"]
    assert sent == [{"otel_status": {"enabled": True, "state": "sent"}}]


def test_child_delivery_status_is_mirrored_to_server(monkeypatch) -> None:
    updates = []
    monkeypatch.setattr(
        delivery_status,
        "update_delivery_status",
        lambda state, *, enabled=True: updates.append((state, enabled)),
    )

    process_workers._apply_worker_observability_status(
        {"state": "failed", "enabled": True}
    )
    process_workers._apply_worker_observability_status(
        {"state": "failed", "enabled": "yes"}
    )

    assert updates == [("failed", True)]
