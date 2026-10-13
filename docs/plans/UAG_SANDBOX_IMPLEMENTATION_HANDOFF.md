# UAG Sandbox 実装引き継ぎ手順書（Windows先行5 PR + 後続2 PR）

- 作成日: 2026-10-14
- 状態: 実装エージェント向け作業手順／実装未着手
- 対象: awaku7/agentcli
- 基点: main（設計 PR #252 マージ済み）
- 仕様の正本: [UAG_SANDBOX_SESSION_DESIGN.md](../UAG_SANDBOX_SESSION_DESIGN.md)
- セキュリティ要件: [UAG_ENTERPRISE_PLATFORM_DESIGN.md](../UAG_ENTERPRISE_PLATFORM_DESIGN.md) §3.1 / E0
- 開発規約: [AGENTS.md](../../AGENTS.md)

> 本書は設計書 §15 の **Windows先行PR 1〜5と、後日実施するLinux PR 6・macOS PR 7**を、別エージェントが実装・検証するための手順にしたもの。**今回すぐ実装するのはWindows向けPR 1〜5のみ**。Linux/macOSは省略せず後続PRに担当を割り当てるが、前倒ししない。矛盾時は最新版の正本設計書とEnterprise E0を優先する。

## 1. 全PR共通の実装ルール

### 1.1 Simple is best

- **既存 Function Call の名前・引数・戻り値は原則変更しない。** 各ツールへ Sandbox 専用クラスを作らず、既存共通ディスパッチの **ExecutionBroker** で実行先を判定する。
- 実行先は **SANDBOX / 狭い BROKERED / DENY** を基本とする。監査済み LOCAL_HOST_PURE は信頼済みローカル CLI/GUI にのみ認め、リモートへ追加しない。
- 「副作用区分」（ToolPolicy）と「隔離・実行先」（ExecutionClass）は別概念。READ_ONLY でも Host 情報を取得するツールをリモート Host 上で動かさない。
- 設定追加は最小限。外部向けは設計書の共通 sandbox 引数／明示 SecurityProfile に寄せ、Backend ごとの環境変数を大量に増やさない。
- **実装順は Windows → Linux → macOS。** Windows先行PR完了後でもLinux/macOSのSandboxは未対応と表示し、明示的な実装・実機検証が済むまで無隔離に切り替えない。
- OS差は Adapter に閉じ込める。Sandbox は **64-bit x86-64 / ARM64 のみ**。ARM32、32-bit OS/ユーザーランドの互換対応を作らない。
- 既存 CLI/GUI は **Sandbox off が既定**で従来動作を維持する。Opt-in が失敗したとき無言で Host 実行へ戻さない。
- リモート Web（認証付きマルチユーザー含む）・Remote A2A は **Sandbox / 限定 Broker / Deny** のいずれかのみ。必要な Backend が無ければ危険なTool実行を拒否する。
- 設計にない Snapshot 実体の保存・復元、デバイスパススルー、Docker必須化、追加管理UIは今回の5 PRに混ぜない。

### 1.2 実装前の事実確認

各PRの開始時に main を更新し、**既存コードと既存テストを読む**。以下のパスは確認対象であって、一律に全ファイルを書き換える指示ではない。

| 領域 | 現行の確認対象 |
| --- | --- |
| Function Call登録・共通実行 | src/uagent/tools/__init__.py の _RUNNERS / run_tool / run_tools_parallel / 動的ロード |
| 副作用・承認 | src/uagent/tools/tool_policy.py、src/uagent/runtime/policy_engine.py、src/uagent/tools/enterprise_policy.py |
| ID・セッション | src/uagent/runtime/identity_context.py、src/uagent/runtime/session_store.py |
| Web | src/uagent/web_impl/process_workers.py、src/uagent/web_impl/rooms.py と実入口 |
| A2A | src/uagent/a2a/server.py、engine.py、auth.py、task_store.py |
| Agent内部 | Auto-pilot、Sub-Agent、Background Job、Skills、MCP、Plugin のRunner呼出経路 |
| 結果・監査 | Tool Result / Artifact / SessionStore / OpenTelemetry の既存経路 |
| 標準 | AGENTS.md、docs/UAG_SANDBOX_SESSION_DESIGN.md、docs/UAG_ENTERPRISE_PLATFORM_DESIGN.md |

