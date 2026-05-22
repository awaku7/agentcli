"""Agent2Agent (A2A) protocol support.

Design goal: keep existing uag/uagw/uagg behavior unchanged.
- The A2A server is started via the separate `uaga` command.
- A2A client integration into the interactive apps can be enabled explicitly.
"""

from __future__ import annotations
