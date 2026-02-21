# Tool i18n 開発ガイド（UAGENT）

このドキュメントは、`src/uagent/tools/` 配下のツールに対して i18n（多言語化）を行うための方針と具体的な実装手順をまとめたものです。

---

## 目的

- ツールのメタデータ（OpenAI function schema の `TOOL_SPEC`）を `UAGENT_LOCALE` に応じて切り替えられるようにする
- 翻訳ファイル（JSON）が無い／不完全でもツールを壊さない（必ず動く）
- ツール開発者が Python ロジックを触らずに翻訳文言を追加・調整できるようにする

---

## 何を翻訳対象にするか

最低限、次の **`TOOL_SPEC` 由来のメタデータ**を翻訳対象とします（モデル/ランタイムへ露出する情報）。

- `TOOL_SPEC["function"]["description"]`
- `TOOL_SPEC["function"].get("system_prompt")`
- `TOOL_SPEC["function"]["parameters"]["properties"][...]["description"]`

※実行時のエラーメッセージや確認文なども翻訳して構いませんが、まずは `TOOL_SPEC` の翻訳を最優先とします。

---

## ロケールの決定

ロケールは環境変数で指定します。

- `UAGENT_LOCALE`

正規化ルール（`src/uagent/tools/i18n_helper.py` 実装）:

- `ja_JP` / `ja-JP` → `ja`
- `en_US` / `en-US` → `en`
- 未設定／空 → `en`

---

## 翻訳の仕組み（make_tool_translator）

ツールでは `src/uagent/tools/i18n_helper.py` の `make_tool_translator(__file__)` を使用します。

### 翻訳ファイルの場所

ツールモジュール `foo_tool.py` に対する翻訳ファイルは、同階層の JSON とします。

- Python: `src/uagent/tools/foo_tool.py`
- JSON: `src/uagent/tools/foo_tool.json`

### JSONフォーマット

```json
{
  "en": {"key": "text", "...": "..."},
  "ja": {"key": "text", "...": "..."}
}
```

### フォールバック順序

翻訳キーの解決は次の順で行います。

1. 指定ロケール（例: `ja`）
2. `en`
3. Python 側に埋め込まれた `default=`

このため、**JSON が存在しなくてもツールは必ず動作**します。

---

## ツール実装で必須のコードパターン

各ツールの先頭で translator を作成し、名前は必ず `_`（アンダースコア）に統一します。

```python
from __future__ import annotations

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)
```

### TOOL_SPEC の文字列を包む

`TOOL_SPEC` の文字列は `_()` で包み、キーと `default=` を指定します。

```python
TOOL_SPEC = {
  "type": "function",
  "function": {
    "name": "my_tool",
    "description": _(
      "tool.description",
      default="(fallback text)"
    ),
    "system_prompt": _(
      "tool.system_prompt",
      default="(fallback system prompt)"
    ),
    "parameters": {
      "type": "object",
      "properties": {
        "arg1": {
          "type": "string",
          "description": _(
            "param.arg1.description",
            default="(fallback param description)"
          )
        }
      }
    }
  }
}
```

---

## 命名規約

### translator 変数名

- **必ず `_` に統一**すること
- `t = ...` は使用しない

### キー命名

推奨キーは次の形式に統一します。

- `tool.description`
- `tool.system_prompt`
- `param.<param_name>.description`

任意で追加してよいキー例:

- `error.<name>`（エラーメッセージ）
- `confirm.<name>`（確認メッセージ）

---

## 翻訳JSONの作成・更新

例: `human_ask_tool.py`

- Python: `src/uagent/tools/human_ask_tool.py`
- JSON: `src/uagent/tools/human_ask_tool.json`

JSON例:

```json
{
  "en": {
    "tool.description": "...",
    "tool.system_prompt": "...",
    "param.message.description": "..."
  },
  "ja": {
    "tool.description": "...",
    "tool.system_prompt": "...",
    "param.message.description": "..."
  }
}
```

---

## 注意点・落とし穴

### 文字コード（UTF-8）

- 翻訳JSONは **UTF-8** で保存してください。
- ツールの Python ソースも **UTF-8** を前提とします。

### system_prompt の長文化

`system_prompt` は長くなりがちです。

- Python 側は三重クォート文字列で読みやすく保つ
- JSON 側は `\n` を含む通常の JSON 文字列として保存する

### 翻訳キー欠落

JSONにキーが無い場合は `default=` が使われます。

- 翻訳が未着手でも壊れない
- `default=` を更新するだけでフォールバック文言を更新できる

---

## テスト手順

- 変更したツールは `python -m py_compile`（構文チェック）を通す
- `UAGENT_LOCALE=ja` / `UAGENT_LOCALE=en` を切り替えて `TOOL_SPEC` が期待通りになることを確認する

---

## 関連ファイル

- `src/uagent/tools/i18n_helper.py`
- `src/uagent/tools/read_file_tool.py`（i18n 実装例）
- `src/uagent/tools/human_ask_tool.py`（JSON 翻訳例）
