from __future__ import annotations

import json
from unittest.mock import MagicMock
import pytest

from uagent.tools.sub_agent_tool import run_tool, SubAgentRunner


def test_sub_agent_translator_smoke(monkeypatch: pytest.MonkeyPatch) -> None:
    # Mock the LLM call to return a structured JSON response for the translator
    mock_response = {
        "status": "success",
        "role": "translator",
        "summary": "Translated the welcome message to Spanish.",
        "translated_text": "¡Bienvenido a uag!",
        "notes": "Preserved the formatting and tone.",
    }

    # Mock _call_llm_single_round on SubAgentRunner
    mock_call = MagicMock(return_value=json.dumps(mock_response, ensure_ascii=False))
    monkeypatch.setattr(SubAgentRunner, "_call_llm_single_round", mock_call)

    # Mock make_client to avoid actual API calls
    mock_client_instance = MagicMock()
    mock_make_client = MagicMock(
        return_value=("openai", mock_client_instance, "gpt-4o")
    )
    monkeypatch.setattr("uagent.tools.sub_agent_tool.make_client", mock_make_client)

    # Execute the translator sub-agent
    args = {
        "agent_name": "translator",
        "task": "Translate 'Welcome to uag!' into Spanish.",
        "response_mode": "json",
        "required_fields": ["status", "role", "summary", "translated_text", "notes"],
        "strict_output": True,
    }

    result_str = run_tool(args)
    result = json.loads(result_str)

    # Assertions
    assert result["status"] == "success"
    assert result["role"] == "translator"
    assert "¡Bienvenido a uag!" in result["translated_text"]
    assert result["summary"] == "Translated the welcome message to Spanish."

    # Verify the mock was called with correct parameters
    mock_call.assert_called_once()
    called_args, called_kwargs = mock_call.call_args
    assert called_kwargs["model_name"] == "gpt-4o"
    assert (
        "You are a specialized sub-agent for translation and localization."
        in called_kwargs["system_prompt"]
    )
    assert "Translate 'Welcome to uag!' into Spanish." in called_kwargs["user_prompt"]
