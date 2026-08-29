"""Opt-in LM Studio Python SDK transport.

This module is deliberately isolated from the OpenAI-compatible transports.
The SDK owns the tool-call loop through ``LLM.act``; the adapter only converts
uag tool specifications and exposes the small client surface used by uagent.
"""

from __future__ import annotations

import queue
import re
import threading
from types import SimpleNamespace
from typing import Any, Callable

from ..env_utils import env_get

_SYNTHETIC_REASONING = re.compile(
    r"__LM_STUDIO_INTERNAL_LSEP_SYNTHETIC_REASONING_END_[A-Za-z0-9_]+__"
)


def _text(value: Any) -> str:
    value = getattr(value, "content", value)
    return _SYNTHETIC_REASONING.sub("", str(value or "")).strip()


def _fragment_text(value: Any) -> str:
    """Extract a streaming fragment without discarding meaningful spaces."""
    value = getattr(value, "content", value)
    return _SYNTHETIC_REASONING.sub("", str(value or ""))


def _chat_input(messages: list[dict[str, Any]] | None) -> Any:
    """Build the SDK Chat object while retaining role boundaries."""
    import lmstudio as lms

    normalized: list[dict[str, Any]] = []
    for message in messages or []:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "user")
        content = message.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                str(item.get("text", ""))
                for item in content
                if isinstance(item, dict) and item.get("text")
            )
        normalized.append({"role": role, "content": str(content or "")})
    try:
        return lms.Chat.from_history({"messages": normalized})
    except Exception:
        return _prompt(messages)


def _prompt(messages: list[dict[str, Any]] | None) -> str:
    parts: list[str] = []
    for message in messages or []:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "user")
        content = message.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                str(item.get("text", ""))
                for item in content
                if isinstance(item, dict) and item.get("text")
            )
        parts.append(f"{role}: {content}")
    return "\n".join(parts)


def _python_type(schema: dict[str, Any]) -> type[Any]:
    kind = str(schema.get("type") or "string").lower()
    return {
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,
    }.get(kind, str)


def _sdk_tools(specs: Any, core: Any = None) -> list[Any]:
    """Convert OpenAI-shaped tool specs into SDK ToolFunctionDef objects."""
    if not isinstance(specs, list):
        return []
    import lmstudio as lms
    from .. import tools as uagent_tools

    result: list[Any] = []
    for spec in specs:
        fn = spec.get("function", {}) if isinstance(spec, dict) else {}
        if not isinstance(fn, dict) or not fn.get("name"):
            continue
        name = str(fn["name"])
        parameters_schema = fn.get("parameters") or {}
        properties = (
            parameters_schema.get("properties", {})
            if isinstance(parameters_schema, dict)
            else {}
        )
        parameters = {
            str(key): _python_type(value if isinstance(value, dict) else {})
            for key, value in properties.items()
        }

        def implementation(_name: str = name, **arguments: Any) -> Any:
            # Reuse uag's normal executor so hooks, computer handling, output
            # normalization, and session messages remain consistent with the
            # OpenAI-compatible transports.
            if core is not None:
                from uuid import uuid4
                from ..llm_flow_helpers import _execute_tool_calls

                tool_call = {
                    "id": f"call_sdk_{uuid4().hex}",
                    "type": "function",
                    "function": {
                        "name": _name,
                        "arguments": __import__("json").dumps(
                            arguments, ensure_ascii=False
                        ),
                    },
                }
                messages = getattr(core, "_lmstudio_sdk_messages", None)
                cache_mgr = getattr(core, "_lmstudio_sdk_cache_mgr", None)
                if isinstance(messages, list):
                    messages.append(
                        {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [tool_call],
                        }
                    )
                    _execute_tool_calls(
                        tool_calls_list=[tool_call],
                        messages=messages,
                        core=core,
                        cache_mgr=cache_mgr,
                    )
                    if messages and isinstance(messages[-1], dict):
                        return messages[-1].get("content", "")
            return uagent_tools.run_tool(_name, arguments)

        result.append(
            lms.ToolFunctionDef(
                name=name,
                description=str(fn.get("description") or name),
                parameters=parameters,
                implementation=implementation,
            )
        )
    return result


