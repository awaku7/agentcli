# UAG セッション常駐型・クロスプラットフォーム Sandbox 設計

- Status: **Design / 未実装**
- Date: 2026-10-14
- Scope: CLI / GUI / Web / A2A、Windows / Linux / macOS
- Priority: Enterprise E0 の一部。ローカル実行の任意 Sandbox は追加要件
- Related: [Enterprise E0 設計](UAG_ENTERPRISE_PLATFORM_DESIGN.md)、[実装ロードマップ](plans/IMPLEMENTATION_ROADMAP.md)、[Web Room 並列処理](WEB_ROOM_CONCURRENCY.md)

## 1. 決定事項

1. UAG 本体の Tool 実行インターフェースと Session 管理を OS 非依存にする。
2. Sandbox を **Tool Call ごとではなく、実行スコープ（Session / Room / A2A Task）ごとに確保・再利用**する。再利用中は、承認された作業領域・インストール済み依存関係などを保持する。
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
          +--> Host-pure (厳密に監査済みの純粋な内部処理のみ)
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

Host-pure は一般的な Tool Runner の直接実行経路ではない。信頼境界の外にデータが出ないことを監査した、極少数の純粋処理専用経路とする。Enterprise E0 の **通常の data-plane tool action は必ず Sandbox** とし、機密操作は専用 Broker、その他は拒否する。この区別は [E0 設計](UAG_ENTERPRISE_PLATFORM_DESIGN.md) を上書きしない。

## 4. エントリーポイントと Sandbox の所有単位

| Entry point | 必須の Scope ID | Sandbox 既定 | 維持・終了の契機 |
| --- | --- | --- | --- |
| CLI (uag) | CLI runtime session UUID | local: off | CLI Session 終了、明示破棄 |
| GUI (uagg) | GUI 会話 ID + runtime 所有情報 | local: off | 会話の切替時は切替先へ、会話削除で破棄 |
| Web (uagw) | **room_id** | local-only: optional / remote: required | Room が存続する間維持。削除・Private Room TTL・認可取消で破棄 |
| A2A (uaga) | **task_id** | remote tools: required | Task の完了・取消・期限切れで破棄 |

- Web の一時的な WebSocket 切断は Room 終了ではない。再接続しても同一 Scope の健全な Sandbox を再利用する。
- 同じ principal と project でも **異なる room_id の Sandbox は共有しない**。Private / shared Room の可変状態も共有しない。
- A2A の opt-in SessionStore が無効でも **task_id 必須**。Task が異なれば会話履歴が似ていても Sandbox は共有しない。
- CLI の新規 Session は新しい Scope とする。保存済み Session をロードした場合は所有者・Workspace を再検証し、健全な既存 Lease があれば再接続できる。無ければ **新規 Sandbox** に復帰し、プロセス状態の復元を装わない。
- GUI の会話切替でも同様。会話を消したときの Sandbox 破棄と、履歴だけを残す動作は分ける。
- CLI/GUI で Sandbox off のときは SessionManager にリソースを作らない。
- Sub-Agent / background Job は親 Scope と権限の縮小を基本とし、長寿命 Job は親終了後の孤立実行を許可しない。独立 Scope が必要な場合は別途定義する。

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
    HOST_PURE = "host_pure"
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
    def execute(
        self, handle: "SandboxHandle", request: "ToolExecutionRequest"
    ) -> "ToolExecutionResult": ...
    def terminate(self, handle: "SandboxHandle") -> None: ...
    def health(self, handle: "SandboxHandle") -> bool: ...
~~~

**create → execute (N 回) → terminate** が UAG の契約である。Backend はこれを以下のいずれかで実現する。

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
- Scope ごとに排他的な Lease 作成を保証し、同時開始しても Sandbox が二重生成されないようにする。
- Scope 内の Tool Call は初期実装では直列化する。並列化は Backend の独立子プロセス制御と資源制限の実証後に検討する。
- User による Stop は **現在の Tool/Turn** を中断する操作で、必ずしも Session の終了を意味しない。Worker が健全なら Lease は維持する。
- 異常終了・安全な状態を判断できない中断時は Lease を破棄して次の Tool でクリーンな環境を再生成する。
- Sandbox に秘密情報の平文が入った場合は E0 の tainted lease 規則に従い **即時破棄し再利用しない**。この場合、同じ Session が生きていても安全性を優先する。

