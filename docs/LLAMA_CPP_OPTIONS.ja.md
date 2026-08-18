# llama.cpp APIオプション

対象サーバー：

```text
http://aispace.sbc.nttdata-sbc.co.jp/v1
```

確認したビルド情報：

```text
llama-server 0.6.0
build_info: b9837-b3fed31b9
llama.cpp commit: b3fed31b99f9bd37725833674252bccb429bb183
```

## uagentからの実効デフォルト

uagent経由の通常の`/v1/chat/completions`では、以下の値が使われます。

| オプション | 実効デフォルト | 意味 |
|---|---:|---|
| `temperature` | `0.2` | 出力のランダム性。低いほど決定的で、ツール呼び出しが安定しやすい |
| `top_p` | サーバー既定の`0.95` | 累積確率がこの値に達するまでの候補だけを使う |
| `max_tokens` | サーバー／モデル既定 | 生成する最大トークン数 |
| `reasoning` | サーバー／モデル既定 | 思考・推論を有効にするかどうか |
| `parallel_tool_calls` | ツール使用時`true` | 複数のツール呼び出しを1回の応答で許可する |

`UAGENT_TEMPERATURE`、`UAGENT_TOP_P`、`UAGENT_MAX_TOKENS`が設定されている場合は、uagentの設定値が優先されます。

## Reasoning関連

| オプション | デフォルト | 意味 |
|---|---:|---|
| `UAGENT_REASONING=off` | 未指定 | llama.cppへ`chat_template_kwargs.enable_thinking=false`を送信し、thinkingを無効化 |
| `UAGENT_REASONING=auto` | 未指定 | llama.cppへ指定せず、モデル／chat templateの既定値に任せる |
| `UAGENT_REASONING=minimal/low/medium/high/xhigh/max` | 未指定 | `enable_thinking=true`を送信。値そのものはQwenのtemplateには渡さない |
| `reasoning_format` | `deepseek`（uagent経由） | reasoningの抽出形式。`none`は生の出力として扱い、`deepseek`では`reasoning_content`へ分離する |
| `reasoning_control` | `false` | ストリーミング中にreasoningブロックを終了できるようにする |
| `chat_template_kwargs` | `{}` | chat templateへ渡す追加パラメータ。Qwen系では`enable_thinking`等を指定する |

例：

```json
{
  "chat_template_kwargs": {
    "enable_thinking": false
  }
}
```

## サンプリング

| オプション | llama-server既定値 | 意味 |
|---|---:|---|
| `temperature` | `0.8`（uagent経由は`0.2`） | 出力のランダム性。高いほど多様、低いほど安定 |
| `top_k` | `40`（対象のQwenでは`20`） | 確率上位K個のトークンに候補を制限 |
| `top_p` | `0.95` | 累積確率による候補制限 |
| `min_p` | `0.05` | 最有力トークンに対する相対確率が低すぎる候補を除外 |
| `top_n_sigma` | `-1` | σベースの候補制限。負値は無効 |
| `typical_p` | `1.0` | Typical Sampling。`1.0`は無効 |
| `repeat_penalty` | `1.0` | 既出トークン列への繰り返しペナルティ。`1.0`は無効 |
| `repeat_last_n` | `64` | 繰り返し判定に使う直近トークン数。`0`は無効、`-1`はコンテキスト長 |
| `presence_penalty` | `0.0` | 一度出現したトークンへのペナルティ |
| `frequency_penalty` | `0.0` | 出現回数に応じたペナルティ |
| `seed` | `-1` | 乱数種。`-1`はランダム |
| `ignore_eos` | `false` | EOSトークンを無視して生成を続ける |

## DRY / XTC / Mirostat

| オプション | デフォルト値 | 意味 |
|---|---:|---|
| `dry_multiplier` | `0.0` | DRY繰り返し抑制の強さ。`0.0`は無効 |
| `dry_base` | `1.75` | DRYペナルティの指数基数 |
| `dry_allowed_length` | `2` | この長さを超える繰り返しにDRYペナルティを適用 |
| `dry_penalty_last_n` | `-1` | DRY判定範囲。`-1`はコンテキスト全体、`0`は無効 |
| `dry_sequence_breakers` | `[`<br>`"\\n", ":", "\\\"", "*"`<br>`]` | DRYの繰り返し区切り文字 |
| `xtc_probability` | `0.0` | XTCで候補を除去する確率。`0.0`は無効 |
| `xtc_threshold` | `0.1` | XTC対象とする最小確率 |
| `mirostat` | `0` | Mirostat。`0`無効、`1` Mirostat、`2` Mirostat 2.0 |
| `mirostat_tau` | `5.0` | Mirostatが目標とするエントロピー |
| `mirostat_eta` | `0.1` | Mirostatの学習率 |

