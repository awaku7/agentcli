# tools/replace_in_file_tool.py
"""replace_in_file_tool

既存ファイルの一部を安全に置換するツール。
改行コードを自動的に正規化・復元することで、OS間の不整合を防止します。

- preview=true の場合は、置換候補（行番号・前後コンテキスト）を返すだけでファイルは変更しない。
- preview=false の場合は、バックアップ(.org/.orgN)を作成してから変更を書き込む。

Safety note:
- 本ツールの API では、pattern/replacement に改行を含めたい場合、原則として "\\n" を用いる。
  生の改行（\n / \r）が混入したまま preview=false で適用すると、Python 等の文字列リテラルを
  壊す事故につながるため、書き込み時は human_ask で確認する。
"""

from __future__ import annotations

import difflib
import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from .safe_file_ops_extras import (
    ensure_within_workdir,
    is_path_dangerous,
    make_backup_before_overwrite,
)

BUSY_LABEL = True
STATUS_LABEL = "tool:replace_in_file"


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "replace_in_file",
        "description": (
            "テキストファイルに対して、文字列置換または正規表現置換を行います。\n"
            "内部で改行コードを正規化するため、改行を含む検索・置換も扱えます。\n"
            "\n"
            "重要（必読）:\n"
            "- まず preview=true でヒット箇所を確認し、問題なければ preview=false で適用してください。\n"
            "- pattern/replacement に『生の改行（実改行文字）』を入れると、Python 等のソースコードを壊す事故につながります。\n"
            "  改行は必ず \\n として表現してください（JSONでは \\\n）。\n"
            "- mode=regex の pattern は Python の re 正規表現です（単なる文字列検索ではありません）。\n"
            "  例: \\x は不正です。\\xNN（例: \\x00, \\x1b）の形で指定してください。\n"
            "- バックスラッシュを文字として検索したいだけなら mode=literal を優先してください。\n"
        ),
        "system_prompt": (
            "テキストファイルに対して、文字列置換または正規表現置換を行います。\n"
            "\n"
            "手順（推奨）:\n"
            "1) read_file で対象箇所を確認\n"
            "2) replace_in_file を preview=true で実行し、ヒット箇所と差分プレビューを確認\n"
            "3) 狙い通りなら preview=false で適用（バックアップ .org/.orgN が作成される）\n"
            "4) .py を編集した場合は python -m py_compile で構文チェック\n"
            "\n"
            "改行の指定（最重要）:\n"
            "- pattern/replacement に『生の改行（実改行文字）』を入れないこと。\n"
            "  - OK: aaa\\nbbb（JSONでは aaa\\\\nbbb）\n"
            "  - NG: aaa<改行>bbb（混入すると Python の文字列リテラルが壊れて SyntaxError になり得る）\n"
            "\n"
            "mode=regex の注意:\n"
            "- pattern は Python の正規表現(re)として解釈される（単なる文字列検索ではない）\n"
            "- \\x は不正（re.error）。\\xNN（例: \\x00）の形式で書く\n"
            "- バックスラッシュを文字として検索したいだけなら mode=literal を優先する\n"
            "\n"
            "Windows パス例の注意（.py 編集時に特に重要）:\n"
            "- Python の \"...\" 文字列に C:\\path のようなバックスラッシュを含める場合は \\ を \\ にエスケープする（例: C:\\\\path）\n"
            "\n"
            "safety:\n"
            "- preview=false で危険パス/大量マッチ等の条件に該当する場合、確認や自動キャンセルが入ることがある\n"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "対象ファイルのパス（workdir配下推奨）。",
                },
                "mode": {
                    "type": "string",
                    "enum": ["literal", "regex"],
                    "description": "置換モード: literal=単純置換 / regex=正規表現置換",
                    "default": "literal",
                },
                "pattern": {
                    "type": "string",
                    "description": "検索パターン。改行は \\n として記述してください。",
                },
                "replacement": {
                    "type": "string",
                    "description": "置換後文字列。",
                },
                "count": {
                    "type": ["integer", "null"],
                    "description": "置換回数上限。null の場合は全置換。",
                    "default": None,
                },
                "preview": {
                    "type": "boolean",
                    "description": "true の場合は置換プレビューのみ返し、ファイルは変更しない。",
                    "default": True,
                },
                "context_lines": {
                    "type": "integer",
                    "description": "プレビューで表示する前後行数。",
                    "default": 2,
                },
                "confirm_if_matches_over": {
                    "type": "integer",
                    "description": "preview=false の実適用時、マッチ件数がこの値以上の場合は human_ask で確認する。",
                    "default": 10,
                },
                "encoding": {
                    "type": "string",
                    "description": "ファイルのエンコーディング（省略時 utf-8）。",
                    "default": "utf-8",
                },
                "raw_newline_policy": {
                    "type": "string",
                    "enum": ["allow", "reject"],
                    "description": "pattern/replacement に生改行(\n/\r)が含まれる場合の扱い。allow=許可 / reject=自動キャンセル（human_askなし）",
                    "default": "allow",
                },
                "regex_replacement_backslash_policy": {
                    "type": "string",
                    "enum": ["allow", "reject"],
                    "description": "mode=regex の replacement にバックスラッシュ(\\)が含まれる場合の扱い。allow=許可 / reject=自動キャンセル（human_askなし）",
                    "default": "allow",
                },
                "strict_for_py": {
                    "type": "boolean",
                    "description": "対象ファイルが .py のときだけ安全ルールを強制する（raw_newline_policy/replacement_backslash_policy を reject として扱う）。",
                    "default": False,
                },
            },
            "required": ["path", "pattern", "replacement"],
        },
    },
}


