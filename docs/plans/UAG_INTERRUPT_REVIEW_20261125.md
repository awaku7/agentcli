# 割り込み（Stop / F12）の計測と修正計画（2026-11-25）

- Status: in progress（INT-01〜05 完了。CLI / Web / GUI の停止表示と状態同期は別途確認予定）
- Priority: P1
- Source: [`IMPLEMENTATION_ROADMAP.md`](IMPLEMENTATION_ROADMAP.md) の「P1: Auto-Pilot / Interrupt の残課題」、[`docs/INTERRUPT.md`](../INTERRUPT.md)
- 確認基準: `main` = `3dfca2816`（PR #470 マージ後）

## 目的

割り込み（CLI の F12、Web の Stop）が、どの経路で、どれだけ遅れて効くかを実測し、効かない経路を直す。

## 計測の方法

- ローカルに偽の OpenAI 互換サーバーを立てる。50 ms ごとに 1 トークン、200 トークン（約 10 秒）を返す。Chat Completions（ストリーミングあり・なし）と Responses（ストリーミング）に対応する。
- 実際の `run_llm_rounds` を動かし、別スレッドから `core.interrupt_requested` を立てる。プラグインの読み込みなどの初回コストは事前に済ませておく。
- 計測する項目: 割り込みからターンが戻るまでの時間、戻った後に画面に出たトークン数、サーバーが送ったチャンク数と接続が切られたか、履歴に assistant の応答が追加されたか。

## 結果

| 経路 | 戻るまで | 戻った後の出力 | 問題 |
|---|---|---|---|
| OpenAI Chat（ストリーミングなし） | 0.04 秒 | なし | 裏でリクエストが最後まで続く（無駄だが実害は小さい） |
| OpenAI Responses（ストリーミング） | 0.1 秒 | 188 トークン | 戻った後も約 9.5 秒、出力が画面に流れ続ける |
| ターンの準備中に割り込み | 10.5 秒 | — | 割り込みが消え、LLM の呼び出しから応答の追加まで最後まで実行される |

補足: ツールを無効（`UAGENT_USE_TOOL=0`）にした状態や、OpenAI の Chat 経路では、レガシー経路のストリーミングなしの呼び出しになる。

## 原因

1. **準備中の割り込みが消える。** `run_llm_rounds` の「前のセッションから残った割り込みフラグを消す」処理が、ターンの準備（メモリ、コンテキスト、ツール選択）と Computer Use の準備の**後**にあった。
1. **割り込み後も出力が続く。** LLM の呼び出しは別スレッドで動き、待つ側が 50 ms ごとにフラグを見て先に戻る（`LLMWaitInterrupted`）。戻った後の処理がフラグを消すので、イベントが届いたときにしかフラグを見ない受信ループは割り込みに気づかず、最後まで出力する。このための仕組み（`llm_call_abandoned()`）はあるが、Responses の受信ループ（`responses_common`）では使っていない（Vercel、LM Studio SDK、Inception では使っている）。

## 修正計画

| ID | 内容 | 重要度 | 状態 |
|---|---|---|---|
| INT-01 | 残ったフラグを消す処理をターンの最初に移す。準備中の割り込みは最初のラウンドの確認で止まる | 高 | 完了（PR #471） |
| INT-02 | 見捨てられた呼び出しからの出力を画面と Web に出さない（`print_stream_delta` など共通の出力処理で止める） | 高 | 完了（PR #472） |
| INT-03 | Responses などの受信ループで `llm_call_abandoned()` も確認し、ループを抜けて接続を閉じる | 中 | 完了（PR #473） |
| INT-04 | Claude / Gemini / DeepSeek などの受信ループも同様に確認する。プロトコルごとに偽サーバーで計測する | 中 | 完了（PR #474） |
| INT-05 | registry 経路（`openai_compatible_runtime`）が、ツールを使う普段のターンで毎回失敗している不具合を直し、割り込みに対応させる | 高 | 進行中（05a〜05d） |

CLI / Web / GUI での停止表示と状態の同期（ロードマップの項目）は、INT-01〜04 の後に、それぞれの入口で確認する。

## INT-01 の結果

