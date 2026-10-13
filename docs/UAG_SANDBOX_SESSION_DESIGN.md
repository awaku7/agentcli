# UAG セッション常駐型・クロスプラットフォーム Sandbox 設計

- Status: **Design / 未実装**
- Date: 2026-10-14
- Scope: CLI / GUI / Web / A2A、Windows / Linux / macOS
- Priority: Enterprise E0 の一部。ローカル実行の任意 Sandbox は追加要件
- Related: [Enterprise E0 設計](UAG_ENTERPRISE_PLATFORM_DESIGN.md)、[実装ロードマップ](plans/IMPLEMENTATION_ROADMAP.md)、[Web Room 並列処理](WEB_ROOM_CONCURRENCY.md)

## 1. 決定事項

1. UAG 本体の Tool 実行インターフェースと Session 管理を OS 非依存にする。
2. Sandbox を **Tool Call ごとではなく、認証済み Principal と実行スコープ（Session / Room / A2A Task）の組ごとに確保・再利用**する。再利用中は承認された作業領域・インストール済み依存関係などを保持する。ただし認可取消・秘密情報混入・実体障害があれば安全性を優先して破棄する。
3. 全エントリーポイント（CLI / GUI / Web / A2A）が共通の **ExecutionBroker** と **SandboxSessionManager** を使う。Host ごとの専用ディスパッチを増やさない。
4. ローカル CLI / GUI は Sandbox を任意とし、既存の直接実行を既定とする。リモート Web / A2A は Enterprise E0 の隔離要件を優先し、必要なバックエンドが無ければ **実行拒否**する。
5. Tool の「副作用区分」「認可結果」「実行区分」「隔離強度」を独立に扱う。**Sandbox 内だから何でも許可するわけではない**。
6. Microsoft MXC は最初に評価する実装候補とするが、UAG の公開インターフェースを MXC 固有型に依存させない。
7. Security Policy、認証、承認、秘密情報管理、実行制限は **信頼できる Broker 側**で強制する。Sandbox 内 Worker の自己申告を信頼しない。

本書は採用方針と受け入れ条件を定義するものであり、MXC の全バックエンドが同一のライフサイクル・隔離強度・OS 機能を提供するという保証ではない。

## 2. 目的と対象外

### 目的

- 会話中の一連の操作で同じ Sandbox 作業領域を使う。
- Windows / Linux / macOS の違いを Sandbox Backend Adapter に閉じ込める。
- 別 Principal / Project / Room / Task 間で Sandbox の可変状態を共有しない。
- Tool、MCP、Plugin、Skills、Sub-Agent に共通の実行制御を適用する。
- Sandbox 停止・認可失効・Broker 再起動時に、安全に失敗または回収できる。
- ローカルの既存機能を不用意に変更しない。

### 対象外（初期導入）

- 異なる OS 上で全てのコマンドが同じ意味で動くこと。**API は共通、使用可能な機能は Capability 判定**とする。
- VM 相当の強固な隔離を軽量プロセス Sandbox で代替すること。
- プロセス状態やメモリの永続保存、Sandbox 内プロセスの再起動後の完全復元。
- すべての物理デバイス、ホスト GUI、任意の認証情報へのアクセス。
- Sandbox 内からホストの Docker ソケット、管理 API、ユーザーホームを直接操作すること。
- 今回の **設計文書 PR** での実行経路の変更。

## 3. 概念上の構成

~~~text
CLI / GUI / Web / A2A
          |
          v
    Common Tool Dispatch (tools.run_tool)
          |
          v
  ExecutionBroker
  - Trusted TurnContext / IdentityContext
  - UnifiedPolicy / ToolPolicy
  - Tool ExecutionClass / SecurityProfile
  - Authorize + limit + audit
          |
          +--> Local-host-pure (明示的にローカル限定・監査済みの純粋処理)
          |
          +--> Brokered control plane (専用操作のみ)
          |
          +--> SandboxSessionManager --> Backend Adapter
          |                                   |
          |                                   +--> MXC Worker / native stateful
          |                                   +--> future OCI/gVisor / Hyper-V VM
          |
          +--> Deny
~~~

Local-host-pure は、**ローカルの信頼済み CLI / GUI に限定**した監査済みの純粋処理専用経路であり、Remote の第4の実行先ではない。Enterprise E0 の Remote ingress では、あらゆる Tool Call を **Sandbox / 狭い専用 Broker / Deny** のいずれかに分類する。日時取得等の純粋な管理サービスを Remote に提供する場合も狭い Brokered Service として実装し、一般 Tool Runner の Host 直接実行を許さない。この区別は [E0 設計](UAG_ENTERPRISE_PLATFORM_DESIGN.md) の隔離要件に従う。

## 4. エントリーポイントと Sandbox の所有単位

| Entry point | 必須の Scope ID | Sandbox 既定 | 維持・終了の契機 |
| --- | --- | --- | --- |
| CLI (uag) | CLI runtime session UUID | local: off | CLI Session 終了、明示破棄 |
| GUI (uagg) | GUI 会話 ID + runtime 所有情報 | local: off | 会話の切替時は切替先へ、会話削除で破棄 |
| Web (uagw) | **room_id + principal_id** | 明示的 local-only: optional / 隔離対象 Remote: required | 認可済み Room の存続中に Principal ごとに保持。削除・Private Room TTL・認可取消で破棄 |
| A2A (uaga) | **task_id** | remote tools: required | Task の完了・取消・期限切れで破棄 |

