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


def test_save_uagent_envsec_writes_values_only_format(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(runtime_env, "get_startup_workdir", lambda: tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("UAGENT_ENVSEC_KEY_BACKEND", "file")

    secret = "dependency-backed"
    sec_path = runtime_env.save_uagent_envsec(env={"UAGENT_TEST_SECRET": secret})

    encrypted = sec_path.read_text(encoding="utf-8")
    assert encrypted.startswith("# uag-envsec:values-only:v1;format=1\n")
    assert "UAGENT_TEST_SECRET" in encrypted
    assert secret not in encrypted
    assert runtime_env._read_envsec_plaintext(sec_path) == (
        "UAGENT_TEST_SECRET" + "=" + secret + "\n"
    )


def test_encrypt_env_document_falls_back_for_trailing_backslash() -> None:
    from uag_envsec import decrypt_text

    from uagent.envsec_util import encrypt_env_document

    document = "UAGENT_WORKDIR=C:\\work\\\n"
    encrypted = encrypt_env_document(document)

    assert not encrypted.startswith("# uag-envsec:values-only:")
    assert decrypt_text(encrypted.strip()) == document
