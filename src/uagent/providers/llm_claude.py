from __future__ import annotations

import json
import re
from typing import Any, Optional

from ..env_utils import env_get
from ..i18n import _
from .. import tools

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
      - claude-3-7-sonnet -> ("sonnet", 3, 7)
      - claude-fable-5    -> ("fable", 5, 0)

    Returns: (family, major, minor) where family is one of {"opus","sonnet","fable"}, or None.
    """

    s = (model_name or "").strip().lower()

    # 1. claude-fable-5 or similar (family-major-minor or family-major)
    m_fable = re.search(r"claude-(fable|opus|sonnet|haiku)-(\d+)(?:[\.-](\d+))?", s)
    if m_fable:
        fam = m_fable.group(1)
        try:
            major = int(m_fable.group(2))
            minor = int(m_fable.group(3)) if m_fable.group(3) else 0
            return fam, major, minor
        except Exception:
            pass

    # 2. claude-3-7-sonnet or similar (major-minor-family)
    m_num_first = re.search(r"claude-(\d+)[\.-](\d+)-(sonnet|opus|haiku|fable)", s)
    if m_num_first:
        try:
            major = int(m_num_first.group(1))
            minor = int(m_num_first.group(2))
            fam = m_num_first.group(3)
            return fam, major, minor
        except Exception:
            pass

    # 3. Fallback for simple major version like claude-3-sonnet
    m_simple = re.search(r"claude-(\d+)-(sonnet|opus|haiku|fable)", s)
    if m_simple:
        try:
            major = int(m_simple.group(1))
            fam = m_simple.group(2)
            return fam, major, 0
        except Exception:
            pass

    # 4. Classic format
    m = re.search(r"claude-(opus|sonnet|haiku|fable)-(\d+)[\.-](\d+)", s)
    if not m:
        return None, None, None
    fam = m.group(1)
    try:
        major = int(m.group(2))
        minor = int(m.group(3))
    except Exception:
        return fam, None, None
    return fam, major, minor


# Models that rejected thinking.type=enabled in this session (per-process memo).
# These require thinking.type=adaptive + output_config.effort.
_ADAPTIVE_THINKING_MODELS: set[str] = set()


def _claude_requires_adaptive_thinking(model_name: str) -> bool:
    """Return True if the model requires thinking.type=adaptive.

    Per API errors, newer models (Fable 5+ / Claude 5+) reject
    thinking.type=enabled and require adaptive + output_config.effort.
    Also returns True if the model was memoized after a runtime rejection.
    """

    if model_name in _ADAPTIVE_THINKING_MODELS:
        return True
    fam, major, _minor = _parse_claude_model(model_name)
    if fam == "fable":
        return True
    if major is not None and major >= 5:
        return True
    return False


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

    - Claude Fable 5+
    - Claude 3.7+ (Sonnet, Opus, etc.)
    - Claude Opus 4.6
    - Claude Sonnet 4.6
    - Claude Opus 4.5

    We treat Opus 4.5+ and Sonnet 4.6+ as supported to be forward-compatible.
    """
    try:
        import llmcapa

        cap = llmcapa.get(model_name)
        if cap is not None and cap.supports_reasoning_effort:
            return True
    except Exception:
        pass

    fam, major, minor = _parse_claude_model(model_name)
    if fam is None or major is None or minor is None:
        # Fallback: if model name contains "3-7", "3.7", "claude-4", "fable", "claude-5", assume it supports effort
        s = (model_name or "").strip().lower()
        if any(x in s for x in ("3-7", "3.7", "claude-4", "fable", "claude-5")):
            return True
        return False

    if fam == "fable" and major >= 5:
        return True
    if major == 3 and minor >= 7:
        return True
    if major >= 4:
        return True
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
                        new_content_blocks.append(
                            {"type": "text", "text": item.get("text", "")}
                        )
                    elif item_type == "image_url":
                        img_url_obj = item.get("image_url") or {}
                        url = img_url_obj.get("url") or ""
                        if url.startswith("data:"):
                            try:
                                header, data = url.split(",", 1)
                                mime_type = header.split(";")[0].split(":")[1]
                                new_content_blocks.append(
                                    {
                                        "type": "image",
                                        "source": {
                                            "type": "base64",
                                            "media_type": mime_type,
                                            "data": data,
                                        },
                                    }
                                )
                            except Exception:
                                pass
                        else:
                            new_content_blocks.append(
                                {"type": "text", "text": f"[Image URL: {url}]"}
                            )

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

    # If model is Claude 3.7+ or Claude 4+ or Fable 5+, treat it as a modern Claude model.
    # Matches "3-7", "3.7", "3-8", "3.8", "3-9", "3.9", "claude-4", "fable", "claude-5", etc.
    is_modern_claude = bool(
        re.search(r"3[\.-][7-9]", model_name)
        or re.search(r"claude-[4-9]", model_name)
        or "fable" in model_name.lower()
        or "claude-5" in model_name.lower()
    )

    # Resolve max_tokens (dynamic based on environment variable or model/thinking)
    max_tokens = 4096
    max_tokens_env = (env_get("UAGENT_MAX_TOKENS") or "").strip()
    if max_tokens_env:
        try:
            max_tokens = int(max_tokens_env)
        except ValueError:
            pass
    else:
        # If model is modern Claude or output_config (thinking) is enabled, default to 8192
        if is_modern_claude or out_cfg is not None:
            max_tokens = 8192

    # Resolve thinking parameter for modern Claude models (Claude 3.7+, Claude 4+, Fable 5+)
    thinking_param = None
    use_adaptive_thinking = False
    if (
        is_modern_claude
        and out_cfg is not None
        and _claude_requires_adaptive_thinking(model_name)
    ):
        # Newer models (Fable 5+ / Claude 5+) reject thinking.type=enabled.
        # Send thinking.type=adaptive and keep output_config.effort.
        use_adaptive_thinking = True
        thinking_param = {"type": "adaptive"}
        claude_temp = None
    elif is_modern_claude and out_cfg is not None:
        eff = out_cfg.get("effort", "medium")
        # Map effort to budget_tokens
        budget = 4096
        if eff == "low":
            budget = 1024
        elif eff == "medium":
            budget = 4096
        elif eff in ("high", "max"):
            budget = 6144

        # Anthropic requires max_tokens > thinking.budget_tokens.
        # If UAGENT_MAX_TOKENS is set too small, shrink the budget; if it
        # cannot be at least 1024 (API minimum), disable thinking entirely.
        if max_tokens <= budget:
            budget = max_tokens - 1024

        if budget >= 1024:
            thinking_param = {"type": "enabled", "budget_tokens": budget}
            # When thinking is enabled, temperature must be omitted or set to 1.0.
            # We omit it by setting claude_temp to None.
            claude_temp = None

    req_kwargs: dict[str, Any] = {
        "model": model_name,
        "max_tokens": max_tokens,
        "messages": anthropic_messages,
    }
    # If output_config (thinking/effort) is used, temperature must be omitted.
    # Otherwise, only set temperature if explicitly configured.
    if claude_temp is not None and out_cfg is None and thinking_param is None:
        req_kwargs["temperature"] = claude_temp

    if system_blocks:
        req_kwargs["system"] = system_blocks
    if anthropic_tools:
        req_kwargs["tools"] = anthropic_tools

    if use_adaptive_thinking and thinking_param is not None:
        req_kwargs["thinking"] = thinking_param
        if out_cfg is not None:
            req_kwargs["output_config"] = out_cfg
        try:
            eff = out_cfg.get("effort") if isinstance(out_cfg, dict) else None
            msg = f"[Claude] using thinking.type=adaptive, output_config.effort: {eff}"
            if callable(on_output_config_info):
                on_output_config_info(msg)
            else:
                print(msg)
        except Exception:
            pass
    elif thinking_param is not None:
        req_kwargs["thinking"] = thinking_param
        try:
            msg = f"[Claude] using thinking.budget_tokens: {thinking_param.get('budget_tokens')}"
            if callable(on_output_config_info):
                on_output_config_info(msg)
            else:
                print(msg)
        except Exception:
            pass
    elif out_cfg is not None:
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

        # Case 1.5: thinking.type "enabled" is not supported (newer models
        # require thinking.type "adaptive" + output_config.effort).
        elif "thinking" in req_kwargs and (
            "thinking.type.enabled" in ml
            or ("thinking.type" in ml and "adaptive" in ml)
        ):
            try:
                # Memoize: this model needs adaptive from the first request next time.
                _ADAPTIVE_THINKING_MODELS.add(model_name)
                fb_msg = (
                    "[Claude] thinking.type=enabled rejected; "
                    "retrying with thinking.type=adaptive + output_config.effort"
                )
                try:
                    if callable(on_output_config_fallback):
                        on_output_config_fallback(fb_msg)
                    else:
                        print(fb_msg)
                except Exception:
                    pass
                req_kwargs["thinking"] = {"type": "adaptive"}
                if out_cfg is not None:
                    req_kwargs["output_config"] = out_cfg
                try:
                    response = client.messages.create(**req_kwargs)
                except Exception as retry_exc:
                    retry_ml = str(retry_exc).lower()
                    # If output_config is also rejected, drop it and retry once more.
                    if "output_config" in retry_ml or "output config" in retry_ml:
                        req_kwargs.pop("output_config", None)
                        response = client.messages.create(**req_kwargs)
                    else:
                        raise e from retry_exc
            except Exception as retry_exc:
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
                if claude_temp is not None:
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
            _t = getattr(block, "thinking", None) or ""
            thinking_text += _t
            # 思考プロセスをコンソールに表示する（空ブロックは見出しを出さない）
            if _t.strip():
                print(f"\n[Claude Thinking]\n{_t}\n")
            elif (env_get("UAGENT_DEBUG") or "").strip():
                try:
                    print(f"\n[Claude Thinking] (empty thinking block) raw={block!r}\n")
                except Exception:
                    pass
        elif block.type == "redacted_thinking":
            # 暗号化された思考ブロック（内容は表示不可）
            if (env_get("UAGENT_DEBUG") or "").strip():
                print("\n[Claude Thinking] (redacted_thinking block)\n")
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