- Web の一時的な WebSocket 切断は Room 終了ではない。再接続しても同一 Scope の健全な Sandbox を再利用する。
- 同じ Principal/Project でも **異なる room_id の Sandbox は共有しない**。同じ Shared Room でも Principal が異なれば別 Lease を割り当て、Private / shared Room の可変状態は共有しない。Room 自体が共有資産でも、Sandbox 内のファイル・プロセスは自動的に他参加者へ共有しない。
- A2A の opt-in SessionStore が無効でも **task_id 必須**。Task が異なれば会話履歴が似ていても Sandbox は共有しない。現行 A2A の単一 Bearer Token は個々の利用者の識別情報ではないため、認証済み Server 側 Service Principal として Scope を生成する。利用者別 Principal を必要とする構成では、事前に信頼できる呼出元識別・認可を追加し、Client 提供の owner/user ID を受け入れない。
- CLI の新規 Session は新しい Scope とする。保存済み Session をロードした場合は所有者・Workspace を再検証し、**同一稼働インスタンス内の健全な既存 Lease** に限り再接続する。CLI 終了後の会話履歴ロードは新規 Sandbox が必要で、終了済みプロセス状態の復元を装わない。会話履歴の Session ID と稼働中 Sandbox Lease は異なる。
- GUI の会話切替でも同様。GUI プロセス内で複数の会話の Lease を保持できるが、切替時は Scope を再検証する。会話を消したときの Sandbox 破棄と、履歴だけを残す動作は分ける。
- CLI/GUI で Sandbox off のときは SessionManager にリソースを作らない。
- Sub-Agent / background Job は親 Scope と権限の縮小を基本とし、長寿命 Job は親終了後の孤立実行を許可しない。独立 Scope が必要な場合は別途定義する。
- ローカルからの接続でも、認証付き Multi-user Web（社内ネットワークのみを含む）や外部公開 Web / Remote A2A には E0 隔離を強制する。ID モードが local、Host の bind address が loopback、または今回の Request の送信元が内部 IP であることだけを根拠に Remote 要件を解除しない。

### 4.1 実行スコープの厳密な識別

~~~python
@dataclass(frozen=True)
class SandboxScope:
    deployment_id: str
    principal_id: str
    project_id: str
    scope_kind: Literal[
        "cli-session", "gui-conversation", "web-room", "a2a-task"
    ]
    scope_id: str             # CLI UUID / GUI conversation / Web room / A2A task
    session_id: str = ""      # 任意の追加制約。Web room_id / A2A task_id の代替不可
~~~

- Scope は認証済みの Host 側 Context と Session 管理から生成する。LLM、Tool 引数、Browser Payload は Scope の権限根拠にしない。
- 文字列を連結して Key を作らず、型付き正規化データを構造化シリアライズして識別する。空の必須 ID・重複・形式異常は拒否する。
- リースには Scope の全項目に加え、Backend、Policy Revision、認証・権限の有効性を照合する Binding Revision を記録する。
- Shared Room 参加者の切替時は、実行主体を毎回再認証・再認可し、必要に応じて Lease をローテーションする。別 Principal の実行に、以前の Principal が作成した可変 Sandbox 状態を引き継がせない。
- Session ID の再利用・復元時も、保存されている Lease ID をそのまま信頼せず、Server 側 Scope Binding を検証する。

## 5. 共通インターフェース

実装言語は Python。以下は概念契約であり、初回 PR で確定する。

~~~python
class ExecutionClass(Enum):
    LOCAL_HOST_PURE = "local_host_pure"  # Remote ingress では選択禁止
    BROKERED = "brokered"
    SANDBOX = "sandbox"
    DENY = "deny"


@dataclass(frozen=True)
class SandboxCapabilities:
    persistent_worker: bool
    native_stateful_exec: bool
    subprocess_confinement: bool
    filesystem_policy: bool
    network_policy: bool
    resource_limits: bool
    interactive_pty: bool
    gui_isolation: bool
    isolation_level: str


class SandboxBackend(Protocol):
    def probe(self) -> SandboxCapabilities: ...
    def create(self, spec: "SandboxSpec") -> "SandboxHandle": ...
    def start_execution(
        self, handle: "SandboxHandle", request: "ToolExecutionRequest"
    ) -> "SandboxExecutionHandle": ...
    def wait_execution(
        self, execution: "SandboxExecutionHandle", *, timeout_seconds: float
    ) -> "ToolExecutionResult": ...
    def cancel_execution(
        self, execution: "SandboxExecutionHandle", *, reason: str
    ) -> "CancellationResult": ...
    def terminate(self, handle: "SandboxHandle") -> None: ...
    def health(self, handle: "SandboxHandle") -> bool: ...
~~~

**create → start_execution / wait_execution / cancel_execution (N 回) → terminate** が UAG の契約である。実行用 Handle は **Lease Handle とは別の opaque ID** とし、Broker が request_id と合わせて現在の実行を追跡する。wait_execution() がブロックしても、別制御 Channel から cancel_execution() を呼べなければならない。cancel_execution() はその実行と子孫プロセスの停止・後始末完了を確認できる場合だけ成功扱いにし、未完了・Timeout・Backend 未対応時は Lease 全体を停止・破棄する。**wait_execution() は Cancel/Lease 終了を含む全終了経路で規定の上限時間内に明示的な終端結果（completed / cancelled / terminated / failed / timeout）を返す**。応答しない Backend/IPC に対しては Broker が自身の待機期限を強制し、該当 Lease を隔離・使用禁止にして終了結果を呼出元へ返す。古い実行が停止したことを確証できるまで新規 Tool Call を同 Scope の Lease に通さず、ワーカーの掃除は別途追跡する。**実行待機のロックは Cancel 後も有限時間内に解除**し、結果待ちスレッドを永続的に塞がない。単一 Worker 内の実行を選択的に止めることができない Backend は、**Stop 時に Lease を破棄する能力**として明示し、保持できるとは約束しない。Backend は以下のいずれかで実現する。

1. **Native stateful**: provision / start / exec / stop / deprovision に実際に対応する MXC Backend を使用。
2. **Persistent Worker**: 1回の隔離付き spawn で専用 RPC Worker を起動し、同じ隔離されたプロセスツリー内で Tool を複数回実行。生存 Worker と作業領域を Session に紐付ける。
3. 上記のいずれも、安全なプロセス生成・子プロセス封じ込め・終了処理を検証できない場合は **unsupported**。ホスト直接実行にフォールバックしない。

SandboxHandle は外部への公開 ID ではない。Capability は実際の Backend/OS/Version/Policy で検証し、宣言だけでは利用許可しない。SandboxManager は Backend オブジェクトではなく Host 側の記録から所有 Scope を照合する。

## 6. SandboxSessionManager

### 6.1 Lease と状態遷移

~~~text
ABSENT -> PROVISIONING -> RUNNING -> TERMINATING -> DESTROYED
                         |                 ^
                         +---- FAILED -----+
~~~

