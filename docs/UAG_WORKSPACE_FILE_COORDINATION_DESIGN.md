# UAG Lightweight Workdir Presence Design

## 1. Purpose

CLI / GUI window / WebRoom / A2A Task が同じ workdir で同時に作業していることを UAG が認識できるようにする。強制排他は行わず、Agent に競合作業の可能性を知らせる advisory Presence とする。

## 2. Principles

- CLI / GUI / Web / A2A Task を同一の Presence lifecycle と TTL で扱う
- A2A の接続相手自体ではなく、UAG 側で実行する Task を登録する
- A2A protocol の通信状態や heartbeat を Presence の生存判定に流用しない
- file claim / file lease / workspace lock は行わない
- cmd / Python / file tool を区別しない
- filesystem monitoring、daemon、external coordination service を導入しない
- 既存 SQLite SessionStore を利用する
- Presence は consistency / security guarantee ではない

## 3. Minimal Data Model

~~~sql
CREATE TABLE active_clients (
    client_instance_id TEXT PRIMARY KEY,
    principal_id TEXT,
    session_id TEXT,
    workdir TEXT NOT NULL,
    client_kind TEXT NOT NULL,
    started_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);
~~~

`client_instance_id` は Presence の実行単位を識別する。Web は Browser tab ではなく **WebRoom ごとに1件**登録し、同じ Room に接続する複数タブは同一 Presence を共有する。Room に接続タブがなく、かつ稼働中 worker / Task もない場合は heartbeat を停止し、再接続時に再登録する。A2A は Task ごとに固有 ID を割り当てる。複数 Task が同じ A2A 接続上で並行実行される場合も Task ごとに登録する。

`workdir` は canonicalize して保存する。Windows の separator、absolute path、case 等の表記差を正規化する。

## 4. Unified Lifecycle

全 Client 種別で同じ手順を用いる。

1. 起動・Task開始時に Presence を登録する
2. **30秒ごとに heartbeat** を送り `last_seen_at` を更新する
3. 更新時に同じ workdir の他の active Client を再検索し、Presence view を更新する
4. **有効な workdir が変更された場合**（CLI / Web の `:cd`、`change_workdir_tool`、session restoration 等）は、その時点で新しい workdir を canonicalize し、自身の `active_clients.workdir` を更新してから新しい workdir の peer を再検索する。古い workdir に対する Presence view は破棄する。**ただし Presence だけを更新してはならず、実際に次のターンで使用される Runtime の canonical workdir と同じ値を使う**
5. 正常終了・Task完了・Taskキャンセル時に登録解除する
6. 異常終了・通信断時は **90秒 TTL** 経過後に inactive と判定する

workdir 変更は実行環境の所有者が提供する共通 setter を経由する。CLI では Runtime の workdir、Web では room owner の `WebRoom.base_dir` を正とし、同一 Room の全タブはこの値と単一の Presence view を共有する。A2A では Task ごとに独立した canonical workdir を保持し、Task-scoped setter を使用する。並列 Task の workdir 変更を process-global `os.chdir()` によって永続化してはならず、他 Task の実行 workdir / Presence に影響させない。、`:cd`、`change_workdir_tool`、session restoration がいずれもその setter を呼ぶ。setter は実行環境側の canonical workdir を更新し、同じ変更の一部として Presence row と peer view を更新する。Web worker の一時的な `os.chdir()` は process cwd の操作に過ぎず、room の永続的な workdir 更新とみなさない。worker が cwd を復元しても、次の Web turn は更新後の `WebRoom.base_dir` から開始する。setter の失敗時に Presence だけ先行更新しない。

Heartbeat は LLM / tool の実行やユーザー入力と独立して継続する。CLI / GUI / Web / A2A Task のいずれも同じ方式とする。専用の外部監視 daemon は不要で、各 Client / Room / Task lifecycle 内の軽量 heartbeat scheduler を使う。

Presence の active 判定は `last_seen_at` が TTL 内かどうかだけとし、PID、プロセス開始時刻、OS固有の生存確認は使用しない。期限切れレコードは照会時に無視し、必要に応じて lazy cleanup する。

SQLite にアクセスする Runtime が Client の代わりに heartbeat を記録する場合でも、Client / Task の生存を確認できる lifecycle に結び付ける。単に共有サーバープロセスが動作中という理由で切断済み Browser tab や終了済み A2A Task の heartbeat を更新し続けてはならない。

## 5. Agent Awareness

他 Client の会話内容を自動注入しない。Agent に渡すのは概念的に次の情報だけとする。

~~~text
workspace_presence:
  other_clients_active: true
  count: 1
~~~

Agent は同じファイルの変更リスクを判断できるが、Presence 自体は read / write / cmd / Python を強制 block しない。

## 6. Scope

初期実装は同じ SQLite SessionStore を共有する実行単位に限定する。別DB間の分散 Presence や分散ロックは対象外。A2A の remote peer が別環境で直接編集するファイルは検出できない。

## 7. Failure Rules

- Presence 登録失敗だけで通常処理を禁止しない
- Heartbeat の遅延・停止で TTL を超えた場合は inactive と判定する（実際のプロセス生存とは区別する）
- Heartbeat が再開すれば active に戻り、他 Client を再検索する
- 正常終了時は削除し、crash 時は TTL で回収する
- Presence は外部 IDE / editor / shell の存在を検出しない
- Presence をファイル整合性の保証として扱わない

## 8. Non-Goals

file claim、file lease、workspace lock、OT、CRDT、automatic semantic merge、Git worktree orchestration、filesystem monitoring、cmd / Python write 予測、distributed lock service、background cleanup daemon、other Session content awareness。

## 9. Acceptance Criteria

1. 同一 canonical workdir の CLI / GUI / Web / A2A Task は相互に active Presence を認識できる
2. 30秒 heartbeat / 90秒 TTL を全 Client 種別で共通適用する
3. LLM / tool の長時間実行中も heartbeat が継続する
4. 正常終了・Task完了・キャンセルでは Presence が解除される
5. crash / 切断後は TTL 経過で inactive になる
6. stale Client の heartbeat 再開時は他 Client の Presence を再検索する
7. PID による Client 種別ごとの例外判定をしない
8. CLI / Web の `:cd`、`change_workdir_tool`、session restoration による workdir 変更後、旧 workdir には存在を広告せず、新 workdir の peer を認識できる
9. 同じ WebRoom に複数タブが接続していても Room の Presence row は1件のみであり、workdir 変更時に全タブが同じ Room の Presence view を参照する。タブ切断時は他の接続・worker / Task があれば Room の Presence を維持する
10. 並列 A2A Task は Task-scoped canonical workdir / setter を使い、一方の `change_workdir_tool` や復元が他方の workdir / Presence を変えない
11. Web の `:cd`、`change_workdir_tool`、session restoration が room-aware setter を経由し、`WebRoom.base_dir` と Presence が一致する。worker の一時的 `os.chdir()` と cwd 復元によって次ターンの workdir が巻き戻らない
12. Presence によってファイル操作を強制停止せず、他 Session の会話履歴も自動注入しない