class LMStudioSDKClient:
    """OpenAI-shaped adapter backed by LM Studio's native Python SDK."""

    def __init__(self, model_name: str) -> None:
        import lmstudio as lms

        self._model = lms.llm(model_name or None)
        self._core: Any = None
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(
        self,
        *,
        model: str = "",
        messages: list[dict[str, Any]] | None = None,
        stream: bool = False,
        tools: Any = None,
        **kwargs: Any,
    ) -> Any:
        del model, kwargs
        prompt = _chat_input(messages)
        sdk_tools = _sdk_tools(tools, self._core)
        if sdk_tools:
            if stream:
                return self._act_stream(prompt, sdk_tools)
            text = self._act_text(prompt, sdk_tools)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=text), finish_reason="stop"
                    )
                ]
            )
        if stream:
            return self._stream(prompt)
        result = self._model.respond(prompt)
        text = _text(result)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=text), finish_reason="stop"
                )
            ]
        )

    def _act_text(self, prompt: Any, sdk_tools: list[Any]) -> str:
        """Run SDK act() and collect visible prediction fragments."""
        parts: list[str] = []
        pending = ""
        marker_seen = False

        def on_fragment(fragment: Any, _index: int) -> None:
            nonlocal marker_seen, pending
            raw = str(getattr(fragment, "content", fragment) or "")
            if marker_seen:
                parts.append(raw)
                return
            pending += raw
            match = _SYNTHETIC_REASONING.search(pending)
            if match is not None:
                marker_seen = True
                parts.clear()
                parts.append(pending[match.end() :])
                pending = ""

        self._model.act(prompt, sdk_tools, on_prediction_fragment=on_fragment)
        if not marker_seen:
            parts.append(pending)
        return "".join(parts).strip()

    def _act_stream(self, prompt: str, sdk_tools: list[Any]):
        """Bridge SDK act() callbacks to the OpenAI-style delta iterator."""
        events: queue.Queue[tuple[str, Any]] = queue.Queue()
        done = object()

        marker_seen = False
        pending = ""

        def on_fragment(fragment: Any, _index: int) -> None:
            nonlocal marker_seen, pending
            raw = str(getattr(fragment, "content", fragment) or "")
            if marker_seen:
                if raw:
                    events.put(("delta", raw))
                return
            pending += raw
            match = _SYNTHETIC_REASONING.search(pending)
            if match is not None:
                marker_seen = True
                visible = pending[match.end() :]
                pending = ""
                if visible:
                    events.put(("delta", visible))

        def run() -> None:
            try:
                result = self._model.act(
                    prompt,
                    sdk_tools,
                    on_prediction_fragment=on_fragment,
                )
                if not marker_seen and pending:
                    events.put(("delta", pending))
                events.put(("result", _text(result)))
            except BaseException as exc:
                events.put(("error", exc))
            finally:
                events.put(("done", done))

        worker = threading.Thread(target=run, name="lmstudio-sdk-act", daemon=True)
        worker.start()
        emitted = False
        while True:
            kind, value = events.get()
            if kind == "delta":
                emitted = True
                yield SimpleNamespace(
                    choices=[SimpleNamespace(delta=SimpleNamespace(content=value))]
                )
            elif kind == "result":
                # Some SDK versions only report the completed text. Do not
                # duplicate it when prediction fragments were already emitted.
                if value and not emitted:
                    yield SimpleNamespace(
                        choices=[SimpleNamespace(delta=SimpleNamespace(content=value))]
                    )
            elif kind == "error":
                raise value
            elif kind == "done":
                break

    def _stream(self, prompt: str):
        for fragment in self._model.respond_stream(prompt):
            text = _fragment_text(fragment)
            if text:
                yield SimpleNamespace(
                    choices=[SimpleNamespace(delta=SimpleNamespace(content=text))]
                )


def make_client(core: Any) -> LMStudioSDKClient:
    getter: Callable[[str], Any] | None = getattr(core, "get_env", None)
    if callable(getter):
        model = getter("UAGENT_LMSTUDIO_DEPNAME") or "local-model"
    else:
        model = env_get("UAGENT_LMSTUDIO_DEPNAME", "local-model") or "local-model"
    client = LMStudioSDKClient(str(model))
    client._core = core
    return client
