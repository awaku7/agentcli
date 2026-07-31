from __future__ import annotations

import importlib.util
import os
import sys
from typing import Any


from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


def load_rust_pyd(
    module_name: str,
    *,
    pyd_path: str | None = None,
    caller_file: str | None = None,
) -> Any:
    """Load a Rust-compiled .pyd native extension module.

    Resolution order:
    1. If ``pyd_path`` is given, load from that exact path.
    2. Look for ``<module_name>.pyd`` next to the caller's source file.
    3. Fall back to a pip-installed module (``import <module_name>``).

    This function always evicts any previously cached version of the module
    from ``sys.modules`` before loading, so repeated calls reload from disk.

    Args:
        module_name: Python module name (e.g. ``"uag_tools_rust"``).
        pyd_path:    Absolute path to the ``.pyd`` file. When given,
                     ``caller_file`` is ignored.
        caller_file: Path to the wrapper's ``__file__``. Auto-detected from
                     the call stack when not provided. Useful for external
                     tool creators who ship a standalone ``.py`` + ``.pyd``
                     pair in the same directory.

    Returns:
        The loaded module.

    Raises:
        ImportError: if neither a local ``.pyd`` nor a pip-installed module
                     can be loaded.
    """
    # 1. Evict any stale cached module
    sys.modules.pop(module_name, None)

    resolved_path: str | None = None

    if pyd_path:
        # Explicit path (internal tools_rust/ build output)
        resolved_path = os.path.abspath(pyd_path)
    else:
        # Auto-detect: look for ``.pyd`` next to the caller's source file
        caller = caller_file or _detect_caller_file()
        if caller:
            default_pyd = f"{module_name}.pyd"
            candidate = os.path.join(
                os.path.dirname(os.path.abspath(caller)), default_pyd
            )
            if os.path.isfile(candidate):
                resolved_path = candidate

    if resolved_path and os.path.isfile(resolved_path):
        spec = importlib.util.spec_from_file_location(module_name, resolved_path)
        if spec is None or spec.loader is None:
            raise ImportError(
                _(
                    "rust.spec_failed",
                    default=f"Cannot create spec for .pyd at {resolved_path}",
                )
            )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.modules[module_name] = mod
        return mod

    # 2. Fallback: pip-installed module
    import importlib as _il

    return _il.import_module(module_name)


def _detect_caller_file() -> str | None:
    """Walk up the call stack to find the first caller outside this module."""
    import inspect

    this_file = os.path.abspath(__file__)
    frame = inspect.currentframe()
    try:
        while frame:
            fname = frame.f_globals.get("__file__", "")
            if fname and os.path.abspath(fname) != this_file:
                return fname
            frame = frame.f_back
        return None
    finally:
        del frame
