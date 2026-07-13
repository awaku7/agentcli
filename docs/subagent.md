# Sub-Agent ツール 設計ドキュメント

## 目的

このドキュメントは `run_sub_agent` ツールの設計・実装状況・拡張計画を記録する。
現状の実装完了機能に加え、不足している仕組みとその優先実装計画を記載する。

## 1. アーキテクチャ（現状）

```
run_tool(args)
  → SubAgentRunner.run()
    → make_client()                         # プロバイダクライアント生成
    → _build_structured_prompt()            # system prompt の構築
    → _build_user_prompt()                  # user prompt の構築 (ContextPack 含む)
    → _call_llm_single_round()              # LLM 1往復呼び出し
    → _validate_structured_output()         # JSON 出力の検証
```

- 各LLMプロバイダ（openai/claude/gemini/vertexai）に対応
- 親エージェントの core モジュールはインポートせず、util_providers.py のみ使用
- スレッドセーフ：`_SUB_AGENT_ENV_LOCK` で環境変数操作を保護
- サブエージェントはツール実行不可（PermissionLevel.NONE 固定）

## 2. 実装済み機能（v0.5.43 時点）

| 機能 | 状態 | 詳細 |
|------|------|------|
| 6種の役割テンプレート | 完了 | planner, reviewer, summarizer, patch_designer, error_analyst, translator |
| 構造化出力 (response_mode) | 完了 | "json" / "text" 切替可能。デフォルト: summarizer以外はjson |
| required_fields 検証 | 完了 | strict_output=true 時、不足フィールドをエラー扱い |
| evidence_required / evidence_min_items | 完了 | evidence配列の件数検証 |
| response_schema 引数 | 完了 | system promptにJSON Schemaを注入（スキーマ自体のバリデーションは未実装） |
| ContextPack | 完了 | current_goal, current_state, constraints, relevant_snippets, recent_errors |
| current_file 注入 | 完了 | ファイル存在確認＋内容読込＋snippets化（最大20000文字） |
| DuplicateCallGuard | 完了 | 同一 agent_name + task の重複呼び出しをSHA256指紋で検出・ブロック |
| エラー応答の構造化 | 完了 | {"status":"error","message":"..."} 形式 |
| 個別プロバイダ設定 | 完了 | UAGENT_SUB_AGENT_{NAME}_PROVIDER/DEPNAME/API_KEY で上書き可能 |
| UI通知(cb.log_message) | 完了 | サブエージェント開始時・完了時に結果をログ出力 |
| テスト | 完了 | tests/test_sub_agent_translator.py（単体テスト） |

## 3. 不足機能の分析と対応方針

現状のサブエージェントは「話すだけで何も実行できない」存在に留まっている。
以下、不足している仕組みを重要度順に整理する。

### 3-1. ツール実行権限（PermissionLevel の実制御）【最重要】

**問題**: `PermissionLevel` は enum 定義（NONE / READ_ONLY / PROPOSE_ONLY）があるが、NONE 固定で未使用。サブエージェントはファイル読み取りすらできない。

**対応方針**:
- READ_ONLY: ファイル読み取りのみ許可（read_file, file_grep 等、安全な読み取りツールのみ）
- PROPOSE_ONLY: 新しいファイル作成の提案はできるが、既存ファイルの削除・上書きは不可
- PermissionLevel を TOOL_SPEC の引数として公開し、呼び出し側が指定可能にする
- サブエージェント内で使用可能なツールリストを `allowed_tools` で制御

**allowed_tools の動作モデル**:
サブエージェントは tool_calls を生成しない（単発テキスト生成のみ）。そのため allowed_tools は以下のように機能する:

1. system prompt に「以下のツールが利用可能です」とツール一覧を列挙する
2. サブエージェントはテキストで「{tool_name}(引数1=値1, 引数2=値2)」のような形式でツール使用を指示する
3. SubAgentRunner がその指示をパースし、代行実行する
4. 実行結果は ContextPack の relevant_snippets に追加され、サブエージェントが次の応答で参照可能になる

この動作モデルは READ_ONLY 時に有効となる。NONE 時は system prompt にツール一覧を追加しない。

### 3-2. 結果キャッシュ機構【高】

**問題**: DuplicateCallGuard は同一入力をブロックするだけ。過去の正常結果をキャッシュして再利用できない。

**対応方針**:
- DuplicateCallGuard に `cache_dir` を追加し、正常終了した結果を SHA256 指紋キーでファイル保存
- 同一指紋の呼び出しが来た場合、LLM を呼ばずにキャッシュを返す
- `cache_ttl`（キャッシュ有効期限）パラメータを TOOL_SPEC に追加

