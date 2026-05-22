# tool_catalog 対応状況メモ

作業日: 2026-05-19

## 目的

- `tool_catalog` の検索順位を改善し、`x_search_terms` を最優先で効かせる。
- 日本語クエリを Janome で分かち書きし、名詞・動詞ベースで検索する。

## 反映済み

### `src/uagent/tools/__init__.py`

- `x_search_terms` を集約する `_collect_search_terms()` を追加済み。
- `get_tool_catalog()` で `x_search_terms` を検索対象に追加済み。
- 検索順位を調整し、`x_search_terms` 一致を最優先で加点するよう変更済み。
- Janome のトークン化は、**名詞・動詞のみ**を base_form 優先で使うよう変更済み。

### `src/uagent/tools/replace_in_file_tool.json`

- `x_search_terms` に日本語/英語の候補を追加済み。
- `replace_in_file` は現在、`x_search_terms` 一致で `tool_catalog` の 1 位に出る状態。

## 現在の挙動

### クエリ: `テキストを置換したい`

- Janome 分解後の主な検索語:
  - `テキスト`
  - `置換`
  - `する`
  - `テキストを置換したい`
  - それぞれの `s` 付き派生
- 現在の結果:
  1. `replace_in_file`
  1. `add_long_memory`
  1. `audio_speech`
  1. `audio_transcribe`
  1. `binary_edit`
  1. `create_file`
  1. `document_extract`
  1. `exstruct`
  1. `fetch_url`
  1. `file_exists`

## 確認済み

- `python_compile` で `src/uagent/tools/__init__.py` は成功。
- `system_reload` 済み。
- `tool_catalog` で `テキストを置換したい` を再検索し、`replace_in_file` が 1 位になることを確認済み。

## 次にやるなら

- 他の重要ツールにも `x_search_terms` を追加して、日本語検索の命中率を上げる。
- 必要なら `tool_catalog` の加点ルールを微調整する。
- 新しい検索語を追加したら `reload` → `再検索` → `順位確認` の順で検証する。

## メモ

- `x_search_terms` は検索専用の拡張フィールド。
- `name` / `description` / `parameters` に加えて検索されるが、`x_search_terms` 一致を強く優先するように調整済み。
