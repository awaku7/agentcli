# tool / 本体の疎結合メモ

## 1. `tool -> util_tools` 依存を減らす
対象:
- `audio_speech_tool.py`
- `generate_image_tool.py`
- `finish_skill_tool.py`

安全な第一段階:
- 既存の `util_tools` 依存を、tool 側の小さな共有モジュールへ移す
- 既存の互換 import はすぐ壊さない
- 動作確認は対象 tool 単位で行う

## 2. tool 初期化まわりを 1 箇所に寄せる
対象:
- `cli.py`
- `web.py`
- `cli_startup.py`

狙い:
- tool 実装を host 側が細かく知りすぎないようにする
- callback 注入や起動順を共通化する

## 3. tool 内ログを callback 化する
対象:
- 大きめの tool から順に

狙い:
- stdout / stderr 依存を減らす
- host 側の表示・保存・通知を統一する

## 先にやる安全な切り出し
- `open_image_with_default_app` を tool 側へ移す
- `finish_skill` のメッセージ削除補助を tool 側へ移す
- host 側の re-export は残す

## 補足
- このメモは順番を固定するためのもの
- 変更は小さく分けて、各段階で `py_compile` と smoke test を通す
