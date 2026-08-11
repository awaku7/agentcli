"""Public tool facade for code_map.

The implementation lives in :mod:`code_map_impl.runner`; the translation
catalog intentionally remains next to this facade as ``code_map_tool.json``.
"""
from __future__ import annotations

import importlib
from .code_map_impl import runner as _runner

# Rebuild the spec when this facade is re-imported so locale changes are honored.
_runner = importlib.reload(_runner)
BUSY_LABEL = _runner.BUSY_LABEL
STATUS_LABEL = _runner.STATUS_LABEL
TOOL_SPEC = _runner.TOOL_SPEC
run_tool = _runner.run_tool
from .code_map_impl.renderers import tree_to_mermaid as _tree_to_mermaid  # noqa: F401

__all__ = ["BUSY_LABEL", "STATUS_LABEL", "TOOL_SPEC", "run_tool"]
