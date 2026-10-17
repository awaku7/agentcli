# Web room concurrency

Start Web with a maximum of three simultaneously executing rooms:

```text
uagw --room-workers 3
```

Alternatively set `UAGENT_WEB_ROOM_WORKERS=3` in the Web server environment.
The command-line option takes precedence. The count must be a positive integer;
the default is 5. Set `--room-workers 1` to use the existing serial implementation.

With a count of 3, A, B and C may execute together. D reports `QUEUED` until a
slot becomes available. Each room still accepts only one active turn; duplicate
submissions to that room are rejected. Stop targets only that room's running
child, and confirmation responses are forwarded only to that child. A queued
room's Stop button remains disabled.

## Isolation

For counts greater than 1, the server starts an isolated Python process for each
foreground turn. The child runs the existing Web worker and normal foreground
tools. Process cwd, core state, tool callbacks, providers and interrupt flags
are separate. The parent owns authenticated connections and relays streaming,
messages, status, images and confirmations over a private local pipe.

History, Responses continuation, tool context, agent state and dynamically loaded
tool names are returned to the originating room. SQLite writes use the room's
existing session ID without creating empty startup sessions. Parent tool setting
changes override the remembered child tool list for the next turn. JSONL files
have separate room/process names to avoid interleaved logs. Shared files selected
by multiple rooms remain shared; process isolation does not merge file edits.

History/working-directory commands are serialized with that room's worker so a
returned child snapshot cannot overwrite a command issued during its turn.
Connect-time history initialization runs in a bootstrap-only child before the
room accepts user turns. This keeps project-instruction selection (including
AGENTS.md) ahead of the first user message without changing the server cwd while
other rooms execute. The bootstrap child returns initialized history to the room
and exits without running an LLM turn; ordinary foreground turns continue to use
one child process each.

## Current limits and verification

Children last for one foreground turn. Process-local tool resources (for example
a browser or MCP connection) are recreated on the next turn; serialized history
and supported continuation state are retained. Background Sub-Agent Jobs are
unavailable inside these children because their runtime cannot outlive the
foreground process. Explicit one-worker mode (`--room-workers 1`) retains existing background Job
behavior. This mode does not change the CLI, GUI or A2A hosts.

Offline tests run the real spawn/IPC/worker path with a fake provider and actual
`python_exec` file operations. They verify concurrent rooms, capacity overflow,
per-room cwd/session/Responses state, Stop routing, separate confirmations,
duplicate rejection and crash cleanup. Real provider, plugin and multi-turn
browser/MCP verification still needs live testing.

On server shutdown, running children receive a cooperative Stop request. After
a bounded grace period, remaining foreground children are terminated; queued
turns are not started. Existing history and memory databases are retained.
