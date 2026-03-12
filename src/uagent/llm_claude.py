import json
import re
from typing import Any, Dict, List, Optional, Tuple

from . import tools

# Anthropic
try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None


def _parse_claude_model(model_name: str) -> Tuple[Optional[str], Optional[int], Optional[int]]:
    """Best-effort parse Claude model name.

    Examples:
      - claude-opus-4-6   -> ("opus", 4, 6)
      - claude-opus-4.6   -> ("opus", 4, 6)
      - claude-sonnet-4-6 -> ("sonnet", 4, 6)

    Returns: (family, major, minor) where family is one of {"opus","sonnet"}, or None.
    """

    s = (model_name or "").strip().lower()
    m = re.search(r"claude-(opus|sonnet)-(\d+)[\.-](\d+)", s)
    if not m:
        return None, None, None
    fam = m.group(1)
    try:
        major = int(m.group(2))
        minor = int(m.group(3))
    except Exception:
        return fam, None, None
    return fam, major, minor


def _claude_supports_max_effort(model_name: str) -> bool:
    """Per docs, max effort is supported only on Claude Opus 4.6.

    We treat "Opus 4.6 and above" as supported to be forward-compatible.
    """

    fam, major, minor = _parse_claude_model(model_name)
    if fam != "opus":
        return False
    if major is None or minor is None:
        # Unknown version: be conservative.
        return False
    return (major, minor) >= (4, 6)


def _claude_supports_effort(model_name: str) -> bool:
    """Per docs, effort is supported on:

    - Claude Opus 4.6
    - Claude Sonnet 4.6
    - Claude Opus 4.5

    We treat Opus 4.5+ and Sonnet 4.6+ as supported to be forward-compatible.
    """

    fam, major, minor = _parse_claude_model(model_name)
    if fam is None or major is None or minor is None:
        # Unknown model/version: be conservative.
        return False
    if fam == "opus":
        return (major, minor) >= (4, 5)
    if fam == "sonnet":
        return (major, minor) >= (4, 6)
    return False


def build_claude_output_config_for_effort(
    model_name: str,
    effort: str | None,
) -> Optional[Dict[str, Any]]:
    """Map agentcli's internal effort levels to Claude output_config.effort.

    agentcli internal: minimal|low|medium|high|xhigh
    Claude docs:       low|medium|high|max

    Notes:
      - Effort is supported by Claude Opus 4.6, Claude Sonnet 4.6, and Claude Opus 4.5.
      - If the target model does not support effort, return None (omit output_config).

    Mapping:
      - minimal -> low
      - low     -> low
      - medium  -> medium
      - high    -> high
      - xhigh   -> max (only if Opus 4.6+; otherwise fallback to high)
    """

    e = (effort or "").strip().lower()
    if not e:
        return None

    # If the model doesn't support effort, do not send output_config at all.
    if not _claude_supports_effort(model_name):
        return None

    if e in ("minimal", "low"):
        return {"effort": "low"}
    if e == "medium":
        return {"effort": "medium"}
    if e == "high":
        return {"effort": "high"}
    if e == "xhigh":
        if _claude_supports_max_effort(model_name):
            return {"effort": "max"}
        # "max" would error on non-Opus-4.6; fall back.
        return {"effort": "high"}

    return None


def claude_chat_with_tools(
    client: Any,
    model_name: str,
    messages: List[Dict[str, Any]],
    *,
    output_config: Optional[Dict[str, Any]] = None,
    on_output_config_info: Optional[Any] = None,
    on_output_config_fallback: Optional[Any] = None,
) -> Tuple[str, List[Dict[str, Any]]]:
    """Anthropic Claude API を使って tool_calls 付き応答を生成する。

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
                anthropic_messages.append({"role": new_role, "content": new_content_blocks})

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

    # Normalize output_config (best-effort)
    out_cfg = None
    if isinstance(output_config, dict) and output_config:
        out_cfg = output_config

    req_kwargs: Dict[str, Any] = {
        "model": model_name,
        "max_tokens": 4096,
        "messages": anthropic_messages,
    }
    if system_blocks:
        req_kwargs["system"] = system_blocks
    if anthropic_tools:
        req_kwargs["tools"] = anthropic_tools
    if out_cfg is not None:
        req_kwargs["output_config"] = out_cfg
        try:
            eff = None
            if isinstance(out_cfg, dict):
                eff = out_cfg.get("effort")
            msg = f"[Claude] using output_config.effort: {eff or out_cfg}"
            if callable(on_output_config_info):
                on_output_config_info(msg)
            else:
                print(msg)
        except Exception:
            pass

    try:
        response = client.messages.create(**req_kwargs)
    except Exception as e:
        # Some Claude deployments reject output_config (or effort) even when the SDK supports it.
        # Best-effort fallback: retry once without output_config.
        msg = str(e)
        ml = msg.lower()
        if out_cfg is not None and ("output_config" in ml or "output config" in ml):
            try:
                try:
                    if callable(on_output_config_fallback):
                        on_output_config_fallback(
                            "[Claude] output_config rejected; retrying without output_config"
                        )
                    else:
                        print(
                            "[Claude] output_config rejected; retrying without output_config"
                        )
                except Exception:
                    pass
                req_kwargs.pop("output_config", None)
                response = client.messages.create(**req_kwargs)
            except Exception:
                raise e
        else:
            raise

    assistant_text = ""
    tool_calls_list: List[Dict[str, Any]] = []

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
