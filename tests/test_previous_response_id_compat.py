from __future__ import annotations

from types import SimpleNamespace


from uagent.providers.llm_openrouter_responses import apply_openrouter_responses_compat
from uagent.providers.util_providers import _normalize_openrouter_send_kwargs
from uagent.uagent_llm import run_llm_rounds


def test_openrouter_responses_compat_strips_previous_response_id() -> None:
    kwargs = {
        "model": "gpt-5.3",
        "input": "hi",
        "previous_response_id": "resp_abc",
        "context_management": [{"type": "compaction", "compact_threshold": 1000}],
    }
    apply_openrouter_responses_compat(kwargs, provider="openrouter", depname="gpt-5.3")
    assert "previous_response_id" not in kwargs
    assert "context_management" not in kwargs


def test_normalize_openrouter_send_kwargs_strips_previous_response_id() -> None:
    out = _normalize_openrouter_send_kwargs(
        {
            "model": "gpt-5.3",
            "input": "hi",
            "previous_response_id": "resp_abc",
            "context_management": [{"type": "compaction"}],
        }
    )
    assert "previous_response_id" not in out
    assert "context_management" not in out


class _FailThenOkResponses:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1 and kwargs.get("previous_response_id"):
            # Simulate OpenRouter/OpenAI SDK validation failure path.
            import httpx
            from openai import APIResponseValidationError

            body = {
                "error": {
                    "code": "invalid_prompt",
                    "message": "Invalid Responses API request",
                },
                "metadata": {
                    "raw": (
                        '[{"path":["previous_response_id"],'
                        '"message":"Invalid input: expected null, received string"}]'
                    )
                },
            }
            req = httpx.Request("POST", "https://example.com/v1/responses")
            resp = httpx.Response(400, json=body, request=req)
            raise APIResponseValidationError(
                response=resp,
                body=body,
                message="Response validation failed: previous_response_id",
            )
        return SimpleNamespace(
            output=[
                SimpleNamespace(
                    type="message",
                    content=[SimpleNamespace(type="output_text", text="ok")],
                )
            ]
        )


class _DummyChat:
    def __init__(self) -> None:
        self.completions = SimpleNamespace(
            create=lambda **_k: (_ for _ in ()).throw(AssertionError("chat path"))
        )


class _DummyClient:
    def __init__(self) -> None:
        self.responses = _FailThenOkResponses()
        self.chat = _DummyChat()


class _DummyCore:
    SYSTEM_PROMPT = "sys"
    _is_web = False
    tools_enabled = True
    responses_state: dict

    def __init__(self) -> None:
        self.responses_state = {
            "previous_response_id": "resp_stale_1",
            "provider": "openai",
            "model": "gpt-5.4-nano",
        }

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


def test_run_llm_rounds_retries_without_previous_response_id(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_STREAMING", "0")
    monkeypatch.setenv("UAGENT_RESPONSES", "1")
    monkeypatch.setenv("UAGENT_USE_TOOL", "0")

    client = _DummyClient()
    core = _DummyCore()
    # Keep responses_state on core and module in sync for the helper.
    import uagent.core as core_mod

    monkeypatch.setattr(core_mod, "responses_state", core.responses_state)
    monkeypatch.setattr(core_mod, "_save_responses_state", lambda: None)

    messages = [{"role": "user", "content": "hello"}]
    run_llm_rounds(
        "openai",
        client,
        "gpt-5.4-nano",
        messages,
        core=core,
        make_client_fn=lambda _core: (None, client, None),
        append_result_to_outfile_fn=lambda text: None,
        try_open_images_from_text_fn=lambda text: None,
    )

    assert len(client.responses.calls) >= 2
    assert client.responses.calls[0].get("previous_response_id") == "resp_stale_1"
    assert "previous_response_id" not in client.responses.calls[1]
    assert "previous_response_id" not in core.responses_state


def test_openrouter_never_sends_previous_response_id(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_STREAMING", "0")
    monkeypatch.setenv("UAGENT_RESPONSES", "1")
    monkeypatch.setenv("UAGENT_USE_TOOL", "0")

    class _OkResponses:
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

    class _Client:
        def __init__(self) -> None:
            self.responses = _OkResponses()
            self.chat = _DummyChat()

    client = _Client()
    core = _DummyCore()
    import uagent.core as core_mod

    monkeypatch.setattr(core_mod, "responses_state", core.responses_state)
    monkeypatch.setattr(core_mod, "_save_responses_state", lambda: None)

    run_llm_rounds(
        "openrouter",
        client,
        "gpt-5.3",
        [{"role": "user", "content": "hello"}],
        core=core,
        make_client_fn=lambda _core: (None, client, None),
        append_result_to_outfile_fn=lambda text: None,
        try_open_images_from_text_fn=lambda text: None,
    )

    assert client.responses.calls
    assert "previous_response_id" not in client.responses.calls[0]