- 初回の許可された Tool Call で遅延作成する。
- RUNNING の間は同じ Lease を再利用し、作業領域や一時的な追加依存関係を保持する。
- Scope ごとに排他的な Lease 作成を保証し、同時開始しても Sandbox が二重生成されないようにする。Scope の中には Principal ID と認可世代を含め、同一 Room の他利用者と共有しない。
- Scope 内の Tool Call は初期実装では直列化する。並列化は Backend の独立子プロセス制御と資源制限の実証後に検討する。
- User による Stop は **現在の Tool/Turn** を中断する操作で、必ずしも Session の終了を意味しない。**個別 Execution Handle と別制御 Channel**から Cancel し、子孫プロセス停止と Broker/Worker 状態の整合性を確認できた場合のみ Lease を維持する。個別 Cancel 非対応・確認不可なら Lease を破棄する。セッションは引き続き有効でも、Sandbox 状態は失われうる。
- 異常終了・安全な状態を判断できない中断時は Lease を隔離・破棄する。**状態消失を Session UI/LLM に明示し、その失敗した Tool を自動再実行しない**。次の Tool 実行に進む前に、クリーンな Sandbox への移行と作業ファイル消失の扱いを確定する。残存プロセスや未確定の外部副作用を「正常終了」と扱わない。
- Sandbox に平文 Credential を注入した瞬間に Lease を **tainted / non-reusable** として確定し、他の Tool Call と Snapshot 作成を直ちに拒否する。ただし当該 Credential を必要とする **現在の操作は許可された時間内で継続**させる。操作の成功・失敗・Cancel・Timeout のいずれかで終了した時点で Credential を取り除き、当該 Lease を破棄（または検証済みの完全クリーン状態へリセット）する。**完了後の次の Tool Call より前**に破棄・検証を完了する。操作が終了しないときは Timeout で強制終了し、未回収の Lease は隔離・利用不可とする。同じ Session が生きていても秘密情報保護を優先する。

### 6.2 セッション終了の定義

「Session が生きている間」は **UAG が管理する有効な Session / Room / Task の存続期間** を指す。単なる WebSocket 切断・一時的な GUI 非表示・ターン終了では破棄しない。

- 明示的な終了・削除、認証取消、Project/Room 権限喪失、Session TTL/期限切れ、管理者による Kill Switch で破棄。
- Session 存続中に短い idle timeout だけで安易に破棄しない。運用上の最大存続期間・メモリ上限・容量上限を超えて破棄する場合は、利用者に **状態消失** を明示し、次回 Tool Call を透過的に再実行しない。管理者が定めたハード制限は Session 存続より優先する。
- SessionStore の「履歴保存期限」と「生存する実行 Lease」は別。履歴が残っていても Sandbox が残る保証はしない。
- Broker 再起動後は既存 Lease を列挙し、Scope・Backend 実体・Owner・Revision を照合して安全なものだけ再接続。それ以外は回収する。**プロセス型 MXC Worker の再接続可否は未検証**であり、再起動後の継続を前提としない。
- 初期単一インスタンス実装では、単一 Owner と process/host fencing を前提とする。他 Node の Lease を誤って操作・再利用しない。**複数Webインスタンス構成を単一インスタンスの実装で E0 完了とはみなさない**。複数インスタンス運用には、共有 Lease Registry、Scope ごとの原子的 Owner Claim、Owner Generation / Fencing Token、実行 Request の Owner へのルーティング、所有権の変更に伴う旧 Worker の失効・Revoke 伝播、Crash/Partition 時の Orphan Recovery が必要。これらを満たさないときは同一 Room/Scope の並列実行を拒否する。

### 6.3 永続レジストリ（秘密情報を持たない）

保存対象: opaque lease_id、typed scope fingerprint、backend、backend opaque handle reference、state、owner instance、generation/fencing token、creation/heartbeat timestamps、policy revision、cleanup status。

保存禁止: API Key、OAuth Token、平文 Credential、任意の Tool 引数/本文、作業ファイルの内容、秘密を含む stdout/stderr。

SQLite は初期の単一ホスト・単一 Owner 実装として使用可能。Crash 後の orphan 削除、再起動時の整合性照合、TTL と回収待ち状態を必須とする。別 Host からの共有ストアや単一 SQLite ファイルへの同時書込みを **分散 Owner 保証と誤認しない**。共有 Owner Claim は同一 Scope に対して世代を単調に更新し、期限切れ Lease を回収しても旧 Owner からの遅延書込み・Tool 実行を Fencing Token で拒否しなければならない。

### 6.4 履歴ロードと Sandbox 再接続

**会話履歴の復元、Session ID の再利用、Sandbox 実体の再接続、Workspace の復元を別々の処理とする。** 保存されたメッセージに SandboxHandle、承認の再利用、稼働中プロセスの存在を示す権限を与えない。

| 履歴ロード時の状態 | Sandbox 側の動作 |
| --- | --- |
| UAG が所有する同一 Scope の RUNNING Lease が健全に存在 | 所有者・Project・Workspace Binding・Policy Revision・Owner Generation を再照合して接続 |
| Lease が無い、正常終了済み、CLI / GUI アプリケーション再起動後 | **新しい Sandbox を遅延生成**。作業領域は承認済み Project Revision から初期化し、過去の未公開ファイル・インストール済み依存・常駐プロセスは復元しない |
| Lease の Crash / 期限切れ / Policy 変更 / Cancel 後の強制破棄 | 前の Lease を使用禁止にして新規生成。**状態消失と必要な環境再構築を UI/LLM に通知** |
| 別 Principal / Project / Room / Task に履歴を取り込む | **元の Lease に絶対に接続しない**。履歴の内容も別途アクセス認可し、許可された現在 Scope の新しい Workspace を使用 |
| Web の一時切断と同じ Room の正当な再接続 | Lease が健全なら再接続。WebSocket 接続 ID ではなく信頼済み Room + Principal Binding で判断 |
| A2A で完了した Task の履歴・Checkpoint を参照 | Task Lease は完了時に破棄済み。新しい A2A Task は別 Scope の Sandbox を作る |

