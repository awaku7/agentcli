"""Regression coverage for explicit UAG Admin pairing export."""

from __future__ import annotations

import json
import os

import pytest

from uagent import admin_pairing


def _set_state(monkeypatch, tmp_path):
    state = tmp_path / "private-state"
    monkeypatch.setenv("UAGENT_STATE_DIR", str(state))
    for name in (
        "UAGENT_INSTANCE_ID",
        "UAGENT_MANAGEMENT_API_TOKEN",
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
        "OTEL_EXPORTER_OTLP_TRACES_HEADERS",
    ):
        monkeypatch.delenv(name, raising=False)
    return state


def test_export_persists_identity_and_distinct_tokens(monkeypatch, tmp_path):
    state = _set_state(monkeypatch, tmp_path)
    first = tmp_path / "transfer-1.json"
    second = tmp_path / "transfer-2.json"
    admin_pairing.export_pairing(
        uag_url="http://127.0.0.1:8000",
        admin_url="http://127.0.0.1:8088",
        output=first,
    )
    admin_pairing.export_pairing(
        uag_url="http://127.0.0.1:8000",
        admin_url="http://127.0.0.1:8088",
        output=second,
    )
    a, b = json.loads(first.read_text()), json.loads(second.read_text())
    assert a == b
    assert a["manifest_bearer"] != a["otlp_bearer"]
    assert a["instance_id"] == (state / "instance_id").read_text().strip()
    assert admin_pairing.get_manifest_pairing_token() == a["manifest_bearer"]
    assert admin_pairing.get_otlp_pairing() == (
        "http://127.0.0.1:8088/otlp/v1/traces",
        a["otlp_bearer"],
    )


def test_export_refuses_unsafe_urls_and_existing_output(monkeypatch, tmp_path):
    _set_state(monkeypatch, tmp_path)
    target = tmp_path / "transfer.json"
    with pytest.raises(ValueError, match="HTTPS"):
        admin_pairing.export_pairing(
            uag_url="http://192.0.2.1:8000",
            admin_url="https://admin.example.com",
            output=target,
        )
    assert not target.exists()
    admin_pairing.export_pairing(
        uag_url="https://uag.example.com",
        admin_url="https://admin.example.com",
        output=target,
    )
    with pytest.raises(FileExistsError):
        admin_pairing.export_pairing(
            uag_url="https://uag.example.com",
            admin_url="https://admin.example.com",
            output=target,
        )
    with pytest.raises(ValueError, match="URLs changed"):
        admin_pairing.export_pairing(
            uag_url="https://another.example.com",
            admin_url="https://admin.example.com",
            output=tmp_path / "wrong.json",
        )


def test_conflicting_preexisting_manifest_token_is_rejected(monkeypatch, tmp_path):
    _set_state(monkeypatch, tmp_path)
    admin_pairing.export_pairing(
        uag_url="http://localhost:8000",
        admin_url="http://localhost:8088",
        output=tmp_path / "first.json",
    )
    monkeypatch.setenv("UAGENT_MANAGEMENT_API_TOKEN", "X" * 50)
    with pytest.raises(ValueError, match="conflicts"):
        admin_pairing.export_pairing(
            uag_url="http://localhost:8000",
            admin_url="http://localhost:8088",
            output=tmp_path / "second.json",
        )


def test_pairing_secret_file_must_be_private_on_posix(monkeypatch, tmp_path):
    state = _set_state(monkeypatch, tmp_path)
    admin_pairing.export_pairing(
        uag_url="http://localhost:8000",
        admin_url="http://localhost:8088",
        output=tmp_path / "first.json",
    )
    stored = state / "admin_pairing_credentials.json"
    if os.name != "nt":
        assert stored.stat().st_mode & 0o077 == 0
        stored.chmod(0o644)
        with pytest.raises(PermissionError):
            admin_pairing.load_pairing()


def test_file_creation_error_leaves_no_runtime_secret(monkeypatch, tmp_path):
    state = _set_state(monkeypatch, tmp_path)
    out = tmp_path / "transfer.json"
    out.write_text("existing", encoding="utf-8")
    with pytest.raises(FileExistsError):
        admin_pairing.export_pairing(
            uag_url="http://localhost:8000",
            admin_url="http://localhost:8088",
            output=out,
        )
    assert not (state / "admin_pairing_credentials.json").exists()


def test_explicit_generic_otel_environment_is_not_overridden(monkeypatch, tmp_path):
    _set_state(monkeypatch, tmp_path)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "https://collector.example.net")
    with pytest.raises(ValueError, match="explicitly configured"):
        admin_pairing.export_pairing(
            uag_url="http://localhost:8000",
            admin_url="http://localhost:8088",
            output=tmp_path / "should-not-export.json",
        )


def test_uag_workdir_override_is_respected(monkeypatch, tmp_path):
    _set_state(monkeypatch, tmp_path)
    workdir = tmp_path / "my-uag-workdir"
    workdir.mkdir()
    monkeypatch.setenv("UAGENT_WORKDIR", str(workdir))
    seen = []

    def fake_export(**kwargs):
        seen.append(os.getcwd())
        return tmp_path / "handled.json"

    monkeypatch.setattr(admin_pairing, "export_pairing", fake_export)
    original_cwd = os.getcwd()
    try:
        assert admin_pairing.main(["export"]) == 0
        assert seen == [str(workdir)]
    finally:
        os.chdir(original_cwd)


