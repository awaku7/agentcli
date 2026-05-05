# TODO

## P0: LLM 通信の Ctrl-C 対応と BUSY 固着防止

### 状況
- かなり改善済み。
- ただし Windows での再現テストが必要。
- 完全な即時停止は別プロセス化が最有力。

### 残タスク
- Windows でネットワーク断 / DNS 不達 / Firewall drop を再現して手動テストする。
- Ctrl-C で中断できることを確認する。
- BUSY 表示や状態が固着しないことを確認する。

### 優先度
- 無限ハング防止: 必須
- UI 状態の復帰: 必須
- 即時キャンセル: 努力目標

## P1: `src/uagent/tools/system_specs_tools.py` の物理ディスク情報

- Windows / macOS で物理ディスクのモデル・種別を best-effort で取得する。
- 既存の軽量実装を壊さない範囲で検討する。

## P2: Playwright Inspector の出力改善

- 遷移ごとに `pages/0001_...` 形式で HTML / PNG を保存する。
- `index.jsonl` で URL / title / 時刻 / ファイル名 を一覧化する。
- `latest.html` を別途保存する。
- SPA 対応を強化する。

## 保留

- 翻訳 provider の追加検討は削除済み。必要時に別途整理する。
