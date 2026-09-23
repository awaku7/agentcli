# Scheduler instance isolation design

## 目的

複数のUAGプロセスを同じOSユーザーで起動しても、内部タイマーが別インスタンスのイベントキューへ混入したり、同じ期限のタイマーが重複発火したりしないようにする。

`session_id` は会話・履歴の識別子であり、プロセス所有権の識別子として単独では使用しない。

## 識別子

| 識別子 | 意味 | 用途 |
|---|---|---|
| `instance_id` | 起動ごとに生成する暗号学的にランダムなUUID | 内部Schedulerの所有者。再起動時は必ず変わる |
| `session_id` | 既存のUAG会話／Session Store ID | 発火イベントの戻り先。認証・認可には使わない |
| `schedule_id` | タイマー固有ID | 削除、監査、重複排除 |
| `run_id` | 1回の発火処理のID | 実行状態、再試行、監査 |

`instance_id` は表示値・principal ID・secretにしない。`session_id` は所有権や認証の代替にしない。

## タイマーの種類

### Internal timer

- 作成元インスタンスだけが発火対象として扱う。
- `owner_instance_id` と `session_id` を保存する。
- デフォルトの永続パスはインスタンス専用にする。
- 既存の共有 `~/.uag/schedules.json` は互換読み取り専用とし、新規作成先には使わない。

### OS-persistent timer

- Windows Task Scheduler / `systemd-run` / `at` が実行主体になる。
- 作成元UAGのイベントキューへ戻すことは保証しない。
- 起動プロセスへ渡すのは `schedule_id` または一回限りの実行トークンだけとし、prompt・token・principal情報をコマンドラインへ埋め込まない。
- 新しいUAGプロセスは、保存済みのスケジュールを読み、`session_id` の存在と認証境界を検証してから実行する。

## 永続化

JSONのread-modify-writeではプロセス間排他とclaimを安全に実装できないため、Schedulerの永続ストアをSQLiteへ移行する。

必要な概念:

- `schedules`: スケジュール定義、owner、session、enabled
- `scheduler_leases`: instance_id、lease期限、heartbeat
- `scheduler_runs`: `(schedule_id, due_at)` の一意なidempotency key
- `scheduler_events`: 発火結果と配信状態

期限アイテムの取得は、トランザクション内でclaimする。

```text
BEGIN IMMEDIATE
  select due schedule where enabled and next_fire_at <= now
  and (lease is absent or lease expired)
  update lease_owner / lease_expires_at
COMMIT
```

同じ `schedule_id + due_at` は一度だけrunを作成する。別プロセスのPython `threading.Lock` に依存しない。

## 発火時の検証

1. `instance_id` が自分の所有物か確認する。
1. `session_id` が存在する場合、Session Storeから現在のidentity bindingを取得する。
1. 作成時の `principal_id`、`project_id`、`room_id`、authentication configuration fingerprint と一致するか確認する。
1. 不一致、失効、設定変更、存在しないsessionの場合はfail-closedとし、LLM/tool実行を行わず監査結果だけを残す。
1. `session_id` の文字列だけでユーザーや権限を復元しない。必ずSession Storeのbindingを再解決する。

## 再起動と孤児タイマー

プロセス再起動では新しい `instance_id` を発行する。旧インスタンス所有のinternal timerは直ちに別インスタンスへ移さない。

- デフォルト: orphaned timerを停止状態にし、管理操作でreclaim
- 明示設定時のみ: lease期限切れ後に新しいinstanceがclaim可能
- reclaim時もsession binding、project/room authorization、configuration fingerprintを再検証

これにより、旧プロセスの残留タイマーが新しい認証コンテキストで勝手に実行されることを防ぐ。

## 環境変数

暫定的な分離には以下を使用できる。

- `UAGENT_SCHEDULES_FILE`: 明示的なScheduler DB/file path
- `UAGENT_STATE_DIR`: state root全体の分離

将来は `UAGENT_SCHEDULER_MODE=instance|shared|os` を導入する。`shared` は明示指定時のみ許可し、leaseとclaimを必須にする。

## テスト計画

- 2プロセスが同じ期限のinternal timerを監視しても、runが1件だけ生成される。
- AのtimerがBのevent queueへ届かない。
- Aのsession_idを指定しても、Bのprincipal/project/roomへ越境できない。
- session revoke、project membership revoke、authentication fingerprint変更後は発火しない。
- 再起動後のorphaned timerはデフォルトで発火しない。
- OS timerはcommand lineにprompt、token、principal情報を含めない。
- v1の共有`schedules.json`からの移行で、未検証timerを自動発火しない。

## 移行方針

1. まず識別子と所有境界をScheduleItemへ追加する。
1. 次にSQLite SchedulerStoreとlease/claimを導入する。
1. internal timerのinstance filteringを有効化する。
1. OS timerのpayloadを実行トークン方式へ変更する。
1. 旧JSONは読み取り・明示importのみ許可し、最終的に廃止する。
