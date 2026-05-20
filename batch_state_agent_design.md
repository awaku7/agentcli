# LLMエージェント向けバッチ状態管理ツール設計指針

## 目的

LLMエージェントが複数ファイル・複数ステップの繰り返し処理を行うときに、途中で順番を間違えたり、同じ処理を繰り返したり、「次はこうします」と言うだけで進まなくなる問題を防ぐ。

基本方針は次の通り。

```text
LLMに順番を記憶させない
LLMに次の状態を自由に決めさせない
進行状態はコード側で永続化する
LLMは現在の1件だけを処理する
```

---

## 現状実装の良い点

現在の `batch_state` ツールは、バッチ状態を `~/.uag/batches/` 配下にJSONとして永続化しており、LLMの会話履歴だけに進行状態を依存していない。

これは正しい方向。

特に良い点は次の通り。

- `targets`
- `current_target`
- `next_index`
- `completed_files`
- `skipped_files`
- `error_files`
- `pending_files`
- `current_file`

を持っており、「どこまで処理したか」をコード側で復元できる。

また、`complete_file` / `skip_file` / `error_file` のように、ファイル単位の結果を明示的に記録できる点も良い。

---

## 現状の問題点

### 1. LLMに見えるアクションが多すぎる

現在のアクションは次のようになっている。

```text
init
load
status
current
next
advance
complete_file
skip_file
error_file
update
reset
append_log
finalize
list
delete
```

これは管理者向けには便利だが、LLM実行時には選択肢が多すぎる。

LLMは似た意味のアクションがあると迷いやすい。

特に次の組み合わせは混乱を起こしやすい。

```text
current / next
advance / complete_file
load / status / current
update / complete_file
finalize / status
```

---

### 2. `next` が状態を進めない

現状では `current` と `next` が同じ動作になっている。

```python
if action in {"current", "next"}:
```

この場合、LLMは `next` を呼べば進むと誤解しやすい。

しかし実際には状態は進まないため、同じファイルを何度も取得する可能性がある。

---

### 3. `advance` と `complete_file` が同じ意味

現状では次のように処理されている。

```python
"advance": "completed_files",
"complete_file": "completed_files",
```

これはLLMにとって曖昧。

「処理が完了した」という意味なら `complete_file` に統一する方がよい。

---

### 4. `update` が強すぎる

`update` は `targets` や `current_target` を書き換えられる。

これは管理者操作としては必要だが、LLMが通常処理中に使うと危険。

たとえば、LLMが途中で `targets` を再生成したり、`current_target` を巻き戻したりすると、順序崩壊や重複処理が起きる。

---

### 5. `recommended_next_action` が「処理前のadvance」を誘発する可能性がある

現状では次のような情報を返している。

```json
{
  "action": "advance",
  "after": "processing current_file"
}
```

人間には分かりやすいが、LLMは `action=advance` の方に引っ張られて、処理前に `advance` してしまうことがある。

---

## 推奨設計

### LLMに公開するアクションを最小化する

LLMに通常公開するアクションは次だけにする。

```text
init
current
complete_file
skip_file
error_file
status
finalize
```

さらに安定させるなら、処理中は次の4つだけでよい。

```text
current
complete_file
skip_file
error_file
```

---

## アクションの役割

### init

バッチを開始する。

- `targets` を登録する
- `task_description` を登録する
- `instructions` を登録する
- `current_target = 0`
- 各 `target.next_index = 0`

初期化後、原則として `targets` は変更しない。

---

### current

現在処理すべき1件だけを返す。

このアクションは状態を進めない。

返す情報は最小限でよい。

```json
{
  "ok": true,
  "batch_id": "batch-xxx",
  "current_file": "path/to/file.txt",
  "current_target": 0,
  "pending_count": 10,
  "done_count": 3,
  "allowed_after_processing": [
    "complete_file",
    "skip_file",
    "error_file"
  ]
}
```

重要なのは、「次の予定」ではなく「今処理すべき対象」を返すこと。

---

### complete_file

現在のファイルを成功として記録する。