- CLI の :load / :sessions load と Web の Session 切替は、**Sandbox ID を履歴からロードして無条件に再利用する操作ではない**。現行 src/uagent/util_cmd_session.py はメッセージや最後の Workdir を復元するが、その Workdir は **実行環境への信頼されたアクセス許可ではない**。Target Session の所有者・Project 境界と、現在許可される Workspace を検証する。異なる場合は Load を拒否するか、既存権限の範囲へ安全に読み替える。
- 再接続できなかったときは自動で以前の Tool Call を再実行しない（削除、メール送信、Git Push 等の副作用を重複させない）。保存した会話の「成功した」という記録は過去の結果であり、現在の Sandbox の実行状態ではない。
- 新規 Sandbox に復元するのは **明示的に Export/Commit 済みの Workspace 内容**のみ。中断前の未公開ファイル・仮想環境・依存ライブラリ・プロセス・ブラウザ Cookie・Port Forward は自動復元しない。
- 将来的な環境 Snapshot / Checkpoint は別機能として設計する。Scope、Ownership、Policy Revision、Artifact 完全性、Secret 混入、Malware 検査に合格した Snapshot のみ復元を許可し、履歴テキストから Snapshot を選択できない。**初期実装は Snapshot 無し**。環境構成・Snapshot 参照の保存方式と復元手順は **6.5** で別途定義する。
- 履歴ロードで Sandbox が切り替わるときは現在の Execution が終了・取消済みであることを確認し、旧 Lease を勝手に破棄しない（他の生存 Session が正当に保有している場合を含む）。異なる Workspace/Scope に混在した実行中状態を作らない。

### 6.5 環境スナップショットと履歴の関係（将来機能の契約）

**会話履歴には復元参照情報を残すが、Sandbox 実体・秘密情報・OS の実行状態を保存しない。** Snapshot 生成や復元は初期導入の対象外。本節は今後実装する際のデータ契約を定める。

| 保存場所 | 保持する情報 | 権限・目的 |
| --- | --- | --- |
| SessionStore 内の構造化イベント | opaque `snapshot_id`、Manifest digest、Session/Scope Binding、作成時点、`ready` / `unavailable` 等の状態 | 履歴ロードから候補を見つける。会話メッセージ本文には展開しない |
| Snapshot Catalog / Manifest | OS・CPU architecture・Backend/バージョン、base image digest、Python/Runtime 版、許可された依存構成の digest、Project Workspace Revision、Policy Revision、所有 Scope、作成日時、保持期限、機密検査結果、署名/検証情報 | 現在の環境で復元可能か、安全かを検査 |
| アクセス制限付き Artifact Store | 許可された Workspace の差分、対応 Backend が安全に取得した環境イメージ等の Snapshot 本体 | 実際の復元。履歴 DB と物理的・論理的に分離、暗号化と保存期間管理 |

SessionStore に書くイベント例（**概念スキーマ・未実装**）:

~~~json
{
  "kind": "sandbox_snapshot_reference",
  "schema_version": 1,
  "session_id": "opaque-session-id",
  "scope_binding": "trusted-scope-fingerprint",
  "snapshot_id": "opaque-snapshot-id",
  "manifest_digest": "sha256:...",
  "workspace_revision": "approved-revision",
  "availability": "ready"
}
~~~

- **履歴データは権限根拠にならない。** 上記イベントは信頼された Broker のみが SessionStore へ書き込み、LLM/ユーザー編集可能なメッセージ、Tool Result、外部から取り込んだ JSON 内の Snapshot ID では復元しない。Scope と Snapshot の紐付けを Catalog 側で改めて検証する。
- **構成情報と Snapshot を区別する。** Snapshot 未作成なら有効な `snapshot_id` を発行せず、必要に応じて秘密を含まない `environment_manifest` を記録し、状態を `not_snapshotted` とする。過去に実行した環境を自動的に再現できると表示しない。
- Manifest の値はホワイトリスト方式で収集・最小化し、環境変数一式、任意の Host 絶対 Path、API Key、Token、Cookie、Proxy 認証情報を保存しない。パッケージ名、Private Registry URL、設定値にも秘密が混入し得るため、無検査の `pip freeze` や環境ダンプをそのまま保持しない。
- Snapshot の種類を `workspace`（承認されたファイル）と `environment`（再現可能な依存関係や Base Image 等）として区別する。**実行中プロセス、Socket、Python 変数、GPU コンテキスト、ブラウザログイン状態は初期の Snapshot 対象外**とする。
- 作成はユーザー明示操作または承認済み管理ポリシーのみ。初期は明示操作が既定で、Tool ごとの Snapshot や全セッションの無条件自動保存はしない。Session 終了時の自動保存は明示的なポリシー、容量上限、バックグラウンド Job の扱いを決めてから導入する。
- 作成時は Scope の Tool 受付を一時停止し、実行中 Tool/子孫プロセス、Background Job、Workspace 書込みを安全なチェックポイントに収束させ、整合性ある状態を取得する。Plaintext Credential を受け取った tainted Lease、機密検査失敗、継続中の不明な副作用がある場合は拒否する。
- Artifact 保存、Manifest 確定、SessionStore 参照公開の順序を定義し、**内容と整合性検証が完了した Snapshot だけ `ready`** とする。中断・保存失敗・孤立 Artifact は `failed` / `unavailable` として回収する。参照だけ存在してデータが無い状況を正常と扱わない。
- 履歴ロード時は、(1) 健全な同一 Scope の生存 Lease 再接続、(2) Snapshot Catalog からの復元候補提示、(3) 新規クリーン Sandbox の順に判断する。Snapshot は **現在の Principal/Project/Room/Task 権限、Policy Revision、Workspace Revision、Backend/OS/architecture 適合性、Manifest Hash/署名、保存期限、Secret/Malware 検査**を毎回通した後に明示承認を得て復元する。別 Scope への移植は通常の履歴 Load で行わず、別途認可された Export/Import が必要。
- Snapshot は作成時点の状態であり、会話の最新メッセージ時点と一致するとは限らない。復元対象の時刻・差分・未公開変更の消失を示す。**履歴に記録された Tool Call を再実行しない**ため、削除・Git Push・メール送信などの副作用も再発生しない。
- Artifact とその Catalog には保存期限、個数/容量制限、手動削除、Project 削除・権限失効、暗号鍵管理、参照切れ時の GC を定義する。履歴が残っていても Artifact が破棄済みなら `unavailable` と表示し、黙って別の Snapshot を選ばない。

