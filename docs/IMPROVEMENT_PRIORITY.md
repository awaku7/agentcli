# 改善優先順位と期待効果

この文書は、`uag_improvement_plan.md` に記載された改善項目を、現在の実装状況を踏まえて整理したものです。
実装済みの範囲と未実装の拡張を区別し、ロードマップのチェック状態を実コードとテストに合わせて更新します。

## 実装状況の調査結果

2026-08-19 時点で、本文のロードマップ項目を実コード、関連テスト、ドキュメントで再確認しました。ロードマップのチェック項目は **20/20 件（100%）** が実装済みです。ただし、これは項目の主要な実装とテストが存在することを示す項目数ベースの目安であり、分散合意、OpenTelemetry完全導入、Plugin sandbox完全実装などの本格的な拡張まで完了したことを意味しません。各項目の規模や完成度も重み付けしていません。

確認した主な実装領域は次のとおりです。

- `src/uagent/runtime/lifecycle.py` / `execution.py` と Lifecycle 関連テスト
- `src/uagent/auth/credential_store.py`、`token_store.py` と CredentialStore 関連テスト
- `src/uagent/a2a/task_store.py` と InMemory/SQLite TaskStore 関連テスト
- `src/uagent/runtime/dag_scheduler.py`、`distributed_coordination.py`、`multi_agent.py`、`remote_agent.py`
- `src/uagent/tools/enterprise_policy.py` と Enterprise Policy 関連テスト
- `src/uagent/runtime/logging_setup.py`、Tool dispatch、LLM、OAuth のイベント実装と関連テスト

今回の再確認で反映した周辺実装は次のとおりです。

- `--non-interactive` に処理を統一し、stdin待ちや`.env.sec`確認を行わない。`human_ask`は入力待ちをせずLLMに自律判断を促す
- 非対話モードでは `AGENTS.md` / `CLAUDE.md` を自動読み込みせず、作業ディレクトリ変更後も再読み込みしない
- 非TTYを含むプロンプト表示で、`[STATE]` を stale prompt より優先する
- ANSIの `CSI 2K` を使わず、Windowsコンソールで `?[2K` が表示されないようにする
- Qwen/llama.cppが省略整数引数を`0`で補完する場合の`read_file`引数を補正する

実装領域の個別テスト、ステータス表示テスト、非対話モードテスト、Pythonコンパイル、Ruffを再確認しました。Computer Useのエラーテストは、日本語ロケールでも表示文言に依存しない検証へ修正済みです。リポジトリ全体のテストは警告付きですが、**全テスト成功**を確認しています。なお、TaskStoreの`datetime.utcnow()`は`datetime.now(timezone.utc)`へ置き換え済みで、Python 3.14の非推奨警告は解消済みです。

## 結論

最優先で実装する順序は次のとおりです。

1. Agent Lifecycle
1. CredentialStore 共通化
1. SQLite TaskStore
1. 構造化 Observability の全境界適用
1. Enterprise Policy Engine

主要なRuntime基盤とOS固有の秘密情報ストアは実装済みです。今後はCredential CLI、個別イベントのペイロード統一、分散合意、Plugin sandboxなど、残っている拡張を優先度順に進めます。

## 1. Agent Lifecycle

### 概要

Agent の実行状態を、CLI、Web、GUI、A2A、Auto-Pilot で共通化します。

```text
CREATED
  ↓
RUNNING
  ↓
WAITING_TOOL
  ↓
RUNNING
  ↓
COMPLETED
```

異常系として、次の状態も統一的に扱います。

```text
FAILED
CANCELLED
TIMEOUT
PAUSED
```

### 実装対象

- `src/uagent/runtime/lifecycle.py`
- Agent 状態の enum と遷移表
- `start()`、`pause()`、`resume()`、`cancel()`、`timeout()`
- `AgentLifecycle.wait()`（対象ステータス、timeout、cancel event）
- cancellation と timeout の統合
- CLI/Web/GUI/A2A の状態通知統合

### 現状

`AgentLifecycle` と `lifecycle_execution()` が実装され、CLI、Web、GUI、A2Aの主要な実行経路で状態を追跡します。キャンセル、タイムアウト、失敗、pause/resumeの状態遷移とテストがあります。

`agent.lifecycle.changed` を後方互換で維持しつつ、`agent.created`、`agent.started`、`agent.waiting_tool`、`agent.completed`、`agent.failed`、`agent.cancelled`、`agent.timeout` などの個別イベントを実装しました。`AgentLifecycle.wait()` は対象ステータス、タイムアウト、キャンセルイベントに対応します。

