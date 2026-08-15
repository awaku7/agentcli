"""Computer Use capability, action, policy, and runtime primitives."""

from .actions import ComputerAction, normalize_action
from .adapters.anthropic import AnthropicComputerAdapter
from .adapters.openai import OpenAIComputerAdapter
from .adapters.gemini import GeminiComputerAdapter
from .adapters.custom import CustomComputerAdapter
from .audit import AuditEvent, InMemoryAuditSink
from .config import computer_use_policy_from_env
from .capability import ComputerUseCapabilityError, get_computer_use_capability
from .policy import ComputerUsePolicy, PolicyDecision
from .loop import run_anthropic_computer_loop
from .results import ComputerActionResult, Screenshot
from .runtime import ComputerRuntime, execute_action

__all__ = [
    "ComputerAction",
    "CustomComputerAdapter",
    "GeminiComputerAdapter",
    "AnthropicComputerAdapter",
    "AuditEvent",
    "ComputerActionResult",
    "ComputerRuntime",
    "ComputerUseCapabilityError",
    "ComputerUsePolicy",
    "computer_use_policy_from_env",
    "InMemoryAuditSink",
    "OpenAIComputerAdapter",
    "PolicyDecision",
    "Screenshot",
    "execute_action",
    "get_computer_use_capability",
    "run_anthropic_computer_loop",
    "normalize_action",
]
