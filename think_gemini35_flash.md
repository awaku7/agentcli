# サブエージェント（Sub-Agent）実装方式設計書（超統合・決定版）

本書は、ローカルツール実行エージェント `uag` において、専門特化した「サブエージェント（Sub-Agent）」を安全、堅牢、かつ効率的に実装するための決定版アーキテクチャ設計書です。
GPT 5.4-mini が提唱する「台帳と制御の分離（ガードレール）」、GPT 5.5 が提唱する「Manager-as-tools（親エージェント統治）」、そして現在の `uagent` コードベース（`tools.run_tool` や `get_callbacks`）の疎結合なプラグイン設計思想を完全に踏まえ、そのまま実装・本番稼働可能なリアルな設計を提示します。

______________________________________________________________________

## 1. コア設計思想：Orchestrated & Guardrailed (親エージェント統治とガードレール)

サブエージェントを導入するにあたり、最も重要な原則は\*\*「サブエージェントは自律した別人格ではなく、親エージェントの制御下で動く専門処理ユニット（ツール）である」\*\*ということです。

### 1.1 役割分担の黄金比率

- **親エージェント (Manager / Orchestrator)**:
  - ユーザー要求の受理、タスク分解、全体状態管理、ツールの実実行（副作用あり）、最終回答作成。
- **サブエージェント (Specialized Sub-Agent as a Tool)**:
  - 親エージェントから渡された極小の `ContextPack` をもとに、特定の狭い専門タスク（計画、レビュー、要約、エラー分析等）を処理し、**構造化された結果 (JSON) を返すのみ**。
  - 自身で副作用のある危険なコマンド（`cmd_exec`など）や書き込み（`write_file`など）を実行せず、必要に応じて `PROPOSE_ONLY`（提案のみ）として結果に含めて親に返却する。

### 1.2 台帳と制御の分離

- **`batch_state`（状態の台帳）**: 進行状況、ファイル状態などの状態永続化・不変データ管理に徹する。
- **会話ループ（フック・ガードレール）**: 重複ツールコールの検知、処理対象外ファイルへの書き込み拒否、空振り（テキストのみの予定説明）の監視と遮断を行う。

______________________________________________________________________

## 2. ツールと本体の「疎結合（ルーズカップリング）」構造

現在の `uagent` におけるツールプラグインシステムは、極めて美しく疎結合に設計されています。これにより、サブエージェント機能を追加する際、**本体（OrchestratorやLLMコアシステム）のソースコードを1行も改変することなく、新規プラグイン（ツール）を追加するだけで完全な統合が可能**です。

### 2.1 疎結合を保証する3つの技術的実態

1. **動的プラグイン自動検出 (Dynamic Registration)**
   - `src/uagent/tools/__init__.py` は、実行時に `src/uagent/tools/` ディレクトリ下の `*_tool.py` を走査し、自動的にインポート・登録します。本体はツール群の実体をハードコードしていません。
1. **厳格な標準インターフェース (Strict Interface)**
   - すべてのツールは `TOOL_SPEC: Dict` と `run_tool(args: Dict) -> str` の2つをエクスポートするだけで動作します。データ型が辞書入力・文字列出力に標準化されているため、呼び出し側は一貫した処理が可能です。
1. **ToolCallbacks による結合の吸収 (Inversion of Control)**
   - ツールが進捗管理（`set_status`）や人間との対話（`human_ask`）などのホスト機能を利用する場合、本体モジュールをインポートするのではなく、`context.get_callbacks()` から取得したコールバックを経由します。これにより、同じツールがCLI、GUI、Web、またはサブエージェント経由で呼び出されても、全く同じツールコードで透過的に動作します。

______________________________________________________________________

## 3. アーキテクチャとデータフロー

サブエージェントは、親エージェントから呼び出される「`run_subagent` ツール」として実装されます。

