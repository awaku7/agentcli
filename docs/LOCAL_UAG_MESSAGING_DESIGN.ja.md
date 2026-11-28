# 同一ユーザー内 UAG プロセス間プレゼンス・メッセージング設計

Status: **CLI/GUI/Web/A2A の初期対応を実装済み。** Web は認証 principal・private room・project 単位、A2A は管理者 opt-in と明示的 inbox pull に限定する。受信は全ホストで確認なしの全自動取り込み（Issue #509 で方針変更。CLI では実行中ラウンドへの割り込みと自動再開を含む）。実プロバイダーを使う複数プロセス間の手動 UI smoke test は未実施。

## 1. 目的

同じマシン・同じ OS ユーザーで動作する UAG の CLI、GUI、Web、A2A が、互いの存在を把握し、必要に応じてメッセージを交換できるようにする。

- 新しい UAG が起動したとき、既存の UAG を一覧表示できる。
- 既存の UAG は後から起動した UAG を検知できる。
- 送信先を指定してメッセージを送れる。
- 受信内容は確認なしで自動的に会話へ取り込む（送信元は表示と履歴で分かる形にする）。実行中のラウンドがある場合は割り込んで処理し、終わったら自動で前の作業を再開する。
- 既存のプロセス登録、イベントキュー、認証・認可の仕組みを活用する。

本設計はローカルの複数 UAG プロセスを対象とする。現行のプロセス登録簿や A2A を、そのままメッセージング機能とみなすものではない。

## 2. 現状と再利用する仕組み

| 既存機能 | 現状 | 本設計での利用 |
|---|---|---|
| `runtime/process_registry.py` | CLI/GUI/Web/A2A がユーザー専用状態ディレクトリへ自己登録する。記録は `instance_id`、entrypoint、PID、プロセス生成時刻など。 | UAG Admin 監視向けに現行どおり維持する。メッセージ機能の宛先一覧・認可には使わない。 |
| `core.event_queue` | CLI の入力やバックグラウンドイベントをメインループへ渡す。 | CLI の受信通知をフォアグラウンド処理へ渡す。GUI/Web は各 UI のイベント機構へ渡す。 |
| `human_ask` | ホスト UI に人間への確認を依頼する既存ツール。 | 受信取り込みでは使わない（Issue #509 で確認を廃止）。 |
| Web identity / room policy | Web は複数の認証済みユーザー、room、project を扱える。OIDC と trusted proxy 経由の企業認証構成がある。 | Web の送受信先を process だけでなく principal/room に束縛する。 |
| A2A | 別プロセスの HTTP エンドポイントで、Bearer 認証とタスク実行を行う。 | A2A は対話 UI と別の受信アダプターとして扱う。ローカル同一ユーザーであることだけを認可に使わない。 |

`instance_id` は UAG インストールの識別子であり、同一インストールの複数プロセス間で共通する。プロセス宛先の識別に単独で使わず、PID とプロセス生成時刻の組、または新規の起動ごとの process UUID を使う。

現行の process registry は Admin 監視向けのスナップショットであり、活動状態・会話本文・現在のタスクは記録しない。また、起動通知や定期監視は提供しない。

## 3. 用語と宛先

- **UAG process**: CLI、GUI、Web、A2A の実行プロセス。
- **process key**: 起動ごとに一意なプロセス識別子。既存の PID + `create_time` を使うか、process UUID を追加する。
- **endpoint**: メッセージを受け取る論理的な宛先。
  - CLI/GUI: process key。
  - Web: process key に加え、認証済み `principal_id` と `room_id`（必要なら session ID）。Web サーバープロセスだけでは宛先を特定できない。
  - A2A: A2A server/process と認証済みタスクコンテキスト。対話ユーザーの代わりとはみなさない。
- **message**: 一つの送信先を持つテキスト。送信元・宛先・作成時刻・状態を記録する。

## 4. 対象範囲と非目標

### 対象

