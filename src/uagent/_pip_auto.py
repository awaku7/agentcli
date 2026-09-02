# src/uagent/_pip_auto.py
"""Auto-install optional Python packages on ImportError."""

from __future__ import annotations

from .i18n import _

import subprocess
import sys
import os

_ALLOWED_PACKAGES = {
    pkg.lower()
    for pkg in {
        # Core/provider packages that may be installed on first use.
    "openai",
    "lmstudio",
    "anthropic",
    "google-genai",
    "xai-sdk",
    "keyring",
    "openrouter",
    "llmcapa",
    "python-dotenv",
    "pyyaml",
    "certifi",
    "tqdm",
    "prompt-toolkit",
    "websockets",
    # Web/server and protocol packages.
    "fastapi",
    "uvicorn",
    "httpx",
    "requests",
    "urllib3",
    "mcp",
    "pydantic",
    "python-multipart",
    "jinja2",
    "pyreadline3",
    "pywin32",
    # Data/document/media packages.
    "numpy",
    "pandas",
    "pint",
    "openpyxl",
    "python-docx",
    "python-pptx",
    "odfpy",
    "pdfplumber",
    "pypdf",
    "pymupdf",
    "msoffcrypto-tool",
    "pillow",
    "qrcode",
    "beautifulsoup4",
    "python-magic",
    "python-magic-bin",
    # Computer/network/automation packages.
    "playwright",
    "pyautogui",
    "pygetwindow",
    "bleak",
    "scapy",
    "psutil",
    "boto3",
    "azure-identity",
    "google-api-python-client",
    "google-cloud-texttospeech",
    "bac0",
    "pymodbus",
    "asyncua",
    "upnpy",
    "winrt-Windows.Devices.Geolocation",
    "pyobjc-framework-corelocation",
    "dbus-next",
    # Developer/analysis packages.
    "pytest",
    "coverage",
    "tree-sitter",
    "tree-sitter-language-pack",
    "mdformat",
    "oletools",
    "packaging",
    "mermaid-cli",
    "ecdsa",
    "cryptography",
    "bitchat-protocol",
    "zai-sdk",
    "together",
    "sounddevice",
    "webrtc-audio-processing",
    # Packages used by tool-level lazy installers.
    "PySide6",
    "catboost",
    "chronos-forecasting",
    "ewmh",
    "exstruct",
    "holidays",
    "janome",
    "jieba",
    "lightgbm",
    "mdformat-frontmatter",
    "paho-mqtt",
    "prophet",
    "pyobjc",
    "pythainlp",
    "python-dali",
    "python-dateutil",
    "scikit-learn",
    "statsforecast",
    "striprtf",
    # Existing compatibility entries.
    "fastapi",
    "uvicorn",
    "pydantic",
    "packaging",
    "playwright",
    "pyautogui",
    "python-docx",
    "openpyxl",
    "beautifulsoup4",
    "pypdf",
    "python-pptx",
    "pymupdf",
    "pillow",
    "qrcode",
    "pandas",
    "numpy",
    "sounddevice",
    "webrtc-audio-processing",
    "dbus-next",
    "pyobjc-framework-corelocation",
    "zai-sdk",
    "tree-sitter",
    "tree-sitter-language-pack",
    "httpx",
    "requests",
    }
}


def _install_policy() -> str:
    value = (os.environ.get("UAGENT_AUTO_INSTALL", "allow") or "allow").strip().lower()
    return value if value in {"allow", "prompt", "off"} else "allow"


def _install_allowed(package_name: str) -> bool:
    normalized = package_name.split("[", 1)[0].split("=", 1)[0].strip().lower()
    return normalized in _ALLOWED_PACKAGES


def _policy_message(label: str, mode: str) -> None:
    print(
        _(
            "Automatic installation is disabled for %(label)s (policy: %(mode)s).",
            default="Automatic installation is disabled for %(label)s (policy: %(mode)s).",
        )
        % {"label": label, "mode": mode},
        file=sys.stderr,
    )


def _confirm_install(label: str) -> bool:
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        _policy_message(label, "prompt-noninteractive")
        return False
    answer = input(
        _("Install %(package)s now? [y/N] ", default="Install %(package)s now? [y/N] ")
        % {"package": label}
    )
    return answer.strip().lower() in {"y", "yes"}


def _may_install(label: str) -> bool:
    policy = _install_policy()
    if policy == "off":
        _policy_message(label, policy)
        return False
    if not _install_allowed(label):
        _policy_message(label, "not-allowlisted")
        return False
    if policy == "prompt":
        return _confirm_install(label)
    return True


