import json
from typing import Any, Dict, List, Tuple

from .env_utils import env_get

from . import tools

# Google Gemini (google-genai)
try:
    from google import genai
    from google.genai import types as gemini_types
except Exception:  # google-genai 未インストール時など
    genai = None  # type: ignore[assignment]
    gemini_types = None  # type: ignore[assignment]


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

    def _collapse_nullable_union(schema: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
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

            dst: Dict[str, Any] = {}

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
                new_props: Dict[str, Any] = {}
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


def _extract_latest_user_text(messages: List[Dict[str, Any]]) -> str:
    for m in reversed(messages or []):
        if not isinstance(m, dict):
            continue
        if m.get("role") != "user":
            continue
        c = m.get("content")
        if isinstance(c, str) and c.strip():
            return c
    return ""


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
        "原因",
        "調査",
        "分析",
        "設計",
        "比較",
        "方針",
        "戦略",
        "最適化",
        "デバッグ",
        "実装",
        "修正",
        "改善",
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
    - include_thoughts: always False (we don't want chain-of-thought in outputs)
    """
    rm = (reasoning_mode or "").strip().lower()
    use_budget = _model_uses_thinking_budget(model_name)

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
            include_thoughts=False,
        )

    if rm not in _GEMINI_THINKING_LEVELS:
        return None

    # Gemini 3+: thinking_level
    return gemini_types.ThinkingConfig(
        thinking_level=rm,
        include_thoughts=False,
    )


def _verbosity_to_max_output_tokens(verbosity_mode: str) -> int | None:
    vm = (verbosity_mode or "").strip().lower()
    if not vm or vm == "off":
        return None

    # Conservative defaults; users can still override output style in prompts.
    if vm == "low":
        return 800
    if vm == "medium":
        return 1600
    if vm == "high":
        return 3200

    return None


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
    messages: List[Dict[str, Any]],
    cached_content: str = None,
    core: Any = None,
) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
    """Gemini Developer API + google-genai を使って tool_calls 付き応答を 1 回分生成する。"""

    if genai is None or gemini_types is None:
        raise RuntimeError(
            "google-genai がインポートできませんでした。（pip install google-genai が必要です）"
        )

    tool_specs = tools.get_tool_specs() or []
    if not isinstance(tool_specs, list):
        tool_specs = []

    func_decls: List[gemini_types.FunctionDeclaration] = []

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

    tools_list: List[gemini_types.Tool] = []
    if func_decls:
        tools_list.append(gemini_types.Tool(function_declarations=func_decls))

    system_instruction_parts: List[str] = []
    contents: List[gemini_types.Content] = []

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
        if contents and getattr(contents[-1], "role", None) == role:
            try:
                contents[-1].parts.append(part)
                return
            except Exception:
                pass
        contents.append(gemini_types.Content(role=role, parts=[part]))

    for m in messages:
        if not isinstance(m, dict):
            continue

        role = m.get("role")
        content = (m.get("content") or "").strip()

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

        if role == "user":
            if content:
                _append("user", gemini_types.Part(text=content))
            continue

        if role == "assistant":
            if content:
                _append("model", gemini_types.Part(text=content))

            tool_calls = m.get("tool_calls") or []
            if isinstance(tool_calls, list):
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

                    if first_fc:
                        try:
                            part_fc = gemini_types.Part(
                                function_call={"name": fc_name, "args": args_obj},
                                thought_signature="skip_thought_signature_validator",
                            )
                        except Exception:
                            part_fc = gemini_types.Part(
                                function_call={"name": fc_name, "args": args_obj}
                            )
                        first_fc = False
                    else:
                        try:
                            part_fc = gemini_types.Part.from_function_call(
                                name=fc_name, args=args_obj
                            )
                        except Exception:
                            part_fc = gemini_types.Part(
                                function_call={"name": fc_name, "args": args_obj}
                            )

                    _append("model", part_fc)
            continue

        if role == "tool":
            tool_name = m.get("name") or "tool"
            if not isinstance(tool_name, str) or not tool_name:
                tool_name = "tool"

            resp_obj: Dict[str, Any]
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
                part = gemini_types.Part.from_function_response(
                    name=tool_name,
                    response=resp_obj,
                )
                _append("tool", part)
            except Exception:
                if content:
                    _append(
                        "tool", gemini_types.Part(text=f"[Tool:{tool_name}] {content}")
                    )
            continue

        if content:
            _append("user", gemini_types.Part(text=f"{role}:\n{content}"))

    # Apply reasoning/verbosity controls from env.
    reasoning_mode = _normalize_reasoning_env(env_get("UAGENT_REASONING"))
    verbosity_mode = _normalize_verbosity_env(env_get("UAGENT_VERBOSITY"))

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

    if not contents and not cached_content:
        # キャッシュもコンテンツもない場合のみ、空のUserメッセージを追加して生成を可能にする。
        contents = [
            gemini_types.Content(role="user", parts=[gemini_types.Part(text="")])
        ]

    cfg_kwargs: Dict[str, Any] = {}

    # NOTE:
    # When using cached_content, Gemini forbids setting system_instruction/tools/tool_config
    # on the GenerateContent request. Those must be part of the CachedContent.
    if cached_content:
        cfg_kwargs["cached_content"] = cached_content
    else:
        if tools_list:
            cfg_kwargs["tools"] = tools_list
            try:
                cfg_kwargs["automatic_function_calling"] = (
                    gemini_types.AutomaticFunctionCallingConfig(disable=True)
                )
            except Exception:
                pass
        if system_instruction:
            cfg_kwargs["system_instruction"] = system_instruction

    if thinking_cfg is not None:
        cfg_kwargs["thinking_config"] = thinking_cfg

    if max_output_tokens is not None:
        cfg_kwargs["max_output_tokens"] = max_output_tokens

    config_obj = (
        gemini_types.GenerateContentConfig(**cfg_kwargs) if cfg_kwargs else None
    )

    gen_kwargs: Dict[str, Any] = {
        "model": model_name,
        "contents": contents,
    }
    if config_obj is not None:
        gen_kwargs["config"] = config_obj

    response = client.models.generate_content(**gen_kwargs)

    candidates = getattr(response, "candidates", None)
    if not candidates:
        return "", [], {}

    candidate = candidates[0]
    content_obj = getattr(candidate, "content", None)
    parts = getattr(content_obj, "parts", None)

    gemini_content_dump: Dict[str, Any] = {}
    try:
        if content_obj is not None:
            md = getattr(content_obj, "model_dump", None)
            if callable(md):
                gemini_content_dump = md(exclude_none=True)
            else:
                gemini_content_dump = {"role": getattr(content_obj, "role", "model")}
    except Exception:
        gemini_content_dump = {}

    if not parts:
        return "", [], gemini_content_dump

    text_chunks: List[str] = []
    tool_calls_list: List[Dict[str, Any]] = []

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

                tool_calls_list.append(
                    {
                        "id": f"gemini_fc_{len(tool_calls_list) + 1}",
                        "type": "function",
                        "function": {
                            "name": name3,
                            "arguments": json.dumps(args_obj, ensure_ascii=False),
                        },
                    }
                )

        t = getattr(part, "text", None)
        if isinstance(t, str) and t:
            text_chunks.append(t)

    assistant_content = "".join(text_chunks)
    return assistant_content, tool_calls_list, gemini_content_dump
