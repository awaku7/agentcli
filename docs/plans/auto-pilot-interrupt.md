# Auto-Pilot / Interrupt残課題

- Status: planned
- Priority: P1
- Source: [`docs/INTERRUPT.md`](../INTERRUPT.md)、[`src/uagent/docs/AUTO_REVIEW.md`](../../src/uagent/docs/AUTO_REVIEW.md)

## 対象候補

- 他プロバイダのストリーミング中割り込み
- non-streaming経路の遅延対応
- 環境変数による割り込み動作のカスタマイズ
- CLI / Web / GUIの停止表示と状態同期

## 受け入れ条件

- F11によるAuto-Pilot終了とF12による応答中断を混同しない
- UI表示と実行状態が一致する
- 通常対話へ戻った後にAuto-Pilot状態が残らない