なお、`CancellationToken.wait()`、`OAuthCallback.wait()`、`RemoteAgentRuntime.wait()` などの待機APIは実装済みです。ここで未実装としているのは、`AgentLifecycle` 自体が提供する独立した待機APIです。

### 期待効果

- 実行中の Agent を確実にキャンセルできる
- タイムアウトを統一的に扱える
- 各 UI で同じ進捗状態を表示できる
- A2A の状態と実際の処理状態が一致する
- pause / resume の基盤ができる
- Auto-Pilot の継続・停止判定が明確になる

次の不整合を防止します。

```text
Task = CANCELLED
実際のLLM処理 = 継続中
```

## 2. CredentialStore 共通化

### 概要

OAuth token、refresh token、Provider API key、MCP credential、A2A credential、外部 API key を統一的に管理します。

### 推奨インターフェース

```python
class CredentialStore(Protocol):
    def get(self, name: str) -> Credential | None:
        ...

    def set(self, name: str, credential: Credential) -> None:
        ...

    def delete(self, name: str) -> None:
        ...
```

### 保存先の優先順位

```text
Encrypted Store
    ↓
Environment

`PersistentCredentialStore`、暗号化された `TokenStore`、および任意依存の `OSCredentialStore` が実装済みです。`python-keyring` が利用可能な環境では、Windows Credential Manager、macOS Keychain、Linux Secret Serviceなどのネイティブバックエンドを自動利用し、利用できない場合は暗号化ファイルへフォールバックします。CredentialStoreから取得できない場合は、従来どおり環境変数へフォールバックします。
```

### 期待効果

- 秘密情報の保存先を統一できる
- Windows Credential Manager、macOS Keychain、Linux Secret Service へ拡張できる
- OAuth token と Provider API key の扱いが一貫する
- ログへの秘密情報漏洩を防ぎやすくなる
- token の期限切れ、refresh、削除を共通化できる
- Provider ごとの認証実装の重複が減る

将来的には、次のような CLI 操作へ拡張できます。

```text
:credential list
:credential set openai
:credential remove github
```

CLIでは `:credential get|set|remove NAME` を利用できます。`set` は秘密入力をマスクし、`get` は秘密値を表示せず、`remove` は確認を要求します。バックエンドが名前列挙をサポートする場合は `:credential list` も利用できます。

## 3. SQLite TaskStore

### 概要

InMemory 中心の TaskStore を抽象化し、まず SQLite による永続化を追加します。

```text
TaskStore
├── InMemoryTaskStore
└── SQLiteTaskStore
```

Redis TaskStoreは実装対象外とします。TaskStoreはInMemoryTaskStoreとSQLiteTaskStoreを使用し、Redis Serverや`redis`（redis-py）ライブラリを新たな運用前提にしません。

### 期待効果

- プロセス再起動後もタスク履歴が残る
- 失敗したタスクを確認できる
- A2A の task history を保存できる
- Web で過去の実行履歴を表示できる
- checkpoint / recovery の基盤になる
- 監査ログとして利用できる

将来的には、次のような操作へ拡張できます。

```text
uag task list
uag task show <task-id>
uag task resume <task-id>
```

## 4. 構造化 Observability の主要境界適用

### 概要

既存のイベントログを、Agent、Task、LLM、Tool、OAuth、Credential の主要境界へ拡張します。個別イベント体系の完全適用は残課題です。

### 共通フィールド

```text
agent_id
session_id
task_id
tool_call_id
event_id
event_code
timestamp
provider
duration_ms
status
error_type
```

### イベント例

```text
agent.created
agent.started
agent.waiting_tool
agent.completed
agent.failed
agent.cancelled
agent.timeout
task.resumed
credential.accessed
oauth.started
oauth.completed
oauth.failed
tool.dispatch
tool.completed
```

### 期待効果

- どの処理で遅延したか分かる
- どのツールが失敗したか分かる
- Provider ごとのエラー率を比較できる
- Web、A2A、CLI の処理を同じ ID で追跡できる
- OAuth や credential 関連の失敗を調査できる
- 再現しにくい問題を解析できる

## 5. Enterprise Policy Engine

### 概要

現在の ToolPolicy を拡張し、Provider、Tool、MCP、Skill、外部ドメイン、Credential、Network、Confirmation を組織単位で制御します。

### ポリシー例

```yaml
tools:
  shell:
    action: deny
  file_delete:
    action: confirm

providers:
  openai:
    action: allow

mcp_servers:
  https://trusted.example.com: allow

network:
  default: deny
```

### 現状