最初に共通 run_tool() 以外の Runner 直呼出し、ダイナミック登録時の import、副作用を伴う Helper を検索し、**リモートでBrokerを迂回できないか**を確認する。全機能を一度に作り替えず、該当PRで必要な通路だけを封じる。

### 1.3 セキュリティ不変条件

1. リモート呼出元・Tool引数・LLM出力から Principal、Project、Room、Task、SecurityProfile を決めない。Trusted Server Contextから生成する。
2. Web は **deployment + principal + project + web-room + room_id**、A2A は **deployment + service-principal + project + a2a-task + task_id**。異なるScopeで可変状態を共有しない。
3. 非LoopbackへBindするA2Aを local-trusted / sandbox-off でツール実行可能にしない。起動時に強制隔離または拒否する。
4. SandboxからHostの Credential Store、環境変数全体、Home、管理API、Docker Socket、他Scopeのファイルへアクセスさせない。
5. Credentialの平文をSandboxへ渡さない方針を優先。やむを得ない場合は直ちに Lease を tainted とし、実行中の当該操作終了後、次の Tool Call **前**に破棄・全状態消去する。
6. 操作停止は Execution Handle ごと。cancel_execution が安全に完了しなければ Leaseごと停止し、wait_execution は有界時間内に終端する。
7. 起動時 probe は **Broker強制の既定15秒締切**。ハングしたAdapterは隔離・回収し、local opt-inはエラー、remoteはfail closed。
8. Toolの許可を「未知 = allow」「ToolPolicy既定 = allow」から推定しない。動的プラグイン、MCP内部プロセス、Sub-Agentにも同じ隔離判定を適用する。
9. ローカルの信頼済み純粋処理は例外だが、リモートの第4の直接Host実行経路を作らない。
10. **Mock成功はセキュリティ隔離の実機検証完了ではない。** 不足するOS/隔離強度はunsupportedとして表示する。

## 2. 実装PRの順序と責務

| PR | 推奨PRタイトル | 取り扱う責務 | 完了判定 |
| --- | --- | --- | --- |
| 1 | feat: add sandbox broker and fail-closed tool routing | ExecutionClass、共通Broker、Policy、Remote ingressとA2A ID拘束、Mockテスト | リモートHost直実行が発生しない |
| 2 | feat: add opt-in Windows MXC local sandbox adapter | **Windows 11 x64先行**のMXC ProcessContainer、隔離Worker、CLI/GUI opt-in、初回セットアップ | Windows x64実機でSessionの複数Toolを隔離実行・回収できる。未検証OS/archは有効化しない |
| 3 | feat: bind sandbox leases to web rooms and A2A tasks | 全入口のSessionManager/Lease/回収と履歴再接続 | Room/Taskごとの状態維持・境界・終了が正しい |
| 4 | feat: enforce Windows production sandbox isolation for remote tools | Windowsの強隔離Backend（Hyper-V候補）、Workspace/Network/Secret/Resourceの実効Policy | **Windows単一インスタンス構成に限り**E0の実機テストが成立 |
| 5 | feat: coordinate sandbox lease ownership across Windows instances | 共有Registry、原子的Owner取得、世代/Fencing/ルーティング | **Windows複数Node**で二重Lease・失効迂回が起きない |

**Windows先行の対象はPR 1〜5。** Linuxは後続PR 6（Raspberry Pi 64-bitを含む）、macOSは後続PR 7で実装・検証する。これらをPR 2の完了条件に含めず、将来の担当を消さない。PRごとに新しい作業ブランチを **最新mainから作る**。前のPRの未マージブランチに無断で積まない。依存が未マージなら先行PRの完了まで次段階の本実装を開始しない。並列でできるのは読み取り調査・テスト設計のみ。

## 3. PR 1 — ExecutionBroker / Policy（まずこれだけ）

**目的:** Sandboxの実Backend導入前に、すべてのTool Callが共通の認可・実行先選択を必ず通る基盤を作る。

### 作業

