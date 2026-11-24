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


def test_encrypt_env_document_falls_back_for_trailing_backslash(
    tmp_path: Path, monkeypatch
) -> None:
    from uag_envsec import decrypt_text, ensure_key_file

    from uagent.envsec_util import encrypt_env_document

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("UAGENT_ENVSEC_KEY_BACKEND", "file")
    ensure_key_file()

    document = "UAGENT_WORKDIR=C:\\work\\\n"
    encrypted = encrypt_env_document(document)

    assert not encrypted.startswith("# uag-envsec:values-only:")
    assert decrypt_text(encrypted.strip()) == document


def test_describe_error_names_type_for_empty_message() -> None:
    from cryptography.exceptions import InvalidTag

    from uagent.runtime.runtime_env import describe_error

    assert describe_error(InvalidTag()) == "InvalidTag"
    assert describe_error(ValueError("boom")) == "ValueError: boom"


def test_startup_decrypt_warning_names_error_type(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    from uag_envsec import encrypt_env_values, ensure_key_file

    from uagent.runtime.runtime_init import load_dotenv_custom

    home_a = tmp_path / "home_a"
    home_b = tmp_path / "home_b"
    workdir = tmp_path / "work"
    for d in (home_a, home_b, workdir):
        d.mkdir()
    monkeypatch.setenv("UAGENT_ENVSEC_KEY_BACKEND", "file")

    name = "UAGENT_" + "PROVIDER"
    doc = f"{name}=openai\n"
    monkeypatch.setattr(Path, "home", lambda: home_a)
    ensure_key_file()
    (workdir / ".env.sec").write_text(
        encrypt_env_values(doc), encoding="utf-8", newline="\n"
    )

    # A different key at the default location: decryption must fail, and
    # the warning must name the exception type (InvalidTag's message is
    # empty, so printing the exception alone would show a blank reason).
    monkeypatch.setattr(Path, "home", lambda: home_b)
    ensure_key_file()
    monkeypatch.chdir(workdir)
    load_dotenv_custom()
    err = capsys.readouterr().err
    assert "Failed to decrypt .env.sec: InvalidTag" in err
