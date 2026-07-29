"""Sub-Agent Tool Plugin for uag
親エージェントの制御下で動作する安全な専門サブエージェントを実行します。
本体のコアシステムをインポートせず、util_providers.py のクライアント生成ユーティリティのみを介して動作します。
"""

from __future__ import annotations
import dataclasses
import datetime
import hashlib
import json
import os
import re
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any, Dict, List, Optional

from .context import get_callbacks
from ..env_utils import env_get
from ..providers.util_providers import make_client
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# 空リスト = 全ツール許可。サブエージェントは human_ask でユーザー確認を取りながら全ツールを実行できる。
_SUB_AGENT_TOOL_WHITELIST: Dict[str, List[str]] = {
    "none": [],
    "read_only": [],  # 空 = 全ツール許可
    "propose_only": [],  # 空 = 全ツール許可 (read_only と同一扱い)
}
_DEFAULT_CACHE_DIR = Path.home() / ".uag" / "subagent_cache"
_SUB_AGENT_LOG_DIR = Path.home() / ".uag" / "subagent_logs"
_SUB_AGENT_ROLES_DIR = Path.home() / ".uag" / "subagent_roles"

# ---------------------------------------------------------------------------
# Enums / Data classes
# ---------------------------------------------------------------------------


class PermissionLevel(str, Enum):
    NONE = "none"
    READ_ONLY = "read_only"
    PROPOSE_ONLY = "propose_only"


@dataclass
class ContextPack:
    current_goal: str
    current_state: str
    constraints: List[str] = field(default_factory=list)
    relevant_snippets: List[str] = field(default_factory=list)
    recent_errors: List[str] = field(default_factory=list)
    shared_context: Dict[str, Any] = field(default_factory=dict)

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


@dataclass
class AgentSpec:
    name: str
    description: str
    system_prompt: str
    permission_level: PermissionLevel = PermissionLevel.NONE
    allowed_tools: List[str] = field(default_factory=list)
    default_required_fields: List[str] = field(default_factory=list)
    default_response_mode: str = "json"


# ---------------------------------------------------------------------------
# Duplicate-call guard 兼 結果キャッシュ
# ---------------------------------------------------------------------------


class DuplicateCallGuard:
    def __init__(self, max_repeats: int = 1, cache_dir: Optional[Path] = None) -> None:
        self.max_repeats = max_repeats
        self.counts: Dict[str, int] = {}
        self.cache_dir = cache_dir

    def fingerprint(self, agent_name: str, task: SubAgentTask) -> str:
        normalized = json.dumps(
            {
                "agent_name": agent_name,
                "parent_goal": task.parent_goal,
                "task": task.task,
                "scope_files": sorted(task.scope_files),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def check_and_record(self, agent_name: str, task: SubAgentTask) -> bool:
        fp = self.fingerprint(agent_name, task)
        current = self.counts.get(fp, 0) + 1
        self.counts[fp] = current
        return current <= self.max_repeats

    def get_cached(self, agent_name: str, task: SubAgentTask) -> Optional[str]:
        if not self.cache_dir:
            return None
        fp = self.fingerprint(agent_name, task)
        cache_file = self.cache_dir / f"{fp}.json"
        if cache_file.exists():
            try:
                return cache_file.read_text(encoding="utf-8")
            except Exception:
                return None
        return None

    def store_cache(self, agent_name: str, task: SubAgentTask, result: str) -> None:
        if not self.cache_dir:
            return
        fp = self.fingerprint(agent_name, task)
        cache_file = self.cache_dir / f"{fp}.json"
        try:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(result, encoding="utf-8")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# TOOL_SPEC
# ---------------------------------------------------------------------------

TOOL_SPEC: Dict[str, Any] = {
    "load_order": 50,
    "type": "function",
    "x_parallel_safe": True,
    "tool_genre": "basic",
    "function": {
        "name": "run_sub_agent",
        "description": _(
            "tool.description",
            default="Execute a specialized or general-purpose sub-agent (planner, reviewer, summarizer, patch_designer, error_analyst, translator, or general) under the control of the parent orchestrator.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "sub-agent",
                "planner",
                "reviewer",
                "summarizer",
                "patch_designer",
                "error_analyst",
                "translator",
                "general",
                "orchestrate",
                "patch",
                "error analysis",
                "debugging",
                "translation",
                "localization",
            ],
        ),
        "x_search_terms_en": [
            "sub-agent",
            "planner",
            "reviewer",
            "summarizer",
            "patch_designer",
            "patch",
            "code patch",
            "error_analyst",
            "debug",
            "error analysis",
            "debugging",
            "orchestrate",
            "translator",
            "translation",
            "localization",
            "general",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "description": _(
                        "param.agent_name.description",
                        default="The name of the sub-agent to run. Built-in: planner, reviewer, summarizer, patch_designer, error_analyst, translator, general. Custom roles can be loaded from UAGENT_SUB_AGENT_ROLES_DIR.",
                    ),
                },
                "task": {
                    "type": "string",
                    "description": _(
                        "param.task.description",
                        default="Specific instruction/task for the sub-agent to process.",
                    ),
                },
                "current_file": {
                    "type": "string",
                    "description": _(
                        "param.current_file.description",
                        default="(Optional) Limit the sub-agent's reasoning scope to this specific file.",
                    ),
                },
                "response_mode": {
                    "type": "string",
                    "enum": ["json", "text"],
                    "description": _(
                        "param.response_mode.description",
                        default="Output mode for the sub-agent.",
                    ),
                },
                "response_schema": {
                    "type": "object",
                    "description": _(
                        "param.response_schema.description",
                        default="Optional JSON Schema object for the expected response.",
                    ),
                },
                "required_fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": _(
                        "param.required_fields.description",
                        default="List of required fields in the JSON response.",
                    ),
                },
                "strict_output": {
                    "type": "boolean",
                    "description": _(
                        "param.strict_output.description",
                        default="Treat missing required fields or schema mismatch as errors.",
                    ),
                },
                "evidence_required": {
                    "type": "boolean",
                    "description": _(
                        "param.evidence_required.description",
                        default="Require evidence.",
                    ),
                },
                "evidence_min_items": {
                    "type": "integer",
                    "minimum": 0,
                    "description": _(
                        "param.evidence_min_items.description",
                        default="Minimum number of evidence items required.",
                    ),
                },
                "permission_level": {
                    "type": "string",
                    "enum": ["none", "read_only", "propose_only"],
                    "description": _(
                        "param.permission_level.description",
                        default="Execution permission level for the sub-agent. 'read_only' allows file reads, 'propose_only' allows reads + new file creation.",
                    ),
                },
                "cache_ttl": {
                    "type": "integer",
                    "minimum": 0,
                    "description": _(
                        "param.cache_ttl.description",
                        default="Cache TTL in seconds. 0 = no cache. Default 0.",
                    ),
                },
                "store_key": {
                    "type": "string",
                    "description": _(
                        "param.store_key.description",
                        default="Key to store this sub-agent's result in the shared context store for use by subsequent sub-agents.",
                    ),
                },
                "load_keys": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": _(
                        "param.load_keys.description",
                        default="List of keys to load from the shared context store. The corresponding values are injected into the sub-agent's ContextPack.",
                    ),
                },
                "parent_goal": {
                    "type": "string",
                    "description": _(
                        "param.parent_goal.description",
                        default="Override the parent agent's goal for this sub-agent invocation.",
                    ),
                },
                "timeout": {
                    "type": "integer",
                    "minimum": 0,
                    "description": _(
                        "param.timeout.description",
                        default="LLM call timeout in seconds. 0 = no timeout. Default 120.",
                    ),
                },
                "max_retries": {
                    "type": "integer",
                    "minimum": 0,
                    "description": _(
                        "param.max_retries.description",
                        default="Maximum number of retries on JSON parse or provider errors. Default 2.",
                    ),
                },
                "max_turns": {
                    "type": "integer",
                    "minimum": 1,
                    "description": _(
                        "param.max_turns.description",
                        default="Maximum number of multi-turn interactions for tool use. 3 = recommended. The sub-agent can use tools across multiple rounds before producing the final answer.",
                    ),
                },
            },
            "required": ["agent_name", "task"],
            "additionalProperties": False,
        },
    },
}

