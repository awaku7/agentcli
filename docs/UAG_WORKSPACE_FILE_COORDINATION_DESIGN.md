# UAG Lightweight Workdir Presence Design

## 1. Purpose

複数の CLI / GUI window / Browser tab が同じ workdir で同時に動作していることを UAG が認識できるようにする。

目的は強制排他ではない。同じ project/workdir で別 Client が作業中であることを Agent に知らせ、同じファイルを同時編集するリスクを判断できるようにする。

## 2. Principles

- CLI / GUI window / Browser tab は Client Instance として同じ扱いにする
- file lock / file claim は行わない
- workspace lock も行わない
- cmd / Python / file tool を区別しない
- filesystem monitoring を行わない
- daemon / external coordination service を要求しない
- 既存 SQLite SessionStore を利用する
- Presence は advisory information であり security / consistency boundary ではない

## 3. Minimal Data Model

~~~sql
CREATE TABLE active_clients (
    client_instance_id TEXT PRIMARY KEY,
    principal_id TEXT,
    session_id TEXT,
    workdir TEXT NOT NULL,
    started_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);
~~~

`workdir` は canonicalize して保存する。特に Windows では separator、absolute path、case 等の表記差で同一 workdir が別物にならないよう、既存の path normalization utility があれば再利用する。

## 4. Lifecycle

Client 起動時に自分を登録する。

~~~text
Client starts
    ↓
canonicalize workdir
    ↓
upsert active_clients
    ↓
query other active clients in same workdir
~~~

正常終了時は自分の row を削除する。

異常終了で row が残る可能性があるため、`last_seen_at` が一定時間以上古い row は active とみなさない。

専用 heartbeat daemon/thread は初期実装では作らない。LLM request、tool execution、user input 等の既存 Runtime activity に合わせて `last_seen_at` を更新する。

## 5. Agent Awareness

Agent へは他 Client の会話内容を自動注入しない。必要なのは Presence 情報だけである。

概念例:

~~~text
workspace_presence:
  other_clients_active: true
  count: 1
~~~

必要であれば session_id / client_instance_id を Runtime diagnostics に保持できるが、LLM へ常に内部 ID を渡す必要はない。

Agent は Presence を見て、同じファイルを変更する可能性がある場合に慎重に進める、ユーザーへ確認する、最新ファイルを再読込する等を判断できる。

Presence 自体は write を block しない。

## 6. Scope

初期実装は同じ SQLite SessionStore を共有する Client 間だけを対象とする。

別PC・別DB間の Presence、distributed locking、network coordination は対象外。

## 7. Failure Rules

- Presence DB への登録失敗だけで通常の Client 起動を禁止しない
- stale row は `last_seen_at` で無視できる
- process crash 後に永久的な「起動中」表示を残さない
- Presence は外部 IDE / editor / shell process の存在を検出しない
- Presence を file consistency の保証として扱わない

## 8. Non-Goals

- file claim / file lease
- workspace lock
- Operational Transformation
- CRDT
- realtime collaborative editing
- automatic semantic merge
- Git branch / worktree orchestration
- filesystem monitoring
- cmd / Python の write 予測
- distributed lock service
- background cleanup daemon
- other Session content awareness

## 9. Acceptance Criteria

1. 同じ canonical workdir で CLI A が活動中に CLI B を起動すると、B は他 Client の存在を認識できる
2. GUI / Browser tab も同じ Client Instance model で認識できる
3. Presence があっても read / write / cmd / Python を Runtime が強制 block しない
4. 正常終了した Client は active から外れる
5. crash した Client は stale timeout 後に active とみなされない
6. Windows path 表記差で同一 workdir が別 Presence にならない
7. Presence のために他 Session の会話履歴を ActiveContext へ自動注入しない
