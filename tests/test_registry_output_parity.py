from __future__ import annotations

from types import SimpleNamespace

from uagent.llm_flow_helpers import _emit_final_answer_if_any
from uagent.llm_round_helpers import _translate_assistant_if_needed
from uagent.runtime.round_identity import DeterministicTestWorkspaceKeyProvider
from uagent.uagent_llm import _try_registry_simple_chat_round


def test_registry_output_can_be_translated_after_responses_stream(monkeypatch) -> None:
    monkeypatch.setattr(
        "uagent.llm_round_helpers.translate_text",
        lambda *args, **kwargs: ("translated", ""),
    )
    config = SimpleNamespace(to_llm="", from_llm="ja")

    translated = _translate_assistant_if_needed(
        assistant_text="original",
        tr_cfg=config,
        use_responses_api=True,
        stream_responses=True,
        stream_output_rendered=False,
    )
    already_rendered = _translate_assistant_if_needed(
        assistant_text="original",
        tr_cfg=config,
        use_responses_api=True,
        stream_responses=True,
        stream_output_rendered=True,
    )

    assert translated == "translated"
    assert already_rendered == "original"


def test_registry_output_is_printed_when_adapter_did_not_render_stream(capsys) -> None:
    saved: list[str] = []
    opened: list[str] = []

    _emit_final_answer_if_any(
        assistant_text="answer",
        use_responses_api=True,
        stream_responses=True,
        stream_output_rendered=False,
        append_result_to_outfile_fn=saved.append,
        try_open_images_from_text_fn=opened.append,
        core=SimpleNamespace(),
    )

    assert capsys.readouterr().out == "answer\n"
    assert saved == ["answer"]
    assert opened == ["answer"]


def test_registry_stream_skip_print_still_renders_reasoning(
    monkeypatch, capsys
) -> None:
    rendered_reasoning: list[str] = []
    saved: list[str] = []
    monkeypatch.setattr(
        "uagent.llm_flow_helpers.render_reasoning",
        lambda text, **_kwargs: rendered_reasoning.append(text),
    )

    _emit_final_answer_if_any(
        assistant_text="already streamed answer",
        reasoning_content="reasoning summary",
        use_responses_api=True,
        stream_responses=True,
        skip_print=True,
        render_reasoning_when_skip_print=True,
        append_result_to_outfile_fn=saved.append,
        try_open_images_from_text_fn=lambda _text: None,
        core=SimpleNamespace(),
    )

    assert rendered_reasoning == ["reasoning summary"]
    assert capsys.readouterr().out == ""
    assert saved == ["already streamed answer"]


def test_final_answer_starts_after_displayed_reasoning_line(
    monkeypatch, capsys
) -> None:
    monkeypatch.setattr("uagent.reasoning_display.get_display_reasoning", lambda: True)
    core = SimpleNamespace(_reasoning_stream_open=False)

    def print_reasoning_delta(text: str) -> None:
        print(text, end="", flush=True)
        core._reasoning_stream_open = not text.endswith("\n")

    def print_stream_delta(text: str) -> None:
        if core._reasoning_stream_open:
            if text != "\n":
                print()
            core._reasoning_stream_open = False
        print(text, end="", flush=True)

    core.print_reasoning_delta = print_reasoning_delta
    core.print_stream_delta = print_stream_delta

    _emit_final_answer_if_any(
        assistant_text="answer",
        reasoning_content="thinking without a trailing newline",
        use_responses_api=False,
        stream_responses=False,
        stream_output_rendered=False,
        append_result_to_outfile_fn=lambda _text: None,
        try_open_images_from_text_fn=lambda _text: None,
        core=core,
        provider="openai",
    )

    assert capsys.readouterr().out == (
        "[Openai Reasoning] thinking without a trailing newline\nanswer\n"
    )


def test_registry_empty_completed_response_falls_back(monkeypatch, tmp_path) -> None:
    class Chat:
        def create(self, **kwargs):
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(message=SimpleNamespace(content="", tool_calls=[]))
                ]
            )

    monkeypatch.setenv("UAGENT_PROVIDER_REGISTRY", "openai")
    monkeypatch.setenv("UAGENT_REASONING", "off")
    monkeypatch.setattr(
        "uagent.runtime.round_identity.CredentialStoreWorkspaceKeyProvider",
        lambda: DeterministicTestWorkspaceKeyProvider(),
    )

    result = _try_registry_simple_chat_round(
        provider="openai",
        client=SimpleNamespace(chat=SimpleNamespace(completions=Chat())),
        depname="gpt-test",
        call_messages=[{"role": "user", "content": "hello"}],
        core=SimpleNamespace(workdir=str(tmp_path), cancellation_token=None),
        use_responses_api=False,
        stream_responses=False,
        send_tools_this_round=False,
        round_count=1,
    )

    assert result is None


def test_registry_retries_low_quality_auto_reasoning_once(
    monkeypatch, tmp_path
) -> None:
    class Chat:
        def __init__(self) -> None:
            self.calls = []
            self.responses = ["short", "A detailed architecture explanation."]

        def create(self, **kwargs):
            self.calls.append(kwargs)
            text = self.responses.pop(0)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=text, tool_calls=[])
                    )
                ]
            )

    chat = Chat()
    monkeypatch.setenv("UAGENT_PROVIDER_REGISTRY", "openai")
    monkeypatch.setenv("UAGENT_REASONING", "auto")
    monkeypatch.setattr(
        "uagent.runtime.round_identity.CredentialStoreWorkspaceKeyProvider",
        lambda: DeterministicTestWorkspaceKeyProvider(),
    )

    result = _try_registry_simple_chat_round(
        provider="openai",
        client=SimpleNamespace(chat=SimpleNamespace(completions=chat)),
        depname="gpt-test",
        call_messages=[
            {"role": "user", "content": "Explain this architecture design."}
        ],
        core=SimpleNamespace(workdir=str(tmp_path), cancellation_token=None),
        use_responses_api=False,
        stream_responses=False,
        send_tools_this_round=False,
        round_count=1,
    )

    assert result == (True, "A detailed architecture explanation.", "", [])
    assert chat.calls[0]["reasoning_effort"] == "minimal"
    assert chat.calls[1]["reasoning_effort"] == "low"
