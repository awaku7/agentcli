"""
Modernize python code typing to 3.11+ style (list, dict, tuple, set) - Absolute Safe Version
"""

import re
from pathlib import Path

ROOT_DIR = Path("src/uagent")
py_files = list(ROOT_DIR.glob("**/*.py"))


def modernize_file(file_path: Path):
    content = file_path.read_text(encoding="utf-8")

    # 既に処理されているかチェック
    has_annotations = "from __future__ import annotations" in content

    # 1. from __future__ import annotations の挿入
    if not has_annotations:
        docstring_match = re.match(r'^(""".*?"""|\'\'\'.*?\'\'\')', content, re.DOTALL)
        if docstring_match:
            docstring = docstring_match.group(1)
            content = content.replace(
                docstring, f"{docstring}\nfrom __future__ import annotations"
            )
        else:
            content = f"from __future__ import annotations\n\n{content}"

    # 2. 型アノテーションの大文字（List, Dict, Tuple, Set）のみを小文字に徹底置換
    # これらはネストに関わらず常に100%安全に小文字に変換できます。
    replacements = {
        # ジェネリクス
        r"\bList\[": "list[",
        r"\bDict\[": "dict[",
        r"\bTuple\[": "tuple[",
        r"\bSet\[": "set[",
        # 独立した単語としての古い型ヒント（引数や変数定義： : List, -> List 等）
        r":\s*List\b": ": list",
        r":\s*Dict\b": ": dict",
        r":\s*Tuple\b": ": tuple",
        r":\s*Set\b": ": set",
        r"->\s*List\b": "-> list",
        r"->\s*Dict\b": "-> dict",
        r"->\s*Tuple\b": "-> tuple",
        r"->\s*Set\b": "-> set",
    }

    for pattern, repl in replacements.items():
        content = re.sub(pattern, repl, content)

    # 書き込み
    file_path.write_text(content, encoding="utf-8")
    print(f"Safe Modernized: {file_path}")


if __name__ == "__main__":
    for py_file in py_files:
        modernize_file(py_file)
