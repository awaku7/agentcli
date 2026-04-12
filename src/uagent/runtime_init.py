import io
import sys
from pathlib import Path

from .runtime_banner import build_startup_banner
from .runtime_env import validate_or_exit_startup_env
from .runtime_memory import append_long_memory_system_messages
from .runtime_workdir import WorkdirDecision, apply_workdir, decide_workdir


def load_dotenv_custom():
    """Load .env and .env.sec from CWD."""
    try:
        from dotenv import load_dotenv

        cwd = Path.cwd()

        # 1. Load .env if exists (no override)
        env_path = cwd / ".env"
        if env_path.exists():
            load_dotenv(env_path, override=False)

        # 2. Load .env.sec if exists (encrypted env)
        sec_path = cwd / ".env.sec"
        if sec_path.exists():
            try:
                # Local import to avoid dependency issues if not used
                from uag_envsec.secret_core import decrypt_text

                # Prefer .uagent.key in CWD, fallback to default (~/.uag/uag_envsec_key)
                local_key = cwd / ".uagent.key"
                kp = str(local_key) if local_key.exists() else None

                body = sec_path.read_text(encoding="utf-8").strip()
                if body:
                    dec = decrypt_text(body, key_path=kp)
                    # Use override=True for secrets to ensure they take precedence
                    load_dotenv(stream=io.StringIO(dec), override=True)
            except Exception as e:
                # Always report decryption errors to stderr if it exists but fails
                print(
                    f"[WARN] Failed to decrypt .env.sec: {e}",
                    file=sys.stderr,
                )
    except ImportError:
        # python-dotenv not installed
        pass


# 実行時に即座に環境変数をロード
load_dotenv_custom()

__all__ = [
    "WorkdirDecision",
    "apply_workdir",
    "decide_workdir",
    "build_startup_banner",
    "validate_or_exit_startup_env",
    "append_long_memory_system_messages",
]