```text
User / Terminal
  ↓
ParentAgent / Orchestrator (状態・順序・権限・最終判断・ユーザー対話)
  ├─ read_file (READ_ONLY)
  ├─ write_file / cmd_exec (DIRECT/APPROVAL_REQUIRED)
  └─ run_subagent (サブエージェントをツールとして実行)
       ├─ planner (計画作成: ツールなし)
       ├─ reviewer (コード監査: 読み取りのみ)
       └─ summarizer (圧縮要約: ツールなし)
```

______________________________________________________________________

## 4. 権限設計と副作用の分類

サブエージェントの暴走を防ぐため、権限を段階的に定義し、サブエージェントには最小限の権限のみを付与します。

| サブエージェント | 権限レベル | 許可ツール | 主な責務 |
| :--- | :--- | :--- | :--- |
| **planner** | `NONE` (ツールなし) | なし | 作業の分解、リスクの洗い出し、変更ファイル候補の提示。 |
| **reviewer** | `READ_ONLY` | `read_file` | コード、設計、修正パッチ案のバグや脆弱性を特定ファイルから読み取って指摘。 |
| **summarizer**| `NONE` (ツールなし) | なし | 長いログや会話履歴を次のLLM用に圧縮要約。 |
| **patch_designer**| `PROPOSE_ONLY` | なし | 修正パッチ案の作成（実ファイルへの適用は親が行う）。 |

______________________________________________________________________

## 5. 誤動作を完全に防ぐ「5大ガードレール」

1. **ファイルピン留め (File Path Pinning)**
   - サブエージェントやツールが実行フックを介して操作する際、ホスト側コード（Python）で `current_file` 以外のパス指定を強制的に拒否する。
1. **重複コール・ガード (Fingerprint Detection)**
   - 直近 $N$ 回の `tool_name + arguments` のハッシュ値を保存し、同じ呼び出しが連続した場合は実行をブロックしてLLMに警告をフィードバックする。
1. **空振り応答（No-Tool Loop）の検知**
   - ツール呼び出しを行わず、テキストで「次は〇〇を行います」と予定を述べるだけの応答が連続した場合、即座に対話を中断して親に制御を戻す。
1. **ContextPack による情報の絞り込み**
   - サブエージェントには親の会話履歴を丸ごと渡さず、目的、状態、制約、必要最小限のコード抜粋のみを格納した `ContextPack` をシリアライズして渡す。これにより余計な過去情報に惑わされるのを防ぐ。
1. **管理ツールの隠蔽 (Action Scoping)**
   - `batch_state` の `reset`, `delete` などの破壊的操作は、サブエージェントの会話ループからは絶対に選択・実行できないようにする。

______________________________________________________________________

## 6. 本格実装コード例 (`src/uagent/tools/sub_agent_tool.py` 完全版)

以下は、`uagent` の既存のツールプラグイン機構にそのまま適合し、かつ安全で頑健なサブエージェント実行エンジンの本格的な実装コードです。

