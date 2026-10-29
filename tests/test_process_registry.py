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
    try:
        (tmp_path / "process_registry").symlink_to(unsafe, target_is_directory=True)
    except (OSError, NotImplementedError):
        return
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


def test_persisted_identity_failure_is_best_effort(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, "get_state_dir", lambda: tmp_path)

    def failed_identity():
        raise RuntimeError("corrupt persisted identity")

    monkeypatch.setattr(registry, "get_instance_id", failed_identity)
    with registry.tracked_process("cli"):
        assert list((tmp_path / "process_registry").glob("*.json")) == []


def test_activate_after_workdir_and_clear(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, "get_state_dir", lambda: tmp_path)
    monkeypatch.setattr(registry, "get_instance_id", lambda: _UUID)
    registry.activate_tracking("web")
    try:
        assert len(list((tmp_path / "process_registry").glob("*.json"))) == 1
    finally:
        registry.clear_tracking("web")
    assert list((tmp_path / "process_registry").glob("*.json")) == []


def test_windows_registry_acl_is_current_user_only(tmp_path, monkeypatch):
    if os.name != "nt":
        return

    import win32security

    monkeypatch.setattr(registry, "get_state_dir", lambda: tmp_path)
    monkeypatch.setattr(registry, "get_instance_id", lambda: _UUID)
    with registry.tracked_process("web"):
        directory = tmp_path / "process_registry"
        paths = list(directory.glob("*.json"))
        assert len(paths) == 1
        for path in [directory, paths[0]]:
            descriptor = win32security.GetFileSecurity(
                str(path),
                win32security.OWNER_SECURITY_INFORMATION
                | win32security.DACL_SECURITY_INFORMATION,
            )
            control, _ = descriptor.GetSecurityDescriptorControl()
            assert control & win32security.SE_DACL_PROTECTED
            acl = descriptor.GetSecurityDescriptorDacl()
            assert acl is not None
            assert acl.GetAceCount() == 1
            assert acl.GetAce(0)[2] == descriptor.GetSecurityDescriptorOwner()
