# WEB_UI_LOGGING (Web UI log/message paths)

This document explains how `src/uagent/web.py` routes output to the Web UI.

Two channels:
- **log path**: stdout/stderr are captured and streamed via WebSocket as `type="log"`
- **message path**: chat messages are sent as `type="message"` / initial payload `type="init"`

Note:
- The Web UI may suppress some CLI-specific guide lines to reduce noise.

---
