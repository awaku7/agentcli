# UAG Object-Oriented Agent Skills 設計書

- **文書状態**: 設計案（実装未着手）
- **作成日**: 2026-10-18
- **対象**: UAG / `awaku7/agentcli`
- **基本方針**: 既存 Agent Skills および UAG 独自仕様との完全な後方互換性を保持し、オプトインでオブジェクト指向機能を追加する。

## 1. 目的と結論

従来の Agent Skill は、`SKILL.md` に書かれた説明と実行手順をLLMが読み込んで使う形式である。UAGはすでにSkillの一覧、読み込み、検証、インストール、`allowed-tools` によるツールのロード・保持、セッションへのSkill指示注入、Skillの審査・有効化を持つ。

これらを再実装せず、**「Skill定義」「実行中のSkillインスタンス」「公開メソッド」「インスタンス固有状態」**を追加する。合成（Skillから別Skillを呼ぶ）はその次の段階で対応する。継承・インターフェース・ポリモーフィズムは将来の拡張点とし、初期実装には含めない。

最重要要件は**既存の `SKILL.md` に一文字も変更を加えず、従来の実行結果・外部API・CLI操作を変えない**ことである。

## 2. 調査した既存実装と標準仕様

### 2.1 Agent Skills標準

- 必須ファイルは `SKILL.md` のみ。`name` と `description` は必須。
- `metadata` は文字列キー・文字列値のマッピング。`allowed-tools` は実験的な項目。
- Skillディレクトリには追加ファイルを任意に配置可能。
- プログレッシブ・ディスクロージャ（一覧→本文→参考ファイルの順に必要時だけ読む）を採用。

公式: https://agentskills.io/specification

### 2.2 UAG実装で確認できた既存機能

| 実装 | 現状 | 設計上の扱い |
|---|---|---|
| `tools/agent_skills_shared.py` | `SKILL.md`パース、標準フィールド検証、参考ファイルのパス検査 | 変更を最小限にし、新しい仕様の検証を別モジュールへ分離 |
| `tools/skills_list_tool.py` | frontmatterのみでSkillを列挙 | 従来の出力を変えない |
| `tools/skills_load_tool.py` | 本文読込と`allowed-tools`に記載されたツールのロード・保持 | 従来の挙動を変えない |
| `tools/skill_history.py` | 実行中Skillのツール保持・解除、`finish_skill` | 既存APIを保持 |
| `tools/_genre_control_util.py` | ツール保持がプロセス共有の辞書（ツール名→理由） | 複数インスタンス対応のため「所有者付き保持」を追加 |
| `util_message.py`, `util_cmd_session.py` | `[SKILL]` systemメッセージ、`:skills`・解除 | 変更せず並行利用可能にする |
| `runtime/skill_lifecycle.py` | draft/reviewed/enabled/improved/deprecated のSkill定義ライフサイクル | **Skill実行インスタンスの状態**とは分離 |
| `runtime/session_store.py` | SQLiteによるセッション、ツール呼び出し等の保存 | インスタンス状態を同じセッションIDに関連付ける |
| `runtime/policy_engine.py` | 統一権限判定（allow/confirm/deny） | 既存の実行経路で評価を受ける |

コード参照: https://github.com/awaku7/agentcli

### 2.3 外部の先例

Microsoft Agent Frameworkにはクラスベースの `ClassSkill` / `AgentClassSkill<T>` が存在する。ただし、これはUAGの実行時インスタンス仕様をそのまま提供するものではない。設計上は概念を参考にし、UAGの独自ランタイムで実現する。

参考: https://learn.microsoft.com/en-us/agent-framework/agents/skills

## 3. 完全互換性の定義（必須条件）

以下の条件を満たさない変更は受け入れない。