Tool、Provider、MCP server、Network、Credential、Skill、Plugin、Roleに対する制御と、Tool dispatch境界でのdeny/confirm判定が実装されています。MCPとNetworkのallowlistは、URLのscheme、hostname境界、port、path境界を検証する厳密判定を実装済みです。allow actionを含むMCP定義では、未登録のendpointをdenyします。

### 期待効果

- 組織単位のセキュリティルールを適用できる
- ユーザーごとに権限を変えられる
- 危険な Tool や MCP を一括拒否できる
- 外部送信や IoT 操作に確認を強制できる
- Skill / Plugin の権限管理へ拡張できる
- 監査やコンプライアンスに対応しやすくなる

## 実装ロードマップ

> 凡例: `[x]` はリポジトリ内に実装とテストがある項目です。`[ ]` は未実装、または対象範囲の一部に留まる項目です。

### Phase A: Runtime 安定化

- [x] Agent Lifecycle (`src/uagent/runtime/lifecycle.py`)
- [x] Lifecycle と cancellation の統合 (`src/uagent/runtime/execution.py`)
- [x] Lifecycle event の追加 (`agent.created` / `agent.started` / `agent.waiting_tool` など)

### Phase B: 認証・タスク基盤

- [x] CredentialStore Protocol (`src/uagent/auth/credential_store.py`)
- [x] OAuth / Provider / MCP の統合（Provider・MCP OAuth・A2A は共通 CredentialStore を既定利用。環境変数・既存 TokenStore への後方互換フォールバックあり）
- [x] Secret access logging (`credential.accessed` / `credential.stored` / `credential.deleted`)
- [x] TaskStore Protocol (`src/uagent/a2a/task_store.py`)
- [x] SQLiteTaskStore (`src/uagent/a2a/task_store.py`)
- [x] restart recovery (`docs/RESTART_RECOVERY.md`; 実行中タスクを安全に FAILED 化)

### Phase C: 観測性・ポリシー

- [x] structured observability の主要境界への適用（CLI / Web / GUI / A2A / LLM / OAuth / Tool）
- [x] Agent Lifecycleの個別イベント体系（`agent.created` など）の完全適用
- [x] `AgentLifecycle.wait()`（対象ステータス、timeout、cancel event）
- [x] trace / duration / correlation ID（event_id / correlation_id / duration_ms / tool_call_id）
- [x] Enterprise Policy Engine (`src/uagent/tools/enterprise_policy.py`)
- [x] Skill / Plugin permission (`EnterprisePolicy` + runtime plugin loading)
- [x] MCP / network allowlist (`EnterprisePolicy`)

### Phase D: 高度化

- [x] Checkpoint / Recovery (`TaskStore.save_checkpoint` / `load_checkpoint`)
- [x] DAG-based Tool Scheduler (`src/uagent/runtime/dag_scheduler.py`)
- [x] Distributed A2A (`RemoteAgentRuntime` over A2A)
- [x] Multi-Agent orchestration (`runtime.multi_agent`)
- [x] Remote Agent Runtime (`runtime.remote_agent`)

> 注記: etcd / ZooKeeper 相当の本格的な consensus、ネットワーク分断耐性、OpenTelemetry の完全導入は、外部基盤を必要とする別スコープです。現行実装は共有ファイル lease と A2A の認証済み task / checkpoint / SSE 同期を提供します。

### ロードマップの集計

| フェーズ | 実装済み | 全項目 | 状況 |
|---|---:|---:|---|
| Phase A: Runtime 安定化 | 3 | 3 | Lifecycle、個別イベント、待機APIを実装済み |
| Phase B: 認証・タスク基盤 | 6 | 6 | CredentialStore、TaskStore、SQLite、restart recoveryを実装済み |
| Phase C: 観測性・ポリシー | 6 | 6 | 主要境界とLifecycle個別イベントを実装済み |
| Phase D: 高度化 | 5 | 5 | Checkpoint、Scheduler、Distributed/Remote/Multi-Agentを実装済み |
| **合計** | **20** | **20** | **100%** |

ロードマップ上の主要項目は実装済みです。今後は、llama.cppの`/props`やOllamaの`/api/show`情報の各UIへの表示統一、個別イベントのCLI/Web/GUI/A2Aでのペイロード統一、分散合意、Plugin sandboxなどの拡張を進めます。

## 現行実装との注意点

ロードマップの主要項目は実装済みですが、次の点は「実装済み」と「完全運用」を分けて扱います。

