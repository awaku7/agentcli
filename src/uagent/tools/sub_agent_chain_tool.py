"""Sub-Agent Chain Tool Plugin for uag
Run a chain that executes multiple sub-agents sequentially and passes results between steps.
"""

from __future__ import annotations
import json
from typing import Any, Dict, List

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

_REVIEW_SEGMENT_CHARS = 12000

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
            default=[
                "chain",
                "sequence",
                "pipeline",
                "orchestrate",
                "multi-step",
                "workflow",
            ],
        ),
        "x_search_terms_en": [
            "chain",
            "sequence",
            "pipeline",
            "orchestrate",
            "multi-step",
            "workflow",
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
                                "description": _(
                                    "param.step.agent_name.description",
                                    default="Sub-agent name to execute for this step.",
                                ),
                            },
                            "task": {
                                "type": "string",
                                "description": _(
                                    "param.step.task.description",
                                    default="Task instruction for this step.",
                                ),
                            },
                            "current_file": {
                                "type": "string",
                                "description": _(
                                    "param.step.current_file.description",
                                    default="(Optional) File to scope this step's reasoning.",
                                ),
                            },
                            "response_mode": {
                                "type": "string",
                                "enum": ["json", "text"],
                                "description": _(
                                    "param.step.response_mode.description",
                                    default="Output mode for this step.",
                                ),
                            },
                            "response_schema": {
                                "type": "object",
                                "description": _(
                                    "param.step.response_schema.description",
                                    default="Optional JSON Schema for the expected response.",
                                ),
                            },
                            "required_fields": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": _(
                                    "param.step.required_fields.description",
                                    default="Required fields in the JSON response.",
                                ),
                            },
                            "strict_output": {
                                "type": "boolean",
                                "description": _(
                                    "param.step.strict_output.description",
                                    default="Treat missing required fields as errors.",
                                ),
                            },
                            "evidence_required": {
                                "type": "boolean",
                                "description": _(
                                    "param.step.evidence_required.description",
                                    default="Require evidence.",
                                ),
                            },
                            "evidence_min_items": {
                                "type": "integer",
                                "minimum": 0,
                                "description": _(
                                    "param.step.evidence_min_items.description",
                                    default="Minimum number of evidence items.",
                                ),
                            },
                            "permission_level": {
                                "type": "string",
                                "enum": ["none", "read_only", "propose_only"],
                                "description": _(
                                    "param.step.permission_level.description",
                                    default="Permission level for this step.",
                                ),
                            },
                            "parent_goal": {
                                "type": "string",
                                "description": _(
                                    "param.step.parent_goal.description",
                                    default="Override the parent goal for this step.",
                                ),
                            },
                            "store_key": {
                                "type": "string",
                                "description": _(
                                    "param.step.store_key.description",
                                    default="Key to store this step's result for subsequent steps.",
                                ),
                            },
                            "load_keys": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": _(
                                    "param.step.load_keys.description",
                                    default="Keys to load from previous steps' stored results.",
                                ),
                            },
                            "cache_ttl": {
                                "type": "integer",
                                "minimum": 0,
                                "description": _(
                                    "param.step.cache_ttl.description",
                                    default="Cache TTL for this step. Default 0.",
                                ),
                            },
                            "timeout": {
                                "type": "integer",
                                "minimum": 0,
                                "description": _(
                                    "param.step.timeout.description",
                                    default="LLM timeout for this step. Default 120.",
                                ),
                            },
                            "max_retries": {
                                "type": "integer",
                                "minimum": 0,
                                "description": _(
                                    "param.step.max_retries.description",
                                    default="Max retries for this step. Default 2.",
                                ),
                            },
                            "max_tool_turns": {
                                "type": "integer",
                                "minimum": 2,
                                "description": _(
                                    "param.step.max_tool_turns.description",
                                    default="Maximum LLM/tool turns inside one autonomous round. Default 3.",
                                ),
                            },
                            "max_agent_rounds": {
                                "type": "integer",
                                "minimum": 1,
                                "description": _(
                                    "param.step.max_agent_rounds.description",
                                    default="Maximum autonomous work rounds including the initial round. Default 3.",
                                ),
                            },
                            "completion_sentinel": {
                                "type": "boolean",
                                "description": _(
                                    "param.step.completion_sentinel.description",
                                    default="Use sentinel-based completion judgment for this step.",
                                ),
                            },
                            "completion_regex": {
                                "type": "string",
                                "description": _(
                                    "param.step.completion_regex.description",
                                    default="Optional completion regex checked before other completion judges.",
                                ),
                            },
                            "review": {
                                "type": "object",
                                "properties": {
                                    "agent_name": {
                                        "type": "string",
                                        "description": _(
                                            "param.step.review.agent_name.description",
                                            default="Reviewer sub-agent name. Default reviewer.",
                                        ),
                                    },
                                    "task": {
                                        "type": "string",
                                        "description": _(
                                            "param.step.review.task.description",
                                            default="Optional extra review instruction applied to the worker result.",
                                        ),
                                    },
                                    "max_retries": {
                                        "type": "integer",
                                        "minimum": 0,
                                        "description": _(
                                            "param.step.review.max_retries.description",
                                            default="Maximum worker retries requested by the reviewer after the initial attempt. Default 2.",
                                        ),
                                    },
                                    "permission_level": {
                                        "type": "string",
                                        "enum": ["none", "read_only", "propose_only"],
                                        "description": _(
                                            "param.step.review.permission_level.description",
                                            default="Permission level for the reviewer. Default none.",
                                        ),
                                    },
                                    "max_tool_turns": {
                                        "type": "integer",
                                        "minimum": 2,
                                        "description": _(
                                            "param.step.review.max_tool_turns.description",
                                            default="Maximum LLM/tool turns inside one reviewer autonomous round. Default 3.",
                                        ),
                                    },
                                    "max_agent_rounds": {
                                        "type": "integer",
                                        "minimum": 1,
                                        "description": _(
                                            "param.step.review.max_agent_rounds.description",
                                            default="Maximum autonomous reviewer work rounds. Default 3.",
                                        ),
                                    },
                                },
                                "additionalProperties": False,
                                "description": _(
                                    "param.step.review.description",
                                    default="Optional review gate. The reviewer returns approve or retry; retry re-runs the worker with review feedback.",
                                ),
                            },
                        },
                        "required": ["agent_name", "task"],
                        "additionalProperties": False,
                    },
                    "description": _(
                        "param.chain.description",
                        default="List of sub-agent steps to execute in sequence.",
                    ),
                },
                "stop_on_error": {
                    "type": "boolean",
                    "description": _(
                        "param.stop_on_error.description",
                        default="If true, stop chain execution on first error. Default true.",
                    ),
                },
            },
            "required": ["chain"],
            "additionalProperties": False,
        },
    },
}


