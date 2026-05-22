# LLMエージェントの会話ループに入れるべきフック設計

## 目的

`batch_state` のような状態管理ツールを用意しても、LLMに反復制御を自由に任せると、以下の問題が残る。

- 同じ `current` / `status` / `next` を繰り返す
- `complete_file` を処理前に呼ぶ
- `current_file` 以外のファイルを完了扱いにする
- 「次はこうします」と言い続けて実処理しない
- 処理済みファイルを再処理する
- `update` / `reset` / `delete` など危険な操作を誤って呼ぶ
- ツールの順序をLLMが途中で間違える

そのため、ツール自体だけでなく、**LLMの会話ループ外側に制御フックを入れる**必要がある。

```text
LLMに反復制御を任せない。
LLMには現在の1件だけ処理させる。
状態遷移・進行判定・完了判定はコード側で行う。
```

______________________________________________________________________

## 推奨アーキテクチャ

### 基本構成

```text
Agent Loop
  ├─ before_llm_call
  ├─ LLM call
  ├─ after_llm_response
  ├─ before_tool_call
  ├─ Tool execution
  └─ after_tool_call
```

より安定させる場合は、LLMに `batch_state` を直接触らせず、外側ループが `current` と `complete_file` を管理する。

```text
Outer Loop
  ↓
batch_state.current
  ↓
LLM: current_file だけ処理
  ↓
Verifier
  ↓
batch_state.complete_file / skip_file / error_file
```

______________________________________________________________________

## フック一覧

## 1. before_llm_call

LLM呼び出し前に、現在状態を取得し、LLMに渡す入力を制限する。

### 役割

- `batch_state.current` を取得する
- `current_file` をプロンプトへ注入する
- `pending_count == 0` ならLLMを呼ばず終了する
- 使用可能なツールを現在状態に応じて制限する
- 連続呼び出し回数やループ兆候を事前チェックする
- LLMに「現在ファイル以外は処理禁止」と明示する

### 入力例

```json
{
  "batch_id": "batch-20260521-001",
  "current_file": "input/a.txt",
  "current_target": 0,
  "pending_count": 12,
  "allowed_tools": [
    "process_current_file"
  ],
  "forbidden_tools": [
    "batch_state.update",
    "batch_state.reset",
    "batch_state.delete",
    "batch_state.list"
  ]
}
```

### プロンプト方針

LLMには未来予定を語らせず、現在ファイルの処理だけを要求する。

悪い指示：

```text
次に何をすべきか考えてください。
```

良い指示：

```text
current_file で指定された1ファイルだけを処理してください。
他のファイル、次のファイル、全体計画には触れないでください。
```

______________________________________________________________________

## 2. after_llm_response

LLM応答直後に、テキスト応答とツール呼び出しを検査する。

### 役割

- tool call があるか確認する
- 「次は〜します」だけの応答を検出する
- 同じ文章の繰り返しを検出する
- 禁止ツールを呼ぼうとしていないか確認する
- 必須出力形式を満たしているか確認する
- 処理結果が空でないか確認する

### 検出すべき危険パターン

```text
次は〇〇します
これから〇〇します
続いて〇〇します
まず〇〇します
I will ...
Next I will ...
```

これらだけで終わっている応答は、実処理していない可能性が高い。

### 対応

1回目は再指示してよい。

```text
予定の説明ではなく、current_file の処理結果だけを返してください。
```

2回以上同じパターンならループ扱いにして中断する。

______________________________________________________________________

## 3. before_tool_call

ツール実行前に、LLMが要求したツール呼び出しを検証する。

### 役割

- action が許可されているか確認する
- `file` が `current_file` と一致しているか確認する
- `complete_file` が処理後に呼ばれているか確認する
- `update` / `reset` / `delete` など危険操作を拒否する
- 同じ action の連続呼び出しを制限する
- `batch_id` が現在のものと一致しているか確認する

### 許可する基本アクション

通常のファイル反復処理では、LLMに許可する `batch_state` action は最小限にする。

```text
current
complete_file
skip_file
error_file
status
finalize
```

ただし、より安定させるなら、LLMに `batch_state` を直接呼ばせず、外側ループだけが呼ぶ。

### 原則禁止アクション

通常処理中は以下をLLMに直接使わせない。

```text
next
advance
update
reset
delete
append_log
load
list
```

特に `update` は状態破壊リスクが高いため、管理者用または初期化用に分離する。

______________________________________________________________________

## 4. after_tool_call

ツール実行後に結果を検証し、次の状態を確定する。

### 役割

