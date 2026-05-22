"""
Modernize python code typing to 3.11+ style (list, dict, tuple, set)
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
        # docstringの下か、ファイルの先頭に挿入
        docstring_match = re.match(r'^(""".*?"""|\'\'\'.*?\'\'\')', content, re.DOTALL)
        if docstring_match:
            docstring = docstring_match.group(1)
            content = content.replace(
                docstring, f"{docstring}\nfrom __future__ import annotations"
            )
        else:
            content = f"from __future__ import annotations\n\n{content}"

    # 2. typing 小文字化 (List, Dict, Tuple, Set の組み込み型置換)
    # 単語境界 `\b` を用いて、独立した型ヒント定義のみを正確に置換
    replacements = {
        r"\bList\[": "list[",
        r"\bDict\[": "dict[",
        r"\bTuple\[": "tuple[",
        r"\bSet\[": "set[",
    }

    for pattern, repl in replacements.items():
        content = re.sub(pattern, repl, content)

    # 書き込み
    file_path.write_text(content, encoding="utf-8")
    print(f"Modernized typing references: {file_path}")


if __name__ == "__main__":
    for py_file in py_files:
        modernize_file(py_file)
