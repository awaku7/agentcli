# vLLM プロバイダー

UAGは、起動済みのvLLM OpenAI互換サーバーを**Responses API**または**Chat Completions**経由で利用できます。自動判定ではllmcapaが設定モデルのResponses API対応を確認した場合にのみResponsesを選びます。`UAGENT_RESPONSES=0`でChat Completionsに固定できます。UAG自身がvLLMの起動、モデルのダウンロード、サーバープロセスの管理を行うことはありません。

## UAGの設定

```dotenv
UAGENT_PROVIDER=vllm
UAGENT_VLLM_BASE_URL=http://localhost:8000/v1
UAGENT_VLLM_DEPNAME=local-model
# vLLMサーバーを--api-key付きで起動した場合のみ設定します（省略可）。
# UAGENT_VLLM_API_KEY=change-me
# 省略可。既定値は120秒です。
# UAGENT_VLLM_TIMEOUT_SEC=120
```

`UAGENT_VLLM_DEPNAME`は必須で、サーバーの`/v1/models`が返すモデルIDと完全一致させてください。サーバー起動時に`--served-model-name`を指定した場合は、同じ値を設定します。Base URLの既定値は`http://localhost:8000/v1`です。APIキーは省略できます。未設定時はOpenAI互換クライアント用のプレースホルダー`dummy`を送信します。`UAGENT_VLLM_API_KEY`を優先し、標準の`VLLM_API_KEY`も利用できます。

UAGは`/v1/models`から該当モデルの`max_model_len`を取得し、カタログ値より優先して実効コンテキスト上限として使います。サーバーが`max_input_tokens`と`max_output_tokens`を別々に返す場合は、入力上限をコンテキスト予算に使い、出力上限で生成トークン数をクランプします。接続できない場合やこれらのフィールドがない場合はllmcapaの値にフォールバックします。メタデータ取得のタイムアウトは既定で5秒です。`UAGENT_VLLM_PROPS_TIMEOUT_SEC`で変更できます。

`previous_response_id`による継続は、実際の会話の次ターンでサーバーに問い合わせて確認します。サーバーが受け付ければ利用し、拒否された場合（例: vLLMのResponses storeが無効）は会話履歴全体を付けて再試行し、その結果をUAGプロセス終了まで記憶します。vLLM側では`VLLM_ENABLE_RESPONSES_API_STORE=1`でstoreを有効化できますが、保存された応答はメモリ上に保持されるため、利用前に考慮してください。Visionはこのプロバイダーアダプターでは利用できません。構造化出力はllmcapaのモデル別情報で判定し、vLLMサーバーとモデル側の対応も必要です。ツール呼び出しにはモデル側の対応に加え、vLLMサーバーをモデルに合ったtool-call parser付きで起動する必要があります。例: `--enable-auto-tool-choice --tool-call-parser <モデル用parser>`。

## 推論強度の安全な指定

`UAGENT_REASONING`で推論強度を指定できますが、vLLMで利用できる値はモデルによって異なります。UAGは、**llmcapaのvLLM専用モデル情報で`supports_reasoning_effort=true`が明示され、`reasoning_effort_values`に指定値が登録されている場合だけ**、Chat Completionsの`reasoning_effort`またはResponsesの`reasoning.effort`を送信します。他Providerのモデル情報やllmcapaの一般的な既定値は、vLLM対応の根拠として使用しません。

明示指定した値の対応を確認できない場合は、誤った値を送信せず、実行時警告を表示してパラメーターを省略します。`UAGENT_REASONING=off`も同様で、`none`への対応が確認されているモデルに限り送信します。未確認の場合、推論のON/OFFはサーバー・モデル側の既定動作に従います。`auto`では未確認の強度指定を省略し、警告は出しません。

数値で上限を指定する`thinking_token_budget`は推論強度とは別の機能で、effortから自動計算しません。明示的なbudget指定は`UAGENT_REASONING`より優先し、推論強度のパラメーターは同時送信しません。

## vLLMの起動

vLLMサーバーは別途起動してください。例:

```sh
vllm serve <model> --host 127.0.0.1 --port 8000 --served-model-name local-model
```

この場合は`UAGENT_VLLM_DEPNAME=local-model`を設定します。サーバーをloopback以外に公開する場合は、APIキーと適切なネットワーク制御で保護してください。UAGのAPIキー設定はクライアント認証用であり、サーバーのネットワーク公開自体を保護するものではありません。

## 数値による推論トークン予算

`UAGENT_VLLM_THINKING_TOKEN_BUDGET`に正の整数を指定すると、vLLMのChat Completionsで推論トークン数の上限を指定できます。明示的なbudget指定を`UAGENT_REASONING`（`high`、`off`、`auto`等）より優先し、`reasoning_effort`は同時送信しません。budget未指定時の推論強度処理は従来どおりです。生成全体の`max_tokens`上限も変更しません。

```dotenv
UAGENT_VLLM_THINKING_TOKEN_BUDGET=4096
# 必要ならChat Completionsに明示的に固定します。
UAGENT_RESPONSES=0
```

予算を指定すると自動トランスポート選択はChat Completionsを優先します。`UAGENT_RESPONSES=1`を明示した場合はエラーになります。vLLMのResponses API経由でこの拡張値を利用できることが未検証のためです。不正な値や0以下の値もエラーになります。

**llmcapaのvLLM専用モデル情報**に数値制御`thinking_token_budget`の対応が明示されている場合に限り送信します。未確認のモデルには黙って送信しません。サーバーが公開するモデル名がllmcapaの該当するvLLMモデルIDとして解決できる必要があります。llmcapa側の検証済みデータがリリース・インストールされるまでは、対応モデルでも未確認と判定されることがあります。

vLLMはモデルに合ったreasoning parser（該当するQwen3モデルとサーバーの組合せでは例として`--reasoning-parser qwen3`）を設定して起動してください。使用するvLLMのバージョン、parser、モデルにも予算制御の対応が必要です。
