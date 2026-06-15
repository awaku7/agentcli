"""Sub-Agent Tool Plugin for uag
親エージェントの制御下で動作する安全な専門サブエージェントを実行します。
本体のコアシステムをインポートせず、util_providers.py のクライアント生成ユーティリティのみを介して動作します。
"""

from __future__ import annotations
import dataclasses
import hashlib
import json
import os
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .context import get_callbacks
from ..env_utils import env_get
from ..providers.util_providers import make_client
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
            default="Execute a specialized, safe sub-agent (planner, reviewer, summarizer, patch_designer, error_analyst, or translator) under the control of the parent...",
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
            "translator",
            "translation",
            "localization",
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
                        "translator",
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
                    "あなたは計画作成に特化したサブエージェントです。"
                    "入力を分析し、実行可能な計画を日本語で簡潔に出力してください。"
                    "出力は必ずJSONで、status, role, summary, assumptions, risks, next_actions を含めてください。"
                    "事実と推測を分け、曖昧な点があれば assumptions に明記してください。"
                ),
            ),
            "reviewer": AgentSpec(
                name="reviewer",
                description="レビューエージェント",
                permission_level=PermissionLevel.NONE,
                system_prompt=(
                    "あなたはレビューに特化したサブエージェントです。"
                    "入力の妥当性、欠落、リスク、改善点を検査し、JSONで返してください。"
                    "出力は status, role, summary, findings, risks, recommended_actions を含めてください。"
                ),
            ),
            "summarizer": AgentSpec(
                name="summarizer",
                description="要約エージェント",
                permission_level=PermissionLevel.NONE,
                system_prompt=(
                    "あなたは要約に特化したサブエージェントです。"
                    "入力を短く正確に要約し、JSONで返してください。"
                    "出力は status, role, summary, key_points, open_questions を含めてください。"
                ),
            ),
            "patch_designer": AgentSpec(
                name="patch_designer",
                description="パッチ設計エージェント",
                permission_level=PermissionLevel.NONE,
                system_prompt=(
                    "あなたは変更差分の設計に特化したサブエージェントです。"
                    "安全で最小限の変更案をJSONで返してください。"
                    "出力は status, role, summary, files, changes, risks, validation_steps を含めてください。"
                ),
            ),
            "error_analyst": AgentSpec(
                name="error_analyst",
                description="エラー分析エージェント",
                permission_level=PermissionLevel.NONE,
                system_prompt=(
                    "あなたはエラー分析に特化したサブエージェントです。"
                    "原因の切り分け、再現条件、対処案をJSONで返してください。"
                    "出力は status, role, summary, root_cause, evidence, proposed_actions を含めてください。"
                ),
            ),
            "translator": AgentSpec(
                name="translator",
                description="翻訳・ローカライズエージェント",
                permission_level=PermissionLevel.NONE,
                system_prompt=(
                    "You are a specialized sub-agent for translation and localization. "
                    "Accurately translate the provided text, document, or PO (gettext) file into the specified target language. "
                    "You must strictly preserve technical terms, context, placeholders (e.g., {path}, %(err)s, %s, etc.), newline characters, and formatting. "
                    "The output must be a JSON object containing: status, role, summary, translated_text, and notes."
                ),
            ),
        }

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
    ) -> str:
        spec = self.specs.get(agent_name)
        if not spec:
            return json.dumps(
                {"status": "error", "message": f"Agent {agent_name} not found."},
                ensure_ascii=False,
            )

        if current_file and not os.path.isfile(current_file):
            return json.dumps(
                {
                    "status": "error",
                    "message": f"Access Denied: File '{current_file}' not found.",
                },
                ensure_ascii=False,
            )

        pack = ContextPack(
            current_goal=task_text,
            current_state="PROCESSING",
            constraints=[
                "副作用のある直接操作は禁止",
                "JSONフォーマットでの確実な返却",
            ],
            relevant_snippets=self._load_current_file_snippets(current_file),
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

        if not self.duplicate_guard.check_and_record(agent_name, task):
            return json.dumps(
                {
                    "status": "blocked",
                    "message": f"Duplicate call blocked for agent: {agent_name} with same arguments.",
                },
                ensure_ascii=False,
            )

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
            return json.dumps(
                {"status": "error", "message": f"Failed to create client: {exc}"},
                ensure_ascii=False,
            )

        if response_mode is None:
            response_mode = "json" if spec.name != "summarizer" else "text"

        if response_mode == "json":

            system_prompt = self._build_structured_prompt(
                spec.system_prompt,
                response_mode=response_mode,
                response_schema=response_schema,
                required_fields=required_fields,
                strict_output=strict_output,
                evidence_required=evidence_required,
                evidence_min_items=evidence_min_items,
            )
        else:
            system_prompt = spec.system_prompt

        user_prompt = self._build_user_prompt(task_text, pack, task.scope_files)

        # UIにサブエージェントの開始を通知
        if cb and getattr(cb, "log_message", None):
            try:
                cb.log_message(
                    {
                        "role": "assistant",
                        "content": f"[Sub-Agent: {agent_name}] 処理を開始します...\nタスク: {task_text}",
                    }
                )
            except Exception:
                pass

        raw_output = self._call_llm_single_round(
            provider=provider,
            client=client,
            model_name=model_name,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        # UIにサブエージェントの完了を通知
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

        if response_mode == "json":
            try:
                result_obj = json.loads(raw_output)
            except Exception as exc:
                return self._wrap_error(f"Invalid JSON output: {exc}")
            validation_error = self._validate_structured_output(
                result_obj=result_obj,
                required_fields=required_fields,
                strict_output=strict_output,
                evidence_required=evidence_required,
                evidence_min_items=evidence_min_items,
            )
            if validation_error:
                return self._wrap_error(validation_error)
            return json.dumps(result_obj, ensure_ascii=False)

        return raw_output


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

    if cb and hasattr(cb, "set_status") and cb.set_status:
        cb.set_status(True, f"Sub-Agent ({agent_name})")

    try:
        return _runner.run(
            agent_name,
            task,
            current_file,
            response_mode=response_mode,
            response_schema=response_schema,
            required_fields=required_fields,
            strict_output=strict_output,
            evidence_required=evidence_required,
            evidence_min_items=evidence_min_items,
        )
    finally:
        if cb and hasattr(cb, "set_status") and cb.set_status:
            cb.set_status(False, "")