**段階的な実装:** ① 非秘密の Environment Manifest / SessionStore イベント契約、② Snapshot Catalog + Artifact Store、③ Backend の安全な保存と再生成、④ CLI/GUI/Web/A2A の履歴復元連携。**本 PR は設計だけで、実際の Snapshot 作成・復元は行わない。**

## 7. Tool 実行分類と権限

既存の src/uagent/tools/tool_policy.py は READ_ONLY / IDEMPOTENT_WRITE / EXTERNAL_SEND / DESTRUCTIVE を区別する。これは **実行環境の安全性を示す分類ではない**。例えば get_env、read_file、http_request GET は READ_ONLY でも、Host の情報を読み取れるため一般 Host-safe ではない。

評価順序:

1. 信頼済みの Entry Point / Principal / Project / Room / Task を確認する。
2. UnifiedPolicy・Role・ToolPolicy による **認可・副作用区分**を評価する（拒否なら即終了）。
3. Tool 名だけでなく引数・実際の機能・MCP 展開先・ネットワーク宛先を考慮して ExecutionClass を決める。
4. 要求する隔離強度と Backend Capability を照合し、実行不可能な操作は **確認画面の前に拒否**する。
5. 確認が必要な操作は Host UI / Broker で確認し、直前に Policy Revision と権限を再検証する。
6. 許可された Scope の Lease へルーティングして実行する。
7. 結果・Artifact・監査ログを制限付きで回収する。

| Tool の性質 | Local Sandbox on | Remote ingress |
| --- | --- | --- |
| 監査済みの純粋計算・日時 | Local-host-pure または Sandbox | **狭い Brokered Service** または Sandbox。Host 直接実行は不可 |
| Shell / Python / Git / コンパイラ / ファイル処理 | Sandbox | **Sandbox 必須** |
| HTTP / Web / Browser / MCP / Plugin / Skills | Policy 審査後 Sandbox または専用 Broker | 適切な隔離または専用 Broker。直接 Host への迂回は禁止 |
| 認証・Policy・管理・監査などの管理操作 | 専用 Broker | 権限を絞った Broker、または Deny |
| Device / USB / Bluetooth / Host Desktop | 個別 Policy / 互換性判定 | **Deny 既定**。専用 Device / GUI Broker は別設計 |
| 未知の Tool、動的ロードされた未分類 Tool | 分類未完了なら保留または拒否 | **Deny 既定** |

- LLM による副作用の確認は Sandbox の権限昇格を意味しない。
- Tool の動的ロード・MCP 子機能・プラグインの内部サブプロセスにも同じ Policy を適用する。ラッパー Tool だけのチェックで完了としない。現行 tools.run_tool() 以外から Runner を直接呼ぶ経路、内部 Helper、Auto-pilot / Sub-Agent / Skills、Web API / WebSocket、LLM が発火させるホスト操作を調査し、Broker を迂回できる Remote 実行経路を塞ぐ。
- 既存 ToolPolicy の未登録 Tool は IDEMPOTENT_WRITE、EnterprisePolicy の未設定 Rule は allow が既定であり、**これらを Remote Sandbox 許可の根拠にしてはならない**。隔離対象 Remote では明示的に登録・審査された Tool/機能だけを許可する。
- 認証要求、確認ダイアログ、ユーザーとの会話、Identity/Policy 管理は Sandbox 内 Tool Runner の任意コマンドとして起動せず、独立の Host 制御 Channel を使う。
- Trusted Broker の Host-pure 処理はホスト OS へアクセスできる汎用 Tool Runner では実行しない。許可対象を個別監査する。
- 承認が必要な操作は UAG の Host UI (CLI / GUI / Web) で確認する。Sandbox 内 Worker が承認状態を偽造できないようにする。

## 8. OS・Backend 選定

MXC は Windows / Linux / macOS 対応の共通 SDK を持つが、Backend ごとに Stateful Lifecycle と安全性が異なる。下表は設計時点の **候補**であり、採用可否は Probe と実機テストの結果で決める。

| OS | 軽量 MXC 候補 | 永続実行の方針 | リモート高リスク用途 |
| --- | --- | --- | --- |
| Windows | ProcessContainer | 隔離された長寿命 Worker の可否を検証 | Hyper-V 隔離 VM/Container 等の強隔離 |
| Linux | Bubblewrap | Persistent Worker の子プロセス・IPC・終了処理を検証 | OCI + gVisor 等 |
| macOS | Seatbelt | Persistent Worker の子プロセス・IPC・終了処理を検証 | 標準軽量 Backend を前提にしない。互換の強隔離が無ければ拒否 |

- Bubblewrap / Seatbelt は通常の spawn/one-shot 方式であり、MXC の native stateful lifecycle がそのまま利用できるわけではない。
- ProcessContainer の利用可能 OS、AppContainer 設定、子プロセス起動能力は実際の MXC バージョンで検証する。
- **軽量プロセス Sandbox は、悪意のある多数のリモート利用者向け VM 隔離と同等ではない**。SecurityProfile ごとに最低隔離強度を定義し、それを満たさない Backend を選ばない。
- MXC ライブラリと UAG Python の連携は、初期 PoC では MXC Node SDK v1 を用いた Host 側小型 Adapter プロセスを候補とする。Node SDK への依存は Adapter に限定し、UAG の Plugin API には出さない。
- 利用可能な Backend が無い場合は、Local opt-in なら起動失敗を明示し、Remote は実行拒否する。自動的に無隔離へ切替えない。
- Windows ネイティブコマンドは Linux/macOS で使えない場合がある。API を統一しても Tool の OS 依存性は Capability で判定する。
- macOS Seatbelt は任意 Hostname / CIDR / Port ごとの直接 Egress 許可・拒否ができない。厳密な宛先制御が必要な場合は、実際に強制可能な別 Network Broker / Backend を要求する。プロキシ設定だけを安全な Egress 強制の証拠としない。

### 8.1 実装前の技術的検証ゲート

Native stateful でない MXC Backend に対し、単に spawn が成功しただけで「セッション常駐 Sandbox 対応」と判定しない。以下を検証する。

