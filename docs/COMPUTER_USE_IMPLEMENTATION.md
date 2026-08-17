# Computer Use 実装・統合ガイド

## Runtime の注入

CLI、GUI、Web、A2Aは、起動時に生成したRuntimeを共通bootstrapへ注入します。

```python
from uagent.computer_use import configure_computer_use

configure_computer_use(
    core,
    provider=provider,
    model=model,
    runtime=runtime,
)
```

`configure_computer_use()` は `UAGENT_COMPUTER_USE` のPolicyを読み取り、
`core.computer_use_runtime` と既存LLM round loopのhandlerを設定します。

現在のエントリーポイントRuntime managerはBrowserRuntimeとDesktopRuntimeを両方生成し、
`manager.runtimes["browser"]` / `manager.runtimes["desktop"]` として登録します。
既存のhandler APIではBrowserRuntimeを既定Runtimeとして使用します。
`core.computer_use_browser_runtime` と `core.computer_use_desktop_runtime` にも登録され、
終了時には両Runtimeが解放されます。

## 安全上の既定値

- Computer Useは既定で無効（`UAGENT_COMPUTER_USE=1` で明示的に有効化）
- 有効化時も確認を既定で要求
- 許可アクション、ドメイン、最大Action数、最大Turn数をPolicyで制限
- Runtime未設定で有効化した場合は実行せず明示的に失敗
- Providerの外部画面情報は信頼できないコンテンツとして扱う

## テスト方針

TDDで次の順に検証します。

1. Action正規化、Policy、Safety、Audit
1. Mock Runtimeによるround loop
1. Anthropic/OpenAI/Gemini adapterの契約テスト
1. 実API E2E（資格情報と明示フラグがある場合のみ）
1. Playwright/OS backendを用いた実環境テスト（明示フラグがある場合のみ）
1. 38ロケールのI18Nキー検証

実API・実環境テストは通常のCIでは実行せず、破壊的操作を許可しません。

## 現在の実装状態

- Capability / Action / Policy / Audit: 実装済み
- Mock / Browser-like / Desktop-like Runtime: 実装済み
- Anthropic / OpenAI / Gemini / Bedrock / Custom adapter: 実装済み
- 既存round loopへのhandler接続: 実装済み
- 共通Runtime bootstrap: 実装済み
- BrowserRuntime / DesktopRuntimeの同時生成・登録: 実装済み
- 実API E2E・実Browser/Desktop E2E: opt-inテストとして追加予定（Webは実起動せず、静的確認のみ）
- 38言語のComputer Use専用メッセージ監査: 完了
- 38ロケールのPO/MOへComputer Use関連メッセージを反映: 完了
- I18Nカタログ監査: `tools_scanned=221`、`missing_units=0`
- I18N関連テストおよびComputer Useテスト: 完了

### 検証済みの範囲

- `babel.cfg` にComputer Useのgettext対象を追加
- CLI/GUI/Computer Useの確認文、Capability/Policy/Runtimeエラーをgettext化
- 38ロケールの翻訳リソースをコンパイル済み
- Webサーバーは起動せず、GUI/Webの共有 `human_ask` 経路は静的に確認
- 最新コミット: `0ded704e`（push済み）
