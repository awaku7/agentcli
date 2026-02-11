## 参照（必要時のみ）: prompt_get ツールの使い方

あなた（LLM）は、**テンプレートを選んだり、別のテンプレートを呼び出したくなった場合にのみ** `prompt_get` ツールを使ってください。
（例：要件定義→基本設計に進めたい／コードレビュー用テンプレを呼びたい／利用可能テンプレ一覧を見たい 等）

### prompt_get の目的
`./prompts` 配下のテンプレートカタログ（`./prompts/index.yaml`）からテンプレを検索・取得し、
テンプレ内の `{{placeholder}}` を `context` で埋め込んだ **完成プロンプト（filled_prompt）** を返します。

### 絶対パスが必要な場合（read_file で参照したいとき）
LLMはローカルファイルを勝手に読めません。**ファイル内容が必要なときは `read_file` ツール**を使います。
ただし実行環境によっては相対パスの起点が不明になるため、**まず `prompt_get(format="json")` を呼んで `tool_root_dir`（リポジトリルート絶対パス）を取得し**、それを使って `read_file` してください。

#### 手順（例）
1. `prompt_get` を JSON で呼ぶ（どのテンプレでもよい）
   - 例：`{"id":"system_dev.requirements.v1","format":"json"}`
2. 返ってきた `tool_root_dir` を使って絶対パスを組み立てる
   - 例：`{tool_root_dir}/prompts/templates/_shared_prompt_get_reference.md`
3. `read_file` を呼ぶ

### 典型的な使い方
- **テンプレ一覧を確認**したい → `list_only: true` を使う
- **特定テンプレを取得**したい → `id`（推奨）または `domain`+`task` で指定
- プレースホルダ未入力を**エラーにしたい** → `strict: true`

### 入力パラメータ（要点）
- `id`: テンプレIDを直接指定（最優先） 例: `system_dev.requirements.v1`
- `domain` / `task`: 絞り込み指定（id未指定時）
- `context`: `{"placeholder": "値"}` の辞書。`{{placeholder}}` を埋める
- `format`: `markdown` または `json`
- `list_only`: trueでメタ情報一覧だけ返す
- `include_template`: trueでテンプレ本文も返す（通常不要）

### 利用例（イメージ）
- 一覧: `{"list_only": true, "format": "json"}`
- 要件定義: `{"id": "system_dev.requirements.v1", "context": {"background": "...", "goals": "..."}}`

---

### prompt_get ツール仕様（TOOL_SPEC・抜粋）
以下は参照用です（必要時のみ利用）。

```json
{
  "type": "function",
  "function": {
    "name": "prompt_get",
    "description": "Professional用途のプロンプトテンプレートを ./prompts から取得し、context を埋め込んだ完成プロンプト（filled_prompt）を返します。",
    "parameters": {
      "type": "object",
      "properties": {
        "domain": {"type": "string"},
        "task": {"type": "string"},
        "context": {"type": "object"},
        "id": {"type": "string"},
        "language": {"type": "string", "default": "ja"},
        "format": {"type": "string", "enum": ["markdown", "json"], "default": "markdown"},
        "strict": {"type": "boolean", "default": false},
        "include_template": {"type": "boolean", "default": false},
        "list_only": {"type": "boolean", "default": false}
      },
      "required": []
    }
  }
}
```