- 同じ OS ユーザー、同じローカル UAG state directory を使うプロセス間の存在確認とテキストメッセージ。
- Web の場合は、OS ユーザー境界に加えて既存の Web principal/room/project 認可を維持する。
- CLI/GUI/Web の受信内容を確認なしで自動的に会話へ投入する。
- ユーザーの明示的な指示に応じた送信 Tool。

### 既定参加 / オプトアウト方針

同一OSユーザー内での自然な peer 発見を優先し、`UAGENT_LOCAL_MESSAGING` は既定で `on` とする。参加したくない UAG では `UAGENT_LOCAL_MESSAGING=off` を設定して再起動する。受信メッセージは承認を挟まず自動で会話へ入る。メールボックスは運ぶ仕組みであり認可の境界ではない、という位置づけに基づく（Issue #509）。

- CLI/GUI は対話実行時に自動で endpoint を登録する。非対話 CLI は登録しない。
- Web は認証済み private room の初回接続時に自動登録し、principal/room/project の範囲に限定する。公開 room は対象外。
- A2A は既定では参加しない。`UAGENT_LOCAL_MESSAGING_A2A=on` も明示された場合だけ endpoint を登録し、受信は task からの明示的 inbox 呼び出しに限る。
- `UAGENT_LOCAL_MESSAGING=off` の場合は endpoint と poller を起動せず、Tool からも送受信できない。再び `on` に戻すにはプロセスを再起動する。
- 既存 `process_registry` は UAG Admin 向け登録として維持し、メッセージ本文やタスク状態は登録しない。
- `all` はこの opt-out 設定の代わりではなく、受信 endpoint の実行中だけ同じ送信元の確認を省略する。

利用者はCLIコマンドで状態を切り替えず、自然文でpeer一覧や送信を依頼し、LLMが `local_messaging` Tool を使う。既存の process registry は新機能の認証・認可には使わない。

### 非目標（初期版）

- 別マシンへの配送、インターネット中継、BLE/Nostr の再利用。
- 会話履歴やセッション状態の共有。
- 受信したメッセージによる、実行中の LLM/tool 呼び出しの強制中断。
- ファイルや大容量添付の転送。
- プロセスの起動・停止・制御。
- Web/A2A の認証境界を迂回したユーザー間メッセージ。

## 5. 全体構成

```text
                    ┌────────────────────────────┐
                    │ SQLite endpoints table     │
                    │ 参加 endpoint の発見       │
                    └─────────────┬──────────────┘
                                  │ scan / poll
┌───────────────┐  send  ┌────────▼───────────┐  poll  ┌────────────────┐
│ UAG endpoint A│───────▶│ local message DB   │◀───────│ UAG endpoint B │
└───────────────┘        │ SQLite mailbox     │        └───────┬────────┘
                         └────────────────────┘                │
                                                  typed event queue
                                                               │
                                                  frontend adapter
                                                               │
                                                    human confirmation
                                                               │
                                                accepted message -> turn
```

SQLite は参加 endpoint の登録/heartbeat とメッセージの耐久化・複数プロセス間の排他に使う。endpoint の PID と process creation time は `psutil` で照合し、既存 `process_registry` は UAG Admin 向けに維持する。初期版はローカル DB の短周期ポーリングとし、ソケット・ポート・常駐サーバーを追加しない。受信ポーラーは DB を確認して型付きイベントを UI 側へ enqueue するだけで、LLM、`human_ask`、UI を直接操作しない。

## 6. プロセス発見と状態表示

1. 既存の `process_registry` は UAG Admin 向け登録として維持し、メッセージ機能への参加同意には使わない。
1. 参加中の endpoint だけが SQLite の `endpoints` に自分を登録し、heartbeat を更新する。opt-out 中の UAG は peer 一覧に出さず、メッセージを送受信しない。
1. 参加中の UAG は `endpoints` のみを peer 一覧・起動通知の対象とし、process key の PID と `create_time` を OS のプロセス情報と照合する。
1. endpoint は正常終了/opt-out 時に削除する。クラッシュ時は heartbeat の期限切れと PID + `create_time` の照合で stale と判定し、PID だけで稼働中と判断しない。
1. 登録簿や DB が利用不能でも UAG 本体の起動は妨げない。監視・メッセージ機能は best-effort とする。

