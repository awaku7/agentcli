"""Application services for non-mutating Responses command operations."""

from __future__ import annotations

from typing import Any


class ResponsesCommandService:
    """Call Responses management operations without formatting or printing."""

    @staticmethod
    def build_token_count_payload(
        messages: list[dict[str, Any]], provider: str
    ) -> tuple[str | None, list[dict[str, Any]], list[dict[str, Any]] | None]:
        from ..providers.llm_openai_responses import build_responses_request

        return build_responses_request(
            messages,
            send_tools_this_round=True,
            provider=provider,
            previous_response_id=None,
        )

    @classmethod
    def count_tokens(
        cls,
        manager: Any,
        messages: list[dict[str, Any]],
        *,
        provider: str,
        previous_response_id: str = "",
        last_usage: dict[str, Any] | None = None,
    ) -> Any:
        """Count input tokens and attach known usage from the last response."""
        instructions, responses_input, responses_tools = cls.build_token_count_payload(
            messages, provider
        )
        count_input = responses_input or [{"role": "user", "content": " "}]
        result = manager.count_input_tokens(
            input=count_input,
            tools=responses_tools,
            instructions=instructions,
            previous_response_id=previous_response_id if not responses_input else None,
        )
        if isinstance(last_usage, dict) and last_usage:
            return {"input_token_count": result, "last_response_usage": last_usage}
        return result

    @staticmethod
    def compact(manager: Any, response_id: str) -> Any:
        return manager.compact(response_id)

    @staticmethod
    def list_items(manager: Any, response_id: str) -> Any:
        return manager.list_input_items(response_id)


__all__ = ["ResponsesCommandService"]
