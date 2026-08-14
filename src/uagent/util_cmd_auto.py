"""Auto-pilot (:auto) command implementation (moved from util_tools.py)."""

from __future__ import annotations

import os
import shlex
from typing import Any

from .env_utils import env_get
from .i18n import _
from .util_common import CommandResult, append_result_to_outfile
from .util_image import try_open_images_from_text

# Default translation function used when core.tr is not provided.
tr = _
tr_ = _


def _get_followup_prompt(goal: str, feedback: str = "") -> str:
    """Generate continuation prompt for the main query (i18n)."""
    prompt = _("Continue. Goal: %(goal)s") % {"goal": goal}
    if feedback:
        prompt += "\n\n" + _("Reviewer notes: %(feedback)s") % {"feedback": feedback}
    return prompt


def _build_judgment_messages(
    messages: list[dict[str, Any]],
    goal: str,
) -> list[dict[str, Any]]:
    """Build messages for the reviewer judgment query.

    The explanatory text is localized through gettext. The COMPLETE/CONTINUE
    tokens and output format remain unchanged because they are protocol values.
    """
    system_prompt = _(
        "auto.review_judgment_system_prompt",
        default=(
            "You are a reviewer. Evaluate the conversation below and "
            "determine whether the goal '%(goal)s' has been achieved.\n"
            "Achieved    \u2192 COMPLETE\n"
            "More needed \u2192 CONTINUE\n"
            "Reply with COMPLETE or CONTINUE.\n"
            "If CONTINUE, briefly state what is still missing.\n"
            "Format: CONTINUE: <reason>"
        ),
    ) % {"goal": goal}

    msgs: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]

    # Recent conversation history (max 6 messages = 3 turns)
    history: list[dict[str, Any]] = []
    for m in reversed(messages):
        if m.get("role") in ("user", "assistant"):
            content = m.get("content", "")
            if isinstance(content, str) and content.strip():
                history.append({"role": m["role"], "content": content[:500]})
                if len(history) >= 6:
                    break

    for h in reversed(history):
        msgs.append(h)

    msgs.append({"role": "user", "content": "COMPLETE or CONTINUE?"})
    return msgs


def _ask_reviewer_judgment(
    provider: str,
    client: Any,
    depname: str,
    messages: list[dict[str, Any]],
    core: Any,
    *,
    make_client_fn: Any,
) -> tuple[str, str]:
    """Ask the LLM as a reviewer whether the goal is achieved.

    Uses run_llm_rounds() in judgment_mode=True so that the same code path
    (Responses API included) is used for the judgment query.
    Returns ("COMPLETE"|"CONTINUE", feedback_text).
    """
    from . import uagent_llm as llm_util

    judgment_msgs = _build_judgment_messages(messages, core.auto_pilot_goal)

    core.set_status(True, "AUTO:judge")

    import warnings

    try:
        result_text = llm_util.run_llm_rounds(
            provider=provider,
            client=client,
            depname=depname,
            messages=messages,
            core=core,
            make_client_fn=make_client_fn,
            append_result_to_outfile_fn=append_result_to_outfile,
            try_open_images_from_text_fn=try_open_images_from_text,
            judgment_mode=True,
            judgment_messages=judgment_msgs,
        )
    except Exception as e:
        warnings.warn(
            _("[AUTO] Judgment call failed: %(etype)s: %(error)s")
            % {"etype": type(e).__name__, "error": e}
        )
        raw = "CONTINUE"
    else:
        raw = (result_text or "").strip()

    # Only an explicit decision token may stop auto-pilot.  Substring matching
    # incorrectly treated phrases such as "not COMPLETE" or "INCOMPLETE" as
    # successful completion.
    saw_complete = False
    saw_continue = False
    for line in raw.splitlines():
        token = line.strip().upper()
        if token == "COMPLETE" or token.startswith("COMPLETE:"):
            saw_complete = True
        if token == "CONTINUE" or token.startswith("CONTINUE:"):
            saw_continue = True

    # CONTINUE has precedence whenever both protocol tokens are present.
    # This prevents mixed reviewer output from stopping auto-pilot early.
    if saw_continue:
        judgment = "CONTINUE"
    elif saw_complete:
        judgment = "COMPLETE"
    else:
        judgment = "CONTINUE"
    if judgment == "COMPLETE":
        feedback = ""
    else:
        # Extract feedback after "CONTINUE:" or the whole text minus "CONTINUE"
        feedback = raw
        for prefix in ("CONTINUE:", "continue:", "CONTINUE", "continue"):
            if prefix in raw:
                parts = raw.split(prefix, 1)
                if len(parts) > 1:
                    feedback = parts[1].strip().lstrip(":")
                    break
        feedback = feedback.strip().strip(" -\n").strip("\"'")

    print(_("\n[AUTO:judge] %(judgment)s") % {"judgment": judgment})
    if feedback:
        print(_("  feedback: %(feedback)s") % {"feedback": feedback})
    return judgment, feedback