```json
{
  "action": "complete_file",
  "batch_id": "batch-xxx",
  "file": "path/to/file.txt"
}
```

`file` が省略された場合は `current_file` を対象にしてよい。

処理内容は次の通り。

- `completed_files` に追加
- `skipped_files` / `error_files` からは削除
- `next_index` を次の未処理ファイルまで進める
- 未処理がなければ `status=done` にする

---

### skip_file

現在のファイルをスキップとして記録する。

```json
{
  "action": "skip_file",
  "batch_id": "batch-xxx",
  "file": "path/to/file.txt",
  "reason": "対象外"
}
```

---

### error_file

現在のファイルをエラーとして記録する。

```json
{
  "action": "error_file",
  "batch_id": "batch-xxx",
  "file": "path/to/file.txt",
  "reason": "読み込み失敗"
}
```

エラーを記録したファイルは、通常は次に進める。

再試行したい場合は別アクションを用意する。

---

### status

人間への確認用。

LLMの通常ループでは毎回使わせない。

---

### finalize

全件完了後にバッチを終了する。

通常は `pending_count == 0` になったらツール側で自動的に `done` にしてよい。

LLMに `finalize` を呼ばせる必要は必ずしもない。

---

## 廃止・非公開にした方がよいアクション

### next

廃止推奨。

理由は、`current` と意味が重複し、状態が進むように見えるため。

代替は `current`。

---

### advance

廃止推奨。

理由は、`complete_file` と意味が重複するため。

代替は `complete_file`。

---

### update

LLM通常処理からは非公開推奨。

管理者用または内部用に分離する。

---

### reset

LLM通常処理からは非公開推奨。

誤って呼ばれると進捗が消える。

---

### delete

LLM通常処理からは非公開推奨。

誤って呼ばれると状態ファイルが消える。

---

### append_log

LLM通常処理からは非公開推奨。

ログは `complete_file` / `skip_file` / `error_file` 側で自動記録する方がよい。

---

### load / list

人間・管理者向け。

LLM実行時には `current` と `status` だけで足りる。

---

## 推奨ステートマシン

```text
[INIT]
   ↓
[CURRENT]
   ↓
[LLMが current_file を処理]
   ↓
┌───────────────────────┐
│ complete_file          │
│ skip_file              │
│ error_file             │
└───────────────────────┘
   ↓
[pending_count > 0 ?]
   ├─ yes → CURRENT
   └─ no  → DONE
```

LLMに自由な遷移を許さない。

---

## ツール戻り値の設計

### current の戻り値

`recommended_next_action` よりも、許可される操作を明示する。

悪い例。

```json
{
  "recommended_next_action": {
    "action": "advance",
    "after": "processing current_file"
  }
}
```

良い例。

```json
{
  "current_file": "a.txt",
  "must_process_current_file_first": true,
  "allowed_after_processing": [
    "complete_file",
    "skip_file",
    "error_file"
  ]
}
```

---

## system prompt の設計

LLMには次のルールを強く与える。

```text
You must process exactly one current_file at a time.
Do not call complete_file, skip_file, or error_file before actually processing current_file.
Do not call update, reset, delete, list, next, or advance during normal execution.
After processing current_file, call exactly one of complete_file, skip_file, or error_file.
Do not describe future steps. Execute the current step only.
```

日本語なら次のようにする。

```text
常に current_file を1件だけ処理する。
処理前に complete_file / skip_file / error_file を呼ばない。
通常処理中に update / reset / delete / list / next / advance を呼ばない。
current_file を処理した後、complete_file / skip_file / error_file のいずれか1つだけを呼ぶ。
「次は〜します」と予定を述べ続けず、現在の1件だけを実行する。
```

---

## 実装方針

### 1. LLM向けTOOL_SPECと管理者向けTOOL_SPECを分ける

現在の `TOOL_SPEC` は全部入りになっている。

これを分離する。

```text
batch_state_user_tool
batch_state_admin_tool
```

または、同じ `run_tool` を使いつつ、LLMに見せる schema だけを制限する。

LLM向け。

