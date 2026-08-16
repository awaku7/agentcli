# agentcli Computer Use 設計書

## 1. 目的

agentcli に Computer Use（CUA: Computer-Using Agent）機能を追加する。

モデルが返したスクリーンショット要求、クリック、キーボード入力、スクロールなどのアクションを、agentcli 側の Computer Runtime で実行し、その結果を次のLLMターンへ返す。

本機能では、次の責務を分離する。

```text
LLM Provider
    ↓ tool call / computer action
Provider Adapter
    ↓ 正規化されたComputer Action
Computer Runtime
    ↓ 実OS・ブラウザー操作
Screenshot / Action Result
    ↓
LLM Provider
```

- **Capability Discovery**: モデルとプロバイダーがComputer Useに対応しているかを判断する
- **Provider Adapter**: プロバイダー固有のtool形式を正規化する
- **Computer Runtime**: スクリーンショット、マウス、キーボードを実行する
- **Safety Layer**: 実行許可、確認、サンドボックス、監査を制御する

agentcli は実行系、llmcapa はモデル能力のデータベースとして扱う。

## 2. 対象範囲

### 初期対応

- Anthropic Claude Computer Use
- OpenAI Responses API Computer Tool
- Google Gemini Computer Use
- Amazon Bedrock 経由の Anthropic Computer Use
- OpenRouter、Qwen、ローカルモデルなどのカスタムハーネス
- Windows、macOS、Linux上のデスクトップ操作
- Playwrightを利用したブラウザー操作

### 初期対象アクション

```text
screenshot
left_click / click
right_click
middle_click
double_click
mouse_move / move
type
key / keypress
scroll
left_click_drag / drag
wait
```

`zoom` などのプロバイダー固有アクションは、capabilityで対応を確認してから利用する。

### 対象外

- 未確認モデルへの自動フォールバック
- ユーザー確認なしの購入、送信、削除、権限変更
- プロバイダー固有のアクションを別プロバイダーへ無条件変換
- 画面上の第三者コンテンツを信頼済み指示として扱うこと

## 3. 既存agentcliとの統合方針

agentcliの既存ツールシステムは、通常のFunction Toolを次の形式で管理している。

```text
src/uagent/tools/<name>_tool.py
    ├─ TOOL_SPEC
    └─ run_tool(args) -> str
```

Computer Useのネイティブツールは、通常のJSON Schema Function Toolとは異なる場合がある。そのため、次の2種類を分離する。

### 3.1 通常のComputer Tool

OpenAI互換APIやUAG側ハーネスで、通常のFunction Toolとして定義する方式。

```text
computer_screenshot
computer_click
computer_type
computer_scroll
```

### 3.2 ネイティブProvider Tool

Anthropicなど、APIがスキーマレスなComputer Toolを提供する方式。

```json
{
  "type": "computer_20251124",
  "name": "computer",
  "display_width_px": 1920,
  "display_height_px": 1080,
  "display_number": 1,
  "enable_zoom": true
}
```

これは既存の `tools.get_tool_specs()` へ通常のJSON Schemaツールとして登録せず、各Provider Adapterがネイティブpayloadとして追加する。

## 4. 正規化データモデル

agentcli側では、llmcapa 0.5.7以降が提供する `ComputerUseCapability` を正規情報源として利用する。llmcapaはComputer Use機能に必須の依存関係とし、Computer Useを有効にする構成では必ずインストールする。UAG側にモデル情報のコピーや独自レジストリは持たせない。llmcapaが利用できない環境では、Computer Useを対応不可として明示的に停止する。

```python
@dataclass(frozen=True)
class ComputerUseCapability:
    supported: bool
    native: bool
    provider: str
    model: str
    api_type: str | None = None
    tool_type: str | None = None
    tool_version: str | None = None
    status: str = "unknown"
    environments: frozenset[str] = frozenset()
    actions: frozenset[str] = frozenset()
    requires_beta: bool = False
    beta_header: str | None = None
    enable_zoom: bool = False
    source_url: str | None = None
    checked_at: str | None = None
```

### 4.1 `native` の意味

```text
native=True
  Provider APIがComputer Toolをネイティブに提供する

native=False
  モデルと外部Computer Runtimeを組み合わせる
  ProviderのネイティブComputer Toolを意味しない
```

### 4.2 バージョンと互換性

`tool_version` は記録用メタデータとして扱う。新しいバージョンだから自動的に互換とは判定しない。

互換性の判定基準は次のとおり。