1. **旧Skillを無変更で動かす**: `uag-object.yaml` がない既存Skillは、従来と同じ読み込み・表示・実行・終了動作をする。
2. **既存APIを壊さない**: `skills_list`、`skills_load`、`skills_validate`、`skills_read_file`、`:skills`、`:skills status`、`:skills clear`、`finish_skill` の入力・出力・副作用を維持する。
3. **既存の独自項目を維持する**: `version`、`inputs`、`outputs` など既存Skillが使用している追加frontmatterを削除・解釈変更しない。
4. **ツール運用を維持する**: `allowed-tools` の従来のツールロード・保持・解除を変更しない。新機能の保持管理と共存させる。
5. **標準仕様を壊さない**: 新規オブジェクト型Skillも標準仕様に準拠した`SKILL.md`を持つ。UAG外では通常の手順書型Skillとして読める。ただしUAG独自のオブジェクト動作が他製品で実行できることまでは保証しない。
6. **段階的読み込みを維持する**: 一覧表示時にメソッド本文や参考ファイルを一括読み込みしない。
7. **オプトイン**: 明示的なマーカーがないSkillは新しいランタイムに自動変換・自動生成しない。初期リリースでは新機能の設定も既定無効。
8. **ローカライズを維持する**: 既存38言語のメッセージ体系を破壊しない。新規のユーザー向け文字列は既存i18n方式へ追加する。
9. **異常系も互換**: 新機能定義が不正であっても、従来の `skills_list` / `skills_load` の成功可否・戻り値は変更せず、新機能の操作だけを明示的エラーにする。
10. **各エントリーポイント共通**: CLIのみ別実装にせず、CLI / GUI / Web / A2A から共通APIを利用する。

### 3.1 拡張仕様の配置方法

**推奨: 標準の `metadata` で関連付けた独立ファイル。** 当初候補だった任意のトップレベル `x-uag` よりも、厳格な外部バリデータに対する互換性を確保しやすい。

```text
python-review/
├── SKILL.md
├── uag-object.yaml         # UAG固有の定義。無くても正常なSkill
└── references/
    ├── analyze.md
    ├── verify.md
    └── state.schema.json
```

```yaml
# SKILL.md の YAML frontmatter（拡張を利用するSkillのみ）
---
name: python-review
description: Pythonコードのレビューと検証を支援する
allowed-tools: "git_ops run_tests lint_format"
metadata:
  uag-object-spec: "uag-object.yaml"
---
```

このあとには従来どおりMarkdown本文を書く。UAG非対応環境でも、本文を読めば通常のレビュー手順を実行できるように記述する。**既存Skillにこのフィールドを追加する必要はない**。

拡張マーカーがないファイルをUAGが勝手に検出・実行しない。`uag-object.yaml` のパスはSkillルート配下のみ許可し、絶対パス、`..`、シンボリックリンク経由のルート外参照を拒否する。

## 4. オブジェクトモデル

| OOPの概念 | UAGの概念 | 意味 |
|---|---|---|
| クラス | Skill定義 | `SKILL.md` + 拡張マニフェスト |
| インスタンス | SkillInstance | セッションに属する個別の実行オブジェクト |
| 公開メソッド | SkillMethod | 入出力スキーマを持つ呼び出し可能な操作 |
| カプセル化 | Private state | 他のSkillから直接書き換えられない状態 |
| コンポジション | `skill`メソッド | 別Skillの操作を明示的に呼び出す（後続） |
| 継承 | 未実装 | 初期段階では導入しない |
| インターフェース | 未実装 | 必要性を検証して後続で定義 |

### 4.1 定義とインスタンスを分ける

```text
SkillDefinition(name, version, definition_hash)
    ├── methods
    ├── state_schema
    └── declared_tools
         |
         | create(session_id)
         v
SkillInstance(instance_id, session_id, state_revision)
    ├── private state (JSON)
    ├── method calls
    ├── tool leases
    └── status (created/active/finished/failed/cancelled)
```

同一のSkill定義から複数のインスタンスを作れる。状態は`session_id`と`instance_id`の組で分離される。これによりルームAのレビュー状態がルームBに漏れない。

既存 `SkillLifecycleManager` の `enabled` 等は**インストール済みSkill定義の審査状態**であり、ここで追加する `active` 等は**実行インスタンスの状態**である。相互に流用しない。

## 5. 宣言仕様 v1（案）

```yaml
# uag-object.yaml
schema: "uag-object-skill/v1"

instance:
  scope: session
  persistence: session-store

state:
  schema: "references/state.schema.json"
  initial:
    targets: []
    findings: []
    verification: null

methods:
  analyze:
    description: "差分を調査して問題点を抽出する"
    kind: prompt
    source: "references/analyze.md"
    tools: [git_ops]

  verify:
    description: "Black・Ruff・関連pytestを検証する"
    kind: prompt
    source: "references/verify.md"
    tools: [run_tests, lint_format]
```

`methods` のキーは外部公開名である。`kind: prompt` は既存LLMの実行経路を利用する。メソッド実行時には対象Skillの手順とインスタンス状態（スキーマで許可された部分）を入力として渡す。構造化した結果を取得し、明示された状態変更だけを検証・適用する。

### 5.1 メソッドの種類