@dataclass
class PreviewHit:
    line_no: int
    before_lines: List[str]
    line_before: str
    line_after: str
    after_lines: List[str]


def _read_text_robust(path: str, encoding: str, max_bytes: int) -> Tuple[str, Any, str]:
    """ファイルを読み込み、(コンテンツ, 検出された改行コード, 実際に使ったエンコーディング) を返す。"""

    size = os.path.getsize(path)
    if size > max_bytes:
        raise ValueError(f"file too large: {size} > {max_bytes} bytes")

    def try_read(enc: str, errors: str) -> Tuple[str, Any, str]:
        with open(path, "r", encoding=enc, errors=errors, newline=None) as f:
            content = f.read()
            return content, f.newlines, enc

    try:
        return try_read(encoding, "strict")
    except (UnicodeDecodeError, LookupError):
        return try_read("utf-8", "replace")


def _unified_diff(path: str, original: str, replaced: str) -> str:
    """Return unified diff string ("" if no changes)."""

    if original == replaced:
        return ""

    a = original.splitlines(True)
    b = replaced.splitlines(True)
    diff = difflib.unified_diff(a, b, fromfile=f"a/{path}", tofile=f"b/{path}")
    return "".join(diff)


def _write_text_robust(path: str, text: str, encoding: str, newline: Any) -> None:
    """元の改行コードを尊重してファイルを書き出す。"""

    # メモリ上の改行コードを一度 \n に統一（混在防止）
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # detected_newline がタプル（混在）の場合は \r\n を優先的に採用
    if isinstance(newline, tuple):
        target_newline = "\r\n" if "\r\n" in newline else newline[0]
    else:
        target_newline = newline or "\n"

    with open(path, "w", encoding=encoding, newline=target_newline) as f:
        f.write(text)


def _build_preview(
    original: str, replaced: str, context_lines: int, max_hits: int = 100
) -> List[PreviewHit]:
    """difflib を使って変更箇所（PreviewHit）のリストを生成する。"""

    orig_lines_raw = original.splitlines(keepends=True)
    new_lines_raw = replaced.splitlines(keepends=True)

    # For matching: normalize line-endings by stripping trailing \r?\n.
    orig_lines = [ln.rstrip("\r\n") for ln in orig_lines_raw]
    new_lines = [ln.rstrip("\r\n") for ln in new_lines_raw]

    matcher = difflib.SequenceMatcher(None, orig_lines, new_lines)
    hits: List[PreviewHit] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue

        # 変更箇所の開始行（1-based）
        line_no = i1 + 1

        start = max(0, i1 - context_lines)
        end = min(len(orig_lines), i2 + context_lines)

        before = orig_lines[start:i1]
        after = orig_lines[i2:end]

        # 変更前後の内容（複数行の場合は連結）
        line_before = "\n".join(orig_lines[i1:i2])
        line_after = "\n".join(new_lines[j1:j2])

        if len(hits) < max_hits:
            hits.append(
                PreviewHit(
                    line_no=line_no,
                    before_lines=before,
                    line_before=line_before,
                    line_after=line_after,
                    after_lines=after,
                )
            )

    return hits


def _human_confirm(message: str) -> bool:
    try:
        from .human_ask_tool import run_tool as human_ask

        res_json = human_ask({"message": message})
        res = json.loads(res_json)
        user_reply = (res.get("user_reply") or "").strip().lower()
        return user_reply in ("y", "yes")
    except Exception:
        return False


