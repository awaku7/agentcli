# tool / 本体の疎結合メモ

## 完了
- `open_image_with_default_app` を `tools/openers.py` に分離した
- `finish_skill` のメッセージ削除補助を `tools/skill_history.py` に分離した
- `search_web_tool.py` のログ出力を callback 経由にした
- `ToolCallbacks` に `finish_skill` と `rewrite_current_log_from_messages` を追加した
- CLI の callback 初期化を `cli_startup.py` 側に寄せた
- 互換 import / re-export は残している

## 1. `tool -> util_tools` 依存を減らす
対象:
- `audio_speech_tool.py`
- `generate_image_tool.py`
- `finish_skill_tool.py`

進捗:
- 完了: `open_image_with_default_app` の分離
- 完了: `finish_skill` 補助の分離
- 継続: 残りの `util_tools` 依存を必要最小限まで削る

## 2. tool 初期化まわりを 1 箇所に寄せる
対象:
- `cli.py`
- `web.py`
- `cli_startup.py`

進捗:
- 完了: CLI 起動経路の callback 初期化を `cli_startup.py` に寄せた
- 継続: `web.py` 側の整理が必要なら別途進める

## 3. tool 内ログを callback 化する
対象:
- `search_web_tool.py`
- 必要なら他の tool

進捗:
- 完了: `search_web_tool.py` を callback 寄りに変更した
- 継続: 他 tool は必要に応じて順次対応

## 補足
- このメモは順番を固定するためのもの
- 変更は小さく分けて、各段階で `py_compile` と smoke test を通す
