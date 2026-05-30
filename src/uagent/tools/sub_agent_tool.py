"""Sub-Agent Tool Plugin for uag
親エージェントの制御下で動作する安全な専門サブエージェントを実行します。
本体のコアシステムをインポートせず、util_providers.py のクライアント生成ユーティリティのみを介して動作します。
"""

from __future__ import annotations
import dataclasses
import hashlib
import json
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .context import get_callbacks
from ..env_utils import env_get
from ..util_providers import make_client
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True


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


TOOL_SPEC: Dict[str, Any] = {
    "load_order": 50,
    "type": "function",
    "function": {
        "name": "run_sub_agent",
        "description": _(
            "tool.description",
            default=(
                "Execute a specialized, safe sub-agent (planner, reviewer, summarizer, patch_designer, or error_analyst) "
                "under the control of the parent orchestrator to process specific tasks and return structured findings."
            ),
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "Run a specialized sub-agent (planner, reviewer, summarizer, patch_designer, or error_analyst) to solve a task. "
                "This sub-agent does not make destructive modifications. It returns structured insights as JSON."
            ),
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
                "orchestrate",
                "patch",
                "error analysis",
                "debugging",
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
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "enum": [
                        "planner",
                        "reviewer",
                        "summarizer",
                        "patch_designer",
                        "error_analyst",
                    ],
                    "description": _(
                        "param.agent_name.description",
                        default="The name of the specialized sub-agent to run.",
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
            },
            "required": ["agent_name", "task"],
            "additionalProperties": False,
        },
    },
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
                    "実際のファイル書き換えやコマンド実行はせず、成果となる計画JSON（構造化データ）のみを出力してください。\n"
                    "必ず以下のJSONフォーマットで回答してください。余計な前置きや説明は含めず、純粋なJSONのみを出力してください。\n"
                    "{\n"
                    '  "status": "completed",\n'
                    '  "summary": "計画の概要",\n'
                    '  "findings": [\n'
                    "    {\n"
                    '      "severity": "low/medium/high",\n'
                    '      "title": "リスクや注意点",\n'
                    '      "detail": "詳細な説明",\n'
                    '      "recommendation": "推奨される対処"\n'
                    "    }\n"
                    "  ],\n"
                    '  "proposed_actions": ["ステップ1", "ステップ2"]\n'
                    "}"
                ),
            ),
            "reviewer": AgentSpec(
                name="reviewer",
                description="監査レビューエージェント",
                permission_level=PermissionLevel.READ_ONLY,
                allowed_tools=["read_file"],
                system_prompt=(
                    "あなたはコード、設計、修正提案を検証するレビュー専門サブエージェントです。\n"
                    "不具合、仕様不一致、セキュリティ、無限ループリスクを特定し、指摘として構造化して出力してください。\n"
                    "必ず以下のJSONフォーマットで回答してください。余計な前置きや説明は含めず、純粋なJSONのみを出力してください。\n"
                    "{\n"
                    '  "status": "completed",\n'
                    '  "summary": "レビューの概要",\n'
                    '  "findings": [\n'
                    "    {\n"
                    '      "severity": "low/medium/high",\n'
                    '      "title": "バグや問題点",\n'
                    '      "detail": "問題の詳細",\n'
                    '      "recommendation": "推奨される修正案"\n'
                    "    }\n"
                    "  ],\n"
                    '  "proposed_actions": ["修正手順やアドバイス"]\n'
                    "}"
                ),
            ),
            "summarizer": AgentSpec(
                name="summarizer",
                description="情報圧縮エージェント",
                permission_level=PermissionLevel.NONE,
                system_prompt=(
                    "あなたは情報要約の専門サブエージェントです。長い履歴やログから、\n"
                    "次のLLM処理に必要不可欠なコアデータ、決定事項、直近のエラーのみをコンパクトに抽出してください。\n"
                    "必ず以下のJSONフォーマットで回答してください。余計な前置きや説明は含めず、純粋なJSONのみを出力してください。\n"
                    "{\n"
                    '  "status": "completed",\n'
                    '  "summary": "要約の概要",\n'
                    '  "findings": [\n'
                    "    {\n"
                    '      "severity": "info/low",\n'
                    '      "title": "重要トピック",\n'
                    '      "detail": "トピックの詳細",\n'
                    '      "recommendation": "特記事項や次のアクション"\n'
                    "    }\n"
                    "  ],\n"
                    '  "proposed_actions": ["推奨する要約ポイント"]\n'
                    "}"
                ),
            ),
            "patch_designer": AgentSpec(
                name="patch_designer",
                description="修正パッチ設計エージェント",
                permission_level=PermissionLevel.PROPOSE_ONLY,
                system_prompt=(
                    "あなたは修正パッチ設計の専門サブエージェントです。プログラムコード、エラーログ、不具合、またはレビュー指摘を基に、安全かつ具体的な修正差分（パッチ案）を設計してください。\n"
                    "実際のファイル書き換えやコマンド実行はせず、成果となる計画・修正パッチJSON（構造化データ）のみを出力してください。\n"
                    "必ず以下のJSONフォーマットで回答してください。余計な前置きや説明は含めず、純粋なJSONのみを出力してください。\n"
                    "{\n"
                    '  "status": "completed",\n'
                    '  "summary": "パッチ設計の概要（どのような修正を行うか）",\n'
                    '  "findings": [\n'
                    "    {\n"
                    '      "severity": "low/medium/high",\n'
                    '      "title": "修正対象ファイルと箇所",\n'
                    '      "detail": "修正方針や具体的な置換元・置換先コード、もしくは差分（diff形式など）の説明",\n'
                    '      "recommendation": "適用時の注意点や、適用後に実行すべきテスト/検証コマンド"\n'
                    "    }\n"
                    "  ],\n"
                    '  "proposed_actions": ["修正パッチを適用するファイルパスとその変更詳細指示"]\n'
                    "}"
                ),
            ),
            "error_analyst": AgentSpec(
                name="error_analyst",
                description="エラー解析・デバッグエージェント",
                permission_level=PermissionLevel.READ_ONLY,
                allowed_tools=["read_file"],
                system_prompt=(
                    "あなたはエラー解析・デバッグの専門サブエージェントです。プログラムコード、テストエラー、コンパイルエラー、またはシステムログを基に、エラーの根本原因（Root Cause）を特定してください。\n"
                    "実際のファイル書き換えやコマンド実行はせず、成果となるエラー解析JSON（構造化データ）のみを出力してください。\n"
                    "必ず以下のJSONフォーマットで回答してください。余計な前置きや説明は含めず、純粋なJSONのみを出力してください。\n"
                    "{\n"
                    '  "status": "completed",\n'
                    '  "summary": "エラー解析の概要（何が原因でエラーが発生したか）",\n'
                    '  "findings": [\n'
                    "    {\n"
                    '      "severity": "low/medium/high",\n'
                    '      "title": "エラーの根本原因とエラー箇所",\n'
                    '      "detail": "問題の詳細（例外クラス、エラーメッセージ、原因コードの説明など）",\n'
                    '      "recommendation": "具体的な修正アクション（修正コード案や対策）"\n'
                    "    }\n"
                    "  ],\n"
                    '  "proposed_actions": ["エラーを解決するために必要なステップ一覧"]\n'
                    "}"
                ),
            ),
        }

    def _call_llm_single_round(
        self,
        provider: str,
        client: Any,
        model_name: str,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """各種プロバイダに対応した安全でシンプルな1往復のLLM生成処理"""
        if provider in ("gemini", "vertexai"):
            from google.genai import types as gemini_types

            response = client.models.generate_content(
                model=model_name,
                contents=user_prompt,
                config=gemini_types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.2,
                ),
            )
            return response.text or ""

        elif provider == "claude":
            response = client.messages.create(
                model=model_name,
                max_tokens=4000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=0.2,
            )
            return response.content[0].text or ""

        else:
            # OpenAI, Azure, Grok, Bedrock, Ollama, OpenRouter, Nvidia, etc.
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
            )
            return response.choices[0].message.content or ""

    def run(
        self, agent_name: str, task_text: str, current_file: Optional[str] = None
    ) -> str:
        spec = self.specs.get(agent_name)
        if not spec:
            return json.dumps(
                {"status": "error", "message": f"Agent {agent_name} not found."}
            )

        # ガードレール: ファイルピン留めの検証
        if current_file and not os.path.exists(current_file):
            return json.dumps(
                {
                    "status": "error",
                    "message": f"Access Denied: File '{current_file}' not found.",
                }
            )

        # ContextPack の構築
        pack = ContextPack(
            current_goal=task_text,
            current_state="PROCESSING",
            constraints=[
                "副作用のある直接操作は禁止",
                "JSONフォーマットでの確実な返却",
            ],
        )

        task = SubAgentTask(
            run_id="run_" + hashlib.md5(task_text.encode("utf-8")).hexdigest()[:10],
            task_id="task_01",
            agent_name=agent_name,
            parent_goal="サブエージェント連携の実行",
            task=task_text,
            context_pack=pack,
            scope_files=[current_file] if current_file else [],
        )

        # 重複チェック
        if not self.duplicate_guard.check_and_record(agent_name, task):
            return json.dumps(
                {
                    "status": "blocked",
                    "message": f"Duplicate call blocked for agent: {agent_name} with same arguments.",
                },
                ensure_ascii=False,
            )

        # コールバック経由で環境変数等の情報を安全に取得
        cb = get_callbacks()

        # Resolve sub-agent specific overrides from environment variables
        # Format: UAGENT_SUB_AGENT_<AGENT_NAME>_PROVIDER / _DEPNAME / _API_KEY
        # Fallback: UAGENT_SUB_AGENT_PROVIDER / _DEPNAME / _API_KEY
        # Default: Main agent configuration (via make_client)
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

        # util_providers から安全にクライアントを取得
        try:
            if sub_provider:
                # Temporarily override environment variables to let make_client build the custom client
                orig_provider = os.environ.get("UAGENT_PROVIDER")
                os.environ["UAGENT_PROVIDER"] = sub_provider

                # Setup provider-specific overrides
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
                    # Restore original environment variables
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
                # No provider override, but check if there's a model/key override for the default provider
                provider, client, model_name = make_client(cb)
                p_upper = provider.upper()
                dep_key = f"UAGENT_{p_upper}_DEPNAME"
                key_key = f"UAGENT_{p_upper}_API_KEY"

                if sub_depname or sub_api_key:
                    orig_depname = os.environ.get(dep_key)
                    orig_api_key = os.environ.get(key_key)

                    if sub_depname:
                        os.environ[dep_key] = sub_depname
                    if sub_api_key:
                        os.environ[key_key] = sub_api_key

                    try:
                        # Re-create client with overridden model/key
                        provider, client, model_name = make_client(cb)
                    finally:
                        if orig_depname is not None:
                            os.environ[dep_key] = orig_depname
                        else:
                            os.environ.pop(dep_key, None)
                        if orig_api_key is not None:
                            os.environ[key_key] = orig_api_key
                        else:
                            os.environ.pop(key_key, None)
        except Exception as e:
            return json.dumps(
                {
                    "status": "error",
                    "message": f"Failed to initialize LLM client: {str(e)}",
                },
                ensure_ascii=False,
            )

        # ターゲットファイルの追加コンテキスト読込（reviewer用など）
        relevant_snippets = []
        if current_file and spec.permission_level == PermissionLevel.READ_ONLY:
            try:
                with open(current_file, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(10000)  # 最大10KB読み込み
                    relevant_snippets.append(
                        f"--- FILE: {current_file} ---\n{content}\n--- END ---"
                    )
            except Exception as e:
                relevant_snippets.append(f"Failed to read pinned file: {str(e)}")

        pack.relevant_snippets = relevant_snippets

        user_prompt = (
            f"以下はあなたに依頼する業務の詳細情報です。\n\n"
            f"【タスク】\n{task_text}\n\n"
            f"【文脈パック】\n{pack.to_json()}"
        )

        try:
            raw_response = self._call_llm_single_round(
                provider=provider,
                client=client,
                model_name=model_name,
                system_prompt=spec.system_prompt,
                user_prompt=user_prompt,
            )

            # JSONクリーンアップ（```json ... ``` のブロックがあれば中身だけを取り出す）
            cleaned = raw_response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                cleaned = "\n".join(lines).strip()

            # JSONパース確認
            try:
                parsed_json = json.loads(cleaned)
                return json.dumps(parsed_json, ensure_ascii=False, indent=2)
            except json.JSONDecodeError:
                # パース失敗時はフォールバックJSONを返す
                return json.dumps(
                    {
                        "status": "completed",
                        "summary": "サブエージェント応答のパースに失敗しましたが、テキスト出力を回収しました。",
                        "findings": [
                            {
                                "severity": "high",
                                "title": "JSONパースエラー",
                                "detail": "LLMの応答が有効なJSONフォーマットではありませんでした。",
                                "recommendation": "テキスト出力を直接確認してください。",
                            }
                        ],
                        "proposed_actions": [],
                        "raw_text": raw_response,
                    },
                    ensure_ascii=False,
                    indent=2,
                )

        except Exception as e:
            return json.dumps(
                {"status": "error", "message": f"LLM execution error: {str(e)}"},
                ensure_ascii=False,
            )


_runner = SubAgentRunner()


def run_tool(args: Dict[str, Any]) -> str:
    cb = get_callbacks()
    agent_name = args["agent_name"]
    task = args["task"]
    current_file = args.get("current_file")

    if cb and hasattr(cb, "set_status") and cb.set_status:
        cb.set_status(True, f"Sub-Agent ({agent_name})")

    try:
        return _runner.run(agent_name, task, current_file)
    finally:
        if cb and hasattr(cb, "set_status") and cb.set_status:
            cb.set_status(False, "")
