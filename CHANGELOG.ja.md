# 変更履歴

このプロジェクトの重要な変更箇所はすべてこのファイルに記録されます。

このフォーマットは [Keep a Changelog](https://keepachangelog.com/ja/1.0.0/) に基づいており、
このプロジェクトは [セマンティック バージョニング](https://semver.org/spec/v2.0.0.html) に準拠しています。

## [0.5.19] - 2026-06-22

### 追加
- ソースコードナビゲーションツール用の 'index' ジャンルを追加（py/ts/cs/jv/dart/cpp/rs の11のidxツール）。
- Z.AI プロバイダーをプロバイダー一覧に追加。
- UAGENT_PARALLEL_WORKERS 環境変数でスレッドプールサイズを設定可能に（デフォルト8）。
- idx ファミリーのドキュメントを全33のREADME翻訳、ツールテーブル、DEVELOPドキュメントに追加。

### 変更
- ツール数（111→112）、並列セーフ数（55→66）を更新。
- 並列実行に関するドキュメントを明確化（最大4同時実行、66並列セーフ）。
- UAGENT_PARALLEL_WORKERS および不足していたプロバイダーを ENVIRONMENT.md と ENVIRONMENT.ja.md に追加。

## [0.5.18] - 2026-06-21

### 追加
- MiniMaxプロバイダーを追加（OpenAI互換、エンドポイント https://api.minimax.io）。
- トルコ語（tr）README翻訳を追加。
- ギリシャ語（el）、ヘブライ語（he）、ハンガリー語（hu）、ルーマニア語（ro）のREADME翻訳を追加。
- el/he/hu/ro ロケールをツールJSONに追加。
- 全翻訳言語を示す世界地図SVGを README.translations.md に追加。
- 動的プロバイダー切替のための `:provider` コマンド仕様を追加。
- .poコンパイルとツールJSON翻訳に関するi18n修正計画のドキュメントを追加。

### 変更
- ツールのオン/オフジャンル制御: シェルメタ文字確認をデフォルトで無効化、ファイルジャンルを汎用実行ツールから分離。
- README.translations.md をカテゴリ別テーブルに再構成。
- README.translations.md の言語名をクリック可能なリンクに変更。
- 世界地図をミラー図法で再描画、大陸をより詳細に表示。
- md2idx の翻訳を30言語に拡大。

### 修正
- SVGマップファイルをリポジトリから削除（GitHubがSVGを自動リンクし、インライン表示が壊れるため）。
- SVGをbase64データURIとして埋め込み、GitHubの自動リンクを防止。
- SVGリンクの代わりにインライン画像として世界地図を表示。
- 国境ベースのハードコードされたSVG座標を使用し、首都の位置を正確に配置。
- 地理的中心ではなく首都に言語ドットを配置。
- SVG要素の順序を変更し、背景がパスの後ろに描画されるように修正。
- 地図のアスペクト比を 1200x720（正距円筒図法）に修正。
- SVG凡例テキストのアンパサンドをエスケープ。
- 9つの翻訳READMEファイルの破損したHTML/コードブロックを復元。
- md2idxツールの見出し番号オフセットを修正。

### その他
- 古い設計ドキュメント、TBD、ブレインストーミングノートを削除。

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
