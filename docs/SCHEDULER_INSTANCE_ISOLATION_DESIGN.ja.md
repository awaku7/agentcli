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
| `event_key` | `run_id + event順序 + kind` から作る一意キー | outbox eventの重複生成防止 |

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

JSONのread-modify-writeではプロセス間排他とclaimを安全に実装できないため、Schedulerの定義・claim・dispatch outboxはSQLiteへ置く。

現行の主要概念:

- `schedules`: スケジュール定義、owner、session、enabled、schedule claim
- `scheduler_runs`: `(schedule_id, due_at)` のidempotency keyを持つ実行記録
- `scheduler_events`: 発火後にconsumerへ渡すdurable outbox

`scheduler_events` は少なくとも次を保持する。

- `event_key`
- `schedule_id`
- `run_id`
- `target_instance_id`
- JSON `payload`
- `pending` / `delivered` / `invalid` status
- dispatch claim owner / lease
- retry可能時刻、attempt count、last error
- created / delivered timestamp

期限アイテムの取得は、トランザクション内でclaimする。

```text
BEGIN IMMEDIATE
  select due schedule where enabled and next_fire_at <= now
  and (lease is absent or lease expired)
  update lease_owner / lease_expires_at
COMMIT
```

同じ `schedule_id + due_at` は一度だけrunを作成する。別プロセスのPython `threading.Lock` に依存しない。

## Durable dispatch / outbox

scheduleをclaimした後、`SchedulerService` は以下の順で処理する。

1. `(schedule_id, due_at)` をidempotency keyとしてrunを作成または再取得する。
1. notice / LLM / direct execution用のevent payloadを構築する。
1. SQLiteの1 transaction内でoutbox eventをinsertし、同時にone-shot scheduleを削除またはperiodic scheduleの次回時刻を更新する。
1. commit後にだけoutbox dispatcherがeventをclaimする。
1. 通常のCLI/GUI `queue.Queue` では、eventをqueueへputしただけでは`delivered`にしない。
1. consumerが`queue.get()`でeventを取り出した時点でoutboxをACKして`delivered`にする。
1. `put()`失敗時はclaimを解放し、eventを`pending`のままretry可能状態へ戻す。

これにより、scheduleだけを確定した後でeventが生成されないというsilent-loss windowを避ける。

### delivery guarantee

outboxの配信保証は **at least once** とする。

- sink acceptance後でもconsumer ACK前にprocessが停止した場合、eventはpending/leased状態として残る。
- 生存中のdispatcherはqueue内でACK待ちのeventのleaseを更新する。長いLLM/tool処理でdequeueが遅れても同じeventを再投入しない。
- ACK writeに失敗した場合もeventは再配信され得る。
- 同一run内では先行pending eventがある間、後続eventをclaimしない。noticeよりexecution eventが先に流れることを防ぐ。
- generic sinkが`put()`のみを提供しconsumer-side ACKを提供できない場合は、互換性のためsink acceptanceをdelivery境界とする。

`delivered`は **consumerへeventが到達した状態** であり、scheduled runの成功完了ではない。
runの`queued` / `running` / `success` / `failed` / `timeout` / `cancelled`とは別のstate machineとして扱う。

### duplicate execution

at-least-once deliveryでは同じeventが再配信される可能性がある。
実行側は永続化された`run_id`を使い、`SchedulerWorker`がrunをclaimすることで同じrunの二重実行を抑止する。

notice等の非実行eventは再表示される可能性があるため、「event exactly once」と「job execution idempotency」を混同しない。

## instance isolationとreclaim

pending outbox eventにも`target_instance_id`を保存する。
owner未設定のscheduleをclaimした場合は、claimしたinstanceをrun metadata、event payload、`target_instance_id`に設定する。
別instanceは通常、そのeventをclaimできない。

process再起動では新しい`instance_id`が発行されるため、旧instanceのschedule/eventを自動的に新instanceへ移してはいけない。
現在は明示的な`reclaim_orphaned_instance(previous_instance_id, new_instance_id)`で、旧ownerの有効scheduleとpending outboxを同じtransaction内で新ownerへ移せる。

