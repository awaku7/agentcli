# Tool I18N 開発・翻訳ガイド

ツール (`src/uagent/tools/*.py`) を多言語化し、JSON 形式の翻訳ファイルを管理するためのガイドです。

---

## ツール多言語化の標準手順 (1つずつ対応する場合)

新しいツールの作成時や、既存のツールを多言語化する際は、以下のステップで行います。

### 1. 準備 (Pythonコードの修正)
ツール内の翻訳したい文字列を `_("key", default="...")` 形式で囲みます。

```python
from .i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)

TOOL_SPEC = {
    "function": {
        "description": _("tool.description", default="Analyzes code."),
        # ...
    }
}
```

### 2. 翻訳対象の抽出 (xgettext の活用)
ツール内の `_()` で囲った内容を自動抽出して、翻訳漏れを防ぎます。

```bash
# 特定のツール (例: my_tool_tool.py) から抽出
xgettext --language=Python --keyword=_:1,2 --from-code=UTF-8 -o my_tool.pot src/uagent/tools/my_tool_tool.py
```
*   `--keyword=_:1,2`: 1番目の引数を翻訳キー (`msgid`)、2番目をデフォルト値 (`msgstr`) として抽出するよう指示します。

### 3. JSON ファイルの作成・更新
抽出した `POT` 内容を元に、同名の JSON ファイルを作成または更新します。

**ファイル名**: `src/uagent/tools/my_tool_tool.json`

```json
{
  "en": {
    "tool.description": "Analyzes code.",
    "param.path.description": "Target file path."
  },
  "ja": {
    "tool.description": "コードを解析します。",
    "param.path.description": "対象ファイルのパス。"
  }
}
```

### 4. 検証
ツールを読み込んで、言語設定に応じて `TOOL_SPEC` が切り替わるか確認します。

```bash
# Windows
set UAGENT_LANG=ja
python -m uagent --tools
```

---

## 翻訳のルール

- **キー名**: `tool.description`, `param.<name>.description`, `error.<name>` を推奨。
- **改行**: JSON 内では `\n` を使用。
- **エンコーディング**: 必ず **UTF-8 (BOMなし)**。

---

## 既存ツールの翻訳を更新する場合
1.  ソースコードの `_()` 定義を確認。
2.  既存の `.json` を開き、不足している言語（例: `de`, `fr`）のブロックを追加。
3.  `python -m py_compile` で構文チェック。
