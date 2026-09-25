"""Process-local Sub-Agent execution context.

This state lives outside ``uagent.tools`` so ``system_reload`` can replace tool
modules without replacing the ContextVar that identifies an active Sub-Agent.
"""

from __future__ import annotations

from contextvars import ContextVar, Token

_ACTIVE_SUB_AGENT: ContextVar[str | None] = ContextVar(
    "uagent_active_sub_agent", default=None
)


def set_active_sub_agent_name(name: str | None) -> Token[str | None]:
    return _ACTIVE_SUB_AGENT.set(str(name) if name else None)


def reset_active_sub_agent_name(token: Token[str | None]) -> None:
    _ACTIVE_SUB_AGENT.reset(token)


def get_active_sub_agent_name() -> str | None:
    return _ACTIVE_SUB_AGENT.get()


__all__ = [
    "get_active_sub_agent_name",
    "reset_active_sub_agent_name",
    "set_active_sub_agent_name",
]
