# vLLM Qwen Reasoning Token Budget

- Status: planned
- Priority: P2
- Source:
  - [Qwen3.5 / Qwen3.6 vLLM recipe](https://docs.vllm.ai/projects/recipes/en/stable/Qwen/Qwen3.5.html)
  - [vLLM Reasoning Outputs](https://docs.vllm.ai/en/latest/features/reasoning_outputs/)
  - [vLLM PR #20859: hard limit for thinking tokens](https://github.com/vllm-project/vllm/pull/20859)
  - llmcapa 0.5.71 metadata for `Qwen/Qwen3.6-35B-A3B` via vLLM: reasoning is supported; `reasoning_effort` is not advertised.

## 目的

UAGからQwen3.6等のQwen3系vLLMモデルに、推論トークンの数値上限を指定できるようにする。これは`reasoning_effort=low|medium|high`ではなく、vLLMの`thinking_token_budget`によるハード上限である。

## 対象範囲

- vLLMプロバイダーのみ。
- `UAGENT_REASONING`の標準effort指定とは分離した、数値の推論トークン予算。
- Qwen3.6を最初の対象とし、vLLMが対応を確認したQwen3系にも適用可能にする。
- 現時点で公式vLLMドキュメントが示すChat Completions経路を先に検証する。Responses APIへの同パラメーター伝達は別途確認し、確認できるまでは対応済みと扱わない。

## 対象ファイル

- `src/uagent/llm_round_helpers.py` または `src/uagent/providers/openai_projection_policy.py`
- `src/uagent/env_validate.py`（設定値の検証が必要な場合）
- `tests/test_vllm_provider_wiring.py`、関連するリクエスト投影テスト
- `docs/VLLM.md`、`docs/VLLM.ja.md`、`docs/ENVIRONMENT.md`、`docs/ENVIRONMENT.ja.md`

## 実装内容

1. `UAGENT_VLLM_THINKING_TOKEN_BUDGET`（正の整数）を追加する。
1. 値が設定された場合に限り、vLLM Chat Completionsリクエストへ`thinking_token_budget`として渡す。未設定なら現状のリクエストを変えない。
1. 負数・0・整数でない値の扱いを定義し、ユーザーに分かるエラーまたは警告を出す。
1. パラメーターはQwenのreasoning強度レベルへ自動変換しない。`max_tokens`は生成全体の上限として別に扱う。
1. UAGが選んだトランスポートがResponses APIの場合の扱いを明示する。未検証なら値を黙って破棄せず、非対応として通知するか、ユーザーが明示的にChat Completionsを選べるようにする。
1. サーバー側ではQwen3系のreasoning parser（例: `--reasoning-parser qwen3`）が必要であることをドキュメントに記載する。

## 受け入れ条件

- 未設定時はvLLMリクエストに`thinking_token_budget`を送らない。
- 正の整数設定時、対応するChat Completionsリクエストだけにその値を渡す。
- 他のプロバイダーへ同パラメーターを送らない。
- 入力上限、thinking予算、`max_tokens`出力上限を混同しない。
- 対応していないvLLMバージョンまたはトランスポートでは、予算が黙って無視されない。
- テストで未設定・有効値・不正値・Responses API選択時の挙動を確認する。

## テスト計画

- ユニットテスト: 設定値の検証、Chat Completionsペイロード、他プロバイダーへの非波及。
- 統合テスト: vLLMのResponses/Chat Completionsルーティングとの相互作用。
- 対応vLLMバージョンを固定し、実サーバーで`thinking_token_budget`がreasoning blockを制限することを確認する。

## 依存関係・リスク

- 現行のvLLMドキュメントには、Qwen3等について`thinking_token_budget`が記載されているが、`llmcapa`のvLLM最小バージョン情報だけでは当該機能の実装バージョンを保証しない。実装前にリリース履歴と使用中のサーバーバージョンを確認する。
- 予算到達時にreasoning blockを強制終了するため、小さすぎる値では回答品質を損なう可能性がある。最終回答のための出力トークン余地も確保する。
- vLLM Responses APIで同パラメーターがサポートされるかは未確認。

## 更新履歴

- 2026-10-28: Qwen3.6/vLLMのeffort指定とthinking token budgetを区別し、将来実装課題として登録。