1. ExecutionClass（SANDBOX / BROKERED / DENY / ローカル限定LOCAL_HOST_PURE）、SecurityProfile、必要Capability、Trusted SandboxScopeの最小モデルを定義。型・エラー形式を必要以上に増やさない。
2. **実行順序を正本 §7 に揃える:** (a) Trusted Principal/Project/Room/Taskと入口を確定 → (b) UnifiedPolicy・Role・ToolPolicyで認可/副作用を判定し、拒否なら終了 → (c) **承認を求める前に**ツール名・引数・実機能・MCP展開先・ネットワーク宛先から ExecutionClass を選び、必要な隔離強度とBackend Capabilityを照合。不可能なら確認ダイアログを出さず拒否 → (d) 必要なHost UI/Broker承認を取得 → (e) **承認後・実行直前に権限とPolicy Revision、Scope/Bindingを再検証**し、失効・変更時は実行拒否（必要なら最初から再判定）→ (f) 許可されたSandbox Leaseまたは狭いBrokerへルーティング。Host側の管理Broker操作と未信頼な汎用Runnerを明確に区別し、古い承認を権限昇格に使わない。
3. src/uagent/tools/__init__.py の共通入口に導入。CLI/GUIのSandbox offだけ既存実行を維持。run_tools_parallel、動的Toolロード、MCP、Sub-Agent等の別経路が迂回しないことを検証。
4. Remote Web（HTTP、WebSocket、1-turn Worker）とA2A（通常・ストリーム）への入口で、**ツールを起動する前**に実効SecurityProfileと認証済みScopeを確定する。Web WorkerがProfileを自由に弱められない。
5. A2Aの信頼済みService Principalと**必須task_id**をServer側で結合。単一Bearer Tokenからユーザーごとの本人識別を捏造せず、Client提供IDでLeaseを選ばない。
6. A2Aの非Loopback Listen検証を実装。Sandbox未対応でも、local-trusted + sandbox-offのままTool実行可能な公開サーバーを立てない。
7. **Mock Backendのみ**でCapability不足・Backendなし・Policy拒否・Brokered操作・取消要求の契約を検証。汎用HostRunnerに到達したかをSpyで検証する。

### 今回はやらない

- MXC SDK、Node Adapter、隔離Workerの実体、OSへの依存インストール。
- Sandboxがあるかのように偽装するダミー実行や、Mockを本番Backendとして許可すること。
- Web Room/A2A Leaseの本格的永続管理（PR 3）。
- リモートの隔離必要Toolを「まだBackendがないので暫定Host許可」にすること。

### 必須テスト・完了条件

- Local Sandbox off のCLI/GUIは従来のFunction Call/承認/出力で動く。
- Remote Tool がSANDBOXと判定されたのにBackendが無い場合、**実際のRunnerは呼ばれず拒否**される。
- Remote BROKEREDは限定操作だけ。任意のTool名・Path・URLを指定してHost汎用Runnerに入れない。
- READ_ONLYの read_file / get_env / http_request GET でも「Hostで安全」と誤分類しない。
- 未分類Tool、遅延ロードTool、MCP子機能、Sub-Agent経由の迂回を拒否できる。
- 非Loopback A2A + local-trusted / sandbox-off は強制隔離または起動拒否。
- 認証付き社内Webがlocalhost経由だからといってLocal扱いされない。
- **認可から確認画面の間・ユーザーの確認待機中・確認直後**にRoomメンバー権限、Principalの権限、Policy Revisionを変更した場合、実行直前の再検証で古い許可が拒否され、Sandbox/HostのどちらのRunnerも起動しない。実行不能なCapabilityの場合は**ユーザー確認前**に拒否する。
- **このPRだけではRemote Toolが利用できなくても正常**。後続PRで適合Backendが導入されるまでfail closedとする。

## 4. PR 2 — MXC Local PoC / CLI・GUI Opt-in

**目的:** **Windows 11 x64先行**でMXC ProcessContainer Adapterを導入し、実Sandbox上の複数Function Callが同一Session環境を使えることを確認する。Linux/macOSのAdapter実装は**後続PR 6・PR 7**へ明示的に延期する。

### 作業

