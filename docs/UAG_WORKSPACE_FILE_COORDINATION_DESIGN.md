# UAG Lightweight Workdir Presence Design

## 1. Purpose

CLI / GUI window / WebRoom / A2A Task が同じ workdir で同時に作業していることを UAG が認識できるようにする。強制排他は行わず、Agent に競合作業の可能性を知らせる advisory Presence とする。

## 2. Principles

- CLI / GUI / Web / A2A Task を同一の最終活動時刻の記録方式で扱う
- A2A の接続相手自体ではなく、UAG 側で実行する Task を登録する
- A2A protocol の通信状態を Presence の生存保証として扱わない
- file claim / file lease / workspace lock は行わない
- cmd / Python / file tool を区別しない
- filesystem monitoring、daemon、external coordination service を導入しない
- 既存 SQLite SessionStore を利用する
- Presence は consistency / security guarantee ではない

## 3. Minimal Data Model

~~~sql
CREATE TABLE active_clients (
    presence_instance_id TEXT PRIMARY KEY,
    owner_kind TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    principal_id TEXT,
    session_id TEXT,
    workdir TEXT NOT NULL,
    client_kind TEXT NOT NULL,
    started_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);
~~~

`presence_instance_id` は Presence 登録単位の固有 ID、`owner_kind` / `owner_id` は所有者（CLI Client / GUI Client / WebRoom / A2A Task）を識別する。`client_instance_id` は個々の Browser tab を含む Client の識別子として別に維持し、Presence ID と混同しない。Web は Browser tab ではなく **WebRoom ごとに1件**登録し、同じ Room に接続する複数タブは同一 Presence を共有する。Room に接続タブがなく、かつ稼働中 worker / Task もない場合は登録を解除し、再接続時に再登録する。A2A は Task ごとに固有 ID を割り当てる。複数 Task が同じ A2A 接続上で並行実行される場合も Task ごとに登録する。

`workdir` は canonicalize して保存する。Windows の separator、absolute path、case 等の表記差を正規化する。

## 4. Unified Lifecycle

全 Client 種別で同じ手順を用いる。

1. 起動・接続・Task開始時に Presence を登録し、`last_seen_at` に時刻を保存する
2. ユーザー入力、ターン開始・終了、tool 実行の開始・終了、workdir 変更時に `last_seen_at` を更新する。定期 heartbeat は送らない
3. 活動時と Presence 照会時に同じ workdir の他の登録を検索し、最終活動時刻を含む Presence view を更新する
4. **有効な workdir が変更された場合**（CLI / Web の `:cd`、`change_workdir_tool`、session restoration 等）は、実行環境の canonical workdir と Presence の workdir / 時刻を更新し、旧 workdir の Presence view を破棄して新しい workdir を再検索する
5. 正常終了・Task完了・Taskキャンセル・WebRoom で接続タブがなく、稼働中 worker / Task もなくなった時に登録解除する
6. 異常終了・通信断では行が残り得るため、照会時に `last_seen_at` を示す。登録があることと現在稼働中であることを区別する。必要に応じて古い行を遅延削除する

workdir 変更は実行環境の所有者が提供する共通 setter を経由する。CLI では Runtime の workdir、Web では room owner の `WebRoom.base_dir` を正とし、同一 Room の全タブはこの値と単一の Presence view を共有する。A2A では Task ごとに独立した canonical workdir を保持し、Task-scoped setter を使用する。並列 Task の workdir 変更を process-global `os.chdir()` によって永続化してはならず、他 Task の実行 workdir / Presence に影響させない。`:cd`、`change_workdir_tool`、session restoration がいずれもその setter を呼ぶ。setter は実行環境側の canonical workdir を更新し、同じ変更の一部として Presence row と peer view を更新する。Web worker の一時的な `os.chdir()` は process cwd の操作に過ぎず、room の永続的な workdir 更新とみなさない。worker が cwd を復元しても、次の Web turn は更新後の `WebRoom.base_dir` から開始する。setter の失敗時に Presence だけ先行更新しない。

定期 scheduler、heartbeat、PID による生存監視は導入しない。長時間の LLM / tool 実行中は時刻が更新されない場合があるため、最終活動時刻は生存保証ではない。一定時間操作のない稼働中 Client と異常終了した Client は時刻だけでは区別できない。

## 5. Agent Awareness

他 Client の会話内容を自動注入しない。Agent に渡すのは概念的に次の情報だけとする。

~~~text
workspace_presence:
  other_clients_registered: true
  count: 1
  last_seen_at: "<timestamp>"
~~~

Agent は同じファイルの変更リスクを判断できるが、Presence 自体は read / write / cmd / Python を強制 block しない。

## 6. Scope

初期実装は同じ SQLite SessionStore を共有する実行単位に限定する。別DB間の分散 Presence や分散ロックは対象外。A2A の remote peer が別環境で直接編集するファイルは検出できない。

## 7. Failure Rules

- Presence 登録や時刻更新の失敗だけで通常処理を禁止しない
- 最終活動時刻が古い場合も、終了済みとは断定しない
- 正常終了時は削除し、異常終了で残った行は照会時などに遅延削除できる
- Presence は外部 IDE / editor / shell の存在を検出しない
- Presence をファイル整合性や実行中であることの保証として扱わない

## 8. Non-Goals

file claim、file lease、workspace lock、OT、CRDT、automatic semantic merge、Git worktree orchestration、filesystem monitoring、cmd / Python write 予測、distributed lock service、background cleanup daemon、other Session content awareness。

## 9. Acceptance Criteria

1. 同じ canonical workdir の CLI / GUI / Web / A2A Task の登録と最終活動時刻を照会できる
2. 起動・入力・ターン・tool・workdir 変更時に時刻を更新し、定期 heartbeat を使わない
3. 長時間処理中や無操作時の時刻は更新されなくてもよく、生存保証と誤認しない
4. 正常終了・Task完了・キャンセル・WebRoom で接続タブがなく、稼働中 worker / Task もなくなった時に登録解除する
5. 異常終了後の残存登録は、時刻を示し、必要に応じて遅延削除する
6. PID や Client 種別ごとの特別な生存判定をしない
7. CLI / Web の `:cd`、`change_workdir_tool`、session restoration 後は実行 workdir と Presence が一致する
8. 複数タブは WebRoom 単位の1登録と Presence view を共有する
9. 並列 A2A Task は独立した workdir / setter / Presence を持つ
10. `presence_instance_id` と `owner_kind` / `owner_id` を Client ID と混同しない
11. Presence はファイル操作を強制停止せず、他 Session の会話履歴も自動注入しない
