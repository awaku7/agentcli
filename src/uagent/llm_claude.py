import json
from typing import Any, Dict, List, Tuple

from . import tools

# Anthropic
try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None


def claude_chat_with_tools(
    client: Any,
    model_name: str,
    messages: List[Dict[str, Any]],
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Anthropic Claude API を使って tool_calls 付き応答を生成する。
    OpenAI 形式の messages を Anthropic 形式に変換してからリクエストする。

    Returns:
        assistant_text: アシスタントのテキスト応答
        tool_calls_list: OpenAI 互換の tool_calls リスト
    """
    if Anthropic is None:
        raise RuntimeError(
            "anthropic パッケージがインストールされていません。（pip install anthropic が必要です）"
        )

    anthropic_messages: List[Dict[str, Any]] = []
    system_content = ""

    # OpenAI 形式のメッセージ履歴を Anthropic 形式に変換
    # - System は system パラメータへ
    # - User/Tool -> User role (Tool は tool_result ブロック)
    # - Assistant -> Assistant role (tool_calls は tool_use ブロック)
    # - 同一ロールの連続は 1 つのメッセージに結合する

    for m in messages:
        role = m.get("role")
        content = m.get("content") or ""

        if role == "system":
            system_content += content + "\n"
            continue

        new_role = None
        new_content_blocks: List[Dict[str, Any]] = []

        if role == "user":
            new_role = "user"
            new_content_blocks.append({"type": "text", "text": content})

        elif role == "assistant":
            new_role = "assistant"
            if content:
                new_content_blocks.append({"type": "text", "text": content})

            tool_calls = m.get("tool_calls", [])
            for tc in tool_calls:
                fn = tc.get("function", {})
                t_name = fn.get("name", "")
                t_args = fn.get("arguments", "{}")
                t_id = tc.get("id")
                try:
                    t_input = json.loads(t_args)
                except Exception:
                    t_input = {}

                new_content_blocks.append(
                    {"type": "tool_use", "id": t_id, "name": t_name, "input": t_input}
                )

        elif role == "tool":
            new_role = "user"
            new_content_blocks.append(
                {
                    "type": "tool_result",
                    "tool_use_id": m.get("tool_call_id"),
                    "content": content,
                }
            )

        if new_role:
            if anthropic_messages and anthropic_messages[-1]["role"] == new_role:
                # 直前のメッセージと同じロールなら結合 (content は常に list)
                anthropic_messages[-1]["content"].extend(new_content_blocks)
            else:
                # 新規メッセージ
                anthropic_messages.append(
                    {"role": new_role, "content": new_content_blocks}
                )

    anthropic_tools = []
    for spec in tools.get_tool_specs():
        fn = spec.get("function", {})
        name = fn.get("name", "")
        desc = fn.get("description", "")
        params = fn.get("parameters", {})
        anthropic_tools.append(
            {
                "name": name,
                "description": desc,
                "input_schema": params,
            }
        )

    # システムプロンプトをキャッシュ対象にする
    system_blocks = []
    if system_content.strip():
        system_blocks.append(
            {
                "type": "text",
                "text": system_content.strip(),
                "cache_control": {"type": "ephemeral"},
            }
        )

    # 最初の user メッセージの最初のテキストブロックにキャッシュを適用する
    first_user_msg = next((m for m in anthropic_messages if m["role"] == "user"), None)
    if first_user_msg and isinstance(first_user_msg["content"], list):
        for block in first_user_msg["content"]:
            if block.get("type") == "text":
                block["cache_control"] = {"type": "ephemeral"}
                break

    response = client.messages.create(
        model=model_name,
        max_tokens=4096,
        system=system_blocks if system_blocks else None,
        messages=anthropic_messages,
        tools=anthropic_tools if anthropic_tools else None,
    )

    assistant_text = ""
    tool_calls_list = []

    for block in response.content:
        if block.type == "text":
            assistant_text += block.text
        elif block.type == "tool_use":
            tool_calls_list.append(
                {
                    "id": block.id,
                    "type": "function",
                    "function": {
                        "name": block.name,
                        "arguments": json.dumps(block.input),
                    },
                }
            )

    return assistant_text, tool_calls_list