# Thread lock for parallel-safe os.environ manipulation in sub-agent
_SUB_AGENT_ENV_LOCK = Lock()


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


class SubAgentRunner:
    def __init__(self) -> None:
        self.duplicate_guard = DuplicateCallGuard(
            max_repeats=1, cache_dir=_DEFAULT_CACHE_DIR
        )
        self.specs: Dict[str, AgentSpec] = {
            "planner": AgentSpec(
                name="planner",
                description="計画作成エージェント",
                permission_level=PermissionLevel.NONE,
                system_prompt=(
                    "あなたは計画作成に特化したサブエージェントです。"
                    "【段階的思考】最初にタスクの全体像を把握し、次に依存関係を分析し、最後に実行可能な手順に分解してください。"
                    "【出力フォーマット】出力は必ずJSONで、以下の各フィールドを厳守してください:\n"
                    '  - status: 必ず"completed"\n'
                    '  - role: "planner"\n'
                    "  - summary: 計画の要約（1〜2文）\n"
                    "  - assumptions: 前提条件のリスト（情報不足の場合は何を仮定したか明記）\n"
                    "  - risks: リスク・注意点のリスト\n"
                    "  - next_actions: 具体的な次の行動手順のリスト（各項目は実行可能な粒度で）\n"
                    "【エッジケース】情報が不足している場合は assumptions にその旨を明記し、必要な追加情報を specific に列挙してください。タスクが既に完了済みの場合は空の next_actions を返してください。\n"
                    "【自己評価】出力前に「この計画で本当にタスクを完了できるか」を自己チェックし、不足があれば assumptions か risks に追記してください。\n"
                    "【トークン効率】各フィールドは必要最小限の情報に絞り、冗長な説明は避けてください。"
                ),
            ),
            "reviewer": AgentSpec(
                name="reviewer",
                description="レビューエージェント",
                permission_level=PermissionLevel.NONE,
                system_prompt=(
                    "あなたはレビューに特化したサブエージェントです。"
                    "【段階的思考】最初に入力の全体構成を把握し、次に「抜け」「論理矛盾」「危険性」「改善余地」の4軸で検査し、最後に優先順位を付けて報告してください。\n"
                    "【出力フォーマット】JSONで以下を厳守:\n"
                    '  - status: "completed" / 問題が致命的なら "error"\n'
                    '  - role: "reviewer"\n'
                    "  - summary: レビュー総評（2〜3文）\n"
                    "  - findings: 発見した問題点のリスト（各項目に severity: high/medium/low を含めること）\n"
                    "  - risks: 将来問題になりうる箇所\n"
                    "  - recommended_actions: 修正提案のリスト\n"
                    '【エッジケース】問題がない場合は findings を空リストにしてください。入力が空や無意味な場合は status を "error" にして理由を message フィールドに記述してください。\n'
                    "【自己評価】各 finding に対して「本当に問題か？」「誤検知ではないか？」を確認し、確信度が低いものは risks に回してください。\n"
                    "【トークン効率】類似の問題はグルーピングし、重要度の高いものから順に記載してください。"
                ),
            ),
            "summarizer": AgentSpec(
                name="summarizer",
                description="要約エージェント",
                permission_level=PermissionLevel.NONE,
                system_prompt=(
                    "あなたは要約に特化したサブエージェントです。"
                    "【段階的思考】最初に入力全体を読み、重要度で情報を選別し、最後に構造化して出力してください。\n"
                    "【出力フォーマット】JSONで以下を厳守:\n"
                    '  - status: "completed"\n'
                    '  - role: "summarizer"\n'
                    "  - summary: 全体の要約（1〜3文）\n"
                    "  - key_points: 重要なポイントのリスト（各項目は具体性を保ち、1項目1情報）\n"
                    "  - open_questions: 未解決の疑問点や確認が必要な点\n"
                    "【エッジケース】入力が極端に短い（1文など）場合は summary だけでよく、key_points は省略可能です。専門用語は元の表現を維持してください。\n"
                    "【自己評価】要約が元の意図を正確に反映しているか確認し、重要情報の欠落がないかチェックしてください。\n"
                    "【トークン効率】冗長表現を避け、各 key_point は20語以内に収めてください。"
                ),
            ),
            "patch_designer": AgentSpec(
                name="patch_designer",
                description="パッチ設計エージェント",
                permission_level=PermissionLevel.NONE,
                system_prompt=(
                    "あなたは変更差分の設計に特化したサブエージェントです。"
                    "【段階的思考】最初に現状のコードを理解し、次に最小変更で目的を達成する方法を設計し、最後に変更の影響範囲を検証してください。\n"
                    "【出力フォーマット】JSONで以下を厳守:\n"
                    '  - status: "completed"\n'
                    '  - role: "patch_designer"\n'
                    "  - summary: 変更概要\n"
                    "  - files: 変更対象ファイルのリスト\n"
                    "  - changes: 各ファイルの具体的な変更内容（追加/削除/修正を明確に）\n"
                    "  - risks: 変更による副作用やリスク\n"
                    "  - validation_steps: 変更後に実行すべき検証手順\n"
                    "【エッジケース】変更が必要ない場合は changes を空リストにし、その理由を summary に記述してください。複数の変更案がある場合は推奨順に列挙してください。\n"
                    "【自己評価】各変更が「本当に必要か」「より安全な代替手段はないか」を確認してください。\n"
                    "【トークン効率】変更内容は unified diff 形式ではなく、変更の意図と箇所を自然言語で簡潔に説明してください。"
                ),
            ),
            "error_analyst": AgentSpec(
                name="error_analyst",
                description="エラー分析エージェント",
                permission_level=PermissionLevel.NONE,
                system_prompt=(
                    "あなたはエラー分析に特化したサブエージェントです。"
                    "【段階的思考】最初にエラーメッセージとコンテキストを収集し、次に原因を切り分け（直接原因→根本原因）、最後に再現条件と対処案を整理してください。\n"
                    "【出力フォーマット】JSONで以下を厳守:\n"
                    '  - status: "completed"\n'
                    '  - role: "error_analyst"\n'
                    "  - summary: エラーの要約\n"
                    "  - root_cause: 根本原因の説明\n"
                    "  - evidence: 判断根拠となった事実のリスト（エラーメッセージ、ログ、スタックトレースなど）\n"
                    "  - proposed_actions: 対処案のリスト（各項目は具体的な操作手順まで含めること）\n"
                    '【エッジケース】原因が特定できない場合は root_cause を "不明" とし、調査に必要な追加情報を列挙してください。複数の原因が考えられる場合は可能性が高い順に列挙してください。\n'
                    "【自己評価】「この原因分析でエラーを再現できるか」「対処案で本当に解決するか」を確認してください。\n"
                    "【トークン効率】evidence は関連部分のみに切り取り、全文を貼り付けないでください。"
                ),
            ),
            "translator": AgentSpec(
                name="translator",
                description="翻訳エージェント",
                permission_level=PermissionLevel.NONE,
                system_prompt=(
                    "あなたは翻訳に特化したサブエージェントです。"
                    "【段階的思考】最初に原文の意図・用語・文体を把握し、次に対象言語の自然な表現へ変換し、最後に用語一貫性とプレースホルダ保全を確認してください。\n"
                    "【出力フォーマット】JSONで以下を厳守:\n"
                    '  - status: "completed"\n'
                    '  - role: "translator"\n'
                    "  - summary: 翻訳結果の要約\n"
                    "  - source_lang: 原文言語（ISO 639-1 等）\n"
                    "  - target_lang: 訳文言語（ISO 639-1 等）\n"
                    "  - translation: 翻訳本文\n"
                    "  - notes: 用語選択・曖昧さ・未訳箇所などの補足（必要な場合のみ）\n"
                    "【エッジケース】原文が複数言語混在の場合は主要言語を source_lang とし、混在箇所を notes に記載してください。"
                    "翻訳不能な断片がある場合は translation に可能な範囲を入れ、notes に理由を書いてください。\n"
                    "【自己評価】意味の忠実性・自然さ・用語一貫性・プレースホルダ（{...} / %(name)s 等）の保全を確認してから出力してください。\n"
                    "【トークン効率】translation 以外に原文全文を重複させないでください。"
                ),
            ),
            "general": AgentSpec(
                name="general",
                description="汎用エージェント",
                permission_level=PermissionLevel.NONE,
                system_prompt=(
                    "あなたは汎用タスク処理エージェントです。特定の役割に縛られず、与えられたタスクを柔軟に処理してください。\n"
                    "【段階的思考】最初にタスクの目的と要件を理解し、次に必要な情報やツールを判断し、最後に結果を構造化して出力してください。\n"
                    "【出力フォーマット】出力はJSONで、以下のフィールドを含めてください:\n"
                    '  - status: "completed"\n'
                    '  - role: "general"\n'
                    "  - summary: 処理結果の要約\n"
                    "  - details: 詳細な結果（内容はタスクに応じて自由に構造化）\n"
                    "  - notes: 補足情報や前提条件（必要な場合のみ）\n"
                    '【エッジケース】タスクの要件が不明確な場合は notes にその旨を記載し、判断した前提条件を明示してください。タスクが実行不能な場合は status を "error" として理由を summary に記述してください。\n'
                    "【自己評価】出力がタスクの要件を満たしているか確認し、不足があれば補ってから出力してください。\n"
                    "【トークン効率】details は必要十分な情報に絞り、冗長な説明を避けてください。"
                ),
            ),
        }
        ext_specs = self._load_external_roles()
        self.specs.update(ext_specs)
        self._shared_store: Dict[str, Any] = {}
        self._store_lock = Lock()
        self._call_chain: List[str] = []
        self._total_usage: Dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        self._usage_lock = Lock()

    # ------------------------------------------------------------------
    # 動的役割生成
    # ------------------------------------------------------------------

    @staticmethod
    def _load_external_roles() -> Dict[str, AgentSpec]:
        dir_str = os.environ.get("UAGENT_SUB_AGENT_ROLES_DIR", "")
        roles_dir = Path(dir_str) if dir_str else _SUB_AGENT_ROLES_DIR
        specs: Dict[str, AgentSpec] = {}
        if not roles_dir.is_dir():
            return specs
        for json_file in sorted(roles_dir.glob("*.json")):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                name = data.get("name", "")
                if not name:
                    continue
                spec = AgentSpec(
                    name=name,
                    description=data.get("description", ""),
                    system_prompt=data.get("system_prompt", ""),
                    permission_level=PermissionLevel.NONE,
                    allowed_tools=data.get("allowed_tools", []),
                    default_required_fields=data.get("default_required_fields", []),
                    default_response_mode=data.get("default_response_mode", "json"),
                )
                specs[name] = spec
            except Exception:
                continue
        return specs

    # ------------------------------------------------------------------
    # コストトラッキング
    # ------------------------------------------------------------------

    def _accumulate_usage(self, usage: Dict[str, int]) -> None:
        with self._usage_lock:
            for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
                self._total_usage[k] += int(usage.get(k, 0) or 0)

    def get_total_usage(self) -> Dict[str, int]:
        with self._usage_lock:
            return dict(self._total_usage)

    def get_total_cost_estimate(
        self,
        *,
        provider: str | None = None,
        model_name: str | None = None,
    ) -> Dict[str, Any] | None:
        """Estimate cumulative cost from tracked usage via llmcapa pricing."""
        usage = self.get_total_usage()
        try:
            from uagent.llmcapa_util import estimate_cost

            return estimate_cost(
                int(usage.get("prompt_tokens", 0) or 0),
                int(usage.get("completion_tokens", 0) or 0),
                model_name,
                provider,
            )
        except Exception:
            return None

    @staticmethod
    def _usage_with_cost(
        usage: Dict[str, int],
        *,
        provider: str | None = None,
        model_name: str | None = None,
    ) -> Dict[str, Any]:
        out: Dict[str, Any] = dict(usage or {})
        try:
            from uagent.llmcapa_util import estimate_cost

            est = estimate_cost(
                int(out.get("prompt_tokens", 0) or 0),
                int(out.get("completion_tokens", 0) or 0),
                model_name,
                provider,
            )
            if est:
                out["estimated_cost"] = est.get("cost")
                out["currency"] = est.get("currency", "USD")
        except Exception:
            pass
        return out

    def reset_usage(self) -> None:
        with self._usage_lock:
            for k in self._total_usage:
                self._total_usage[k] = 0

    # ------------------------------------------------------------------
    # 永続化ログ
    # ------------------------------------------------------------------

    def _write_log(
        self,
        agent_name: str,
        task: Optional[SubAgentTask],
        result: str,
        status: str,
        *,
        retries: int = 0,
        error: str = "",
        usage: Optional[Dict[str, int]] = None,
    ) -> None:
        log_dir_str = os.environ.get("UAGENT_SUB_AGENT_LOG_DIR", "")
        log_dir = Path(log_dir_str) if log_dir_str else _SUB_AGENT_LOG_DIR
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            today = datetime.date.today().strftime("%Y%m%d")
            log_file = log_dir / f"subagent_{today}.jsonl"
            entry: Dict[str, Any] = {
                "timestamp": datetime.datetime.now().isoformat(),
                "agent_name": agent_name,
                "status": status,
                "retries": retries,
            }
            if error:
                entry["error"] = error[:500]
            if usage:
                entry["usage"] = usage
            if task is not None:
                entry["run_id"] = task.run_id
                entry["parent_goal"] = task.parent_goal
                entry["task_preview"] = task.task[:300]
            if result:
                entry["result_preview"] = result[:1000]
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _infer_status(self, result: str) -> str:
        if result.startswith('{"status":"error"'):
            return "error"  # noqa: i18n
        if result.startswith('{"status":"blocked"'):
            return "blocked"  # noqa: i18n
        if result.startswith('{"status":"completed"'):
            return "completed"
        try:
            obj = json.loads(result)
            if isinstance(obj, dict):
                return obj.get("status", "completed")
        except Exception:
            pass
        return "completed"

    # ------------------------------------------------------------------
    # PermissionLevel 支援 (共通)
    # ------------------------------------------------------------------

    def _build_tool_list_prompt(self, permission_level: str) -> str:
        if permission_level == "none":
            return ""
        # 空リスト = 全ツール許可
        return (
            "\n\n[利用可能なツール]\n"
            "すべてのツールが利用可能です。\n"
            "ツールを使用するには {tool_name}(引数1=値1, 引数2=値2) の形式で指示してください。\n"
            "危険な操作を行う場合は、先に human_ask で確認を取ってください。"
        )

    def _execute_tool_calls(self, text: str, permission_level: str) -> List[str]:
        """Parse tool call patterns and execute them, returning list of result strings."""
        if permission_level == "none":
            return []
        # 空リスト = 全ツール許可
        pattern = r"(\w+)\s*\(\s*([^)]*)\s*\)"
        seen_signatures: set[str] = set()
        results: List[str] = []
        for match in re.finditer(pattern, text):
            tool_name = match.group(1)
            args_str = match.group(2)
            sig = f"{tool_name}({args_str.strip()})"
            if sig in seen_signatures:
                continue
            seen_signatures.add(sig)
            args: Dict[str, Any] = {}
            for arg_match in re.finditer(
                r'(\w+)\s*=\s*(?:"([^"]*)"|(\d+(?:\.\d+)?)|(True|False)|(None))',
                args_str,
            ):
                key = arg_match.group(1)
                raw = arg_match.group(2)
                if raw is not None:
                    args[key] = raw
                elif arg_match.group(3) is not None:
                    raw_num = arg_match.group(3)
                    args[key] = int(raw_num) if "." not in raw_num else float(raw_num)
                elif arg_match.group(4) is not None:
                    args[key] = arg_match.group(4) == "True"
                elif arg_match.group(5) is not None:
                    args[key] = None
            try:
                from . import _RUNNERS as tool_runners

                runner = tool_runners.get(tool_name)
                if runner:
                    result = runner(args)
                    results.append(f"[tool:{tool_name}]\n{result}")
                else:
                    results.append(f"[tool:{tool_name} error: runner not found]")
            except Exception as exc:
                results.append(f"[tool:{tool_name} error: {exc}]")
        return results

    def _parse_and_execute_tools(self, text: str, permission_level: str) -> str:
        """Single-turn tool execution: append results to original text."""
        results = self._execute_tool_calls(text, permission_level)
        if results:
            return text + "\n\n---\nツール実行結果:\n" + "\n\n".join(results)
        return text

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------

    def _build_structured_prompt(
        self,
        base_prompt: str,
        response_mode: Optional[str],
        response_schema: Optional[Dict[str, Any]],
        required_fields: Optional[List[str]],
        strict_output: bool,
        evidence_required: bool,
        evidence_min_items: int,
    ) -> str:
        parts = [base_prompt]
        if response_mode:
            parts.append("\n\nresponse_mode: " + response_mode)
        if response_schema:
            parts.append(
                "\n\nresponse_schema:\n"
                + json.dumps(response_schema, ensure_ascii=False, indent=2)
            )
        if required_fields:
            parts.append("\n\nrequired_fields: " + ", ".join(required_fields))
        if strict_output:
            parts.append("\n\nstrict_output: true")
        if evidence_required:
            parts.append(
                f"\n\nevidence_required: true (min_items={evidence_min_items})"
            )
        return "".join(parts)

    def _validate_structured_output(
        self,
        result_obj: Dict[str, Any],
        required_fields: Optional[List[str]],
        strict_output: bool,
        evidence_required: bool,
        evidence_min_items: int,
    ) -> Optional[str]:
        if required_fields:
            missing = [f for f in required_fields if f not in result_obj]
            if missing and strict_output:
                return f"Missing required fields: {', '.join(missing)}"
        if evidence_required:
            evidence = result_obj.get("evidence")
            if not isinstance(evidence, list) or len(evidence) < evidence_min_items:
                return f"Evidence must contain at least {evidence_min_items} items."
        return None

    def _wrap_error(self, message: str) -> str:
        return json.dumps({"status": "error", "message": message}, ensure_ascii=False)

    def _load_current_file_snippets(
        self,
        current_file: Optional[str],
        *,
        max_chars: int = 20000,
    ) -> List[str]:
        if not current_file:
            return []
        try:
            text = Path(current_file).read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            return [
                f"current_file: {current_file}",
                f"[failed to read file: {exc}]",
            ]
        if len(text) > max_chars:
            text = text[:max_chars] + "\n...[truncated]"
        return [
            f"current_file: {current_file}\n{text}",
        ]

    def _build_user_prompt(
        self,
        task_text: str,
        context_pack: ContextPack,
        scope_files: List[str],
    ) -> str:
        parts = [task_text.strip(), "[context_pack]\n" + context_pack.to_json()]
        if scope_files:
            parts.append(
                "[scope_files]\n" + "\n".join(f"- {path}" for path in scope_files)
            )
        return "\n\n".join(part for part in parts if part)

    # ------------------------------------------------------------------
    # LLM call
    # ------------------------------------------------------------------

    def _call_llm_single_round(
        self,
        provider: str,
        client: Any,
        model_name: str,
        system_prompt: str,
        user_prompt: str,
        timeout: int = 120,
    ) -> tuple[str, Dict[str, int]]:
        max_tokens = 4000
        try:
            from uagent.llmcapa_util import clamp_max_tokens

            max_tokens = clamp_max_tokens(max_tokens, model_name, provider)
        except Exception:
            pass

        if provider in ("gemini", "vertexai"):
            from google.genai import types as gemini_types

            config_kw: Dict[str, Any] = dict(
                system_instruction=system_prompt,
                temperature=0.2,
                max_output_tokens=max_tokens,
            )
            if timeout > 0:
                config_kw["timeout"] = timeout
            response = client.models.generate_content(
                model=model_name,
                contents=user_prompt,
                config=gemini_types.GenerateContentConfig(**config_kw),
            )
            usage: Dict[str, int] = {}
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                meta = response.usage_metadata
                pt = getattr(meta, "prompt_token_count", 0) or 0
                ct = getattr(meta, "candidates_token_count", 0) or 0
                usage = {
                    "prompt_tokens": pt,
                    "completion_tokens": ct,
                    "total_tokens": pt + ct,
                }
            return (response.text or "", usage)

        elif provider == "claude":
            kwargs: Dict[str, Any] = dict(
                model=model_name,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=0.2,
            )
            if timeout > 0:
                kwargs["timeout"] = timeout
            response = client.messages.create(**kwargs)
            usage: Dict[str, int] = {}
            if hasattr(response, "usage") and response.usage:
                it = getattr(response.usage, "input_tokens", 0) or 0
                ot = getattr(response.usage, "output_tokens", 0) or 0
                usage = {
                    "prompt_tokens": it,
                    "completion_tokens": ot,
                    "total_tokens": it + ot,
                }
            return (response.content[0].text or "", usage)

        else:
            kwargs: Dict[str, Any] = dict(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=max_tokens,
            )
            if timeout > 0:
                kwargs["timeout"] = timeout
            response = client.chat.completions.create(**kwargs)
            usage: Dict[str, int] = {}
            if hasattr(response, "usage") and response.usage:
                usage = {
                    "prompt_tokens": getattr(response.usage, "prompt_tokens", 0) or 0,
                    "completion_tokens": getattr(response.usage, "completion_tokens", 0)
                    or 0,
                    "total_tokens": getattr(response.usage, "total_tokens", 0) or 0,
                }
            return (response.choices[0].message.content or "", usage)

    # ------------------------------------------------------------------
    # メイン実行
    # ------------------------------------------------------------------

    def run(
        self,
        agent_name: str,
        task_text: str,
        current_file: Optional[str] = None,
        response_mode: Optional[str] = None,
        response_schema: Optional[Dict[str, Any]] = None,
        required_fields: Optional[List[str]] = None,
        strict_output: bool = False,
        evidence_required: bool = False,
        evidence_min_items: int = 0,
        permission_level: str = "none",
        cache_ttl: int = 0,
        store_key: Optional[str] = None,
        load_keys: Optional[List[str]] = None,
        parent_goal: Optional[str] = None,
        timeout: int = 120,
        max_retries: int = 2,
        max_turns: int = 3,
    ) -> str:
        spec = self.specs.get(agent_name)
        if not spec:
            result = json.dumps(
                {"status": "error", "message": f"Agent {agent_name} not found."},
                ensure_ascii=False,
            )
            self._write_log(agent_name, None, result, "error")
            return result

        if current_file and not os.path.isfile(current_file):
            result = json.dumps(
                {
                    "status": "error",
                    "message": f"Access Denied: File '{current_file}' not found.",
                },
                ensure_ascii=False,
            )
            self._write_log(agent_name, None, result, "error")
            return result

        goal = parent_goal or task_text
        pack = ContextPack(
            current_goal=goal,
            current_state="PROCESSING",
            constraints=[
                "副作用のある直接操作は禁止",
                "JSONフォーマットでの確実な返却",
            ],
            relevant_snippets=self._load_current_file_snippets(current_file),
        )

        if load_keys:
            with self._store_lock:
                for key in load_keys:
                    if key in self._shared_store:
                        pack.shared_context[key] = self._shared_store[key]

        task = SubAgentTask(
            run_id="run_" + hashlib.md5(task_text.encode("utf-8")).hexdigest()[:10],
            task_id="task_01",
            agent_name=agent_name,
            parent_goal=goal,
            task=task_text,
            context_pack=pack,
            scope_files=[current_file] if current_file else [],
        )

        with _SUB_AGENT_ENV_LOCK:
            if not self.duplicate_guard.check_and_record(agent_name, task):
                result = json.dumps(
                    {
                        "status": "blocked",
                        "message": f"Duplicate call blocked for agent: {agent_name} with same arguments.",
                    },
                    ensure_ascii=False,
                )
                self._write_log(agent_name, task, result, "blocked")
                return result

        if cache_ttl > 0:
            cached = self.duplicate_guard.get_cached(agent_name, task)
            if cached is not None:
                self._write_log(agent_name, task, cached, "cache_hit")
                return cached

        if agent_name in self._call_chain:
            result = json.dumps(
                {
                    "status": "error",
                    "message": f"Circular sub-agent call detected: {agent_name} is already in the call chain.",
                },
                ensure_ascii=False,
            )
            self._write_log(agent_name, task, result, "error")
            return result

        self._call_chain.append(agent_name)
        try:
            result, llm_usage, total_retries = self._run_llm(
                agent_name=agent_name,
                spec=spec,
                task=task,
                pack=pack,
                response_mode=response_mode,
                response_schema=response_schema,
                required_fields=required_fields,
                strict_output=strict_output,
                evidence_required=evidence_required,
                evidence_min_items=evidence_min_items,
                permission_level=permission_level,
                cache_ttl=cache_ttl,
                store_key=store_key,
                timeout=timeout,
                max_retries=max_retries,
                max_turns=max_turns,
            )
            status = self._infer_status(result)
            self._write_log(
                agent_name, task, result, status, retries=total_retries, usage=llm_usage
            )
            return result
        finally:
            self._call_chain.pop()

    def _run_llm(
        self,
        agent_name: str,
        spec: AgentSpec,
        task: SubAgentTask,
        pack: ContextPack,
        response_mode: Optional[str],
        response_schema: Optional[Dict[str, Any]],
        required_fields: Optional[List[str]],
        strict_output: bool,
        evidence_required: bool,
        evidence_min_items: int,
        permission_level: str,
        cache_ttl: int,
        store_key: Optional[str],
        timeout: int,
        max_retries: int,
        max_turns: int = 3,
    ) -> tuple[str, Dict[str, int], int]:
        cb = get_callbacks()
        agent_upper = agent_name.upper()
        sub_provider = (
            (
                env_get(f"UAGENT_SUB_AGENT_{agent_upper}_PROVIDER")
                or env_get("UAGENT_SUB_AGENT_PROVIDER")
                or ""
            )
            .strip()
            .lower()
        )
        sub_depname = (
            env_get(f"UAGENT_SUB_AGENT_{agent_upper}_DEPNAME")
            or env_get("UAGENT_SUB_AGENT_DEPNAME")
            or ""
        ).strip()
        sub_api_key = (
            env_get(f"UAGENT_SUB_AGENT_{agent_upper}_API_KEY")
            or env_get("UAGENT_SUB_AGENT_API_KEY")
            or ""
        ).strip()

        try:
            if sub_provider:
                with _SUB_AGENT_ENV_LOCK:
                    orig_provider = os.environ.get("UAGENT_PROVIDER")
                    os.environ["UAGENT_PROVIDER"] = sub_provider
                    orig_depname = None
                    orig_api_key = None
                    p_upper = sub_provider.upper()
                    dep_key = f"UAGENT_{p_upper}_DEPNAME"
                    key_key = f"UAGENT_{p_upper}_API_KEY"
                    if sub_depname:
                        orig_depname = os.environ.get(dep_key)
                        os.environ[dep_key] = sub_depname
                    if sub_api_key:
                        orig_api_key = os.environ.get(key_key)
                        os.environ[key_key] = sub_api_key
                    try:
                        provider, client, model_name = make_client(cb)
                    finally:
                        if orig_provider is not None:
                            os.environ["UAGENT_PROVIDER"] = orig_provider
                        else:
                            os.environ.pop("UAGENT_PROVIDER", None)
                        if sub_depname:
                            if orig_depname is not None:
                                os.environ[dep_key] = orig_depname
                            else:
                                os.environ.pop(dep_key, None)
                        if sub_api_key:
                            if orig_api_key is not None:
                                os.environ[key_key] = orig_api_key
                            else:
                                os.environ.pop(key_key, None)
            else:
                provider, client, model_name = make_client(cb)
        except Exception as exc:
            return (
                json.dumps(
                    {"status": "error", "message": f"Failed to create client: {exc}"},
                    ensure_ascii=False,
                ),
                {},
                0,
            )

        if response_mode is None:
            if spec.default_response_mode:
                response_mode = spec.default_response_mode
            else:
                response_mode = "json" if spec.name != "summarizer" else "text"

        if required_fields is None and spec.default_required_fields:
            required_fields = list(spec.default_required_fields)

        # --- System prompt 構築 ---
        base_prompt = spec.system_prompt
        if permission_level != "none":
            base_prompt += self._build_tool_list_prompt(permission_level)

        if max_turns > 1 and permission_level != "none":
            base_prompt += (
                f"\n\nあなたは最大{max_turns}ターンまで会話を続けられます。"
                "ツールを使って情報を集めた後、最終ターンではツール呼び出しを含めずに最終回答だけを出力してください。"
                "各ターンでは、前のターンの出力とツール結果が「会話履歴」として追記されます。"
            )

        if response_mode == "json":
            system_prompt = self._build_structured_prompt(
                base_prompt,
                response_mode,
                response_schema,
                required_fields,
                strict_output,
                evidence_required,
                evidence_min_items,
            )
        else:
            system_prompt = base_prompt

        user_prompt = self._build_user_prompt(task.task, pack, task.scope_files)

        if cb and getattr(cb, "log_message", None):
            try:
                cb.log_message(
                    {
                        "role": "assistant",
                        "content": f"[Sub-Agent: {agent_name}] 処理を開始します...\nタスク: {task.task}",
                    }
                )
            except Exception:
                pass

        # --- マルチターン or シングルターン ---
        if max_turns > 1 and permission_level != "none":
            raw_output, total_retries, llm_usage = self._run_llm_multi_turn(
                cb=cb,
                provider=provider,
                client=client,
                model_name=model_name,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                timeout=timeout,
                max_retries=max_retries,
                response_mode=response_mode or "",
                permission_level=permission_level,
                max_turns=max_turns,
            )
        else:
            raw_output, total_retries, llm_usage = self._call_with_retry(
                provider=provider,
                client=client,
                model_name=model_name,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                timeout=timeout,
                max_retries=max_retries,
                response_mode=response_mode or "",
            )
            if permission_level != "none":
                raw_output = self._parse_and_execute_tools(raw_output, permission_level)

        self._accumulate_usage(llm_usage)
        llm_usage = self._usage_with_cost(
            llm_usage, provider=provider, model_name=model_name
        )

        if cb and getattr(cb, "log_message", None):
            try:
                cb.log_message(
                    {
                        "role": "assistant",
                        "content": f"[Sub-Agent: {agent_name}] 処理が完了しました。\n結果:\n{raw_output}",
                    }
                )
            except Exception:
                pass

        # --- 出力検証 ---
        if response_mode == "json":
            try:
                result_obj = json.loads(raw_output)
            except Exception as exc:
                return (
                    self._wrap_error(f"Invalid JSON output: {exc}"),
                    llm_usage,
                    total_retries,
                )
            validation_error = self._validate_structured_output(
                result_obj,
                required_fields,
                strict_output,
                evidence_required,
                evidence_min_items,
            )
            if validation_error:
                return (self._wrap_error(validation_error), llm_usage, total_retries)
            result_str = json.dumps(result_obj, ensure_ascii=False)
        else:
            result_str = raw_output

        if store_key:
            with self._store_lock:
                self._shared_store[store_key] = result_str

        if cache_ttl > 0:
            self.duplicate_guard.store_cache(agent_name, task, result_str)

        return (result_str, llm_usage, total_retries)

    # ------------------------------------------------------------------
    # マルチターン実行
    # ------------------------------------------------------------------

    def _run_llm_multi_turn(
        self,
        cb: Any,
        provider: str,
        client: Any,
        model_name: str,
        system_prompt: str,
        user_prompt: str,
        timeout: int,
        max_retries: int,
        response_mode: str,
        permission_level: str,
        max_turns: int,
    ) -> tuple[str, int, Dict[str, int]]:
        """マルチターンLLM実行。ツール呼び出しを複数ラウンドにわたって処理する。"""

        conversation = user_prompt
        total_retries = 0
        total_usage: Dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        last_raw = ""

        for turn in range(max_turns):
            is_last = turn == max_turns - 1

            if cb and getattr(cb, "log_message", None) and not is_last:
                try:
                    cb.log_message(
                        {
                            "role": "assistant",
                            "content": f"[Sub-Agent] Turn {turn + 1}/{max_turns} - ツール実行結果を反映して次のターンに進みます。",
                        }
                    )
                except Exception:
                    pass

            # 最終ターン以外はJSONバリデーションをスキップ（中間出力はツール呼び出しの可能性）
            current_response_mode = response_mode if is_last else ""

            raw, retries, usage = self._call_with_retry(
                provider,
                client,
                model_name,
                system_prompt,
                conversation,
                timeout,
                max_retries,
                current_response_mode,
            )
            total_retries += retries
            for k in total_usage:
                total_usage[k] += usage.get(k, 0)

            last_raw = raw

            # 最終ターン → そのまま返す
            if is_last:
                return raw, total_retries, total_usage

            # 会話履歴に追記
            conversation += f"\n\n[Your Response Turn {turn + 1}]:\n{raw}\n"

            # ツール呼び出しをパースして実行
            tool_results = self._execute_tool_calls(raw, permission_level)
            if tool_results:
                for tr in tool_results:
                    conversation += f"\n{tr}\n"
                continue  # 次のターンへ

            # ツール呼び出しがない → これが最終回答
            return raw, total_retries, total_usage

        return last_raw, total_retries, total_usage

    def _call_with_retry(
        self,
        provider: str,
        client: Any,
        model_name: str,
        system_prompt: str,
        user_prompt: str,
        timeout: int,
        max_retries: int,
        response_mode: str,
    ) -> tuple[str, int, Dict[str, int]]:
        import time

        last_error = ""
        total_retries = 0
        total_usage: Dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        for attempt in range(max_retries + 1):
            try:
                raw, usage = self._call_llm_single_round(
                    provider,
                    client,
                    model_name,
                    system_prompt,
                    user_prompt,
                    timeout,
                )
                for k in total_usage:
                    total_usage[k] += usage.get(k, 0)
                if response_mode == "json":
                    try:
                        json.loads(raw)
                    except json.JSONDecodeError:
                        if attempt < max_retries:
                            total_retries += 1
                            last_error = f"Invalid JSON on attempt {attempt + 1}"
                            system_prompt += "\n\n[前回の出力はJSON形式ではありませんでした。必ず有効なJSONのみを出力してください。]"
                            time.sleep(1)
                            continue
                return raw, total_retries, total_usage
            except Exception as exc:
                last_error = str(exc)
                if attempt < max_retries:
                    total_retries += 1
                    time.sleep(2**attempt)
                    continue
                break
        return (
            self._wrap_error(
                f"LLM call failed after {max_retries + 1} attempts: {last_error}"
            ),
            total_retries,
            total_usage,
        )