- API種別
- tool type / schema
- 対応環境
- 必要アクション
- ベータヘッダーなどの必須条件

## 5. Provider Adapter

```python
class ComputerProviderAdapter(Protocol):
    provider: str

    def build_tools(
        self,
        capability: ComputerUseCapability,
        display: DisplayInfo,
    ) -> list[dict]: ...

    def parse_actions(self, response: object) -> list[ComputerAction]: ...

    def build_tool_result(
        self,
        action: ComputerAction,
        result: ComputerActionResult,
    ) -> object: ...
```

候補モジュール:

```text
src/uagent/computer_use/
    __init__.py
    capability.py
    actions.py
    runtime.py
    safety.py
    loop.py
    adapters/
        __init__.py
        anthropic.py
        openai.py
        gemini.py
        bedrock.py
        custom.py
```

### 5.1 Anthropic Adapter

- Messages APIを利用する
- `computer_20251124` / `computer_20250124` をモデルcapabilityから選択する
- `computer-use-2025-11-24` などのベータヘッダーを付ける
- `tool_use` の入力を正規化する
- `tool_result` にスクリーンショットまたは実行結果を返す

### 5.2 OpenAI Adapter

- Responses APIの `computer` toolを利用する
- `computer_call` を処理する
- `actions[]` を正規化する
- アクション実行後に `computer_call_output` を返す

### 5.3 Gemini Adapter

- Gemini API固有のComputer Use形式を処理する
- Geminiのアクション名を正規化する
- Browser / Desktop / Mobileの環境差をcapabilityで確認する

### 5.4 Bedrock Adapter

- Bedrock Runtime / Bedrock Mantleのエンドポイント差を吸収する
- Anthropic Messages互換のpayloadを利用する
- `anthropic_beta` と `tools` の対応をモデル単位で設定する
- リージョン別モデルID、推論プロファイルを考慮する

### 5.5 Custom Adapter

Qwen、OpenRouter、Ollama、ローカルモデルなど、ネイティブComputer Toolを提供しない経路で利用する。

```text
native=False
api_type=custom_harness
```

モデルへ通常のツールスキーマを提示し、戻された関数呼び出しをComputer Runtimeへ渡す。

## 6. Computer Action

Provider固有形式から、次の正規化形式へ変換する。

```python
@dataclass(frozen=True)
class ComputerAction:
    action_id: str
    action: str
    coordinate: tuple[int, int] | None = None
    text: str | None = None
    key: str | None = None
    button: str | None = None
    scroll_x: int | None = None
    scroll_y: int | None = None
    region: tuple[int, int, int, int] | None = None
```

対応例:

| 正規化アクション | 例 |
|---|---|
| `screenshot` | 現在の画面を取得 |
| `click` | 座標とボタンを指定してクリック |
| `type` | テキストを入力 |
| `keypress` | キーまたはキー組み合わせを送信 |
| `scroll` | 指定方向へスクロール |
| `drag` | 座標列に沿ってドラッグ |
| `wait` | 指定時間待機 |
| `zoom` | 指定領域を拡大 |

未対応アクションはRuntimeで実行せず、明示的なエラーを返す。

## 7. Computer Runtime

```python
class ComputerRuntime(Protocol):
    def screenshot(self) -> Screenshot: ...
    def click(self, x: int, y: int, button: str = "left") -> None: ...
    def move(self, x: int, y: int) -> None: ...
    def type_text(self, text: str) -> None: ...
    def keypress(self, key: str) -> None: ...
    def scroll(self, x: int, y: int, dx: int, dy: int) -> None: ...
    def drag(self, path: list[tuple[int, int]]) -> None: ...
    def wait(self, seconds: float) -> None: ...
```

### 7.1 Browser Runtime

Playwrightを優先する。

- ブラウザーを分離して起動する
- 拡張機能と不要なファイルアクセスを無効化する
- viewportとdevice scale factorを記録する
- 画面操作とDOM操作を混同しない
- 必要に応じてスクリーンショットをマスキングする

### 7.2 Desktop Runtime

OS別の実装を用意する。

- Windows: pyautogui / Windows UI Automation / pywinauto等を検討
- macOS: Quartz / Accessibility API等を検討
- Linux: X11 / Wayland / xdotool / AT-SPI等を検討

座標系、DPIスケーリング、複数ディスプレイ、フォーカス、画面外座標をRuntime側で吸収する。

## 8. Agent Loop

