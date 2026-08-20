"""scheck package.

Version is resolved from installed distribution metadata (pyproject.toml) when available.

This avoids keeping version in multiple places.
"""

from __future__ import annotations

import sys
import warnings


def _ensure_runtime_dependencies() -> None:
    """Install the optional core dependencies when they are missing."""
    try:
        from importlib.util import find_spec

        from ._pip_auto import install_with_status
    except Exception:
        return

    packages = [
        ("requests", "requests"),
        ("httpx", "httpx"),
        ("urllib3", "urllib3"),
        ("python-dotenv", "dotenv"),
        ("tqdm", "tqdm"),
        ("prompt-toolkit", "prompt_toolkit"),
        ("llmcapa", "llmcapa"),
        ("pyyaml", "yaml"),
        ("certifi", "certifi"),
        ("numpy", "numpy"),
        ("jinja2", "jinja2"),
        ("python-multipart", "multipart"),
        ("websockets", "websockets"),
    ]
    if sys.platform == "win32":
        packages.extend((("pyreadline3", "pyreadline3"), ("pywin32", "win32api")))

    for package_name, module_name in packages:
        try:
            if find_spec(module_name) is not None:
                continue
        except Exception:
            pass
        try:
            install_with_status(package_name, module_name=module_name)
        except Exception as exc:
            warnings.warn(
                f"Could not auto-install {package_name}: {exc}",
                RuntimeWarning,
                stacklevel=2,
            )


_ensure_runtime_dependencies()

# Suppress pkg_resources deprecation warning from jieba/_compat.py
# Applied at package level so all entry points (uag/uagw/uagg/uaga/scheck) are covered.
warnings.filterwarnings(
    "ignore",
    message="pkg_resources is deprecated as an API.*",
    category=UserWarning,
)


def __getattr__(name: str):
    # PEP 562: module attribute access hook
    if name != "__version__":
        raise AttributeError(name)

    try:
        # Prefer installed distribution metadata
        from importlib.metadata import version

        return version("uag")
    except Exception:
        # Fallback for source-tree execution without installation
        return "unknown"


__all__ = ["__version__"]
