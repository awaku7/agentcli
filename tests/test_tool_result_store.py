from __future__ import annotations

import json

from uagent.runtime.session_store import SessionStore


def test_tool_result_record_is_persisted_and_decoded(tmp_path) -> None:
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session = store.create_session(project="demo", entry_point="test")
        store.record_tool_result(
            session.session_id,
            {
                "result_id": "result-1",
                "task_id": "task-1",
                "tool_name": "example",
                "result_class": "large",
                "size_bytes": 123,
                "summary": "summary",
                "artifact_ref": "artifact://a1",
                "importance": "high",
                "evictable": False,
                "created_at": "2026-01-01T00:00:00+00:00",
                "metadata": {"tool_call_id": "call-1"},
            },
            {"role": "tool", "content": "bounded"},
        )

        results = store.list_tool_results(session.session_id)

    assert len(results) == 1
    assert results[0]["result_id"] == "result-1"
    assert results[0]["result_class"] == "large"
    assert results[0]["evictable"] is False
    assert results[0]["persistent_history"]["content"] == "bounded"
    assert results[0]["metadata"]["tool_call_id"] == "call-1"


def test_tool_result_session_lookup_by_task_id(tmp_path) -> None:
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session = store.create_session(project="demo", entry_point="a2a")
        store.record_tool_result(
            session.session_id,
            {"result_id": "task-result", "task_id": "task-1", "tool_name": "example"},
            "result",
        )

        assert store.find_sessions_by_task_id("task-1") == [session.session_id]
        assert store.find_sessions_by_task_id("missing") == []


def test_tool_result_can_be_retrieved_by_id(tmp_path) -> None:
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session = store.create_session(project="demo", entry_point="test")
        store.record_tool_result(
            session.session_id,
            {"result_id": "result-id", "tool_name": "read_file"},
            {"content": "full result"},
        )

        result = store.get_tool_result(session.session_id, "result-id")
        missing = store.get_tool_result(session.session_id, "missing")

    assert result is not None
    assert result["persistent_history"] == {"content": "full result"}
    assert missing is None


def test_tool_result_search_and_context_projection(tmp_path) -> None:
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session = store.create_session(project="demo", entry_point="test")
        store.record_tool_result(
            session.session_id,
            {
                "result_id": "result-search",
                "tool_name": "read_file",
                "summary": "configuration source",
                "artifact_ref": "artifact://cfg",
            },
            "configuration content",
        )

        results = store.search_tool_results(session.session_id, "configuration")

    assert len(results) == 1
    assert results[0]["result_id"] == "result-search"
    assert results[0]["persistent_history"] == "configuration content"


def test_tool_result_search_ranks_summary_and_supports_multiple_tokens(
    tmp_path,
) -> None:
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session = store.create_session(project="demo", entry_point="test")
        store.record_tool_result(
            session.session_id,
            {"result_id": "weak", "tool_name": "read_file", "summary": "source"},
            "configuration text",
        )
        store.record_tool_result(
            session.session_id,
            {
                "result_id": "strong",
                "tool_name": "configuration_reader",
                "summary": "configuration source",
            },
            "other",
        )

        results = store.search_tool_results(session.session_id, "configuration source")

    assert results[0]["result_id"] == "strong"


def test_tool_result_record_sanitizes_binary_history(tmp_path) -> None:
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session = store.create_session(project="demo", entry_point="test")
        store.record_tool_result(
            session.session_id,
            {"result_id": "result-2", "tool_name": "image"},
            {"image_b64": "secret", "path": "/tmp/image.png"},
        )
        result = store.list_tool_results(session.session_id)[0]

    assert "secret" not in str(result["persistent_history"])
    assert result["persistent_history"]["path"] == "/tmp/image.png"


