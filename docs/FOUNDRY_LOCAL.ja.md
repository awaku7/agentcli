# Microsoft Foundry Local

UAG では Foundry Local を、通常のローカル OpenAI 互換 Chat Completions エンドポイントとして扱います。

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

この検索で見つからない場合、別の llmcapa プロバイダにはフォールバックしません。現在の Foundry Local は既存の OpenAI 互換 Chat Completions transport を利用します。Foundry SDK 直接対応が必要になった場合は、後で別途追加できます。
