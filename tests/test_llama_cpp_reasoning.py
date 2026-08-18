from __future__ import annotations

from uagent.llm_round_helpers import _apply_llama_cpp_reasoning_kwargs


def test_llama_cpp_reasoning_off_disables_thinking(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_REASONING", "off")
    kwargs = {}
    _apply_llama_cpp_reasoning_kwargs(kwargs)
    assert kwargs == {
        "extra_body": {
            "reasoning_format": "deepseek",
            "chat_template_kwargs": {"enable_thinking": False},
        },
    }


def test_llama_cpp_reasoning_effort_enables_thinking(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_REASONING", "high")
    kwargs = {}
    _apply_llama_cpp_reasoning_kwargs(kwargs)
    assert kwargs == {
        "extra_body": {
            "reasoning_format": "deepseek",
            "chat_template_kwargs": {"enable_thinking": True},
        },
    }


def test_llama_cpp_reasoning_auto_keeps_server_default(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_REASONING", "auto")
    kwargs = {}
    _apply_llama_cpp_reasoning_kwargs(kwargs)
    assert kwargs == {"extra_body": {"reasoning_format": "deepseek"}}
