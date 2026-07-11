# Python 高速化可能性分析レポート

> 分析対象: agentcli (commit 6987ae0f)
> 分析日: 2025年

---

## 優先度 大 (高頻度パスで改善効果大)

### 1. `tools/__init__.py` - `get_tool_specs()` ✅ 実装済み

**変更内容**:
- キャッシュ変数 `_TOOL_SPECS_CACHE` + ダーティフラグ `_TOOL_SPECS_DIRTY` を追加
- `TOOL_SPECS` が変更される4箇所 (`_load_plugins`, `_register_tool_module`, `_register_extra_spec`, lazy spec append) でフラグを立てる
- `get_tool_specs()` は2回目以降、キャッシュを返す（ツール変更がない限り再構築しない）
- 同じコミットで `run_tool()` の `next()` 線形走査を `_TOOL_TRACE_FLAGS` 辞書ルックアップに置き換え

---

### 2. `tools/__init__.py` - `get_tool_catalog()` (L832)

**問題点**:
- 内部に `_score_spec()` というクロージャを毎回定義している (関数オブジェクトのアロケーション)。
- スコアリング部分で二重ループ `for tok in tokens:` → 各 spec に対して線形探索。
- 未ロードの lazy tool を検索するセクションで `os.scandir()` を毎回実行 → ディスクI/O。
- さらに未ロードの lazy module ごとに `.spec.json` のファイル読み取りも行う。
- `search_web` と `fetch_url` の強制包含ロジックが重複 (2回 `_find_tool_modules()` を呼ぶ)。
- `debug_tools` が有効な場合、毎回 print が走る（無効時も条件判定が無駄）。

**改善案**:
- `_score_spec` をモジュールレベルの関数にする。
- 未ロードツールの検索結果をキャッシュする (TTL付き)。
- `search_web`/`fetch_url` の強制包含をループ内で1回の判定に統合。
- `debug_tools` 判定は外側の if にまとめる。

---

### 3. `providers/llm_openai_responses.py` - `build_responses_request()` (L554)

**問題点**:
- 全メッセージを2回走査している（1回目: 先読みスキャン L569-592、2回目: ビルド L612以降）。
- 各メッセージで `dict(m)` によるディープコピーが発生。
- `previous_response_id` モード時でも毎回 `for _idx, _msg in enumerate(call_messages)` で全会話を先読み。
- 巨大な `TOOL_CALLING_RULES` と `[Web search rules]` を毎ラウンド文字列連結 (instructions_list.append → 最後に join)。

**改善案**:
- 先読みスキャンとビルドを1パスに統合。
- `dict(m)` の代わりに、必要なキーのみコピーする。
- 再現性のある `instructions` 文字列は1回ビルドしてキャッシュする（変更がない限り）。

---

### 4. `providers/llm_openai_responses.py` - `parse_responses_stream()` (L1001)

**問題点**:
- 内部に `_dump_event`, `_print_delta`, `_ensure_buf`, `_merge_buf` の4つのクロージャを毎ストリームごとに定義。
- イベントごとに `getattr(ev, "type", None)`, `getattr(ev, "event", None)` などを何度も呼ぶ。
- ストリームイベントが大量にある場合 (tool_call + reasoning + text)、毎回の属性アクセスが累積的にコストになる。
- `tool_calls_buf` のキー解決に文字列連結 `f"call_{int(time.time() * 1000)}_{len(tool_calls_buf)}"` を使用。

**改善案**:
- クロージャの代わりにモジュールレベルの関数、またはメソッドに抽出。
- よくアクセスする属性はローカル変数にバインド (`ev_type = ev.type` など `getattr` のオーバーヘッド削減)。
- キー生成に `object()` センチネルを使うなど、不要な文字列生成を回避。

---

### 5. `core.py` - `_mask_message()` (L598)

**問題点**:
- ログ出力のたびに全メッセージを再帰的に走査。
- `isinstance(obj, dict)` の判定のたびに新しい dict を生成 → すべてのメッセージをミュータブルコピー。
- `human_ask` の content 判定で `startswith("{") and endswith("}")` の文字列チェック + `json.loads` を毎回試行。
- リスト再帰でも `[_mask_message(x) for x in obj]` で新しいリストを生成。

**改善案**:
- インプレース編集が可能なら `obj.copy()` ではなく `for k in obj: obj[k] = ...` で上書き（ただし副作用に注意）。
- `human_ask` の JSON パースは失敗が想定されるので `try/except` は妥当だが、軽量な先頭チェック（`'"tool": "human_ask"' in v` など）で早期 fallback する。
- マスキングが不要なメッセージ (system ロールやツール結果が短いもの) はスキップ。

---

## 優先度 中 (特定シナリオで改善効果あり)

### 6. `tools/search_files_tool.py` - `_looks_binary()` (L151)

**問題点**:
- ファイル先頭バイト列を Python の for ループで1バイトずつ検査。
- 条件分岐が各バイトに対して発生 (b in (9,10,13), 0 <= b < 32)。

**改善案**:
- `bytes.translate()` を使って制御文字を一括カウント:
  ```python
  control_table = bytes([1 if 0 <= b < 32 and b not in (9,10,13) else 0 for b in range(256)])
  bad = sum(head.translate(control_table))
  ```
