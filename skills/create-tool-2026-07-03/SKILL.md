---
name: create-tool
description: 新規ツール（Python + JSON）を生成し、i18n翻訳（全34ロケール）・ruff/black整形・py_compile検証まで一貫実行する。
license: Apache-2.0
---

# 目的

agentcli に新規ツールを追加する一連の工程を自動実行する。
手作業で抜けがちな **i18n翻訳（全34言語）・コード整形・構文チェック** まで含めて完了する。

# 入力（このスキルがユーザーに確認すること）

ユーザーに以下を質問し、全て揃ったら実行を開始する。

1. **ツール名**: 英小文字+アンダースコア（例: `pdf_ocr`）
2. **英語説明**: `tool.description` に使う1行（簡潔に）
3. **引数定義**: 各引数の name / type / required / description（英、簡潔に）
4. **実装概要**: `run_tool()` の処理内容
5. **x_search_terms（英）**: 検索ワード配列（省略可）

## 質問テンプレート

```
これから新規ツールを作成します。以下を教えてください：
1. ツール名（例: pdf_ocr）
2. 英語の説明（簡潔に）
3. 引数（JSON形式、説明は簡潔に）
4. 実装の概要（何をするツールか）
5. x_search_terms（省略可）
```

注: 日本語を含む全ロケールの翻訳は `translate_text` で自動生成する。

# LLM が自動判断する項目（ユーザーには聞かない）

以下の項目はユーザー入力ではなく、LLMがツールの実装内容から判断して設定する。

| 項目 | 判断基準 |
|------|---------|
| `tool_genre` | ツールの機能から判断。ファイル操作→`file`、API呼出→`external`、デバイス制御→`iot`、開発補助→`devel`、汎用→`basic` |
| `BUSY_LABEL` | 時間のかかる処理なら `True`、即時返却なら `False` |
| `STATUS_LABEL` | 任意。表示用ラベル文字列、なければ None |
| `LAZY_LOAD` | 重いimport（PIL/numpy等）が必要な場合のみ `True` |
| `tool_level` | 基本的に省略（=0）。システム内部用なら `-1`（隠し） |
| `x_parallel_safe` | 副作用なし並列実行安全なら `True`、状態変更するなら `False` |
| `additionalProperties` | 基本的に `False` |

# 環境

- Python 実行環境（`python_exec` ツール）
- 既存ツール: `translate_text` / `lint_format` / `python_compile` / `create_file`
- `src/uagent/tools/` が書き込み可能

# 実行フロー（この順序で固定）

## Step 0: 重複チェック

- `search_files(glob="<name>_tool.*", path="src/uagent/tools")` で既存ツールと重複しないか確認
- 重複あればスキル中断しユーザーに報告

## Step 1: Python ファイル生成

`create_file` で `src/uagent/tools/<name>_tool.py` を生成する。

### テンプレート

```python
from __future__ import annotations

# src/uagent/tools/<name>_tool.py

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

from typing import Any

BUSY_LABEL = False  # LLM判断
STATUS_LABEL = None

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "tool_genre": "<genre>",  # LLM判断
    "x_parallel_safe": False,
    "function": {
        "name": "<name>",
        "description": _(
            "tool.description",
            default="<english description>",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[<x_search_terms_english_array>],
        ),
        "x_search_terms_en": [<x_search_terms_english_array>],
        "parameters": {
            "type": "object",
            "properties": {
                <param_name>: {
                    "type": "<type>",
                    "description": _(
                        "param.<param_name>.description",
                        default="<english description>",
                    ),
                }
            },
            "required": [<required_param_names>],
            "additionalProperties": False,
        },
    },
}

def run_tool(args: dict[str, Any]) -> str:
    <implementation>
```

### ルール

- `_("key", default="...")` で全ユーザー向け文字列をラップ
- key は `tool.description`, `param.<name>.description` の命名規則
- `x_search_terms` は `_("x_search_terms", default=[...])`（i18n経由で現在ロケールの配列を読む）
- `x_search_terms_en` は英語配列を直書き（英語検索用の fallback、i18n を通さない）
- `run_tool()` は必ず `str` を返す
- エラーハンドリングを含める