このreclaimは **自動実行しない**。callerは以下を再検証してから実行する必要がある。

- `session_id` が現在も有効か
- 保存時と現在のprincipal / project / room境界が整合するか
- authentication configurationが失効・変更されていないか
- operatorが旧instanceの停止を確認しているか

pending eventをreclaimした場合、payloadの`owner_instance_id`を新ownerへ更新し、`reclaimed_from_instance_id`へ旧ownerを残す。

## 発火時の検証

1. `instance_id` が自分の所有物か確認する。
1. `session_id` が存在する場合、Session Storeから現在のidentity bindingを取得する。
1. 作成時の `principal_id`、`project_id`、`room_id`、authentication configuration fingerprint と一致するか確認する。
1. 不一致、失効、設定変更、存在しないsessionの場合はfail-closedとし、LLM/tool実行を行わず監査結果だけを残す。
1. `session_id` の文字列だけでユーザーや権限を復元しない。必ずSession Storeのbindingを再解決する。

現行のoutbox/reclaim APIはこの再検証を自動実行しないため、認証付きmulti-user環境で自動reclaimへ進む前にidentity-bound reclaim serviceを追加する。

## 再起動と孤児タイマー

プロセス再起動では新しい `instance_id` を発行する。旧インスタンス所有のinternal timerは直ちに別インスタンスへ移さない。

- デフォルト: orphaned timer / pending eventを旧ownerに束縛したまま停止状態にする。
- 明示reclaim時のみ: session / authentication境界を再検証したうえで新ownerへ移す。
- schedule確定前にcrashした場合はschedule側をreclaimする。
- schedule確定後、consumer ACK前にcrashした場合はpending outbox側をreclaimする。

これにより、旧プロセスの残留タイマーが新しい認証コンテキストで勝手に実行されることを防ぐ。

## 環境変数

暫定的な分離には以下を使用できる。

- `UAGENT_SCHEDULES_FILE`: 明示的なScheduler DB/file path
- `UAGENT_STATE_DIR`: state root全体の分離

将来は `UAGENT_SCHEDULER_MODE=instance|shared|os` を導入する。`shared` は明示指定時のみ許可し、leaseとclaimを必須にする。

## テスト計画

実装済みの回帰テスト対象:

- sink failure後もoutbox eventがpendingで残り、後続pollで再配信できる。
- consumer dequeue前はpending、dequeue ACK後にdeliveredへ遷移する。
- 同一runのnotice配信失敗時に後続execution eventが追い越さない。
- pending eventを別instanceが自動claimしない。
- 明示reclaimでschedule確定前／outbox生成後の双方を新instanceへ引き継げる。
- schedule claimを失ったtransactionではoutbox rowも作られない。

継続検証:

- 2プロセスが同じ期限のinternal timerを監視しても、runが1件だけ生成される。
- AのtimerがBのevent queueへ届かない。
- Aのsession_idを指定しても、Bのprincipal/project/roomへ越境できない。
- session revoke、project membership revoke、authentication fingerprint変更後は発火/reclaimしない。
- process killをschedule claim前／run作成後／outbox commit後／queue put後／consumer ACK前後へ注入する。
- OS timerはcommand lineにprompt、token、principal情報を含めない。
- v1の共有`schedules.json`からの移行で、未検証timerを自動発火しない。

## 移行方針

1. 識別子と所有境界をScheduleItemへ追加する。**完了**
1. SQLite SchedulerStoreとschedule lease/claimを導入する。**完了**
1. internal timerのinstance filteringを有効化する。**完了**
1. OS timerのpayloadを実行トークン方式へ変更する。**完了**
1. durable `scheduler_events` outboxとdequeue ACKを導入する。**完了**
1. identity-bound reclaim serviceとmulti-process failure injectionを追加する。**継続**
1. 旧JSONは読み取り・明示importのみ許可し、最終的に廃止する。