1. MXCの現行API・Windows ProcessContainer実装、対応Windowsビルド、Node SDKとNative Runtime依存を**着手時に実際に確認**する。**PR 2のAdapterはWindowsだけ**。Linux Bubblewrap・macOS 15+ Seatbeltは後続PRで実装する。Windows実機でProbe・隔離付き複数実行・Cleanupと失敗時動作を検証する。
2. 必要最小限のPython Host Adapter + 隔離Workerを作る。MXCへの依存はAdapterに隠し、Function Callの公的契約にMXC固有型を出さない。
3. **Native stateful** が使えれば採用。spawnのみなら隔離した長寿命Worker + 構造化IPCを検証する。子孫プロセスまで封じ込められなければ unsupported。
4. Worker側には許可された機能だけを投影。Hostの.env/.env.sec、Credential Store、管理設定、Hostのos.environ全体を引き継がない。stdoutとIPCを分離し、結果をサイズ制限付きで受け取る。
5. CLI/GUIのSandbox opt-inを設計書の共通引数へまとめる。off時は追加インストール/Probe/環境変更を行わない。
6. 初回のみOS/arch/依存を調べ、管理者権限やOS変更を要するときは**明示同意**を求める。2回目以降は静かな短時間Probeのみ。非対話実行・依存不足は明示エラー。
7. Brokerがprobeの**既定15秒期限**を強制し、固着するSDKを回収できる独立Helperで実行。初回実行確認は通常起動Probeと別の有界手順にする。
8. ローカルでSession内のファイル・導入済み依存を複数Toolで使い回し、停止時はWorker/子孫プロセスを回収する。操作単位とLease単位の取消を区別。

### 対応範囲・対象外

- **PR 2で有効化する対象はWindows 11 x64**。Windows ARM64は、SDKと実機の適合を確認できるまで未対応とする。Linux x86-64/ARM64・Raspberry Pi ARM64・macOSは後続PR 6/7の対象であり、Windows段階で対応済みと表示しない。
- Windows用コマンドをLinux/macOSで使えるかのように扱わない。
- このPRの軽量MXC Sandboxを、Enterprise Remote向け強隔離として**有効化しない**。
- ホストへの安全な書き戻しや高度なネットワーク隔離はPR 4の検証ゲートを満たすまで不許可。
- **Windows 11 x64でのAdapter実装・実機検証がPR 2の完了条件**。Linux/macOSは正本§15に明記した**後続PR 6/7の担当**とし、PR 2〜5の未完了条件としない。対応していないOS/CPUではSandbox opt-inおよびRemote Toolを拒否し、暗黙にHost実行へ戻さない。

### 必須テスト・完了条件

- 1 Sessionに対する3回のTool呼出でWorker/Leaseは原則1つ、別Sessionでは別環境。
- 例: create_file → python_exec → read_file に相当する操作で同一Sandboxのファイルが利用できる。
- 子プロセス/任意Host Path/秘密環境変数の隔離を**実際の不正アクセス試験**で確認。
- Stop/Cancel/Timeout/Crashで子孫プロセスが残らない。wait_executionが無限待機しない。
- 32-bit拒否、OS未対応、導入拒否、オフライン、Helperハング時に**無隔離へ戻らない**。
- Local Sandbox off の回帰テストが通る。**Windows 11 x64**のBackend/SDK版、Probe・不正アクセス・複数Tool・Cleanupの実機試験と結果をPR本文に記録する。**Windows ARM64の実機確認が無ければ当該archは未対応と表示**。Linux/macOS/Raspberry PiではWindows先行段階でSandboxが明示的な未対応エラーとなり、Hostへフォールバックしないテストも行う。

## 5. PR 3 — 全入口とSandboxSessionManagerの統合

**目的:** CLI/GUI/Web/A2Aのセッション単位でLeaseを再利用・廃棄し、別ユーザー/Room/Taskへ共有しない。

### 作業

