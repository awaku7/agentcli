# i18n cleanup continuation note

## 状況
- コメントと docstring は対象外。
- 対象は、実際にユーザーに見える未翻訳の固定文のみ。
- 直近の検索では、残件は主に次の 5 ファイル。
  - `src/uagent/env_validate.py`
  - `src/uagent/llm_flow_helpers.py`
  - `src/uagent/scheckgui.py`
  - `src/uagent/util_tools.py`
  - `src/uagent/a2a/engine.py`

## すでに実施したこと
- `src/uagent/locales/uagent.pot` を再生成。
- `src/uagent/locales/en/LC_MESSAGES/uag.po` を再生成。
- 非英語 locale の `msgstr` を更新。
- `outputs/i18n/po_qc_summary.tsv` を作成。
- `scripts/po_qc_summary.py` を調整し、`same_as_en` 判定を見直し。

## 次回やること
1. 残っているユーザー向け文字列を `_()` に寄せる。
2. `search_files` で再確認する。
3. 必要なら POT/PO を再生成する。
4. `compile_locales.py` で検証する。

## いまの方針
- コメントや docstring は触らない。
- 画面表示、ログ表示、エラーメッセージ、CLI ヘルプのみ処理する。
- 迷ったら文字列がユーザー向けかどうかを基準にする。
