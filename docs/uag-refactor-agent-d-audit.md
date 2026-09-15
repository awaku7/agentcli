# Agent D 監査報告: I18N / telemetry

## 監査範囲

- 開始 commit: `2435ad6a69244cf8dabe18286389bb0389c3cfde`
- 対象: `src/uagent`、`src/uagent/locales`、`src/uagent/tools/*_tool.json`、`scripts/*i18n*`、既存 telemetry 実装
- 方針: read-only。production code、locale、tool JSON は変更していない。

## 実行結果

| 検証 | 結果 |
|---|---|
| gettext catalog | `.po` 38件、`.mo` 38件。対応関係は欠落なし |
| `i18n_audit.py` | 38 locale を認識。Python の日本語文字列 134件、tool catalog issue 2ファイル |
| `i18n_tools_check.py --json` | 256 JSONを走査。error 72件、warning 0件 |
| `pytest tests/test_structured_observability.py -q` | 6 passed |
| `pytest tests/test_context_budget_integration.py -q` | 7 passed |
| `pytest tests/test_context_tokens.py -q` | 2 passed |

`i18n_audit.py` は Windows の既定 CP932 出力では `UnicodeEncodeError` になった。`PYTHONIOENCODING=utf-8` を指定すると監査結果を出力できる。CI と開発者向けコマンドでは UTF-8 stdout を明示するか、スクリプト側で stdout を UTF-8 に再設定する必要がある。

## I18N findings

### Tool JSON の実エラー

次の2ファイルで、英語カタログに存在する以下4キーが複数言語で欠落している。

- `src/uagent/tools/generate_image_tool.json`
- `src/uagent/tools/img2img_tool.json`

欠落キー:

- `param.output_compression.description`
- `param.output_format.description`
- `param.partial_images.description`
- `param.stream.description`

`i18n_audit.py` の集計では、各ファイルに 144 件の locale/key 欠落が報告された。これは現行 baseline に存在する問題として記録し、リファクタの新規差分と分離して扱う。

### Python の日本語文字列

134件が検出されたが、全てが未翻訳のユーザー表示とは限らない。主な内訳は docstring、説明用コメント、profile のキーワード集合、provider 固有メッセージ、tool の既定文言である。次のように分類してから修正する。

1. host UI に到達する表示文言: gettext 化
2. tool のユーザー表示・エラー: `*_tool.json` 化
3. docstring / コメント / 内部判定語: 対象外として allowlist 化
4. provider request の固定値: 翻訳対象外として確認

単純に 134件を全て翻訳対象にしない。

### 所有者と検証経路

| 対象 | 所有者 | 検証 |
|---|---|---|
| runtime / provider / CLI / GUI / Web の表示 | host gettext | `compile_locales.py`、`po_qc_summary.py` |
| tool の description / error | `*_tool.json` | `i18n_tools_check.py`、`i18n_validate.py` |
| event / reason code | 翻訳しない | stable code の contract test |
| renderer の最終文言 | host 側 | locale key / placeholder test |

## Telemetry findings

### 現行で確認できるもの

- `_observed_llm_rounds` は `llm.started` / `llm.completed` / `llm.failed` を記録する。
- 現行 LLM event は provider、model、status、duration、error type を中心とする。
- `_record_context_telemetry` は `raw_chars`、`active_chars`、`saved_chars`、`saved_ratio`、role 別 section、budget usage を保持する。
- context decision log は session store が利用可能な場合に保存される。
- tool-loop debug は arguments / result の本文ではなく、sha256 の短縮値と長さを出す実装になっている。

### リファクタで追加すべき fields

`turn_id`、`round_id`、`attempt_id`、`request_id`、`stream_id`、`session_generation`、`plan_observation_id`、`projection_id` は、既存の event schema と衝突しないよう versioned allowlist に追加する。

次の値は telemetry に出さない。

- prompt 本文
- tool arguments / tool result 本文
- 生の `plan_id` / `projection_id`（外部観測時）
- workspace/session key
- provider access token、Authorization header、cookie

`log_event()` の現在の secret redaction は限定されたキー名に対するものなので、将来の telemetry は自由な `**fields` のログではなく、event code ごとの allowlist で生成する。保持期間、外部送信可否、sampling 方針も event schema と同時に定義する。

## CI / checklist 提案

1. `python scripts/i18n_tools_check.py --json` を全 tool JSON に対して実行し、error を CI failure とする。
2. `python scripts/i18n_validate.py <catalog>` を変更した tool catalog ごとに実行する。
3. `python scripts/compile_locales.py` と `python scripts/po_qc_summary.py` を host locale 変更時に実行する。
4. Windows runner では `PYTHONIOENCODING=utf-8` を設定し、`i18n_audit.py` の出力失敗を防ぐ。
5. 38 locale の key、placeholder、JSON 構造、`.po` / `.mo` 対応を構造テストする。
6. telemetry test では、禁止フィールドが出力されないこと、ID が opaque 化されること、schema version が付くことを検証する。
7. baseline に既存する `generate_image` / `img2img` の欠落キーを、refactor 差分の failure と混同しないよう issue 化する。

## 主担当への判断依頼

- `generate_image_tool.json` と `img2img_tool.json` の欠落キーを今回のリファクタで修復するか、既存 issue として別作業に分離するか。
- 134件の日本語文字列監査結果を allowlist 管理する仕組みを導入するか。
- telemetry の新 ID fields を event schema version 2 として追加するか、既存 schema version 1 に optional fields として追加するか。
- retention / sampling / 外部送信可否を event category 単位で決定するか。

## 未解決事項

- `StreamEvent` の terminal event 一意性は設計上定義されているが、現行 `round_contracts.py` では `type: str` のため、実行時検証は未実装である。Agent A/C または主担当で contract validator を追加する必要がある。
- canonical JSON と `RoundIdentityFactory` の結合はまだ caller 側に残っているため、RFC 8785 / Unicode NFC を実装する担当と integration test の所有者を明示する必要がある。

## 報告

担当: Agent D
開始 commit: `2435ad6a69244cf8dabe18286389bb0389c3cfde`
変更ファイル: `docs/uag-refactor-agent-d-audit.md` のみ
契約への影響: なし。監査結果と検証 checklist の提案のみ
互換性 / feature flag: 変更なし
実行した検証: 上記の i18n audit、tool catalog check、対象 pytest
未解決事項・主担当への判断依頼: 本文末尾に記載
