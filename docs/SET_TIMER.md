# `set_timer`

`set_timer` creates, lists, and deletes persistent one-shot timers. Timers are
stored by the scheduler and can inject a prompt into the next LLM turn.

## LLM execution

```json
{
  "seconds": 60,
  "message": "Timer finished",
  "on_timeout_prompt": "Check the deployment status",
  "required_tools": ["workspace_status"],
  "execution_mode": "llm"
}
```

`required_tools` are loaded and pinned only while the scheduled LLM run is
executing. Existing pins are restored afterward.

## Direct tool execution

A timer can execute one explicit tool without an LLM round:

```json
{
  "seconds": 300,
  "execution_mode": "direct",
  "target_tool": "workspace_status",
  "target_args": {}
}
```

Direct jobs use the normal tool dispatcher and policy checks. Management tools
and arbitrary-code tools are rejected as direct targets. `direct` cannot be
combined with `os_persist=true`; OS-level jobs start a separate `uag` process
and therefore use the normal injected-message path.

## Listing and deletion

Use `{"action":"list"}` to list internal and OS-level timers. Internal timers
include a `schedule_id`; pass it as `schedule_id` with `{"action":"delete"}`
to remove one. OS-level jobs use `job_name`.

Retry, timeout, and required-tool metadata are persisted with the run. A failed
or timed-out run is recorded in `SchedulerRunStore` with its final status.
