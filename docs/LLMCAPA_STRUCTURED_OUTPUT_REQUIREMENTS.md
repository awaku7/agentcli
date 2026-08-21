# llmcapa Structured Output 対応要件

## 1. 目的

uag がモデル単位で Structured Output の適用可否を判断できるようにする。

現在の `Capability` は `supports_json_mode` を持つが、JSON Schema 対応を独立して表現できない。そのため、JSON Object モードに対応するモデルへ JSON Schema を送信する誤判定が起こり得る。

判定単位はプロバイダー単位ではなく、必ず次の組み合わせとする。

```text
provider + model_id
```

## 2. 必須能力フィールド

`Capability` に次のフィールドを追加する。

```python
supports_json_mode: bool | None
supports_json_schema: bool | None
```

### 値の意味

| 値 | 意味 |
|---|---|
| `True` | 公式仕様または検証済み実装で対応を確認済み |
| `False` | 公式仕様または検証済み実装で非対応を確認済み |
| `None` | 情報不足、未確認、プロバイダー依存 |

既存の `supports_json_mode` が `bool` 固定の場合は、後方互換性を保つため段階的に `bool | None` へ移行する。ただし、未知を`False`として扱うと対応モデルを誤ってフォールバックへ送るため、uagでは未知と非対応を区別できるAPIを提供する。

## 3. 推奨API

```python
supports_json_mode(model_id: str, provider: str) -> bool | None
supports_json_schema(model_id: str, provider: str) -> bool | None
```

既存の汎用APIも対応させる。

```python
capability.supports("json_mode") -> bool | None
capability.supports("json_schema") -> bool | None
```

JSON SchemaがJSON Objectモードの上位互換であるとは仮定しない。両方の値を個別に管理する。

## 4. データモデル例

JSON Schema対応まで確認できるモデル:

```python
Capability(
    provider="openai",
    model_id="gpt-4o",
    supports_json_mode=True,
    supports_json_schema=True,
)
```

JSONモードのみ確認できるモデル:

```python
Capability(
    provider="deepseek",
    model_id="deepseek-chat",
    supports_json_mode=True,
    supports_json_schema=False,
)
```

未確認のモデル:

```python
Capability(
    provider="custom-gateway",
    model_id="example-model",
    supports_json_mode=None,
    supports_json_schema=None,
)
```

## 5. 公式情報と検証情報

能力情報には、可能であれば根拠を保持する。

```python
extra={
    "structured_output": {
        "json_mode": {
            "supported": True,
            "source": "official documentation URL",
            "checked_at": "2026-08-21",
        },
        "json_schema": {
            "supported": False,
            "source": "official documentation URL",
            "checked_at": "2026-08-21",
        },
    }
}
```

最低限、次を記録できるようにする。

- 対応状態
- 確認元URLまたは検証方法
- 確認日
- プロバイダー名
- モデルIDまたはモデル範囲

プロバイダー全体の仕様とモデル固有の制約が異なる場合は、モデル固有の情報を優先する。

## 6. uagでの分岐契約

uag は次の優先順位で出力形式を選択する。

```python
schema_support = supports_json_schema(model_id, provider)
json_support = supports_json_mode(model_id, provider)

if response_schema is not None and schema_support is True:
    use_native_json_schema()
elif json_support is True:
    use_native_json_object()
else:
    request_json_in_prompt_and_validate_locally()
```

`None` は `False` と同じではない。`None` の場合は、対象プロバイダーに安全な既定値がある場合だけそれを使用し、それ以外はローカルパース・検証へフォールバックする。

## 7. プロバイダー別の初期方針

| プロバイダー | JSON Object | JSON Schema | 方針 |
|---|---:|---:|---|
| OpenAI | 確認済み | モデルごとに確認 | model_id単位で判定 |
| Azure | 互換構成ごとに確認 | デプロイモデルごとに確認 | deployment名をモデルIDとして扱う |
| OpenRouter | モデル・ルーター依存 | モデル・ルーター依存 | 未確認時はフォールバック |
| Gemini / Vertex AI | API形式が別 | `response_schema` | Google API能力として別管理 |
| Claude | API形式が別 | `output_config.format` | Anthropic能力として別管理 |
| DeepSeek | 確認済み | 直接送信しない | JSON Object + プロンプトSchema |
| Z.AI | 確認済み | 直接送信しない | JSON Object |
| Ollama | モデル・バージョン依存 | モデル・バージョン依存 | API実測またはカタログ情報 |
| llama.cpp | サーバー・モデル依存 | サーバー・モデル依存 | `/props`とモデル情報を優先 |

## 8. 必須テスト

最低限、次のテストを追加する。

1. JSONモードのみ対応するモデルにJSON Schemaを送らない。
2. JSON Schema対応モデルにはネイティブSchemaを送る。
3. 能力不明モデルはローカル検証フォールバックになる。
4. 同じモデルIDでもプロバイダーが異なる場合に能力を混同しない。
5. Azureのdeployment名を別モデルとして解決できる。
6. `UAGENT_STRUCTURED_OUTPUT=false` が能力判定より優先される。
7. 通常会話ではStructured Outputを付与しない。
8. ツール呼び出し中に、モデルが未対応の形式を受け取らない。
9. ストリーミング時のプロバイダー固有制約を回避する。
10. capabilityキャッシュのクリア後に新しい能力情報が反映される。

## 9. 後方互換性

- 既存の `supports_json_mode` は維持する。
- 既存データに `supports_json_schema` がない場合は`None`として扱う。
- 既存のllmcapa利用者が未知フィールドで壊れないよう、追加フィールドはオプショナルにする。
- uag側では古いllmcapaでも動作する互換分岐を用意する。

## 10. 完了条件

- `Capability` がJSONモードとJSON Schemaを別々に表現できる。
- `provider + model_id`で能力を解決できる。
- 公式根拠または検証方法を記録できる。
- uagが`True`、`False`、`None`を区別して分岐できる。
- 未対応・不明モデルへ不正な`response_format`を送らない。
- 対応プロバイダーの回帰テストが通る。
