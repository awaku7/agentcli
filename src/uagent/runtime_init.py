from .runtime_workdir import WorkdirDecision, apply_workdir, decide_workdir
from .runtime_banner import build_startup_banner
from .runtime_env import validate_or_exit_startup_env
from .runtime_memory import append_long_memory_system_messages


def load_dotenv_custom():
    try:
        from pathlib import Path
        from dotenv import load_dotenv

        # Only load the .env file in the current working directory.
        current_env = Path.cwd() / ".env"
        if current_env.exists():
            load_dotenv(current_env, override=False)
    except ImportError:
        pass


# 初期化時に実行
load_dotenv_custom()

__all__ = [
    "WorkdirDecision",
    "apply_workdir",
    "decide_workdir",
    "build_startup_banner",
    "validate_or_exit_startup_env",
    "append_long_memory_system_messages",
]