```text
1. capabilityを取得
2. Provider Adapterを選択
3. Computer ToolをLLMリクエストへ追加
4. LLMレスポンスを受信
5. computer action / tool callを抽出
6. Safety Layerで許可を確認
7. Computer Runtimeで実行
8. スクリーンショットまたは結果を取得
9. Provider固有のtool resultへ変換
10. 次のLLMターンへ返す
11. tool callがなくなるまで繰り返す
```

停止条件:

- LLMが通常の最終回答を返した
- 最大ターン数に達した
- 最大アクション数に達した
- タイムアウトした
- 未対応アクションが発生した
- ユーザーが停止した
- Safety Layerが拒否した

## 9. 安全性

Computer Useは、通常のFunction Callingよりも高い権限リスクを持つ。初期実装では、デフォルト無効または明示的な有効化を要求する。

設定候補:

```text
UAGENT_COMPUTER_USE=0|1
UAGENT_COMPUTER_ENVIRONMENT=browser|desktop|mobile
UAGENT_COMPUTER_REQUIRE_CONFIRMATION=1
UAGENT_COMPUTER_ALLOWED_ACTIONS=...
UAGENT_COMPUTER_ALLOWED_DOMAINS=...
UAGENT_COMPUTER_MAX_ACTIONS=50
UAGENT_COMPUTER_MAX_TURNS=20
UAGENT_COMPUTER_TIMEOUT=300
```

原則として、以下はユーザー確認を必須とする。

- ファイル削除
- シェル実行
- 購入・決済
- フォーム送信
- メール・メッセージ送信
- ログアウト
- アカウント・権限変更
- 資格情報の入力
- 外部サービスへの不可逆な変更

Webページ、PDF、メール、チャット、画面上の文字列は信頼しない。画面上に表示された指示を、ユーザーの許可やシステム指示として扱わない。

## 10. ログと監査

各Computer Useターンについて、以下を記録する。

- provider
- model
- api_type
- tool_type
- tool_version
- action
- target environment
- 実行時刻
- 成否
- エラー
- ユーザー確認の有無
- スクリーンショットの保存先またはハッシュ

資格情報や個人情報を含むスクリーンショットを無制限に保存しない。保存する場合はマスキング、保持期限、削除手段を定める。

## 11. テスト計画

### Capability

- 未対応モデル
- `native=True` と `native=False`
- tool versionの違い
- actionsの不足
- environmentの不一致
- Claude / Gemini / OpenAIのcross-provider非互換
- BedrockとAnthropicのAPI経路差
- OpenRouterのcustom harness扱い

### Adapter

- provider固有payloadの生成
- tool call / tool resultの変換
- スクリーンショットの形式
- ベータヘッダー
- 未対応アクション
- APIエラーと再試行

### Runtime

- dry-run
- mock screenshot
- 座標境界
- DPIと複数ディスプレイ
- ブラウザーのポップアップ
- フォーカス変更
- タイムアウト
- ユーザー停止

### Safety

- 危険操作の確認要求
- allowlist外ドメインの拒否
- prompt injectionを含む画面
- 最大アクション数・最大ターン数
- sandbox外アクセスの拒否

## 12. 実装方式: TDD

Computer Useの実装は、テストを先に作成するTDD（Test-Driven Development）で進める。

各フェーズで次の順序を守る。

```text
1. 期待する振る舞いをテストで定義
2. テストが失敗することを確認
3. 最小限の実装を追加
4. テストを通す
5. リファクタリング
6. 全体テストを実行
```

### TDDの対象

- `ComputerAction` の正規化
- `action_id` / `session_id` / `turn_id` の追跡
- Capability lookupとllmcapa連携
- Provider Adapterのpayload変換
- tool call / tool resultの変換
- `ComputerUsePolicy` の許可判定
- before/after Safety処理
- User Confirmation
- Browser / Desktop Runtimeのmock
- タイムアウト、停止、最大アクション数
- Audit情報の生成
- Claude / OpenAI / Gemini / Bedrockのcross-provider境界
- I18Nメッセージの存在とフォールバック

実Runtimeや外部APIに依存するテストは、mock / fake / dry-runを基本とする。Provider APIを使うE2Eテストは、明示的なオプトインがない限り実行しない。

## 13. 実装フェーズ

### Phase 1: Capabilityと設定

- Computer Use設定を追加
- capability lookupを追加
- `native` とcustom harnessを区別
- dry-run判定を追加

### Phase 2: Runtime

