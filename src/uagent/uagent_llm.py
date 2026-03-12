import json
import re
from .env_utils import env_get
import time
from .i18n import _
from .translate import load_translate_config, translate_text
import traceback
from typing import Any, Dict, List, Optional
from urllib.error import URLError

from . import tools
from .llm_errors import (
    _compute_retry_wait_seconds,
    _extract_retry_after,
    _is_rate_limit_error,
)
from .llm_gemini import gemini_chat_with_tools, _sanitize_gemini_parameters
from .llm_claude import claude_chat_with_tools
from .llm_openai_responses import (
    build_responses_request,
    parse_responses_response,
    parse_responses_stream,
)

try:
    from google.genai import types as gemini_types
except ImportError:
    gemini_types = None

try:
    from openai import APIConnectionError, BadRequestError
except Exception:
    BadRequestError = None
    APIConnectionError = None


def _is_gpt54_tool_search_target(
    *,
    provider: str,
    depname: str,
    use_responses_api: bool,
) -> bool:
    """Return True when GPT-5.4 tool narrowing is explicitly enabled.

    Guarded by env:
    - UAGENT_ENABLE_GPT54_TOOL_SEARCH=1|true|yes|on

    Only applies when using the Responses API.
    """

    enabled = (env_get("UAGENT_ENABLE_GPT54_TOOL_SEARCH") or "").strip().lower()
    if enabled not in ("1", "true", "yes", "on"):
        return False

    if not use_responses_api:
        return False

    model = (depname or "").strip().lower()

    marker = "gpt-5."
    idx = model.find(marker)
    if idx < 0:
        return False

    tail = model[idx + len(marker) :]
    digits: List[str] = []
    for ch in tail:
        if ch.isdigit():
            digits.append(ch)
        else:
            break

    if not digits:
        return False

    try:
        minor = int("".join(digits))
    except Exception:
        return False

    return minor >= 4


def _select_tool_specs_for_gpt54(
    call_messages: List[Dict[str, Any]],
) -> Optional[List[Dict[str, Any]]]:
    """Narrow tool surface for GPT-5.4 (Responses API) using tool_catalog.

    Policy:
    - Always include tool_catalog and human_ask when narrowing is applied.
    - If tool_catalog has hits: include only hit tools (+ tool_catalog + human_ask).
    - If tool_catalog has zero hits, or user text is empty: fail open (return full tool set).

    This function is stateless: it does not depend on previous tool calls.
    """

    specs = tools.get_tool_specs() or []
    if not specs:
        return []

    # latest user text
    latest_user_text = ""
    for m in reversed(call_messages):
        if m.get("role") != "user":
            continue
        content = m.get("content")
        if isinstance(content, str):
            latest_user_text = content
            break
        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") in (
                    "text",
                    "input_text",
                    "output_text",
                ):
                    txt = item.get("text")
                    if isinstance(txt, str) and txt.strip():
                        parts.append(txt)
            if parts:
                latest_user_text = "\n".join(parts)
                break

    latest_user_text = (latest_user_text or "").strip()
    if not latest_user_text:
        if env_get("UAGENT_DEBUG_TOOLS") == "1":
            try:
                print("[debug] gpt54.latest_user_text=", latest_user_text)
                print("[debug] gpt54.tool_catalog_hits=", [])
                print("[debug] gpt54.narrowing=skip_empty_query(full_tools)")
            except Exception:
                pass
        return specs

    rows = tools.get_tool_catalog(query=latest_user_text, max_results=8)
    hit_names = {
        str(row.get("name") or "").strip()
        for row in (rows or [])
        if isinstance(row, dict)
    }
    hit_names.discard("")

    if env_get("UAGENT_DEBUG_TOOLS") == "1":
        try:
            print("[debug] gpt54.latest_user_text=", latest_user_text)
            print("[debug] gpt54.tool_catalog_hits=", sorted(hit_names))
        except Exception:
            pass

    if not hit_names:
        if env_get("UAGENT_DEBUG_TOOLS") == "1":
            try:
                print("[debug] gpt54.narrowing=zero_hit_fail_open(full_tools)")
            except Exception:
                pass
        return specs

    # Always keep these when narrowing applies
    selected_names = {"tool_catalog", "human_ask"}
    selected_names.update(hit_names)

    narrowed: List[Dict[str, Any]] = []
    for spec in specs:
        if not isinstance(spec, dict):
            continue
        fn = spec.get("function") or {}
        if not isinstance(fn, dict):
            continue
        name = str(fn.get("name") or "").strip()
        if name in selected_names:
            narrowed.append(spec)

    return narrowed


# Auto reasoning (Responses API only)
_AUTO_EFFORT_LADDER = ("minimal", "low", "medium", "high", "xhigh")


def _extract_latest_user_text(call_messages: List[Dict[str, Any]]) -> str:
    for m in reversed(call_messages or []):
        if m.get("role") != "user":
            continue
        c = m.get("content")
        if isinstance(c, str):
            return c
        if isinstance(c, list):
            parts: List[str] = []
            for item in c:
                if isinstance(item, dict):
                    t = item.get("type")
                    if t in ("text", "input_text", "output_text"):
                        txt = item.get("text")
                        if isinstance(txt, str) and txt.strip():
                            parts.append(txt)
            if parts:
                return "\n".join(parts)
    return ""


def _is_thinking_task(user_text: str) -> bool:
    t = (user_text or "").strip().lower()
    if not t:
        return False

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
    if any(k in t for k in keywords):
        return True

    return len(t) >= 200


def _choose_auto_effort(user_text: str) -> str:
    n = len((user_text or "").strip())
    if n >= 900:
        return "high"
    if n >= 450:
        return "medium"
    if n >= 120:
        return "low"
    return "minimal"


def _bump_effort(effort: str | None) -> str | None:
    if effort not in _AUTO_EFFORT_LADDER:
        return "minimal"
    idx = _AUTO_EFFORT_LADDER.index(effort)
    if idx >= len(_AUTO_EFFORT_LADDER) - 1:
        return None
    return _AUTO_EFFORT_LADDER[idx + 1]


def _auto_low_quality(user_text: str, assistant_text: str) -> bool:
    a = (assistant_text or "").strip()
    if not a:
        return True

    al = a.lower()

    # "can't / don't know" patterns
    if re.search(
        r"(i can't|i cannot|cannot|unable to|don't know|do not know|can't help|cannot help)",
        al,
    ):
        return True
    if re.search(
        r"(わかりません|分かりません|できません|出来ません|不明です|わからない|無理です)",
        a,
    ):
        return True

    # format/requirements: JSON requested
    ut = (user_text or "").lower()
    if "json" in ut:
        s = a.lstrip()
        if not (s.startswith("{") or s.startswith("[") or "```json" in s.lower()):
            return True

    return False


