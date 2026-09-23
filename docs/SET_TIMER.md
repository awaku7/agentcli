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

## Delivery durability

Internal timer events use a SQLite-backed outbox. The scheduler commits the
schedule transition and its dispatch events together before handing an event to
the in-process queue.

For the normal CLI/GUI queue, an outbox event is acknowledged when the consumer
dequeues it. If queue delivery fails, the event remains pending and is retried.
If a process stops before dequeue, the pending event remains durable instead of
being silently lost.

Delivery is **at least once**. A rare retry can therefore produce the same
scheduler event more than once. Scheduled tool and LLM execution still uses the
persisted `run_id` / idempotency state to avoid executing the same run twice.
The outbox `delivered` state means that the event reached the consumer; it does
not mean that the scheduled run completed successfully.

Internal timer state is bound to its scheduler instance. Another UAG process
does not automatically consume that instance's pending timers or events.
Recovery after a process restart is an explicit ownership-reclaim operation and
must be performed only after the persisted session/authentication boundary has
been revalidated.

## Listing and deletion

Use `{"action":"list"}` to list internal and OS-level timers. Internal timers
include a `schedule_id`; pass it as `schedule_id` with `{"action":"delete"}`
to remove one. OS-level jobs use `job_name`.

Retry, timeout, and required-tool metadata are persisted with the run. A failed
or timed-out run is recorded in `SchedulerRunStore` with its final status.
