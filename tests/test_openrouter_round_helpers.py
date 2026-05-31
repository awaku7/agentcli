from __future__ import annotations

from types import SimpleNamespace

import pytest

from uagent.uagent_llm import run_llm_rounds


class _DummyResponses:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            output=[
                SimpleNamespace(
                    type="message",
                    content=[SimpleNamespace(type="output_text", text="ok")],
                )
            ]
        )


class _DummyOpenAICompletions:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        msg = SimpleNamespace(content="ok", tool_calls=[])
        choice = SimpleNamespace(message=msg)
        return SimpleNamespace(choices=[choice])


class _DummyChat:
    def __init__(self) -> None:
        self.completions = _DummyOpenAICompletions()


class _DummyFullClient:
    def __init__(self) -> None:
        self.responses = _DummyResponses()
        self.chat = _DummyChat()


class _DummyCore:
    SYSTEM_PROMPT = "sys"
    _is_web = False

    def set_status(self, busy, label):
        return None

    def log_message(self, msg):
        return None

    def sanitize_messages_for_tools(self, messages):
        return messages

    def compress_history_with_llm(self, client, depname, messages, keep_last):
        return messages

    def rewrite_current_log_from_messages(self, messages):
        return None

    def build_tools_system_prompt(self, tool_specs):
        return "tools"


@pytest.mark.parametrize(
    "responses_env, expected_path",
    [
        ("1", "responses"),
        (None, "chat"),
    ],
)
def test_run_llm_rounds_openrouter_routes_to_expected_api(
    monkeypatch: pytest.MonkeyPatch,
    responses_env: str | None,
    expected_path: str,
) -> None:
    monkeypatch.setenv("UAGENT_STREAMING", "0")
    if responses_env is None:
        monkeypatch.delenv("UAGENT_RESPONSES", raising=False)
    else:
        monkeypatch.setenv("UAGENT_RESPONSES", responses_env)

    client = _DummyFullClient()
    core = _DummyCore()
    messages = [{"role": "user", "content": "hello"}]

    run_llm_rounds(
        "openrouter",
        client,
        "gpt-5.3",
        messages,
        core=core,
        make_client_fn=lambda _core: (None, client, None),
        append_result_to_outfile_fn=lambda text: None,
        try_open_images_from_text_fn=lambda text: None,
    )

    if expected_path == "responses":
        assert client.responses.calls
        assert client.responses.calls[0]["model"] == "gpt-5.3"
        assert not client.chat.completions.calls
    else:
        assert client.chat.completions.calls
        assert client.chat.completions.calls[0]["model"] == "gpt-5.3"
        assert not client.responses.calls
