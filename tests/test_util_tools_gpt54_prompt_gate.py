import pytest

from uagent.util_tools import _use_gpt54_lightweight_tools_prompt


@pytest.fixture
def _clear_model_env(monkeypatch):
    keys = [
        "UAGENT_RESPONSES",
        "UAGENT_AZURE_DEPNAME",
        "UAGENT_OPENAI_DEPNAME",
        "UAGENT_OPENROUTER_DEPNAME",
        "UAGENT_AZURE_DEPLOYMENT",
        "UAGENT_OPENAI_MODEL",
        "UAGENT_MODEL",
    ]
    for k in keys:
        monkeypatch.delenv(k, raising=False)


def test_lightweight_prompt_gate_accepts_openai_depname(_clear_model_env, monkeypatch):
    monkeypatch.setenv("UAGENT_RESPONSES", "1")
    monkeypatch.setenv("UAGENT_OPENAI_DEPNAME", "gpt-5.4")
    assert _use_gpt54_lightweight_tools_prompt() is True


def test_lightweight_prompt_gate_accepts_azure_depname(_clear_model_env, monkeypatch):
    monkeypatch.setenv("UAGENT_RESPONSES", "true")
    monkeypatch.setenv("UAGENT_AZURE_DEPNAME", "gpt-5.4-mini")
    assert _use_gpt54_lightweight_tools_prompt() is True


def test_lightweight_prompt_gate_requires_responses(_clear_model_env, monkeypatch):
    monkeypatch.setenv("UAGENT_OPENROUTER_DEPNAME", "openai/gpt-5.4")
    assert _use_gpt54_lightweight_tools_prompt() is False