1. 設計書の型付きSandboxScopeをSessionManagerで使い、Host側のTrusted Context以外からScopeを生成しない。
2. Webは**principal + project + room_id**、A2Aは**Service Principal + task_id**を必須とし、異なるscope_kindが同じLeaseにならないようにする。
3. Webの1-turn Worker（現行process_workers.py）にLeaseの所有権を持たせない。安全なサーバー側Supervisor/BrokerがOwnerとなり、Turn Workerは認可済みLeaseを参照する。
4. CLIの既存Session切替・履歴ロードと、GUIの**現在のSessionでの継続実行・既存の履歴ロード／Session変更・終了操作（実際に提供されている場合のみ）**をLeaseの状態遷移として結ぶ。**SandboxのためにGUIの会話一覧・A/B切替・削除UIを新設しない。** WebのSocket切断・同Room再接続、Room削除/TTL、A2A Task終了/Cancelは既存のライフサイクルへ統合する。
5. 保存済み履歴と生きたLeaseを区別。再起動後は新規Sandboxで、**過去のToolを自動再実行しない**。初期段階ではProject Revision/Export済み内容だけを新規投入。
6. Lease Registryは単一Host/単一OwnerのSQLite等を許容するが、これを分散Owner排他の代替としない。Crash後の孤立プロセス回収、TTL、二重生成防止を用意。
7. Sub-Agent/Background Jobは親のScopeと縮小権限を継承し、終了後の孤立実行を許さない。

### 今回はやらない

- 複数Host間の原子的Claim/Fencing/所有権移譲（PR 5）。複数インスタンス構成で安全だと宣言しない。
- Snapshot実体の保存と復元。設計済みの参照情報があることと機能実装済みを混同しない。
- 強隔離のないMXCをRemote Web/A2Aへ無断採用すること。

### 必須テスト・完了条件

- **CLI Session Aで複数回Toolを呼び、同じLeaseが再利用される**。新規CLI Session Bでは別Leaseとし、終了/明示破棄で回収する。CLI履歴ロードは、生存Leaseが同一実行Scopeで健全なときだけ再接続する。
- **GUIの現行単一会話/Session**で3回のTool Callが同じ健全なLeaseを使い、GUI/Session終了で回収することを試験する。既存の履歴ロード・Session変更・削除イベントが利用可能な場合だけScope再認可・Lease選択・Cleanupを試験し、MockのSession変更イベントでもA/BのLease混在を禁止する。**新しいGUI会話切替画面や会話管理UIの実装・UI操作試験は必須条件にしない。**
- **CLI/GUIのプロセス再起動後**は古い生存Leaseを当然に再利用せず、新規Sandboxを生成する。保存済み履歴やWorkdirだけでHostへのアクセス権を拡大せず、過去Toolを再実行しない。GUIに未実装の会話切替画面をSandboxの前提条件として追加しない。
- 同一Room/Principalの再接続では健全なLeaseを再利用、異なるRoom/Principal/Projectは別Lease。
- WebSocketの切断だけでRoom Leaseを消さず、Room削除・TTL・権限失効時は回収する。
- A2A別TaskでLeaseを共有せず、Cancel/完了で破棄する。
- 切替直前の実行中Toolが誤って別Scopeへ流れない。Owner Generation/Binding不一致は拒否。
- Crash/Restartからの復帰で古い結果・副作用を再実行しない。
- **Remoteで必要な強隔離Backendがなければ、この段階でもToolは拒否のまま**。

## 6. PR 4 — Remote Production Isolation（単一インスタンス）

**目的:** Remote Web/A2Aの実Toolを、対象環境で**実効的な隔離ポリシー**のもとに起動できるようにする。単一インスタンスに限ってE0の合否を判定する。

### 作業

