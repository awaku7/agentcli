# CLI terminal output single-writer refactor

- Status: preparation / design
- Scope: interactive CLI terminal I/O only. GUI and Web have their own renderers and are not changed by this plan.
- Baseline: `main` after PR #478 (`976f165f`).

## Goal

Give one CLI UI owner exclusive responsibility for terminal input and output. Worker threads (LLM calls, spinner, Nostr listener, local-peer listener, Sub-Agent jobs, and tools) publish typed events; they do not directly redraw the terminal. This should make line ordering deterministic and eliminate the need for a broad output mutex.

This is stronger than putting more `print()` calls under `core.print_lock`: a lock only coordinates writers that opt into it, whereas an ownership boundary prevents other threads from writing directly in the first place.

## Current ownership and known producers

- `cli_impl/main.py` starts `stdin_loop` in a daemon thread. That thread reads keyboard input and puts user/command events on `core.event_queue`; the main CLI loop consumes the queue and calls `run_llm_rounds`.
- `llm_helpers._call_maybe_thread` runs provider I/O in the `uagent-llm-call` daemon thread by default. Provider text reaches `core_impl/display.py::print_stream_delta`, which writes terminal output under `core.print_lock`.
- `runtime/spinner.py` has its own `uagent-spinner` thread. It writes CR-rewritten frames to stderr and also takes `core.print_lock`.
- `cli_impl/stdin_loop.py` draws and redraws prompts. It waits during ordinary busy turns, but it still owns terminal I/O while a prompt is active.
- `nostr_remote_runtime.py` receives on a background listener and enqueues normal requests. It also invokes `_display_nostr_incoming` from that receive path, which writes a notification directly to the terminal (currently guarded by `core.print_lock`).
- `runtime/local_messaging.py` enqueues peer-presence and inbound-message events; the CLI main loop displays/handles those events. Sub-Agent notices also normally go through the CLI event queue, while the `:job` UI has synchronous output paths.
- CLI command handlers, tools, and third-party plugins contain additional direct `print()` / stdout/stderr writes. They must be audited before claiming exclusive terminal ownership.

## Proposed architecture

1. Keep domain event delivery separate from display events. A received CLI/Nostr/peer event is authorized and normalized first; it must not directly print.
1. Introduce typed output events for stream deltas/reasoning, status, notices, spinner state, prompt ownership/redraw, turn completion/interruption, and tool output. Each event carries an explicit `source`/`origin` (for example `provider`, `tool:<name>`, `sub_agent:<job_id>`, `nostr`, or `local_peer`) independently of its destination. Keep turn/generation IDs on turn-scoped events so late output from a stopped turn is discarded. Model destinations/routing separately (initially the interactive CLI terminal; later GUI, Web, remote peers, or logs may subscribe) so adding a sink does not require changing producers.
1. Make one UI event loop own both prompt rendering and terminal drawing. It drains display events while the LLM round runs in a worker, so streamed output remains live, and it continues accepting ordinary user input during generation. When a message is submitted during generation, ask whether to interrupt the active turn. On yes, stop that turn; on no, keep generating. In either case retain all submitted messages and process them in FIFO order after the active turn is resolved. The answer prompt must be handled by the UI owner without stopping the event pump. `Ctrl-C` and F12 remain interrupt-without-message controls. Handle all keystrokes/actions in the same UI input owner rather than letting a second thread read stdin. `prompt_toolkit` input, prompt redraws, spinner animation, and notices must all use this same owner; a separate writer thread beside a separately drawing prompt is not sufficient.
1. Migrate the spinner from a terminal-writing thread to a timer/state event consumed by the UI owner. Move Nostr incoming notifications and background-job notices onto the display-event path.
1. Add a separate output callback/facade to the tool execution context. Tools call the injected callback with structured content; the runner supplies the authoritative source (for example `tool:<name>`). The callback only enqueues an event and never renders or chooses destinations itself. Add it through the existing `ToolCallbacks` injection mechanism, but do not overload `log_message`, which records conversation/session messages. Keep user-facing output events distinct from tool results returned to the model, and define a compatibility policy for third-party plugins and subprocess output rather than silently redirecting process-wide stdout in a way that mixes concurrent sessions.
1. Once all interactive writes use the owner, remove `core.print_lock` from routine terminal rendering. Retain locks for shared state (interrupt/status/human-ask/job state) and any transition/compatibility boundary that still genuinely needs synchronization.

## Implementation stages

1. **Inventory and contract:** finish locating terminal writers and classify them as foreground, prompt/UI, worker, or external-plugin output. Add the event schema and ordering/cancellation rules.
1. **UI owner:** keep keyboard input, prompt redraw, status, spinner, and CLI notices on one owner; move blocking `run_llm_rounds` orchestration off that owner and relay its stream events back.
1. **Background producers:** route provider streams, Nostr/peer messages, Sub-Agent notices, and tool output through the display-event channel. Remove their terminal writes.
1. **Lock reduction:** remove redundant terminal-write locking after all writers are migrated. Keep unrelated state locks.
1. **Verification:** stress concurrent stream/status/notice producers and test prompt editing, F12, Ctrl+C, human_ask, Nostr/peer input, cancellation, and shutdown on Windows and POSIX terminals.

## Acceptance criteria

- Only the CLI UI owner writes to the interactive terminal during a session; the spinner and stream callbacks never write directly from their worker threads.
- While a prompt is being edited, stream/status/notification updates do not corrupt the edit buffer; while streaming, no second ordinary prompt is drawn.
- Ordinary user input can be entered and submitted while the LLM is generating. The CLI asks whether to interrupt: yes interrupts the active generation; no lets it continue. Both choices retain all submitted messages and process them FIFO after the active turn is resolved.
- Ctrl-C/F12 remain independently usable to stop the active turn without adding a message, including while the input or interrupt-confirmation prompt is open.
- Events for an interrupted/abandoned turn cannot appear after the interruption or in the next turn.
- Nostr and local-peer messages still pass through existing authorization/confirmation and session checks, then appear in deterministic order.
- `core.print_lock` is not the correctness boundary for routine UI writes; remaining locks are documented as protecting shared state or explicit compatibility paths.
- Concurrent-output regression tests pass on supported Windows and POSIX configurations.

## Risks and open design points

- `prompt_toolkit` currently owns input rendering in `stdin_loop`; the UI ownership change must use its application/event-loop integration rather than writing around it.
- Windows spinner output may use `WriteConsoleW`, which bypasses Python stream wrappers and must be removed from the worker path.
- Some tools/plugins/subprocesses print directly. The migration needs a clear callback/facade policy, including whether unsupported direct plugin output is captured, serialized, redirected, or documented as legacy. Callbacks may be invoked from worker threads, so enqueueing must be thread-safe and must not block waiting for the UI owner; rendering and fan-out stay in output adapters/router code.
- Nostr `/uag status` can be answered by a side worker while a foreground turn is active. Its terminal notification must go through the UI event loop without delaying the remote status reply.