- `run_llm_rounds` の最初（judgment モードの切り替えの直後、ターンの準備の前）で、残ったフラグを消すようにした。元の位置の処理は削除した。
- 準備中に割り込まれたときは、Computer Use の URL 直接ナビゲーションも行わない（ブラウザーを開かない）。
- 計測: 準備中（開始から 0.07 秒 / 0.25 秒）の割り込みで、0.04〜0.2 秒で戻る。LLM へのリクエストは送られない（サーバーへのリクエスト 0 件）。履歴には停止のプロンプトが追加され、assistant の応答は追加されない。
- テスト: `tests/test_interrupt_during_turn_prep.py`（準備中の割り込みで LLM を呼ばないこと、ターンの前から残っていた割り込みは従来どおり消えること、準備中の割り込みでは URL 直接ナビゲーションをしないこと）。修正前のコードでは、新しい動作を確かめる 2 つのテストが失敗することを確認した。

## INT-02 の結果

- 判定の関数 `is_abandoned_stream_output()` を `llm_helpers` に追加した。見捨てられた呼び出し（`llm_call_abandoned()`）のスレッドから出た、ストリーム系のメッセージ（`assistant_stream_*`、`assistant_reasoning_delta`、`reasoning`）なら真を返す。
- 次の 3 か所で、見捨てられた呼び出しからの出力を捨てる。
  - `core_impl/display.py` の `print_stream_delta` / `print_reasoning_delta`（端末。大半のプロバイダが使う）
  - `core_impl/logs.py` の `log_message`（ログファイルへの書き込み）
  - `web_impl/agent_worker.py` の `_patched_log_message`（Web のルームへの転送。次のターンを表示中のこともある）
- プロバイダが直接 `print` するのは、`core` に `print_stream_delta` がない場合の代替だけ（テストなど）なので、対象にしなかった。
- 計測（200 トークン、Responses のストリーミング）: 戻るまで 0.05 秒。戻った後の出力は 188 トークン → **0**。受信ループ自体はまだ最後まで回り、サーバーは 200 トークンすべてを送る（INT-03 で対応）。
- テスト:
  - `tests/test_interrupt_stream_output.py`: 偽サーバー（`tests/fake_openai_stream_server.py`）に対して、別プロセスで実際のラウンドを動かし、ストリームの途中で割り込む。戻った後の出力が 0 であることを確かめる。ガードを外すと 49 トークンが出て失敗することを確認した。
  - 同じファイルに、表示の関数と判定の関数の単体テストもある。

## INT-03 の結果

- `parse_responses_stream`（`providers/responses_common.py`）の受信ループで、イベントごとに `llm_call_abandoned()` も確認し、真ならループを抜ける。割り込みのフラグが先に消されていても止まる。
- 割り込みでループを抜けたときは、`finally` でストリームを閉じる（これまでは抜けるだけで、HTTP の応答は閉じていなかった）。フラグを見て抜けた場合も同じ。
- vLLM の使用量を拾う包み（`capture_vllm_responses_usage`）は、閉じられたときに中のストリームも閉じるようにした。
- 計測（200 トークン、Responses のストリーミング、10 トークン目で割り込み）: サーバーが送ったのは 200 → **12** トークン。割り込みから 0.15 秒で接続が切れた。戻るまで 0.03 秒、戻った後の出力は 0。
- テスト: `tests/test_interrupt_stream_output.py` の端から端までのテストに「接続が切られ、サーバーが途中で止まる」確認を加えた（修正前は失敗することを確認）。vLLM の包みの単体テストも追加した。
- registry 経路（`openai_compatible_runtime`）は、`UAGENT_PROVIDER_REGISTRY=all` を指定してもこの構成では使われなかった。この経路はラウンドのスレッドで直接ストリームを読み、既定の `NoCancellation` は止まらないので、INT-04 で扱う。

## INT-04 の結果

### 対象の洗い出し

| プロバイダ | 受信ループ | 修正前の状態 | 対応 |
|---|---|---|---|
| DeepSeek（Z.AI なども同じ関数） | `parse_deepseek_stream` | 割り込みの確認なし、閉じない | 共通ラッパーを適用 |
| Gemini / Vertex AI | `gemini_chat_with_tools` | 同上 | 同上 |
| Novita | `_parse_novita_stream` | 同上 | 同上 |
| Together | `_parse_together_stream` | 同上 | 同上 |
| PFN | `iter_pfn_stream_content` | 同上 | 同上 |
| Grok | `iter_xai_stream_parts` | 同上 | 同上 |
| Claude | — | ストリーミングしない | 待つ側がすぐ戻るので対応不要 |
| Vercel、LM Studio SDK、Inception（legacy） | — | 見捨てられたかを確認済み | 変更なし |
| Foundry Local、Inception（registry） | キャンセル用トークン | registry 経路の作り | INT-05 で扱う |

### 変更

