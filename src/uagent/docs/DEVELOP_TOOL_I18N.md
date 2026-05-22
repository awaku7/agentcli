# Tool I18N 開発・翻訳ガイド

ツール (`src/uagent/tools/*.py`) を多言語化し、JSON 形式の翻訳ファイルを管理するための統合ガイドです。`docs/TOOL_I18N_GUIDE.md` の内容はこの文書に統合しました。

______________________________________________________________________

## 1. 重要な前提

- ツール側の I18N は、メインアプリの gettext (`.po` / `.mo`) とは**別方式**です。
- ツールの翻訳は、各 Python モジュールと同じベース名の JSON で管理します。
  - 例: `src/uagent/tools/get_workdir_tool.py`
  - 翻訳ファイル: `src/uagent/tools/get_workdir_tool.json`
- `make_tool_translator(__file__)` を使うと、実行時の言語設定に応じて適切な翻訳ブロックを選べます。
- インドネシア語 (`id`) はツール側でも正式対応対象です。

______________________________________________________________________

## 2. ツール多言語化の標準手順

### 2.1 Python コードの修正

翻訳したい文字列を `_()` で囲みます。

```python
from .i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)

TOOL_SPEC = {
    "function": {
        "description": _("tool.description", default="Analyzes code."),
    }
}
```

### 2.2 JSON 翻訳ファイルの更新

同名の JSON に翻訳を入れます。

```json
{
  "en": {
    "tool.description": "Analyzes code.",
    "param.path.description": "Target file path."
  },
  "ja": {
    "tool.description": "コードを解析します。",
    "param.path.description": "対象ファイルのパス。"
  },
  "id": {
    "tool.description": "Kode dianalisis.",
    "param.path.description": "Path file target."
  }
}
```

### 2.3 翻訳対象の抽出

ツール内の `_()` で囲った内容を自動抽出して、翻訳漏れを防ぎます。

```bash
xgettext --language=Python --keyword=_:1,2 --from-code=UTF-8 -o my_tool.pot src/uagent/tools/my_tool_tool.py
```

- `--keyword=_:1,2`: 1番目の引数を翻訳キー (`msgid`)、2番目の引数をデフォルト値として抽出します。

### 2.4 検証

- ツールが読み込まれることを確認する
- 必要なら `python -m py_compile` で構文チェックする
- JSON のキーが Python 側のキーと一致していることを確認する
- 変更後に `system_reload` や軽い読み込み確認を行う

______________________________________________________________________

## 3. 翻訳のルール

- **キー名**
  - 推奨: `tool.description`, `tool.system_prompt`, `param.<name>.description`, `err.<name>`
- **プレースホルダー**
  - `{path}`, `{count}`, `%(err)s` などは**変更しない**
- **技術識別子**
  - ファイル名、クラス名、関数名、形式マーカー、`[WARN]` のようなタグは基本的に翻訳しない
- **改行**
  - JSON 内では `\n` を使う
  - 複数行の system prompt は構造を保つ
- **エンコーディング**
  - UTF-8（BOM なし）を推奨

______________________________________________________________________

## 4. 既存ツールを更新する場合

1. Python 側の `_()` キーを確認する
1. 既存の `<tool>_tool.json` を開く
1. 不足している言語ブロックを追加する
1. 既存キーの文言を更新する場合は、`en` と各ロケールを同期する
1. 変更後はツールが正しく読み込まれるか確認する

______________________________________________________________________

## 5. 破壊的操作や外部操作があるツール

次のようなツールは、実行前に `human_ask` による確認を必ず入れます。

- delete / overwrite / rename / move
- shell / PowerShell / Python / Git 実行
- 外部 API / MCP / ブラウザ / Webhook / 送信系
- ファイルやディレクトリを変更する操作

確認メッセージは、ユーザーが内容を見て判断できるように具体的にします。

______________________________________________________________________

## 6. 検証チェックリスト

- `TOOL_SPEC` と `run_tool` の両方がある
- JSON のキーと Python のキーが一致している
- `en` の fallback が欠けていない
- `id`（インドネシア語）を含む必要なロケールが入っている
- プレースホルダーが壊れていない
- 危険な処理に `human_ask` が入っている
- 変更後にツールの読み込み確認をした

______________________________________________________________________

## 7. 参考

- `src/uagent/docs/DEVELOP_TOOL.md`
- `src/uagent/tools/*.json`
- `src/uagent/tools/i18n_helper.py`

______________________________________________________________________

## 8. 補足: インドネシア語 (`id`) 対応

- インドネシア語の翻訳は `id` キーに入れる
- `make_tool_translator(__file__)` は `id_ID` のようなタグを `id` に正規化する
- `id` が無い場合でも、`en` の fallback が完結していれば表示は崩れにくい

______________________________________________________________________

## 9. 運用メモ

- ツールの I18N は gettext の `.po` / `.mo` ではなく、`src/uagent/tools/*.json` で管理する
- 技術識別子、ファイル名、データ形式マーカーは翻訳しない
- 既存の翻訳は、意味が変わらない限り維持する
- 大きな文言変更をした場合は、`en` と各ロケールを必ず同期する

必要に応じて、このガイドに各ツール固有の運用ルールを追記してください。
