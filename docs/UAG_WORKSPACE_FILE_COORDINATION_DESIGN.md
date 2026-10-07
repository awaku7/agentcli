# UAG Lightweight Workspace File Coordination Design

## 1. Purpose

複数の CLI / GUI window / Browser tab、または別 Session が同じ project/workspace を扱うとき、同一ファイルへの同時 write による上書き・競合を軽量に防ぐ。

これは共同編集、OT、CRDT、分散 filesystem lock を実装する機能ではない。UAG Runtime 内の write coordination に限定する。

## 2. Principles

- CLI / GUI window / Browser tab は Client Instance として同じ扱いにする
- read は claim 不要
- edit / write / delete / rename は対象 file の claim を要求する
- 同じ principal でも別 Client / Session の claim は競合として扱う
- OS file lock を長時間保持しない
- daemon / external lock server を要求しない
- 既存 SQLite SessionStore を利用する
- crash で永久 lock にならない Lease とする
- claim は編集意図の調停であり、filesystem security boundary ではない

## 3. Minimal Data Model

~~~sql
CREATE TABLE file_claims (
    project_key TEXT NOT NULL,
    canonical_path TEXT NOT NULL,
    principal_id TEXT,
    session_id TEXT NOT NULL,
    client_instance_id TEXT NOT NULL,
    claimed_at TEXT NOT NULL,
    heartbeat_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    PRIMARY KEY (project_key, canonical_path)
);
~~~

初期実装では history table、wait queue、priority、semantic merge は持たない。

`canonical_path` は workspace root を基準に正規化し、`..`、相対/絶対表記差、Windows の path separator / case normalization により同じファイルが別 claim にならないようにする。既存の workspace/path safety utility があれば再利用する。

## 4. Claim Flow

~~~text
write-capable tool
      ↓
canonicalize target path
      ↓
remove expired claim
      ↓
atomic claim
   ┌──┴──┐
 success conflict
   │        │
 write     return FILE_BUSY
   │
 release
~~~

claim 取得は SQLite transaction 内で atomic に行う。既存 claim が同じ Client に属する場合は idempotent refresh を許可する。

他 Client / Session の有効な claim がある場合は write を実行しない。

## 5. Lease

Claim は短い lease とし、Client が write operation を継続している間だけ必要に応じて heartbeat を更新する。

短時間の通常 file edit では、claim → write → release だけでよく、常時 heartbeat thread を必須にしない。長時間 operation のみ既存 Runtime lifecycle から refresh する。

process crash 等で release されなくても `expires_at` 後に次の claim 要求で回収できる。初期実装では専用 cleanup daemon を作らない。

## 6. Tool Integration

File Claim Manager は write-capable tool の共通境界に置く。

対象例:

- file create / edit / patch / overwrite
- delete
- rename / move

read / search / stat は対象外。

複数ファイルを一度に変更する operation は canonical path 順に claim を取得し、途中で失敗した場合は取得済み claim を release する。これにより単純な deadlock を避ける。

## 7. Conflict Result

競合時は LLM に巨大な他 Session context を渡さない。最低限の structured result を返す。

~~~text
FILE_BUSY
project_key: ...
path: ...
session_id: ...
client_instance_id: ...
expires_at: ...
~~~

Runtime / Agent は別作業へ進む、後で retry する、またはユーザーへ確認することを選べる。

他 Session の Raw History や AgentState を自動注入しない。

## 8. Scope

初期実装は **同じ SQLite SessionStore を共有する Client** 間の coordination を対象とする。

別PC・別DB・network filesystem をまたぐ distributed locking は対象外。Server deployment で必要になった場合は Storage backend / Concurrent Runtime の別設計として拡張する。

## 9. Failure Rules

- claim 取得失敗時は write しない
- DB unavailable 時に暗黙で claim を bypass しない
- expired claim は次回 claim 時に回収可能
- write failure 後も best-effort release する
- release failure は lease expiry により回復可能
- claim は外部 editor / IDE の変更までは防げない

## 10. Non-Goals

- Operational Transformation
- CRDT
- realtime collaborative editing
- automatic semantic merge
- Git branch / worktree orchestration
- distributed lock service
- background cleanup daemon
- other Session content awareness
- external editor locking

## 11. Acceptance Criteria

1. CLI A が file X を claim 中、CLI B は file X を write できない
2. CLI A が file X を claim 中でも file X の read は可能
3. 同じ user でも別 Client / Session は競合する
4. claim release 後は別 Client が取得できる
5. crash で claim が残っても lease expiry 後に回復できる
6. Windows path 表記差で同じ file に複数 claim が作られない
7. 複数 file operation は安定順で claim し、部分取得失敗時に rollback/release する
8. FILE_BUSY のために他 Session の会話履歴を ActiveContext へ自動注入しない
