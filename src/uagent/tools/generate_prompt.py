from __future__ import annotations

from datetime import datetime
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "generate_prompt",
        "description": "指定した単一ファイルを解析し、解析結果に基づいたプロンプトを生成して files/ 以下に一意のファイルとして保存します。",
        "system_prompt": """このツールは次の目的で使われます: 指定した単一ファイルを解析し、解析結果に基づいたプロンプトを生成して files/ 以下に一意のファイルとして保存します。""",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "解析対象のファイルパス（必須）",
                },
                "template": {
                    "type": "string",
                    "description": "（任意）プロンプトのテンプレート。プレースホルダ: {path},{lines},{size},{mtime},{excerpt},{timestamp} を使用できます。",
                },
            },
            "required": ["path"],
        },
    },
}


DEFAULT_TEMPLATE = (
    "次のファイルを解析し、問題点の指摘・改善案・および修正パッチを生成してください。\n"
    "対象ファイル: {path}\n"
    "ファイル概要: 行数={lines}、サイズ={size}バイト、最終更新={mtime}\n\n"
    "抜粋（冒頭最大20行）:\n{excerpt}\n\n"
    "出力要件:\n"
    "1) 現状の問題点を箇条書きで3点以内で示す。\n"
    "2) 改善案を2案示し、それぞれのトレードオフを簡潔に説明する。\n"
    "3) 実際にファイルを修正する場合の差分（patch/unified diff 形式）を生成する。\n\n"
    "このプロンプトは自動生成されました。生成時刻: {timestamp}\n"
)


SafeGeneratePrompt = Callable[[str, str | None], str]

# 安全ラッパーを利用して読み取り対象が危険な場合は確認する
safe_generate_prompt: Optional[SafeGeneratePrompt]
try:
    from .safe_file_ops import safe_generate_prompt as safe_generate_prompt
except Exception:
    safe_generate_prompt = None


def _derive_result_path(out_path: Path) -> Path:
    """生成プロンプトファイルから、既定の結果出力ファイルパスを決める。"""
    # files/prompt_YYYYmmddTHHMMSS.txt -> files/result_prompt_YYYYmmddTHHMMSS.txt
    stem = out_path.stem
    return out_path.with_name(f"result_{stem}.txt")


def run_tool(args: Dict[str, Any]) -> str:
    """prompt generator tool

    args:
      - path: 解析対象ファイルのパス（必須）
      - template: 任意のテンプレート文字列

    動作:
      - 指定ファイルの存在を確認し、メタ情報と冒頭の抜粋を取得
      - テンプレートに埋め込み、files/ に一意のファイル名で保存
      - 保存したプロンプトファイル名と、推奨の結果ファイル名を返す
    """

    path = (args.get("path") or "").strip()
    template = args.get("template") or DEFAULT_TEMPLATE

    if not path:
        return "[generate_prompt error] path が指定されていません"

    p = Path(path)
    if not p.exists() or not p.is_file():
        return f"[generate_prompt error] 指定ファイルが存在しません: {path}"

    # 可能なら safe wrapper を使う（読み取りでも確認する）
    try:
        if safe_generate_prompt is not None:
            out = safe_generate_prompt(path, template)
            out_path = Path(str(out))
            result_path = _derive_result_path(out_path)
            return (
                "[generate_prompt] プロンプトを作成しました:\n"
                f"  prompt_file: {out_path}\n"
                f"  result_file(suggested): {result_path}"
            )
    except PermissionError as e:
        return f"[generate_prompt error] PermissionError: {e}"
    except Exception:
        # fallthrough to builtin logic
        pass

    try:
        text = p.read_text(encoding="utf-8")
    except Exception:
        try:
            text = p.read_text(encoding="latin-1")
        except Exception as e:
            return f"[generate_prompt error] ファイル読み込みに失敗しました: {e}"

    lines = text.splitlines()
    excerpt = "\n".join(lines[:20])
    stat = p.stat()
    size = stat.st_size
    mtime = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(stat.st_mtime))
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")

    prompt_text = template.format(
        path=str(p),
        lines=len(lines),
        size=size,
        mtime=mtime,
        excerpt=excerpt,
        timestamp=timestamp,
    )

    from uagent.utils.paths import get_files_dir

    files_dir = get_files_dir()
    try:
        files_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return f"[generate_prompt error] files ディレクトリを作成できません: {e}"

    base_name = f"prompt_{timestamp}.txt"
    out_path = files_dir / base_name
    # 競合が起きたら連番を付与
    i = 1
    while out_path.exists():
        out_path = files_dir / f"prompt_{timestamp}_{i}.txt"
        i += 1

    try:
        out_path.write_text(prompt_text, encoding="utf-8")
    except Exception as e:
        return f"[generate_prompt error] ファイル書き込みに失敗しました: {e}"

    result_path = _derive_result_path(out_path)

    return (
        "[generate_prompt] プロンプトを作成しました:\n"
        f"  prompt_file: {out_path}\n"
        f"  result_file(suggested): {result_path}"
    )