## Step 2: JSON ファイル生成（全34ロケール、翻訳込み）

`python_exec` で以下のスクリプトを実行し、`src/uagent/tools/<name>_tool.json` を一発生成する。

### 処理内容

1. `en` セクションをユーザー入力から作成
2. `ja` を含む残り33ロケールについて、`translate_text` を呼び出して翻訳
3. 全34ロケールをまとめて `json.dumps(indent=2, ensure_ascii=False)` で書き出し

### 翻訳対象キー（各ロケール）

- `tool.description`
- `x_search_terms`（配列の各要素を翻訳）
- `param.<name>.description`（各パラメータ）

### ロケール一覧（34）と Google 言語コード

| JSON locale | Google code |
|---|---|
| ja | ja |
| es | es |
| fr | fr |
| ko | ko |
| de | de |
| it | it |
| ru | ru |
| pt_br | pt |
| pt | pt |
| id | id |
| vi | vi |
| pl | pl |
| hi | hi |
| ar | ar |
| sv | sv |
| sw | sw |
| nb | no |
| nl | nl |
| fi | fi |
| cs | cs |
| uk | uk |
| tr | tr |
| th | th |
| zh_cn | zh-CN |
| zh_tw | zh-TW |
| bn | bn |
| fa | fa |
| mn | mn |
| mr | mr |
| el | el |
| he | iw |
| hu | hu |
| ro | ro |

### 実装戦略

`python_exec` 内で全ロケールをループ。各ロケールの全テキストを `translate_text(texts=[...], target_lang=..., source_lang="en")` に一度に渡して翻訳し、戻り値を各キーにマッピングする。

### 【重要】プレースホルダ保護

`translate_text` の `protect_placeholders` はコードファイル自動検出に依存するため、平文の description 文字列に含まれる `{path}` や `{name}` 等のプレースホルダは保護されない。Google Translate が `{path}` を `{パス}` などに翻訳してしまう。

対処: **翻訳前にプレースホルダを独自トークンで置換し、翻訳後に戻す。**

```python
import re

def protect(text: str) -> tuple[str, dict[str, str]]:
    mapping = {}
    def replacer(m):
        orig = m.group(0)
        token = f"__PH_{len(mapping)}__"
        mapping[token] = orig
        return token
    text = re.sub(r'\{[A-Za-z_][A-Za-z0-9_]*\}', replacer, text)
    return text, mapping

def restore(text: str, mapping: dict[str, str]) -> str:
    for token, orig in mapping.items():
        text = text.replace(token, orig)
    return text
```

各テキストを翻訳前に `protect()` で処理し、翻訳結果に `restore()` を適用する。

### その他の注意

- `x_search_terms` は各言語のネイティブな検索ワードに翻訳する
- 翻訳エラー・空文字の場合は英語のまま保持（fallback）

## Step 3: ruff/black 整形

`lint_format(tools=["ruff", "black"], mode="fix", targets=["src/uagent/tools/<name>_tool.py"])`

- ユーザーに確認を求める: 「<name>_tool.py に ruff/black を適用しますか？（y/n）」
- 承諾されたら実行。拒否されたらスキップ。

## Step 4: 構文チェック

`python_compile(path="src/uagent/tools/<name>_tool.py")` を実行。

- エラーが出た場合は修正して再チェック（最大3回リトライ）

## Step 5: 完了報告

生成ファイル一覧と内容サマリを出力する。

- `src/uagent/tools/<name>_tool.py`
- `src/uagent/tools/<name>_tool.json`

# 成功判定

- `python_compile` がエラーなし
- `lint_format(mode=check)` がエラーなし
- 2ファイルが存在する
- JSON に全34ロケールのエントリが含まれている
- JSON 内の全 `{xxx}` プレースホルダが元の名前を維持している（`{パス}` などに翻訳されていない）

# 失敗時のよくある原因

- `translate_text` の一時的APIエラー（リトライ可能）
- JSON のキー名ミス（typo）
- `run_tool()` 内の構文エラー
- 同名ツールが既に存在する（Step 0 で防止）
- プレースホルダ名が翻訳されてしまう（`{path}` → `{パス}`）。翻訳前の保護処理が必須
