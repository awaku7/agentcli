"""Sub-Agent Tool Plugin for uag
Run safe specialist sub-agents under parent-agent control.
Operate through the client-generation utilities in util_providers.py without importing the core system.
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
from ..auth.provider_credentials import get_provider_api_key
from ..env_utils import env_get
from ..providers.util_providers import make_client
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# An empty list allows all tools; the sub-agent must obtain user confirmation through human_ask.
_SUB_AGENT_TOOL_WHITELIST: Dict[str, List[str]] = {
    "none": [],
    "read_only": [],  # Empty means all tools are allowed
    "propose_only": [],  # Empty means all tools are allowed (treated the same as read_only)
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
# Duplicate-call guard and result cache
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
                description="Planning agent",
                permission_level=PermissionLevel.NONE,
                system_prompt=(
                    _(
                        "auto.6cb7e91442d0aa96",
                        default='You are a sub-agent specialized in planning. First understand the overall task, then analyze dependencies, and finally break it into executable steps.\n[Output format] Output must be JSON and strictly include these fields:\n  - status: always "completed"\n  - role: "planner"\n  - summary: Plan summary (1–2 sentences)\n  - assumptions: List of assumptions; explicitly state assumptions made due to missing information\n  - risks: List of risks and cautions\n  - next_actions: List of concrete next steps, each at an executable level\n[Edge cases] If information is insufficient, state that in assumptions and list the required additional information specifically. If the task is already complete, return an empty next_actions list.\n[Self-evaluation] Before output, check whether this plan can really complete the task; add missing items to assumptions or risks.\n[Token efficiency] Keep each field to the minimum necessary information and avoid verbose explanations.',
                    )
                ),
            ),
            "reviewer": AgentSpec(
                name="reviewer",
                description="Review agent",
                permission_level=PermissionLevel.NONE,
                system_prompt=(
                    _(
                        "auto.238f691c6304d301",
                        default='You are a sub-agent specialized in review. First understand the overall structure of the input, then inspect it across four axes—omissions, logical contradictions, risks, and opportunities for improvement—and finally report findings in priority order.\n[Output format] Strictly output JSON with:\n  - status: "completed" / "error" if the problem is fatal\n  - role: "reviewer"\n  - summary: Overall review (2–3 sentences)\n  - findings: List of discovered issues, each including severity: high/medium/low\n  - risks: Areas that may become problems in the future\n  - recommended_actions: List of proposed fixes\n[Edge cases] If there are no problems, return an empty findings list. If the input is empty or meaningless, set status to "error" and explain why in the message field.\n[Self-evaluation] For each finding, check whether it is truly a problem and not a false positive; move low-confidence items to risks.\n[Token efficiency] Group similar issues and list them in descending order of importance.',
                    )
                ),
            ),
            "summarizer": AgentSpec(
                name="summarizer",
                description="Summarization agent",
                permission_level=PermissionLevel.NONE,
                system_prompt=(
                    _(
                        "auto.da98c4c06ff99472",
                        default='You are a sub-agent specialized in summarization. First read the entire input, select information by importance, and finally output it in a structured form.\n[Output format] Strictly output JSON with:\n  - status: "completed"\n  - role: "summarizer"\n  - summary: Overall summary (1–3 sentences)\n  - key_points: List of important points, keeping each item specific and focused on one piece of information\n  - open_questions: Unresolved questions or items requiring confirmation\n[Edge cases] If the input is extremely short (such as one sentence), summary alone is sufficient and key_points may be omitted. Preserve technical terms as written.\n[Self-evaluation] Confirm that the summary accurately reflects the original intent and does not omit important information.\n[Token efficiency] Avoid verbosity; keep each key_point within 20 words.',
                    )
                ),
            ),
            "patch_designer": AgentSpec(
                name="patch_designer",
                description="Patch design agent",
                permission_level=PermissionLevel.NONE,
                system_prompt=(
                    _(
                        "auto.417eea12dad04caa",
                        default='You are a sub-agent specialized in designing code changes. First understand the current code, then design the smallest change that achieves the goal, and finally verify the scope of the change.\n[Output format] Strictly output JSON with:\n  - status: "completed"\n  - role: "patch_designer"\n  - summary: Change summary\n  - files: List of files to change\n  - changes: Specific changes for each file, clearly identifying additions, deletions, and modifications\n  - risks: Side effects and risks caused by the change\n  - validation_steps: Validation steps to run after the change\n[Edge cases] If no change is needed, set changes to an empty list and explain why in summary. If multiple approaches exist, list them in recommended order.\n[Self-evaluation] Check whether each change is truly necessary and whether a safer alternative exists.\n[Token efficiency] Explain the intent and location of changes concisely in natural language rather than unified diff format.',
                    )
                ),
            ),
            "error_analyst": AgentSpec(
                name="error_analyst",
                description="Error analysis agent",
                permission_level=PermissionLevel.NONE,
                system_prompt=(
                    _(
                        "auto.4651eaae39b1dbbb",
                        default='You are a sub-agent specialized in error analysis. First collect the error message and context, then isolate the cause (direct cause to root cause), and finally organize reproduction conditions and remedies.\n[Output format] Strictly output JSON with:\n  - status: "completed"\n  - role: "error_analyst"\n  - summary: Error summary\n  - root_cause: Explanation of the root cause\n  - evidence: List of facts supporting the judgment, such as error messages, logs, and stack traces\n  - proposed_actions: List of remedies, including concrete operating steps for each item\n[Edge cases] If the cause cannot be identified, set root_cause to "unknown" and list the additional information needed for investigation. If multiple causes are possible, list them in order of likelihood.\n[Self-evaluation] Confirm whether this analysis can reproduce the error and whether the proposed remedies will actually resolve it.\n[Token efficiency] Include only relevant excerpts in evidence; do not paste the full text.',
                    )
                ),
            ),
            "translator": AgentSpec(
                name="translator",
                description="Translation agent",
                permission_level=PermissionLevel.NONE,
                system_prompt=(
                    _(
                        "auto.c30a5aed7a2d7578",
                        default='You are a sub-agent specialized in translation. First understand the intent, terminology, and style of the source, then convert it into natural expressions in the target language, and finally check terminology consistency and placeholder preservation.\n[Output format] Strictly output JSON with:\n  - status: "completed"\n  - role: "translator"\n  - summary: Summary of the translation result\n  - source_lang: Source language (ISO 639-1, etc.)\n  - target_lang: Target language (ISO 639-1, etc.)\n  - translation: Translated text\n  - notes: Notes on terminology choices, ambiguity, or untranslated portions, only when needed\n[Edge cases] If the source mixes multiple languages, use the primary language as source_lang and describe mixed portions in notes. If a fragment cannot be translated, put the possible result in translation and explain why in notes.\n[Self-evaluation] Before output, confirm fidelity, naturalness, terminology consistency, and preservation of placeholders ({...} / __UAG_PROTECTED_0__, etc.).\n[Token efficiency] Do not duplicate the full source text outside translation.',
                    )
                ),
            ),
            "general": AgentSpec(
                name="general",
                description="General-purpose agent",
                permission_level=PermissionLevel.NONE,
                system_prompt=(
                    _(
                        "auto.924901d00f734fac",
                        default='You are a general-purpose task-processing agent. Process the given task flexibly without being constrained to a specific role.\n[Step-by-step reasoning] First understand the task objective and requirements, then determine the necessary information and tools, and finally output a structured result.\n[Output format] Output JSON containing:\n  - status: "completed"\n  - role: "general"\n  - summary: Summary of the processing result\n  - details: Detailed result, structured as appropriate for the task\n  - notes: Additional information or assumptions, only when needed\n[Edge cases] If the requirements are unclear, state that in notes and make the assumptions explicit. If the task cannot be performed, set status to "error" and explain why in summary.\n[Self-evaluation] Confirm that the output meets the task requirements and fill in any omissions before output.\n[Token efficiency] Keep details to the necessary information and avoid verbosity.',
                    )
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
    # Dynamic role generation
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
    # Cost tracking
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
    # Persistent log
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
            return _("status.error", default="error")
        if result.startswith('{"status":"blocked"'):
            return _("status.blocked", default="blocked")
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
    # PermissionLevel support (shared)
    # ------------------------------------------------------------------

    def _build_tool_list_prompt(self, permission_level: str) -> str:
        if permission_level == "none":
            return ""
        # Empty list means all tools are allowed
        return (
            "\n\n[Available tools]\n"
            "All tools are available.\n"
            "Use a tool with {tool_name}(arg1=value, arg2=value).\n"
            "For dangerous operations, obtain confirmation through human_ask first."
        )

    def _annotate_human_ask(
        self, tool_name: str, args: Dict[str, Any], agent_name: str
    ) -> Dict[str, Any]:
        """Identify confirmation prompts originating from a sub-agent."""
        if tool_name != "human_ask" or not agent_name:
            return args
        out = dict(args)
        message = str(out.get("message") or "")
        prefix = _(
            "subagent.human_ask_prefix",
            default="[Sub-agent %(agent)s] Human confirmation request:\n",
        ) % {"agent": agent_name}
        if not message.startswith(prefix):
            out["message"] = prefix + message
        return out

    def _execute_tool_calls(
        self, text: str, permission_level: str, agent_name: str = ""
    ) -> List[str]:
        """Parse tool call patterns and execute them, returning list of result strings."""
        if permission_level == "none":
            return []
        # Empty list means all tools are allowed
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

                args = self._annotate_human_ask(tool_name, args, agent_name)
                runner = tool_runners.get(tool_name)
                if runner:
                    result = runner(args)
                    results.append(f"[tool:{tool_name}]\n{result}")
                else:
                    results.append(f"[tool:{tool_name} error: runner not found]")
            except Exception as exc:
                results.append(f"[tool:{tool_name} error: {exc}]")
        return results

    def _parse_and_execute_tools(
        self, text: str, permission_level: str, agent_name: str = ""
    ) -> str:
        """Compatibility execution for providers without native tool calls."""
        results = self._execute_tool_calls(text, permission_level, agent_name)
        if results:
            return text + "\n\n---\nTool execution result:\n" + "\n\n".join(results)
        return text

    def _native_tool_specs(self, spec: AgentSpec) -> list[dict[str, Any]]:
        """Return the live function schemas used by the parent tool loop."""
        from . import get_tool_specs

        specs = get_tool_specs()
        allowed = {str(n) for n in (spec.allowed_tools or []) if n}
        if not allowed:
            return specs
        management = {"tool_catalog", "tool_load", "unload_tool"}
        return [
            item
            for item in specs
            if str(item.get("function", {}).get("name", "")) in allowed | management
        ]

    def _call_responses_with_tools(
        self,
        client: Any,
        model_name: str,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tool_specs: list[dict[str, Any]],
        timeout: int,
        provider: str,
    ) -> tuple[str, list[dict[str, Any]], Dict[str, int]]:
        """Call the OpenAI/Azure Responses API with native tools."""
        from ..providers.llm_openai_responses import build_responses_request
        from ..providers.responses_common import parse_responses_response

        instructions, input_items, response_tools = build_responses_request(
            [{"role": "system", "content": system_prompt}] + messages,
            send_tools_this_round=True,
            provider=provider,
            tool_specs=tool_specs,
        )
        reasoning = str(os.environ.get("UAGENT_REASONING", "") or "").strip().lower()
        kwargs: Dict[str, Any] = {
            "model": model_name,
            "instructions": instructions or system_prompt,
            "input": input_items,
            "tools": response_tools or [],
        }
        if reasoning in {"minimal", "low", "medium", "high", "xhigh", "max"}:
            try:
                from ..llmcapa_util import get_reasoning_effort_values

                valid = get_reasoning_effort_values(model_name, provider) or []
                if valid:
                    order = ["minimal", "low", "medium", "high", "xhigh", "max"]
                    requested_index = order.index(reasoning)
                    effort = min(
                        valid,
                        key=lambda value: abs(
                            order.index(str(value).lower())
                            if str(value).lower() in order
                            else requested_index - requested_index
                        ),
                    )
                    kwargs["reasoning"] = {"effort": effort}
            except Exception:
                pass
        if timeout > 0:
            kwargs["timeout"] = timeout
        response = client.responses.create(**kwargs)
        text, _reasoning, calls, _response_id, _items = parse_responses_response(
            response
        )
        usage_obj = getattr(response, "usage", None)
        usage = {
            "prompt_tokens": getattr(usage_obj, "input_tokens", 0) or 0,
            "completion_tokens": getattr(usage_obj, "output_tokens", 0) or 0,
            "total_tokens": getattr(usage_obj, "total_tokens", 0) or 0,
        }
        return text or "", calls, usage

    def _call_openai_with_tools(
        self,
        client: Any,
        model_name: str,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tool_specs: list[dict[str, Any]],
        timeout: int,
        provider: str = "",
    ) -> tuple[str, list[dict[str, Any]], Dict[str, int]]:
        """Make one OpenAI-compatible native function-calling request."""
        kwargs: Dict[str, Any] = {
            "model": model_name,
            "messages": [{"role": "system", "content": system_prompt}] + messages,
            "tools": tool_specs,
            "tool_choice": "auto",
        }
        model_lower = str(model_name or "").lower()
        modern = model_lower.startswith("gpt-5") or re.match(
            r"^o[1-4](?:[-.]|$)", model_lower
        )
        kwargs["max_completion_tokens" if modern else "max_tokens"] = 4000
        if not modern:
            kwargs["temperature"] = 0.2
        if timeout > 0:
            kwargs["timeout"] = timeout
        response = client.chat.completions.create(**kwargs)
        message = response.choices[0].message
        calls: list[dict[str, Any]] = []
        for call in getattr(message, "tool_calls", None) or []:
            fn = getattr(call, "function", None)
            calls.append(
                {
                    "id": getattr(call, "id", ""),
                    "type": "function",
                    "function": {
                        "name": getattr(fn, "name", ""),
                        "arguments": getattr(fn, "arguments", "{}"),
                    },
                }
            )
        usage_obj = getattr(response, "usage", None)
        usage = {
            "prompt_tokens": getattr(usage_obj, "prompt_tokens", 0) or 0,
            "completion_tokens": getattr(usage_obj, "completion_tokens", 0) or 0,
            "total_tokens": getattr(usage_obj, "total_tokens", 0) or 0,
        }
        return getattr(message, "content", None) or "", calls, usage

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
            )
            # OpenAI reasoning models (GPT-5/o-series) reject temperature.
            model_lower = str(model_name or "").lower()
            _modern_openai_model = provider in ("openai", "azure") and (
                model_lower.startswith("gpt-5")
                or re.match(r"^o[1-4](?:[-.]|$)", model_lower)
            )
            if not _modern_openai_model:
                kwargs["temperature"] = 0.2
            # New OpenAI reasoning models (GPT-5/o-series) reject the legacy
            # ``max_tokens`` parameter and require ``max_completion_tokens``.
            # Keep the legacy name for older chat-completions models and other
            # OpenAI-compatible providers.
            if _modern_openai_model:
                kwargs["max_completion_tokens"] = max_tokens
            else:
                kwargs["max_tokens"] = max_tokens
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
    # Main execution
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
                "Direct operations with side effects are prohibited",
                "Reliable return in JSON format",
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
            or (get_provider_api_key(sub_provider) if sub_provider else "")
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

        # --- Build system prompt ---
        base_prompt = spec.system_prompt
        if permission_level != "none":
            base_prompt += self._build_tool_list_prompt(permission_level)

        if max_turns > 1 and permission_level != "none":
            base_prompt += (
                f"\n\nYou can continue the conversation for up to {max_turns} turns."
                "After gathering information with tools, output only the final answer without tool calls in the final turn."
                "Each turn appends the previous output and tool results to the conversation history."
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
                        "content": f"[Sub-Agent: {agent_name}] Processing started...\nTask: {task.task}",
                    }
                )
            except Exception:
                pass

        # --- Multi-turn or single-turn ---
        if permission_level != "none":
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
                max_turns=max(2, max_turns),
                agent_spec=spec,
                agent_name=agent_name,
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
                        "content": f"[Sub-Agent: {agent_name}] Processing completed.\nResult:\n{raw_output}",
                    }
                )
            except Exception:
                pass

        # --- Validate output ---
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
    # Multi-turn execution
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
        agent_spec: Optional[AgentSpec] = None,
        agent_name: str = "",
    ) -> tuple[str, int, Dict[str, int]]:
        """Run a multi-turn LLM process, handling native tool calls."""

        native_tools = permission_level != "none" and provider not in (
            "gemini",
            "vertexai",
            "claude",
            "grok",
        )
        tool_specs = (
            self._native_tool_specs(agent_spec) if native_tools and agent_spec else []
        )
        reasoning_mode = (
            str(os.environ.get("UAGENT_REASONING", "") or "").strip().lower()
        )
        responses_env = (
            str(os.environ.get("UAGENT_RESPONSES", "") or "").strip().lower()
        )
        use_responses_tools = bool(
            native_tools
            and provider in ("openai", "azure")
            and hasattr(client, "responses")
            and (responses_env in {"1", "true", "yes", "on"} or reasoning_mode != "")
        )
        conversation = user_prompt
        conversation_messages: list[dict[str, Any]] = [
            {"role": "user", "content": user_prompt}
        ]
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
                            "content": f"[Sub-Agent] Turn {turn + 1}/{max_turns} - Reflect the tool result and proceed to the next turn.",
                        }
                    )
                except Exception:
                    pass

            # Skip JSON validation before the final turn (intermediate output may contain tool calls)
            current_response_mode = response_mode if is_last else ""

            if use_responses_tools:
                raw, native_calls, usage = self._call_responses_with_tools(
                    client,
                    model_name,
                    system_prompt,
                    conversation_messages,
                    tool_specs,
                    timeout,
                    provider,
                )
                retries = 0
            elif native_tools:
                raw, native_calls, usage = self._call_openai_with_tools(
                    client,
                    model_name,
                    system_prompt,
                    conversation_messages,
                    tool_specs,
                    timeout,
                    provider,
                )
                retries = 0
            else:
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
                native_calls = []
            total_retries += retries
            for k in total_usage:
                total_usage[k] += usage.get(k, 0)

            last_raw = raw

            # Final turn: return as-is
            if is_last:
                return raw, total_retries, total_usage

            if native_tools and native_calls:
                from . import run_tool

                conversation_messages.append(
                    {
                        "role": "assistant",
                        "content": raw or None,
                        "tool_calls": native_calls,
                    }
                )
                for call in native_calls:
                    fn = call.get("function", {})
                    try:
                        args = json.loads(fn.get("arguments") or "{}")
                    except (TypeError, json.JSONDecodeError):
                        args = {}
                    tool_name = str(fn.get("name") or "")
                    args = self._annotate_human_ask(tool_name, args, agent_name)
                    result = run_tool(tool_name, args)
                    conversation_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.get("id", ""),
                            "content": str(result),
                        }
                    )
                tool_specs = (
                    self._native_tool_specs(agent_spec) if agent_spec else tool_specs
                )
                continue

            # Append to conversation history
            conversation += f"\n\n[Your Response Turn {turn + 1}]:\n{raw}\n"

            # Parse and execute tool calls
            tool_results = self._execute_tool_calls(raw, permission_level, agent_name)
            if tool_results:
                for tr in tool_results:
                    conversation += f"\n{tr}\n"
                continue  # the next turn

            # No tool calls: this is the final answer
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
                            system_prompt += "\n\n[The previous output was not valid JSON. Output valid JSON only.]"
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