endpoint の状態表示には稼働情報（entrypoint、PID、起動時刻）に加え、workdir と短い purpose を含める。workdir は現在のプロセスのカレントディレクトリ（Web は private room の base_dir）、purpose は `UAGENT_WORK_PURPOSE` または `local_messaging(action=list, purpose=...)` で明示された最大500文字の要約とする。会話本文・prompt・Tool 入出力を自動収集しない。作業状況は同じ scope の peer 一覧から直接参照でき、状態の登録・一覧表示に `human_ask` は使わない。CLI poller は inbox を約 0.5 秒ごとに確認し、heartbeat と workdir を 2 秒ごとに更新する。heartbeat が 15 秒以上古い endpoint は peer 一覧から除外する。`idle`/`busy`/`awaiting_confirmation` といった活動状態は引き続き対象外。

## 7. SQLite メールボックス

### 保存場所と制約

- `get_state_dir()` 配下に専用 DB（例: `local_messaging/messages.sqlite3`）を置く。
- 既定のユーザー専用ディレクトリと同等の OS 権限/ACL を維持する。
- 複数 OS ユーザー間の共有 DB、ネットワークファイルシステム上の DB は初期版の対象外。
- WAL、短い transaction、busy timeout を使い、ネットワーク待ちや人間の確認待ちの間は transaction/lock を保持しない。

### 最小データモデル案

`endpoints` テーブル:

| 列 | 目的 |
|---|---|
| `endpoint_id` | 参加 endpoint の UUID。Web では principal/room ごとに分ける |
| `process_key` | endpoint をホストする UAG プロセス |
| `entrypoint` | `cli` / `gui` / `web` / `a2a` |
| `pid` / `create_time` | OS process incarnation の照合。PID 再利用を誤認しない |
| `enabled_at` / `heartbeat_at` | 参加状態と稼働状態の確認。endpoint は heartbeat TTL で期限切れとする |
| `workdir` | ホストが共有する現在の作業ディレクトリ |
| `purpose` | endpoint が明示的に共有する短い作業目的（最大500文字）。prompt全文は保存しない |

Web 対応時は `principal_id` / `room_id` 等の認証・配送スコープを追加し、Web server process 一つを一つのユーザー endpoint とみなさない。

`messages` テーブル:

| 列 | 目的 |
|---|---|
| `message_id` | メッセージ UUID / 主キー |
| `sender_endpoint_id` | 送信元 endpoint |
| `recipient_endpoint_id` | 配送先 endpoint |
| `body` | UTF-8 テキスト。信頼されない入力として扱う |
| `created_at` / `expires_at` | 作成時刻と有効期限 |
| `status` | `pending` / `claimed` / `accepted` / `rejected` / `expired` / `failed` |
| `claim_owner` / `claim_until` | 重複確認・処理を避ける短期 claim |
| `decided_at` | 確認結果の時刻 |

送信時に message row を commit してから成功を返す。受信側は宛先を限定して pending item を短期 claim し、UI へ渡す。受信側の承認/拒否を DB に反映する。CLAIM lease は 60 秒で、受信確認中は poller が更新する。message の既定 TTL は 1 時間、terminal/expired row は期限後 7 日で削除する。配信保証は at-least-once とし、同じ message ID の二重 turn を受信側で抑止する。

初期版では本文サイズに上限を設け、添付は含めない。保持期間後の削除/expiry 処理を行う。配送先プロセスが終了した場合、メッセージを新しいプロセスへ自動転送しない。再起動後のプロセスは異なる process key であり、誤って別会話へ届けてはならない。

## 8. 受信・承認フロー