### 3-3. 情報共有バス（サブエージェント間コンテキスト受け渡し）【高】

**問題**: サブエージェントの出力を別のサブエージェントが参照するには、親エージェントが中継するしかない。会話履歴が肥大化する。

**対応方針**:
- ContextPack に `shared_context` フィールドを追加（Dict[str, Any]）
- `store_key` / `load_keys` 引数を TOOL_SPEC に追加
  - `store_key`: このサブエージェントの出力を共有ストアに保存するキー名
  - `load_keys`: 共有ストアから読み込むキー名のリスト（対応する値が ContextPack に自動注入される）
- 共有ストアは SubAgentRunner のインスタンス変数（スレッドセーフ）として保持

**共有ストアの生存期間管理**:
- `_shared_store` は SubAgentRunner のインスタンス変数として保持される
- セッション開始時にクリアする（SubAgentRunner.__init__() または専用の reset() メソッド）
- 明示的にクリアする手段として `store_key="__clear__"` を予約する
- Phase 3 で永続化ログと統合する場合、ディスクへの保存/復元を追加する

**parent_goal の動的伝搬**:
- 現在 `parent_goal` は `"サブエージェント連携の実行"` で固定されている
- 親エージェントの現在の目標を動的に受け取るための `parent_goal` 引数を TOOL_SPEC に追加する
- 未指定時は従来通り固定値を使用する
- 情報共有バス（load_keys）を経由して他のサブエージェントの出力から parent_goal を補完する機構も検討する

### 3-4. フォールバック・リトライ機構【中】

**問題**: JSONパースエラーやプロバイダエラーが発生しても、リトライなしで即座にエラー応答を返す。

**対応方針**:
- `max_retries` 引数を TOOL_SPEC に追加（デフォルト 2）
- `_call_llm_single_round` のラッパーでリトライループを実装:
  - JSONパースエラー → system prompt に「前回の出力はJSON形式ではありませんでした。必ず有効なJSONのみを出力してください」を追加してリトライ
  - プロバイダエラー → exponential backoff でリトライ
- 最大リトライ回数を超えた場合は structured error を返す

**タイムアウト**:
- `_call_llm_single_round()` に timeout パラメータを追加する（デフォルト 120秒）
- `timeout` 引数を TOOL_SPEC に追加（integer, 秒単位, 0=無制限）
- タイムアウト発生時は structured error を返す
- プロバイダごとにタイムアウトの設定方法が異なるため、_call_llm_single_round の分岐内で各プロバイダの client に適切な timeout を設定する

### 3-5. 永続化ログ【中】

**問題**: サブエージェントの実行履歴がセッション内でしか見られない。

**対応方針**:
- `UAGENT_SUB_AGENT_LOG_DIR`（デフォルト: `~/.uag/subagent_logs/`）に実行ログを保存
- 保存内容: run_id, agent_name, task, ContextPack, 出力結果, トークン使用量, 実行日時
- ログは日別ファイル（`subagent_YYYYMMDD.jsonl`）

### 3-6. 動的役割生成【中】

**問題**: 6種類の AgentSpec がコードにハードコードされている。新しい役割を追加するには Python 編集が必要。

**対応方針**:
- `UAGENT_SUB_AGENT_ROLES_DIR`（デフォルト: `~/.uag/subagent_roles/`）に JSON 設定ファイル方式で新しい役割を定義可能にする
- 設定ファイルのフォーマット例:
  ```json
  {
    "name": "security_auditor",
    "description": "セキュリティ監査エージェント",
    "system_prompt": "あなたはセキュリティ監査に特化したサブエージェントです。...",
    "default_required_fields": ["status", "role", "summary", "vulnerabilities", "severity", "recommendations"],
    "default_response_mode": "json"
  }
  ```
- ビルトインの6役割は引き続きコード内に保持し、外部定義がビルトインをオーバーライド可能にする

### 3-7. コスト・トークン使用量トラッキング【中】

**問題**: サブエージェントごとの API コストやトークン消費量が記録されない。

**対応方針**:
- `_call_llm_single_round` の戻り値に使用トークン数を含める（プロバイダごとの response オブジェクトから抽出）
- 累積使用量を SubAgentRunner のインスタンス変数で保持
- 永続化ログにも記録

### 3-8. 連携オーケストレーション【中〜高 ※設計次第】

**問題**: 複数のサブエージェントを順次実行したり、条件分岐させたりする機構がない。親エージェントが自力で tool_calls を組み立てる必要がある。