# ---------------------------------------------------------------------------
# Module-level runner instance
# ---------------------------------------------------------------------------

_runner = SubAgentRunner()


def run_tool(args: Dict[str, Any]) -> str:
    cb = get_callbacks()
    agent_name = args["agent_name"]
    task = args["task"]
    current_file = args.get("current_file")
    response_mode = args.get("response_mode")
    response_schema = args.get("response_schema")
    required_fields = args.get("required_fields")
    strict_output = args.get("strict_output", False)
    evidence_required = args.get("evidence_required", False)
    evidence_min_items = args.get("evidence_min_items", 0)
    permission_level = args.get("permission_level", "none")
    cache_ttl = args.get("cache_ttl", 0)
    store_key = args.get("store_key")
    load_keys = args.get("load_keys")
    parent_goal = args.get("parent_goal")
    timeout = args.get("timeout", 120)
    max_retries = args.get("max_retries", 2)
    max_turns = args.get("max_turns", 3)

    if cb and hasattr(cb, "set_status") and cb.set_status:
        cb.set_status(True, f"Sub-Agent ({agent_name})")

    # Fire SubagentStart hook
    try:
        from uagent.hooks_engine import (
            get_default_registry_path,
            load_hooks_registry,
            fire_event,
        )

        _hooks = load_hooks_registry(get_default_registry_path())
        if _hooks:
            fire_event("SubagentStart", _hooks)
    except Exception:
        pass

    try:
        result = _runner.run(
            agent_name,
            task,
            current_file,
            response_mode=response_mode,
            response_schema=response_schema,
            required_fields=required_fields,
            strict_output=strict_output,
            evidence_required=evidence_required,
            evidence_min_items=evidence_min_items,
            permission_level=permission_level,
            cache_ttl=cache_ttl,
            store_key=store_key,
            load_keys=load_keys,
            parent_goal=parent_goal,
            timeout=timeout,
            max_retries=max_retries,
            max_turns=max_turns,
        )
    finally:
        if cb and hasattr(cb, "set_status") and cb.set_status:
            cb.set_status(False, "")
            cb.set_status(False, "")

    # Fire SubagentStop hook
    try:
        from uagent.hooks_engine import (
            get_default_registry_path,
            load_hooks_registry,
            fire_event,
        )

        _hooks = load_hooks_registry(get_default_registry_path())
        if _hooks:
            fire_event("SubagentStop", _hooks)
    except Exception:
        pass

    return result
