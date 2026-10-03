# :auto — 自動マルチラウンド実行コマンド

`:auto` は、uag に**目標を繰り返し実行させる**コマンドです。
1回のメッセージでは足りない長期的な分析・編集・調査などに使います。

______________________________________________________________________

## 基本の使い方

```
:auto <目標> [--max-rounds N|INFINITE]
:auto <目標> --infinite
:auto INFINITE <目標>
```

例:

```
:auto README.mdを日本語に翻訳して
:auto プロジェクトのコードを全体的に分析して
:auto バグの原因を調査して修正する --max-rounds 20
```

______________________________________________________________________

## 何が起こるか

`:auto` を実行すると、以下のループが回ります:

```
Round 1: 目標に向けてLLMを実行 → LLMが応答・ツール実行
         ↓
        レビューアが「目標達成した？」を判定
         ↓ "まだ" なら続行

Round 2: 「続けて」→ LLM実行 → レビューア判定
         ↓ "まだ"

Round 3: ... (以下繰り返し)
```

各ラウンドは2ステップで構成されます:

| ステップ | 役割 |
|---|---|
| **Step A** (メインクエリ) | 目標達成に向けて LLM に続きを実行させる |
| **Step B** (レビューア判定) | 別コンテキストで LLM に「COMPLETE or CONTINUE?」と判定させる |

### Decision Providerをレビューアに使う（任意）

既定値は `UAGENT_DECISION_PROVIDER=none` で、従来どおりLLMレビューアを
使用します。

`UAGENT_DECISION_PROVIDER=typesafe`、`openrouter`、または `laya` を明示的に選択すると、
Step BではまずDecision Providerに型付きの完了判定を依頼します。
TypeSafe/JevとOpenRouter/Jevは、1回のリクエストで `goal_satisfied` と
`material_work_remaining` の2つのboolean/noul質問を使います。UAGはそれぞれ
true/falseの場合だけ `COMPLETE` とします。Layaは従来のchoice判定を維持します。completion regexとsentinel modeはDecision Providerより先に評価されます。

Decision Providerの初期化失敗、必要な質問形式への非対応、判定時エラー、不正な応答は
従来のLLMレビューアへフォールバックします。そのため `UAGENT_AP_*` は、
Decision Provider有効時にはフォールバックLLMレビューア設定として機能します。

`uag_setup` では `none` / `typesafe` / `openrouter` / `laya` を選択できます。
OpenRouterでは専用キーが未指定なら既存の `UAGENT_OPENROUTER_API_KEY` を再利用できます。

Decision Providerへ渡す会話・ツール結果は件数と文字数を制限し、secret maskingを
適用します。confidenceは診断ログ用途のみで、完了判定の閾値には使用しません。

Layaにはbinary choiceの順序依存を検出する追加ガードがあります。同じ意味の判定を
`COMPLETE / CONTINUE` と、選択肢を逆順にした `CONTINUE / COMPLETE` の2回実行し、
両方が同じ意味の答えを返した場合だけLaya判定を採用します。結果が食い違った場合は
従来のLLMレビューアへフォールバックします。TypeSafe/JevとOpenRouter Decisionsは
従来どおり1回判定です。

### 初回判定で完了した動作確認例（2026-10-03）

メインモデルを `openai / gpt-6-luna`、判定プロバイダーをOpenRouter/Jevにした
CLI実行で、今日と去年の同じ日の天気を回答後、初回の判定で完了したことを
ユーザー提供ログで確認しました。

```text
[INFO] 判定プロバイダー = openrouter; モデル = ~typesafe/jev-latest
agentcli> :auto 今日の天気と去年の今日の天気を調べる
[AUTO] 開始しました。目的: 今日の天気と去年の今日の天気を調べる
[AUTO] 最大ラウンド数: 10
［2026-10-03と2025-10-03の天気を回答］
[AUTO:judge:decision] provider=openrouter model=typesafe/jev-1.13-20260917 judgment=COMPLETE confidence=0.7100 latency_ms=1531.3
[AUTO] レビュー/分析が完了しました。
```

上の回答部分は実際の天気回答を要約したものです。判定ログは実行ログの値です。
追加の作業ラウンドは発生していません。最大ラウンド数の10は上限であり、
10回の実行を要求する値ではありません。この上限はDecision Providerのstateに
渡しません。起動バナーには設定したモデルの別名、判定ログにはプロバイダーが
返した実際のモデル名を表示します。バナーのラベル・書式は全38言語に対応しています。
confidenceとlatencyはこの1回の観測値であり、完了判定の閾値や性能保証ではありません。

### 3方式の比較用Observability

OpenTelemetryを有効にすると、Auto Pilotは次の3方式を同じメタデータ形式で記録します。

- `llm_reviewer`: 従来の追加LLMレビューア呼び出し
- `decision_provider`: TypeSafe/Jev、OpenRouter Decisions/Jev、またはLaya
- `sentinel`: メインLLM自身の `AUTO_COMPLETE / AUTO_CONTINUE`。追加判定呼び出しなし