### 6.2 セッション終了の定義

「Session が生きている間」は **UAG が管理する有効な Session / Room / Task の存続期間** を指す。単なる WebSocket 切断・一時的な GUI 非表示・ターン終了では破棄しない。

- 明示的な終了・削除、認証取消、Project/Room 権限喪失、Session TTL/期限切れ、管理者による Kill Switch で破棄。
- Session 存続中に短い idle timeout だけで安易に破棄しない。運用上の絶対 Lease 上限や資源不足時の破棄が必要なら、その影響を明示して再作成する。
- SessionStore の「履歴保存期限」と「生存する実行 Lease」は別。履歴が残っていても Sandbox が残る保証はしない。
- Broker 再起動後は既存 Lease を列挙し、Scope・Backend 実体・Owner・Revision を照合して安全なものだけ再接続。それ以外は回収する。
- Multi-instance 化前は、単一 Owner と process/host fencing を前提とする。他 Node の Lease を誤って操作・再利用しない。

### 6.3 永続レジストリ（秘密情報を持たない）

保存対象: opaque lease_id、typed scope fingerprint、backend、backend opaque handle reference、state、owner instance、generation/fencing token、creation/heartbeat timestamps、policy revision、cleanup status。

保存禁止: API Key、OAuth Token、平文 Credential、任意の Tool 引数/本文、作業ファイルの内容、秘密を含む stdout/stderr。

SQLite は初期の単一ホスト実装として使用可能。Crash 後の orphan 削除、再起動時の整合性照合、TTL と回収待ち状態を必須とする。

## 7. Tool 実行分類と権限

既存の src/uagent/tools/tool_policy.py は READ_ONLY / IDEMPOTENT_WRITE / EXTERNAL_SEND / DESTRUCTIVE を区別する。これは **実行環境の安全性を示す分類ではない**。例えば get_env、read_file、http_request GET は READ_ONLY でも、Host の情報を読み取れるため一般 Host-safe ではない。

評価順序:

1. 信頼済みの Entry Point / Principal / Project / Room / Task を確認する。
2. UnifiedPolicy・Role・ToolPolicy による **認可・副作用・確認**を評価する。
3. Tool 名だけでなく引数・実際の機能・MCP 展開先・ネットワーク宛先を考慮して ExecutionClass を決める。
4. 要求する隔離強度と Backend Capability を照合する。
5. 許可された Scope の Lease へルーティングし、実行直前にも Policy Revision と権限を再検証する。
6. 結果・Artifact・監査ログを制限付きで回収する。

| Tool の性質 | Local Sandbox on | Remote ingress |
| --- | --- | --- |
| 監査済みの純粋計算・日時 | Host-pure または Sandbox | Host-pure は厳格な専用実装に限る |
| Shell / Python / Git / コンパイラ / ファイル処理 | Sandbox | **Sandbox 必須** |
| HTTP / Web / Browser / MCP / Plugin / Skills | Policy 審査後 Sandbox または専用 Broker | 適切な隔離または専用 Broker。直接 Host への迂回は禁止 |
| 認証・Policy・管理・監査などの管理操作 | 専用 Broker | 権限を絞った Broker、または Deny |
| Device / USB / Bluetooth / Host Desktop | 個別 Policy / 互換性判定 | **Deny 既定**。専用 Device / GUI Broker は別設計 |
| 未知の Tool、動的ロードされた未分類 Tool | 分類未完了なら保留または拒否 | **Deny 既定** |

- LLM による副作用の確認は Sandbox の権限昇格を意味しない。
- Tool の動的ロード・MCP 子機能・プラグインの内部サブプロセスにも同じ Policy を適用する。ラッパー Tool だけのチェックで完了としない。
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

### 8.1 実装前の技術的検証ゲート

Native stateful でない MXC Backend に対し、単に spawn が成功しただけで「セッション常駐 Sandbox 対応」と判定しない。以下を検証する。

- Sandbox 内 Worker が複数リクエストを受信でき、各 Tool から生成した子孫プロセスまで同じ Sandbox Policy に閉じ込められる。
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
- 書き戻しは Broker が認可済み Project 範囲へ明示的に反映。Path Traversal、Symlink、Hardlink、Archive Slip 等を検査する。
- 作業ファイルは Session 内の複数 Tool 間で保持するが、別 Scope に引き継がない。

