# Structured Output 継続作業メモ

## 現在の方針

- 共通環境変数は `UAGENT_STRUCTURED_OUTPUT` に統一する。
- デフォルトは有効（未設定時 `true`）。
- `false` / `0` / `off` で無効化する。
- 旧環境変数は使用しない。
  - `UAGENT_RESPONSE_FORMAT`
  - `UAGENT_LLAMA_CPP_FORMAT`
  - `UAGENT_OLLAMA_FORMAT`
- 対応判定はプロバイダー単位ではなく、`provider + model` 単位で行う。
- 非対応モデルは、プロンプトでJSONを要求し、ローカルでパース・検証するフォールバックを使用する。

## 実装済みプロバイダー

- OpenAI
  - Chat Completions: `response_format`
  - Responses API: `text.format`
  - JSON Object / JSON Schema
- Azure
  - OpenAI互換形式
- OpenRouter
  - OpenAI互換形式
  - モデル対応状況に依存
- Gemini / Vertex AI
  - `response_mime_type="application/json"`
  - `response_schema`
- Claude / Anthropic
  - `output_config.format`
  - JSON Schema
- Grok / xAI
  - JSON Schema形式
- DeepSeek
  - 公式仕様に合わせて `response_format={"type":"json_object"}`
  - Schemaはプロンプトで指定
- Z.AI
  - 公式仕様に合わせて `response_format={"type":"json_object"}`
  - Schemaはプロンプトで指定
- Ollama
  - `format="json"`
  - JSON Schema指定時はSchema本体を `format` に渡す
- llama.cpp
  - `response_format`
  - JSON / JSON Schema

## 重要な仕様確認

### DeepSeek

DeepSeek公式ドキュメントでは、Structured Outputは現在JSONモードとして提供される。

```json
{"response_format": {"type": "json_object"}}
```

`json_schema`形式を直接送信しない。システムプロンプトにJSON構造を記述する。

### Z.AI

Z.AI公式ドキュメントでも、現在のStructured OutputはJSONモードが基本。

```json
{"response_format": {"type": "json_object"}}
```

`json_schema`形式を直接送信しない。

### Bedrock

AWS公式のStructured Outputは、Converse APIでは次の形式を使用する。

```python
outputConfig={
    "textFormat": {
        "type": "json_schema",
        "structure": {
            "jsonSchema": {
                "name": "response",
                "description": "Structured response",
                "schema": json.dumps(schema),
            }
        },
    }
}
```

ただし現在のBedrock実装はAWS SDKの `bedrock-runtime.converse()` ではなく、OpenAI SDKを使ったカスタムOpenAI互換エンドポイントである。そのため、AWS公式仕様に合わせるにはBedrock専用のConverse APIアダプターが必要。現時点では保留。

## 未対応プロバイダー

- Bedrock（保留）
- NVIDIA
- Alibaba
- Moonshot
- MiMo
- LM Studio
- MiniMax
- Hugging Face
- Sakana
- Sakura
- Novita
- Together
- Vercel
- PFN

## 次回の作業候補

1. `llmcapa`のモデル能力情報を確認し、Structured Output判定をモデル単位にする。
2. `supports_json_mode` とJSON Schema対応を区別できる能力フィールドを追加・確認する。
3. OpenAI互換プロバイダーについて、モデル単位で実際の `response_format` 対応を確認する。
4. 完全なOpenAI互換が確認できたプロバイダーだけ、共通アダプターへ追加する。
5. 優先候補は以下。
   - Alibaba
   - Moonshot
   - MiMo
   - LM Studio
   - MiniMax
   - Novita
   - Together
   - Vercel
   - NVIDIA
   - PFN
6. Bedrockは最後にAWS SDK Converse API専用アダプターとして実装する。

## 検証状況

以下の変更ファイルはPython構文チェック済み。

- `src/uagent/providers/structured_output.py`
- `src/uagent/llm_round_helpers.py`
- `src/uagent/providers/llm_openai_responses.py`
- `src/uagent/providers/llm_gemini.py`
- `src/uagent/providers/llm_claude.py`
- `src/uagent/providers/llm_deepseek.py`
- `src/uagent/providers/llm_zai.py`
- `src/uagent/providers/llm_ollama.py`
- `src/uagent/providers/llm_llama_cpp.py`
- `src/uagent/llm_grok_round.py`

## 注意

- ネイティブStructured Outputをデフォルト有効にする場合でも、通常会話を無条件にJSON化しないこと。
- `response_mode=json` または `response_schema` が指定された場合にだけ、ネイティブ出力形式を付与する。
- ストリーミング、ツール呼び出し、推論モデルでは、モデルごとの制約を確認する。