1. 参加中 endpoint の各ホストはバックグラウンド poller を起動し、`endpoints` の heartbeat と自分宛て inbox を確認する。
1. メッセージを検知したら、`local_message_received` などの型付きイベントをホストのイベントキューへ入れる。
1. poller は確認 UI を開かず、LLM を起動せず、イベントの表示状態を自分で決めない。
1. フォアグラウンド側がイベントを処理し、確認なしで受理する。送信元ラベル付き user turn として会話へ投入する。本文は明示的に外部コンテンツとして区別し、system/developer 指示へ昇格させない。
1. CLI では、現在の LLM/tool 処理中に届いたメッセージは監視スレッドが検知してラウンドへ割り込み、ピアのターンを処理したあと、自動の再開ターンを差して前の作業を続ける。割り込みは `human_ask` や入力プロンプトが使われている間は行わない。

### 確認フローの廃止（Issue #509）

初期版では `human_ask` による `y / n / all` 確認と送信元単位の grant があったが、同一マシン・同一ユーザーのピアに対しては運ぶ仕組みと認可を分ける位置づけと合わず、Issue #509 の方針で全ホストとも確認なしの自動取り込みに変更した。取り込み確認の廃止は、通常の ToolPolicy、Tool 確認、Enterprise Policy には影響しない。

## 9. エントリポイント別アダプター

| エントリポイント | 受信通知・確認 | 宛先/認可 |
|---|---|---|
| CLI | `core.event_queue` へ enqueue。メインループで確認なしに会話 turn として処理。実行中は割り込み＋自動再開。 | process key。 |
| GUI | GUI worker のイベントキューへ渡し、確認なしに会話 turn として処理。 | process key。 |
| Web | 対象 private room 専用の受信スレッドで確認なしに受理し、その room の worker へ渡す。 | 認証 principal・room・project の完全一致が必要。OIDC/AD等の既存 connection identity を再検証する。公開roomとWebプロセス全体へのbroadcastは禁止。 |
| A2A | 非対話サービスのため人間向け `human_ask` は使用しない。認証済み task が `local_messaging(action=inbox)` を明示的に呼び出した場合だけ受信し、未信頼データとして返す。自動 inbox listener は持たない。 | 管理者の `UAGENT_LOCAL_MESSAGING=on` と `UAGENT_LOCAL_MESSAGING_A2A=on` の両方が必要。さらにA2A Bearer認証、task context、ToolPolicyを維持する。 |

### A2A の初期方針

A2A endpoint は既定で無効とする。両管理者設定が有効な場合でも、バックグラウンドで自動受信・会話投入は行わない。認証済み A2A task が `local_messaging(action=inbox)` を呼んだ時点で初めて inbox item を claim し、明示的な Tool 結果として未信頼マーカー付きで返す。A2A endpoint はCLI/GUIと同じローカルOSユーザーのメッセージ領域を使うため、管理者がA2A連携を有効化した場合、認証済みA2A taskはopt-in済みCLI/GUI peerを一覧・宛先指定できる。CLI/GUI/Web 側は受信時に人間の確認を行わない（Issue #509）。A2A 側の受信は従来どおり明示的な inbox 呼び出しに限る。

## 10. 送信 API / Tool 案

- `local_messaging(action=list, purpose=...)`: 到達可能な参加 endpoint と共有済みの workdir/purpose を一覧表示する。`purpose` を指定した場合は現在のendpoint情報として共有する。Webではprincipal/room/projectの範囲内に限定し、状態共有に `human_ask` は使わない。会話本文や秘密情報は返さない。
- `local_messaging(action=send)`: 一覧の `endpoint_id` を指定してテキストを送る。message ID と配送受付状態を返す。
- `local_messaging(action=inbox)`: A2A専用。管理者opt-in済みA2A endpointに対し、現在の認証済みtaskが明示的に受信内容を取得する。

Tool は送信依頼を SQLite へ記録するだけで、宛先選定を曖昧にして broadcast しない。受信確認は Tool 実行とは独立して poller が行う。ユーザーが明示していない自動返信や、相互に agent を起動し続ける無限往復を防ぐため、返信はメッセージ ID/送信元を示し、通常の ToolPolicy を維持する。

## 11. セキュリティ・プライバシー

