# Restart Recovery

When the A2A server starts with a persistent SQLite TaskStore, tasks left in `IN_PROGRESS` or `CANCEL_REQUESTED` are detected and marked `FAILED` with the stable error code `TASK_INTERRUPTED_BY_RESTART`.

The original input, task history, and error code remain available through the normal task APIs. A structured `task.recovered_after_restart` event records the recovery count without exposing secrets.

This behavior is intentionally conservative: uagent does not resume an interrupted LLM or Tool call automatically. Checkpoint-based resume is a separate feature.

## Configuration

```text
UAGENT_TASK_STORE=sqlite
UAGENT_TASK_STORE_PATH=/path/to/tasks.sqlite3
```

On Windows PowerShell:

```powershell
$env:UAGENT_TASK_STORE = "sqlite"
$env:UAGENT_TASK_STORE_PATH = "$HOME/.uag/a2a/tasks.sqlite3"
```

## I18N

`TASK_INTERRUPTED_BY_RESTART` and `task.recovered_after_restart` are stable machine-readable values and are not translated. User-facing clients should translate their presentation while preserving these values in API responses and logs.


## Checkpoints

Task stores also expose `save_checkpoint(task_id, checkpoint)` and `load_checkpoint(task_id)` for durable recovery metadata. Checkpoints contain structured, application-owned data; secret values must not be stored in them. Automatic resume of an interrupted LLM or Tool call is intentionally not performed yet.