1. リモートに必要なIsolationLevelをSecurityProfileへ明示する。**PR 4はWindows向けのHyper-V隔離Backend/VM等を候補として選定・検証**する。Linux OCI/gVisor等は後続PR 6、macOSは後続PR 7の評価範囲。対応する強隔離がないOSではunsupported/denyとする。
2. Capability Probeと実機違反テストにより、Backendが**要求隔離強度を実際に強制できる**ことを証明。プロセス分離だけでVM相当と主張しない。
3. Scope別Workspaceの**copy-in / validated copy-out**を導入し、Host公開は承認済みProjectへの明示Export/Commitのみ。競合Revision/Path Traversal/Symlink/Hardlinkを検査する。
4. ネットワークは既定egress deny。許可先、DNS、metadata/private/link-local、Host管理ポート、Proxy回避を試験する。Seatbeltの細かな宛先制御不可などを無言で許容しない。
5. CredentialはBroker内で管理。短寿命認可を優先。Sandboxに平文を注入したLeaseは即tainted、**実行中の当該Tool終了後**に破棄、次Toolへ再利用しない。
6. CPU、メモリ、Process、Disk、時間、出力、並列実行数の上限を適用。出力は既存のResult/Artifact/SessionStore投影と機密保護を通す。
7. CLI/GUI/Web/A2Aの本物の入口から、実Providerと主要Function Callを使用して受け入れ試験。Backendなし/低機能時の拒否も試す。
8. **Browser/Computer UseをRemote隔離対象として明示的に扱う**。Browser Profile、Downloads、Clipboard、Temporary Files、Desktop Sessionを隔離Browser/VM側で保持し、**Hostの可視DesktopやBrowser Profileに接続させない**。GUIが必要なComputer Useに安全な専用Desktop/VMを提供できなければ、Remoteでは当該ToolをDenyし、部分対応をE0機能完了と取り違えない。

### 今回はやらない

- 単一インスタンスで成功したことを**Enterprise E0全体の完了**と呼ぶこと。
- 複数インスタンスのOwner排他、ネットワーク分断耐性（PR 5）。
- 汎用Host Shell/Network Broker、任意デバイスパススルー、秘密の恒久引継ぎ。
- 将来のSnapshot復元、コンテナプール高速化などの機能追加。

### 必須テスト・完了条件

- 他Principal/Room/Task/ProjectのファイルやLeaseへアクセス不可。Host Home/Credential/管理Socketの読み取り不可。
- Networkの拒否先へのアクセス失敗、Container側のProxy設定だけではなく強制機構を検証。
- Tool内で子プロセスを起動してもSandbox外へ逃げず、Crash/Cancel/Stopで回収。
- Credentialを使う操作の成功・失敗・Cancel・Timeoutの全経路で、次Toolまでに秘密保持状態が破棄される。
- **CPU、Memory、Process/Fork数、Disk/一時領域、Wall Time、stdout/stderr/Tool Resultサイズ、同時Tool/Lease数、通信接続数（要求Profileで制御する場合）**について、各上限を超える実Tool/子プロセスの違反テストを行い、Operationを有界時間で中断・隔離/回収し、**Host Agentや他Scopeを停止・枯渇させない**ことを実機で確認。Capability宣言値・Mockのみでは合格にしない。
- **Remote Browser/Computer Use**ではSandbox/VM固有のBrowser Profile・Downloads・Clipboard・Desktop Sessionから操作・画面取得できること、**Host可視Desktop/ブラウザプロファイル/Clipboard/Microphone/Camera/Printer/任意のHost共有フォルダに到達できないこと**を実機で試験する。提供できないComputer UseはRemoteでDenyとなりHostへフォールバックしないことを検証。
- Export競合時は上書きせず拒否。Tool Result/Telemetryに秘密を流さない。
- 単一インスタンスでしか検証していない環境はその旨をPRに明示。未検証OS/隔離Backendはリモート実行を拒否。

## 7. PR 5 — 複数インスタンスの所有権・Fencing

**目的:** **Windows先行**で2つ以上のWeb/A2Aサーバーが同じScopeを処理しても、同時に別Leaseを作ったり、古いOwnerが実行を継続したりできないようにする。他OSへの統合検証は後続PRで行う。

### 作業

1. 共有Lease Registryと**Scopeごとの原子的Owner Claim**、単調増加するGeneration/Fencing Tokenを定義・実装。単一SQLiteを共有しただけで完了としない。
2. Lease生成、Tool実行、Snapshot以外のWorkspace Export、Cancel、Revokeの各境界で現行Generationを照合し、古いOwnerの書込み・実行・Cleanupを拒否する。
3. Room/Taskに対するOwnerルーティングを実装。誤Nodeへの再送、タイムアウト、リトライで**副作用を二重実行しない**。非Ownerは安全に委譲または拒否。
4. Node障害・Heartbeat切れ・ネットワーク分断からの回復時、古いLeaseを回収/隔離してから次Ownerへ移行。失効・Policy変更を全Nodeに伝播。
5. Broker再起動やPartition時、実行継続の安全性が証明できなければfail closed。強隔離Backend自体の安全条件を緩めない。
6. 複数Nodeの運用・監査・回収状況の観測を、秘密を載せずに最低限追加する。