- tool result の `ok` を確認する
- `pending_count` / `done_count` の変化を確認する
- 完了後に `current_file` が進んだか確認する
- `pending_count == 0` なら finalize する
- 失敗時は retry / skip / error のどれかへ分類する
- 同じ結果が連続していないか確認する

### 成功条件の例

`complete_file` 後は以下を満たすべき。

```text
done_count が1増える
または
completed_files に current_file が入る
または
pending_count が1減る
```

満たさない場合は、状態更新失敗として扱う。

______________________________________________________________________

## 推奨する外側ループ

最も安定する形は、反復そのものをLLMにやらせない構成である。

```python
while True:
    state = batch_state_current(batch_id)

    if state["pending_count"] <= 0:
        batch_state_finalize(batch_id)
        break

    current_file = state["current_file"]

    result = llm_process_one_file(
        batch_id=batch_id,
        current_file=current_file,
        instructions=state["instructions"],
    )

    verified = verify_result(current_file, result)

    if verified.ok:
        batch_state_complete_file(batch_id, current_file, verified.message)
    elif verified.skippable:
        batch_state_skip_file(batch_id, current_file, verified.reason)
    else:
        batch_state_error_file(batch_id, current_file, verified.reason)
```

この構成では、LLMは「1ファイルを処理する関数」として扱う。

______________________________________________________________________

## LLMに直接 `batch_state` を触らせる場合の制約

どうしてもLLMに `batch_state` を呼ばせる場合は、会話ループ側で以下を強制する。

### 1. action allowlist

状態に応じて許可アクションを切り替える。

```json
{
  "phase": "processing",
  "allowed_actions": [
    "complete_file",
    "skip_file",
    "error_file"
  ]
}
```

処理前フェーズでは `complete_file` を許可しない。

```json
{
  "phase": "before_processing",
  "allowed_actions": [
    "current",
    "status"
  ]
}
```

### 2. current_file固定

`complete_file` / `skip_file` / `error_file` の対象は、必ず現在の `current_file` と一致させる。

```python
if tool_name == "batch_state" and action in result_actions:
    if args.get("file") != state["current_file"]:
        reject_tool_call()
```

`file` 省略時に current_file を使う仕様は便利だが、LLMの誤用検出が弱くなる。\
外側ループでは、明示的に `file == current_file` を強制した方がよい。

### 3. 危険アクション拒否

通常処理中は以下を拒否する。

```python
DANGEROUS_ACTIONS = {
    "update",
    "reset",
    "delete",
    "append_log",
    "list",
    "load",
}
```

`update` は特に危険。\
`targets`, `current_target`, `current_file`, `done_files` をLLMが変更できると、順番崩壊の原因になる。

### 4. `next` と `advance` を使わせない

`next` は `current` と意味が重複しやすい。\
`advance` は `complete_file` と意味が重複しやすい。

LLMには似た選択肢を与えない。

推奨：

```text
current
complete_file
skip_file
error_file
```

非推奨：

```text
next
advance
```

______________________________________________________________________

## ループ検出

会話ループ側で、以下を検出して停止または再指示する。

## 1. 同一action連続

```python
if same_action_count >= 3:
    stop_as_loop()
```

特に危険な連続呼び出し：

```text
current → current → current
status → status → status
next → next → next
```

## 2. 同一応答文連続

```python
if normalize(response_text) == normalize(previous_response_text):
    repeated_text_count += 1
```

2回以上で再指示、3回以上で停止。

## 3. 状態変化なし

ツール呼び出し後に以下が変わらない場合は危険。

```text
current_file
done_count
pending_count
completed_files
skipped_files
error_files
```

同じ状態が続く場合は、LLMが前進していない。

## 4. 未来宣言のみ

以下のような応答だけで、実処理結果がない場合は再指示する。

```text
次はこのファイルを処理します。
処理を開始します。
まず内容を確認します。
```

______________________________________________________________________

## 推奨するレスポンス形式

LLMの出力は、自由文ではなく構造化する。

### 成功

```json
{
  "status": "success",
  "file": "input/a.txt",
  "summary": "処理内容の要約",
  "artifacts": [
    "output/a.txt"
  ]
}
```

### スキップ

```json
{
  "status": "skip",
  "file": "input/a.txt",
  "reason": "対象条件に一致しない"
}
```

### エラー

```json
{
  "status": "error",
  "file": "input/a.txt",
  "reason": "入力ファイルを読み込めなかった"
}
```

### 禁止したい形式

```text
次に output/a.txt を作成します。
```

これは「予定」であって「結果」ではない。

______________________________________________________________________