- Browser Runtimeを実装
- screenshotと基本操作を実装
- action normalizationを実装
- safety gateを実装

### Phase 3: Anthropic

- native tool payload
- beta header
- tool_use / tool_result loop
- Claude向けテスト

### Phase 4: OpenAI / Gemini

- Responses API adapter
- Gemini adapter
- cross-providerテスト

### Phase 5: BedrockとCustom Harness

- Bedrock Runtime / Mantle
- OpenRouter
- Qwen / Ollama / ローカルモデル

### Phase 6: GUI/Web/A2A統合

- CLI
- GUI
- Web
- A2A

すべてのエントリーポイントで、Computer Useの有効化、停止、確認、ログ方針を一致させる。

## 14. 未決定事項

- Windows Desktop Runtimeの採用ライブラリ
- macOS / Linux対応の優先順位
- Browser RuntimeとDesktop RuntimeのAPI統合方法
- スクリーンショットの圧縮・マスキング
- Computer Use専用UIの設計
- Provider Adapterの既存LLM round loopへの挿入位置
- tool catalog / genre maskとの統合方法
- 既存の通常ツール実行ループとのエラー境界

## 15. I18N: 38か国語対応

Computer Use機能で追加するユーザー向けメッセージ、LLM向けメッセージ、確認ダイアログ、エラー、Safety通知、監査表示は、agentcli既存のI18N機構を利用して**38か国語**に対応する。

対象には次を含む。

#### ユーザー向け

- Computer Useの有効化・無効化
- ユーザー確認メッセージ
- 危険操作の警告
- 未対応アクションのエラー
- 未対応環境のエラー
- Provider Adapterの変換エラー
- Runtimeのタイムアウト・実行失敗
- Safety Layerによる拒否
- Audit画面・ログの表示文言

#### LLM向け

- Computer Toolの利用説明
- ComputerActionの実行ルール
- スクリーンショット確認の指示
- 操作後の検証指示
- Safety制約、許可範囲、停止条件
- 未対応アクションやRuntimeエラーの通知
- Browser / Desktop / Mobile環境の説明
- Prompt Injection対策のシステム指示
- Provider Adapterが生成するtool result内の説明文

ユーザー向け文言とLLM向け文言は、同じ翻訳キーを無理に共有せず、用途を区別したキー名前空間で管理する。LLM向けメッセージも、選択された言語で自然に対話できる表現を用意する。モデルの理解に影響するため、翻訳の正確性、プレースホルダー、操作名、禁止事項をテストで検証する。
実装ルール:

- ユーザー向け、LLM向けともにハードコードした自然言語文字列を追加しない
- 既存のgettext / localeリソースを利用する
- ユーザー向けとLLM向けで用途別のメッセージキーを管理する
- プレースホルダー名を全言語で一致させる
- action名、tool type、APIフィールド名、enum値などのプロトコル識別子は翻訳しない
- 未翻訳時は英語へフォールバックする
- `.po` / `.mo` のコンパイルを行う
- 翻訳の未登録、重複、プレースホルダー不一致をCIで検出する
- CLI、GUI、Web、A2Aで同じメッセージキーを共有する

受け入れ条件は、ユーザー向け・LLM向けの両方について38言語すべてで翻訳リソースの検証が通り、未翻訳時も英語フォールバックで動作することとする。LLM向けメッセージは、操作名・禁止事項・プレースホルダーが壊れていないことをテストで確認する。

## 16. 受け入れ基準

- Computer Useを明示的に有効化しない限り、既存のagentcli動作が変わらない
- 未対応モデルを誤ってComputer Use対応と判定しない
- Claude / Gemini / OpenAIのネイティブツール形式を混同しない
- Computer Use actionの実行前にSafety Layerを通過する
- 危険操作にユーザー確認が入る
- dry-runとmockでRuntimeなしのテストが可能
- CLI、GUI、Web、A2Aで設定と停止条件が一致する
- 既存テストがすべて通過する

## 17. レビュー反映版の実装決定

### 17.1 推奨アーキテクチャ

Computer Useの処理経路は、次の責務分離を維持する。

```text
LLM
  ↓
Provider Adapter
  ↓
ComputerAction
  ↓
Safety Layer
  ↓
BrowserRuntime / DesktopRuntime
  ↓
Screenshot / Result
  ↓
Provider Adapter
  ↓
LLM
```

LLMから生成されたアクションをRuntimeへ直接渡さない。必ず `Provider Adapter → ComputerAction → Safety Layer → Runtime` の経路を通す。

