from __future__ import annotations

from types import SimpleNamespace

import pytest

from uagent.providers.llm_deepseek_responses import apply_deepseek_responses_compat
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

    def __init__(self) -> None:
        self.responses_state: dict = {}

    def set_status(self, busy, label):
        return None

    def log_message(self, msg):
        return None

    def get_env(self, name):
        return ""

    def get_env_url(self, name, default=""):
        return default

    def sanitize_messages_for_tools(self, messages):
        return messages

    def compress_history_with_llm(self, client, depname, messages, keep_last):
        return messages

    def rewrite_current_log_from_messages(self, messages):
        return None

    def build_tools_system_prompt(self, tool_specs):
        return "tools"


def _run_deepseek(
    monkeypatch: pytest.MonkeyPatch,
    responses_env: str,
    reasoning: str | None = None,
) -> _DummyFullClient:
    monkeypatch.setenv("UAGENT_STREAMING", "0")
    monkeypatch.setenv("UAGENT_RESPONSES", responses_env)
    if reasoning is not None:
        monkeypatch.setenv("UAGENT_REASONING", reasoning)
    else:
        monkeypatch.delenv("UAGENT_REASONING", raising=False)

    client = _DummyFullClient()
    core = _DummyCore()
    messages = [{"role": "user", "content": "hello"}]

    run_llm_rounds(
        "deepseek",
        client,
        "deepseek-v4-flash",
        messages,
        core=core,
        make_client_fn=lambda _core: (None, client, None),
        append_result_to_outfile_fn=lambda text: None,
        try_open_images_from_text_fn=lambda text: None,
    )
    return client


def test_run_llm_rounds_deepseek_routes_to_responses_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _run_deepseek(monkeypatch, "1")
    assert client.responses.calls
    assert not client.chat.completions.calls
    kwargs = client.responses.calls[0]
    assert kwargs["model"] == "deepseek-v4-flash"
    # context_management is not supported by DeepSeek and must be removed.
    assert "context_management" not in kwargs


def test_run_llm_rounds_deepseek_chat_api_when_responses_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _run_deepseek(monkeypatch, "0")
    assert client.chat.completions.calls
    assert not client.responses.calls
    assert client.chat.completions.calls[0]["model"] == "deepseek-v4-flash"


@pytest.mark.parametrize(
    ("reasoning", "expected_effort"),
    [
        ("medium", "high"),
        ("high", "high"),
        ("xhigh", "max"),
    ],
)
def test_run_llm_rounds_deepseek_effort_mapping(
    monkeypatch: pytest.MonkeyPatch,
    reasoning: str,
    expected_effort: str,
) -> None:
    client = _run_deepseek(monkeypatch, "1", reasoning=reasoning)
    kwargs = client.responses.calls[0]
    assert kwargs["reasoning"] == {"effort": expected_effort}


def test_run_llm_rounds_deepseek_effort_falls_back_to_valid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Simulate a model whose llmcapa capability only accepts {"max"}.
    # medium maps to "high", which is not valid, so it must fall back to "max".
    from uagent.providers import llm_deepseek

    monkeypatch.setattr(
        llm_deepseek,
        "_get_valid_deepseek_efforts",
        lambda model: frozenset({"max"}),
    )
    client = _run_deepseek(monkeypatch, "1", reasoning="medium")
    kwargs = client.responses.calls[0]
    assert kwargs["reasoning"] == {"effort": "max"}


def test_apply_deepseek_responses_compat_removes_unsupported_keys() -> None:
    kwargs = {
        "context_management": [
            {"type": "compaction", "compact_threshold": 1000}
        ],
        "text": {"verbosity": "high"},
        "reasoning": {"effort": "high"},
    }
    apply_deepseek_responses_compat(kwargs, provider="deepseek", depname="x")
    assert "context_management" not in kwargs
    assert "text" not in kwargs
    assert kwargs["reasoning"] == {"effort": "high"}


def test_apply_deepseek_responses_compat_keeps_remaining_text_keys() -> None:
    kwargs = {"text": {"verbosity": "high", "other": 1}}
    apply_deepseek_responses_compat(kwargs, provider="deepseek", depname="x")
    assert kwargs["text"] == {"other": 1}


def test_apply_deepseek_responses_compat_noop_for_other_providers() -> None:
    kwargs = {
        "context_management": [{"type": "compaction"}],
        "text": {"verbosity": "high"},
    }
    apply_deepseek_responses_compat(kwargs, provider="openai", depname="x")
    assert "context_management" in kwargs
    assert kwargs["text"] == {"verbosity": "high"}
