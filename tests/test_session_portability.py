from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import pytest

from uagent.runtime import session_portability as p
from uagent.runtime.session_store import SessionStore, SessionStoreError


@pytest.fixture
def store(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as value:
        yield value


@pytest.fixture
def payload():
    return {
        "format": "uag-session",
        "version": 1,
        "session": {
            "source_session_id": "a" * 32,
            "created_at": "2026-09-24",
            "entry_point": "cli",
            "project_hint": "demo",
        },
        "conversation": [
            {"role": "user", "content": "continue 日本語"},
            {"role": "assistant", "content": "ready"},
        ],
        "references": {
            "memory": ["memory:abc@1"],
            "artifacts": ["artifact://" + "b" * 32],
        },
    }


def test_encrypted_roundtrip_fresh_keys_and_nonce(payload):
    one = p.encrypt(payload, "correct horse")
    two = p.encrypt(payload, "correct horse")
    assert one != two
    assert b"continue" not in one and b"demo" not in one
    assert p.decrypt(one, "correct horse") == payload
    assert (
        p.HEADER.unpack(one[: p.HEADER.size])[7:]
        != p.HEADER.unpack(two[: p.HEADER.size])[7:]
    )


@pytest.mark.parametrize("position", [0, 10, 11, 12, 25, 41, 53, 65, 89, -1])
def test_tampering_rejected(payload, position):
    package = bytearray(p.encrypt(payload, "password"))
    package[position] ^= 1
    with pytest.raises(p.PortableSessionError):
        p.decrypt(bytes(package), "password")


def test_wrong_passphrase_and_truncation(payload):
    package = p.encrypt(payload, "good")
    with pytest.raises(p.PortableSessionError, match="wrong passphrase or damaged"):
        p.decrypt(package, "bad")
    for size in (0, 10, p.HEADER.size, len(package) - 1):
        with pytest.raises(p.PortableSessionError):
            p.decrypt(package[:size], "good")


@pytest.mark.parametrize(
    "index,value", [(4, 2**32 - 1), (5, 2**32 - 1), (6, 0), (4, 8), (3, 16)]
)
def test_kdf_rejected_before_derivation(payload, monkeypatch, index, value):
    package = p.encrypt(payload, "good")
    fields = list(p.HEADER.unpack(package[: p.HEADER.size]))
    fields[index] = value
    monkeypatch.setattr(p, "_derive", lambda *a: pytest.fail("KDF must not run"))
    with pytest.raises(p.PortableSessionError):
        p.decrypt(p.HEADER.pack(*fields) + package[p.HEADER.size :], "good")


@pytest.mark.parametrize("value", ["", None, "a" * 1025])
def test_invalid_passphrase(payload, value):
    with pytest.raises(p.PortableSessionError):
        p.encrypt(payload, value)


@pytest.mark.parametrize(
    "ref",
    [
        "../../secret",
        "artifact://../secret",
        "C:\\secret",
        "/etc/passwd",
        "memory:../x@1",
        "artifact://" + "b" * 32 + "/../../x",
    ],
)
def test_reference_path_traversal_rejected(payload, ref):
    payload["references"]["artifacts"] = [ref]
    with pytest.raises(p.PortableSessionError):
        p.validate_payload(payload)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p.update(version=True),
        lambda p: p.update(version=2),
        lambda p: p.update(credentials={"password": "secret"}),
        lambda p: p["session"].update(principal_id="admin"),
        lambda p: p["session"].update(source_session_id="../../x"),
        lambda p: p["conversation"][0].update(role="system"),
        lambda p: p["conversation"][0].update(tool_calls=[]),
        lambda p: p.update(conversation="bad"),
    ],
)
def test_malformed_schema(payload, mutation):
    mutation(payload)
    with pytest.raises(p.PortableSessionError):
        p.validate_payload(payload)


def test_size_limits_before_kdf(payload, monkeypatch):
    monkeypatch.setattr(p, "_derive", lambda *a: pytest.fail("KDF must not run"))
    with pytest.raises(p.PortableSessionError):
        p.decrypt(b"x" * (p.MAX_PACKAGE + 1), "good")
    payload["conversation"] *= p.MAX_MESSAGES
    with pytest.raises(p.PortableSessionError):
        p.encrypt(payload, "good")