- `b"\x00" in head` は既に高速。

---

### 7. `tools/replace_in_file_tool.py` - `_find_best_fuzzy_match()` (L498)

**問題点**:
- `difflib.SequenceMatcher(None, text_lower, pattern_lower)` は O(n*m) の最悪計算量。
- 大きなファイル (例: 数万行の会話ログ) に対して、パターンマッチのたびに全体の SequenceMatcher を実行する。

**改善案**:
- SequenceMatcher の前に、より軽量なアプローチ (Rabin-Karp 的ハッシュによる部分文字列検索) で候補を絞り込む。
- 最大検索長に制限を設ける。
- 事前に行ベースのマッチで候補行を特定してから SequenceMatcher を実行する。

---

### 8. `profile_manager.py` - `_is_similar_phrase()` (L166)

**問題点**:
- プロファイル重複チェックで全ての phrase ペアに対して以下を実行:
  1. `_char_bigram_jaccard()`: 文字バイグラム集合と Jaccard 計算 → O(k1+k2)。
  2. `_longest_common_substring_ratio()`: O(n*m) の DP 的計算。
  3. コンセプトドメインマッチング: 6個のドメインセット × 各キーワードの部分文字列チェック。
- 50エントリで 1225 ペアの比較が発生しうる。

**改善案**:
- Jaccard 前に長さの差が大きいものはスキップ（`abs(len(na)-len(nb)) / max(len(na),len(nb)) > 0.5`）。
- `_char_bigram_jaccard` の bigram 生成を `functools.lru_cache` でメモ化。
- コンセプトドメインマッチングは文字列短い場合はスキップ。

---

### 9. `core.py` - `compress_history_with_llm()` (L1410)

**問題点**:
- チャンクごとに直列 LLM 呼び出し: 前のチャンクの集約が完了するまで次のチャンクを処理できない。
- チャンクサイズの指数的逓減リトライ: コンテキスト長超過時に `while True` で `chunk_size //= 2` を繰り返す。これにより最悪ケースでチャンク数が倍増。
- 各チャンクで `_message_to_text()` による全メッセージのレンダリングが再実行される。

**改善案**:
- チャンクサイズを最初から控えめにする（デフォルト50→20程度）。
- `_message_to_text` の結果をチャンクごとに一度だけ計算してキャッシュ。

---

### 10. `llm_flow_helpers.py` - `_execute_tool_calls()` (L265)

**問題点**:
- `_is_external_data_tool(name)` は内部で `tools.get_external_data_tools()` を毎回呼ぶ。
- パラレル実行の prefetch 判定で `json.dumps(parsed_args, ...)` を全ツールコールに対して2回実行。

**改善案**:
- `_is_external_data_tool` を `functools.lru_cache` でキャッシュ。
- キャッシュキーの json シリアライズを1回に減らす。

---

## 優先度 小 (改善しても効果が限定的)

### 11. `tools/__init__.py` - `run_tool()` (L1231)

**問題点**: 毎ツール実行で `next((s for s in TOOL_SPECS if ...))` で全スペックを線形走査して x_scheck フラグを探す。

**改善案**: `_BUSY_LABEL_TOOLS` と同様に `_EMIT_TRACE_TOOLS` 辞書を事前構築。

### 12. `llm_round_helpers.py` - 全般

**問題点**: 内部に `_t(s)` フォールバック関数が `UnboundLocalError` 対策で毎回定義される。

**改善案**: モジュールレベルのフォールバックに抽出。

### 13. `providers/llm_gemini.py` - `_sanitize_gemini_parameters()` (L50)

**問題点**: 全ツールの JSON Schema を Gemini 互換フォーマットに再帰的変換。毎ラウンド実行。

**改善案**: ツールスキーマ変更がない限り結果をキャッシュ。

### 14. `core.py` - `shrink_messages()` (L1268)

**問題点**: `len(others) <= keep_last` の場合は実質変更不要なのに `_fix_tool_call_boundaries` が常に実行される。

**改善案**: 該当ケースでは呼び出しをスキップ。

---

## 全体的な設計上の観察

### パフォーマンスに影響するパターン

1. **毎ラウンドの全ツールスキーマコピー**: `get_tool_specs()` と `build_responses_request()` で毎回100+ツールのディクショナリをコピー。
2. **過剰なクロージャ定義**: ホットパスで内部関数を毎回定義 → 関数オブジェクトのアロケーションが累積。
3. **try/except の乱用**: `except Exception: pass` が多数。成功パスでも try ブロックのセットアップコストがかかる。
4. **過剰なディクショナリコピー**: `dict(m)` によるメッセージコピーが複数箇所で発生。

### 高速化の指針

1. **キャッシュ戦略**: ツールスキーマの変換結果、カタログ検索結果、`_is_external_data_tool` の結果などをキャッシュ。
2. **遅延評価**: 巨大データ構造のコピーは必要な時だけ行う。
3. **プロファイル計測**: 実際のボトルネック特定には `cProfile` や `py-spy` による実測が有効。上記は静的分析に基づく推定。
