# TODO: Sub-Agent Extensions

## 1. 専門サブエージェントのロードマップ
以下の専門サブエージェントを順次追加し、Orchestrator（親）の自律開発・デバッグループを強力に支援します。

- [x] **`planner`** (計画作成): ステップ、リスク、制約の設計
- [x] **`reviewer`** (監査レビュー): バグ・仕様不一致・無限ループの検出
- [x] **`summarizer`** (情報圧縮): 長い履歴やログの圧縮・要約
- [x] **`patch_designer`** (修正パッチ設計): 差分パッチ案の設計・提案
- [x] **`error_analyst`** (エラー解析・デバッグ): 実行エラー、スタックトレースの根本原因特定（今回実装）
- [ ] **`dependency_resolver`** (依存関係解決): ImportError等のパッケージ・依存関係解決案の提示
- [ ] **`refactoring_expert`** (リファクタリング): クリーンコード、可読性、PEP 8基準の美化提案
- [ ] **`test_designer`** (テストケース設計): 境界値やエラー系を網羅したpytestテストコード設計
- [ ] **`security_vulnerability_auditor`** (セキュリティ監査): 脆弱性や秘密情報の混入チェック
- [ ] **`user_intent_clarifier`** (曖昧さ解消): 仕様決定のための簡潔な質問設計

## 2. 実装済みエージェントの検証ステータス
- `run_sub_agent` ツールに `error_analyst` が追加され、スモークテスト（I18NおよびPythonコンパイル）をクリアしていることを確認。
