# tools/apply_patch_tool.py
"""apply_patch_tool

unified diff (git apply 互換) を安全に適用するツール。

改善点:
- 改行コードの差異による適用失敗を回避するため、オプションを拡充。
- パッチ一時ファイルの作成をより確実に行う。
"""

from __future__ import annotations
from .i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)


import json
import os
import re
import time
import uuid
import subprocess
import shlex
from typing import Any, Dict, List, Optional, Tuple

from .safe_file_ops_extras import is_path_dangerous

BUSY_LABEL = True
STATUS_LABEL = "tool:apply_patch"


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "apply_patch",
        "description": (
            "unified diff (git apply 互換) を適用します（最終手段）。通常の編集は replace_in_file を最優先してください。"
        ),
        "system_prompt": (
            "unified diff (git apply 互換) を適用するツールです（最終手段）。AIがこのツールを扱う際は以下を厳守してください：\n"
            "0. **原則禁止（通常編集は別ツール）**: ファイル修正は原則として `replace_in_file`（preview=trueで差分確認→preview=falseで適用）を最優先してください。\n"
            "1. **使用が許される条件**: 次の場合に限り `apply_patch` を使用できます。\n"
            "   - 人間が用意した正しい unified diff（git apply 互換）をそのまま適用する場合\n"
            "   - 変更が広範囲・複雑で `replace_in_file` だと誤爆リスクが高い場合（この場合でも、まず対象箇所を `read_file` で確認）\n"
            "2. **LLMがパッチ本文を生成して適用する運用は避ける**: パッチ生成は失敗率が高いため、原則として行わないでください。\n"
            "3. **正確なコンテキスト**: 適用前に必ず `read_file` で最新内容を確認し、空白・インデント・改行を一致させてください。\n"
            "4. **dry_run必須**: 常に `dry_run=true` で検証し、成功を確認してから `dry_run=false` を実行してください。\n"
            "5. **改行/空白の差異対策**: 失敗する場合は `ignore_whitespace=True` や `whitespace='fix'` を検討してください。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "patch_text": {"type": "string", "description": "unified diff 本文"},
                "dry_run": {
                    "type": "boolean",
                    "description": "true=適用可否チェックのみ / false=適用する",
                    "default": True,
                },
                "whitespace": {
                    "type": "string",
                    "enum": ["nowarn", "warn", "error", "fix"],
                    "description": "git apply の --whitespace オプション。改行コード不一致の修正には 'fix' が有効です。",
                    "default": "nowarn",
                },
                "ignore_whitespace": {
                    "type": "boolean",
                    "description": "改行コードや空白のみの差異を無視してパッチを適用します (--ignore-whitespace)。",
                    "default": False,
                },
                "strip": {
                    "type": "integer",
                    "description": "git apply の -pN 相当（パス先頭要素を剥ぐ数）。未指定なら 0。",
                    "default": 0,
                },
                "confirm": {
                    "type": "string",
                    "enum": ["auto", "always", "never"],
                    "description": "dry_run=false 時の human_ask 確認方針",
                    "default": "auto",
                },
                "confirm_if_files_over": {
                    "type": "integer",
                    "description": "dry_run=false で対象ファイル数がこの値を超えると確認（confirm=auto時）",
                    "default": 10,
                },
                "confirm_if_added_lines_over": {
                    "type": "integer",
                    "description": "dry_run=false で追加行数がこの値を超えると確認（confirm=auto時）",
                    "default": 500,
                },
                "confirm_if_deleted_lines_over": {
                    "type": "integer",
                    "description": "dry_run=false で削除行数がこの値を超えると確認（confirm=auto時）",
                    "default": 500,
                },
            },
            "required": ["patch_text"],
        },
    },
}


_DIFF_HEADER_RE = re.compile(r"^(---|\+\+\+)\s+(?P<path>\S+)")


def _extract_paths_from_patch(patch_text: str) -> List[str]:
    paths: List[str] = []
    for line in (patch_text or "").splitlines():
        m = _DIFF_HEADER_RE.match(line.strip())
        if not m:
            continue
        p = m.group("path")
        if not p:
            continue
        # strip leading a/ b/
        if p.startswith("a/") or p.startswith("b/"):
            p2 = p[2:]
        else:
            p2 = p
        if p2 == "/dev/null":
            continue
        if p2 not in paths:
            paths.append(p2)
    return paths


_NUMSTAT_RE = re.compile(r"^(?P<add>\d+|-)\s+(?P<del>\d+|-)\s+(?P<path>.+)$")