def _build_step_args(
    step: Dict[str, Any],
    *,
    task_override: str | None = None,
    include_store_key: bool = True,
) -> Dict[str, Any]:
    return {
        "agent_name": step["agent_name"],
        "task": task_override if task_override is not None else step["task"],
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
        "store_key": step.get("store_key") if include_store_key else None,
        "load_keys": step.get("load_keys"),
        "timeout": step.get("timeout", 120),
        "max_retries": step.get("max_retries", 2),
        "max_tool_turns": step.get("max_tool_turns", 3),
        "max_agent_rounds": step.get("max_agent_rounds", 3),
        "completion_sentinel": step.get("completion_sentinel"),
        "completion_regex": step.get("completion_regex"),
    }


def _decode_result(raw: str) -> tuple[str, Dict[str, Any] | None]:
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return "completed", None
    if not isinstance(obj, dict):
        return "completed", None
    return str(obj.get("status", "completed")), obj


def _split_candidate_for_review(candidate: str) -> List[str]:
    text = str(candidate or "")
    if not text:
        return [""]
    return [
        text[start : start + _REVIEW_SEGMENT_CHARS]
        for start in range(0, len(text), _REVIEW_SEGMENT_CHARS)
    ]


def _build_review_task(
    *,
    worker_task: str,
    candidate_segment: str,
    segment_index: int,
    segment_count: int,
    review_task: str,
) -> str:
    extra = str(review_task or "").strip()
    if segment_count == 1:
        coverage = "The candidate below is the complete worker result."
    else:
        coverage = (
            f"The candidate is split into {segment_count} review segments. "
            f"This is segment {segment_index} of {segment_count}. Review this "
            "segment for concrete defects, contradictions, unsafe content, or "
            "evidence that the worker task is not satisfied. Do not infer that "
            "content is missing merely because it may be in another segment."
        )
    prompt = (
        "Review whether the worker result satisfies the worker task. "
        "Return only JSON with status, verdict, and feedback. "
        'verdict must be "approve" when this review segment has no material '
        'issue, or "retry" when the worker should run again. feedback must '
        "state the concrete remaining work when verdict is retry.\n\n"
        f"[Worker task]\n{worker_task}\n\n"
        f"[Review coverage]\n{coverage}\n\n"
        f"[Candidate segment {segment_index}/{segment_count}]\n"
        f"{candidate_segment}"
    )
    if extra:
        prompt += f"\n\n[Additional review instruction]\n{extra}"
    return prompt


