"""Sub-Agent Chain Tool Plugin for uag
複数のサブエージェントを順次実行し、結果をステップ間で受け渡すチェーン実行を行います。
"""

from __future__ import annotations
import json
from typing import Any, Dict, List

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True

TOOL_SPEC: Dict[str, Any] = {
    "load_order": 55,
    "type": "function",
    "x_parallel_safe": False,
    "tool_genre": "basic",
    "function": {
        "name": "run_sub_agent_chain",
        "description": _(
            "tool.description",
            default="Execute a sequence of sub-agents in a chain. Each step's result is automatically available to subsequent steps via the shared context store.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=["chain", "sequence", "pipeline", "orchestrate", "multi-step", "workflow"],
        ),
        "x_search_terms_en": [
            "chain", "sequence", "pipeline", "orchestrate", "multi-step", "workflow",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "chain": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "agent_name": {
                                "type": "string",
                                "description": _("param.step.agent_name.description", default="Sub-agent name to execute for this step."),
                            },
                            "task": {
                                "type": "string",
                                "description": _("param.step.task.description", default="Task instruction for this step."),
                            },
                            "current_file": {
                                "type": "string",
                                "description": _("param.step.current_file.description", default="(Optional) File to scope this step's reasoning."),
                            },
                            "response_mode": {
                                "type": "string",
                                "enum": ["json", "text"],
                                "description": _("param.step.response_mode.description", default="Output mode for this step."),
                            },
                            "response_schema": {
                                "type": "object",
                                "description": _("param.step.response_schema.description", default="Optional JSON Schema for the expected response."),
                            },
                            "required_fields": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": _("param.step.required_fields.description", default="Required fields in the JSON response."),
                            },
                            "strict_output": {
                                "type": "boolean",
                                "description": _("param.step.strict_output.description", default="Treat missing required fields as errors."),
                            },
                            "evidence_required": {
                                "type": "boolean",
                                "description": _("param.step.evidence_required.description", default="Require evidence."),
                            },
                            "evidence_min_items": {
                                "type": "integer",
                                "minimum": 0,
                                "description": _("param.step.evidence_min_items.description", default="Minimum number of evidence items."),
                            },
                            "permission_level": {
                                "type": "string",
                                "enum": ["none", "read_only", "propose_only"],
                                "description": _("param.step.permission_level.description", default="Permission level for this step."),
                            },
                            "parent_goal": {
                                "type": "string",
                                "description": _("param.step.parent_goal.description", default="Override the parent goal for this step."),
                            },
                            "store_key": {
                                "type": "string",
                                "description": _("param.step.store_key.description", default="Key to store this step's result for subsequent steps."),
                            },
                            "load_keys": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": _("param.step.load_keys.description", default="Keys to load from previous steps' stored results."),
                            },
                            "cache_ttl": {
                                "type": "integer",
                                "minimum": 0,
                                "description": _("param.step.cache_ttl.description", default="Cache TTL for this step. Default 0."),
                            },
                            "timeout": {
                                "type": "integer",
                                "minimum": 0,
                                "description": _("param.step.timeout.description", default="LLM timeout for this step. Default 120."),
                            },
                            "max_retries": {
                                "type": "integer",
                                "minimum": 0,
                                "description": _("param.step.max_retries.description", default="Max retries for this step. Default 2."),
                            },
                            "max_turns": {
                                "type": "integer",
                                "minimum": 1,
                                "description": _("param.step.max_turns.description", default="Max multi-turn interactions for this step. 3 = recommended. Default 3."),
                            },
                        },
                        "required": ["agent_name", "task"],
                        "additionalProperties": False,
                    },
                    "description": _("param.chain.description", default="List of sub-agent steps to execute in sequence."),
                },
                "stop_on_error": {
                    "type": "boolean",
                    "description": _("param.stop_on_error.description", default="If true, stop chain execution on first error. Default true."),
                },
            },
            "required": ["chain"],
            "additionalProperties": False,
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    from .sub_agent_tool import run_tool as run_sub_agent

    chain: List[Dict[str, Any]] = args["chain"]
    stop_on_error: bool = args.get("stop_on_error", True)

    results: List[Dict[str, Any]] = []
    chain_error: str = ""

    for i, step in enumerate(chain):
        step_args: Dict[str, Any] = {
            "agent_name": step["agent_name"],
            "task": step["task"],
            "current_file": step.get("current_file"),
            "response_mode": step.get("response_mode"),
            "response_schema": step.get("response_schema"),
            "required_fields": step.get("required_fields"),
            "strict_output": step.get("strict_output", False),
            "evidence_required": step.get("evidence_required", False),
            "evidence_min_items": step.get("evidence_min_items", 0),
            "permission_level": step.get("permission_level", "none"),
            "parent_goal": step.get("parent_goal"),
            "cache_ttl": step.get("cache_ttl", 0),
            "store_key": step.get("store_key"),
            "load_keys": step.get("load_keys"),
            "timeout": step.get("timeout", 120),
            "max_retries": step.get("max_retries", 2),
            "max_turns": step.get("max_turns", 3),
        }

        step_result: Dict[str, Any] = {"step": i + 1, "agent_name": step["agent_name"]}
        try:
            raw = run_sub_agent(step_args)
            step_result["result"] = raw
            try:
                obj = json.loads(raw)
                if isinstance(obj, dict):
                    status = obj.get("status", "completed")
                    step_result["status"] = status
                    if status in ("error", "blocked"):
                        err_msg = obj.get("message", "Unknown error")
                        step_result["error"] = err_msg
                        if stop_on_error:
                            chain_error = f"Chain stopped at step {i + 1} ({step['agent_name']}): {err_msg}"
                            results.append(step_result)
                            break
                else:
                    step_result["status"] = "completed"
            except json.JSONDecodeError:
                step_result["status"] = "completed"
                step_result["result"] = raw
        except Exception as exc:
            step_result["status"] = "error"
            step_result["error"] = str(exc)
            if stop_on_error:
                chain_error = f"Chain stopped at step {i + 1} ({step['agent_name']}): {exc}"
                results.append(step_result)
                break

        results.append(step_result)

    output: Dict[str, Any] = {
        "status": "error" if chain_error else "completed",
        "steps": results,
        "total_steps": len(results),
    }
    if chain_error:
        output["message"] = chain_error

    return json.dumps(output, ensure_ascii=False)