def test_envsec_validation_uses_workdir_environment_order(monkeypatch, tmp_path):
    """Decrypt after the usual loader activates the .env-selected key backend."""
    import sys
    import types

    from uagent.runtime import runtime_init

    _set_state(monkeypatch, tmp_path)
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    (workdir / ".env.sec").write_text("encrypted-placeholder", encoding="utf-8")
    stages = []

    def load_config():
        stages.append("loaded")
        monkeypatch.setenv("UAGENT_ENVSEC_KEY_BACKEND", "keyring")

    def decrypt(ciphertext):
        assert ciphertext == "encrypted-placeholder"
        assert os.environ["UAGENT_ENVSEC_KEY_BACKEND"] == "keyring"
        stages.append("decrypted")
        return ""

    fake_envsec = types.ModuleType("uag_envsec")
    fake_envsec.decrypt_text = decrypt
    monkeypatch.setitem(sys.modules, "uag_envsec", fake_envsec)
    monkeypatch.setattr(runtime_init, "load_dotenv_custom", load_config)
    monkeypatch.setattr(
        admin_pairing, "export_pairing", lambda **kwargs: tmp_path / "out.json"
    )
    original_dir = os.getcwd()
    try:
        assert admin_pairing.main(["export", "--workdir", str(workdir)]) == 0
    finally:
        os.chdir(original_dir)
    assert stages == ["loaded", "decrypted"]


def test_explicit_trace_endpoint_keeps_its_existing_exporter(monkeypatch):
    pytest.importorskip("opentelemetry.exporter.otlp.proto.http.trace_exporter")
    from opentelemetry.exporter.otlp.proto.http import trace_exporter

    from uagent.runtime.observability import otel_backend

    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "otlp")
    monkeypatch.setenv(
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
        "https://collector.example.net/v1/traces",
    )
    for key in (
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "OTEL_EXPORTER_OTLP_HEADERS",
        "OTEL_EXPORTER_OTLP_TRACES_HEADERS",
        "OTEL_EXPORTER_OTLP_TRACES_PROTOCOL",
        "OTEL_EXPORTER_OTLP_PROTOCOL",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(
        admin_pairing,
        "get_otlp_pairing",
        lambda: ("https://admin.example.net/otlp/v1/traces", "S" * 48),
    )
    constructor_calls = []

    def fake_exporter(**kwargs):
        constructor_calls.append(kwargs)
        return object()

    monkeypatch.setattr(trace_exporter, "OTLPSpanExporter", fake_exporter)
    otel_backend._build_trace_exporter()
    assert constructor_calls == [{}]


def test_explicit_metrics_endpoint_is_not_suppressed(monkeypatch):
    pytest.importorskip("opentelemetry.exporter.otlp.proto.http.metric_exporter")
    from opentelemetry.exporter.otlp.proto.http import metric_exporter

    from uagent.runtime.observability import otel_backend

    monkeypatch.delenv("OTEL_METRICS_EXPORTER", raising=False)
    monkeypatch.setenv(
        "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
        "https://metrics.example.net/v1/metrics",
    )
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_METRICS_PROTOCOL", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_PROTOCOL", raising=False)
    monkeypatch.setattr(
        admin_pairing,
        "get_otlp_pairing",
        lambda: ("https://admin.example.net/otlp/v1/traces", "S" * 48),
    )
    constructor_calls = []

    def fake_exporter(**kwargs):
        constructor_calls.append(kwargs)
        return object()

    monkeypatch.setattr(metric_exporter, "OTLPMetricExporter", fake_exporter)
    otel_backend._build_metric_exporter()
    assert constructor_calls == [{}]


@pytest.mark.skipif(os.name != "nt", reason="Windows-only ACL verification")
def test_windows_private_pairing_file_acl(monkeypatch, tmp_path):
    pytest.importorskip("win32security")
    _set_state(monkeypatch, tmp_path)
    transfer = tmp_path / "windows-transfer.json"
    admin_pairing.export_pairing(
        uag_url="http://127.0.0.1:8000",
        admin_url="http://127.0.0.1:8088",
        output=transfer,
    )
    # Owner-only DACL checks must succeed for both newly created secrets.
    admin_pairing._windows_private_acl(transfer)
    admin_pairing._windows_private_acl(
        tmp_path / "private-state" / "admin_pairing_credentials.json"
    )