def _build_retry_task(
    *,
    original_task: str,
    feedback: str,
    attempt: int,
) -> str:
    return (
        f"{original_task}\n\n"
        f"[Review feedback before retry {attempt}]\n{feedback}\n\n"
        "Revise the result to address every material review issue. Re-check the "
        "original task and do not merely describe the feedback."
    )


def _run_review_gate(
    *,
    run_sub_agent: Any,
    step: Dict[str, Any],
    initial_raw: str,
) -> tuple[str, List[Dict[str, Any]], int, str, str]:
    review = step.get("review")
    if not isinstance(review, dict):
        status, _ = _decode_result(initial_raw)
        return initial_raw, [], 1, status, ""

    max_retries = max(0, int(review.get("max_retries", 2) or 0))
    reviewer_agent = str(review.get("agent_name") or "reviewer")
    original_task = str(step["task"])
    candidate_raw = initial_raw
    reviews: List[Dict[str, Any]] = []
    worker_attempts = 1

    for review_round in range(max_retries + 1):
        candidate_status, candidate_obj = _decode_result(candidate_raw)
        if candidate_status in ("error", "blocked"):
            message = ""
            if candidate_obj:
                message = str(candidate_obj.get("message", "") or "")
            return candidate_raw, reviews, worker_attempts, candidate_status, message

        segments = _split_candidate_for_review(candidate_raw)
        retry_feedback: List[str] = []

        for segment_index, candidate_segment in enumerate(segments, start=1):
            review_args: Dict[str, Any] = {
                "agent_name": reviewer_agent,
                "task": _build_review_task(
                    worker_task=original_task,
                    candidate_segment=candidate_segment,
                    segment_index=segment_index,
                    segment_count=len(segments),
                    review_task=str(review.get("task") or ""),
                ),
                "response_mode": "json",
                "response_schema": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string"},
                        "verdict": {
                            "type": "string",
                            "enum": ["approve", "retry"],
                        },
                        "feedback": {"type": "string"},
                    },
                    "required": ["status", "verdict", "feedback"],
                },
                "required_fields": ["status", "verdict", "feedback"],
                "strict_output": True,
                "permission_level": review.get("permission_level", "none"),
                "parent_goal": step.get("parent_goal"),
                "timeout": step.get("timeout", 120),
                "max_retries": step.get("max_retries", 2),
                "max_tool_turns": review.get("max_tool_turns", 3),
                "max_agent_rounds": review.get("max_agent_rounds", 3),
            }

            review_raw = run_sub_agent(review_args)
            review_status, review_obj = _decode_result(review_raw)
            review_record: Dict[str, Any] = {
                "round": review_round + 1,
                "segment": segment_index,
                "segments": len(segments),
                "agent_name": reviewer_agent,
                "result": review_raw,
                "status": review_status,
            }
            reviews.append(review_record)

            if review_status in ("error", "blocked") or review_obj is None:
                message = (
                    str(review_obj.get("message", "") or "")
                    if review_obj
                    else "Reviewer did not return a JSON object."
                )
                return (
                    candidate_raw,
                    reviews,
                    worker_attempts,
                    "blocked",
                    f"Review gate failed: {message}",
                )

            verdict = str(review_obj.get("verdict", "") or "").strip().lower()
            feedback = str(review_obj.get("feedback", "") or "").strip()
            review_record["verdict"] = verdict
            review_record["feedback"] = feedback

            if verdict == "retry":
                retry_feedback.append(
                    f"Segment {segment_index}/{len(segments)}: "
                    f"{feedback or 'Material work remains.'}"
                )
                continue

            if verdict != "approve":
                return (
                    candidate_raw,
                    reviews,
                    worker_attempts,
                    "blocked",
                    f"Review gate returned invalid verdict: {verdict or '<empty>'}",
                )

        if not retry_feedback:
            return candidate_raw, reviews, worker_attempts, "completed", ""

        feedback = "\n".join(retry_feedback)
        if review_round >= max_retries:
            return (
                candidate_raw,
                reviews,
                worker_attempts,
                "blocked",
                (
                    "Review gate exhausted worker retries before approval. "
                    f"Last feedback: {feedback}"
                ),
            )

        worker_attempts += 1
        retry_args = _build_step_args(
            step,
            task_override=_build_retry_task(
                original_task=original_task,
                feedback=feedback,
                attempt=worker_attempts,
            ),
            include_store_key=False,
        )
        candidate_raw = run_sub_agent(retry_args)

    return (
        candidate_raw,
        reviews,
        worker_attempts,
        "blocked",
        "Review gate stopped without an approval verdict.",
    )