def test_import_detached_and_repeated_ids_remapped(store, payload):
    first = store.import_portable_payload(payload, principal_id="destination")
    second = store.import_portable_payload(payload)
    assert (
        len(
            {
                first.session_id,
                second.session_id,
                payload["session"]["source_session_id"],
            }
        )
        == 3
    )
    row = store.get_session(first.session_id)
    assert row["principal_id"] == "destination"
    assert row["project"] is None and row["project_path"] is None and not row["room_id"]
    assert store.list_messages(first.session_id) == payload["conversation"]
    assert store.latest_response_state(first.session_id) is None
    assert store.latest_tool_context(first.session_id) == {}
    assert (
        store.get_portable_metadata(first.session_id)["references"]
        == payload["references"]
    )


def test_id_collision_never_overwrites(store, payload, monkeypatch):
    original = store.import_portable_payload(payload)
    monkeypatch.setattr(
        "uagent.runtime.session_store.uuid.uuid4",
        lambda: SimpleNamespace(hex=original.session_id),
    )
    with pytest.raises(SessionStoreError):
        store.import_portable_payload(payload)
    assert store.list_messages(original.session_id) == payload["conversation"]
    assert len(store.list_sessions()) == 1


def test_source_id_collision_rolls_back(store, payload, monkeypatch):
    monkeypatch.setattr(
        "uagent.runtime.session_store.uuid.uuid4",
        lambda: SimpleNamespace(hex=payload["session"]["source_session_id"]),
    )
    with pytest.raises(SessionStoreError):
        store.import_portable_payload(payload)
    assert store.list_sessions() == []


def test_import_failure_is_atomic(store, payload, monkeypatch):
    original = store._append_message_unlocked

    def append(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("disk failure")

    monkeypatch.setattr(store, "_append_message_unlocked", append)
    with pytest.raises(RuntimeError):
        store.import_portable_payload(payload)
    assert store.list_sessions() == []
    assert (
        store._connection.execute("SELECT count(*) FROM message_search").fetchone()[0]
        == 0
    )


def test_credential_exclusion_and_inert_conversation(store, monkeypatch):
    session = store.create_session(project="../../old-path", entry_point="cli")
    monkeypatch.setenv("DEMO_API_KEY", "environment-value-123")
    store.append_message(
        session.session_id, "system", "[MEMORY EVIDENCE] private projection"
    )
    store.append_message(
        session.session_id,
        "user",
        "ordinary task\nenvironment-value-123\nAuthorization: Basic abcdef\n-----BEGIN RSA PRIVATE KEY-----\nprivate-material\n-----END RSA PRIVATE KEY-----\nOAuth: oauth-value\npassword = 'spaces are secret'",
        payload={"api_key": "hidden-key"},
    )
    store.append_message(
        session.session_id,
        "assistant",
        "hidden-key",
        payload={
            "provider_state": {"accessToken": "hidden-token"},
            "tool_calls": [{"id": "execute-me"}],
        },
    )
    store.append_message(
        session.session_id,
        "tool",
        "completed safely",
        payload={"tool_call_id": "execute-me"},
    )
    exported = p.snapshot(store, session.session_id)
    raw = json.dumps(exported)
    for secret in (
        "environment-value-123",
        "abcdef",
        "private-material",
        "oauth-value",
        "spaces are secret",
        "hidden-key",
        "hidden-token",
        "execute-me",
        "private projection",
        "../../old-path",
    ):
        assert secret not in raw
    assert all(set(m) == {"role", "content"} for m in exported["conversation"])
    assert exported["conversation"][-1]["role"] == "assistant"


def test_files_only_encrypted_no_overwrite(store, payload, tmp_path):
    source = store.import_portable_payload(payload)
    path = tmp_path / "test.uag"
    p.export_file(store, source.session_id, path, "good")
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        p.export_file(store, source.session_id, path, "good")
    assert path.read_bytes() == original
    imported = p.import_file(store, path, "good")
    assert imported.session_id != source.session_id
    path.write_text(json.dumps(payload))
    count = len(store.list_sessions())
    with pytest.raises(p.PortableSessionError):
        p.import_file(store, path, "good")
    assert len(store.list_sessions()) == count


def test_cli_export_import_without_provider(
    store, payload, tmp_path, monkeypatch, capsys
):
    from uagent import session_cli

    source = store.import_portable_payload(payload)
    monkeypatch.setenv("UAGENT_SESSION_STORE_PATH", str(store.path))
    monkeypatch.setattr(session_cli, "read_passphrase", lambda **kw: "good")
    path = str(tmp_path / "with spaces.uag")
    assert session_cli.main(["export", source.session_id, "-o", path]) == 0
    capsys.readouterr()
    assert session_cli.main(["import", path]) == 0
    imported_id = capsys.readouterr().out.strip()
    assert imported_id != source.session_id
    assert store.list_messages(imported_id) == payload["conversation"]


def test_duplicate_json_rejected():
    with pytest.raises(p.PortableSessionError):
        json.loads('{"version":1,"version":2}', object_pairs_hook=p._unique_pairs)


def test_legacy_import_cannot_accept_plaintext_uag(store, payload, tmp_path):
    path = tmp_path / "plaintext.uag"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SessionStoreError, match="encrypted portable import"):
        store.import_jsonl(path)
    assert store.list_sessions() == []