### 今回はやらない

- 根拠のない分散処理機構の全面刷新や、独立したConsensus基盤の無条件導入。
- Enterprise E1〜E8の別領域（SCIM、監査高度化、DLP等）をこのPRへ混在させること。

### 必須テスト・完了条件

- 同じScopeで2つのNodeが同時にClaimしても、実行可能なOwnerは1つ。
- 故障前Ownerが復帰しても旧GenerationのTool Call/Export/Revocation処理は拒否。
- リトライ、Partition、Node Crash、Admin Revoke、Room削除、Task Cancelで二重副作用・孤立Leaseを作らない。
- Ownerを失ったNodeがHostへ直接フォールバックしない。
- 複数Nodeの実負荷/障害注入テストを実施。Mock-onlyなら「設計/ユニットテスト段階」と明記する。

### 7.1 PR 6 — Linux Backend（後日着手）

**開始条件:** Windows先行PR 1〜5の仕様とテスト結果を継承し、Linuxの実装を明示的に開始するときだけ着手する。

- Linux x86-64 / ARM64（64-bit Raspberry Piを含む）でMXC Bubblewrap Adapterを実装し、隔離Workerの複数Tool・IPC・Cancel・Cleanup、Kernel/User Namespace・SDKの適合性を確認する。
- Linux上でCLI/GUIのopt-inと必要な初回導入を有効化し、未対応環境・32-bitはDenyする。Linux向けRemoteはOCI/gVisor等の**必要隔離強度を実機で確認できた場合のみ**有効化する。
- **PR 6の完了ゲート:** Linux x86-64、Linux ARM64、Raspberry Pi ARM64（64-bit OS）の**3対象それぞれ**で、実機のProbe・複数Tool・Cleanup・隔離違反・Cancel/Crash回収を合格させる。一つでも未検証ならPR 6全体を完了としない。途中の部分実装は実機で検証済みの構成だけ利用可能とし、未検証構成を保証しない。
- HostのCredential・Filesystem・Network・Resource・Browser隔離、SessionManager、Owner/FencingをLinux実環境で検証。**Windows PR 1〜5の合格をLinuxの合格と取り違えない**。

### 7.2 PR 7 — macOS Backend（後日着手）

**開始条件:** Windows先行の共通実装を維持したまま、macOSの実機・MXC SDK・Seatbeltの適合性を確認できること。

- macOS 15+ x86-64 / ARM64のMXC Seatbelt Adapter、隔離Worker、CLI/GUIのopt-in・初回導入・Capability Probe・Cancel・Cleanupを実装する。
- macOSで同一Session複数Tool、子孫プロセス封じ込め、Host Credential/Filesystemからの隔離とResource上限を実機で確認する。macOSのネットワーク宛先制限はSeatbeltだけで達成できると仮定しない。
- macOSのRemote Web/A2Aは、**専用Backendで必要な隔離強度を満たせない限りDenyを維持**する。Browser/Computer UseのHost Desktop露出も禁止する。
- **PR 7の完了ゲート:** **macOS 15+ ARM64とx86-64の両方**で、MXC Seatbelt Adapterの実機Probe・同一Session複数Tool・Cleanup・隔離違反・Cancel/Crash回収が合格していること。一方しか実機確認できない場合は、未検証の構成をSandbox非対応のままにし、**PR 7全体を完了と報告しない**。対応OS/arch/SDKと検証結果を明記する。Remote用強隔離Backendがない環境はDenyを維持する。

**PR 6・PR 7はWindows版のマージ条件には含めず、後日それぞれ独立したPRで実装・検証する。** 以降の共通テスト・レビュー手順は同じく適用する。

## 8. 全PRの作業・レビュー手順