- Sandbox 内 Worker が複数リクエストを受信でき、各 Tool から生成した子孫プロセスまで同じ Sandbox Policy に閉じ込められる。別のプロセスを生成する Shell / Python / Git / Binary Tool が禁止された Host Namespace に抜け出さない。
- Worker を侵害・停止・二重起動しても Host 制御 API や別 Scope のデータへアクセスできない。
- 標準入出力・制御 IPC の寿命、閉塞、再接続、出力上限と Timeout を扱える。
- Worker および子孫プロセスが Stop / Crash / Session 終了後に残留しない。
- OS ごとの Network / Filesystem / Resource Policy を、実際に違反する試験で確認する。

どれかを満たせない環境では Persistent Worker Backend を **unsupported** とする。

## 9. RPC と Tool 実行境界

Broker と Worker は専用 IPC を使う。Protocol はバージョン付き・構造化・サイズ上限付きとし、実装詳細は特定 OS に依存させない。

~~~json
{
  "version": 1,
  "request_id": "opaque-request-id",
  "operation": "execute",
  "tool": "python_exec",
  "args": {"code": "print(1 + 1)"},
  "limits": {"wall_seconds": 30, "output_bytes": 65536}
}
~~~

- Scope / Principal / Privilege は Worker からの自己申告では決めず、Broker が **接続に結び付けた認可済み Lease** から解決する。
- 受信 Worker を信頼しない。返信 JSON は非信頼データとして検証し、サイズ・形式・Artifact 参照を制限する。
- Host 側の各 Tool の run_tool() を Sandbox へ無差別に複製しない。実行に必要な Module/Capability のみを明示投影する。
- stdout と Protocol Channel は分離する。Tool 出力が制御フレームに紛れ込まないようにする。
- 信頼できない任意コードは Worker の保護領域で直接評価しない。必要な隔離を継承する子プロセスに分離する。
- Toolbox の拡張・アップロード・パッケージインストールは Sandbox 領域だけに限定する。

## 10. ファイル・ネットワーク・秘密情報・結果

### ファイルシステム

- Scope 専用の Workspace 投影を使用する。Host Root、認証ファイル、任意の Home、UAG の管理設定、Docker Socket 等は渡さない。
- 初期設定は必要ファイルの **copy-in / validated copy-out** を優先し、直接マウントは読み取り専用を原則とする。
- 書き戻しは Broker が認可済み Project 範囲へ明示的に反映。Path Traversal、Symlink、Hardlink、Archive Slip 等を検査する。Sandbox 側の作業中変更は直ちに Host の Project ファイルへ反映されたとみなさない。
- 作業ファイルは Session 内の複数 Tool 間で保持するが、別 Scope に引き継がない。
- **Workspace 同期方式**を初期実装で固定する。原則は開始時に承認済み Source Revision を copy-in し、複数 Tool は同一 Sandbox Workspace を参照する。Host 側への公開は明示的な export/commit で行い、対象パス・Host 側の更新世代・差分衝突・原子的書き込みを検証する。別の GUI / CLI / Room が同じ Project を変更した場合、上書きではなく競合として扱う。
- CLI の :cd、GUI の Workspace 変更、Web の Project/Root 変更で既存 Lease を別 Workspace に付け替えない。Scope の Project Binding を再検証し、新しい Lease を作成・既存を破棄する。

### ネットワーク

- 既定は egress deny。宛先、DNS、proxy、private/link-local/metadata 宛先、接続数を Policy で制限する。
- Tool が外部 API を使う場合は、許可された Destination と Credential Scope を毎回確認する。API 操作を専用 Broker にする場合も、汎用 Host HTTP Client と任意 Credential の組み合わせを許可しない。
- Proxy / Firewall 制御を Backend が強制できない場合は「許可済み」と扱わない。

### 秘密情報

- Host 側 Credential Store を丸ごとマウントせず、Host 環境変数も引き継がない。
- 認証付き操作は、可能な限り **Broker 経由の短寿命認可**で行い、秘密の平文を Sandbox へ渡さない。
- 平文 Credential を Sandbox へ渡した場合は、**注入直後に tainted 状態へ遷移し、新規 Tool を禁止**する。許可された現在の操作が成功・失敗・Cancel・Timeout で終わるまでは継続可能とし、終了直後に Credential を撤去して Lease 全体を破棄する（または書込み可能な全状態とプロセスツリーが完全に消去されたことを検証）。**次の Tool Call には再利用しない**。E0 の制約と同様、長時間終了しない操作には期限を設ける。

### 結果

- stdout/stderr、画像、生成物、ツール結果、タイムアウトと例外を上限制御する。
- Tool Result は既存の Result Manager / Artifact Manager / SessionStore の秘匿化・縮小・保存境界を通す。
- Sandbox が返す相対 Path は認可済み Export 領域に解決し、Host 任意 Path へ直接書き込まない。

## 11. 設定と安全な既定値

提案する CLI 形式（**まだ実装されていない**）:

~~~text
uag  --sandbox off           # Local 既定
uag  --sandbox auto          # Policy と利用可能な Backend を照合
uag  --sandbox mxc           # MXC Adapter を明示
uagg --sandbox auto
uagw --sandbox auto
uaga --sandbox auto
~~~