def test_tool_result_persistence_redacts_nested_secrets_in_database(tmp_path) -> None:
    secrets = (
        "summary-dummy-secret",
        "metadata-dummy-token",
        "password-dummy-value",
        "private-key-dummy-value",
        "body-dummy-bearer",
        "camel-case-dummy-token",
        "signed-token-dummy-value",
        "unknown-token-object-field",
        "password-status-secret",
        "private-key-token-id-secret",
    )
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session = store.create_session(project="demo", entry_point="test")
        store.record_tool_result(
            session.session_id,
            {
                "result_id": "result-redaction",
                "tool_name": "example",
                "summary": f"api_key={secrets[0]}",
                "metadata": {
                    "tool_call_id": "call-redaction",
                    "status": "failed",
                    "authorization": f"Bearer {secrets[1]}",
                },
            },
            {
                "nested": {
                    "password": secrets[2],
                    "private_key": secrets[3],
                },
                "detail": f"Authorization: Bearer {secrets[4]}",
                "authorization_url": (
                    "https://idp.example/authorize?client_id=demo&state=state-dummy&access_token=oauth-access-dummy"
                ),
                "signature": "ET MALWARE Test Rule",
                "json_text": json.dumps(
                    {"accessToken": secrets[5]}, ensure_ascii=False
                ),
                "password": {"status": secrets[8]},
                "private_key": {"token_id": secrets[9]},
                "secret_findings": [
                    {"path": "src/app.py", "line": 17, "kind": "api_key_assignment"}
                ],
                "token": {
                    "signed_token": secrets[6],
                    "token_id": "tokid-public-123",
                    "status": "approved",
                    "expires_at": "2026-10-12T12:00:00Z",
                    "internal": secrets[7],
                },
                "token_id": "verification-id-public-123",
            },
        )
        raw = store._connection.execute(
            "SELECT summary, metadata_json, persistent_json "
            "FROM tool_results WHERE session_id = ? AND result_id = ?",
            (session.session_id, "result-redaction"),
        ).fetchone()
        assert raw is not None
        raw_text = " ".join(str(value) for value in raw)
        assert all(secret not in raw_text for secret in secrets)
        metadata = json.loads(raw["metadata_json"])
        persistent = json.loads(raw["persistent_json"])
        result = store.get_tool_result(session.session_id, "result-redaction")

    assert metadata["tool_call_id"] == "call-redaction"
    assert metadata["status"] == "failed"
    assert metadata["authorization"] == "********"
    assert persistent["nested"]["password"] == "********"
    assert persistent["nested"]["private_key"] == "********"
    assert persistent["password"]["status"] == "********"
    assert persistent["private_key"]["token_id"] == "********"
    assert persistent["secret_findings"] == [
        {"path": "src/app.py", "line": 17, "kind": "api_key_assignment"}
    ]
    assert "********" in persistent["detail"]
    assert persistent["authorization_url"] == (
        "https://idp.example/authorize?client_id=demo&state=state-dummy"
        "&access_token=********"
    )
    assert persistent["signature"] == "ET MALWARE Test Rule"
    assert json.loads(persistent["json_text"])["accessToken"] == "********"
    assert persistent["token"] == {
        "signed_token": "********",
        "token_id": "tokid-public-123",
        "status": "approved",
        "expires_at": "2026-10-12T12:00:00Z",
        "internal": "********",
    }
    assert persistent["token_id"] == "verification-id-public-123"
    assert result is not None
    assert result["summary"] == "api_key=********"


def test_tool_result_persistence_enforces_utf8_record_byte_budget(tmp_path) -> None:
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session = store.create_session(project="demo", entry_point="test")
        store.record_tool_result(
            session.session_id,
            {
                "result_id": "result-byte-limit",
                "tool_name": "read_file",
                "result_class": "huge",
                "size_bytes": 1_500_000,
                "summary": "large result",
                "artifact_ref": "artifact://bounded-ref",
                "metadata": {
                    "tool_call_id": "call-byte-limit",
                    "status": "timeout",
                    "padding": "x" * 100_000,
                },
            },
            {"content": "界" * 500_000, "tail": "end"},
        )
        raw = store._connection.execute(
            "SELECT result_id, session_id, task_id, tool_name, result_class, "
            "size_bytes, summary, artifact_ref, importance, evictable, "
            "metadata_json, persistent_json, created_at FROM tool_results "
            "WHERE session_id = ? AND result_id = ?",
            (session.session_id, "result-byte-limit"),
        ).fetchone()
        assert raw is not None
        stored_bytes = sum(len(str(value).encode("utf-8")) for value in raw)
        metadata = json.loads(raw["metadata_json"])
        persisted = json.loads(raw["persistent_json"])
        result = store.get_tool_result(session.session_id, "result-byte-limit")

    assert stored_bytes <= 512 * 1024
    assert metadata["tool_call_id"] == "call-byte-limit"
    assert metadata["status"] == "timeout"
    assert metadata["_uagent_metadata_truncated"] is True
    assert persisted["_uagent_persisted_history"] == "truncated"
    assert persisted["artifact_ref"] == "artifact://bounded-ref"
    assert result is not None
    assert result["persistent_history"]["original_bytes"] > 512 * 1024


def test_tool_result_redaction_failure_never_persists_raw_fallback(
    tmp_path, monkeypatch
) -> None:
    from uagent.runtime import session_store as session_store_module

    def fail_serialization(*_args, **_kwargs):
        raise RuntimeError("simulated sanitizer failure")

    monkeypatch.setattr(
        session_store_module, "bounded_persistent_json", fail_serialization
    )
    secret = "raw-dummy-payload-secret"
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session = store.create_session(project="demo", entry_point="test")
        store.record_tool_result(
            session.session_id,
            {
                "result_id": "result-safe-fallback",
                "tool_name": "example",
                "metadata": {"status": "success", "tool_call_id": "call-safe"},
            },
            {"content": secret},
        )
        raw = store._connection.execute(
            "SELECT persistent_json, metadata_json FROM tool_results "
            "WHERE session_id = ? AND result_id = ?",
            (session.session_id, "result-safe-fallback"),
        ).fetchone()

    assert raw is not None
    assert secret not in raw["persistent_json"]
    assert "omitted_after_sanitization_error" in raw["persistent_json"]
    metadata = json.loads(raw["metadata_json"])
    assert metadata["status"] == "success"