def test_interactive_portable_and_legacy_commands(
    store, payload, tmp_path, monkeypatch
):
    from uagent import session_cli
    from uagent.util_cmd_session import _handle_cmd_sessions

    source = store.import_portable_payload(payload)
    core = SimpleNamespace(session_store=store, session_id=source.session_id)
    monkeypatch.setattr(session_cli, "read_passphrase", lambda **kwargs: "good")
    path = tmp_path / "with spaces.uag"
    _handle_cmd_sessions(
        f'export {source.session_id} "{path}"', core=core, tr=lambda x: x
    )
    assert path.read_bytes().startswith(p.MAGIC)
    _handle_cmd_sessions(f'import-uag "{path}"', core=core, tr=lambda x: x)
    assert len(store.list_sessions()) == 2
    legacy = tmp_path / "legacy.jsonl"
    legacy.write_text('{"role":"user","content":"legacy dialogue"}\n', encoding="utf-8")
    _handle_cmd_sessions(f"import {legacy}", core=core, tr=lambda x: x)
    assert len(store.list_sessions()) == 3


def test_web_command_never_prompts_for_passphrase(store, monkeypatch):
    from uagent import session_cli
    from uagent.util_cmd_session import _handle_cmd_sessions

    monkeypatch.setattr(
        session_cli,
        "read_passphrase",
        lambda **kwargs: pytest.fail("Web must not prompt"),
    )
    core = SimpleNamespace(session_store=store, _is_web=True)
    assert _handle_cmd_sessions("import-uag private.uag", core=core, tr=lambda x: x)


def test_reference_roundtrip_no_resolution(store, payload):
    imported = store.import_portable_payload(copy.deepcopy(payload))
    assert p.snapshot(store, imported.session_id)["references"] == payload["references"]


def test_resume_keeps_destination_instructions_and_no_source_state(store, payload):
    from uagent.session_cli import restore_imported_session

    session = store.import_portable_payload(payload)
    core = SimpleNamespace(session_id="startup")
    messages = [{"role": "system", "content": "destination instructions"}]
    restore_imported_session(core, store, messages, session.session_id)
    assert (
        messages
        == [{"role": "system", "content": "destination instructions"}]
        + payload["conversation"]
    )
    assert core.session_id == core._session_store_active_id == session.session_id
    assert not hasattr(core, "previous_response_id")


def test_cli_resume_cannot_rebind_web_identity(store, payload):
    from uagent.session_cli import restore_imported_session

    session = store.import_portable_payload(payload, principal_id="alice")
    core = SimpleNamespace(session_id="unchanged")
    messages = []
    with pytest.raises(ValueError, match="authorization"):
        restore_imported_session(core, store, messages, session.session_id)
    assert not messages and core.session_id == "unchanged"


@pytest.mark.parametrize(
    "text",
    [
        "password: |\n  multi line\n  secret value",
        "OIDC refresh token:\n```\nopaque-value\n```",
        "-----BEGIN PGP PRIVATE KEY BLOCK-----\nprivate-data\n-----END PGP PRIVATE KEY BLOCK-----",
        '{"privateKey": "first\\nsecond"}',
    ],
)
def test_multiline_credentials_removed(store, text):
    session = store.create_session(project=None, entry_point="cli")
    store.append_message(session.session_id, "user", text)
    assert (
        p.snapshot(store, session.session_id)["conversation"][0]["content"]
        == "[REDACTED]"
    )


def test_authenticated_malformed_json_is_not_imported(store, payload):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    package = p.encrypt(payload, "good")
    header = package[: p.HEADER.size]
    salt, wrap_nonce, nonce = p.HEADER.unpack(header)[7:]
    wrapped = package[p.HEADER.size : p.HEADER.size + 48]
    dek = AESGCM(p._derive("good", salt)).decrypt(wrap_nonce, wrapped, header + b"/DEK")
    for raw in (b'{"version":1,"version":2}', b"[]", b"{" * 1500, b"null", b"not-json"):
        malicious = (
            header
            + wrapped
            + AESGCM(dek).encrypt(nonce, raw, header + wrapped + b"/payload")
        )
        with pytest.raises(p.PortableSessionError):
            store.import_portable_payload(p.decrypt(malicious, "good"))
    assert store.list_sessions() == []