## 生成・キャッシュ

| オプション | デフォルト値 | 意味 |
|---|---:|---|
| `max_tokens` | `-1` | OpenAI互換の最大生成トークン数。`-1`は無制限 |
| `n_predict` | `-1` | llama.cpp独自の最大生成トークン数 |
| `n_keep` | `0` | コンテキストシフト時に保持するプロンプトトークン数 |
| `n_discard` | `0` | コンテキストシフト時に破棄するトークン数。`0`は自動計算 |
| `stop` | `[]` | 指定文字列の出現時に生成を停止 |
| `stream` | `true`（サーバー既定） | ストリーミング応答を有効化 |
| `cache_prompt` | `true` | 共通プロンプトのKVキャッシュを再利用 |
| `n_cache_reuse` | `0` | KVキャッシュ再利用の最小チャンクサイズ。`0`は無効 |
| `id_slot` | `-1` | 使用するサーバースロット。`-1`は自動選択 |
| `t_max_predict_ms` | `0` | 生成時間上限（ms）。`0`は無制限 |

## 出力制約・確率情報

| オプション | デフォルト値 | 意味 |
|---|---:|---|
| `grammar` | 未指定 | BNF形式の文法で出力を制約 |
| `json_schema` | 未指定 | JSON Schemaで出力を制約 |
| `response_format` | 未指定 | OpenAI互換のJSON／JSON Schema出力指定 |
| `logit_bias` | `[]` | 特定トークンの出現確率を増減 |
| `n_probs` | `0` | 各生成トークンの上位確率候補数。`0`は無効 |
| `min_keep` | `0` | サンプラーが最低限保持する候補数 |
| `return_tokens` | `false` | 生のトークンIDをレスポンスに含める |
| `timings_per_token` | `false` | トークンごとの処理時間を含める |
| `post_sampling_probs` | `false` | サンプリング後の確率を返す |
| `response_fields` | 未指定 | レスポンスに含めるフィールドを限定 |

## ツール呼び出し

| オプション | デフォルト値 | 意味 |
|---|---:|---|
| `tools` | 未指定 | モデルへ関数定義を渡す |
| `tool_choice` | `auto`（uagent） | ツールを自動選択。`none`等も指定可能 |
| `parallel_tool_calls` | `true`（uagentのllama.cpp） | 1回の応答で複数ツールを呼び出す |
| `parse_tool_calls` | サーバー既定 | 生成されたテキストからツール呼び出しを解析 |

uagent側では、並列指定されても安全性を確認します。読み取り専用・並列安全なツールだけが並列実行され、書き込みや破壊的操作は逐次実行されます。

## マルチモーダル

対象サーバーの`qwen3.6:35b`では、`/props`で以下を確認しています。

| モダリティ | 対応 |
|---|---|
| Vision | 対応 |
| Video | 対応 |
| Audio | 非対応 |

画像・動画の利用可否はモデルとmmprojの構成に依存します。全llama.cppモデルに共通とは限りません。

## 直接APIとuagentの差

上記は、llama.cppビルドで利用可能なAPIオプションと、uagentが意味を理解している項目をまとめたものです。

現在、uagentから明示的に設定できる主な環境変数は次のとおりです。

```text
UAGENT_REASONING
UAGENT_TEMPERATURE
UAGENT_TOP_P
UAGENT_MAX_TOKENS
```

`top_k`、`min_p`、`mirostat`、`dry_*`などはllama-server APIでは利用できますが、uagentの専用環境変数としてはまだ公開していません。

## 参照

- [llama.cpp server README](https://github.com/ggml-org/llama.cpp/blob/b3fed31b99f9bd37725833674252bccb429bb183/tools/server/README.md)
- [llama.cpp commit b3fed31b9](https://github.com/ggml-org/llama.cpp/commit/b3fed31b99f9bd37725833674252bccb429bb183)
