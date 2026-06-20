# 変更履歴

このプロジェクトの重要な変更箇所はすべてこのファイルに記録されます。

このフォーマットは [Keep a Changelog](https://keepachangelog.com/ja/1.0.0/) に基づいており、
このプロジェクトは [セマンティック バージョニング](https://semver.org/spec/v2.0.0.html) に準拠しています。

## [0.5.17] - 2026-06-20

### 修正
- `catalog_tool.json` の出力にリテラル `{persist}` プレースホルダーが表示される問題を修正（30言語）。
  - `msg.load.ok` 文字列に `(persist={persist})` のサフィックスが含まれていたが、
    呼び出し側で `persist` パラメータを渡していなかったため展開されていなかった。
  - `tools_control_tool.py` から未使用の `persist` パラメータ参照を削除。
- `human_ask` の `ui.howto` 表示テキストから `"""retry` / `"""end` の記載を削除
  （10言語の翻訳: bn, fa, ko, mr, nb, sw, th, vi, zh_CN, zh_TW）。

### その他
- `.vs/` および `.uagent_web_uploads/` を `.gitignore` に追加。

## [0.5.16] - 2026-06-20

### 修正
- 全77ツールJSONファイルの5408件の翻訳 truncation を修正（29言語）。
  - 自動翻訳時の文字数制限で切れていた翻訳を Google Translate で再翻訳。
  - 対象言語: ar, bn, cs, de, es, fa, fi, fr, hi, id, it, ja, ko, mn, mr, nb, nl,
    pl, pt, pt_BR, ru, sv, sw, th, tr, uk, vi, zh_CN, zh_TW。