- 新規設定は可能な限り単一の共通引数にまとめ、Backend 固有の細かなオプションを環境変数として大量追加しない。
- Remote profile は sandbox=off を許可しない。CLI から指定された値と Deployment Policy のうち **厳しい方**を採用する。隔離対象は [Enterprise E0](UAG_ENTERPRISE_PLATFORM_DESIGN.md#31-enterprise-phase-e0-remote-execution-isolation) に従い、認証付き Multi-user Web（イントラネットを含む）、外部公開 Web / WebSocket、ツールを使う Remote A2A。**SecurityProfile は起動時に信頼できる管理設定として確定**し、リクエストの IP・Host header・ブラウザ指定値から弱い Profile を選ばない。
- "auto" は OS 判定だけで無条件許可せず、必要な IsolationLevel / Capability / Enterprise Policy を照合する。
- Local GUI/CLI の既存直接実行は Feature が有効になるまで変更しない。
- 有効化時に Worker/Backend の自動インストールを行う場合も、管理者確認・署名/Hash 検証・配布経路の制約を必要とする。信頼できない SDK や実行ファイルを自動導入しない。

## 12. 既存 UAG 実装への組み込み箇所

| 現行要素 | 変更方針 |
| --- | --- |
| src/uagent/tools/__init__.py / run_tool() | 共通 Policy 判定後に ExecutionBroker に振り分け。Host 直実行経路の迂回が無いことを保証 |
| runtime/policy_engine.py / ToolPolicy / EnterprisePolicy | 既存の副作用・認可を活用し、ExecutionClass と Backend 能力判定を独立追加 |
| runtime/identity_context.py / TurnContext | Trusted Scope 生成・Principal/Project/Room/Session 境界検証の基礎として再利用 |
| runtime/session_store.py | Lease Registry への安全なリンク。履歴と Sandbox 実体の寿命を混同しない |
| web_impl/process_workers.py | PR #236 の **1-turn subprocess** をセキュリティ Sandbox と誤認しない。Broker/SessionManager は 1-turn 子プロセスとは独立の長寿命 Owner が保持 |
| web_impl/rooms.py / Room Access | Room 削除・Private Room 期限切れ・認可取消で Lease を回収。Socket 切断のみで破棄しない |
| a2a/engine.py / a2a/server.py / a2a/auth.py | 現行は単一 A2A Bearer Token を確認するが、個々の Principal ID までは識別しておらず、engine の resolved_turn_context() に task_id が自動で埋まるわけでもない。**Server 側 Service Principal / 強制的な Task ID Binding** を先に追加し、Task Cancel/終了で Lease Cleanup。将来の Multi-tenant は別の信頼できる Identity Binding が必須 |
| CLI / GUI Session 切替 | 切替先 Lease を認可し直し、存在すれば再利用。新規 Session と会話削除で Cleanup |
| Background Job / Sub-Agent | 元 Scope からの派生権限、独立 Job の終了と取消、orphan cleanup を明示 |

特に PR #236 の Web 1-turn プロセスに Sandbox 所有権を持たせると、Turn 終了時に Sandbox が失われる。SessionManager は Web サーバー側の安全な Supervisor または専用 Broker Service が所有し、子 Worker は認可された Lease に RPC でアクセスする。

## 13. 異常系・競合・監査

- **backend unavailable / timeout / crash**: Remote は Tool Call を失敗扱いにし、Host では実行しない。Local opt-in も黙って Sandbox を無効化しない。Worker が再作成されても過去のファイル・プロセス状態が復元されたと装わず、途中の Tool Call を再実行しない。
- **lease mismatch**: Principal、Project、Room、Task、Auth/Policy Revision、Owner Generation の不一致を拒否。既存 Lease を別 Scope に割り当てない。履歴中の Session ID・Workdir・任意 Tool 出力を Trust Anchor としない。
- **revocation**: 新規 Tool を直ちに遮断し、実行中 Tool の Execution Handle に Cancel を要求、取消完了が確認できなければ Lease 全体を強制終了し、終了後も別 Scope に再利用しない。既存 Lease の新規利用も禁止する。Cancel/強制終了後は呼出元の wait_execution() が有限時間内に終端結果を受け取ることを要求する。既に完了した外部送信・不可逆な副作用は取り消せないため、監査・補償手順を別途用意する。
- **duplicate Tool / parallel turns**: Scope ごとの同時実行を制御し、各 Request ID の再送・タイムアウトで二重副作用を起こさない。
- **host restart / orphan**: Active Lease Registry を照合し、所有者不明の実体を上限付き Cleanup で回収。Cleanup 失敗は記録・再試行し、再利用しない。
- **cleanup failure**: Session が消えたように表示しても Sandbox 実体が残る可能性を監視可能にする。Audit/Telemetry に機密本文を載せない。
- **resource exhaustion**: Scope 別と Host 全体の同時 Sandbox 数、CPU、メモリ、Disk、Process、Tool 実行時間、Network、出力サイズを制限する。
- **security-profile mismatch**: 必要隔離強度を満たす Backend が無ければ拒否。ProcessContainer 等への無断ダウングレードを禁止する。

## 14. テストと受け入れ条件

### 契約テスト（Mock Backend）

1. CLI Session A は Tool を3回実行しても Lease を1回だけ作成し、Session B と共有しない。
2. GUI 会話切替・戻りで Lease を正しく選択し、会話削除で破棄する。
3. Web Room A/B（同じ Principal/Project でも）は異なる Lease。Socket 切断・再接続では有効な Lease を再利用する。
4. Private Room の TTL、認可失効、Room 削除で Lease を破棄する。
5. A2A Task A/B は、同一 Principal/Project/SessionStore でも異なる Lease を持ち、Task Cancel/完了で破棄する。単一 Bearer Token からユーザー Principal を偽造せず、Server Service Principal に紐付ける。
6. 同時作成、重複 Call、Stop、Worker Crash、Lease Registry 再起動で二重生成・漏洩が無い。**wait_execution() 中でも別 Channel で Cancel 可能**で、成功した Cancel 後の状態再利用と、Timeout 時の Lease 強制破棄を区別する。Backend が Cancel/Terminate に応答しないケースを注入し、Broker 側の待機期限到達時に必ず終端結果を返し、直列化ロックを解放し、該当 Lease を隔離して新規 Tool を拒否する。
7. 未分類 Tool、Capability 不足、Policy 拒否、Backend 不在時に **Host Tool Runner が一度も呼ばれない**。現行 ToolPolicy / EnterprisePolicy の allow 既定に依存した Remote の実行許可を拒否する。
8. Local Sandbox off の CLI/GUI で既存動作に回帰が無い。
9. 平文 Credential が注入された Lease は即座に tainted となって他の Tool と Snapshot を拒否する一方、**その Credential を必要とする実行中 Tool が完了するまでは継続可能**。操作終了直後の Credential 撤去・Lease 破棄が次 Tool の前に完了することを確認する。Cancel と Timeout 時も同じ境界を守り、Workspace を含めて完全に再生成される。
10. 監査データと Telemetry に秘密・会話本文・Tool 引数が漏れない。
11. 認証付き Multi-user Web を localhost 経由で操作しても、公開 Web を local identity で起動しても、Remote の隔離要件を回避できない。
12. CLI :cd / GUI Workspace / Web Project を変更した場合、前の Sandbox が新しい Host Path を読み書きできず、作業ファイルの export が競合検出と明示許可なしで Host へ反映されない。
13. Worker の Session 中クラッシュと再起動では状態消失を利用者へ通知し、以前の Tool を自動再実行しない。
14. 未隔離 Helper 直接呼出し、MCP / Plugin 内部 subprocess、Sub-Agent の越境を拒否し、Host-pure への Remote 第4経路がない。
15. macOS Seatbelt の宛先絞り込み不能など Backend ごとの Capability 不足で、静かに Network Policy を弱めない。
16. :load / :sessions load / GUI 履歴復帰 / Web 再接続で、健全な同一 Scope の Lease だけが再利用され、アプリ再起動や Crash 後は **状態消失を通知し、過去の Tool を再実行しない**。
17. Saved Session の Workdir 指定だけでは別 Project/Workspace の Host File にアクセスできない。Sandbox 新規生成では承認済み Export/Commit 内容以外は自動復元しない。
18. 2つの Web インスタンスが同一 Room/Principal/Project を同時に取得しようとした場合、単一原子的 Claim・Fencing Token・Owner ルーティングが無ければ拒否し、競合 Lease を作らない。
19. Snapshot 未作成時は有効な参照 ID を捏造しない。Artifact 保存失敗時に履歴イベントが ready にならず、履歴本文から任意の Snapshot を復元できない。
20. Snapshot 復元前に Scope/Policy/Workspace/Backend/署名/秘密検査を行い、不一致を拒否して過去の Tool Call を再実行しない。

### OS 実機検証（導入必須）

- Windows (MXC ProcessContainer)、Linux (MXC Bubblewrap)、macOS (MXC Seatbelt) の各サポート対象バージョンで Probe→複数実行→Cleanup。
- Worker 内から起動した子孫プロセスが隔離ポリシーを継承すること。
- Sandbox 外 Path、Host Credential、ネットワーク制限先、Host Broker 制御 Channel へのアクセスが拒否されること。
- Worker 強制終了、親 Broker 再起動、OS 停止、複数 Session 同時実行による孤立リソースを回収できること。
- Resource Limit、結果上限、取消、Backend feature 不足をテストする。
- CLI/GUI/Web/A2A の実 Provider + 実 Tool 経路で検証する。Mock 成功のみで Enterprise E0 を完了扱いにしない。
- Remote multi-user は別途 gVisor/Hyper-V 等の十分な隔離強度のバックエンドで検証する。軽量ローカル Sandbox の成功を代用しない。

## 15. 実装計画（小さく、ただし細切れにしない）

| 段階 | 内容 | 完了条件 |
| --- | --- | --- |
| Design PR（本書） | OS 非依存契約、Scope、セキュリティ要件、受け入れテストを決定 | 文書レビュー。コード変更なし |
| PR 1: Broker / Policy | ExecutionClass、Broker、明示 SecurityProfile、Web 全入口と A2A Service Principal/Task ID Binding を含む remote ingress の fail-closed routing、Mock Backend 契約テスト | Remote で Host 直接実行へ迂回できない。Backend 未対応なら Remote Tool 不許可 |
| PR 2: MXC local PoC | Windows / Linux / macOS の MXC Adapter、常駐 Worker の可否判定、CLI/GUI opt-in | 同一 Session 複数 Tool が再利用され、停止時に破棄 |
| PR 3: SessionManager 統合 | Web Room・A2A Task と Lease の Binding/Recovery/Cleanup | Room 再接続、Task 終了、Crash、異なる Principal を検証 |
| PR 4: Production Isolation (single instance) | リモート用の強隔離 Backend、Network/Filesystem/Resource Policy、単一インスタンスでの実環境検証 | **単一インスタンス構成に限定した** E0 隔離の受け入れ条件を満たす。Enterprise 全体の完了は主張しない |
| PR 5: Multi-instance ownership | 共有 Lease Registry、原子的 Owner Claim、世代/Fencing Token、Owner ルーティング、他 Node への Revoke 伝播と Crash/Partition 回収 | 複数 Node で同一 Scope の Lease を二重作成せず、管理者失効を全 Node で強制。Enterprise 完了判定は E1-E5 等の既存ゲートにも従う |

既存 [Enterprise E0 Delivery Plan](UAG_ENTERPRISE_PLATFORM_DESIGN.md#16-delivery-plan) の置換ではなく、**Session 維持と全 Host 共通化の具体化**である。実装順・PR の統合は差分規模と実機検証の結果で調整し、機能追加を無制限に混ぜない。

## 16. 未確定事項 / PoC で決めること

- 各 MXC Backend で長寿命 Worker の子孫プロセスが確実に隔離・強制終了できるか。
- 現行 CLI/GUI における Session の終了通知・会話削除イベントにどこまで連携できるか。
- ファイルの永続保持を、Sandbox 破棄と別の Project Workspace export として許可する範囲。履歴ロード時は Export 済み Project ファイルのみを初期再投影し、**Sandbox 内プロセス Snapshot は初期実装で復元しない**。
- 将来の Snapshot について Manifest の保存許可項目、暗号鍵・保持期限、保存タイミング、Backend の復元適合性を確定する。参照情報の設計だけで、Snapshot 実体が存在するかのように扱わない。
- Web 同一 Room の共有メンバー交代に対する Lease ローテーションと公開済み成果物の可視性。
- A2A の複数 Task を一つの上位会話にまとめるユースケースを将来許可する場合の明示的な Shared Scope 設計。
- Backend ごとの IsolationLevel 判定を、どの OS/API/テスト結果で「適合」と認定するか。

未決定の事項を都合のよい既定値で暗黙処理しない。Remote の危険な操作は、適合性確認まで拒否する。

## 17. 参考資料

- [Microsoft MXC](https://github.com/microsoft/mxc)
- [MXC SDK Lifecycle](https://github.com/microsoft/mxc/blob/main/docs/container-lifecycle.md)
- [MXC Bubblewrap Backend](https://github.com/microsoft/mxc/blob/main/docs/backends/bwrap/bubblewrap-backend.md)
- [MXC Seatbelt Backend](https://github.com/microsoft/mxc/blob/main/docs/backends/seatbelt/seatbelt-backend.md)
- [MXC ProcessContainer prerequisites](https://github.com/microsoft/mxc/blob/main/docs/backends/process-container/os-version-support.md)
- [UAG Enterprise Phase E0](UAG_ENTERPRISE_PLATFORM_DESIGN.md#31-enterprise-phase-e0-remote-execution-isolation)
