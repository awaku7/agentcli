# TOOL_ASYNC — ツール非同期化（並列実行）設計書

## 1. 背景

uag のツール実行モデルは、LLMが返した tool_calls を**逐次的に1つずつ同期的に実行**している。LLMが1回のレスポンスで複数のツール呼び出しを返した場合でも、直列に実行されるため、I/O待ちが発生するツール（fetch_url, search_web, echonet_* など）が複数あると無駄な待ち時間が生じる。

本ドキュメントでは、ツール実行の非同期化（並列化）の設計方針と実装計画を記す。

## 2. 現状分析

### 2.1 ツール実行のデータフロー

```
LLMレスポンス解析 (uagent_llm.py)
  → _execute_tool_calls() (llm_flow_helpers.py)
    → for tc in tool_calls_list:            # 逐次ループ
        → tools.run_tool(name, args)
          → _RUNNERS[name](args)             # 同期的関数呼び出し
        → 結果を messages に append
  → 次のLLMラウンドへ
```

### 2.2 ツールの契約（インターフェース）

各ツールモジュールは以下をエクスポートする:

- `TOOL_SPEC: dict` — OpenAI function calling 互換スキーマ
- `run_tool(args: dict) -> str` — 同期的な文字列返却関数
- `BUSY_LABEL` / `STATUS_LABEL` — オプションのステータス表示（デフォルト無効）

### 2.3 ツールの特性分類

| カテゴリ | 例 | I/O特性 | 並列化の恩恵 |
|---|---|---|---|
| ファイルI/O | read_file, create_file, file_grep | ブロッキング（1ms〜数秒） | 中 |
| ネットワークI/O | fetch_url, search_web, bluesky, echonet_* | ネットワーク待ち（100ms〜30s） | 大 |
| プロセス実行 | cmd_exec, pwsh_exec, bash_exec | 外部プロセス（可変） | 中（ただし副作用リスク高） |
| ユーザー対話 | human_ask | ブロッキング待機 | 並列不可 |
| 計算/変換 | calculator, date_calc | CPU or 軽量 | 小 |
| ハードウェアI/O | ble_ops, switchbot_ble_* | ハードウェアI/O | 中〜大 |

### 2.4 GILの影響

I/Oバウンドな処理ではGILが解放されるため、今回のツール群においてスレッドプール方式でもGILは実質的に問題にならない。

- ファイルI/O: `open()` / `read()` のカーネル待ち中はGIL解放
- ネットワークI/O: `socket` / `urlopen` の待ち中はGIL解放
- プロセス実行: `subprocess.run()` の待ち中はGIL解放

## 3. 実装方針

### 3.1 選択肢の比較

| 方式 | 概要 | ツール変更 | 外部ツール互換 | 導入コスト | 推奨 |
|---|---|---|---|---|---|
| **A: asyncio全面移行** | run_tool を async def に変更 | 全ツール必要 | 切れる | 極大 | × |
| **B: スレッドプール並列実行** | ツールI/F変更なし、実行エンジンのみ変更 | 不要 | 維持 | 中 | ○ |
| **C: 限定並列実行（opt-in）** | B + x_parallel_safe フラグで opt-in | フラグ追加のみ | 維持 | 小 | **採用** |

### 3.2 採用方式: 限定並列実行（選択肢C）

**基本戦略**:
- ツールのインターフェースは変更しない（`run_tool(args: dict) -> str` のまま）
- 並列実行したいツールは `TOOL_SPEC` に `"x_parallel_safe": True` を追加する（opt-in）
- 実行エンジン（`_execute_tool_calls`）に並列実行フェーズを追加する
- デフォルトは逐次実行（安全側）

**並列実行のルール**:
1. 同じLLMラウンド内の並列安全なツール呼び出しをまとめて `ThreadPoolExecutor` で実行
2. 並列安全でないツールは従来通り逐次実行
3. 結果は元の tool_calls の順序で messages に追加
4. ツール結果キャッシュと組み合わせて動作する

**スレッドプール**:
- 4ワーカー固定（モジュールレベルのシングルトン）
- スレッド名プレフィックス: `tool_par`

### 3.3 並列化の opt-in 基準

並列化の opt-in は以下の条件をすべて満たすツールに限定する:

1. **I/Oバウンド**であること（CPUバウンドはGILの恩恵が少ない）
2. **副作用がない**こと（ファイル書き込み、状態変更、ユーザー対話を含まない）
3. **読み取り専用**であること（グローバル状態を変更しない）
4. **スレッドセーフ**であること（内部で共有状態に書き込まない）

### 3.4 初期の opt-in 候補一覧

| ツール名 | 理由 | 優先度 |
|---|---|---|
| fetch_url | ネットワーク待ち支配的、副作用なし | 高（PoC対象） |
| search_web | 同上 | 高 |
| file_grep / search_files | ディスクI/O待ち | 中 |
| file_hash | I/Oバウンド | 中 |
| calculator | 安全だが恩恵薄い | 低 |
| date_calc | 同上 | 低 |
| bluesky | ネットワーク待ち | 中 |
| echonet_scan / echonet_node_status | ネットワーク待ち（UDP） | 中 |
| analyze_image | API呼び出し待ち | 中 |
| audio_speech / audio_transcribe | API呼び出し待ち | 中 |