**対応方針**:
- Phase 3 で対応。専用のオーケストレーションツール（`run_sub_agent_chain`）を追加
- チェーン定義: `[{"agent":"planner","task":"...","store_key":"plan"},{"agent":"reviewer","task":"...","load_keys":["plan"]}]`
- 各ステップの結果が次のステップの ContextPack に自動注入される
- エラー発生時の停止/継続ポリシーを指定可能

### 3-9. コンテキスト自動収集【低】

**問題**: ContextPack の各フィールドが手動設定前提。特に recent_errors は呼び出し側が明示的にセットする必要がある。

**対応方針**:
- 親エージェントの会話履歴から直近のエラー（例外発生時のログ）を自動スキャンして ContextPack に注入するオプション
- `auto_context` 引数（bool, デフォルト false）で有効化

### 3-10. 並列実行【低】

**問題**: x_parallel_safe=True だが、複数サブエージェントを並列起動する機構がない。

**対応方針**: Phase 4 で対応。thread pool を使った並列実行ラッパーを提供。

### 3-11. サブエージェントの入れ子呼び出し【中】

**問題**: PermissionLevel が READ_ONLY 以上になると、サブエージェントが別のサブエージェントを呼び出す可能性がある。現在はそのための制御機構がない。

**対応方針**:
- 最大ネスト深さ `max_nesting_depth` を SubAgentRunner に追加（デフォルト 3）
- 循環呼び出し検出: 呼び出しチェーンを追跡し、同一 agent_name が2回出現したらブロック
- コンテキスト汚染防止: 入れ子呼び出し時は親の ContextPack を子にコピーするが、親の _shared_store への書き込みはブロックする
- TOOL_SPEC に `nesting_depth` 引数を追加（内部使用、LLM が直接指定するものではない）

### 3-12. i18n 対応【低】

**問題**: コード内に日本語/英語のハードコードが混在している（parent_goal, constraints, system_prompt 等）。TOOL_SPEC の description は i18n 対応済みだが、実行時の文字列は未対応。

**対応方針**:
- Phase 4 で対応
- `make_tool_translator(__file__)` を使って system_prompt を多言語化する
- parent_goal と constraints も translate 可能な形に変更する
- AgentSpec に `locale` フィールドを追加し、サブエージェントごとに使用言語を指定可能にする
- 現状の日本語 system_prompt はデフォルト値として維持する

### 3-13. ContextPack/SubAgentTask ファクトリ不在【低】

**問題**: `run()` メソッド内で ContextPack と SubAgentTask がベタ書きで生成されている。今後引数が増えると管理が煩雑になる。

**対応方針**:
- Phase 3 以降でリファクタリング対象とする
- `ContextPack.from_run_args(...)` クラスメソッドを追加
- `SubAgentTask.from_context(...)` クラスメソッドを追加
- 現状は `run()` メソッド内の生成ロジックをそのまま維持する

## 4. 優先実装計画

### Phase 1（即時: 次回実装時）
| # | 機能 | 変更箇所 | 推定工数 |
|---|------|---------|---------|
| 1 | PermissionLevel の実制御 | SubAgentRunner.run() にツールフィルタリング追加 | 小 |
| 2 | 結果キャッシュ | DuplicateCallGuard にキャッシュ保存/参照を追加 | 小 |
| 3 | 情報共有バス | ContextPack 拡張 + shared_store を SubAgentRunner に追加 | 小〜中 |

### Phase 2（短期: 次の次）
| # | 機能 | 変更箇所 | 推定工数 |
|---|------|---------|---------|
| 4 | フォールバック・リトライ | _call_llm_single_round にラッパー追加 | 小 |
| 5 | 永続化ログ | SubAgentRunner.run() 終了時にファイル書き込み | 小 |

### Phase 3（中期）
| # | 機能 | 変更箇所 | 推定工数 |
|---|------|---------|---------|
| 6 | 動的役割生成 | SubAgentRunner.__init__() で外部 JSON 読み込み | 中 |
| 7 | コストトラッキング | _call_llm_single_round の戻り値拡張 | 小 |
| 8 | オーケストレーションツール | 新規ツール run_sub_agent_chain | 大 |

### Phase 4（長期）
| # | 機能 | 変更箇所 | 推定工数 |
|---|------|---------|---------|
| 9 | コンテキスト自動収集 | auto_context オプション追加 | 中 |
| 10 | 並列実行 | ThreadPoolExecutor ラッパー | 中 |
| 11 | 入れ子呼び出し制御 | SubAgentRunner に max_nesting_depth + 循環検出追加 | 中 |
| 12 | i18n 対応 | system_prompt の多言語化 + locale フィールド追加 | 中 |

## 5. Phase 1 詳細設計

### 5-1. PermissionLevel の実制御

