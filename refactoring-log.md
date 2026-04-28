# Refactoring log

## 2026-04-28 19:46 JST
- `refactoring.md` に作業ログ方針を追記した。
- `refactoring-log.md` を作成した。
- I18N 方針を追記した。
- 旧パス互換は維持し、shim で段階移行する方針を確認した。

## 記録方針
- 変更の要点、判断理由、確認結果を簡潔に残す。
- 失敗ややり直しも残す。
- 秘密情報は書かない。

## 2026-04-28 19:49 JST
- `uagent_llm.py` から初期ヘルパー群を `llm_helpers.py` に分離した。
- `llm_helpers.py` を追加した。
- `uagent_llm.py` の先頭 import とヘルパー定義の整理を進めた。
- `py_compile` で `uagent_llm.py` と `llm_helpers.py` の構文確認が通った。

## 2026-04-28 19:56 JST
- `uagent_llm.py` の分離後に残っていた構文崩れを修正した。
- `py_compile` で `uagent_llm.py` が通ることを確認した。

## 2026-04-28 19:56 JST
- `_init_gemini_cache` / `_maybe_auto_shrink_messages` / `_build_call_messages` を `llm_message_helpers.py` に分離した。
- `uagent_llm.py` から旧定義を削除し、参照だけ残す形にした。
- `py_compile` で `llm_message_helpers.py` / `llm_round_helpers.py` / `llm_helpers.py` / `uagent_llm.py` の構文確認が通った。

- 2026-04-28: Added unconditional Gemini image-generation debug logs in generate_image_tool.py (pre-call, post-call, per-item, traceback). Verified with py_compile.
- 2026-04-28: Switched Gemini image generation from generate_images to generate_content with response_modalities=[TEXT, IMAGE] and image_config. Verified after edit.
- 2026-04-28: Removed unsupported output_mime_type from Gemini image_config after runtime error. Will re-verify with py_compile/runtime.