### 17.2 llmcapaとの責務分離

`llmcapa 0.5.7` をComputer Use capabilityの正規情報源とする。UAG側で同じモデル情報を独自管理しない。

```text
UAG → llmcapa → ComputerUseCapability
```

UAG内部に互換型が必要な場合も、コピーしたデータベースではなく、読み取り専用のViewまたはAdapterとして実装する。

### 17.3 `ComputerAction.action_id`

Providerから返されたComputer Callと実行結果を対応付けるため、§6で定義した正規化アクションに `action_id` を必須で持たせる。

追跡単位は次の階層とする。

```text
session_id
  └─ turn_id
       └─ action_id
            └─ result
```

### 17.4 座標系

座標系が混在する可能性に備え、将来的に次の区別を可能にする。

```python
class CoordinateSpace(str, Enum):
    SCREEN = "screen"
    VIEWPORT = "viewport"
    NORMALIZED = "normalized"
```

初期実装ではRuntime内部で変換を吸収してよい。ただし、スクリーン座標、ブラウザーviewport、CSS pixel、physical pixelを混同しない。

### 17.5 `ComputerUsePolicy`

環境変数だけで安全設定を管理せず、すべてのエントリーポイントで共有するPolicyオブジェクトを持つ。

```python
@dataclass(frozen=True)
class ComputerUsePolicy:
    enabled: bool
    environment: str
    require_confirmation: bool
    allowed_actions: frozenset[str]
    allowed_domains: frozenset[str]
    max_actions: int
    max_turns: int
    timeout: float
```

CLI、GUI、Web、A2AはPolicyの入力を提供し、実行時には同一のSafety Layerを利用する。

```text
CLI ─────┐
GUI ─────┤
Web ─────┼──> ComputerUsePolicy
A2A ─────┘
```

### 17.6 Safety Layerのbefore / after分離

Safety Layerは実行前と実行後の両方で動作する。

```text
before_execute
  ↓
Safety Policy
  ↓
User Confirmation
  ↓
Runtime
  ↓
after_execute
  ↓
Audit
```

実行前には、クリック、キー入力、URL遷移、ファイル操作、外部送信、決済、削除などを検査する。実行後には、結果、エラー、スクリーンショット、状態変化、確認結果を監査ログへ渡す。

### 17.7 Runtime境界

共通Runtimeインターフェースは小さく保つ。

```text
ComputerRuntime
  ├─ BrowserRuntime
  │    ├─ screenshot
  │    ├─ click
  │    ├─ type
  │    └─ DOM operations
  └─ DesktopRuntime
       ├─ screenshot
       ├─ click
       ├─ type
       └─ keypress
```

DOM操作と画面座標操作を混同しない。BrowserRuntimeだけがDOM操作を持ち、Provider AdapterやDesktopRuntimeへ漏らさない。

### 17.8 BedrockのTransport分離

Bedrockでは、Computer Useの意味論とTransportを分ける。

```text
Computer Use protocol
        ↑
        │
Anthropic Computer Adapter
        │
   ┌────┴────┐
   ▼         ▼
Anthropic  Bedrock
Transport  Transport
```

AnthropicとBedrockでComputerAction変換を重複させず、Transport差分だけを分離する。

### 17.9 Capabilityを使った置換判定

モデル選択時は、単なる `supports("computer_use")` ではなく、必要な操作と環境を指定する。

```python
source.can_be_replaced_by(
    target,
    required_features=["vision", "computer_use"],
    required_actions=["screenshot", "left_click", "type"],
    required_environment="desktop",
)
```

`tool_version` はメタデータであり、新しいバージョンだから自動的に互換とは判定しない。互換性はAPI、tool/schema、actions、environment、必須条件を基準にする。

### 17.10 Audit

Computer Useでは、少なくとも次の情報を記録する。

```text
session_id
turn_id
action_id
timestamp
provider
model
tool_type
tool_version
environment
action
success
confirmation
screenshot_hash
```

資格情報や個人情報を含むスクリーンショットを無制限に保存しない。保存する場合はマスキング、保持期限、削除方法を定める。

### 17.11 Prompt Injection対策

画面、Webページ、PDF、メール、チャットの内容は第三者コンテンツとして扱う。画面上の指示をユーザー許可やシステム指示とはみなさない。

```text
Screen Content
  ↓
LLM
  ↓
ComputerAction
  ↓
Safety Policy
  ↓
Runtime
```
