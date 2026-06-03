from __future__ import annotations

import json
import re
from typing import Any, Optional

from .env_utils import env_get
from .i18n import _
from . import tools

# Anthropic
try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None


def _parse_claude_model(
    model_name: str,
) -> tuple[Optional[str], Optional[int], Optional[int]]:
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
) -> Optional[dict[str, Any]]:
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
    messages: list[dict[str, Any]],
    *,
    output_config: Optional[dict[str, Any]] = None,
    on_output_config_info: Optional[Any] = None,
    on_output_config_fallback: Optional[Any] = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Anthropic Claude API を使って tool_calls 付き応答を生成する。

    OpenAI 形式の messages を Anthropic 形式に変換してからリクエストする。

    Returns:
        assistant_text: アシスタントのテキスト応答
        tool_calls_list: OpenAI 互換の tool_calls リスト
    """

    if Anthropic is None:
        raise RuntimeError(_("anthropic package is not installed."))

    anthropic_messages: list[dict[str, Any]] = []
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
        new_content_blocks: list[dict[str, Any]] = []

        if role == "user":
            new_role = "user"
            if isinstance(content, str):
                new_content_blocks.append({"type": "text", "text": content})
            elif isinstance(content, list):
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    item_type = item.get("type")
                    if item_type == "text":
                        new_content_blocks.append({"type": "text", "text": item.get("text", "")})
                    elif item_type == "image_url":
                        img_url_obj = item.get("image_url") or {}
                        url = img_url_obj.get("url") or ""
                        if url.startswith("data:"):
                            try:
                                header, data = url.split(",", 1)
                                mime_type = header.split(";")[0].split(":")[1]
                                new_content_blocks.append({
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": mime_type,
                                        "data": data,
                                    }
                                })
                            except Exception:
                                pass
                        else:
                            new_content_blocks.append({
                                "type": "text",
                                "text": f"[Image URL: {url}]"
                            })

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

    # Normalize output_config (best-effort)
    out_cfg = None
    if isinstance(output_config, dict) and output_config:
        out_cfg = output_config

    # Resolve temperature (only set if explicitly configured via UAGENT_CLAUDE_TEMPERATURE)
    claude_temp = None
    temp_env = (env_get("UAGENT_CLAUDE_TEMPERATURE") or "").strip()
    if temp_env:
        try:
            claude_temp = float(temp_env)
        except ValueError:
            pass

    # Resolve max_tokens (dynamic based on environment variable or model/thinking)
    max_tokens = 4096
    max_tokens_env = (env_get("UAGENT_MAX_TOKENS") or "").strip()
    if max_tokens_env:
        try:
            max_tokens = int(max_tokens_env)
        except ValueError:
            pass
    else:
        # If model is Claude 3.7+ or Claude 4+ or output_config (thinking) is enabled, default to 8192
        # Matches "3-7", "3.7", "3-8", "3.8", "3-9", "3.9", "claude-4", etc.
        is_modern_claude = bool(
            re.search(r"3[\.-][7-9]", model_name) or
            re.search(r"claude-[4-9]", model_name)
        )
        if is_modern_claude or out_cfg is not None:
            max_tokens = 8192

    req_kwargs: dict[str, Any] = {
        "model": model_name,
        "max_tokens": max_tokens,
        "messages": anthropic_messages,
    }
    # If output_config (thinking/effort) is used, temperature must be omitted.
    # Otherwise, only set temperature if explicitly configured.
    if claude_temp is not None and out_cfg is None:
        req_kwargs["temperature"] = claude_temp

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
        msg = str(e)
        ml = msg.lower()

        # Case 1: Temperature is rejected/deprecated
        if "temperature" in ml and "temperature" in req_kwargs:
            try:
                try:
                    if callable(on_output_config_fallback):
                        on_output_config_fallback(
                            "[Claude] temperature rejected; retrying without temperature"
                        )
                    else:
                        print(
                            "[Claude] temperature rejected; retrying without temperature"
                        )
                except Exception:
                    pass
                req_kwargs.pop("temperature", None)
                response = client.messages.create(**req_kwargs)
            except Exception as retry_exc:
                retry_msg = str(retry_exc)
                retry_ml = retry_msg.lower()
                if out_cfg is not None and (
                    "output_config" in retry_ml or "output config" in retry_ml
                ):
                    try:
                        req_kwargs.pop("output_config", None)
                        response = client.messages.create(**req_kwargs)
                    except Exception:
                        raise e from retry_exc
                else:
                    raise e from retry_exc

        # Case 2: output_config is rejected
        elif out_cfg is not None and ("output_config" in ml or "output config" in ml):
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
                # If we removed output_config, we can restore temperature if it wasn't rejected
                req_kwargs["temperature"] = claude_temp
                try:
                    response = client.messages.create(**req_kwargs)
                except Exception as retry_exc:
                    retry_msg = str(retry_exc)
                    retry_ml = retry_msg.lower()
                    if "temperature" in retry_ml:
                        req_kwargs.pop("temperature", None)
                        response = client.messages.create(**req_kwargs)
                    else:
                        raise e from retry_exc
            except Exception as retry_exc:
                raise e from retry_exc
        else:
            raise

    assistant_text = ""
    tool_calls_list: list[dict[str, Any]] = []
    thinking_text = ""

    for block in response.content:
        if block.type == "text":
            assistant_text += block.text
        elif block.type == "thinking":
            thinking_text += block.thinking
            # 思考プロセスをコンソールに表示する
            print(f"\n[Claude Thinking]\n{block.thinking}\n")
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

    # 思考プロセスが検出された場合、assistant_text の先頭に埋め込むことで
    # 上位モジュールや会話履歴に思考プロセスを正しく伝播させる
    if thinking_text:
        assistant_text = f"<thinking>\n{thinking_text}\n</thinking>\n" + assistant_text

    return assistant_text, tool_calls_list