1. **最新mainを取得し、関連実装とテストを確認。** 他の作業ブランチ・未マージPRとの競合も確認する。
2. 当該PRの **目的・対象外・失敗時挙動・テスト** を先に確定。設計未決事項は勝手に安全でない既定値を入れず、記録して必要なら止める。
3. 最小限の実装と対象テストを書く。MCP/Skills/Sub-Agent/CLI/GUI/Web/A2Aの迂回を含む重要な回帰テストを落とさない。
4. 対象範囲のテスト → 差分レビュー → Blackで整形 → Ruff/Blackチェック → 最終コード状態で全pytestの順に検証。**Blackはコミット前に必ず実行**し、CIで失敗した後追い整形を繰り返さない。
5. AGENTS.md の**ピン留め品質ツール**を使用する。コマンド例（環境構築済み想定）:

   ~~~bash
   python -m black <変更したPythonファイル>
   python -m ruff check src tests
   python -m black --check src tests
   python -m compileall -q src/uagent
   python -m pytest -q . --durations=30
   git diff --check
   ~~~

   対象テストは実装中に何度でもよいが、全pytestは**最終コード状態で1回**を基本とする。ログに失敗があれば原因修正・再検証してからpush。環境依存の未実施項目は「未実施」と記載。
6. Tool、Startup、MCP、Web、A2Aを変更したPRは、該当する実経路の結合テストを行う。Backendの隔離強度は**Mockでは証明できない**。
7. 英語のConventional Commitで小さくまとめ、PRを作成する。PR本文に変更点、未変更点、テスト結果、実機環境、リスク、後続PRへ残した作業を記載する。
8. Codexレビューを**1回依頼**し、P1/P2は妥当性を調査して**指摘箇所だけ**修正する。新機能・広範なリファクタを追加して泥沼にしない。修正後に関連テスト・Black・CIを再確認し、必要な再レビューを依頼する。
9. **CI成功・指摘解消・差分の最終点検**後にユーザーへマージ可否を報告。マージ操作はユーザーが判断する。未完了の実機テストを済みと申告しない。
10. マージ後、次PRは新しいmainから開始。完成範囲と未実装の隔離要件を更新する。

## 9. PR本文・引き継ぎ報告テンプレート

### PR本文

- 対象PR段階: **PR N / 7**（PR 1〜5: Windows先行、PR 6: Linux後日、PR 7: macOS後日）。Windows先行の進捗は別途「Windows段階 N/5」と表記してよい。
- 目的とScope: 何ができるようになったか
- 仕様根拠: Sandbox Designの該当節、Enterprise E0の該当条件
- 実装したこと / **実装しないこと**
- Host直実行の可能性: あるか、許されるのはローカルか、Remoteをどこで拒否したか
- テスト: 単体 / 結合 / OS実機 / Security negative test / 未実施
- CI / Black / Ruff: 成否とCommit SHA
- Codexレビュー: 確認したコミットと残件
- リスクと次PRへの持越し: 明確に記載

### 次エージェントへの引き継ぎ

- 作業ブランチとPR URL、最終SHA、main取り込み状況
- 変更ファイル、追加した実行Class/Backendの一覧
- 実行済みテストの正確なコマンドと結果
- **未確認のOS/Backend/脅威シナリオ**
- 次PRが前提としてよいAPI契約
- 機能を壊さないために守る失敗・拒否動作

## 10. この5PRで完了と宣言してはいけないもの

- Sandboxの **設計PR #252がマージされた事実だけ**で、Sandboxが利用可能だと説明すること。
- PR 1のMockテスト通過で、MXCやリモート隔離ができたと説明すること。
- PR 2のWindows軽量Local Sandboxを、権限未検証のRemoteマルチユーザー環境で有効化すること。
- Windows先行PR 1〜5の完了をLinux/macOS/Raspberry Piの対応完了と宣言すること（担当は後続PR 6/7）。
- PR 4の単一NodeのE0試験で、PR 5の分散Owner保証まで完了と判断すること。
- 将来用Snapshot参照仕様だけで、環境/実行プロセスの復元ができると説明すること。
- Raspberry Pi ARM64や全OSにおけるMXCの実機動作を、README上の対応表だけで保証すること。
- Enterprise Platform全体（E1以降を含む）の完了宣言。必要に応じて各Phaseの既存受け入れ条件を別途確認する。

**最初の実装指示:** mainからPR 1用ブランチを作り、共通ExecutionBroker/PolicyとRemoteのfail-closedルーティング、Mockテストだけを実装する。PR 1のレビューとマージを待ってPR 2へ進む。
