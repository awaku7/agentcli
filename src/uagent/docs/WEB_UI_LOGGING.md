# WEB_UI_LOGGING (Web UI log/message paths)

This document explains how `src/uagent/web.py` routes output to the Web UI.

Two channels:

- **log path**: stdout/stderr are captured and streamed via WebSocket as `type="log"`
- **message path**: chat messages are sent as `type="message"` / initial payload `type="init"`

Note:

- The Web UI may suppress some CLI-specific guide lines to reduce noise.
- `[STATE] ...` lines from stderr are filtered on the log path; status is delivered via `type="status"`.
- CLI streaming uses `core.print_stream_delta()` so status lines do not split assistant text mid-line.

______________________________________________________________________