def _run_auto_pilot_loop(
    provider: str,
    client: Any,
    depname: str,
    messages: list[dict[str, Any]],
    core: Any,
    make_client_fn: Any,
    append_result_to_outfile_fn: Any,
    try_open_images_from_text_fn: Any,
) -> None:
    """Auto-pilot main loop.

    Step B (judgment) is performed FIRST to check the initial goal execution
    done by the caller. If COMPLETE, the loop exits immediately -- no extra round.
    Only if CONTINUE does Step A (followup refinement) run.

    1 round = 2 LLM calls:
      Step B: Reviewer judgment (evaluates previous work / initial goal)
      Step A: Main query (continuation of review/analysis if not yet done)
    """
    # Lazy import to avoid circular imports at module level
    from . import uagent_llm as llm_util

    # Allow separate LLM for reviewer (created once before the loop)
    _judge_provider = provider
    _judge_client = client
    _judge_depname = depname
    _judge_override = env_get("UAGENT_AP_PROVIDER", "").strip()
    if _judge_override:
        _saved = {}
        try:
            _prefix = "UAGENT_AP_"
            _std_prefix = "UAGENT_"
            for _key, _val in os.environ.items():
                if _key.startswith(_prefix):
                    _std_key = _std_prefix + _key[len(_prefix) :]
                    _saved[_std_key] = os.environ.get(_std_key, "")
                    os.environ[_std_key] = _val
            _judge_provider, _judge_client, _judge_depname = make_client_fn(core)
        except Exception:
            pass
        finally:
            for _std_key, _orig_val in _saved.items():
                if _orig_val:
                    os.environ[_std_key] = _orig_val
                else:
                    os.environ.pop(_std_key, None)

    feedback = ""
    while True:
        # 1. x key exit check
        with core.auto_pilot_exit_lock:
            if core.auto_pilot_exit_requested:
                core.auto_pilot_exit_requested = False
                core.auto_pilot_active = False
                print(_("[AUTO] Exited by user (x key)."))
                return

        # === Step B first: Reviewer judgment ===
        # On the first iteration this judges the initial goal execution.
        # On subsequent iterations this judges the followup from Step A.
        judgment, feedback = _ask_reviewer_judgment(
            _judge_provider,
            _judge_client,
            _judge_depname,
            messages,
            core,
            make_client_fn=make_client_fn,
        )

        if judgment == "COMPLETE":
            core.auto_pilot_active = False
            print(_("[AUTO] Review/analysis completed."))
            return

        # 2. Max rounds check (after judgment to count actual followup rounds)
        core.auto_pilot_round += 1
        max_rounds = core.auto_pilot_max_rounds
        if max_rounds is not None and core.auto_pilot_round > max_rounds:
            core.auto_pilot_active = False
            print(
                _("[AUTO] Max rounds (%(max)d) reached. Stopping.")
                % {"max": max_rounds}
            )
            return

        # === Step A: Main query (refinement followup) ===
        next_prompt = _get_followup_prompt(core.auto_pilot_goal, feedback)

        core.set_status(True, "AUTO")
        if core.auto_pilot_max_rounds is None:
            print(_("[AUTO] Round %(round)d/INFINITE") % {"round": core.auto_pilot_round})
        else:
            print(
                _("[AUTO] Round %(round)d/%(max)d")
                % {"round": core.auto_pilot_round, "max": core.auto_pilot_max_rounds}
            )

        user_msg = {"role": "user", "content": next_prompt}
        messages.append(user_msg)
        core.log_message(user_msg)

        # Reset interrupt flag for each round
        with core.interrupt_lock:
            core.interrupt_requested = False

        llm_util.run_llm_rounds(
            provider,
            client,
            depname,
            messages,
            core=core,
            make_client_fn=make_client_fn,
            append_result_to_outfile_fn=append_result_to_outfile_fn,
            try_open_images_from_text_fn=try_open_images_from_text_fn,
        )

        core.set_status(True, "AUTO")


def _handle_cmd_auto(
    arg: str,
    messages_ref: list[dict[str, Any]],
    client: Any,
    depname: str,
    *,
    core: Any,
    tr: Any,
) -> CommandResult | bool:
    """Handle the :auto command.

    Usage:
      :auto <goal> [--max-rounds N|INFINITE]
      :auto <goal> --infinite
      :auto INFINITE <goal>
      :auto off
    """
    a = (arg or "").strip()

    if a.lower() == "off":
        core.auto_pilot_active = False
        core.auto_pilot_exit_requested = False
        print(_("[AUTO] Auto-pilot turned off."))
        return CommandResult()

    if not a:
        print(tr("Usage: :auto <goal> [--max-rounds N]"))
        print(tr("       :auto off"))
        return CommandResult()

    # Parse goal and options. INFINITE is accepted as an explicit mode token
    # as well as the value of --max-rounds.
    goal_parts: list[str] = []
    max_rounds: int | None = 10
    infinite_mode = False
    tokens = shlex.split(a)
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token == "--infinite":
            infinite_mode = True
            i += 1
        elif token == "--max-rounds" and i + 1 < len(tokens):
            raw_max = tokens[i + 1]
            if raw_max.upper() == "INFINITE":
                infinite_mode = True
                i += 2
                continue
            try:
                max_rounds = int(raw_max)
            except ValueError:
                print(
                    tr("Invalid value for --max-rounds: %(val)s")
                    % {"val": raw_max}
                )
                return CommandResult()
            if max_rounds <= 0:
                print(
                    tr("Invalid value for --max-rounds: %(val)s")
                    % {"val": raw_max}
                )
                return CommandResult()
            i += 2
        elif not goal_parts and token.upper() == "INFINITE":
            infinite_mode = True
            i += 1
        else:
            goal_parts.append(token)
            i += 1

    if infinite_mode:
        max_rounds = None

    goal = " ".join(goal_parts)
    if not goal:
        print(tr("Goal cannot be empty."))
        return CommandResult()

    # Set auto-pilot state
    core.auto_pilot_goal = goal
    core.auto_pilot_max_rounds = max_rounds
    core.auto_pilot_round = 0
    core.auto_pilot_exit_requested = False
    core.auto_pilot_active = True

    print(_("[AUTO] Started. Goal: %(goal)s") % {"goal": goal})
    if max_rounds is None:
        print(_("[AUTO] Max rounds: INFINITE"))
    else:
        print(_("[AUTO] Max rounds: %(max)d") % {"max": max_rounds})

    # Return CommandResult with run_llm=True to trigger the first LLM call
    return CommandResult(run_llm=True, prompt=goal)
