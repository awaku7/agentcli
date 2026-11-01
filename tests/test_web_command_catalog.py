"""Authorization and discovery for the Web command picker."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from fastapi.responses import JSONResponse

from uagent import tools
from uagent.web_impl import connection_identity, routes_api
from uagent.web_impl.rooms import web_manager


class FakeRequest:
    query_params = {"lang": "en"}


def _setup(monkeypatch, *, profile="remote", authn="oidc", private=False):
    identity = SimpleNamespace(principal_id="alice", authn_kind=authn)
    monkeypatch.setattr(routes_api, "_request_identity", lambda _req: identity)
    monkeypatch.setattr(
        connection_identity,
        "require_room_access",
        lambda _identity, _room: ("project-a", private),
    )
    monkeypatch.setattr(web_manager, "execution_profile", profile, raising=False)
    monkeypatch.setattr(web_manager, "sandbox_enabled", False, raising=False)


def _catalog():
    response = asyncio.run(routes_api.api_commands(FakeRequest(), "room-a"))
    assert isinstance(response, JSONResponse)
    return response, json.loads(response.body)


def test_remote_picker_only_lists_web_allowed_commands(monkeypatch):
    _setup(monkeypatch)
    monkeypatch.setattr(
        tools,
        "get_dynamic_command_catalog",
        lambda: (_ for _ in ()).throw(AssertionError("imported host commands")),
    )
    response, body = _catalog()
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    names = {item["name"] for item in body["commands"]}
    assert {"otel", "r", "v"} <= names
    assert {"help", "tools", "rm", "load"} & names == set()


def test_local_picker_merges_dynamic_commands_without_handlers(monkeypatch):
    _setup(monkeypatch, profile="local_trusted", authn="local")
    monkeypatch.setattr(
        tools,
        "get_dynamic_command_catalog",
        lambda: [
            {
                "name": "custom",
                "subcommands": [
                    {"name": "run", "summary": "Run a plugin", "usage": ":custom run"}
                ],
            }
        ],
    )
    response, body = _catalog()
    assert response.status_code == 200
    commands = {item["name"]: item for item in body["commands"]}
    assert "tools" in commands
    assert commands["custom"]["subcommands"][0]["name"] == "run"


def test_private_room_hides_session_history_commands(monkeypatch):
    _setup(monkeypatch, profile="local_trusted", authn="local", private=True)
    monkeypatch.setattr(tools, "get_dynamic_command_catalog", lambda: [])
    _, body = _catalog()
    names = {item["name"] for item in body["commands"]}
    assert not {"load", "cont", "logs", "sessions"} & names
    assert "model" in names


def test_command_catalog_rejects_room_without_access(monkeypatch):
    _setup(monkeypatch)
    def forbidden(_identity, _room):
        raise PermissionError("not your room")

    monkeypatch.setattr(connection_identity, "require_room_access", forbidden)
    response = asyncio.run(routes_api.api_commands(FakeRequest(), "room-a"))
    assert response.status_code == 403


def test_dynamic_catalog_does_not_include_callable_handlers(monkeypatch):
    monkeypatch.setattr(tools, "_ensure_loaded", lambda: None)
    monkeypatch.setattr(
        tools,
        "_DYNAMIC_COMMANDS",
        {
            "sample": {
                "run": {
                    "handler": lambda _arg: "secret",
                    "help_text": "Run",
                    "usage": ":sample run",
                }
            }
        },
    )
    catalog = tools.get_dynamic_command_catalog()
    assert catalog == [
        {
            "name": "sample",
            "subcommands": [
                {"name": "run", "summary": "Run", "usage": ":sample run"}
            ],
        }
    ]