- `llm_helpers` に 2 つを追加した。
  - `stream_stop_requested()`: 待つ側がいる呼び出しのスレッドでは「見捨てられたか」、ラウンドのスレッドで直接読む場合は割り込みフラグを返す。フラグは消さず、ラウンドに処理を任せる。
  - `iter_until_stopped(stream)`: 項目を渡す前に `stream_stop_requested()` を確認し、真ならストリームを閉じて止める。
- 上の 6 つの受信ループを `iter_until_stopped(...)` で包んだ。
- 計測（DeepSeek、Chat Completions のストリーミング、200 トークン中 10 トークン目で割り込み）: サーバーが送ったのは 200 → **12** トークン。接続は切られた。
- Gemini は uag 側に接続先を変える設定がなく、偽サーバーで計測できなかった。ループの変更は他と同じなので、共通ラッパーの単体テストで確かめた。Grok（gRPC）も同様。
- テスト: `tests/test_interrupt_stream_output.py` の端から端までのテストを、OpenAI Responses と DeepSeek Chat の 2 つで回すようにした。DeepSeek は修正前のコードでは「接続が切られない」で失敗することを確認した。共通ラッパーの単体テスト（止めないとき、見捨てられたとき、ラウンドのスレッドでフラグが立ったとき）も追加した。

## INT-05: registry 経路の不具合（調査済み、未修正）

- **現象:** registry 経路（`llm_registry_round._try_registry_simple_chat_round`）は、ツールを使う普段のターンで毎回例外になり、`except Exception: return None` で黙って legacy 経路に戻っている。対応プロバイダ（openai、azure、openrouter、vllm、ollama、nvidia、grok、pfn、lmstudio、sakana など）で、既定で有効なはずの経路が実際にはほぼ使われていない。
- **原因:** ツール選択が返す判断（`ContextDecision` オブジェクト）を、`runtime/context_plan_builder.py` の `build_context_plan` が `dict(item)` で dict として扱い、`TypeError: 'ContextDecision' object is not iterable` になる。判断は 2026-09-07 から `ContextDecision` で、`dict(item)` は 2026-09-15（`6ad2c7697`）に入った。
- **直すときの注意:** 直すと多くのプロバイダで、実際に通る経路が registry に切り替わる。この経路はラウンドのスレッドでストリームを直接読み、既定のキャンセル用トークン（`NoCancellation`）は止まらないので、割り込みがまったく効かない。
- **進め方:**
  1. 判断の変換を直し、割り込み（キャンセル）にも対応させる。
  1. 偽サーバーで、legacy 経路と registry 経路の出力・ツール呼び出し・割り込みの動作を比べる。
  1. 差がなければ有効にする。`UAGENT_PROVIDER_REGISTRY=off` で元の経路に戻せることも確認する。

## INT-05 の追加調査と計画

判断の変換を直して registry 経路を実際に通したところ、legacy 経路との差が 3 つ見つかった（偽サーバー、OpenAI、Chat と Responses）。

| 項目 | legacy 経路 | registry 経路 |
|---|---|---|
| 画面への表示 | Responses は 0.35 秒後から逐次表示 | 10 秒後にまとめて 1 回 |
| 会話の履歴 | 応答が追加される | **最終回答が追加されない**（次のターンで LLM が前の回答を見られない） |
| 割り込み | 0.03 秒で戻り、接続を切る | 効かない（戻るまで 9.6 秒、サーバーは最後まで送る） |

方針（2026-11-25 に決定）: 3 つとも直してから有効にする。registry 経路は変換の不具合で今は使われていないので、先に 3 つを直して `main` に入れても利用者の動作は変わらない。最後に変換を直した時点で有効になる。

| ID | 内容 | 状態 |
|---|---|---|
| INT-05a | 最終回答を会話の履歴に追加する | 完了 |
| INT-05b | 逐次表示する | 完了 |
| INT-05c | 割り込みで止まる（キャンセル用トークンを割り込みのフラグにつなぐ） | 完了 |
| INT-05d | 判断の変換を直して有効にする。偽サーバーで legacy 経路と、出力・履歴・ツール呼び出し・割り込みを比べる | 完了 |

### INT-05a の結果

- registry 経路の最終回答（ツール継続のない応答）を処理するところで、legacy 経路と同じく、表示の前に `_append_assistant_message` で履歴に追加するようにした（`_should_keep_assistant_message` の判定も同じ）。
- judgment モードでは、legacy 経路と同じく最終回答を表示しない。
- 確認: 変換の修正を一時的に当てて偽サーバーで動かすと、履歴が `['user']` → `['user', 'assistant']` になった（Chat、Responses とも）。
- テスト: `tests/test_registry_round_parity.py`（新規）。履歴への追加と、judgment モードで表示しないこと。修正前は 2 つとも失敗することを確認した。