## Verifierを必ず入れる

LLMの自己申告だけで `complete_file` しない。

### 検証例

- 出力ファイルが存在する
- 出力ファイルサイズが0ではない
- JSONが妥当
- Markdownの必須見出しがある
- 変換後ファイル数が期待値と一致する
- エラー文字列が含まれていない

### 例

```python
def verify_result(current_file: str, result: dict) -> VerifyResult:
    if result.get("status") != "success":
        return VerifyResult.error(result.get("reason", "unknown error"))

    for path in result.get("artifacts", []):
        if not os.path.exists(path):
            return VerifyResult.error(f"artifact not found: {path}")
        if os.path.getsize(path) == 0:
            return VerifyResult.error(f"artifact is empty: {path}")

    return VerifyResult.ok("verified")
```

______________________________________________________________________

## 状態遷移モデル

### 推奨状態

```text
IDLE
  ↓
BATCH_ACTIVE
  ↓
FILE_ASSIGNED
  ↓
FILE_PROCESSING
  ↓
FILE_VERIFYING
  ↓
FILE_COMPLETED / FILE_SKIPPED / FILE_ERROR
  ↓
BATCH_ACTIVE
  ↓
BATCH_DONE
```

### LLMが担当する範囲

```text
FILE_PROCESSING
```

のみ。

### コード側が担当する範囲

```text
IDLE
BATCH_ACTIVE
FILE_ASSIGNED
FILE_VERIFYING
FILE_COMPLETED
FILE_SKIPPED
FILE_ERROR
BATCH_DONE
```

______________________________________________________________________

## `batch_state` 側に追加するとよい項目

会話ループ側の検証をしやすくするため、`batch_state.current` の戻り値に以下を追加するとよい。

```json
{
  "lease_id": "uuid",
  "assigned_at": "2026-05-21T08:00:00Z",
  "allowed_result_actions": [
    "complete_file",
    "skip_file",
    "error_file"
  ],
  "must_process_file_first": true,
  "current_file_locked": true
}
```

### lease_id

`current_file` を取得したときに発行する処理権限ID。

`complete_file` 時に同じ `lease_id` を要求すると、古い応答や順序違いを拒否できる。

```python
if args["lease_id"] != state["current_lease_id"]:
    reject_stale_completion()
```

### current_file_locked

現在ファイル以外の完了処理を拒否するための明示フラグ。

### allowed_result_actions

LLMまたは外側ループに、次に許可される状態遷移だけを示す。

______________________________________________________________________

## 推奨する最終設計

最も安全な設計は以下。

```text
1. batch_state は永続状態の source of truth
2. 外側ループが current を取得する
3. LLMには current_file だけ渡す
4. LLMは処理結果JSONだけ返す
5. 外側ループが verify する
6. 外側ループが complete_file / skip_file / error_file を呼ぶ
7. pending_count == 0 で finalize
```

LLMに渡す権限は最小化する。

```text
LLMに与えるもの:
  - current_file
  - instructions
  - 必要な読み書きツール

LLMに与えないもの:
  - batch_state.update
  - batch_state.reset
  - batch_state.delete
  - next file の選択権
  - current_target の変更権
  - 完了判定の最終権限
```

______________________________________________________________________

## 実装優先順位

### 優先度A

まず入れるべきもの。

- `before_tool_call` で action allowlist
- `file == current_file` チェック
- `update/reset/delete/list/load/append_log` の禁止
- 同一action 3回連続の停止
- 「次は〜します」だけの応答を再指示
- `complete_file` 後の `pending_count` 変化チェック

### 優先度B

次に入れるもの。

- Verifierノード
- LLM出力JSONスキーマ固定
- `next` / `advance` の非公開化
- 外側ループによる `current` / `complete_file` 管理

### 優先度C

さらに堅牢化するもの。

- `lease_id`
- checkpoint / replay
- event sourcing
- retry budget
- per-file timeout
- batch pause / resume
- stale tool call rejection

______________________________________________________________________

## 結論

`batch_state` のような状態管理ツールは有効だが、それだけでは不十分である。\
LLMの会話ループに制御フックを入れ、LLMの自由度を以下の範囲まで狭めるべき。

```text
LLMは現在の1件を処理するだけ。
順番、進行、完了、検証、終了判定はコード側で行う。
```

この設計にすると、長期バッチ処理で起きやすい以下の問題を大きく減らせる。

- 順番間違い
- next/status/current の無限ループ
- 「次は〜します」の繰り返し
- 処理前complete
- 状態破壊
- 再処理
- 完了判定ミス
