#!/usr/bin/env python3
"""Probe Foundry Local Chat Completions tool calling without importing UAG.

This diagnostic talks directly to the configured OpenAI-compatible Foundry
Local endpoint and runs three independent cases:

1. ``simple-auto``: one trivial ``get_weather`` function with tool_choice=auto.
2. ``catalog-auto``: a UAG-shaped ``tool_catalog`` function with tool_choice=auto.
3. ``catalog-forced``: the same ``tool_catalog`` function forced by tool_choice.

Interpretation:
- simple-auto FAIL: model/runtime/Foundry tool calling is not working reliably.
- simple-auto PASS, catalog-auto FAIL, catalog-forced PASS: automatic selection of
  the catalog tool is the likely problem (prompt/model behavior).
- simple-auto PASS, catalog-forced FAIL: the catalog schema or server-side tool
  handling needs investigation before changing UAG's discovery flow.

Configuration is read from the normal Foundry Local UAG environment variables,
but this file deliberately does not import any ``uagent`` module.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import sys
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen


ENV_BASE_URL = "UAGENT_FOUNDRY_LOCAL_BASE_URL"
ENV_MODEL = "UAGENT_FOUNDRY_LOCAL_DEPNAME"
ENV_API_KEY = "UAGENT_FOUNDRY_LOCAL_API_KEY"


@dataclass(frozen=True)
class ProbeCase:
    name: str
    prompt: str
    tools: list[dict[str, Any]]
    tool_choice: Any
    expected_tool: str


@dataclass(frozen=True)
class ProbeResult:
    case: ProbeCase
    status_code: int
    finish_reason: str
    assistant_text: str
    tool_calls: list[dict[str, Any]]
    raw: dict[str, Any]

    @property
    def called_names(self) -> list[str]:
        names: list[str] = []
        for call in self.tool_calls:
            function = call.get("function") if isinstance(call, dict) else None
            if not isinstance(function, dict):
                continue
            name = function.get("name")
            if isinstance(name, str) and name:
                names.append(name)
        return names

    @property
    def passed(self) -> bool:
        return self.case.expected_tool in self.called_names


def _simple_weather_tool() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name, for example Osaka.",
                    }
                },
                "required": ["city"],
            },
        },
    }


def _uag_catalog_tool() -> dict[str, Any]:
    """Return a standalone copy of UAG's tool_catalog function schema.

    UAG-only registration metadata is intentionally omitted: this probe is for
    the OpenAI-compatible wire contract, so only fields that belong in a
    Chat Completions ``tools`` item are sent.
    """

    return {
        "type": "function",
        "function": {
            "name": "tool_catalog",
            "description": (
                "Return a JSON catalog of available tools with ok, query, count, "
                "and tools fields so the model can discover relevant tools before "
                "requesting full tool definitions. Results include a 'loaded' field "
                "indicating if the tool is currently enabled. When a 'query' is "
                "provided, the top-ranked unloaded tool is automatically loaded "
                "(indicated by 'auto_loaded' in the response)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Natural-language query describing the needed capability. "
                            "Ignored when all=true."
                        ),
                    },
                    "all": {
                        "type": "boolean",
                        "description": (
                            "If true, return all available tools (loaded + unloaded) "
                            "without query filtering."
                        ),
                        "default": False,
                    },
                },
            },
        },
    }


def _cases() -> dict[str, ProbeCase]:
    catalog = _uag_catalog_tool()
    return {
        "simple-auto": ProbeCase(
            name="simple-auto",
            prompt=(
                "大阪の現在の天気を取得してください。推測や手順説明ではなく、"
                "必要な get_weather ツールを呼び出してください。"
            ),
            tools=[_simple_weather_tool()],
            tool_choice="auto",
            expected_tool="get_weather",
        ),
        "catalog-auto": ProbeCase(
            name="catalog-auto",
            prompt=(
                "今日の天気を調べたいです。利用可能な実行ツールを推測せず、"
                "まず tool_catalog を呼び出して天気取得能力を検索してください。"
            ),
            tools=[catalog],
            tool_choice="auto",
            expected_tool="tool_catalog",
        ),
        "catalog-forced": ProbeCase(
            name="catalog-forced",
            prompt="今日の天気を調べるために利用可能なツールを検索してください。",
            tools=[catalog],
            tool_choice={
                "type": "function",
                "function": {"name": "tool_catalog"},
            },
            expected_tool="tool_catalog",
        ),
    }


def _chat_completions_url(base_url: str) -> str:
    raw = (base_url or "").strip()
    if not raw:
        raise ValueError(f"--base-url or {ENV_BASE_URL} is required")
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"invalid Foundry Local base URL: {raw!r}")

    hostname = parsed.hostname
    is_loopback = hostname.lower() == "localhost"
    if not is_loopback:
        try:
            is_loopback = ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            is_loopback = False
    if not is_loopback:
        raise ValueError(
            "Foundry Local probe only accepts loopback endpoints "
            f"(got host {hostname!r})"
        )

    path = parsed.path.rstrip("/")
    if path.endswith("/chat/completions"):
        endpoint_path = path
    else:
        endpoint_path = path + "/chat/completions"
    return urlunsplit((parsed.scheme, parsed.netloc, endpoint_path, "", ""))


def _post_json(
    url: str,
    payload: dict[str, Any],
    *,
    api_key: str,
    timeout: float,
) -> tuple[int, dict[str, Any]]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = Request(url, data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            status = int(getattr(response, "status", 200))
            raw = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {raw}") from exc
    except URLError as exc:
        raise RuntimeError(f"connection failed: {exc}") from exc

    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"non-JSON response (HTTP {status}): {raw!r}") from exc
    if not isinstance(decoded, dict):
        raise RuntimeError(f"unexpected JSON response type: {type(decoded).__name__}")
    return status, decoded


def _parse_result(case: ProbeCase, status: int, raw: dict[str, Any]) -> ProbeResult:
    choices = raw.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise RuntimeError(f"response has no choices[0]: {json.dumps(raw, ensure_ascii=False)}")
    choice = choices[0]
    message = choice.get("message")
    if not isinstance(message, dict):
        message = {}
    content = message.get("content")
    assistant_text = content if isinstance(content, str) else ""
    calls = message.get("tool_calls")
    tool_calls = [item for item in calls if isinstance(item, dict)] if isinstance(calls, list) else []
    return ProbeResult(
        case=case,
        status_code=status,
        finish_reason=str(choice.get("finish_reason") or ""),
        assistant_text=assistant_text,
        tool_calls=tool_calls,
        raw=raw,
    )


def _run_case(
    case: ProbeCase,
    *,
    url: str,
    model: str,
    api_key: str,
    timeout: float,
    temperature: float,
) -> ProbeResult:
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are testing native OpenAI-compatible function calling. "
                    "When the requested action matches an available function, emit "
                    "a native tool call instead of describing a hypothetical call."
                ),
            },
            {"role": "user", "content": case.prompt},
        ],
        "tools": case.tools,
        "tool_choice": case.tool_choice,
        "temperature": temperature,
        "stream": False,
    }
    status, raw = _post_json(url, payload, api_key=api_key, timeout=timeout)
    return _parse_result(case, status, raw)


def _print_result(result: ProbeResult, *, show_json: bool) -> None:
    verdict = "PASS" if result.passed else "FAIL"
    print(f"\n=== {result.case.name}: {verdict} ===")
    print(f"HTTP: {result.status_code}")
    print(f"finish_reason: {result.finish_reason or '(empty)'}")
    print(f"expected_tool: {result.case.expected_tool}")
    print(f"called_tools: {result.called_names or []}")
    if result.tool_calls:
        for index, call in enumerate(result.tool_calls, start=1):
            function = call.get("function") if isinstance(call, dict) else None
            if not isinstance(function, dict):
                continue
            print(f"tool_call[{index}].name: {function.get('name')!r}")
            print(f"tool_call[{index}].arguments: {function.get('arguments')!r}")
    if result.assistant_text:
        print(f"assistant_text: {result.assistant_text!r}")
    if show_json:
        print("raw_response:")
        print(json.dumps(result.raw, ensure_ascii=False, indent=2))


def _print_interpretation(results: list[ProbeResult]) -> None:
    by_name = {item.case.name: item for item in results}
    simple = by_name.get("simple-auto")
    catalog_auto = by_name.get("catalog-auto")
    catalog_forced = by_name.get("catalog-forced")
    if not (simple and catalog_auto and catalog_forced):
        return

    print("\n=== interpretation ===")
    if not simple.passed:
        print(
            "simple-auto failed: investigate the model / Foundry Local runtime / "
            "OpenAI-compatible tool-calling path before changing UAG discovery."
        )
    elif not catalog_forced.passed:
        print(
            "simple-auto passed but catalog-forced failed: investigate the "
            "tool_catalog schema or Foundry Local handling of that schema."
        )
    elif not catalog_auto.passed:
        print(
            "forced catalog call works but catalog-auto failed: native tool calling "
            "works; automatic tool selection/prompt behavior is the likely issue."
        )
    else:
        print(
            "all direct probes passed: Foundry Local can call these tools outside "
            "UAG, so compare UAG's actual messages/tools payload next."
        )


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Direct Foundry Local Chat Completions tool-calling probe."
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get(ENV_BASE_URL, ""),
        help=f"Foundry Local /v1 base URL (default: ${ENV_BASE_URL})",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get(ENV_MODEL, ""),
        help=f"Model id (default: ${ENV_MODEL})",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get(ENV_API_KEY, ""),
        help=f"Optional bearer token (default: ${ENV_API_KEY})",
    )
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument(
        "--case",
        choices=("all", "simple-auto", "catalog-auto", "catalog-forced"),
        default="all",
    )
    parser.add_argument(
        "--show-json",
        action="store_true",
        help="Print complete JSON responses after each case.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        url = _chat_completions_url(args.base_url)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    model = str(args.model or "").strip()
    if not model:
        print(f"ERROR: --model or {ENV_MODEL} is required", file=sys.stderr)
        return 2

    selected = _cases()
    cases = list(selected.values()) if args.case == "all" else [selected[args.case]]
    print(f"endpoint: {url}")
    print(f"model: {model}")
    print(f"cases: {', '.join(case.name for case in cases)}")

    results: list[ProbeResult] = []
    for case in cases:
        try:
            result = _run_case(
                case,
                url=url,
                model=model,
                api_key=str(args.api_key or ""),
                timeout=max(1.0, float(args.timeout)),
                temperature=float(args.temperature),
            )
        except Exception as exc:
            print(f"\n=== {case.name}: ERROR ===", file=sys.stderr)
            print(str(exc), file=sys.stderr)
            return 2
        results.append(result)
        _print_result(result, show_json=bool(args.show_json))

    _print_interpretation(results)
    failures = [result.case.name for result in results if not result.passed]
    if failures:
        print(f"\nFAILED CASES: {', '.join(failures)}")
        return 1
    print("\nALL SELECTED CASES PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