**TOOL_SPEC 変更**:
```python
"permission_level": {
    "type": "string",
    "enum": ["none", "read_only", "propose_only"],
    "description": "Sub-agent execution permission level.",
}
```

**実装**:
- READ_ONLY 時: safe_exec_ops.py に倣った safe フィルタを適用。ファイル読み取りツール（read_file, file_grep, search_files）のみ許可し、書き込みツール（create_file, delete_file）はエラーを返す。
- PROPOSE_ONLY 時: 新しいファイル作成の提案を許可するが、既存ファイルの変更・削除は拒否。create_file は新規ファイルのみ許可。
- `_SUB_AGENT_TOOL_WHITELIST` をモジュール定数として定義。
- allowed_tools の動作モデル（3-1参照）に従い、system prompt へのツール一覧注入と結果パースを実装する。

### 5-2. 結果キャッシュ

**DuplicateCallGuard 変更**:
```python
class DuplicateCallGuard:
    def __init__(self, max_repeats: int = 1, cache_dir: Optional[Path] = None):
        ...
    def get_cached(self, agent_name: str, task: SubAgentTask) -> Optional[str]:
        fp = self.fingerprint(agent_name, task)
        cache_file = self.cache_dir / f"{fp}.json"
        if cache_file.exists():
            return cache_file.read_text(encoding="utf-8")
        return None
    def store_cache(self, agent_name: str, task: SubAgentTask, result: str) -> None:
        fp = self.fingerprint(agent_name, task)
        cache_file = self.cache_dir / f"{fp}.json"
        cache_file.write_text(result, encoding="utf-8")
```

**TOOL_SPEC 変更**:
```python
"cache_ttl": {
    "type": "integer",
    "description": "Cache TTL in seconds. 0 = no cache. Default 0.",
}
```

### 5-3. 情報共有バス

**ContextPack 変更**:
```python
@dataclass
class ContextPack:
    current_goal: str
    current_state: str
    constraints: List[str] = field(default_factory=list)
    relevant_snippets: List[str] = field(default_factory=list)
    recent_errors: List[str] = field(default_factory=list)
    shared_context: Dict[str, Any] = field(default_factory=dict)  # 追加
```

**SubAgentRunner 変更**:
```python
class SubAgentRunner:
    def __init__(self):
        ...
        self._shared_store: Dict[str, Any] = {}  # サブエージェント間共有ストア
        self._store_lock = Lock()
```

**TOOL_SPEC 変更**:
```python
"store_key": {
    "type": "string",
    "description": "Key to store this sub-agent's result in the shared context store.",
},
"load_keys": {
    "type": "array",
    "items": {"type": "string"},
    "description": "Keys to load from the shared context store.",
},
```

## 6. 設計原則

1. **後方互換は一切考慮しない。新しい設計を常に優先する。**
2. **役割ごとにテンプレートを分ける。**
3. **参照した根拠を残す。**
4. **サブエージェントはデフォルトでツールを実行しない。明示的に permission_level を指定した場合のみ権限を付与する。**
5. **キャッシュは明示的に有効化された場合のみ使用する（cache_ttl > 0）。**
6. **共有ストアはスレッドセーフに実装し、内容が肥大化しないよう store_key 単位で管理する。**

## 7. 実装時の判断基準

- **後方互換は一切考慮しない。破壊的変更を躊躇しない。**
- エラーは例外で投げっぱなしにせず、可能な限り構造化して返す。
- 必要情報が足りない場合は、推測で埋めずに不足として返す。
- Phase 単位で実装し、1 Phase 内の変更は 1 回の PR で完了させる。
- Phase 完了後、関連するテストを新規・更新し、テストスイートが通過することを確認する。

## 8. 完了条件

このドキュメントが十分に具体的である状態は、次の質問に答えられるとき:

- 何を入力として受け取るか → TOOL_SPEC の引数定義を参照
- 何を出力するか → 役割ごとの JSON 形式を参照
- 失敗時に何を返すか → {"status":"error","message":"..."}
- どの役割にどの制約を置くか → 役割テンプレート表を参照
- **現在の不足機能は何か → 第3節を参照**
- **次に実装すべきものは何か → 第4節のPhase 1を参照**
- **その実装の詳細設計は何か → 第5節を参照**

## 9. 関連ドキュメント

- `docs/ENVIRONMENT.ja.md` 第10節: 環境変数による個別プロバイダ設定の詳細
- `src/uagent/tools/sub_agent_tool.py`: 実装コード
- `tests/test_sub_agent_translator.py`: 単体テスト
- `src/uagent/docs/DEVELOP_TOOL.md`: ツールプラグインの作成方法
- `src/uagent/docs/DEVELOP_I18N.md`: 国際化対応ガイド