### INT-05b の結果

- Registry の `RoundOrchestrator` が渡すイベント observer で `TextDelta` を受け取り、従来の `core.print_stream_delta` を使って到着ごとに表示する。
- `TextSnapshot` は累積スナップショットとして扱い、前回表示済みの文字列に続く差分だけを表示する。プロバイダが過去の内容を修正した場合は端末上で巻き戻せないため、新しいスナップショット全体を出す。非ストリーミング時は observer から出力しない。
- Registry ストリームで表示済みの最終回答は、ラウンド終了後にもう一度 `print()` しない。履歴保存、結果ファイルへの追記、画像処理は従来どおり行う。
- `tests/test_registry_round_parity.py` にイベント差分表示、スナップショット差分、最終回答の二重表示防止を追加。5 件成功、ruff 検査成功。

### INT-05c の結果

- Registry 用のキャンセル用トークンを追加し、既存の `core.cancellation_token` があれば維持しつつ、`stream_stop_requested(core)` も確認する。F12 / Web Stop が立てる `interrupt_requested` がストリームのキャンセルに届く。
- Registry が `cancelled` / `interrupted` を返した場合、互換経路へフォールバックして二度目のリクエストを送らず、標準のラウンド割り込み処理に渡す。
- OpenAI-compatible runtime のストリーム停止・close、キャンセル結果での fallback 抑止、割り込みフラグとの接続をテスト。関連3ファイルのテスト21件成功、ruff検査成功。
- `tests/test_interrupt_stream_output.py` の最初の失敗原因は、テストプロセスが親環境の `UAGENT_REASONING=auto` を引き継いでいたこと。Responses + reasoning auto は再試行のため streaming を意図的に無効化するため、偽サーバーへの要求も `stream=false` となり、ストリーム切断を測れていなかった。テストで `UAGENT_REASONING=off` を固定し、全10件成功、openai-responses の途中切断も確認。

### INT-05d の結果

- `ContextDecision` を `to_dict()` で ContextPlan の判断記録に正規化し、デフォルトで使われる registry 経路の `TypeError` を解消。判断オブジェクト入りの plan 作成と registry 呼び出し準備をテスト。
- 偽 Responses サーバーで `UAGENT_PROVIDER_REGISTRY=off` の legacy 経路と `=all` の registry 経路を比較。表示テキスト、履歴、正規化したツール呼び出し、スタブ実行結果が一致することを確認。
- 同じ偽サーバーで両経路の割り込みも検証し、部分出力後に早期終了して接続が閉じることを確認。表示差分から見つかった registry の行末改行漏れも修正。
- `UAGENT_REASONING=auto` は Responses の再試行のためストリーミングを無効化するため、該当テストでは `off` を明示。関連6ファイルのテスト48件成功、ruff 検査成功。

## 別件として見つかったこと

Responses を使う設定で、llmcapa が知らないモデル名（独自のモデルや新しいモデル）を使うと、プラグインの読み込み時に llmcapa のモデル検索がツールのモジュールごとに走り、15 秒以上かかる。見つからなかった結果がキャッシュされない（`_should_preload_lazy_specs()` が `_register_tool_module` のたびに呼ばれる）ため。割り込みとは別の性能の問題として扱う。

## 更新履歴

- 2026-11-25: 作成。計測と原因の分析、INT-01 を実施。
- 2026-11-25: INT-02（見捨てられた呼び出しの出力を止める）を実施。
- 2026-11-25: INT-03（Responses の受信ループを抜けて接続を閉じる）を実施。
- 2026-11-25: INT-04（各プロバイダの受信ループ）を実施。registry 経路の不具合を INT-05 として記録。
- 2026-11-25: INT-05 の追加調査（legacy 経路との差 3 つ）と計画（05a〜05d）。INT-05a（最終回答を履歴に追加）を実施。
- 2026-11-25: INT-05b（registry 経路の逐次表示）を実施。イベント単位の表示と最終回答の二重表示防止を追加。
- 2026-11-25: INT-05c（registry 経路の割り込みキャンセル）を実施。openai-responses の割り込みテストが reasoning auto により非ストリーミングになっていたため、テスト環境を固定して再確認し、途中切断を確認。
- 2026-11-25: INT-05d（ContextDecision 変換と registry/legacy の parity 検証）を実施。テキスト、履歴、ツール呼び出し、割り込み、registry off の経路を偽サーバーで確認。
