from __future__ import annotations

from pathlib import Path

from uagent.runtime import runtime_env


def test_runtime_envsec_uses_external_uag_envsec(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(runtime_env, "get_startup_workdir", lambda: tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("UAGENT_ENVSEC_KEY_BACKEND", "file")

    sec_path = runtime_env.save_uagent_envsec(
        env={"UAGENT_TEST_SECRET": "dependency-backed"}
    )

    assert sec_path == tmp_path / ".env.sec"
    encrypted = sec_path.read_text(encoding="utf-8").strip()
    # The wire format is owned by the external dependency and may be versioned.
    assert "dependency-backed" not in encrypted
    assert runtime_env._read_envsec_plaintext(sec_path) == (
        "UAGENT_TEST_SECRET=dependency-backed\n"
    )
