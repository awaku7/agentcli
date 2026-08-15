"""Provider-specific Computer Use adapters."""

from .anthropic import AnthropicComputerAdapter
from .openai import OpenAIComputerAdapter

__all__ = ["AnthropicComputerAdapter", "OpenAIComputerAdapter"]