| 種類 | 役割 | 導入段階 |
|---|---|---|
| `prompt` | LLMにSkill固有の手順を実行させる | 最初の実行版 |
| `tool` | 既存のFunction Call/MCPアダプターへ構造化引数を渡す。ツールの直接呼び出しは禁止 | 次段階 |
| `skill` | 別Skillの公開メソッドを呼ぶ。合成用 | 合成段階 |

`tool` 型は任意のPythonを評価・実行する形式にしない。入力からツール引数へのマッピングは宣言的で、入力スキーマとツールスキーマの検証後、**既存の実行ルーター**へ送る。セキュリティを迂回する `import` や `eval` は認めない。

### 5.2 インターフェース（擬似API）

以下は**設計上のAPIであり、現行UAGに実装されていない**。

```python
instance = skill_object.create(skill="python-review", session_id=session_id)
result1 = skill_object.call(instance.id, "analyze", inputs={"target": "PR #123"})
result2 = skill_object.call(instance.id, "verify", inputs={})
state = skill_object.get_state(instance.id)
skill_object.finish(instance.id)
```

MVPでは一つのランタイムサービス `SkillObjectRuntime` に `create / list_methods / call / get_state / finish` をまとめる。LLM公開ツールを何個増やすかは別途判断し、既存 `skills_*` に破壊的変更を加えない。

### 5.3 メソッドの戻り値

成功例（概念）:

```json
{
  "ok": true,
  "instance_id": "<uuid>",
  "method": "analyze",
  "status": "active",
  "state_revision": 2,
  "result": {"summary": "差分の調査を完了"}
}
```

失敗時も例外メッセージを非構造化のまま返さず、機械判定可能な `error.code` を返す。想定: `SKILL_NOT_FOUND`, `OBJECT_SPEC_INVALID`, `METHOD_NOT_FOUND`, `ACCESS_DENIED`, `DEPENDENCY_UNAVAILABLE`, `REVISION_CONFLICT`, `DEFINITION_CHANGED`, `METHOD_FAILED`, `CANCELLED`。

## 6. インスタンス状態と永続化

- **保存先**: 既存SQLite Session Storeと関連する名前空間付きの追加テーブル。既存 `agent_states` をSkill単位の格納先として流用しない。
- **識別**: `instance_id`（UUID）に、`session_id`、Skill定義のパス/識別子、定義ハッシュ、バージョン、所有ユーザー/ルーム文脈を関連付ける。
- **機密性**: 状態はJSONシリアライズ可能な値に限定し、認証情報・アクセストークン・Cookieなどを保存しない。保存前に既存の秘匿化機構を通す。
- **排他制御**: 各状態に `state_revision` を持たせ、楽観的排他制御（CAS）で更新する。同時更新は自動上書きせず `REVISION_CONFLICT`。
- **復元**: 再起動後にセッションを復元すると、同じインスタンスの状態を読み直せる。
- **定義の変更**: 作成時にSkillファイルと参照する拡張マニフェストのハッシュを固定。途中で変更された場合、黙って別定義で実行せず `DEFINITION_CHANGED` にする。
- **状態上限**: 初期案として1インスタンス64KiB。大きなファイルや成果物は既存Artifact/Session Storeの参照を持つ。
- **クリーンアップ**: セッションの削除に連動してインスタンス状態を削除。終了済みインスタンスは参照可能だが書き込み不可。
- **失敗・中断**: 副作用を伴うツールを勝手に再実行しない。将来のリトライでは明示的な冪等キーと実行記録を使う。

### 6.1 状態遷移（実行インスタンス）

```text
created -> active -> finished
              |--> failed
              `--> cancelled
