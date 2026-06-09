from __future__ import annotations

import io
import os
import sys
from pathlib import Path

from ..i18n import _

from .runtime_banner import build_startup_banner
from .runtime_env import validate_or_exit_startup_env
from .runtime_memory import append_long_memory_system_messages
from .runtime_workdir import WorkdirDecision, apply_workdir, decide_workdir

_STARTUP_UAGENT_ENV_SNAPSHOT: dict[str, str] | None = None


def capture_startup_uagent_env_snapshot(*, force: bool = False) -> dict[str, str]:
    """Capture UAGENT_* values that existed before dotenv files are loaded."""

    global _STARTUP_UAGENT_ENV_SNAPSHOT
    if force or _STARTUP_UAGENT_ENV_SNAPSHOT is None:
        _STARTUP_UAGENT_ENV_SNAPSHOT = {
            key: value for key, value in os.environ.items() if key.startswith("UAGENT_")
        }
    return dict(_STARTUP_UAGENT_ENV_SNAPSHOT)


def get_startup_uagent_env_snapshot() -> dict[str, str] | None:
    if _STARTUP_UAGENT_ENV_SNAPSHOT is None:
        return None
    return dict(_STARTUP_UAGENT_ENV_SNAPSHOT)


def load_dotenv_custom() -> None:
    """Load .env and .env.sec from CWD using startup precedence rules.

    Effective priority for UAGENT_* keys:
    1. pre-existing process environment captured before dotenv loading
    2. .env.sec
    3. .env
    4. application defaults

    UAGENT_* keys are recomputed on each reload to avoid stale values from a
    previous .env/.env.sec load masking file changes made by setup or users.
    """

    try:
        from dotenv import dotenv_values, load_dotenv
    except ImportError:
        # python-dotenv is not installed.
        return

    cwd = Path.cwd()
    startup_snapshot = capture_startup_uagent_env_snapshot()

    env_values: dict[str, str | None] = {}
    env_path = cwd / ".env"
    if env_path.exists():
        # Keep historical behavior for non-UAGENT keys. UAGENT_* keys are
        # normalized below according to the startup precedence rules.
        load_dotenv(env_path, override=False)
        env_values = dict(dotenv_values(env_path))

    sec_values: dict[str, str | None] = {}
    sec_path = cwd / ".env.sec"
    if sec_path.exists():
        try:
            # Local import to avoid dependency issues if not used.
            from uag_envsec.secret_core import decrypt_text

            # Prefer .uagent.key in CWD, fallback to default (~/.uag/uag_envsec_key).
            local_key = cwd / ".uagent.key"
            kp = str(local_key) if local_key.exists() else None

            body = sec_path.read_text(encoding="utf-8").strip()
            if body:
                dec = decrypt_text(body, key_path=kp)
                sec_values = dict(dotenv_values(stream=io.StringIO(dec)))
        except Exception as e:
            # Always report decryption errors to stderr if it exists but fails.
            print(
                _("[WARN] Failed to decrypt .env.sec: %(err)s", err=e),
                file=sys.stderr,
            )

    def _value(value: str | None) -> str:
        return "" if value is None else str(value)

    # Remove UAGENT_* values that came from previous dotenv loads. True
    # pre-existing process values are restored at the end and remain highest
    # priority.
    for key in [k for k in os.environ if k.startswith("UAGENT_")]:
        if key not in startup_snapshot:
            os.environ.pop(key, None)

    for values in (env_values, sec_values):
        for key, value in values.items():
            if not key:
                continue
            if key.startswith("UAGENT_"):
                if key not in startup_snapshot:
                    os.environ[key] = _value(value)
            elif values is sec_values:
                # Match the previous .env.sec behavior for non-UAGENT secrets.
                os.environ[key] = _value(value)

    # Pre-existing UAGENT_* env vars are explicit per-run overrides.
    os.environ.update(startup_snapshot)


def reload_dotenv_custom() -> None:
    """Reload .env and .env.sec from the current CWD into the current process."""

    load_dotenv_custom()


__all__ = [
    "WorkdirDecision",
    "apply_workdir",
    "decide_workdir",
    "build_startup_banner",
    "validate_or_exit_startup_env",
    "append_long_memory_system_messages",
    "capture_startup_uagent_env_snapshot",
    "get_startup_uagent_env_snapshot",
    "load_dotenv_custom",
    "reload_dotenv_custom",
]