def run_tool(args: Dict[str, Any]) -> str:
    from .context import get_callbacks

    cb = get_callbacks()

    # Safety: prevent accidental raw-newline injections.
    def _has_raw_newline(s: str) -> bool:
        return ("\n" in s) or ("\r" in s)

    def _escape_for_tool_arg(s: str) -> str:
        s = s.replace("\r\n", "\n").replace("\r", "\n")
        return s.replace("\n", r"\\n")

    max_bytes = (
        getattr(cb, "read_file_max_bytes", 1_000_000) if cb is not None else 1_000_000
    )

    def _validate_re_sub_replacement(repl: str) -> str | None:
        try:
            re.compile("").sub(repl, "")
            return None
        except re.error as e:
            return str(e)

    path = str(args.get("path") or "")
    mode = str(args.get("mode") or "literal")
    pattern_raw = args.get("pattern", None)
    pattern = "" if pattern_raw is None else str(pattern_raw)
    replacement_raw = args.get("replacement", None)
    replacement = "" if replacement_raw is None else str(replacement_raw)

    count = args.get("count", None)
    count_int: int | None = None
    if count is not None:
        try:
            count_int = int(count)
        except Exception:
            return json.dumps(
                {"ok": False, "error": f"count must be int or null: {count!r}"},
                ensure_ascii=False,
            )
        if count_int < 0:
            return json.dumps(
                {"ok": False, "error": f"count must be >= 0 or null: {count_int}"},
                ensure_ascii=False,
            )

    preview = bool(args.get("preview", True))

    raw_newline_policy = str(args.get("raw_newline_policy") or "allow").strip().lower()
    regex_repl_bs_policy = str(
        args.get("regex_replacement_backslash_policy") or "allow"
    ).strip().lower()
    strict_for_py = bool(args.get("strict_for_py", False))

    if raw_newline_policy not in ("allow", "reject"):
        return json.dumps(
            {"ok": False, "error": f"invalid raw_newline_policy: {raw_newline_policy!r}"},
            ensure_ascii=False,
        )
    if regex_repl_bs_policy not in ("allow", "reject"):
        return json.dumps(
            {
                "ok": False,
                "error": f"invalid regex_replacement_backslash_policy: {regex_repl_bs_policy!r}",
            },
            ensure_ascii=False,
        )

    ext = os.path.splitext(path)[1].lower() if path else ""

    # .py は生改行混入で構文破壊を起こし得るため、常に reject する
    if ext == ".py":
        raw_newline_policy = "reject"

    # strict_for_py が有効なら追加で regex replacement のバックスラッシュも reject
    if strict_for_py and ext == ".py":
        regex_repl_bs_policy = "reject"

    if raw_newline_policy == "reject" and (
        _has_raw_newline(pattern) or _has_raw_newline(replacement)
    ):
        return json.dumps(
            {
                "ok": False,
                "error": (
                    "REJECT_RAW_NEWLINE: pattern/replacement contains a raw newline (\\n/\\r). "
                    "Do not send literal newlines. Encode them as \\\"\\n\\\" in the JSON string "
                    "(i.e. write \\n as \\\\n), or use python_exec to edit the file safely."
                ),
                "suggested_args": {
                    **args,
                    "pattern": _escape_for_tool_arg(pattern),
                    "replacement": _escape_for_tool_arg(replacement),
                    "raw_newline_policy": "allow",
                },
                "suggested_call": "Call replace_in_file again with suggested_args (pattern/replacement use \\n escapes).",
            },
            ensure_ascii=False,
        )

    if mode == "regex" and regex_repl_bs_policy == "reject" and ("\\" in replacement):
        _allowed = bool(
            re.fullmatch(r"(?:[^\\]|\\[1-9]|\\g<[^>]+>)*\Z", replacement)
        )
        if not _allowed:
            return json.dumps(
                {
                    "ok": False,
                    "error": (
                        "REJECT_REGEX_REPLACEMENT_BACKSLASH: mode=regex replacement contains backslash (\\). "
                        "Only group references are allowed when regex_replacement_backslash_policy=reject: "
                        "\\1-\\9 and \\g<...>. Other escapes like \\w/\\s/\\n are rejected. "
                        "If you need them, set regex_replacement_backslash_policy=allow or use python_exec."
                    ),
                    "suggested_args": {**args, "regex_replacement_backslash_policy": "allow"},
                    "suggested_call": "If you really intend backslash escapes beyond group refs, re-run with suggested_args.",
                },
                ensure_ascii=False,
            )

    context_lines = int(args.get("context_lines", 2))
    confirm_if_matches_over = int(args.get("confirm_if_matches_over", 10))
    encoding = str(args.get("encoding") or "utf-8")

    if pattern == "":
        return json.dumps({"ok": False, "error": "pattern must be non-empty"}, ensure_ascii=False)

    if not path:
        return json.dumps({"ok": False, "error": "path is required"}, ensure_ascii=False)

    if is_path_dangerous(path):
        return json.dumps(
            {"ok": False, "error": f"dangerous path rejected: {path}"},
            ensure_ascii=False,
        )

    try:
        safe_path = ensure_within_workdir(path)
    except Exception as e:
        return json.dumps({"ok": False, "error": f"path not allowed: {e}"}, ensure_ascii=False)

    if not os.path.exists(safe_path) or not os.path.isfile(safe_path):
        return json.dumps({"ok": False, "error": f"file not found: {safe_path}"}, ensure_ascii=False)

    if BUSY_LABEL:
        try:
            if cb is not None and getattr(cb, "set_status", None):
                cb.set_status(True, STATUS_LABEL)
        except Exception:
            pass

    try:
        original, detected_newline, detected_encoding = _read_text_robust(
            safe_path, encoding=encoding, max_bytes=max_bytes
        )

        if mode not in ("literal", "regex"):
            return json.dumps(
                {"ok": False, "error": f"mode must be literal|regex: {mode!r}"},
                ensure_ascii=False,
            )

        replaced = original
        match_count = 0

        if mode == "literal":
            match_count = original.count(pattern)
            replaced = (
                original.replace(pattern, replacement)
                if count_int is None
                else original.replace(pattern, replacement, count_int)
            )

        else:
            try:
                cre = re.compile(pattern)
            except re.error as e:
                return json.dumps(
                    {"ok": False, "error": f"invalid regex pattern: {e}"},
                    ensure_ascii=False,
                )

            _repl_err = _validate_re_sub_replacement(replacement)
            if _repl_err is not None:
                return json.dumps(
                    {
                        "ok": False,
                        "error": f"invalid regex replacement template: {_repl_err}",
                        "suggested_args": {**args, "mode": "literal"},
                        "suggested_call": "Python re.sub rejected the replacement template. Consider mode=literal, or escape backslashes properly.",
                    },
                    ensure_ascii=False,
                )

            if count_int is None:
                replaced, match_count = cre.subn(replacement, original)
            else:
                replaced, match_count = cre.subn(replacement, original, count=count_int)

        changed = replaced != original

        if preview:
            hits = _build_preview(original, replaced, context_lines=context_lines)
            return json.dumps(
                {
                    "ok": True,
                    "path": safe_path,
                    "mode": mode,
                    "match_count": match_count,
                    "changed": changed,
                    "preview": True,
                    "diff": _unified_diff(safe_path, original, replaced),
                    "summary": f"Preview: {match_count} matches found",
                    "hits": [h.__dict__ for h in hits],
                    "detected_newline": detected_newline,
                    "encoding": detected_encoding,
                },
                ensure_ascii=False,
            )

        if match_count >= confirm_if_matches_over:
            ok = _human_confirm(
                f"{safe_path} に {match_count} 件マッチしました。\n適用しますか？ (y/N)"
            )
            if not ok:
                return json.dumps({"ok": False, "error": "cancelled by user"}, ensure_ascii=False)

        backup = make_backup_before_overwrite(safe_path)
        _write_text_robust(
            safe_path,
            replaced,
            encoding=detected_encoding,
            newline=detected_newline,
        )

        diff = _unified_diff(safe_path, original, replaced)

        summary = (
            "Successfully no change (0 matches)"
            if match_count == 0
            else f"Applied: {match_count} matches"
        )

        return json.dumps(
            {
                "ok": True,
                "path": safe_path,
                "mode": mode,
                "match_count": match_count,
                "changed": changed,
                "preview": False,
                "summary": summary,
                "diff": diff,
                "backup": backup,
                "written": True,
                "new_size": os.path.getsize(safe_path),
                "detected_newline": detected_newline,
                "encoding": detected_encoding,
            },
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps(
            {
                "ok": False,
                "error": f"{type(e).__name__}: {e}",
                "diff": "",
                "summary": "Error",
            },
            ensure_ascii=False,
        )

    finally:
        if BUSY_LABEL:
            try:
                if cb is not None and getattr(cb, "set_status", None):
                    cb.set_status(False, "IDLE")
            except Exception:
                pass