def _parse_numstat(text: str) -> Tuple[int, int, List[Dict[str, Any]]]:
    added_total = 0
    deleted_total = 0
    files: List[Dict[str, Any]] = []

    for line in (text or "").splitlines():
        line = line.strip("\r\n")
        if not line:
            continue
        m = _NUMSTAT_RE.match(line)
        if not m:
            continue
        a = m.group("add")
        d = m.group("del")
        p = m.group("path")

        add_i = int(a) if a.isdigit() else None
        del_i = int(d) if d.isdigit() else None

        if add_i is not None:
            added_total += add_i
        if del_i is not None:
            deleted_total += del_i

        files.append({"path": p, "added": add_i, "deleted": del_i})

    return added_total, deleted_total, files


def _human_confirm(message: str) -> bool:
    try:
        from .human_ask_tool import run_tool as human_ask

        res_json = human_ask({"message": message})
        res = json.loads(res_json)
        user_reply = (res.get("user_reply") or "").strip().lower()
        return user_reply in ("y", "yes")
    except Exception:
        return False


def _cmd_exec_json(
    command: str, cwd: Optional[str] = None
) -> Tuple[str, str, int, Optional[str]]:
    """Execute a command and return (stdout, stderr, returncode, error_tag).

    - When cwd is None, we prefer cmd_exec_json_tool (tool-managed execution).
    - When cwd is provided, we execute directly via subprocess with a safety guard
      (only allow git commands) so that git apply can be run from repo root.

    Note:
    - command is a string API kept for backward-compat.
    - For robust path handling (spaces etc.), prefer _cmd_exec_json_argv.
    """

    # Safety guard: if a custom cwd is requested, only allow git commands.
    if cwd is not None and not (
        command.lstrip().startswith("git ") or command.strip() == "git"
    ):
        return "", "", 1, "blocked: cwd execution is only allowed for git commands"

    # If caller requests cwd, run directly so cwd is honored.
    if cwd is not None:
        try:
            argv = shlex.split(command, posix=False)
            cp = subprocess.run(
                argv,
                shell=False,
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            return cp.stdout or "", cp.stderr or "", int(cp.returncode or 0), None
        except Exception as e:
            return (
                "",
                f"subprocess failed: {type(e).__name__}: {e}",
                1,
                "subprocess_failed",
            )

    # Default: tool-managed execution
    try:
        from .cmd_exec_json_tool import run_tool as cmd_exec_json

        out = cmd_exec_json({"command": command})
        obj = json.loads(out)
        if obj.get("blocked"):
            return "", "", 1, str(obj.get("reason") or "blocked")
        if obj.get("timeout"):
            return "", "", 124, str(obj.get("message") or "timeout")
        stdout = str(obj.get("stdout") or "")
        stderr = str(obj.get("stderr") or "")
        code = int(obj.get("returncode") or 0)
        return stdout, stderr, code, None
    except Exception as e:
        return (
            "",
            f"cmd_exec_json unavailable: {type(e).__name__}: {e}",
            1,
            "unavailable",
        )


def _cmd_exec_json_argv(
    argv: List[str], cwd: Optional[str] = None
) -> Tuple[str, str, int, Optional[str]]:
    """Execute argv and return (stdout, stderr, returncode, error_tag).

    - If cwd is provided: execute directly via subprocess.run(argv, shell=False).
    - If cwd is None: execute via cmd_exec_json_tool, converting argv to a command string
      with subprocess.list2cmdline on Windows, or shlex.join on non-Windows.

    This avoids space/quote issues that occur when building command strings manually.
    """

    if not argv:
        return "", "", 1, "invalid: empty argv"

    # Safety guard: if a custom cwd is requested, only allow git commands.
    if cwd is not None and argv[0] != "git":
        return "", "", 1, "blocked: cwd execution is only allowed for git commands"

    if cwd is not None:
        try:
            cp = subprocess.run(
                argv,
                shell=False,
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            return cp.stdout or "", cp.stderr or "", int(cp.returncode or 0), None
        except Exception as e:
            return (
                "",
                f"subprocess failed: {type(e).__name__}: {e}",
                1,
                "subprocess_failed",
            )

    # cwd is None -> tool-managed execution
    try:
        from .cmd_exec_json_tool import run_tool as cmd_exec_json

        if os.name == "nt":
            cmd = subprocess.list2cmdline(argv)
        else:
            # py3.8+: shlex.join
            cmd = shlex.join(argv)

        out = cmd_exec_json({"command": cmd})
        obj = json.loads(out)
        if obj.get("blocked"):
            return "", "", 1, str(obj.get("reason") or "blocked")
        if obj.get("timeout"):
            return "", "", 124, str(obj.get("message") or "timeout")
        stdout = str(obj.get("stdout") or "")
        stderr = str(obj.get("stderr") or "")
        code = int(obj.get("returncode") or 0)
        return stdout, stderr, code, None
    except Exception as e:
        return (
            "",
            f"cmd_exec_json unavailable: {type(e).__name__}: {e}",
            1,
            "unavailable",
        )


def run_tool(args: Dict[str, Any]) -> str:
    patch_text = str(args.get("patch_text") or "")
    dry_run = bool(args.get("dry_run", True))
    whitespace = str(args.get("whitespace") or "nowarn")
    ignore_whitespace = bool(args.get("ignore_whitespace", False))
    strip = int(args.get("strip", 0))
    confirm = str(args.get("confirm") or "auto")
    confirm_if_files_over = int(args.get("confirm_if_files_over", 10))
    confirm_if_added_lines_over = int(args.get("confirm_if_added_lines_over", 500))
    confirm_if_deleted_lines_over = int(args.get("confirm_if_deleted_lines_over", 500))

    if not patch_text.strip():
        return json.dumps(
            {"ok": False, "error": "patch_text is empty"}, ensure_ascii=False
        )

    # パッチテキストの改行を LF に正規化
    patch_text = patch_text.replace("\r\n", "\n").replace("\r", "\n")

    paths = _extract_paths_from_patch(patch_text)
    for p in paths:
        if is_path_dangerous(p) or ".." in p.replace("\\", "/").split("/"):
            return json.dumps(
                {
                    "ok": False,
                    "error": f"dangerous path in patch rejected: {p}",
                    "paths": paths,
                },
                ensure_ascii=False,
            )

    # Ensure git is available
    so, se, code, err_tag = _cmd_exec_json("git --version")
    if code != 0:
        return json.dumps(
            {
                "ok": False,
                "error": f"git not available: {se or so}",
                "error_tag": err_tag,
            },
            ensure_ascii=False,
        )

    # Ensure inside git repo
    so, se, code, err_tag = _cmd_exec_json("git rev-parse --is-inside-work-tree")
    if code != 0 or (so.strip().lower() != "true"):
        return json.dumps(
            {
                "ok": False,
                "error": "not inside a git work tree (git repo required)",
                "stderr": se,
                "error_tag": err_tag,
            },
            ensure_ascii=False,
        )

    from uagent.utils.paths import get_tmp_patch_dir

    tmp_dir = str(get_tmp_patch_dir())
    try:
        os.makedirs(tmp_dir, exist_ok=True)
    except Exception as e:
        return json.dumps(
            {"ok": False, "error": f"failed to create tmp dir: {e}"}, ensure_ascii=False
        )

    ts = time.strftime("%Y%m%d_%H%M%S")
    uniq = f"{time.time_ns()}_{uuid.uuid4().hex}"
    patch_path = os.path.abspath(
        os.path.join(tmp_dir, f"patch_{ts}_{uniq}.diff")
    ).replace("\\", "/")
    try:
        # 常に LF で書き出す
        with open(patch_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(patch_text)
    except Exception as e:
        return json.dumps(
            {"ok": False, "error": f"failed to write patch temp file: {e}"},
            ensure_ascii=False,
        )

    # p_opt = f" -p{strip}" if strip else ""
    # ws_opt = f" --whitespace={whitespace}" if whitespace else ""
    # iw_opt = " --ignore-whitespace" if ignore_whitespace else ""
    # common_opts = f"{p_opt}{ws_opt}{iw_opt}"

    # argv form for robust execution (avoid space/quote issues)
    common_argv: List[str] = []
    if strip:
        common_argv.append(f"-p{strip}")
    if whitespace:
        common_argv.append(f"--whitespace={whitespace}")
    if ignore_whitespace:
        common_argv.append("--ignore-whitespace")

    # Determine repo root and run git commands from there to keep paths stable
    rt_out, rt_err, rt_code, rt_tag = _cmd_exec_json("git rev-parse --show-toplevel")
    if rt_code != 0:
        return json.dumps(
            {
                "ok": False,
                "error": "failed to determine git repo root (git rev-parse --show-toplevel)",
                "stdout": rt_out,
                "stderr": rt_err,
                "error_tag": rt_tag,
            },
            ensure_ascii=False,
        )

    repo_root = (rt_out or "").strip().splitlines()[0]

    # Use absolute path (relpath can break on Windows when repo_root and patch_path are on different drives)
    patch_abs_path = patch_path
    # stats (best effort)
    ns_out, ns_err, ns_code, _ = _cmd_exec_json_argv(
        [
            "git",
            "apply",
            *common_argv,
            "--numstat",
            patch_abs_path,
        ],
        cwd=repo_root,
    )
    added_total, deleted_total, file_stats = (
        _parse_numstat(ns_out) if ns_code == 0 else (0, 0, [])
    )

    # dry-run check
    ck_out, ck_err, ck_code, ck_tag = _cmd_exec_json_argv(
        [
            "git",
            "apply",
            *common_argv,
            "--check",
            patch_abs_path,
        ],
        cwd=repo_root,
    )
    if ck_code != 0:
        note = ""
        if "whitespace error" in (ck_err or "").lower():
            note = " Hint: 改行コードや空白の差異が疑われます。ignore_whitespace=True や whitespace='fix' を試してください。"

        return json.dumps(
            {
                "ok": False,
                "dry_run": True,
                "error": f"patch cannot be applied (git apply --check failed).{note}",
                "stdout": ck_out,
                "stderr": ck_err,
                "error_tag": ck_tag,
                "paths": paths,
                "added_total": added_total,
                "deleted_total": deleted_total,
                "file_stats": file_stats,
                "patch_file": patch_path,
            },
            ensure_ascii=False,
        )

    if dry_run:
        return json.dumps(
            {
                "ok": True,
                "dry_run": True,
                "summary": f"Patch check successful for {len(paths)} file(s): {', '.join(paths)}",
                "paths": paths,
                "added_total": added_total,
                "deleted_total": deleted_total,
                "file_stats": file_stats,
                "patch_file": patch_path,
            },
            ensure_ascii=False,
        )

    # confirm if needed
    need_confirm = False
    reasons: List[str] = []

    if confirm == "always":
        need_confirm = True
        reasons.append("confirm=always")
    elif confirm == "auto":
        if len(paths) > confirm_if_files_over:
            need_confirm = True
            reasons.append(f"files({len(paths)}) > {confirm_if_files_over}")
        if added_total > confirm_if_added_lines_over:
            need_confirm = True
            reasons.append(
                f"added_total({added_total}) > {confirm_if_added_lines_over}"
            )
        if deleted_total > confirm_if_deleted_lines_over:
            need_confirm = True
            reasons.append(
                f"deleted_total({deleted_total}) > {confirm_if_deleted_lines_over}"
            )

    if need_confirm:
        msg = (
            "apply_patch は git apply によりファイルを変更します。\n"
            f"patch_file: {patch_path}\n"
            f"files: {len(paths)}\n"
            f"added_total: {added_total}\n"
            f"deleted_total: {deleted_total}\n"
            f"reasons: {', '.join(reasons)}\n\n"
            "実行してよければ y、キャンセルなら c を入力してください。"
        )
        if not _human_confirm(msg):
            return json.dumps(
                {
                    "ok": False,
                    "error": "cancelled by user",
                    "paths": paths,
                    "added_total": added_total,
                    "deleted_total": deleted_total,
                    "file_stats": file_stats,
                    "patch_file": patch_path,
                },
                ensure_ascii=False,
            )

    ap_out, ap_err, ap_code, ap_tag = _cmd_exec_json_argv(
        [
            "git",
            "apply",
            *common_argv,
            patch_abs_path,
        ],
        cwd=repo_root,
    )
    if ap_code != 0:
        return json.dumps(
            {
                "ok": False,
                "summary": f"Failed to apply patch to {len(paths)} file(s).",
                "files": [{"path": p, "result": "Failed"} for p in paths],
                "error": "git apply failed",
                "stdout": ap_out,
                "stderr": ap_err,
                "error_tag": ap_tag,
                "paths": paths,
                "added_total": added_total,
                "deleted_total": deleted_total,
                "file_stats": file_stats,
                "patch_file": patch_path,
            },
            ensure_ascii=False,
        )

    return json.dumps(
        {
            "ok": True,
            "dry_run": False,
            "summary": f"Successfully applied patch to {len(paths)} file(s): {', '.join(paths)}",
            "files": [{"path": p, "result": "Applied"} for p in paths],
            "stdout": ap_out,
            "stderr": ap_err,
            "error_tag": ap_tag,
            "paths": paths,
            "added_total": added_total,
            "deleted_total": deleted_total,
            "file_stats": file_stats,
            "patch_file": patch_path,
        },
        ensure_ascii=False,
    )
