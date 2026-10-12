import json
from pathlib import Path

from uagent.runtime.history import materialize_large_tool_result


def test_large_tool_result_is_saved_and_referenced(tmp_path, monkeypatch):
    value = "header\n" + ("payload\n" * 20) + "footer"
    monkeypatch.setenv("UAGENT_WORKDIR", str(tmp_path))
    state_dir = tmp_path / "state"
    monkeypatch.setenv("UAGENT_STATE_DIR", str(state_dir))
    monkeypatch.setenv("UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS", "10")
    monkeypatch.setenv("UAGENT_TOOL_RESULT_MAX_CHARS", "30")

    result = materialize_large_tool_result(value, tool_name="example")

    assert "[tool result stored as artifact]" in result
    assert "artifact_ref: artifact://" in result
    assert f"original_length: {len(value)}" in result
    artifact_path = next(
        line.split(": ", 1)[1]
        for line in result.splitlines()
        if line.startswith("artifact_path: ")
    )
    assert (
        Path(state_dir, "artifacts", artifact_path).read_text(encoding="utf-8") == value
    )
    assert len(result) > len(value) or "preview:" in result


def test_artifact_registration_failure_keeps_bounded_fallback(monkeypatch):
    monkeypatch.setenv("UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS", "1")
    monkeypatch.setenv("UAGENT_TOOL_RESULT_MAX_CHARS", "200")

    # An invalid workdir makes artifact registration fail without allowing the
    # original oversized value back into the returned context entry.
    monkeypatch.setenv("UAGENT_WORKDIR", str(Path.cwd() / "missing-uagent-workdir"))
    result = materialize_large_tool_result("x" * 300, tool_name="example")

    assert len(result) <= 200
    assert "original length=300" in result


def test_large_json_artifact_redacts_nested_secrets_and_preserves_json(
    tmp_path, monkeypatch
):
    value = json.dumps(
        {
            "public": "keep-this",
            "authorization_url": (
                "https://idp.example/authorize?client_id=demo&state=state-dummy&access_token=oauth-access-dummy"
            ),
            "signature": "ET MALWARE Test Rule",
            "token": {
                "signed_token": "artifact-signed-token-dummy",
                "token_id": "artifact-token-id-public",
                "status": "approved",
                "expires_at": "2026-10-12T12:00:00Z",
            },
            "connection_settings": {
                "private_key": "artifact-private-dummy",
                "nested": {"authorization": "Bearer artifact-token-dummy"},
            },
        },
        ensure_ascii=False,
    )
    monkeypatch.setenv("UAGENT_WORKDIR", str(tmp_path))
    state_dir = tmp_path / "state"
    monkeypatch.setenv("UAGENT_STATE_DIR", str(state_dir))
    monkeypatch.setenv("UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS", "1")

    result = materialize_large_tool_result(value, tool_name="example")

    artifact_path = next(
        line.split(": ", 1)[1]
        for line in result.splitlines()
        if line.startswith("artifact_path: ")
    )
    stored_text = Path(state_dir, "artifacts", artifact_path).read_text(
        encoding="utf-8"
    )
    stored = json.loads(stored_text)
    assert stored["public"] == "keep-this"
    assert stored["authorization_url"] == (
        "https://idp.example/authorize?client_id=demo&state=state-dummy"
        "&access_token=********"
    )
    assert stored["signature"] == "ET MALWARE Test Rule"
    assert stored["token"] == {
        "signed_token": "********",
        "token_id": "artifact-token-id-public",
        "status": "approved",
        "expires_at": "2026-10-12T12:00:00Z",
    }
    assert stored["connection_settings"]["private_key"] == "********"
    assert stored["connection_settings"]["nested"]["authorization"] == "********"
    assert "artifact-private-dummy" not in stored_text
    assert "artifact-token-dummy" not in stored_text
    assert "artifact-signed-token-dummy" not in stored_text
