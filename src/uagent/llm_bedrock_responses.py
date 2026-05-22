from __future__ import annotations

from typing import Any, Optional

from . import tools


def _as_str(x: Any) -> str:
    if x is None:
        return ""
    return str(x)


def _extract_text_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                t = item.get("type")
                if t in ("text", "input_text", "output_text"):
                    parts.append(_as_str(item.get("text", "")))
                elif t in ("image_url", "input_image"):
                    iu = item.get("image_url")
                    if isinstance(iu, dict):
                        parts.append("[image] " + _as_str(iu.get("url", "")))
                    else:
                        parts.append("[image] " + _as_str(iu))
                else:
                    parts.append(_as_str(item))
            else:
                parts.append(_as_str(item))
        return "\n".join([p for p in parts if p is not None])
    return _as_str(content)


def _messages_to_bedrock_input(call_messages: list[dict[str, Any]]) -> str:
    lines: list[str] = []

    for m in call_messages:
        role = _as_str(m.get("role", "user")).lower()

        # tool_calls trace from assistant messages
        tcs = m.get("tool_calls")
        if isinstance(tcs, list) and tcs:
            for tc in tcs:
                if not isinstance(tc, dict):
                    continue
                fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
                name = _as_str(fn.get("name", "unknown"))
                args = _as_str(fn.get("arguments", "{}"))
                lines.append(f"[assistant.tool_call] {name}({args})")

        content_text = _extract_text_content(m.get("content"))

        if role == "system":
            lines.append("[system]")
            if content_text:
                lines.append(content_text)
            continue

        if role == "tool":
            tool_name = _as_str(m.get("name", "unknown"))
            lines.append(f"[tool:{tool_name}]")
            if content_text:
                lines.append(content_text)
            continue

        if role == "assistant":
            lines.append("[assistant]")
            if content_text:
                lines.append(content_text)
            continue

        lines.append("[user]")
        if content_text:
            lines.append(content_text)

    return "\n".join(lines).strip()


def _build_flat_tools(
    tool_specs: Optional[list[dict[str, Any]]] = None,
) -> list[dict[str, Any]]:
    raw_specs = tools.get_tool_specs() if tool_specs is None else tool_specs
    flat_tools: list[dict[str, Any]] = []

    for t in raw_specs or []:
        if not isinstance(t, dict):
            continue
        fn = t.get("function") or {}
        if not isinstance(fn, dict):
            continue
        name = fn.get("name")
        if not name:
            continue
        flat_tools.append(
            {
                "type": t.get("type") or "function",
                "name": name,
                "description": fn.get("description") or "",
                "parameters": fn.get("parameters")
                or {"type": "object", "properties": {}},
            }
        )

    return flat_tools


def build_bedrock_responses_request(
    call_messages: list[dict[str, Any]],
    *,
    send_tools_this_round: bool,
    tool_specs: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Build a Bedrock-specific Responses request payload fragment.

    Bedrock OpenAI-compatible gateways may reject message-list `input` payloads
    for Responses API. This builder sends a single string input transcript.
    """

    input_text = _messages_to_bedrock_input(call_messages)

    req: dict[str, Any] = {
        "input": input_text,
    }

    if send_tools_this_round:
        req_tools = _build_flat_tools(tool_specs=tool_specs)
        if req_tools:
            req["tools"] = req_tools
            req["tool_choice"] = "auto"

    return req
