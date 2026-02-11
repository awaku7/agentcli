"""prompt_get tool

./prompts 配下のプロンプトテンプレート集を検索・取得し、
必要に応じてプレースホルダへコンテキストを埋め込んだ完成プロンプトを返す。

設計方針
- 仕様は ./prompts/index.yaml をカタログとして扱う
- テンプレ本文は ./prompts/templates/*.md
- LLM 側の利便性優先で、返却は Markdown か JSON を選べる

注意
- 本ツールは「プロンプトを返す」ためのもので、LLMがテンプレを利用して業務成果物を直接生成する。
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "prompt_get",
        "description": (
            "プロフェッショナル用途のプロンプトテンプレートを ./prompts から取得し、"
            "context を埋め込んだ完成プロンプト（filled_prompt）を返します。"
            "とくにシステム開発、プログラム開発には強いです"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "ドメイン（例: system_dev）",
                },
                "task": {
                    "type": "string",
                    "description": "タスク（例: requirements, code_review など）",
                },
                "context": {
                    "type": "object",
                    "description": (
                        "テンプレの {{placeholder}} に埋め込む値。"
                        "{placeholder: value} の辞書。値は文字列推奨。"
                    ),
                },
                "id": {
                    "type": "string",
                    "description": "テンプレIDを直接指定する場合（domain/taskより優先）",
                },
                "language": {
                    "type": "string",
                    "description": "言語（将来拡張用）。現状は ja のみを想定",
                    "default": "ja",
                },
                "format": {
                    "type": "string",
                    "enum": ["markdown", "json"],
                    "description": "出力形式",
                    "default": "markdown",
                },
                "strict": {
                    "type": "boolean",
                    "description": "true の場合、未指定プレースホルダがあるとエラーにする",
                    "default": False,
                },
                "include_template": {
                    "type": "boolean",
                    "description": "true の場合、template本文も返す（通常は不要）",
                    "default": False,
                },
                "list_only": {
                    "type": "boolean",
                    "description": "true の場合、該当テンプレのメタ情報のみ一覧で返す",
                    "default": False,
                },
            },
            "required": [],
        },
    },
}


@dataclass
class PromptEntry:
    id: str
    domain: str
    task: str
    title: str
    file: str
    placeholders: List[str]


def _tool_root_dir() -> str:
    # SBCAgentCLI/tools/prompt_get_tool.py -> SBCAgentCLI
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _prompts_dir() -> str:
    return os.path.join(_tool_root_dir(), "prompts")


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _load_index_yaml(index_path: str) -> List[PromptEntry]:
    """YAMLを最小実装で読む。

    依存追加を避けるため PyYAML 不使用。
    index.yaml はこのツールが生成/想定する非常に限定的な形式（リスト+スカラー+配列）にする。
    """

    text = _read_text(index_path)
    lines = [ln.rstrip("\n") for ln in text.splitlines()]

    entries: List[Dict[str, Any]] = []
    cur: Optional[Dict[str, Any]] = None
    in_placeholders = False

    def commit() -> None:
        nonlocal cur
        if cur is not None:
            entries.append(cur)
        cur = None

    for ln in lines:
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue

        if ln.startswith("-") and re.match(r"^-\s+id:\s+", ln):
            # new item
            commit()
            cur = {"placeholders": []}
            in_placeholders = False
            m = re.match(r"^-\s+id:\s+(.*)$", ln)
            if m:
                cur["id"] = m.group(1).strip()
            continue

        if cur is None:
            # unexpected but ignore
            continue

        if ln.startswith("placeholders:"):
            in_placeholders = True
            if "placeholders" not in cur or cur["placeholders"] is None:
                cur["placeholders"] = []
            continue

        if in_placeholders and ln.startswith("-"):
            # placeholder item
            ph = ln.lstrip("-").strip()
            if ph:
                cur.setdefault("placeholders", []).append(ph)
            continue

        # key: value
        in_placeholders = False
        m = re.match(r"^([a-zA-Z0-9_]+):\s*(.*)$", ln)
        if m:
            key = m.group(1)
            val = m.group(2).strip()
            # remove optional quotes
            if (val.startswith('"') and val.endswith('"')) or (
                val.startswith("'") and val.endswith("'")
            ):
                val = val[1:-1]
            cur[key] = val

    commit()

    out: List[PromptEntry] = []
    for e in entries:
        try:
            out.append(
                PromptEntry(
                    id=str(e.get("id", "")).strip(),
                    domain=str(e.get("domain", "")).strip(),
                    task=str(e.get("task", "")).strip(),
                    title=str(e.get("title", "")).strip(),
                    file=str(e.get("file", "")).strip(),
                    placeholders=list(e.get("placeholders", []) or []),
                )
            )
        except Exception:
            continue

    # filter invalid
    out = [x for x in out if x.id and x.domain and x.task and x.file]
    return out


_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_\-]+)\s*\}\}")


def _fill_template(
    template: str, context: Dict[str, Any], strict: bool
) -> Tuple[str, List[str]]:
    missing: List[str] = []

    def repl(m: re.Match) -> str:
        key = m.group(1)
        if key in context and context[key] is not None:
            return str(context[key])
        missing.append(key)
        return "" if not strict else m.group(0)

    filled = _PLACEHOLDER_RE.sub(repl, template)

    # strictなら、missingがあればエラーにする（置換は元のまま残る）
    if strict and missing:
        raise ValueError(f"missing placeholders: {sorted(set(missing))}")

    return filled, sorted(set(missing))


def _match_entries(
    entries: List[PromptEntry],
    template_id: Optional[str],
    domain: Optional[str],
    task: Optional[str],
) -> List[PromptEntry]:
    if template_id:
        return [e for e in entries if e.id == template_id]
    res = entries
    if domain:
        res = [e for e in res if e.domain == domain]
    if task:
        res = [e for e in res if e.task == task]
    return res


def run_tool(args: Dict[str, Any]) -> str:
    """tool runner"""

    domain = args.get("domain")
    task = args.get("task")
    template_id = args.get("id")
    context = args.get("context") or {}

    out_format = (args.get("format") or "markdown").lower()
    strict = bool(args.get("strict", False))
    include_template = bool(args.get("include_template", False))
    list_only = bool(args.get("list_only", False))

    pdir = _prompts_dir()
    index_path = os.path.join(pdir, "index.yaml")
    if not os.path.exists(index_path):
        return f"[tool error] prompts index not found: {index_path}"

    entries = _load_index_yaml(index_path)
    matched = _match_entries(entries, template_id, domain, task)

    tool_root_dir = _tool_root_dir()

    if list_only:
        payload = [
            {
                "id": e.id,
                "domain": e.domain,
                "task": e.task,
                "title": e.title,
                "file": e.file,
                "placeholders": e.placeholders,
                "tool_root_dir": tool_root_dir,
                "prompts_dir": pdir,
                "index_path": index_path,
            }
            for e in matched
        ]
        if out_format == "json":
            return json.dumps({"matches": payload}, ensure_ascii=False, indent=2)
        # markdown
        if not payload:
            return "該当テンプレートがありません。"
        lines = ["## テンプレ一覧", ""]
        for p in payload:
            lines.append(f"- **{p['id']}** ({p['domain']}/{p['task']}): {p['title']}")
        return "\n".join(lines)

    if not matched:
        return "[tool error] template not found. specify {id} or {domain, task}."

    # domain+task が曖昧な場合は先頭
    e = matched[0]
    template_path = os.path.join(pdir, e.file.replace("/", os.sep))
    if not os.path.exists(template_path):
        return f"[tool error] template file not found: {template_path}"

    template_text = _read_text(template_path)

    # filled mode
    try:
        filled, missing = _fill_template(template_text, context, strict=strict)
    except Exception as ex:
        return f"[tool error] {ex}"

    result: Dict[str, Any] = {
        "id": e.id,
        "domain": e.domain,
        "task": e.task,
        "title": e.title,
        "placeholders": e.placeholders,
        "missing_placeholders": missing,
        "filled_prompt": filled,
        # 追加: ファイル参照をしたいLLM向けに絶対パス情報を返す
        "tool_root_dir": tool_root_dir,
        "prompts_dir": pdir,
        "index_path": index_path,
        "template_path": template_path,
    }
    if include_template:
        result["template"] = template_text

    if out_format == "json":
        return json.dumps(result, ensure_ascii=False, indent=2)

    # markdown
    md: List[str] = []
    md.append(f"## {e.title}")
    md.append("")
    md.append(f"- id: `{e.id}`")
    md.append(f"- domain/task: `{e.domain}` / `{e.task}`")
    if missing:
        md.append(f"- missing_placeholders: {', '.join(missing)}")
    else:
        md.append("- missing_placeholders: (none)")
    md.append("")
    md.append("---")
    md.append("")
    md.append(filled)
    return "\n".join(md)
