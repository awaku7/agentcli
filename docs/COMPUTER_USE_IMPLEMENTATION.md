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
Runtimeを自動生成しないため、Browser/Desktopの権限・ライフサイクルは各入口が管理します。

## 安全上の既定値

- Computer Useは既定で無効
- 有効化時も確認を既定で要求
- 許可アクション、ドメイン、最大Action数、最大Turn数をPolicyで制限
- Runtime未設定で有効化した場合は実行せず明示的に失敗
- Providerの外部画面情報は信頼できないコンテンツとして扱う

## テスト方針

TDDで次の順に検証します。

1. Action正規化、Policy、Safety、Audit
2. Mock Runtimeによるround loop
3. Anthropic/OpenAI/Gemini adapterの契約テスト
4. 実API E2E（資格情報と明示フラグがある場合のみ）
5. Playwright/OS backendを用いた実環境テスト（明示フラグがある場合のみ）
6. 38ロケールのI18Nキー検証

実API・実環境テストは通常のCIでは実行せず、破壊的操作を許可しません。

## 現在の実装状態

- Capability / Action / Policy / Audit: 実装済み
- Mock / Browser-like / Desktop-like Runtime: 実装済み
- Anthropic / OpenAI / Gemini / Bedrock / Custom adapter: 実装済み
- 既存round loopへのhandler接続: 実装済み
- 共通Runtime bootstrap: 実装済み
- 各エントリーポイントの実Runtime生成: 次段階
- 実API E2E・実Browser/Desktop E2E: opt-inテストとして追加予定
- 38言語のComputer Use専用メッセージ監査: 最終段階