def run_llm_rounds(
    provider: str,
    client: Any,
    depname: str,
    messages: List[Dict[str, Any]],
    *,
    core: Any,
    make_client_fn: Any,
    append_result_to_outfile_fn: Any,
    try_open_images_from_text_fn: Any,
) -> None:
    max_tool_rounds = 200
    round_count = 0

    empty_no_tool_rounds = 0

    # Some OpenAI-compatible local providers may return empty assistant messages after tool calls.
    # Tolerate a few consecutive empty/no-tool rounds, then abort with an explicit warning.
    try:
        empty_no_tool_max = int(env_get("UAGENT_EMPTY_NO_TOOL_MAX", "2"))
    except Exception:
        empty_no_tool_max = 2
    if empty_no_tool_max < 0:
        empty_no_tool_max = 2

    def _effectively_empty_text(s: Any) -> bool:
        if s is None:
            return True
        if not isinstance(s, str):
            try:
                s = str(s)
            except Exception:
                return True
        t = s.strip()
        # Treat common invisible characters as empty too (e.g., zero-width space/BOM).
        # Treat common invisible characters as empty too.
        # - Zero-width (ZWSP/ZWNJ/ZWJ), BOM
        # - NO-BREAK SPACE (NBSP), WORD JOINER, INVISIBLE SEPARATOR, SHY
        for cp in (
            0x200B, 0x200C, 0x200D, 0xFEFF,
            0x00A0, 0x2060, 0x2063, 0x00AD,
        ):
            t = t.replace(chr(cp), "")
        # Remove any remaining Unicode separator/control characters by category.
        try:
            import unicodedata
            t = "".join(ch for ch in t if unicodedata.category(ch) not in ("Cf", "Zs", "Zl", "Zp", "Cc"))
        except Exception:
            pass
        return t == ""

    core.set_status(True, "LLM")

    tool_result_cache: Dict[str, str] = {}
    use_tool_result_cache = env_get(
        "UAGENT_TOOL_RESULT_CACHE", "0"
    ).strip().lower() not in ("0", "false", "no", "off")
    reuse_only_rounds = 0

    from .gemini_cache_mgr import GeminiCacheManager

    cache_mgr = GeminiCacheManager(depname)
    gemini_cache_name = None

    use_cache_env = env_get("UAGENT_GEMINI_CACHE", "1").lower()
    if (
        provider == "gemini"
        and use_cache_env not in ("0", "false", "no")
        and gemini_types
    ):
        clear_on_start = env_get("UAGENT_GEMINI_CACHE_CLEAR_ON_START", "1").lower() in (
            "1",
            "true",
        )
        if clear_on_start:
            try:
                cache_mgr.clear_cache(client)
            except Exception:
                pass
        try:
            system_instruction = "\n".join(
                [m["content"] for m in messages if m["role"] == "system"]
            )
            tool_specs = tools.get_tool_specs() or []

            if cache_mgr.is_cache_valid(system_instruction, tool_specs):
                gemini_cache_name = cache_mgr.get_cache_name()
            else:
                func_decls = []
                for spec in tool_specs:
                    fn = spec.get("function", {})
                    func_decls.append(
                        gemini_types.FunctionDeclaration(
                            name=fn.get("name"),
                            description=fn.get("description", ""),
                            parameters=_sanitize_gemini_parameters(
                                fn.get("parameters", {})
                            ),
                        )
                    )

                # キャッシュにはシステムプロンプトのみを含める。
                # ユーザーの問いかけはリクエスト本体(generate_content)で送る。
                cache_initial_msgs = [m for m in messages if m["role"] == "system"]
                gemini_cache_name = cache_mgr.create_cache(
                    client, system_instruction, func_decls, cache_initial_msgs
                )
        except Exception:
            pass  # print(f"[Gemini] キャッシュ処理中にエラーが発生しました (通常モードで続行): {e}")

    try:
        while True:
            round_count += 1
            if True:
                # Auto shrink_llm (optional)
                shrink_cnt_raw = (env_get("UAGENT_SHRINK_CNT", "") or "").strip()
                try:
                    shrink_cnt = int(shrink_cnt_raw) if shrink_cnt_raw != "" else 100
                except Exception:
                    shrink_cnt = 100

                if shrink_cnt > 0:
                    # Count non-system messages (same rule as core.shrink_messages)
                    others_count = 0
                    hit_non_system = False
                    for m in messages:
                        if m.get("role") == "system" and not hit_non_system:
                            continue
                        hit_non_system = True
                        others_count += 1

                    if others_count >= shrink_cnt:
                        keep_last_raw = (
                            env_get("UAGENT_SHRINK_KEEP_LAST", "") or ""
                        ).strip()
                        try:
                            keep_last = (
                                int(keep_last_raw) if keep_last_raw != "" else 20
                            )
                        except Exception:
                            keep_last = 20

                        try:
                            # If Gemini cache is enabled, clear it on auto shrink_llm
                            # to avoid mismatched cached system instructions.
                            if provider == "gemini":
                                try:
                                    cache_mgr.clear_cache(client)
                                except Exception:
                                    pass
                                gemini_cache_name = None

                            new_messages = core.compress_history_with_llm(
                                client=client,
                                depname=depname,
                                messages=messages,
                                keep_last=keep_last,
                            )
                            messages.clear()
                            messages.extend(new_messages)

                            # Persist into current session log
                            try:
                                core.rewrite_current_log_from_messages(messages)
                            except Exception:
                                pass

                            print(
                                (
                                    "[INFO] Auto shrink_llm triggered: "
                                    f"others={others_count} >= cnt={shrink_cnt} "
                                    f"keep_last={keep_last}"
                                )
                            )
                        except Exception as e:
                            print(
                                "[WARN] Auto shrink_llm failed: "
                                f"{type(e).__name__}: {e}"
                            )
            if round_count > max_tool_rounds:
                print(
                    _("[WARN] Tool rounds exceeded %(max)d; aborting.")
                    % {"max": max_tool_rounds}
                )
                break

            # Optional translation layer (off by default).
            # We keep the original `messages` history unchanged and create a translated
            # copy only for the LLM call.
            tr_cfg = load_translate_config()

            if provider == "gemini":
                if gemini_cache_name:
                    # キャッシュには System プロンプトが含まれているため、それ以外(User, Assistant, Tool等)を送る。
                    # これにより 1 発目の User プロンプトが確実にリクエストに含まれるようになる。
                    call_messages = [m for m in messages if m["role"] != "system"]
                else:
                    call_messages = messages
            else:
                call_messages = core.sanitize_messages_for_tools(messages)

            # Translate call_messages copy for LLM (if enabled).
            translated_call_messages = call_messages
            if tr_cfg is not None:
                try:
                    translated_call_messages = []
                    for m in call_messages:
                        role = m.get("role")
                        if role in ("system", "user", "assistant"):
                            content = m.get("content")
                            if isinstance(content, str) and content.strip():
                                # Determine src lang for UI side; if thread-local is set,
                                # translate.py will also auto-skip when target is English and
                                # text already looks English.
                                src_lang = ""
                                out, diag = translate_text(
                                    content,
                                    direction="to_llm",
                                    src_lang=src_lang,
                                    cfg=tr_cfg,
                                )
                                nm = dict(m)
                                nm["content"] = out
                                translated_call_messages.append(nm)
                                continue
                        translated_call_messages.append(m)
                except Exception:
                    pass

            call_messages = translated_call_messages

            tool_calls_list: List[Dict[str, Any]] = []
            assistant_text: str = ""
            use_responses_api = (env_get("UAGENT_RESPONSES", "") or "").lower() in (
                "1",
                "true",
            )

            def _env_default_true(name: str, default: bool = True) -> bool:
                v = (env_get(name, "") or "").strip().lower()
                if v == "":
                    return bool(default)
                return v in ("1", "true", "yes", "on")

            stream_responses = _env_default_true("UAGENT_STREAMING", default=True)

            # If translation is enabled, disable streaming to avoid mismatched partial outputs.
            # (We translate per-call, not per-delta.)
            if tr_cfg is not None and (
                (tr_cfg.to_llm or "").strip() or (tr_cfg.from_llm or "").strip()
            ):
                stream_responses = False

            # If using Responses API and reasoning=auto, disable streaming so we can retry once
            # (and avoid mixed partial outputs that cannot be "taken back").
            if use_responses_api and stream_responses:
                _r0 = (env_get("UAGENT_REASONING") or "").strip().lower()
                if _r0 == "auto":
                    stream_responses = False
                    try:
                        core.set_status(True, "LLM:auto")
                    except Exception:
                        pass

            send_tools_this_round = True
            max_retries_429 = int(env_get("UAGENT_429_MAX_RETRIES", "20"))
            retry_base = float(env_get("UAGENT_429_BACKOFF_BASE", "2"))
            retry_cap = float(env_get("UAGENT_429_BACKOFF_CAP", "65"))

            if provider == "gemini":
                attempt_429 = 0
                gemini_content_dump: Dict[str, Any] = {}
                while True:
                    try:
                        assistant_text, tool_calls_list, gemini_content_dump = (
                            gemini_chat_with_tools(
                                client,
                                depname,
                                call_messages,
                                cached_content=gemini_cache_name,
                                core=core,
                            )
                        )
                        break
                    except Exception as e:
                        if _is_rate_limit_error(e):
                            attempt_429 += 1
                            if attempt_429 > max_retries_429:
                                print(
                                    "[Gemini Error] "
                                    + _("429 retry limit (%(max_retries)s) reached.")
                                    % {"max_retries": max_retries_429}
                                )
                                print(repr(e))
                                return
                            _unused, new_client, _unused2 = make_client_fn(core)
                            client = new_client
                            ra = _extract_retry_after(e)
                            wait_s = _compute_retry_wait_seconds(
                                attempt=attempt_429,
                                retry_after_header=ra,
                                base=retry_base,
                                cap=retry_cap,
                            )
                            time.sleep(wait_s)
                            continue
                        print(
                            _(
                                "[Gemini Error] An error occurred while generating a response."
                            )
                        )
                        print(repr(e))
                        return
                # Translate assistant output (if enabled; avoid responses+streaming double output)
                if (
                    tr_cfg is not None
                    and isinstance(assistant_text, str)
                    and assistant_text.strip()
                    and not (use_responses_api and stream_responses)
                ):
                    out, diag = translate_text(
                        assistant_text,
                        direction="from_llm",
                        src_lang="",
                        cfg=tr_cfg,
                    )
                    if diag:
                        # Non-fatal: keep original output and show diagnostics.
                        print(f"[Translate Error] {diag}")
                    else:
                        assistant_text = out

                assistant_msg: Dict[str, Any] = {
                    "role": "assistant",
                    "content": assistant_text,
                }
                if tool_calls_list:
                    assistant_msg["tool_calls"] = tool_calls_list
                if isinstance(gemini_content_dump, dict) and gemini_content_dump:
                    assistant_msg["_gemini_content"] = gemini_content_dump
                messages.append(assistant_msg)
                # Web streaming (mode A): do not emit final assistant message to UI to avoid duplicates.
                if not bool(getattr(core, "_is_web", False)):
                    core.log_message(assistant_msg)

                if not tool_calls_list:
                    if not _effectively_empty_text(assistant_text):
                        # Responses+Streaming already printed deltas in parse_responses_stream(); avoid double-print.
                        if not (use_responses_api and stream_responses):
                            print(assistant_text)
                        append_result_to_outfile_fn(assistant_text)
                        try_open_images_from_text_fn(assistant_text)
                    break

            elif provider == "claude":
                attempt_429 = 0
                while True:
                    try:
                        assistant_text, tool_calls_list = claude_chat_with_tools(
                            client, depname, call_messages
                        )
                        break
                    except Exception as e:
                        if _is_rate_limit_error(e):
                            attempt_429 += 1
                            if attempt_429 > max_retries_429:
                                print(
                                    "[Claude Error] "
                                    + _("429 retry limit (%(max_retries)s) reached.")
                                    % {"max_retries": max_retries_429}
                                )
                                print(repr(e))
                                return
                            _unused, new_client, _unused2 = make_client_fn(core)
                            client = new_client
                            ra = _extract_retry_after(e)
                            wait_s = _compute_retry_wait_seconds(
                                attempt=attempt_429,
                                retry_after_header=ra,
                                base=retry_base,
                                cap=retry_cap,
                            )
                            time.sleep(wait_s)
                            continue
                        print(
                            _(
                                "[Claude Error] An error occurred while generating a response."
                            )
                        )
                        print(repr(e))
                        return
                # Translate assistant output (if enabled; avoid responses+streaming double output)
                if (
                    tr_cfg is not None
                    and isinstance(assistant_text, str)
                    and assistant_text.strip()
                    and not (use_responses_api and stream_responses)
                ):
                    out, diag = translate_text(
                        assistant_text,
                        direction="from_llm",
                        src_lang="",
                        cfg=tr_cfg,
                    )
                    if diag:
                        # Non-fatal: keep original output and show diagnostics.
                        print(f"[Translate Error] {diag}")
                    else:
                        assistant_text = out

                assistant_msg = {
                    "role": "assistant",
                    "content": assistant_text,
                }
                if tool_calls_list:
                    assistant_msg["tool_calls"] = tool_calls_list

                # Preserve OpenRouter reasoning chain (if present) by passing it back unmodified.
                if provider == "openrouter" and reasoning_details is not None:
                    try:
                        assistant_msg["reasoning_details"] = reasoning_details
                    except Exception:
                        pass

                messages.append(assistant_msg)
                core.log_message(assistant_msg)

                if not tool_calls_list:
                    if not _effectively_empty_text(assistant_text):
                        # Responses+Streaming already printed deltas in parse_responses_stream(); avoid double-print.
                        if not (use_responses_api and stream_responses):
                            print(assistant_text)
                        append_result_to_outfile_fn(assistant_text)
                        try_open_images_from_text_fn(assistant_text)
                    break

            else:  # OpenAI / Azure
                attempt_429 = 0
                while True:
                    try:
                        if use_responses_api:
                            use_gpt54_tool_search = _is_gpt54_tool_search_target(
                                provider=provider,
                                depname=depname,
                                use_responses_api=use_responses_api,
                            )
                            responses_tool_specs = (
                                _select_tool_specs_for_gpt54(call_messages)
                                if use_gpt54_tool_search
                                else None
                            )

                            instructions_str, input_msgs, req_tools = (
                                build_responses_request(
                                    call_messages,
                                    send_tools_this_round=send_tools_this_round,
                                    provider=provider,
                                    tool_specs=responses_tool_specs,
                                )
                            )

                            resp_kwargs: Dict[str, Any] = {
                                "model": depname,
                                "input": input_msgs,
                            }

                            # Optional Responses API knobs via env (OpenAI SDK >= 2.x)
                            # - UAGENT_REASONING: auto|minimal|low|medium|high|xhigh|off (unset/off => do not send)
                            # - UAGENT_VERBOSITY: low|medium|high|off (unset/off => do not send)
                            _reasoning = (
                                (env_get("UAGENT_REASONING") or "").strip().lower()
                            )
                            _auto_user_text = ""
                            _effort_used = None

                            if _reasoning in (
                                "minimal",
                                "low",
                                "medium",
                                "high",
                                "xhigh",
                            ):
                                _effort_used = _reasoning
                            elif _reasoning == "auto":
                                _auto_user_text = _extract_latest_user_text(
                                    call_messages
                                )
                                if _is_thinking_task(_auto_user_text):
                                    _effort_used = _choose_auto_effort(_auto_user_text)

                            if _effort_used in (
                                "minimal",
                                "low",
                                "medium",
                                "high",
                                "xhigh",
                            ):
                                resp_kwargs["reasoning"] = {"effort": _effort_used}
                                try:
                                    if _reasoning == "auto":
                                        core.set_status(
                                            True, f"LLM:auto->{_effort_used}"
                                        )
                                    else:
                                        core.set_status(True, f"LLM:{_effort_used}")
                                except Exception:
                                    pass

                            _verbosity = (
                                (env_get("UAGENT_VERBOSITY") or "").strip().lower()
                            )
                            if _verbosity in ("low", "medium", "high"):
                                _text_cfg = resp_kwargs.get("text")
                                if not isinstance(_text_cfg, dict):
                                    _text_cfg = {}
                                _text_cfg["verbosity"] = _verbosity
                                resp_kwargs["text"] = _text_cfg
                            if instructions_str is not None:
                                resp_kwargs["instructions"] = instructions_str
                            if send_tools_this_round and req_tools:
                                resp_kwargs["tools"] = req_tools
                                resp_kwargs["tool_choice"] = "auto"

                            if stream_responses:
                                resp = client.responses.create(
                                    **resp_kwargs,
                                    stream=True,
                                )
                                (
                                    assistant_text,
                                    tool_calls_list,
                                ) = parse_responses_stream(
                                    resp,
                                    # In Web mode, parse_responses_stream streams deltas via core.log_message.
                                    print_delta_fn=(
                                        None
                                        if bool(getattr(core, "_is_web", False))
                                        else (
                                            lambda s: (
                                                print(s, end="", flush=True)
                                                if s
                                                else None
                                            )
                                        )
                                    ),
                                    core=core,
                                )
                                # ensure newline after streaming output
                                if assistant_text and not bool(
                                    getattr(core, "_is_web", False)
                                ):
                                    print("")
                            else:
                                resp = client.responses.create(**resp_kwargs)
                                assistant_text, tool_calls_list = (
                                    parse_responses_response(resp)
                                )

                                # Auto retry (non-streaming only): if output looks unusable, retry once with higher effort.
                                if (
                                    _reasoning == "auto"
                                    and _effort_used
                                    in ("minimal", "low", "medium", "high", "xhigh")
                                    and not tool_calls_list
                                    and _auto_low_quality(
                                        _auto_user_text, assistant_text
                                    )
                                ):
                                    _next_effort = _bump_effort(_effort_used)
                                    if _next_effort in (
                                        "minimal",
                                        "low",
                                        "medium",
                                        "high",
                                        "xhigh",
                                    ):
                                        resp_kwargs["reasoning"] = {
                                            "effort": _next_effort
                                        }
                                        try:
                                            core.set_status(
                                                True, f"LLM:auto->{_next_effort}"
                                            )
                                        except Exception:
                                            pass
                                        resp2 = client.responses.create(**resp_kwargs)
                                        assistant_text, tool_calls_list = (
                                            parse_responses_response(resp2)
                                        )
                        else:
                            req_tools = (
                                tools.get_tool_specs()
                                if send_tools_this_round
                                else None
                            )

                            chat_kwargs: Dict[str, Any] = {
                                "model": depname,
                                "messages": call_messages,
                            }
                            if send_tools_this_round and req_tools is not None:
                                chat_kwargs["tools"] = req_tools
                                chat_kwargs["tool_choice"] = "auto"

                            # OpenRouter provider routing (optional)
                            # NOTE: openai-python ChatCompletions does NOT accept unknown top-level kwargs.
                            # Route options must be sent via extra_body.
                            # - default: do nothing (OpenRouter decides routing)
                            # - if UAGENT_OPENROUTER_PROVIDER_IGNORE is set, send extra_body.provider.ignore
                            # - if UAGENT_OPENROUTER_REASONING is enabled, send extra_body.reasoning.enabled
                            if provider == "openrouter":
                                # Enable OpenRouter reasoning_details (Chat Completions extension)
                                try:
                                    _raw_reason = (env_get("UAGENT_OPENROUTER_REASONING", "0") or "").strip().lower()
                                    if _raw_reason in ("1", "true", "yes", "on", "enabled"):
                                        _eb = chat_kwargs.get("extra_body")
                                        if not isinstance(_eb, dict):
                                            _eb = {}
                                        _eb["reasoning"] = {"enabled": True}
                                        chat_kwargs["extra_body"] = _eb
                                except Exception:
                                    pass

                                try:
                                    _raw_ignore = (
                                        env_get("UAGENT_OPENROUTER_PROVIDER_IGNORE", "")
                                        or ""
                                    ).strip()
                                    if _raw_ignore:
                                        _ignores = [
                                            s.strip()
                                            for s in _raw_ignore.split(",")
                                            if s.strip()
                                        ]
                                        if _ignores:
                                            _eb = chat_kwargs.get("extra_body")
                                            if not isinstance(_eb, dict):
                                                _eb = {}
                                            _eb["provider"] = {"ignore": _ignores}
                                            chat_kwargs["extra_body"] = _eb
                                            # Ensure we don't send unsupported top-level 'provider'
                                            chat_kwargs.pop("provider", None)
                                except Exception:
                                    pass

                            # OpenRouter/Azure-proxy compatibility: some stacks validate tools[i].parameters
                            # at the top-level (older/alternate schema), so mirror function.parameters.
                            if provider == "openrouter":
                                try:
                                    _new_tools = []
                                    for _t in chat_kwargs.get("tools") or []:
                                        if (
                                            isinstance(_t, dict)
                                            and "parameters" not in _t
                                            and isinstance(_t.get("function"), dict)
                                            and isinstance(
                                                _t["function"].get("parameters"), dict
                                            )
                                        ):
                                            _t2 = _t.copy()
                                            _t2["parameters"] = _t["function"][
                                                "parameters"
                                            ]
                                            _new_tools.append(_t2)
                                        else:
                                            _new_tools.append(_t)
                                    chat_kwargs["tools"] = _new_tools
                                except Exception:
                                    pass
                                # Rename schema key to 'operations' for Azure/OpenAI-proxy compatibility; runtime accepts both.
                                try:
                                    _fixed_tools = []
                                    for _t in chat_kwargs.get("tools") or []:
                                        if not (
                                            isinstance(_t, dict)
                                            and isinstance(_t.get("function"), dict)
                                        ):
                                            _fixed_tools.append(_t)
                                            continue

                                        _t2 = _t.copy()
                                        _fn = _t2.get("function") or {}
                                        _fn2 = (
                                            _fn.copy() if isinstance(_fn, dict) else _fn
                                        )

                                        if (
                                            isinstance(_fn2, dict)
                                            and _fn2.get("name") == "libcst_transform"
                                        ):
                                            _params = _fn2.get("parameters")
                                            if (
                                                isinstance(_params, dict)
                                                and _params.get("type") == "object"
                                            ):
                                                _props = _params.get("properties")
                                                if (
                                                    isinstance(_props, dict)
                                                    and "ops" in _props
                                                    and "operations" not in _props
                                                ):
                                                    _params2 = _params.copy()
                                                    _props2 = _props.copy()
                                                    _props2["operations"] = _props2.pop(
                                                        "ops"
                                                    )
                                                    _params2["properties"] = _props2
                                                    _req = _params2.get("required")
                                                    if isinstance(_req, list):
                                                        _params2["required"] = [
                                                            (
                                                                "operations"
                                                                if x == "ops"
                                                                else x
                                                            )
                                                            for x in _req
                                                        ]
                                                    _fn2["parameters"] = _params2
                                                    _t2["function"] = _fn2
                                                    if isinstance(
                                                        _t2.get("parameters"), dict
                                                    ):
                                                        _t2["parameters"] = _params2

                                        _fixed_tools.append(_t2)
                                    chat_kwargs["tools"] = _fixed_tools
                                except Exception:
                                    pass

                                # OpenRouter/Azure-proxy odd validator: handle_mcp_v2 rejects tool_arguments as required.
                                # To avoid Azure/OpenAI proxy schema rejection, drop tool_arguments from schema surface.
                                try:
                                    _fixed_tools = []
                                    for _t in chat_kwargs.get("tools") or []:
                                        if not (
                                            isinstance(_t, dict)
                                            and isinstance(_t.get("function"), dict)
                                        ):
                                            _fixed_tools.append(_t)
                                            continue

                                        _t2 = _t.copy()
                                        _fn = _t2.get("function") or {}
                                        _fn2 = (
                                            _fn.copy() if isinstance(_fn, dict) else _fn
                                        )

                                        if (
                                            isinstance(_fn2, dict)
                                            and _fn2.get("name") == "handle_mcp_v2"
                                        ):
                                            _params = _fn2.get("parameters")
                                            if (
                                                isinstance(_params, dict)
                                                and _params.get("type") == "object"
                                            ):
                                                _props = _params.get("properties")
                                                if (
                                                    isinstance(_props, dict)
                                                    and "tool_arguments" in _props
                                                ):
                                                    _params2 = _params.copy()
                                                    _props2 = _props.copy()
                                                    _props2.pop("tool_arguments", None)
                                                    _params2["properties"] = _props2
                                                    # keep required as-is here; it will be re-normalized below.
                                                    _fn2["parameters"] = _params2
                                                    _t2["function"] = _fn2
                                                    if isinstance(
                                                        _t2.get("parameters"), dict
                                                    ):
                                                        _t2["parameters"] = _params2

                                        _fixed_tools.append(_t2)
                                    chat_kwargs["tools"] = _fixed_tools
                                except Exception:
                                    pass

                                # OpenRouter/OpenAI-proxy strict schema: mcp_servers_add.env is a free-form mapping.

                                # Some validators effectively disallow object properties without fixed 'properties', causing the

                                # property to be dropped and then failing because 'required' still includes 'env'.

                                # To avoid request rejection, hide 'env' from the tool schema surface for openrouter.

                                try:

                                    _fixed_tools = []

                                    for _t in chat_kwargs.get("tools") or []:

                                        if not (
                                            isinstance(_t, dict)
                                            and isinstance(_t.get("function"), dict)
                                        ):

                                            _fixed_tools.append(_t)

                                            continue

                                        _t2 = _t.copy()

                                        _fn = _t2.get("function") or {}

                                        _fn2 = (
                                            _fn.copy() if isinstance(_fn, dict) else _fn
                                        )

                                        if (
                                            isinstance(_fn2, dict)
                                            and _fn2.get("name") == "mcp_servers_add"
                                        ):

                                            _params = _fn2.get("parameters")

                                            if (
                                                isinstance(_params, dict)
                                                and _params.get("type") == "object"
                                            ):

                                                _props = _params.get("properties")

                                                if (
                                                    isinstance(_props, dict)
                                                    and "env" in _props
                                                ):

                                                    _params2 = _params.copy()

                                                    _props2 = _props.copy()

                                                    _props2.pop("env", None)

                                                    _params2["properties"] = _props2

                                                    _req = _params2.get("required")

                                                    if isinstance(_req, list):

                                                        _params2["required"] = [
                                                            x
                                                            for x in _req
                                                            if x != "env"
                                                        ]

                                                    _fn2["parameters"] = _params2

                                                    _t2["function"] = _fn2

                                                    if isinstance(
                                                        _t2.get("parameters"), dict
                                                    ):

                                                        _t2["parameters"] = _params2

                                        _fixed_tools.append(_t2)

                                    chat_kwargs["tools"] = _fixed_tools

                                except Exception:

                                    pass

                                # OpenRouter/Azure-proxy strict schema: required must include all property keys.
                                # Some providers reject schemas where required is missing or incomplete.
                                try:
                                    _fixed_tools = []
                                    for _t in chat_kwargs.get("tools") or []:
                                        if not (
                                            isinstance(_t, dict)
                                            and isinstance(_t.get("function"), dict)
                                        ):
                                            _fixed_tools.append(_t)
                                            continue

                                        _t2 = _t.copy()
                                        _fn = _t2.get("function") or {}
                                        _fn2 = (
                                            _fn.copy() if isinstance(_fn, dict) else _fn
                                        )
                                        _params = (
                                            _fn2.get("parameters")
                                            if isinstance(_fn2, dict)
                                            else None
                                        )

                                        if (
                                            isinstance(_params, dict)
                                            and _params.get("type") == "object"
                                        ):
                                            _props = _params.get("properties")
                                            if isinstance(_props, dict) and _props:

                                                _params2 = _params.copy()
                                                _params2["required"] = list(
                                                    _props.keys()
                                                )
                                                _fn2["parameters"] = _params2
                                                _t2["function"] = _fn2
                                                if isinstance(
                                                    _t2.get("parameters"), dict
                                                ):
                                                    _t2["parameters"] = _params2

                                        _fixed_tools.append(_t2)
                                    chat_kwargs["tools"] = _fixed_tools
                                except Exception:
                                    pass

                                # OpenRouter/Azure-proxy strict schema: recursively enforce additionalProperties:false
                                # for all object schemas (including nested objects/arrays/combinators).
                                try:

                                    def _fix_schema(_s: Any) -> Any:
                                        if not isinstance(_s, dict):
                                            return _s

                                        _t = _s.get("type")
                                        if _t == "object":
                                            _props = _s.get("properties")
                                            if isinstance(_props, dict):
                                                # Only enforce additionalProperties:false on objects that declare properties.
                                                # Some strict validators reject object schemas with additionalProperties:false
                                                # but without properties.
                                                if "additionalProperties" not in _s:
                                                    _s = _s.copy()
                                                    _s["additionalProperties"] = False

                                                _new_props = {}
                                                _changed = False
                                                for _k, _v in _props.items():
                                                    _v2 = _fix_schema(_v)
                                                    _new_props[_k] = _v2
                                                    _changed = _changed or (
                                                        _v2 is not _v
                                                    )
                                                if _changed:
                                                    _s = _s.copy()
                                                    _s["properties"] = _new_props

                                        # arrays
                                        if _t == "array" and isinstance(
                                            _s.get("items"), (dict, list)
                                        ):
                                            _items = _s.get("items")
                                            if isinstance(_items, dict):
                                                _it2 = _fix_schema(_items)
                                                if _it2 is not _items:
                                                    _s = _s.copy()
                                                    _s["items"] = _it2
                                            elif isinstance(_items, list):
                                                _new_items = []
                                                _changed = False
                                                for _it in _items:
                                                    _it2 = _fix_schema(_it)
                                                    _new_items.append(_it2)
                                                    _changed = _changed or (
                                                        _it2 is not _it
                                                    )
                                                if _changed:
                                                    _s = _s.copy()
                                                    _s["items"] = _new_items

                                        # combinators
                                        for _ck in ("anyOf", "oneOf", "allOf"):
                                            _cv = _s.get(_ck)
                                            if isinstance(_cv, list) and _cv:
                                                _new_cv = []
                                                _changed = False
                                                for _it in _cv:
                                                    _it2 = _fix_schema(_it)
                                                    _new_cv.append(_it2)
                                                    _changed = _changed or (
                                                        _it2 is not _it
                                                    )
                                                if _changed:
                                                    _s = _s.copy()
                                                    _s[_ck] = _new_cv

                                        return _s

                                    _tools2 = []
                                    for _t in chat_kwargs.get("tools") or []:
                                        if not (
                                            isinstance(_t, dict)
                                            and isinstance(_t.get("function"), dict)
                                        ):
                                            _tools2.append(_t)
                                            continue
                                        _t2 = _t.copy()
                                        _fn = _t2.get("function") or {}
                                        _fn2 = (
                                            _fn.copy() if isinstance(_fn, dict) else _fn
                                        )
                                        _params = (
                                            _fn2.get("parameters")
                                            if isinstance(_fn2, dict)
                                            else None
                                        )
                                        if isinstance(_params, dict):
                                            _params2 = _fix_schema(_params)
                                            if _params2 is not _params:
                                                _fn2["parameters"] = _params2
                                                _t2["function"] = _fn2
                                                if isinstance(
                                                    _t2.get("parameters"), dict
                                                ):
                                                    _t2["parameters"] = _params2
                                        _tools2.append(_t2)
                                    chat_kwargs["tools"] = _tools2
                                except Exception:
                                    pass

                            # Final OpenRouter/Azure-proxy compatibility sync:
                            # - ensure tools[i].parameters always mirrors function.parameters
                            # - ensure required matches properties keys (no extra required keys)
                            try:
                                _fixed_tools = []
                                for _t in chat_kwargs.get("tools") or []:
                                    if not (
                                        isinstance(_t, dict)
                                        and isinstance(_t.get("function"), dict)
                                    ):
                                        _fixed_tools.append(_t)
                                        continue

                                    _t2 = _t.copy()
                                    _fn = _t2.get("function") or {}
                                    _fn2 = _fn.copy() if isinstance(_fn, dict) else _fn
                                    _params = (
                                        _fn2.get("parameters")
                                        if isinstance(_fn2, dict)
                                        else None
                                    )

                                    if isinstance(_params, dict):
                                        # Always mirror to top-level parameters (some stacks validate only this)
                                        _t2["parameters"] = _params

                                        # Strict validator: required must be an array containing every property key,
                                        # and must not contain keys not present in properties.
                                        if _params.get("type") == "object":
                                            _props = _params.get("properties")
                                            if isinstance(_props, dict):
                                                _params2 = _params.copy()
                                                _params2["required"] = list(
                                                    _props.keys()
                                                )
                                                _fn2["parameters"] = _params2
                                                _t2["function"] = _fn2
                                                _t2["parameters"] = _params2

                                    _fixed_tools.append(_t2)

                                chat_kwargs["tools"] = _fixed_tools
                            except Exception:
                                pass

                            # OpenRouter-specific fallback models support (does not affect other providers)
                            # Enabled only when:
                            # - provider == "openrouter"
                            # - UAGENT_OPENROUTER_DEPNAME == "openrouter/auto" (depname passed here)
                            # - UAGENT_OPENROUTER_FALLBACK_MODELS is set (comma-separated model IDs)
                            if (
                                provider == "openrouter"
                                and (depname or "").strip() == "openrouter/auto"
                            ):
                                raw_fb = (
                                    env_get("UAGENT_OPENROUTER_FALLBACK_MODELS", "")
                                    or ""
                                ).strip()
                                if raw_fb:
                                    fb_models = [
                                        s.strip()
                                        for s in raw_fb.split(",")
                                        if s.strip()
                                    ]
                                    if fb_models:
                                        chat_kwargs["models"] = fb_models
                            if env_get("UAGENT_DEBUG_TOOLS") == "1":
                                try:
                                    import json as _json

                                    _tools = chat_kwargs.get("tools") or []
                                    print("[debug] tools_count=", len(_tools))
                                    for _i in (0, 32):
                                        if 0 <= _i < len(_tools):
                                            _ti = _tools[_i]
                                            print(
                                                f"[debug] chat_kwargs.tools[{_i}].keys=",
                                                (
                                                    sorted(_ti.keys())
                                                    if isinstance(_ti, dict)
                                                    else None
                                                ),
                                            )
                                            print(
                                                f"[debug] chat_kwargs.tools[{_i}]=",
                                                (
                                                    _json.dumps(_ti, ensure_ascii=False)
                                                    if _ti is not None
                                                    else None
                                                ),
                                            )
                                except Exception as _e:
                                    print("[debug] tools dump failed:", repr(_e))

                            resp = client.chat.completions.create(**chat_kwargs)
                        break
                    except Exception as e:
                        # NOTE: i18n function _ is a global import, but some exception paths
                        # previously triggered UnboundLocalError: '_' due to local-scope issues.
                        # Use a safe fallback translator to avoid crashing while reporting errors.
                        def _t(s: str) -> str:
                            return s

                        try:
                            _t = _
                        except Exception:
                            pass

                        # Context-window overflow (OpenAI Responses streaming can raise APIError)
                        # We handle it explicitly to avoid the generic error path.
                        if (
                            "context window" in str(e).lower()
                            or "exceeds the context" in str(e).lower()
                        ):
                            print(
                                "[Azure/OpenAI Error] "
                                + _t("Input exceeds the context window.")
                            )
                            print(repr(e))
                            return

                        if BadRequestError is not None and isinstance(
                            e, BadRequestError
                        ):
                            print("[Azure/OpenAI Error] " + _t("400 BadRequest"))
                            print(f"Error code: 400 - {e}")
                            return
                        if APIConnectionError is not None and isinstance(
                            e, APIConnectionError
                        ):
                            print("[Azure/OpenAI Error] " + _t("Connection error"))
                            print(repr(e))
                            return
                        if isinstance(e, URLError):
                            print("[Network Error]")
                            print(repr(e))
                            return
                        if _is_rate_limit_error(e):
                            attempt_429 += 1
                            if attempt_429 > max_retries_429:
                                print(
                                    "[Azure/OpenAI Error] "
                                    + _t("429 retry limit (%(max_retries)s) reached.")
                                    % {"max_retries": max_retries_429}
                                )
                                print(repr(e))
                                return
                            _unused, new_client, _unused2 = make_client_fn(core)
                            client = new_client
                            ra = _extract_retry_after(e)
                            wait_s = _compute_retry_wait_seconds(
                                attempt=attempt_429,
                                retry_after_header=ra,
                                base=retry_base,
                                cap=retry_cap,
                            )
                            time.sleep(wait_s)
                            continue
                        print("[LLM Error] " + _t("Unexpected exception."))
                        print(repr(e))
                        return

                try:
                    if use_responses_api:
                        # Responses API: assistant_text/tool_calls_list are already parsed above
                        # - streaming: parse_responses_stream(resp)
                        # - non-streaming: parse_responses_response(resp)
                        pass
                    else:
                        choice = resp.choices[0]
                        msg = choice.message

                        # OpenRouter ChatCompletions can return reasoning_details when enabled via extra_body.
                        reasoning_details = None
                        if provider == "openrouter":
                            try:
                                reasoning_details = getattr(msg, "reasoning_details", None)
                            except Exception:
                                reasoning_details = None

                        raw_tool_calls = getattr(msg, "tool_calls", None) or []
                        for tc in raw_tool_calls:
                            tc_id = getattr(tc, "id", None)
                            fn_obj = getattr(tc, "function", None)

                            if fn_obj is None and isinstance(tc, dict):
                                tc_id = tc.get("id")
                                fn_obj = tc.get("function") or {}

                            fn_name = getattr(fn_obj, "name", None)
                            fn_args = getattr(fn_obj, "arguments", None)

                            if isinstance(fn_obj, dict):
                                fn_name = fn_obj.get("name")
                                fn_args = fn_obj.get("arguments")

                            if not isinstance(fn_name, str) or not fn_name:
                                continue

                            if isinstance(fn_args, dict):
                                fn_args = json.dumps(fn_args, ensure_ascii=False)
                            elif fn_args is None:
                                fn_args = "{}"
                            elif not isinstance(fn_args, str):
                                fn_args = str(fn_args)

                            tool_calls_list.append(
                                {
                                    "id": tc_id or "",
                                    "type": "function",
                                    "function": {
                                        "name": fn_name,
                                        "arguments": fn_args,
                                    },
                                }
                            )

                        raw_content = getattr(msg, "content", "")
                        if isinstance(raw_content, str):
                            assistant_text = raw_content
                        elif raw_content is None:
                            assistant_text = ""
                        elif isinstance(raw_content, list):
                            parts = []
                            for item in raw_content:
                                if isinstance(item, str):
                                    parts.append(item)
                                elif isinstance(item, dict):
                                    if isinstance(item.get("text"), str):
                                        parts.append(item["text"])
                                    elif isinstance(item.get("content"), str):
                                        parts.append(item["content"])
                                    elif isinstance(item.get("value"), str):
                                        parts.append(item["value"])
                                else:
                                    txt = getattr(item, "text", None)
                                    if isinstance(txt, str):
                                        parts.append(txt)
                            assistant_text = "".join(parts)
                        else:
                            assistant_text = str(raw_content)

                except Exception as e:
                    print(
                        "[ERROR] "
                        + _("Error while parsing response: %(err)s") % {"err": e}
                    )
                    traceback.print_exc()
                    return

                assistant_msg = {
                    "role": "assistant",
                    "content": assistant_text,
                }
                if tool_calls_list:
                    assistant_msg["tool_calls"] = tool_calls_list

                # Preserve OpenRouter reasoning chain (if present) by passing it back unmodified.
                if provider == "openrouter" and reasoning_details is not None:
                    try:
                        assistant_msg["reasoning_details"] = reasoning_details
                    except Exception:
                        pass

                messages.append(assistant_msg)
                core.log_message(assistant_msg)

                eff_empty = _effectively_empty_text(assistant_text)
                if env_get("UAGENT_DEBUG_FLOW") == "1":
                    try:
                        _t = assistant_text if isinstance(assistant_text, str) else str(assistant_text)
                        _u = _t.encode("utf-8", errors="backslashreplace").decode("utf-8", errors="replace")
                        _tool_names = []
                        try:
                            _tool_names = [tc.get("function", {}).get("name") for tc in tool_calls_list][:5]
                        except Exception:
                            pass
                        print(
                            "[debug] llm_resp: "
                            f"tool_calls={len(tool_calls_list)} names={_tool_names} "
                            f"eff_empty={eff_empty} len={len(_t)} repr={_u!r}",
                            file=sys.stderr,
                        )
                    except Exception:
                        pass

                if (
                    not tool_calls_list
                    and eff_empty
                ):
                    empty_no_tool_rounds += 1

                    # Optional debug for empty assistant responses (no tool calls).
                    if env_get("UAGENT_DEBUG_EMPTY") == "1":
                        try:
                            _t = assistant_text if isinstance(assistant_text, str) else str(assistant_text)
                            _u = _t.encode("utf-8", errors="backslashreplace").decode("utf-8", errors="replace")
                            print(
                                "[debug] empty assistant_text (no tool_calls): "
                                f"round={empty_no_tool_rounds}/{empty_no_tool_max} "
                                f"len={len(_t)} repr={_u!r}",
                                file=sys.stderr,
                            )
                        except Exception:
                            pass

                    # Optional nudge to recover from providers that sometimes emit an empty message
                    # right after tool calls.
                    if (
                        empty_no_tool_rounds == 1
                        and env_get("UAGENT_EMPTY_NO_TOOL_NUDGE", "1") != "0"
                    ):
                        try:
                            nudge_msg = {
                                "role": "user",
                                "content": "前回のアシスタント返答が空でした。直前のツール結果を踏まえて回答してください。",
                            }
                            messages.append(nudge_msg)
                            core.log_message(nudge_msg)
                        except Exception:
                            pass

                    if empty_no_tool_rounds <= empty_no_tool_max:
                        continue

                    warn_text = (
                        "[WARN] LLM returned an empty assistant message without tool calls.\
"
                        f"provider={provider} depname={depname} "
                        f"empty_no_tool_rounds={empty_no_tool_rounds} (max={empty_no_tool_max})\
"
                        "This may happen with OpenAI-compatible local providers after tool calls. "
                        "You can try setting UAGENT_EMPTY_NO_TOOL_MAX to a higher value, or switching provider."
                    )
                    try:
                        warn_msg = {"role": "assistant", "content": warn_text}
                        messages.append(warn_msg)
                        core.log_message(warn_msg)
                    except Exception:
                        pass
                    try:
                        print(warn_text, file=sys.stderr)
                    except Exception:
                        pass
                    break
                else:
                    empty_no_tool_rounds = 0

                if not tool_calls_list:
                    if not _effectively_empty_text(assistant_text):
                        # Responses+Streaming already printed deltas in parse_responses_stream(); avoid double-print.
                        if not (use_responses_api and stream_responses):
                            print(assistant_text)
                        append_result_to_outfile_fn(assistant_text)
                        try_open_images_from_text_fn(assistant_text)
                    break

            executed_new_tool = False

            for tc in tool_calls_list:
                func = tc["function"]
                name = func["name"]
                arg_str = func.get("arguments") or "{}"
                tool_cache_key = None
                parsed_args = None
                tool_result = ""

                try:
                    parsed_args = json.loads(arg_str)
                    if not isinstance(parsed_args, dict):
                        raise ValueError(
                            "arguments は JSON object である必要があります。"
                        )
                except Exception as e:
                    tb = traceback.format_exc()
                    tool_result = (
                        f"[tool args error] name={name!r} raw={arg_str!r} "
                        f"err={type(e).__name__}: {e}\nTraceback:\n{tb}"
                    )
                    tool_cache_key = f"error:{name}:{arg_str}"
                    parsed_args = None

                if parsed_args is not None:
                    canonical_args = json.dumps(
                        parsed_args, ensure_ascii=False, sort_keys=True
                    )
                    tool_cache_key = json.dumps(
                        {"name": name, "args": canonical_args},
                        ensure_ascii=False,
                        sort_keys=True,
                    )

                    cached = (
                        tool_result_cache.get(tool_cache_key)
                        if use_tool_result_cache
                        else None
                    )
                    if cached is not None:
                        tool_result = (
                            "[INFO] 同一内容のツール呼び出しのため、前回の結果を再利用します。\n"
                            + cached
                        )
                    else:
                        core.set_status(True, f"tool:{name}")
                        try:
                            # ファイルアクセスをキャッシュ管理に記録
                            if name == "read_file" and "filename" in parsed_args:
                                cache_mgr.record_file_access(parsed_args["filename"])

                            tool_result = tools.run_tool(name, parsed_args)
                        except Exception as e:
                            tb = traceback.format_exc()
                            tool_result = (
                                f"[tool runtime error] name={name!r} "
                                f"err={type(e).__name__}: {e}\nTraceback:\n{tb}"
                            )
                        tool_result_cache[tool_cache_key] = tool_result
                        executed_new_tool = True

                elif tool_cache_key:
                    tool_result_cache[tool_cache_key] = tool_result

                tool_msg = {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "name": name,
                    "content": tool_result,
                }
                messages.append(tool_msg)
                core.log_message(tool_msg)

            core.set_status(True, "LLM")

            if executed_new_tool:
                reuse_only_rounds = 0
            else:
                reuse_only_rounds += 1
                if reuse_only_rounds >= 3:
                    print(
                        "[WARN] 3 ラウンド連続で同一ツール結果の再利用のみとなったため、"
                        "ループ防止のため処理を終了しました。"
                    )
                    break

    finally:
        # セッション中（プログラム終了まで）キャッシュを保持するため、ここでは削除しない。
        # クリーンアップは cli.py のメインループを抜けた際の finally で行う。
        core.set_status(False, "")