### ネットワーク

- 既定は egress deny。宛先、DNS、proxy、private/link-local/metadata 宛先、接続数を Policy で制限する。
- Tool が外部 API を使う場合は、許可された Destination と Credential Scope を毎回確認する。
- Proxy / Firewall 制御を Backend が強制できない場合は「許可済み」と扱わない。

### 秘密情報

- Host 側 Credential Store を丸ごとマウントせず、Host 環境変数も引き継がない。
- 認証付き操作は、可能な限り **Broker 経由の短寿命認可**で行い、秘密の平文を Sandbox へ渡さない。
- 平文 Credential が Sandbox へ渡された Lease は **tainted** として直ちに再利用不可、破棄・クリーン状態への再生成を必須とする。Session 維持より秘密保護を優先する。

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
- Remote profile は sandbox=off を許可しない。CLI から指定された値と Deployment Policy のうち **厳しい方**を採用する。
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
| a2a/engine.py / a2a/server.py | Task ID と認証済み Principal の Scope Binding、Task Cancel/終了に伴う Lease Cleanup |
| CLI / GUI Session 切替 | 切替先 Lease を認可し直し、存在すれば再利用。新規 Session と会話削除で Cleanup |
| Background Job / Sub-Agent | 元 Scope からの派生権限、独立 Job の終了と取消、orphan cleanup を明示 |

特に PR #236 の Web 1-turn プロセスに Sandbox 所有権を持たせると、Turn 終了時に Sandbox が失われる。SessionManager は Web サーバー側の安全な Supervisor または専用 Broker Service が所有し、子 Worker は認可された Lease に RPC でアクセスする。

## 13. 異常系・競合・監査

- **backend unavailable / timeout / crash**: Remote は Tool Call を失敗扱いにし、Host では実行しない。Local opt-in も黙って Sandbox を無効化しない。
- **lease mismatch**: Principal、Project、Room、Task、Auth/Policy Revision、Owner Generation の不一致を拒否。既存 Lease を別 Scope に割り当てない。
- **revocation**: 新規 Tool を直ちに遮断し、実行中 Tool と既存 Lease の取消・終了を行う。
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
5. A2A Task A/B は、同一 Principal/Project/SessionStore でも異なる Lease を持ち、Task Cancel/完了で破棄する。
6. 同時作成、重複 Call、Stop、Worker Crash、Lease Registry 再起動で二重生成・漏洩が無い。
7. 未分類 Tool、Capability 不足、Policy 拒否、Backend 不在時に **Host Tool Runner が一度も呼ばれない**。
8. Local Sandbox off の CLI/GUI で既存動作に回帰が無い。
9. 秘密を Sandbox に渡した Lease の再利用は禁止され、Workspace を含めて完全に再生成される。
10. 監査データと Telemetry に秘密・会話本文・Tool 引数が漏れない。

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
| PR 1: Broker / Policy | ExecutionClass、Broker、remote ingress の fail-closed routing、Mock Backend 契約テスト | 全入口から Host 直接実行へ迂回できない |
| PR 2: MXC local PoC | Windows / Linux / macOS の MXC Adapter、常駐 Worker の可否判定、CLI/GUI opt-in | 同一 Session 複数 Tool が再利用され、停止時に破棄 |
| PR 3: SessionManager 統合 | Web Room・A2A Task と Lease の Binding/Recovery/Cleanup | Room 再接続、Task 終了、Crash、異なる Principal を検証 |
| PR 4: Production Isolation | リモート用の強隔離 Backend、Network/Filesystem/Resource Policy、実環境検証 | Enterprise E0 の受け入れ条件を満たす |

既存 [Enterprise E0 Delivery Plan](UAG_ENTERPRISE_PLATFORM_DESIGN.md#16-delivery-plan) の置換ではなく、**Session 維持と全 Host 共通化の具体化**である。実装順・PR の統合は差分規模と実機検証の結果で調整し、機能追加を無制限に混ぜない。

## 16. 未確定事項 / PoC で決めること

- 各 MXC Backend で長寿命 Worker の子孫プロセスが確実に隔離・強制終了できるか。
- 現行 CLI/GUI における Session の終了通知・会話削除イベントにどこまで連携できるか。
- ファイルの永続保持を、Sandbox 破棄と別の Project Workspace export として許可する範囲。
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
