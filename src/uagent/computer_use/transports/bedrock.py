"""Amazon Bedrock transport for Anthropic Computer Use."""

from __future__ import annotations

from typing import Any


class BedrockTransport:
    """Build Bedrock Runtime and Mantle-compatible request fragments."""

    anthropic_version = "bedrock-2023-05-31"

    def build_request(
        self,
        *,
        model_id: str,
        tool: dict[str, Any],
        beta_header: str | None,
        messages: list[dict[str, Any]],
        max_tokens: int,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "anthropic_version": self.anthropic_version,
            "max_tokens": int(max_tokens),
            "messages": messages,
            "tools": [tool],
        }
        if beta_header:
            body["anthropic_beta"] = [beta_header]
        return {"modelId": model_id, "body": body}

    def headers(self, beta_header: str | None) -> dict[str, str]:
        """Return Bedrock Mantle HTTP headers."""
        return {"anthropic-beta": beta_header} if beta_header else {}
