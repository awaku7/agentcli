from __future__ import annotations

from types import SimpleNamespace

from uagent.util_tools import handle_command


class _Responses:
    def retrieve(self, response_id: str):
        return {"id": response_id, "status": "completed"}


class _Client:
    responses = _Responses()


def test_response_status_command_retrieves_saved_response(capsys) -> None:
    core = SimpleNamespace(
        tr=lambda text: text,
        responses_state={
            "provider": "openai",
            "model": "gpt-5.4",
            "previous_response_id": "resp_1",
        },
    )

    assert handle_command(
        ":response status", [], _Client(), "gpt-5.4", core=core
    ) is True
    output = capsys.readouterr().out
    assert '"id": "resp_1"' in output
    assert "completed" in output


def test_response_command_is_safe_for_unsupported_provider(capsys) -> None:
    core = SimpleNamespace(
        tr=lambda text: text,
        responses_state={"provider": "openrouter"},
    )

    assert handle_command(":response status", [], _Client(), "model", core=core) is True
    assert "OpenAI/Azure only" in capsys.readouterr().out
