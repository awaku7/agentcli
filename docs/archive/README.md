# 実装済み・過去の設計記録

このディレクトリは、現行の機能仕様や未完了の実装計画ではなく、過去の設計判断・完了判定を参照するための保管場所です。記載された当時の実装状況を現在の状態と混同しないでください。

- [Sub-Agent Job Runtime V1 設計](sub-agent-job-runtime-v1.md) — V1 実装済みの設計履歴。現在の説明は [Sub-Agent](../subagent.md) を参照。
- [UAG Memory Architecture V2](UAG_MEMORY_ARCHITECTURE_V2.md) — 2026年9月のV2設計・再レビュー記録。現行の認証・共有境界は [Memory V3](../UAG_MEMORY_ARCHITECTURE_V3.md) を参照。
- [Memory V2 Completion Decision](MEMORY_V2_COMPLETION.md) — V2の既定有効化・評価結果・完了判定。現行の運用仕様は [Memory](../MEMORY.md)、評価ゲートは [Memory Evaluation](../MEMORY_EVALUATION.md) を参照。
- [改善優先順位と期待効果（2026-08-19）](IMPROVEMENT_PRIORITY.md) — 20項目の当時の完了判定と残る拡張候補の履歴。現行の残作業は [実装ロードマップ](../plans/IMPLEMENTATION_ROADMAP.md) を参照。
- [Session Portability 旧設計案](SESSION_PORTABILITY_DESIGN.md) — 2026-09-24の実装前設計。平文 `.uags` は採用されておらず、現在の暗号化 `.uag` 仕様は [Session Portability v1](../SESSION_PORTABILITY.md) を参照。
- [Context Runtime 旧実装計画](UAG_CONTEXT_RUNTIME_TODO.md) — 旧TODOの主要機能の実装記録。現行設計§32の拡張要件との差分照合は [実装ロードマップ](../plans/IMPLEMENTATION_ROADMAP.md) で管理し、現在の要件は [Context Management Design](../UAG_CONTEXT_MANAGEMENT_DESIGN.md) を参照。
