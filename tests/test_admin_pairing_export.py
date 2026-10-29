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
