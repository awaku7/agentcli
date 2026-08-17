from __future__ import annotations

import json

from uagent.auth import InMemoryCredentialStore
from uagent.util_cmd_credentials import handle_credential_command


class _Core:
    pass


def _translate(text: str, **_: object) -> str:
    return text


def test_credential_command_set_get_remove(monkeypatch, capsys) -> None:
    import uagent.util_cmd_credentials as commands

    store = InMemoryCredentialStore()
    monkeypatch.setattr(commands, "get_default_credential_store", lambda: store)
    monkeypatch.setattr(
        "uagent.tools.run_tool",
        lambda name, args: (
            json.dumps({"user_reply": "secret-value"})
            if args.get("is_password")
            else json.dumps({"user_reply": "y"})
        ),
    )
    core = _Core()

    handle_credential_command("set demo api_key", core=core, tr=_translate)
    assert store.get("demo") is not None

    handle_credential_command("get demo", core=core, tr=_translate)
    output = capsys.readouterr().out
    assert "name: demo" in output
    assert "kind: api_key" in output
    assert "secret-value" not in output

    handle_credential_command("remove demo", core=core, tr=_translate)
    assert store.get("demo") is None
