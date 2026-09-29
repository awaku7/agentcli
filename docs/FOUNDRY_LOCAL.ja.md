# Microsoft Foundry Local

UAG では Foundry Local を、通常のローカル OpenAI 互換エンドポイントとして扱います。

設定例:

```text
UAGENT_PROVIDER=foundry_local
UAGENT_FOUNDRY_LOCAL_BASE_URL=http://localhost:<port>/v1
UAGENT_FOUNDRY_LOCAL_DEPNAME=phi-4-mini   # 省略可
UAGENT_FOUNDRY_LOCAL_API_KEY=...          # 省略可
```

base URL は loopback（`localhost`、`127.0.0.1`、`::1` など）である必要があります。UAG はこの統合で Foundry Local の起動、モデルのダウンロード/ロード、localhost 探索、Foundry Local SDK の利用を行いません。

モデル能力の情報は llmcapa を次の組み合わせで直接検索します。

```python
llmcapa.get(model_name, provider="foundry-local")
```

モデル名は `/` を含めてそのまま使用します。この検索で見つからない場合、末尾だけの再検索、prefix 検索、provider 無指定検索、別 provider へのフォールバックは行いません。

UAG は既存の OpenAI 互換 Chat Completions / Responses transport を利用します。どのモデル依存機能を使えるかは、上記の exact な llmcapa Capability で判断します。特に Responses は `UAGENT_RESPONSES=1` が指定されていても `responses_api=True` が必要で、function calling / tools も明示的な対応情報がある場合だけ使用します。false または unknown の場合は推測で有効化しません。

Foundry SDK の直接利用が必要になった場合は、後で別機能として追加できます。
