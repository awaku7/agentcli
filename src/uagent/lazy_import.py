"""Lazy, on-demand imports for optional runtime dependencies."""

from __future__ import annotations

import importlib
from typing import Any


class LazyModule:
    def __init__(self, package_name: str, module_name: str | None = None) -> None:
        self._package_name = package_name
        self._module_name = module_name or package_name
        self._module: Any = None

    def _load(self) -> Any:
        if self._module is None:
            from ._pip_auto import install_with_status

            if not install_with_status(self._package_name, self._module_name):
                raise ModuleNotFoundError(f"No module named '{self._module_name}'")
            self._module = importlib.import_module(self._module_name)
        return self._module

    def __getattr__(self, name: str) -> Any:
        return getattr(self._load(), name)


def lazy_module(package_name: str, module_name: str | None = None) -> LazyModule:
    return LazyModule(package_name, module_name)
