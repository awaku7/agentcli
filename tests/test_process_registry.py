"""Local process registry lifecycle, identity and fail-closed behavior."""

from __future__ import annotations

import json
import os

from uagent.runtime import process_registry as registry

_UUID = "12345678-1234-5678-1234-567812345678"


def test_tracks_and_cleans_process(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, "get_state_dir", lambda: tmp_path)
    monkeypatch.setattr(registry, "get_instance_id", lambda: _UUID)

    with registry.tracked_process("cli"):
        files = list((tmp_path / "process_registry").glob("*.json"))
        assert len(files) == 1
        record = json.loads(files[0].read_text(encoding="utf-8"))
        assert record == {
            "version": 1,
            "instance_id": _UUID,
            "entrypoint": "cli",
            "pid": os.getpid(),
            "create_time": registry.psutil.Process(os.getpid()).create_time(),
        }
        assert "password" not in record
    assert list((tmp_path / "process_registry").glob("*.json")) == []


def test_does_not_register_non_uag_entrypoints(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, "get_state_dir", lambda: tmp_path)
    with registry.tracked_process("arbitrary"):
        assert not (tmp_path / "process_registry").exists()


def test_does_not_follow_registry_symlink(tmp_path, monkeypatch):
    unsafe = tmp_path / "elsewhere"
    unsafe.mkdir()
    (tmp_path / "process_registry").symlink_to(unsafe, target_is_directory=True)
    monkeypatch.setattr(registry, "get_state_dir", lambda: tmp_path)
    with registry.tracked_process("web"):
        assert not list(unsafe.iterdir())


def test_registration_errors_do_not_block_uag(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, "get_state_dir", lambda: tmp_path)
    monkeypatch.setattr(registry, "get_instance_id", lambda: _UUID)

    def deny(*args, **kwargs):
        raise PermissionError("not writable")

    monkeypatch.setattr(registry, "_register", deny)
    with registry.tracked_process("a2a"):
        assert True


def test_record_removed_after_exception(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, "get_state_dir", lambda: tmp_path)
    monkeypatch.setattr(registry, "get_instance_id", lambda: _UUID)
    try:
        with registry.tracked_process("gui"):
            raise RuntimeError("exit")
    except RuntimeError:
        pass
    assert list((tmp_path / "process_registry").glob("*.json")) == []