def auto_install(package_name: str, module_name: str | None = None) -> bool:
    """Try to install a Python package via pip, then verify it's importable.

    Args:
        package_name: The pip package name (e.g. 'mermaid-cli').
        module_name: The module to import after install (defaults to package_name).

    Returns:
        True if the module is importable after the attempt, False otherwise.
    """
    target = module_name or package_name

    # Try importing first
    try:
        __import__(target)
        return True
    except ImportError:
        pass

    if not _may_install(package_name):
        return False

    # Attempt pip install
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", package_name],
            stdout=sys.stderr,
            stderr=sys.stderr,
            timeout=120,
        )
    except Exception:
        return False

    # Verify after install
    try:
        __import__(target)
        return True
    except ImportError:
        return False


def install_with_status(
    package_name: str,
    module_name: str | None = None,
    display_name: str | None = None,
    verify_submodule: str | None = None,
    version_spec: str | None = None,
) -> bool:
    """Auto-install a package with progress messages.

    Displays localized status messages during install.
    Falls back to auto_install if i18n messages are unavailable.

    Args:
        package_name: The pip package name.
        module_name: The module to import after install (defaults to package_name).
        display_name: Human-readable name for messages (defaults to package_name).
        verify_submodule: If set, additionally import this submodule (e.g. "PySide6.QtCore")
                          to verify C extension DLLs actually load. Default None.
        version_spec: Minimum version requirement (e.g. ">=0.5.0"). If set, the installed
                      version is checked via importlib.metadata and reinstall is triggered
                      if it does not satisfy the requirement.

    Returns:
        True if all imports succeed after the attempt, False otherwise.
    """
    label = display_name or package_name
    target = module_name or package_name

    def _run_pip(*args: str) -> bool:
        full_pkg = package_name
        if version_spec:
            full_pkg = f"{package_name}{version_spec}"
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", *args, full_pkg],
                stdout=sys.stderr,
                stderr=sys.stderr,
                timeout=120,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _check_version() -> bool:
        if not version_spec:
            return True
        try:
            from importlib.metadata import version as _pkg_version

            installed = _pkg_version(package_name)
            # Parse version_spec like ">=0.5.0"
            spec = version_spec.strip()
            if spec.startswith(">="):
                from packaging.version import Version

                return Version(installed) >= Version(spec[2:])
            elif spec.startswith(">"):
                from packaging.version import Version

                return Version(installed) > Version(spec[1:])
            elif spec.startswith("=="):
                from packaging.version import Version

                return Version(installed) == Version(spec[2:])
            elif spec.startswith("<="):
                from packaging.version import Version

                return Version(installed) <= Version(spec[2:])
            elif spec.startswith("<"):
                from packaging.version import Version

                return Version(installed) < Version(spec[1:])
            elif spec.startswith("~="):
                from packaging.version import Version

                return Version(installed) == Version(spec[2:])
            elif spec.startswith("!="):
                from packaging.version import Version

                return Version(installed) != Version(spec[2:])
            # Fallback: treat as minimum (">=X")
            from packaging.version import Version

            return Version(installed) >= Version(spec)
        except Exception:
            return True  # version check failed, assume OK

    def _verify(*, fresh: bool = False) -> bool:
        if fresh and target in sys.modules:
            del sys.modules[target]
            if verify_submodule and verify_submodule in sys.modules:
                del sys.modules[verify_submodule]
        try:
            __import__(target)
        except ImportError:
            return False
        if not _check_version():
            return False
        if verify_submodule:
            try:
                __import__(verify_submodule, fromlist=[""])
            except Exception:
                return False
        return True

    # Already works
    if _verify():
        return True

    if not _may_install(label):
        return False

    # Try installing
    print(_("Installing %(label)s...") % {"label": label}, file=sys.stderr)
    _run_pip()
    if _verify(fresh=True):
        print(
            _("%(label)s installed successfully.") % {"label": label}, file=sys.stderr
        )
        return True

    # One more try with --force-reinstall (e.g. stale/corrupted installation)
    print(_("Retrying with --force-reinstall..."), file=sys.stderr)
    _run_pip("--force-reinstall")
    if _verify(fresh=True):
        print(
            _("%(label)s installed successfully.") % {"label": label}, file=sys.stderr
        )
        return True

    print(_("Failed to install %(label)s.") % {"label": label}, file=sys.stderr)
    return False


def install_playwright_with_chromium() -> bool:
    """Ensure playwright and chromium browser are installed.

    Installs the pip package if missing, and installs the Chromium browser
    binary via 'playwright install chromium' if not already present.

    Returns True if playwright and chromium are available after the attempt,
    False otherwise.
    """
    try:
        import playwright  # noqa: F401
    except ImportError:
        ok = install_with_status("playwright", display_name="playwright")
        if not ok:
            return False
        try:
            import playwright  # noqa: F401
        except ImportError:
            return False

    # Ensure Chromium browser binary is installed
    import subprocess
    import sys

    try:
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            stdout=sys.stderr,
            stderr=sys.stderr,
            timeout=300,
        )
    except Exception:
        return False

    return True