created ----------> cancelled
```

`finished / failed / cancelled` は終端状態。`finish()` は冪等に扱い、二重解放を防止する。失敗後の再実行は新しいインスタンス、または明示的な再開API（将来）を必要とする。

## 7. `allowed-tools` と実行権限

**現行UAGの `allowed-tools` は、主にツールのロードと保持のための宣言として機能している。これだけをセキュリティ境界とみなさない。**

- 従来の `allowed-tools` の解釈を維持する。
- オブジェクトメソッドの `tools` は依存ツールの宣言・事前検証に使う。定義されたツールは `allowed-tools` の具体的な名前と整合することを検査する。
- 実際のFunction Callは、必ず既存のUnifiedPolicy・Enterprise Policy・`human_ask`・Sandbox経路を通す。
- 未実装のSandboxバックエンドに対しては、必要な安全機能があるとみなさず拒否する。
- Skillの有効化は権限付与ではない。親Skillから子Skillを呼ぶ場合も、権限を昇格させない。
- 読み取り専用のスキルでも、LLMが出力を介して機密情報を漏らす可能性があるため、出力と監査記録を適切に処理する。
- 非信頼の `SKILL.md`、外部Skillファイル、メソッド本文からの指示をシステム全体のポリシーより優先させない。

### 7.1 現行のグローバルツール保持との競合（必修の対応）

現在の `_genre_control_util.py` では `_PINNED_TOOLS` がプロセス共有のツール名→理由の辞書である。`skill_history.py` の `finish_skill` はSkillが保持したツールを解除する。単純にオブジェクト型Skillでも同じ仕組みを用いると、別インスタンスが使用中のツールが解除される恐れがある。

対策は**既存APIを残したまま、新規インスタンス向けの所有者付きリースを追加**すること。

```text
legacy pin_tool(tool, reason) / unpin_tool(tool)  # 既存の意味を保持
new    acquire_tool_lease(tool, instance_id)
new    release_tool_lease(tool, instance_id)

is_tool_pinned(tool) = legacy_pin_exists OR any_active_lease
```

`finish_skill` は従来の保持だけを解放し、オブジェクト型Skillのリースを消さない。オブジェクト型Skillの `finish` は自分のリースだけを解放する。`list_pinned_tools` の既存出力形式も保持し、新しい詳細表示は別APIとする。変更時は**既存Skill単独、複数オブジェクトSkill、混在実行**のテストを必須とする。

## 8. Skill合成（後続段階）

継承に先立ち、Skillから別のSkillを呼ぶ明示的な合成を導入する。

```yaml
# 将来の uag-object.yaml（例）
methods:
  full_review:
    kind: skill
    target:
      skill: python-review
      method: analyze