- 同一 OS ユーザー内の利便機能であり、同じ OS ユーザー権限のプロセス同士を隔離するセキュリティ境界ではない。
- デフォルト state directory の ACL/permissions を維持し、別 OS ユーザーからの読み取り/書き込みを許さない。手動で異なる OS ユーザー間に `UAGENT_STATE_DIR` を共有する構成は非対応とする。
- process registry は発見情報であり、認証・認可トークンではない。PID、`instance_id`、ファイル名を秘密として扱わない。
- Web はローカル DB にアクセスできることを Web user の認可根拠にしない。送受信は `principal_id`、room、project membership と session validity に束縛する。
- 受信本文は信頼しない。コマンド、秘密情報、system instruction として特別扱いせず、通常のコンテンツ安全対策を適用する。
- ログに本文を不用意に残さず、監査には message ID、送受信 endpoint、判定、時刻などの最小メタデータを使う。
- DB が壊れている/権限が不正/書き込み不能な場合、メッセージ機能を停止し、UAG 本体の対話は継続する。

## 12. ライフサイクルと障害時の挙動

- 起動: state directory と UI identity を確定後、既存 process registry を照合し、自分を登録して poller を開始する。
- 終了: poller を停止し、DB connection を閉じ、既存の process registry cleanup を行う。
- graceful shutdown: 宛先 process key の pending item は expired または undeliverable とする。
- crash: stale process registry entry は PID + process creation time で除外する。未決 item は lease expiry 後に回収するが、別 process key へ自動転送しない。
- DB contention: transaction は短く保ち、busy timeout 後は bounded retry。LLM/API/UI の待機中に DB transaction を保持しない。
- poller failure: エラーを記録して再試行し、CLI/GUI/Web のメインイベントループを停止させない。

## 13. 実装フェーズ案

1. **CLI/GUI**: 対話起動時に自動参加。`UAGENT_LOCAL_MESSAGING=off` で opt-out。イベントキューと既存 `human_ask` の `y/n/all` を利用。
1. **Web**: 初回接続時にprivate room endpointを自動作成。principal/room/project scoped routing、既存WebSocket確認UI、OIDC/room再検証を利用。共通設定が `off` なら参加しない。
1. **A2A**: `UAGENT_LOCAL_MESSAGING_A2A=on` の明示的な管理者設定が必要（共通設定 `off` も尊重）。自動受信せず、認証済みtaskからの明示的な `inbox` pull のみ。

全フェーズで同じ mailbox schema と message state machine を使い、frontend 間で別の配送実装を複製しない。

## 14. 受け入れ条件・テスト観点

- 複数の CLI が同一 state directory で登録され、各プロセスを別々に識別できる。
- 新規起動/正常終了を既存プロセスが検知し、PID 再利用や stale record を誤認しない。
- 送信先以外にメッセージが漏れず、並行 poller による重複 turn が抑止される。
- `y`/`n`/`all` が仕様どおりで、`all` は送信元ごと・実行中 UI endpoint のみに有効。
- UI が処理中のメッセージはキューで保留され、安全なターン境界で処理される。
- 外部メッセージ本文が system instruction として扱われず、`all` が ToolPolicy を迂回しない。
- GUI の確認操作はGUI worker/UI経路、Webの確認は宛先private room/principal/projectに限定される。
- OIDC の失効/room 権限変更後に Web の古い宛先へ配信・取り込みしない。
- A2A endpoint は両管理者フラグなしでは作られず、taskの明示的なinbox呼び出しなしでは受信しない。
- mailbox の利用不能が通常の UAG 起動・会話を妨げない。

## 15. 関連資料

- [UAG プロセス自己登録](UAG_PROCESS_REGISTRY.md)
- [Web multi-user / OIDC identity](UAG_OPENTELEMETRY_WEB_IDENTITY.md)
- [Active Directory / Windows 認証](ACTIVE_DIRECTORY.ja.md)
- [Interrupt / cancellation](INTERRUPT.md)
- [Multi-Agent and Remote Runtime](MULTI_AGENT_RUNTIME.md)
- [Scheduler instance isolation](SCHEDULER_INSTANCE_ISOLATION_DESIGN.ja.md)