## 4. PoC実装記録

### 4.1 変更ファイル

| ファイル | 変更内容 |
|---|---|
| `src/uagent/tools/__init__.py` | `concurrent.futures` インポート追加、`_PARALLEL_TOOL_EXECUTOR`、`is_parallel_safe()`、`run_tools_parallel()` を追加 |
| `src/uagent/tools/fetch_url_tool.py` | `TOOL_SPEC` に `"x_parallel_safe": True` を追加 |
| `src/uagent/llm_flow_helpers.py` | `_execute_tool_calls()` に Phase 1（並列プリフェッチ）と Phase 2（逐次処理＋プリフェッチ結果利用）を追加 |

### 4.2 バックアップ

- `src/uagent/tools/__init__.py.org5`
- `src/uagent/tools/fetch_url_tool.py.org1`
- `src/uagent/tools/fetch_url_tool.py.org`（既存）
- `src/uagent/llm_flow_helpers.py.org1`
- `src/uagent/llm_flow_helpers.py.org`
- `src/uagent/llm_flow_helpers.py.org2`
- `src/uagent/llm_flow_helpers.py.org3`
- `src/uagent/llm_flow_helpers.py.org4`

### 4.3 アーキテクチャ

```
_execute_tool_calls():

  [Phase 1: 並列プリフェッチ]
  tool_calls_list をスキャン
    → is_parallel_safe(name) == True のものを _parallel_batch に集約
    → キャッシュチェック（tool_result_cache）
    → 未キャッシュのものを run_tools_parallel() で一括実行
    → 結果を _prefetched[tc_id] に格納
    → tool_result_cache にも反映

  [Phase 2: 逐次処理]
  tool_calls_list を順次処理
    → tc["id"] が _prefetched にあれば結果を再利用
    → なければ従来通り tools.run_tool() を実行
    → 後処理（tool_msg 構築, attachments 抽出, auto_user_msg 生成）は従来通り
```

### 4.4 検証

`python -m py_compile` で3ファイルすべての構文チェック通過済み。

## 5. 本実装に向けたTODO

### 5.1 トレーサビリティ

- [ ] 並列実行時の `[TOOL]` トレース出力の競合対策（行が混ざる問題）
  - 方法1: 各スレッド内で結果文字列をバッファリングし、メインスレッドで一括出力
  - 方法2: `_emit_tool_trace` 内で `threading.Lock` で保護
- [ ] Busyステータス表示の改善（並列中は `"tool:parallel(N)"` のように実行中ツール数を表示）

### 5.2 スレッドプール管理

- [ ] ワーカー数の環境変数対応（例: `UAGENT_PARALLEL_TOOL_WORKERS`）
- [ ] アプリケーション終了時のクリーンシャットダウン（現状はプロセス終了時に自動回収）
- [ ] スレッドプールの動的リサイズ（将来）

### 5.3 エラーハンドリング

- [ ] 並列実行中のあるツールがハングした場合のタイムアウト
- [ ] キャンセル（LLMラウンド中断時の未完了ツールのキャンセル）

### 5.4 他のツールへの opt-in 展開

- [ ] `search_web` — ネットワークI/O、副作用なし
- [ ] `file_grep` / `search_files` — ディスクI/O、読み取り専用
- [ ] `file_hash` — 同上
- [ ] `bluesky` — ネットワークI/O
- [ ] `echonet_scan` / `echonet_node_status` — ネットワークI/O
- [ ] `analyze_image` — API呼び出し待ち
- [ ] `audio_speech` / `audio_transcribe` — API呼び出し待ち
- [ ] `calculator` / `date_calc` — 安全だが優先度低

### 5.5 テスト

- [ ] 単体テスト: `is_parallel_safe()` / `run_tools_parallel()`
- [ ] 結合テスト: LLMが複数の並列安全ツールを同時に呼び出すシナリオ
- [ ] キャッシュとの組み合わせテスト
- [ ] 並列安全ツール + 非並列ツール混在のテスト

### 5.6 ドキュメント

- [ ] `DEVELOP_TOOL.md` に `x_parallel_safe` の説明を追加
- [ ] 外部ツール開発者向けの注意事項を記載

## 6. 考慮点・リスク

| 項目 | リスク | 対策 |
|---|---|---|
| スレッドセーフ | 複数ツールが同時に同じリソースにアクセス | 副作用のあるツールは opt-in しない |
| stdout の混線 | 並列実行中の print() 出力が混ざる | Lock 保護 または バッファリング |
| 外部ツール互換性 | 外部ツールが opt-in していない限り従来挙動 | デフォルト `x_parallel_safe=False` |
| キャッシュの一貫性 | 並列実行とキャッシュのタイミング | Phase 1 終了後にキャッシュ反映 |
| LLMのツール選択 | LLMが並列実行を期待して多くのツールを一度に呼ぶとワーカー不足 | max_workers の適切な設定と監視 |
| human_ask との共存 | ユーザー入力待機中に他のツールを実行すると混乱 | human_ask は逐次グループで処理 |