def run_tool(args: Dict[str, Any]) -> str:
    from . import sub_agent_tool

    run_sub_agent = sub_agent_tool.run_tool
    chain: List[Dict[str, Any]] = args["chain"]
    stop_on_error: bool = args.get("stop_on_error", True)

    results: List[Dict[str, Any]] = []
    chain_error: str = ""

    for i, step in enumerate(chain):
        step_result: Dict[str, Any] = {"step": i + 1, "agent_name": step["agent_name"]}
        try:
            reviewed_step = isinstance(step.get("review"), dict)
            raw = run_sub_agent(
                _build_step_args(step, include_store_key=not reviewed_step)
            )
            final_raw, reviews, attempts, status, review_error = _run_review_gate(
                run_sub_agent=run_sub_agent,
                step=step,
                initial_raw=raw,
            )
            step_result["result"] = final_raw
            step_result["status"] = status
            if reviews:
                step_result["attempts"] = attempts
                step_result["reviews"] = reviews

            if (
                status == "completed"
                and reviewed_step
                and step.get("store_key")
            ):
                sub_agent_tool.publish_shared_result(
                    str(step["store_key"]),
                    final_raw,
                )

            if status in ("error", "blocked"):
                _, obj = _decode_result(final_raw)
                err_msg = review_error
                if not err_msg and obj:
                    err_msg = str(
                        obj.get("message", "Unknown error") or "Unknown error"
                    )
                if not err_msg:
                    err_msg = "Unknown error"
                step_result["error"] = err_msg
                if stop_on_error:
                    chain_error = (
                        f"Chain stopped at step {i + 1} "
                        f"({step['agent_name']}): {err_msg}"
                    )
                    results.append(step_result)
                    break
        except Exception as exc:
            step_result["status"] = "error"
            step_result["error"] = str(exc)
            if stop_on_error:
                chain_error = (
                    f"Chain stopped at step {i + 1} ({step['agent_name']}): {exc}"
                )
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