```

- 子Skillは親と異なるインスタンスIDと状態を持つ。
- 子の出力は明示的な戻り値として親へ返し、子の私有状態へ親が直接アクセスしない。
- 循環参照を検証時に検出し、実行時にも最大呼び出し深度・総呼び出し回数・タイムアウトを制限する。
- Child Tool権限は親を超えず、`human_ask`を省略しない。
- 親の中断・キャンセルが子に伝播する。別セッションのインスタンスは暗黙に参照しない。

インターフェースと継承は、合成の使用実績を確認してから最小仕様を決める。複雑な多重継承は採用しない方向で評価する。

## 9. 読み込み・実行時の契約

| ケース | 従来の `skills_list` / `skills_load` | Object API |
|---|---|---|
| 旧Skill（マーカーなし） | **従来どおり** | 明示的な `OBJECT_SPEC_NOT_DECLARED` |
| 拡張Skill・正常定義 | **従来どおり** | create/call等を利用可能 |
| 拡張ファイルが存在しない | **従来どおり** | `OBJECT_SPEC_INVALID` |
| 拡張ファイルが不正 | **従来どおり** | `OBJECT_SPEC_INVALID` |
| オブジェクト機能が無効 | **従来どおり** | `FEATURE_DISABLED` |
| 定義ファイルが実行中に変更 | 既存コマンドは従来どおり | 既存インスタンスは `DEFINITION_CHANGED` |
| 2セッションが同じSkillを使用 | **従来どおり** | 別インスタンス、別状態 |

名前の重複・参照先の曖昧さはObject APIで明示的にエラーにするか、ユーザーが選択した正規化済みSkillパスに固定する。実行中に同名の別Skillへ勝手に切り替えない。

## 10. 段階的実装計画（PRを分離）

### PR1: 拡張マニフェストの読み込み・検証だけ

- `uag-object.yaml` のスキーマと読み込み・検証モジュール。
- `metadata.uag-object-spec` があるときだけオブジェクト定義を検証。
- 既存 `skills_list` / `skills_load` の戻り値・振る舞いを変更しない。
- 初期段階では実行APIを追加しない。
- 標準準拠・旧Skill完全互換の回帰テスト。

### PR2: SkillInstanceと永続状態

- インスタンスID、定義ハッシュ、状態管理、SQLite連携、楽観的排他制御。
- `create/get_state/finish/list_methods`。
- この段階では実際のLLM/ツール実行は追加しない。
- 再起動復元・二重終了・並列セッションのテスト。

### PR3: メソッド実行とツールの所有者付き保持

- `call` と `prompt` メソッド実行。必要な既存Function Callは既存ルーター経由。
- 新しいツールリースの仕組みを追加し、旧 `pin_tool` の意味を維持。
- 既存Policy、`human_ask`、Sandbox、セッションログへの統合。
- 同時実行・競合・危険操作・キャンセル・回帰テスト。

### PR4: 合成と必要な公開インターフェース

- `skill`メソッド、呼び出し深度制限、子の権限制限、循環参照検査。
- UI/ツール経由の利用と多言語対応。
- 依存Skill欠落や複数Skill混在のテスト。

PRごとに実装を止めて差分・CI・レビューを確認し、次のPRへ進む。無関係な整理、互換性のないAPI変更、機能の先取りは混在させない。

## 11. 受け入れテスト

必須のテスト群（名称は仮）:

```text
test_legacy_skill_load_unchanged
test_legacy_skill_list_output_unchanged
test_legacy_skills_cli_and_finish_unchanged
test_legacy_allowed_tools_load_pin_unpin
test_legacy_extra_frontmatter_fields_unchanged
test_object_spec_opt_in_only
test_object_spec_invalid_does_not_break_legacy_loading
test_object_path_traversal_and_symlink_escape_denied
test_object_instance_session_isolation
test_object_instance_persistence_after_restart
test_object_state_revision_conflict
test_object_definition_change_rejected
test_object_methods_do_not_bypass_policy
test_object_method_requires_human_ask_when_dangerous
test_object_tool_leases_parallel_instances
test_object_and_legacy_tool_pins_do_not_interfere
test_object_finish_is_idempotent
test_composition_rejects_cycle_and_permission_escalation
```

検証は `python -m black --check`、Ruff、関連pytest、既存回帰テストを必須とし、実行できない場合は未検証と明記する。CI失敗はログを確認して原因を特定し、必要最小限の修正のみ行う。mainへの直接コミットは行わない。

## 12. 明示的な非目標

初期段階では行わない。

- 従来の全Skillを自動的にクラスへ変換すること。
- Pythonクラスの継承階層をそのまま`SKILL.md`へ移すこと。
- 任意コードの動的評価、無審査の権限付与。
- Skillを使うためだけに新たな外部フレームワークや依存ランタイムを必須とすること。
- プロバイダーの特定機能にSkillの実行を固定すること。
- 既存のMemory・Sub-Agent・MCP・Policy・Session Storeを重複実装すること。
- 全機能を一度に実装すること。

## 13. 設計上の重要な判断

1. **採用**: 標準 `metadata` + 任意の側面ファイル `uag-object.yaml`。未知のトップレベルfrontmatterを大量に増やさない。
2. **採用**: 明示的なインスタンスID、プライベートな状態、メソッド公開。
3. **採用**: 従来Skillは全く変えず、オブジェクト機能を明示選択。
4. **採用**: Skill定義のライフサイクルと実行インスタンスのライフサイクルを分離。
5. **採用**: 合成を継承より優先。
6. **保留**: インターフェース/メソッドオーバーライド/継承の具体的な構文。
7. **禁止**: `allowed-tools`の宣言を実行権限の付与と解釈すること。
8. **必須**: ツール保持の所有者管理。現行の単一共有辞書をそのまま複数インスタンスへ適用しない。

## 14. 参考資料

- Agent Skills仕様: https://agentskills.io/specification
- Microsoft Agent Framework Agent Skills: https://learn.microsoft.com/en-us/agent-framework/agents/skills
- UAG既存Skill共通処理: https://github.com/awaku7/agentcli/blob/main/src/uagent/tools/agent_skills_shared.py
- UAG既存Skill読み込み: https://github.com/awaku7/agentcli/blob/main/src/uagent/tools/skills_load_tool.py
- UAG既存ツール保持: https://github.com/awaku7/agentcli/blob/main/src/uagent/tools/skill_history.py
- UAG既存ツール管理: https://github.com/awaku7/agentcli/blob/main/src/uagent/tools/_genre_control_util.py
- UAG Skill Lifecycle: https://github.com/awaku7/agentcli/blob/main/src/uagent/runtime/skill_lifecycle.py
- UAG新アーキテクチャ: https://github.com/awaku7/agentcli/blob/main/docs/NEW_ARCHITECTURE.md
- AgentFile関連提案（正式標準ではない）: https://github.com/agentskills/agentskills/issues/178

---

**結論**: UAGは `SKILL.md` の標準形式と既存拡張仕様をそのまま維持し、明示的に選択したSkillだけを状態付きの実行オブジェクトとして扱う。小さなPRで互換性を検証しながら進める。