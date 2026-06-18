from __future__ import annotations

import json
from typing import Any

from ..env_utils import env_get
from ..llm_image_helpers import build_image_default_prompt
from ..i18n import _

from .. import tools


# -----------------------------
# Gemini JSON Schema 変換（修正版）
# -----------------------------
def _gemini_map_type(t: str) -> str:
    """JSON Schema/OpenAPI の type を google-genai の enum 表記へ正規化する。"""
    if not t:
        return "TYPE_UNSPECIFIED"
    u = str(t).strip()
    if not u:
        return "TYPE_UNSPECIFIED"

    u_up = u.upper()
    if u_up in (
        "TYPE_UNSPECIFIED",
        "STRING",
        "NUMBER",
        "INTEGER",
        "BOOLEAN",
        "ARRAY",
        "OBJECT",
        "NULL",
    ):
        return u_up

    m = {
        "string": "STRING",
        "number": "NUMBER",
        "integer": "INTEGER",
        "boolean": "BOOLEAN",
        "array": "ARRAY",
        "object": "OBJECT",
        "null": "NULL",
    }
    return m.get(u.lower(), "TYPE_UNSPECIFIED")


def _sanitize_gemini_parameters(params: Any) -> Any:
    """TOOL_SPEC の JSON Schema(parameters) を Gemini(FunctionDeclaration.parameters) 互換へ変換する。"""
    if not params or not isinstance(params, dict):
        return {"type": "OBJECT", "properties": {}}

    _ALLOW_KEYS = {
        "type",
        "description",
        "enum",
        "items",
        "properties",
        "required",
        "nullable",
        "format",
    }

    def _is_null_schema(s: Any) -> bool:
        if not isinstance(s, dict):
            return False
        t = s.get("type")
        if t == "null" or t == "NULL":
            return True
        if isinstance(t, list) and any(str(x).lower() == "null" for x in t):
            return True
        return False

    def _collapse_nullable_union(schema: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        nullable = False
        out = dict(schema)

        t = out.get("type")
        if isinstance(t, list):
            ts = [str(x) for x in t if x is not None]
            has_null = any(x.lower() == "null" for x in ts)
            non_null = [x for x in ts if x.lower() != "null"]
            if has_null:
                nullable = True
                if len(non_null) >= 1:
                    out["type"] = non_null[0]
                else:
                    out["type"] = "null"

        for key in ("anyOf", "oneOf"):
            variants = out.get(key)
            if not isinstance(variants, list) or not variants:
                continue

            non_null_vars = [v for v in variants if not _is_null_schema(v)]
            has_null = len(non_null_vars) != len(variants)

            if (
                has_null
                and len(non_null_vars) == 1
                and isinstance(non_null_vars[0], dict)
            ):
                nullable = True
                base = dict(non_null_vars[0])

                for mk in ("description", "enum", "format"):
                    if mk in out and mk not in base:
                        base[mk] = out[mk]

                out.pop(key, None)
                out = {**out, **base}
                break

        return out, nullable

    def _sanitize(obj: Any) -> Any:
        if isinstance(obj, dict):
            src = {k: v for k, v in obj.items() if not str(k).startswith("$")}
            src.pop("additionalProperties", None)
            src.pop("additional_properties", None)

            src, nullable_from_union = _collapse_nullable_union(src)

            dst: dict[str, Any] = {}

            t = src.get("type")
            if isinstance(t, str):
                dst["type"] = _gemini_map_type(t)
            elif t is None:
                if "properties" in src:
                    dst["type"] = "OBJECT"
                elif "items" in src:
                    dst["type"] = "ARRAY"
                else:
                    dst["type"] = "TYPE_UNSPECIFIED"
            else:
                dst["type"] = "TYPE_UNSPECIFIED"

            if src.get("nullable") is True or nullable_from_union:
                dst["nullable"] = True

            for k in ("description", "format"):
                v = src.get(k)
                if isinstance(v, str) and v:
                    dst[k] = v

            v_enum = src.get("enum")
            if isinstance(v_enum, list) and v_enum:
                dst["enum"] = v_enum

            v_req = src.get("required")
            if isinstance(v_req, list) and v_req:
                dst["required"] = [str(x) for x in v_req if isinstance(x, (str, int))]

            props = src.get("properties")
            if isinstance(props, dict):
                new_props: dict[str, Any] = {}
                for pk, pv in props.items():
                    if not isinstance(pk, str) or not pk:
                        continue
                    new_props[pk] = _sanitize(pv)
                dst["properties"] = new_props

            items = src.get("items")
            if isinstance(items, dict):
                dst["items"] = _sanitize(items)
            elif isinstance(items, list):
                dst["items"] = _sanitize(items[0]) if items else {"type": "STRING"}

            dst = {k: v for k, v in dst.items() if k in _ALLOW_KEYS}
            return dst

        if isinstance(obj, list):
            return [_sanitize(x) for x in obj]

        return obj

    out = _sanitize(params)

    if not isinstance(out, dict):
        return {"type": "OBJECT", "properties": {}}
    if out.get("type") != "OBJECT":
        return {"type": "OBJECT", "properties": {}}
    if "properties" not in out or not isinstance(out.get("properties"), dict):
        out["properties"] = {}

    # Gemini requires that every key in "required" exists in "properties".
    # Remove dangling required entries to avoid 400 INVALID_ARGUMENT.
    v_req = out.get("required")
    if isinstance(v_req, list):
        valid_keys = set(out.get("properties", {}).keys())
        out["required"] = [k for k in v_req if k in valid_keys]

    return out


# -----------------------------
# Reasoning / Verbosity (Gemini)
# -----------------------------

_GEMINI_THINKING_LEVELS = {"minimal", "low", "medium", "high"}
_GEMINI_VERBOSITY_LEVELS = {"low", "medium", "high"}


def _normalize_reasoning_env(value: str | None) -> str:
    v = (value or "off").strip().lower()
    m = {
        "0": "off",
        "1": "low",
        "2": "medium",
        "3": "high",
        "unset": "off",
        "none": "off",
    }
    v = m.get(v, v)
    if v in {"off", "auto", "minimal", "low", "medium", "high", "xhigh"}:
        return v
    return "off"


def _normalize_verbosity_env(value: str | None) -> str:
    v = (value or "off").strip().lower()
    m = {
        "0": "off",
        "1": "low",
        "2": "medium",
        "3": "high",
        "unset": "off",
        "none": "off",
    }
    v = m.get(v, v)
    if v in {"off", "low", "medium", "high"}:
        return v
    return "off"


def _extract_latest_user_text(messages: list[dict[str, Any]]) -> str:
    for m in reversed(messages or []):
        if not isinstance(m, dict):
            continue
        if m.get("role") != "user":
            continue
        c = _message_content_text(m)
        if c.strip():
            return c
    return ""


def _message_content_text(message: dict[str, Any]) -> str:
    """Normalize message content to plain text for Gemini helpers."""
    c = message.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        parts: list[str] = []
        for item in c:
            if isinstance(item, dict):
                t = item.get("type")
                if t in ("text", "input_text", "output_text"):
                    txt = item.get("text")
                    if isinstance(txt, str) and txt.strip():
                        parts.append(txt)
            elif isinstance(item, str) and item.strip():
                parts.append(item)
        if parts:
            return "\n".join(parts)
    if c is None:
        return ""
    return str(c)


def _attachment_to_gemini_part(att: dict[str, Any]) -> Any | None:
    """Convert an attachment dict to a Gemini image Part when possible."""

    if not isinstance(att, dict):
        return None

    try:
        import base64
        import mimetypes
        from pathlib import Path
        from google.genai import types as gemini_types  # lazy
    except Exception:
        return None

    mime = (
        str(
            att.get("mime")
            or att.get("mime_type")
            or att.get("content_type")
            or att.get("type")
            or ""
        )
        .strip()
        .lower()
    )

    def _normalize_mime(m: str, path: str | None = None) -> str:
        mm = (m or "").strip().lower()
        if mm.startswith("image/") or mm.startswith("audio/"):
            return mm
        if mm == "image":
            mm = ""
        if mm == "audio":
            mm = ""
        if path:
            guessed, mime_subtype = mimetypes.guess_type(path)
            if isinstance(guessed, str) and (
                guessed.startswith("image/") or guessed.startswith("audio/")
            ):
                return guessed
            suffix = Path(path).suffix.lower()
            if suffix in (".jpg", ".jpeg"):
                return "image/jpeg"
            if suffix == ".png":
                return "image/png"
            if suffix == ".webp":
                return "image/webp"
            if suffix == ".gif":
                return "image/gif"
            if suffix == ".mp3":
                return "audio/mp3"
            if suffix == ".wav":
                return "audio/wav"
            if suffix in (".ogg", ".oga"):
                return "audio/ogg"
            if suffix in (".m4a", ".aac"):
                return "audio/aac"
            if suffix == ".flac":
                return "audio/flac"
        return "image/png"

    data_url = att.get("data_url") or att.get("dataUrl") or att.get("data")
    if isinstance(data_url, str) and data_url.startswith("data:"):
        try:
            header, b64 = data_url.split(",", 1)
            data_mime = header[5:].split(";", 1)[0].strip()
            payload = base64.b64decode(b64)
            return gemini_types.Part.from_bytes(
                data=payload,
                mime_type=_normalize_mime(data_mime or mime),
            )
        except Exception:
            pass

    path = (
        att.get("saved_path")
        or att.get("path")
        or att.get("file_path")
        or att.get("url")
    )
    if not isinstance(path, str) or not path.strip():
        return None
    path = path.strip()

    if (
        not mime.startswith("image/")
        and not mime.startswith("audio/")
        and mime not in ("image", "audio", "")
    ):
        return None

    try:
        p = Path(path)
        if not p.exists() or not p.is_file():
            return None
        if p.stat().st_size > 10_000_000:
            return None
        return gemini_types.Part.from_bytes(
            data=p.read_bytes(),
            mime_type=_normalize_mime(mime, str(p)),
        )
    except Exception:
        return None


def _choose_auto_thinking_level(user_text: str) -> str:
    t = (user_text or "").strip()
    n = len(t)

    # Light heuristics (keep local; avoid importing uagent_llm to prevent circular deps).
    tl = t.lower()
    keywords = (
        "why",
        "explain",
        "analyze",
        "analysis",
        "compare",
        "design",
        "plan",
        "strategy",
        "debug",
        "refactor",
        "optimize",
        "architecture",
        "tradeoff",
        "pros",
        "cons",
        "root cause",
        "root cause",
        "investigation",
        "analysis",
        "design",
        "comparison",
        "policy",
        "strategy",
        "optimization",
        "debugging",
        "implementation",
        "fix",
        "improvement",
    )

    if any(k in tl for k in keywords):
        # If explicitly asking for analysis/design/debug, start from at least 'low'.
        if n >= 900:
            return "high"
        if n >= 450:
            return "medium"
        return "low"

    if n >= 900:
        return "medium"
    if n >= 450:
        return "low"
    return "minimal"


def _model_uses_thinking_budget(model_name: str) -> bool:
    try:
        import llmcapa

        cap = llmcapa.get(model_name)
        if cap is not None:
            return cap.supports_thinking_budget
    except Exception:
        pass
    mn = (model_name or "").lower()
    return "2.5" in mn


def _build_thinking_config(
    *,
    gemini_types: Any,
    model_name: str,
    reasoning_mode: str,
    user_text_for_auto: str,
) -> Any:
    """Map UAGENT_REASONING -> google-genai ThinkingConfig.

    Model family:
    - Gemini 2.5: use thinking_budget
    - Gemini 3.x: use thinking_level

    Policy:
    - off/unset: for 2.5 => thinking_budget=0 (disable). for others => return None.
    - auto: choose MINIMAL/LOW/MEDIUM/HIGH
    - xhigh: round to HIGH
    - include_thoughts: True by default (can be opted out via UAGENT_GEMINI_INCLUDE_THOUGHTS=0/false)
    """
    rm = (reasoning_mode or "").strip().lower()
    use_budget = _model_uses_thinking_budget(model_name)

    # Opt-out logic for include_thoughts (defaults to True)
    inc_thoughts_env = (env_get("UAGENT_GEMINI_INCLUDE_THOUGHTS") or "").strip().lower()
    include_thoughts = inc_thoughts_env not in ("0", "false", "no", "off")

    if not rm or rm == "off":
        # Gemini 2.5: explicitly disable thinking with thinking_budget=0.
        if use_budget:
            return gemini_types.ThinkingConfig(
                thinking_budget=0,
                include_thoughts=False,
            )
        return None

    if rm == "auto":
        rm = _choose_auto_thinking_level(user_text_for_auto)

    if rm == "xhigh":
        rm = "high"

    if use_budget:
        # NOTE: budget values are conservative defaults.
        budget_map = {
            "minimal": 128,
            "low": 512,
            "medium": 2048,
            "high": 4096,
        }
        budget = budget_map.get(rm)
        if budget is None:
            return None
        return gemini_types.ThinkingConfig(
            thinking_budget=budget,
            include_thoughts=include_thoughts,
        )

    if rm not in _GEMINI_THINKING_LEVELS:
        return None

    # Gemini 3+: thinking_level
    return gemini_types.ThinkingConfig(
        thinking_level=rm,
        include_thoughts=include_thoughts,
    )


def _verbosity_to_max_output_tokens(verbosity_mode: str) -> int | None:
    # Allow user override via environment variable
    env_val = (env_get("UAGENT_GEMINI_MAX_OUTPUT_TOKENS") or "").strip()
    if env_val:
        try:
            return int(env_val)
        except ValueError:
            pass

    vm = (verbosity_mode or "").strip().lower()
    # If verbosity is off or unspecified, use the maximum physical limit (65536)
    if not vm or vm == "off":
        return 65536

    # Conservative defaults; users can still override output style in prompts.
    if vm == "low":
        return 800
    if vm == "medium":
        return 1600
    if vm == "high":
        return 3200

    return 65536


def _verbosity_to_instruction(verbosity_mode: str) -> str | None:
    vm = (verbosity_mode or "").strip().lower()
    if not vm or vm == "off":
        return None

    if vm == "low":
        return "Verbosity=low: be concise; avoid extra explanation unless asked."
    if vm == "medium":
        return "Verbosity=medium: normal level of detail; include key steps."
    if vm == "high":
        return "Verbosity=high: be detailed; explain reasoning at a high level; include important edge cases."

    return None


def gemini_chat_with_tools(
    client: Any,
    model_name: str,
    messages: list[dict[str, Any]],
    cached_content: str = None,
    stream: bool = False,
    core: Any = None,
    force_thinking_level: str | None = None,
    send_tools: bool = True,
    provider: str = "gemini",
) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    """Gemini Developer API + google-genai を使って tool_calls 付き応答を 1 回分生成する。"""

    try:
        from google import genai  # lazy
        from google.genai import types as gemini_types
    except Exception:
        genai = None
        gemini_types = None
    if genai is None or gemini_types is None:
        raise RuntimeError(
            _(
                "google-genai could not be imported (pip install google-genai is required)."
            )
        )

    # OpenAIの環境変数命名規則（UAGENT_OPENAI_WEB_SEARCH）に合わせ、
    # Gemini用の組み込みWeb検索有効化環境変数を UAGENT_GEMINI_WEB_SEARCH とします。
    use_google_search_env = (env_get("UAGENT_GEMINI_WEB_SEARCH") or "").strip().lower()
    if use_google_search_env == "":
        use_google_search = True
    else:
        use_google_search = use_google_search_env in ("1", "true", "yes", "on")

    tools_list: list[Any] = []

    if send_tools:
        tool_specs = tools.get_tool_specs() or []
    else:
        tool_specs = []
    if not isinstance(tool_specs, list):
        tool_specs = []

    if use_google_search:
        try:
            tools_list.append(
                gemini_types.Tool(google_search=gemini_types.GoogleSearch())
            )
        except Exception:
            tools_list.append({"google_search": {}})

        # Keep local tools enabled, but exclude the local DuckDuckGo web search
        # when Gemini built-in Google Search is active.
        tool_specs = [
            spec
            for spec in tool_specs
            if not (
                isinstance(spec, dict)
                and isinstance(spec.get("function"), dict)
                and str((spec.get("function") or {}).get("name") or "").strip()
                == "search_web"
            )
        ]

    func_decls: list[gemini_types.FunctionDeclaration] = []

    for spec in tool_specs:
        if not isinstance(spec, dict):
            continue
        fn = spec.get("function", {})
        if not isinstance(fn, dict):
            continue

        name = fn.get("name")
        if not isinstance(name, str) or not name:
            continue

        desc = fn.get("description", "")
        if not isinstance(desc, str):
            desc = str(desc)

        raw_params = fn.get("parameters", {})
        if not isinstance(raw_params, dict):
            raw_params = {"type": "object", "properties": {}}

        params = _sanitize_gemini_parameters(raw_params)

        func_decls.append(
            gemini_types.FunctionDeclaration(
                name=name,
                description=desc,
                parameters=params,
            )
        )

    if func_decls:
        tools_list.append(gemini_types.Tool(function_declarations=func_decls))

    system_instruction_parts: list[str] = []
    contents: list[gemini_types.Content] = []

    # Defaults to avoid NameError if early errors occur before we compute them.
    thinking_cfg = None
    max_output_tokens = None

    def _try_content_from_dump(d: Any) -> Any:
        if not isinstance(d, dict):
            return None
        try:
            mv = getattr(gemini_types.Content, "model_validate", None)
            if callable(mv):
                return mv(d)
        except Exception:
            pass
        try:
            return gemini_types.Content(**d)
        except Exception:
            return None

    def _append(role: str, part: gemini_types.Part) -> None:
        # google-genai SDK expects "model" for assistant and "tool" for tool responses.
        # Map internal role names to Gemini API expected roles.
        gemini_role = role
        if role == "assistant":
            gemini_role = "model"
        elif role == "tool":
            gemini_role = "tool"

        if contents and getattr(contents[-1], "role", None) == gemini_role:
            try:
                contents[-1].parts.append(part)
                return
            except Exception:
                pass
        contents.append(gemini_types.Content(role=gemini_role, parts=[part]))

    def _emit_stream_delta(delta_text: str) -> None:
        if not delta_text:
            return
        try:
            if core is not None and bool(getattr(core, "_is_web", False)):
                lm = getattr(core, "log_message", None)
                if callable(lm):
                    lm({"type": "assistant_stream_delta", "delta": delta_text})
                    return
        except Exception:
            pass
        print(delta_text, end="", flush=True)

    for m in messages:
        if not isinstance(m, dict):
            continue

        role = m.get("role")
        content = _message_content_text(m).strip()

        if role == "system":
            if content:
                system_instruction_parts.append(content)
            continue

        if role == "assistant":
            gemini_dump = m.get("_gemini_content")
            cobj = _try_content_from_dump(gemini_dump)
            if cobj is not None:
                contents.append(cobj)
                continue

            tool_calls = m.get("tool_calls") or []
            has_tool_calls = isinstance(tool_calls, list) and bool(tool_calls)

            if content and not has_tool_calls:
                _append("model", gemini_types.Part(text=content))

            if has_tool_calls:
                first_fc = True
                for tc in tool_calls:
                    if not isinstance(tc, dict):
                        continue
                    fnc = tc.get("function") or {}
                    if not isinstance(fnc, dict):
                        continue
                    fc_name = fnc.get("name")
                    if not isinstance(fc_name, str) or not fc_name:
                        continue
                    fc_id = tc.get("id")
                    args_str = fnc.get("arguments") or "{}"
                    try:
                        parsed = (
                            json.loads(args_str)
                            if isinstance(args_str, str)
                            else args_str
                        )
                        args_obj = parsed if isinstance(parsed, dict) else {}
                    except Exception:
                        args_obj = {}

                    fc_dict = {"name": fc_name, "args": args_obj}
                    if isinstance(fc_id, str) and fc_id:
                        fc_dict["id"] = fc_id

                    if first_fc:
                        try:
                            part_fc = gemini_types.Part(
                                function_call=fc_dict,
                                thought_signature="skip_thought_signature_validator",
                            )
                        except Exception:
                            part_fc = gemini_types.Part(function_call=fc_dict)
                        first_fc = False
                    else:
                        try:
                            part_fc = gemini_types.Part(function_call=fc_dict)
                        except Exception:
                            part_fc = gemini_types.Part(function_call=fc_dict)

                    _append("model", part_fc)
            continue

        if role == "user":
            user_parts: list[Any] = []
            attachments = m.get("attachments")
            has_attachments = isinstance(attachments, list) and bool(attachments)

            if not content and has_attachments:
                content = build_image_default_prompt("describe")

            if content:
                user_parts.append(gemini_types.Part(text=content))

            if has_attachments:
                for att in attachments:
                    part = _attachment_to_gemini_part(att)
                    if part is not None:
                        user_parts.append(part)

            if user_parts:
                for part in user_parts:
                    _append("user", part)
            continue

        if role == "tool":
            tool_name = m.get("name") or "tool"
            if not isinstance(tool_name, str) or not tool_name:
                tool_name = "tool"
            tool_call_id = m.get("tool_call_id")

            resp_obj: dict[str, Any]
            if content:
                try:
                    parsed = json.loads(content)
                    resp_obj = (
                        parsed if isinstance(parsed, dict) else {"content": content}
                    )
                except Exception:
                    resp_obj = {"content": content}
            else:
                resp_obj = {"content": ""}

            try:
                fr_dict = {"name": tool_name, "response": resp_obj}
                if isinstance(tool_call_id, str) and tool_call_id:
                    fr_dict["id"] = tool_call_id

                part = gemini_types.Part(function_response=fr_dict)
                # Gemini tool results must be sent with role="tool" in google-genai SDK.
                # Sending them as "user" causes Gemini to fail to recognize the response and repeat the same tool call.
                _append("tool", part)
            except Exception:
                if content:
                    _append(
                        "tool", gemini_types.Part(text=f"[Tool:{tool_name}] {content}")
                    )
            continue

        if content:
            _append("model", gemini_types.Part(text=f"{role}:\n{content}"))

    # Apply reasoning/verbosity controls from env.
    reasoning_mode = _normalize_reasoning_env(env_get("UAGENT_REASONING"))
    # Force Gemini verbosity to 'off' to avoid truncation and loop issues.
    # Verbosity instructions and token limits often cause Gemini to stop prematurely or repeat itself.
    verbosity_mode = "off"

    verbosity_instr = _verbosity_to_instruction(verbosity_mode)
    if verbosity_instr:
        if cached_content:
            # NOTE: GenerateContent requests using cached_content cannot set system_instruction.
            # Send the style hint as a leading user message instead.
            contents.insert(
                0,
                gemini_types.Content(
                    role="user",
                    parts=[gemini_types.Part(text=verbosity_instr)],
                ),
            )
        else:
            system_instruction_parts.append(verbosity_instr)

    if force_thinking_level:
        reasoning_mode = force_thinking_level.strip().lower() or reasoning_mode

    # Resolve and display the effective reasoning level when reasoning=auto.
    _auto_user_text = _extract_latest_user_text(messages)
    if core is not None:
        try:
            if reasoning_mode == "auto":
                _eff = _choose_auto_thinking_level(_auto_user_text)
                core.set_status(True, f"LLM:auto->{_eff}")
            elif reasoning_mode in ("minimal", "low", "medium", "high", "xhigh"):
                _eff = "high" if reasoning_mode == "xhigh" else reasoning_mode
                core.set_status(True, f"LLM:{_eff}")
        except Exception:
            pass

    thinking_cfg = _build_thinking_config(
        gemini_types=gemini_types,
        model_name=model_name,
        reasoning_mode=reasoning_mode,
        user_text_for_auto=_auto_user_text,
    )

    max_output_tokens = _verbosity_to_max_output_tokens(verbosity_mode)

    system_instruction = (
        "\n\n".join(system_instruction_parts) if system_instruction_parts else None
    )
    valid_contents: list[gemini_types.Content] = []
    for c in contents:
        try:
            parts = getattr(c, "parts", None)
            if parts is None:
                continue
            if not isinstance(parts, list) or not parts:
                continue
            valid_parts = [p for p in parts if p is not None]
            if not valid_parts:
                continue
            try:
                c.parts = valid_parts
            except Exception:
                pass
            valid_contents.append(c)
        except Exception:
            continue
    contents = valid_contents

    if not contents and not cached_content:
        # キャッシュもコンテンツもない場合のみ、最低1つのPartを持つUserメッセージを追加する。
        contents = [
            gemini_types.Content(role="user", parts=[gemini_types.Part(text=" ")])
        ]

    cfg_kwargs: dict[str, Any] = {}

    # NOTE:
    # When using cached_content, Gemini forbids setting system_instruction/tools/tool_config
    # on the GenerateContent request. Those must be part of the CachedContent.
    if cached_content:
        cfg_kwargs["cached_content"] = cached_content
    else:
        if tools_list:
            cfg_kwargs["tools"] = tools_list
            # include_server_side_tool_invocations is not supported by
            # VertexAI Enterprise Agent Platform.
            if provider != "vertexai":
                try:
                    cfg_kwargs["tool_config"] = gemini_types.ToolConfig(
                        include_server_side_tool_invocations=True
                    )
                except Exception:
                    pass
            try:
                cfg_kwargs["automatic_function_calling"] = (
                    gemini_types.AutomaticFunctionCallingConfig(disable=True)
                )
            except Exception:
                pass
        if system_instruction:
            cfg_kwargs["system_instruction"] = system_instruction

    # Resolve temperature (default 0.2 for deterministic tool use and stable reasoning)
    temp_env = (env_get("UAGENT_GEMINI_TEMPERATURE") or "").strip()
    if temp_env:
        try:
            cfg_kwargs["temperature"] = float(temp_env)
        except ValueError:
            cfg_kwargs["temperature"] = 0.2
    else:
        cfg_kwargs["temperature"] = 0.2

    if thinking_cfg is not None:
        cfg_kwargs["thinking_config"] = thinking_cfg

    if max_output_tokens is not None:
        cfg_kwargs["max_output_tokens"] = max_output_tokens

    # Apply safety settings to prevent Gemini from silently blocking or muting responses.
    # Users can opt out or customize via environment variables if needed.
    safety_off_env = (env_get("UAGENT_GEMINI_SAFETY_OFF") or "1").strip().lower()
    if safety_off_env in ("1", "true", "yes", "on"):
        try:
            safety_settings = [
                gemini_types.SafetySetting(
                    category=cat,
                    threshold=gemini_types.HarmBlockThreshold.BLOCK_NONE,
                )
                for cat in [
                    gemini_types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                    gemini_types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                    gemini_types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                    gemini_types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                    gemini_types.HarmCategory.HARM_CATEGORY_CIVIC_INTEGRITY,
                ]
            ]
            cfg_kwargs["safety_settings"] = safety_settings
        except Exception:
            pass

    config_obj = (
        gemini_types.GenerateContentConfig(**cfg_kwargs) if cfg_kwargs else None
    )

    gen_kwargs: dict[str, Any] = {
        "model": model_name,
        "contents": contents,
    }
    if config_obj is not None:
        gen_kwargs["config"] = config_obj

    assistant_text_parts: list[str] = []
    tool_calls_list: list[dict[str, Any]] = []
    gemini_content_dump: dict[str, Any] = {}

    def _collect_from_response_obj(
        response_obj: Any,
        *,
        stream_mode: bool,
        text_so_far: str,
    ) -> tuple[str, list[dict[str, Any]], dict[str, Any], str]:
        candidates = getattr(response_obj, "candidates", None)
        if not candidates:
            return "", [], {}, text_so_far

        candidate = candidates[0]
        content_obj = getattr(candidate, "content", None)
        parts = getattr(content_obj, "parts", None)

        gemini_content_dump: dict[str, Any] = {}
        try:
            fr = getattr(candidate, "finish_reason", None)
            if fr is not None:
                fr_str = str(fr)
                gemini_content_dump["finish_reason"] = fr_str
                if fr_str.lower() not in (
                    "stop",
                    "finish_reason_unspecified",
                    "max_tokens",
                ):
                    # STOP以外の異常系（length, safetyなど）だけ出力
                    pass  # print(f"\\n[Gemini] finish_reason={fr_str}")
        except Exception:
            pass
        try:
            if content_obj is not None:
                md = getattr(content_obj, "model_dump", None)
                if callable(md):
                    dumped = md(exclude_none=True)
                    if isinstance(dumped, dict):
                        gemini_content_dump.update(dumped)
                    else:
                        gemini_content_dump.update(
                            {"role": getattr(content_obj, "role", "model")}
                        )
                else:
                    gemini_content_dump.update(
                        {"role": getattr(content_obj, "role", "model")}
                    )
        except Exception:
            gemini_content_dump = {
                "finish_reason": gemini_content_dump.get("finish_reason", "unknown")
            }

        chunk_texts: list[str] = []
        chunk_tool_calls: list[dict[str, Any]] = []

        if stream_mode:
            # Avoid response.text here because google-genai emits a warning when
            # the chunk contains non-text parts such as function_call.
            # We reconstruct text only from content.parts below.
            pass

        if parts:
            for part in parts:
                fc = getattr(part, "function_call", None)
                if fc is not None:
                    if isinstance(fc, dict):
                        name3 = fc.get("name")
                        args_raw = fc.get("args")
                    else:
                        name3 = getattr(fc, "name", None)
                        args_raw = getattr(fc, "args", None)

                    if isinstance(name3, str) and name3:
                        if isinstance(args_raw, str):
                            try:
                                args_obj = json.loads(args_raw)
                            except Exception:
                                args_obj = {"_raw": args_raw}
                        elif isinstance(args_raw, dict):
                            args_obj = args_raw
                        else:
                            args_obj = {}

                        chunk_tool_calls.append(
                            {
                                "id": f"gemini_fc_{len(chunk_tool_calls) + 1}",
                                "type": "function",
                                "function": {
                                    "name": name3,
                                    "arguments": json.dumps(
                                        args_obj, ensure_ascii=False
                                    ),
                                },
                            }
                        )

                is_thought = getattr(part, "thought", False)

                if not stream_mode:
                    t = getattr(part, "text", None)
                    if isinstance(t, str) and t:
                        if is_thought:
                            # Non-streaming mode: print thought in gray but do not append to final answer
                            try:
                                print(f"\033[90m{t}\033[0m", end="", flush=True)
                            except Exception:
                                pass
                        else:
                            chunk_texts.append(t)
                else:
                    t = getattr(part, "text", None)
                    if isinstance(t, str) and t:
                        if is_thought:
                            # Streaming mode: print thought in gray but do not append to final answer
                            _emit_stream_delta(f"\033[90m{t}\033[0m")
                        else:
                            delta_text = t
                            if text_so_far and t.startswith(text_so_far):
                                delta_text = t[len(text_so_far) :]
                            if delta_text:
                                chunk_texts.append(delta_text)
                                _emit_stream_delta(delta_text)
                                text_so_far += delta_text

        return "".join(chunk_texts), chunk_tool_calls, gemini_content_dump, text_so_far

    if stream:
        try:
            if core is not None and bool(getattr(core, "_is_web", False)):
                lm = getattr(core, "log_message", None)
                if callable(lm):
                    lm({"type": "assistant_stream_start"})
        except Exception:
            pass

        text_so_far = ""
        try:
            stream_iter = client.models.generate_content_stream(**gen_kwargs)
            for response in stream_iter:
                (
                    chunk_text,
                    chunk_tool_calls,
                    chunk_dump,
                    text_so_far,
                ) = _collect_from_response_obj(
                    response,
                    stream_mode=True,
                    text_so_far=text_so_far,
                )
                if chunk_text:
                    assistant_text_parts.append(chunk_text)
                if chunk_tool_calls:
                    tool_calls_list.extend(chunk_tool_calls)
                if chunk_dump:
                    gemini_content_dump = chunk_dump
        except Exception as e:
            err_str = str(e).lower()
            if (
                "finish_reason" in err_str
                or "safety" in err_str
                or "blocked" in err_str
            ):
                warning_msg = "\n\n" + _(
                    "[Gemini Error: Response blocked by safety filter or finish reason]",
                    default="[Gemini Error: Response blocked by safety filter or finish reason]",
                )
            else:
                warning_msg = "\n\n" + _(
                    "[Gemini Error: %(err)s]", default="[Gemini Error: %(err)s]"
                ) % {"err": str(e)}

            # Append the warning message so the user knows why it stopped
            assistant_text_parts.append(warning_msg)
            _emit_stream_delta(warning_msg)

        try:
            if core is not None and bool(getattr(core, "_is_web", False)):
                lm = getattr(core, "log_message", None)
                if callable(lm):
                    lm({"type": "assistant_stream_end"})
        except Exception:
            pass

        assistant_content = "".join(assistant_text_parts)
        if (
            assistant_content
            and not bool(getattr(core, "_is_web", False))
            and not assistant_content.endswith("\n")
        ):
            print("")

        # Gemini stream deduplication for tool calls
        unique_tcs = []
        seen = set()
        for tc in tool_calls_list:
            sig = json.dumps(tc.get("function", {}), sort_keys=True)
            if sig not in seen:
                seen.add(sig)
                unique_tcs.append(tc)
        tool_calls_list = unique_tcs

        return assistant_content, tool_calls_list, gemini_content_dump

    response = client.models.generate_content(**gen_kwargs)
    assistant_content, tool_calls_list, gemini_content_dump, response_meta = (
        _collect_from_response_obj(
            response,
            stream_mode=False,
            text_so_far="",
        )
    )

    # Gemini deduplication for tool calls (just in case)
    unique_tcs = []
    seen = set()
    for tc in tool_calls_list:
        sig = json.dumps(tc.get("function", {}), sort_keys=True)
        if sig not in seen:
            seen.add(sig)
            unique_tcs.append(tc)
    tool_calls_list = unique_tcs

    return assistant_content, tool_calls_list, gemini_content_dump