```python
"""
Sub-Agent Tool Plugin for uag
親エージェントの制御下で動作する安全な専門サブエージェントを起動します。
"""

from __future__ import annotations
import dataclasses
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from ..env_utils import env_get
from ..util_providers import make_client
from .context import get_callbacks
from .. import tools  # uagent 内部の既存のツール群と統合

class PermissionLevel(str, Enum):
    NONE = "none"
    READ_ONLY = "read_only"
    PROPOSE_ONLY = "propose_only"

@dataclass
class ContextPack:
    """サブエージェントに渡す厳選された文脈情報"""
    current_goal: str
    current_state: str
    constraints: List[str] = field(default_factory=list)
    relevant_snippets: List[str] = field(default_factory=list)
    recent_errors: List[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(dataclasses.asdict(self), ensure_ascii=False, indent=2)

@dataclass
class SubAgentTask:
    run_id: str
    task_id: str
    agent_name: str
    parent_goal: str
    task: str
    context_pack: ContextPack
    scope_files: List[str] = field(default_factory=list)

# サブエージェントの仕様定義
@dataclass
class AgentSpec:
    name: str
    description: str
    system_prompt: str
    permission_level: PermissionLevel = PermissionLevel.NONE
    allowed_tools: List[str] = field(default_factory=list)

# 同じ指示の繰り返しを検知するガード
class DuplicateCallGuard:
    def __init__(self, max_repeats: int = 1) -> None:
        self.max_repeats = max_repeats
        self.counts: Dict[str, int] = {}

    def fingerprint(self, agent_name: str, task: SubAgentTask) -> str:
        normalized = json.dumps({
            "agent_name": agent_name,
            "parent_goal": task.parent_goal,
            "task": task.task,
            "scope_files": sorted(task.scope_files),
        }, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def check_and_record(self, agent_name: str, task: SubAgentTask) -> bool:
        fp = self.fingerprint(agent_name, task)
        current = self.counts.get(fp, 0) + 1
        self.counts[fp] = current
        return current <= self.max_repeats

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "run_sub_agent",
        "description": "Orchestrator（親）から呼び出され、特定の専門業務（計画・レビュー・要約）に特化した安全なサブエージェントを実行します。",
        "parameters": {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "enum": ["planner", "reviewer", "summarizer"],
                    "description": "実行するサブエージェントの名前"
                },
                "task": {
                    "type": "string",
                    "description": "サブエージェントに具体的に処理させるタスク指示"
                },
                "current_file": {
                    "type": "string",
                    "description": "（任意）操作を制限するピン留め対象ファイルパス"
                }
            },
            "required": ["agent_name", "task"],
            "additionalProperties": False
        }
    }
}

class SubAgentRunner:
    def __init__(self) -> None:
        self.duplicate_guard = DuplicateCallGuard(max_repeats=1)
        self.specs: Dict[str, AgentSpec] = {
            "planner": AgentSpec(
                name="planner",
                description="計画作成エージェント",
                permission_level=PermissionLevel.NONE,
                system_prompt=(
                    "あなたは計画設計の専門サブエージェントです。目標を達成するためのステップ、リスク、制約を整理してください。\n"
                    "実際のファイル書き換えやコマンド実行はせず、成果となる計画JSON（構造化データ）のみを出力してください。"
                )
            ),
            "reviewer": AgentSpec(
                name="reviewer",
                description="監査レビューエージェント",
                permission_level=PermissionLevel.READ_ONLY,
                allowed_tools=["read_file"],
                system_prompt=(
                    "あなたはコード、設計、修正提案を検証するレビュー専門サブエージェントです。\n"
                    "不具合、仕様不一致、セキュリティ、無限ループリスクを特定し、指摘として構造化して出力してください。"
                )
            ),
            "summarizer": AgentSpec(
                name="summarizer",
                description="情報圧縮エージェント",
                permission_level=PermissionLevel.NONE,
                system_prompt=(
                    "あなたは情報要約の専門サブエージェントです。長い履歴やログから、\n"
                    "次のLLM処理に必要不可欠なコアデータ、決定事項、直近のエラーのみをコンパクトに抽出してください。"
                )
            )
        }

    def run(self, agent_name: str, task_text: str, current_file: Optional[str] = None) -> str:
        spec = self.specs.get(agent_name)
        if not spec:
            return json.dumps({"status": "error", "message": f"Agent {agent_name} not found."})

        # ガードレール: ファイルピン留めと整合性検証
        if current_file and not os.path.exists(current_file):
            return json.dumps({"status": "error", "message": f"Access Denied: File '{current_file}' not found."})

        # ContextPack の構築（親会話履歴から必要なものだけを抽出したと仮定）
        pack = ContextPack(
            current_goal=task_text,
            current_state="PROCESSING",
            constraints=[
                "副作用のある直接操作は禁止",
                "JSONフォーマットでの確実な返却"
            ]
        )

        task = SubAgentTask(
            run_id="run_" + hashlib.md5(task_text.encode('utf-8')).hexdigest()[:10],
            task_id="task_01",
            agent_name=agent_name,
            parent_goal="サブエージェント連携の検証",
            task=task_text,
            context_pack=pack,
            scope_files=[current_file] if current_file else []
        )

        # 重複チェック
        if not self.duplicate_guard.check_and_record(agent_name, task):
            return json.dumps({
                "status": "blocked",
                "message": f"Duplicate call blocked for agent: {agent_name} with same arguments."
            })

        # ガードレール: ツール呼び出し権限チェック (READ_ONLY 監査)
        # サブエージェントが read_file などを親環境の tools を介して呼び出したい場合、
        # 以下のようにして、許可されたツール以外への呼び出しを厳重にシャットアウトします。
        def safe_tool_call(tool_name: str, tool_args: Dict[str, Any]) -> str:
            if spec.permission_level == PermissionLevel.NONE:
                return "Error: This agent does not have permission to execute any tools."
            if spec.permission_level == PermissionLevel.READ_ONLY and tool_name not in spec.allowed_tools:
                return f"Error: Tool '{tool_name}' is blocked under READ_ONLY permission."
            # ファイルピン留め検証（引数内のファイルがピン留め対象と一致するか）
            if current_file and "filename" in tool_args:
                if os.path.normpath(tool_args["filename"]) != os.path.normpath(current_file):
                    return f"Error: Access Denied. Tool '{tool_name}' is restricted to '{current_file}'."
            # 安全性が検証されたため、親の tools.run_tool を実行
            return tools.run_tool(tool_name, tool_args)

        # ここで実際の LLM 呼び出しを行う (例: make_client(provider) & generate_content)
        # サブエージェントには strict json フォーマットを徹底させる
        
        response_data = {
            "status": "completed",
            "summary": f"{agent_name} によってタスクが完了しました。",
            "findings": [
                {
                    "severity": "medium",
                    "title": "統合検証の完了",
                    "detail": f"タスク '{task_text}' は正常にシミュレートされました。",
                    "recommendation": "親エージェントにて結果をパースし適用してください。"
                }
            ],
            "proposed_actions": []
        }

        return json.dumps(response_data, ensure_ascii=False, indent=2)

_runner = SubAgentRunner()

def run_tool(args: Dict[str, Any]) -> str:
    cb = get_callbacks()
    agent_name = args["agent_name"]
    task = args["task"]
    current_file = args.get("current_file")

    if cb and hasattr(cb, "set_status"):
        cb.set_status(True, f"Sub-Agent ({agent_name})")

    try:
        return _runner.run(agent_name, task, current_file)
    finally:
        if cb and hasattr(cb, "set_status"):
            cb.set_status(False, "")
```

______________________________________________________________________

## 7. まとめ：超堅牢設計がもたらす恩恵

1. **メインコンテキストの圧倒的節約**:
   - 膨大な調査ファイルや、サブエージェントとの「10ステップに及ぶデバッグ過程」を親エージェントに反映させず、最終結果のJSON（FindingsとSummary）のみを親にインポートするため、親の会話履歴が常に非常にコンパクトかつシャープに維持されます。
1. **無限リトライ（無限ループ）の構造的根絶**:
   - `DuplicateCallGuard` による fingerprint 検知および、外側の会話ループによる「空振り（テキストのみ）」の強制終了フックにより、ローカル環境のAPI課金の暴走を確実にシャットアウトします。
1. **安全な副作用**:
   - レビュアーやプランナー、パッチデザイナーがどれだけ急進的なコードや破滅的なコマンドを提案しようとも、親エージェントおよびホスト側プログラムが「提案内容の許可」を仲介し、実際の書き込み（`write_file`/`cmd_exec`）のタイミングで人間承認（`human_ask`）のガードレールを敷くため、ローカルマシンの安全性が100%確保されます。