- Enterprise PolicyのMCP / Network allowlistは、scheme、hostname境界、port、path境界を検証する厳密判定を実装済みです。allow actionを含むMCP定義では、未登録endpointをdenyします。
- Distributed A2Aは共有ファイルleaseと認証済みA2A task / checkpoint / SSE同期を提供します。etcd / ZooKeeper相当のconsensusやネットワーク分断耐性は未実装です。
- Observabilityは主要境界に適用済みで、共通envelope（`schema_version`、`event_id`、`correlation_id`、`timestamp`、`status`、`event_code`）を追加しました。イベント固有payloadの完全統一は継続課題です。
- Computer Useエラーテストは日本語ロケールでも表示文言に依存しない検証へ修正済みです。リポジトリ全体のテストは警告付きですが成功しています。

## 今後の実装優先順位

ロードマップの主要基盤は実装済みのため、残課題はリスクと依存関係を考慮して次の順序で進めます。

### P0: 品質ゲート

- [x] 日本語ロケールでも成立するComputer Useエラーテストへ修正
- [x] 全体テスト、Ruff、Black、受入チェックを安定して成功させる

### P1: セキュリティ境界

- [x] MCP / Network allowlistをscheme、hostname境界、port、path境界の厳密判定へ強化
- Plugin sandboxを強化（作業ディレクトリ、ネットワーク、subprocess、リソース制限）

### P2: 観測性

- CLI / Web / GUI / A2Aのイベントpayloadとschemaを統一
- schema統一後にOpenTelemetryのtrace/span/exporterを導入

### P3: 分散実行

- Distributed A2Aのlease競合、再接続、二重実行、ネットワーク分断を強化
- 必要性が明確になった場合にetcd / ZooKeeper相当のconsensusを検討

### P4: スケール対応

- Redis TaskStoreは実装対象外
- TaskStoreはInMemoryTaskStoreとSQLiteTaskStoreを使用する

OpenTelemetry、Plugin sandbox、consensusは、要件と外部基盤を確認してから着手します。

## 全体的な改善効果

改善後は、各 UI が個別に状態・ログ・認証を管理するのではなく、共通 Agent Runtime を利用します。

```text
CLI
Web
GUI
A2A
  │
  ▼
共通 Agent Runtime
  ├── Lifecycle
  ├── Cancellation
  ├── TaskStore
  ├── CredentialStore
  ├── Policy Engine
  └── Observability
```

その結果、uag は次の能力を持つようになります。

- 入口が増えても挙動がぶれない
- キャンセルや失敗処理が正確になる
- 再起動や復旧に強くなる
- 認証情報を安全に管理できる
- 問題の原因を追跡できる
- 新機能追加時の重複実装が減る
- 企業向けの制御を追加しやすくなる

> **「動く」だけでなく、「止められる・再開できる・追跡できる・安全に制御できる」Agent Runtime にすることが目標です。**

## I18N 注意事項

I18N は表示文言だけでなく、Agent 実行コンテキストの一部として扱います。

- 非同期処理では `contextvars` を使ってロケールを伝播する
- CLI、Web、GUI、A2A の入口でロケールを確定する
- ユーザー向けメッセージを直接ハードコードしない
- ログ・イベントコード・API の状態値はローカライズせず、安定した機械可読値を使用する
- 翻訳キーを追加・変更した場合は、各言語の未翻訳・プレースホルダー不一致を確認する
- 技術用語、Provider 名、Tool 名、イベントコード、API フィールド名は原則として翻訳しない
- 非対話型実行、エラー処理、キャンセル処理でもロケールを失わない
- README や設計文書を更新する場合は、各国語版との同期要否を確認する

## TDD 開発方針

今後の実装は、原則としてテスト駆動開発（TDD）で進めます。

```text
Red    → 失敗するテストを先に追加
Green  → テストを通す最小限の実装
Refactor → 重複・責務・型・可読性を改善
```

### 実装単位ごとの手順

1. 要件と受入条件をテストケースへ分解する
1. まず失敗する単体テストまたは統合テストを追加する
1. 最小限の実装でテストを成功させる
1. I18N、エラー、キャンセル、権限境界を含む回帰テストを追加する
1. リファクタリング後に対象テストと全体テストを実行する
1. `python scripts/acceptance_check.py` が `acceptance: OK` になることを確認する
1. 仕様変更や設計判断を本ドキュメントまたは `ARCHITECTURE.md` に追記する

### TDD の完了条件

- 新しい動作に対応するテストが先に存在する
- 正常系だけでなく、異常系・境界値・キャンセル・ロケールを検証する
- 外部 API や OAuth は実通信に依存しないテストも用意する
- Tool Safety と confirmation の拒否経路を検証する
- 既存テストを壊していない
- import graph、ruff、全体受入チェックが成功する

## 関連文書

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [README_AUTO.md](README_AUTO.md)