def test_racing_export_does_not_remove_competing_transfer_file(monkeypatch, tmp_path):
    _set_state(monkeypatch, tmp_path)
    target = tmp_path / "competing-transfer.json"
    original_create = admin_pairing._secure_create

    def competing_create(path, payload):
        if path == target:
            # A different process won CREATE_NEW after the early exists check.
            target.write_text("owned-by-other-process", encoding="utf-8")
            raise FileExistsError("another exporter created transfer file")
        return original_create(path, payload)

    monkeypatch.setattr(admin_pairing, "_secure_create", competing_create)
    with pytest.raises(FileExistsError):
        admin_pairing.export_pairing(
            uag_url="http://127.0.0.1:8000",
            admin_url="http://127.0.0.1:8088",
            output=target,
        )
    assert target.read_text(encoding="utf-8") == "owned-by-other-process"
    assert not (tmp_path / "private-state" / "admin_pairing_credentials.json").exists()


def test_supervisor_pairing_is_single_file_with_separate_persisted_secret(
    monkeypatch, tmp_path
):
    state = _set_state(monkeypatch, tmp_path)
    monkeypatch.setenv("UAG_SUPERVISOR_HOST_ID", "remote-host")
    first = tmp_path / "supervisor-transfer.json"
    second = tmp_path / "supervisor-transfer-2.json"

    for filename in (first, second):
        admin_pairing.export_pairing(
            uag_url="https://uag.example.net",
            admin_url="https://admin.example.net",
            supervisor_url="https://supervisor.example.net",
            output=filename,
        )

    pair = json.loads(first.read_text(encoding="utf-8"))
    assert json.loads(second.read_text(encoding="utf-8")) == pair
    assert pair["supervisor"]["host_id"] == "remote-host"
    assert pair["supervisor"]["base_url"] == "https://supervisor.example.net"
    assert pair["supervisor"]["read_bearer"] not in (
        pair["manifest_bearer"],
        pair["otlp_bearer"],
    )
    assert (
        admin_pairing.get_supervisor_read_token() == pair["supervisor"]["read_bearer"]
    )
    stored = json.loads(
        (state / "admin_pairing_credentials.json").read_text(encoding="utf-8")
    )
    assert stored["supervisor_bearer"] == pair["supervisor"]["read_bearer"]
    assert "supervisor" not in stored
    assert admin_pairing.load_pairing()["manifest_bearer"] == pair["manifest_bearer"]
    if os.name != "nt":
        assert (state / "admin_pairing_credentials.json").stat().st_mode & 0o077 == 0


def test_supervisor_export_refuses_insecure_endpoint(monkeypatch, tmp_path):
    _set_state(monkeypatch, tmp_path)
    with pytest.raises(ValueError, match="HTTPS"):
        admin_pairing.export_pairing(
            uag_url="https://uag.example.net",
            admin_url="https://admin.example.net",
            supervisor_url="http://supervisor.example.net:8091",
            output=tmp_path / "never.json",
        )


def test_supervisor_rotation_changes_every_credential_atomically(monkeypatch, tmp_path):
    state = _set_state(monkeypatch, tmp_path)
    monkeypatch.setenv("UAG_SUPERVISOR_HOST_ID", "remote-host")
    first = tmp_path / "first.json"
    second = tmp_path / "rotated.json"
    kwargs = {
        "uag_url": "https://uag.example.net",
        "admin_url": "https://admin.example.net",
        "supervisor_url": "https://supervisor.example.net",
    }
    admin_pairing.export_pairing(**kwargs, output=first)
    old = json.loads(first.read_text(encoding="utf-8"))
    with pytest.raises(ValueError, match="supervisor-url"):
        admin_pairing.export_pairing(
            uag_url=kwargs["uag_url"],
            admin_url=kwargs["admin_url"],
            output=tmp_path / "invalid-rotation.json",
            rotate=True,
        )
    assert (
        json.loads(
            (state / "admin_pairing_credentials.json").read_text(encoding="utf-8")
        )["supervisor_bearer"]
        == old["supervisor"]["read_bearer"]
    )

    admin_pairing.export_pairing(**kwargs, output=second, rotate=True)
    new = json.loads(second.read_text(encoding="utf-8"))
    assert new["manifest_bearer"] != old["manifest_bearer"]
    assert new["otlp_bearer"] != old["otlp_bearer"]
    assert new["supervisor"]["read_bearer"] != old["supervisor"]["read_bearer"]
    assert admin_pairing.get_supervisor_read_token() == new["supervisor"]["read_bearer"]
    assert admin_pairing.get_manifest_pairing_token() == new["manifest_bearer"]


def test_failed_transfer_does_not_rotate_supervisor_token(monkeypatch, tmp_path):
    state = _set_state(monkeypatch, tmp_path)
    first = tmp_path / "before.json"
    kwargs = {
        "uag_url": "https://uag.example.net",
        "admin_url": "https://admin.example.net",
        "supervisor_url": "https://supervisor.example.net",
    }
    admin_pairing.export_pairing(**kwargs, output=first)
    original = (state / "admin_pairing_credentials.json").read_bytes()
    existing = tmp_path / "occupied.json"
    existing.write_text("external", encoding="utf-8")
    with pytest.raises(FileExistsError):
        admin_pairing.export_pairing(**kwargs, output=existing, rotate=True)
    assert (state / "admin_pairing_credentials.json").read_bytes() == original
    assert (
        admin_pairing.get_supervisor_read_token()
        == json.loads(first.read_text(encoding="utf-8"))["supervisor"]["read_bearer"]
    )
