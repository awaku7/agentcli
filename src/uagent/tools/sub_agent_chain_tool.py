"""Sub-Agent Chain Tool Plugin for uag
Run a chain that executes multiple sub-agents sequentially and passes results between steps.
"""

from __future__ import annotations
import json
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from typing import Any, Dict, List

from ..runtime.identity_context import submit_with_current_context

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

_MAX_REVIEW_CANDIDATE_CHARS = 12000
_MAX_PARALLEL_GROUP_WORKERS = 8

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
                            "parallel_group": {
                                "type": "string",
                                "description": _(
                                    "param.step.parallel_group.description",
                                    default="Optional group name. Consecutive steps with the same non-empty group run concurrently.",
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


def _build_review_task(
    *,
    worker_task: str,
    candidate: str,
    review_round: int,
    review_task: str,
) -> str:
    extra = str(review_task or "").strip()
    prompt = (
        "Review whether the worker result satisfies the worker task. "
        "Return only JSON with status, verdict, and feedback. "
        'verdict must be "approve" when the complete candidate has no material '
        'issue, or "retry" when the worker should run again. feedback must '
        "state the concrete remaining work when verdict is retry.\n\n"
        f"[Review round]\n{review_round}\n\n"
        f"[Worker task]\n{worker_task}\n\n"
        f"[Complete candidate]\n{candidate}"
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

        if len(candidate_raw) > _MAX_REVIEW_CANDIDATE_CHARS:
            return (
                candidate_raw,
                reviews,
                worker_attempts,
                "blocked",
                (
                    "Review candidate exceeds the supported review size "
                    f"({_MAX_REVIEW_CANDIDATE_CHARS} characters). "
                    "Large-result review requires a separate review strategy."
                ),
            )

        review_args: Dict[str, Any] = {
            "agent_name": reviewer_agent,
            "task": _build_review_task(
                worker_task=original_task,
                candidate=candidate_raw,
                review_round=review_round + 1,
                review_task=str(review.get("task") or ""),
            ),
            "current_file": step.get("current_file"),
            "load_keys": step.get("load_keys"),
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

        if verdict == "approve":
            return candidate_raw, reviews, worker_attempts, "completed", ""

        if verdict != "retry":
            return (
                candidate_raw,
                reviews,
                worker_attempts,
                "blocked",
                f"Review gate returned invalid verdict: {verdict or '<empty>'}",
            )

        feedback = feedback or "Material work remains."
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


def _step_store_key(step: Dict[str, Any]) -> str:
    value = step.get("store_key")
    return str(value) if value else ""


def _parallel_group_name(step: Dict[str, Any]) -> str:
    return str(step.get("parallel_group") or "").strip()


def _validate_parallel_group(
    group_name: str,
    group_steps: List[Dict[str, Any]],
) -> str:
    store_keys = [_step_store_key(step) for step in group_steps]
    non_empty_keys = [key for key in store_keys if key]
    if len(non_empty_keys) != len(set(non_empty_keys)):
        return (
            f"Parallel group '{group_name}' contains duplicate store_key values. "
            "Parallel members must publish to distinct keys."
        )

    for index, step in enumerate(group_steps):
        sibling_keys = {
            key
            for sibling_index, key in enumerate(store_keys)
            if sibling_index != index and key
        }
        requested = {str(key) for key in (step.get("load_keys") or [])}
        overlap = sorted(sibling_keys & requested)
        if overlap:
            return (
                f"Parallel group '{group_name}' has an intra-group dependency: "
                f"step {index + 1} loads sibling store_key(s) "
                f"{', '.join(overlap)}. Parallel members may only load context "
                "published before the group starts."
            )
    return ""


def _run_chain_step(
    *,
    run_sub_agent: Any,
    publish_shared_result: Any,
    step: Dict[str, Any],
    step_number: int,
    defer_store_publish: bool,
) -> tuple[Dict[str, Any], tuple[str, str] | None]:
    step_result: Dict[str, Any] = {
        "step": step_number,
        "agent_name": step["agent_name"],
    }
    group_name = _parallel_group_name(step)
    if group_name:
        step_result["parallel_group"] = group_name

    reviewed_step = isinstance(step.get("review"), dict)
    include_store_key = not reviewed_step and not defer_store_publish
    raw = run_sub_agent(_build_step_args(step, include_store_key=include_store_key))
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

    publish_later: tuple[str, str] | None = None
    store_key = _step_store_key(step)
    if status == "completed" and store_key:
        if defer_store_publish:
            publish_later = (store_key, final_raw)
        elif reviewed_step:
            publish_shared_result(store_key, final_raw)

    if status in ("error", "blocked"):
        _, obj = _decode_result(final_raw)
        err_msg = review_error
        if not err_msg and obj:
            err_msg = str(obj.get("message", "Unknown error") or "Unknown error")
        step_result["error"] = err_msg or "Unknown error"

    return step_result, publish_later


def run_tool(args: Dict[str, Any]) -> str:
    from . import sub_agent_tool

    run_sub_agent = sub_agent_tool.run_tool
    chain: List[Dict[str, Any]] = args["chain"]
    stop_on_error: bool = args.get("stop_on_error", True)

    results: List[Dict[str, Any]] = []
    chain_error = ""
    index = 0

    while index < len(chain):
        step = chain[index]
        group_name = _parallel_group_name(step)

        if not group_name:
            try:
                step_result, _ = _run_chain_step(
                    run_sub_agent=run_sub_agent,
                    publish_shared_result=sub_agent_tool.publish_shared_result,
                    step=step,
                    step_number=index + 1,
                    defer_store_publish=False,
                )
            except Exception as exc:
                step_result = {
                    "step": index + 1,
                    "agent_name": step["agent_name"],
                    "status": "error",
                    "error": str(exc),
                }

            results.append(step_result)
            if stop_on_error and step_result["status"] in ("error", "blocked"):
                chain_error = (
                    f"Chain stopped at step {index + 1} "
                    f"({step['agent_name']}): {step_result['error']}"
                )
                break
            index += 1
            continue

        group_end = index + 1
        while (
            group_end < len(chain)
            and _parallel_group_name(chain[group_end]) == group_name
        ):
            group_end += 1
        group_steps = chain[index:group_end]

        validation_error = _validate_parallel_group(group_name, group_steps)
        if validation_error:
            chain_error = validation_error
            break

        if len(group_steps) == 1:
            try:
                step_result, _ = _run_chain_step(
                    run_sub_agent=run_sub_agent,
                    publish_shared_result=sub_agent_tool.publish_shared_result,
                    step=group_steps[0],
                    step_number=index + 1,
                    defer_store_publish=False,
                )
            except Exception as exc:
                step_result = {
                    "step": index + 1,
                    "agent_name": group_steps[0]["agent_name"],
                    "parallel_group": group_name,
                    "status": "error",
                    "error": str(exc),
                }
            results.append(step_result)
            if stop_on_error and step_result["status"] in ("error", "blocked"):
                chain_error = (
                    f"Chain stopped at step {index + 1} "
                    f"({group_steps[0]['agent_name']}): {step_result['error']}"
                )
                break
            index = group_end
            continue

        max_workers = min(_MAX_PARALLEL_GROUP_WORKERS, len(group_steps))
        group_results: List[
            tuple[Dict[str, Any], tuple[str, str] | None] | None
        ] = [None] * len(group_steps)

        with ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="sub_agent_group",
        ) as executor:
            active = {}
            next_offset = 0
            failure_seen = False

            def submit_group_step(offset: int) -> None:
                group_step = group_steps[offset]
                future = submit_with_current_context(
                    executor,
                    _run_chain_step,
                    run_sub_agent=run_sub_agent,
                    publish_shared_result=sub_agent_tool.publish_shared_result,
                    step=group_step,
                    step_number=index + offset + 1,
                    defer_store_publish=True,
                )
                active[future] = (offset, group_step)

            while next_offset < len(group_steps) and len(active) < max_workers:
                submit_group_step(next_offset)
                next_offset += 1

            while active:
                done, _ = wait(active, return_when=FIRST_COMPLETED)
                for future in done:
                    offset, group_step = active.pop(future)
                    try:
                        group_results[offset] = future.result()
                    except Exception as exc:
                        group_results[offset] = (
                            {
                                "step": index + offset + 1,
                                "agent_name": group_step["agent_name"],
                                "parallel_group": group_name,
                                "status": "error",
                                "error": str(exc),
                            },
                            None,
                        )

                    item = group_results[offset]
                    if (
                        stop_on_error
                        and item is not None
                        and item[0]["status"] in ("error", "blocked")
                    ):
                        failure_seen = True

                if failure_seen:
                    for future in list(active):
                        if future.cancel():
                            active.pop(future)
                    continue

                while next_offset < len(group_steps) and len(active) < max_workers:
                    submit_group_step(next_offset)
                    next_offset += 1

        first_error: Dict[str, Any] | None = None
        pending_publications: List[tuple[str, str]] = []
        for item in group_results:
            if item is None:
                continue
            step_result, publish_later = item
            results.append(step_result)
            if publish_later is not None:
                pending_publications.append(publish_later)
            if (
                first_error is None
                and step_result["status"] in ("error", "blocked")
            ):
                first_error = step_result

        if first_error is None or not stop_on_error:
            for key, value in pending_publications:
                sub_agent_tool.publish_shared_result(key, value)

        if stop_on_error and first_error is not None:
            chain_error = (
                f"Chain stopped after parallel group '{group_name}' at step "
                f"{first_error['step']} ({first_error['agent_name']}): "
                f"{first_error['error']}"
            )
            break

        index = group_end

    output: Dict[str, Any] = {
        "status": "error" if chain_error else "completed",
        "steps": results,
        "total_steps": len(results),
    }
    if chain_error:
        output["message"] = chain_error

    return json.dumps(output, ensure_ascii=False)
