# 現在の応答を停止する（Stop / F12）

停止操作はフロントエンドごとに異なります。**旧案の「`c` キーで停止」は廃止済み**です。`c` は通常の入力であり、割り込み操作ではありません。

## フロントエンド別の操作

| フロントエンド | 操作 | 経路 |
|---|---|---|
| CLI（CUI） | 処理中に **F12** を押す。POSIX では TTY が必要。 | CLI の入力監視が共有割り込みフラグを立てる。F12 は Auto-Pilot の停止も要求する。 |
| GUI | 応答中に **Stop** ボタンを押す。 | ボタンが共有割り込みフラグを立てる。Auto-Pilot には別の停止操作がある。 |
| Web | 実行中のルームで **Stop** を押す。 | WebSocket handler がアクティブルームを検証し、worker に割り込みを送る（process-worker モードでは IPC）。ブラウザー上の F12 は停止操作ではない。 |

## 割り込み時の動作

- 実行中の応答へ停止を要求する。キャンセルに対応した provider のストリームは速やかに閉じる／抜けるが、非ストリーミング呼び出しや割り込み不能な処理は次の確認地点まで動く場合がある。
- 共通のラウンド処理がユーザー `Stop` メッセージを履歴に記録し、中断された応答の tool call は実行しない。必要に応じて provider の継続状態をクリアまたは更新する。
- 中断後に残った provider 呼び出しからの遅延出力は抑止し、次のターンへ漏れないようにする。
- これは停止要求であり、任意の同期 tool や第三者呼び出しを即時に強制終了できる保証ではない。

## Web のストリーミングと停止

Web は端末 stdout ではなく `core.log_message` のストリームイベント橋渡しを使います。registry 経路も各テキスト差分をこの経路へ送り、応答の完了／中断時に終端イベントを送信します。Web worker がアクティブルームへ中継し、process-worker モードでは再接続・復旧用に途中テキストも保持します。

## 関連テスト

- `tests/test_auto_pilot_f12_interrupt.py`: Windows / POSIX の F12 検出。通常キーでは割り込まないこと。
- `tests/test_interrupt_stream_output.py`: provider stream のキャンセルと遅延出力の抑止。
- `tests/test_registry_round_parity.py`: registry stream 表示と終端イベント、Web への橋渡し。
- `tests/test_web_process_workers.py`、`tests/test_web_loaded_session_runtime.py`: Web worker の割り込み経路とアクティブルームの所有権。

registry 経路の調査履歴は[割り込みレビュー計画](plans/UAG_INTERRUPT_REVIEW_20261125.md)を参照してください。