`uag.auto.judgment` イベントには、判定方式、`COMPLETE / CONTINUE`、round、
fallback有無、provider/model、latency、利用可能な場合のconfidenceを記録します。
Decision Provider失敗と、その後に実際に採用されたLLM fallback判定は別attemptとして
記録されます。goal、prompt、会話本文、tool本文、レビューア応答本文はTelemetryへ
出力しません。

比較用metricは `uag.auto.judgment.attempts`、`uag.auto.judgments`、
`uag.auto.judgment.failures`、`uag.auto.judgment.latency_ms`、
`uag.auto.runs`、`uag.auto.followup_rounds` です。
`uag.auto.run.finished` では終了理由とmax-round到達有無も記録します。

______________________________________________________________________

## 止め方

`:auto` を止める方法は3つあります:

| 方法 | 説明 |
|---|---|
| **F12キー** | 実行中でも即座に停止。LLM応答待ち中でも割り込めます（推奨） |
| **`COMPLETE` と判定される** | レビューアが「目標達成」と判断したら自動停止 |
| **`--max-rounds N` に到達** | デフォルト10ラウンド。N を指定して変更可能 |

実行前にキャンセルする場合は `:auto off` も使えますが、
動作中の停止には **F12キー** を使ってください。

______________________________________________________________________

## オプション

| オプション | デフォルト | 説明 |
|---|---|---|
| `--max-rounds N` | `10` | 最大ラウンド数。多めに欲しいときは `--max-rounds 30` など |
| `--max-rounds INFINITE` / `--infinite` | 無制限 | レビューアが `COMPLETE` と判定するか、ユーザーが停止するまで継続 |

______________________________________________________________________

## レビューアーに別のLLMを指定する（任意）

デフォルトではレビューアー（Step B）はメインクエリ（Step A）と同じプロバイダ・モデルを使用します。
`UAGENT_AP_` プレフィックスの環境変数で、レビューアーに別のLLMを指定できます。

例：メイン = Claude、レビューアー = OpenAI GPT-4o-mini

```bat
set UAGENT_PROVIDER=claude
set UAGENT_CLAUDE_API_KEY=sk-ant-...
set UAGENT_AP_PROVIDER=openai
set UAGENT_AP_OPENAI_API_KEY=sk-...
set UAGENT_AP_OPENAI_DEPNAME=gpt-4o-mini
```

例：メイン = GPT-4o、レビューアー = Gemini Flash（安価）

```bat
set UAGENT_PROVIDER=openai
set UAGENT_OPENAI_API_KEY=sk-...
set UAGENT_AP_PROVIDER=gemini
set UAGENT_AP_GEMINI_API_KEY=AIza...
set UAGENT_AP_GEMINI_DEPNAME=gemini-2.0-flash
```

仕組み：

- `UAGENT_AP_PROVIDER` にレビューアーに使いたいプロバイダを指定します。
- `UAGENT_AP_*` 変数はレビューアークライアント作成時に `UAGENT_*`（`AP_` 除去）にマッピングされます。
- `UAGENT_AP_PROVIDER` 未設定時は従来通りメインと同じLLMを使用します（デフォルト動作）。
- `make_client()` が対応するすべてのプロバイダが利用可能です。各プロバイダ固有の変数は [ENVIRONMENT.md](ENVIRONMENT.md) を参照してください。

______________________________________________________________________

## 実践的な使い方のコツ

### 目標は具体的に書く

- 良い例: `:auto src/uagent/ 以下の全テストを通るようにリファクタする`
- 悪い例: `:auto 直して`

目標が具体的なほど、レビューアが「COMPLETE」と判定しやすくなります。

### ラウンド数に余裕を持たせる

複雑な作業ほど多くのラウンドが必要です。`--max-rounds 3` だと途中で止まることがあります。
まずはデフォルト（10）で試し、足りなければ増やしてください。

### 他のコマンドと組み合わせる

`:auto` 実行中に F11 で停止し、手動で調整してから再開することもできます。

______________________________________________________________________

## 内部動作（簡略版）

興味がある方向けのアーキテクチャ概要です。

```
CLI: ":auto READMEを翻訳して"
  │
  ├─ _handle_cmd_auto()          # 目標をパース、フラグ設定
  ├─ run_llm_rounds()            # Step A: 最初のLLM実行
  └─ _run_auto_pilot_loop()      # ループ制御
       │
       ├─ run_llm_rounds()        # Step A: 続きのLLM実行
       └─ _ask_reviewer_judgment() # Step B: レビューア判定
            └─ run_llm_rounds(judgment_mode=True)  # 別コンテキストで判定
```

- メインのLLM実行とレビューア判定は **同じプロバイダ・同じAPIパス** を通ります（Responses API 対応含む）
- レビューア判定は **メインの会話履歴を変更しません**（独立したメッセージリストで実行）

______________________________________________________________________

## 注意事項

- `:auto` は LLM API を **各ラウンドで2回**（Step A + Step B）呼び出します。
  ラウンド数が多くなると API コストが増えることに注意してください。
- ツール実行（ファイル読み書きなど）は Step A でのみ行われます。
  レビューア判定（Step B）ではツールは実行されません。