```text
init
current
complete_file
skip_file
error_file
status
```

管理者向け。

```text
list
load
update
reset
delete
finalize
append_log
```

---

### 2. `next` を削除または非公開

後方互換が必要なら内部では残してもよい。

ただし、TOOL_SPECからは外す。

---

### 3. `advance` を削除または非公開

後方互換が必要なら `complete_file` の別名として内部に残してもよい。

ただし、TOOL_SPECからは外す。

---

### 4. `update` を通常実行ループから外す

`update` はバッチ作成後の修正や管理者操作だけに使う。

LLMが処理中に `targets` や `current_target` を書き換えられないようにする。

---

### 5. `current` の戻り値を短くする

LLMに大量の状態を返すと、余計な推論や誤判断を誘発する。

通常ループ用の `current` は短くする。

例。

```json
{
  "ok": true,
  "batch_id": "batch-xxx",
  "status": "active",
  "current_file": "dir/file.txt",
  "pending_count": 8,
  "done_count": 2,
  "total_count": 10,
  "allowed_after_processing": [
    "complete_file",
    "skip_file",
    "error_file"
  ]
}
```

詳細状態は `status` で見る。

---

### 6. 同一ファイルの二重完了を防ぐ

`complete_file` を同じファイルに対して再度呼んだ場合は、成功扱いにしてもよいが、状態は変えない。

戻り値に `already_recorded: true` を入れるとよい。

```json
{
  "ok": true,
  "already_recorded": true,
  "file": "dir/file.txt"
}
```

---

### 7. 処理対象の予約機構を検討する

複数エージェントや並列処理をする場合は、`current` だけでは不十分。

その場合は次の状態を追加する。

```text
leased_files
lease_id
lease_expires_at
```

ただし、単一LLMの直列処理なら不要。

---

## 推奨する最終アクション一覧

### LLM実行用

```text
init
current
complete_file
skip_file
error_file
status
```

### 管理者用

```text
list
load
update
reset
delete
append_log
finalize
```

### 廃止または後方互換用

```text
next
advance
```

---

## 推奨ループ

LLMエージェント側の実行ループは次のようにする。

```python
while True:
    state = batch_state({"action": "current", "batch_id": batch_id})

    if not state["current_file"]:
        break

    try:
        process_file(state["current_file"])
        batch_state({
            "action": "complete_file",
            "batch_id": batch_id,
            "file": state["current_file"]
        })
    except Skipped as e:
        batch_state({
            "action": "skip_file",
            "batch_id": batch_id,
            "file": state["current_file"],
            "reason": str(e)
        })
    except Exception as e:
        batch_state({
            "action": "error_file",
            "batch_id": batch_id,
            "file": state["current_file"],
            "reason": repr(e)
        })
```

重要なのは、ループ制御はコード側が持つこと。

LLMに「次に何をするか」を自由に決めさせない。

---

## LLMに任せてよいこと・任せないこと

### LLMに任せてよいこと

- 現在の1ファイルの内容理解
- 現在の1ファイルに対する変換
- 現在の1ファイルの処理結果の説明
- 成功・スキップ・エラーの理由文生成

### LLMに任せないこと

- 次にどのファイルを処理するか
- 何件目まで終わったか
- `targets` の再構築
- `current_target` の変更
- 全体ループの継続判定
- リトライ回数の管理
- 完了判定

---

## まとめ

現在の実装は、状態を永続化している点で正しい。

ただし、LLMに見せる操作が多く、似た意味のアクションがあるため、長時間実行時に迷いやすい。

最も効果が高い改善は次の3つ。

```text
1. LLMに見せるアクションを減らす
2. next と advance を非公開または廃止する
3. update / reset / delete を通常処理から外す
```

最終的には次の形にする。

```text
LLMは current_file を1件だけ処理する
処理後に complete_file / skip_file / error_file のどれかを呼ぶ
次の対象選択と進捗管理はツール側が行う
```

この形にすると、LLMが順番を間違える、同じことを繰り返す、「次はこうします」だけで止まる、といった問題をかなり抑えられる。
