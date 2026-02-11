import json
from typing import Any, Dict, List, Tuple

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


def gemini_chat_with_tools(
    client: Any,
    model_name: str,
    messages: List[Dict[str, Any]],
    cached_content: str = None,
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

    system_instruction = (
        "\n\n".join(system_instruction_parts) if system_instruction_parts else None
    )

    if not contents and not cached_content:
        # キャッシュもコンテンツもない場合のみ、空のUserメッセージを追加して生成を可能にする。
        contents = [
            gemini_types.Content(role="user", parts=[gemini_types.Part(text="")])
        ]

    cfg_kwargs: Dict[str, Any] = {}
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
