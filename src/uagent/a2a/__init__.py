"""Agent2Agent (A2A) protocol support.

Design goal: keep existing uag/uagw/uagg behavior unchanged.
- The A2A server is started via the separate `uaga` command.
- A2A client integration into the interactive apps can be enabled explicitly.
"""

from __future__ import annotations

# ``uaga`` points directly at ``uagent.a2a.server:main``. Python imports this
# package before the server module, so consume only the UAG-specific OTel flags
# here before ``server.main()`` reaches its strict ``argparse.parse_args()``.
# Environment fallback is intentionally resolved later, after dotenv reload.
from ..runtime.observability.settings import consume_process_otel_cli_flags

consume_process_otel_cli_flags()
