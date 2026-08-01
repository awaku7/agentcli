from __future__ import annotations

from typing import Any

import importlib
import sys

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

TOOL_SPEC = {
    "tool_genre": "devel",
    "type": "function",
    "function": {
        "name": "system_reload",
        "description": _(
            "tool.description",
            default=(
                "Reload the system and reflect the latest code for all tools under tools/ (Python .py files) into memory. Run this after modifying code."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "reload system",
                "refresh tools",
                "reload code",
                "システムリロード",
                "recargar sistema",
                "recharger le système",
                "시스템 재로드",
                "перезагрузить систему",
            ],
        ),
        "x_search_terms_en": [
            "reload system",
            "refresh tools",
            "reload code",
            "システムリロード",
            "recargar sistema",
            "recharger le système",
            "시스템 재로드",
            "перезагрузить систему",
        ],
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}


# Background modules with thread/loop state that must be stopped BEFORE
# importlib.reload() so the old threads see their own stop event and exit
# cleanly. Reloading first would reset the module globals (e.g. _RUNNING,
# _STOP_EVENT) while the old listener threads keep running on stale closures.
# Each entry: (module_name, running_check(module)->bool, stop_callable(module))
_PRE_RELOAD_STOPPERS: list[tuple[str, Any, Any]] = [
    (
        "uagent.tools.pybitchat_shared",
        lambda m: bool(getattr(m, "_RUNNING", False)),
        lambda m: m.stop(),
    ),
    (
        "uagent.tools.echonet_shared",
        lambda m: getattr(m, "_LISTENER_THREAD", None) is not None,
        lambda m: m.stop(),
    ),
    (
        "uagent.tools.bacnet_shared",
        lambda m: getattr(m, "_BAC0_THREAD", None) is not None,
        lambda m: m.stop_bac0(),
    ),
    (
        "uagent.tools.switchbot_shared",
        lambda m: bool(getattr(m, "_POLLERS", {})),
        lambda m: m.stop(),
    ),
]


def _stop_running_backgrounds() -> list[str]:
    """Stop background services that are currently running, before reload.

    Returns the list of stopped service names (short module names).
    Modules not yet imported are skipped; they will be (re)loaded fresh.
    """
    stopped: list[str] = []
    for mod_name, running_check, stop_callable in _PRE_RELOAD_STOPPERS:
        mod = sys.modules.get(mod_name)
        if mod is None:
            continue
        try:
            if running_check(mod):
                stop_callable(mod)
                stopped.append(mod_name.rsplit(".", 1)[-1])
        except Exception:
            pass
    return stopped


def run_tool(args: dict[str, Any]) -> str:
    # Stop running background services (pybitchat, echonet, bacnet, switchbot)
    # BEFORE reload so old threads exit on their own stop event and module
    # globals like _RUNNING are not left inconsistent.
    stopped = _stop_running_backgrounds()
    try:
        pkg_name = __package__ or "src.uagent.tools"
        # importlib.reload() はサブモジュールを再帰的に再ロードしないため、
        # sys.modules に残った旧コード（例: pybitchat_shared.enqueue_send）が
        # ツールから参照され続ける。パッケージ再ロード前にサブモジュールを
        # sys.modules から外し、__init__.py のインポートで最新コードを
        # 再インポートさせる。
        for name in list(sys.modules):
            if name.startswith(pkg_name + "."):
                sys.modules.pop(name, None)
        mod = sys.modules.get(pkg_name)
        if mod is None:
            mod = importlib.import_module(pkg_name)
        importlib.reload(mod)
        # reload後はsys.modulesから新しいモジュールを再取得（mod変数は古いまま）
        new_mod = sys.modules.get(pkg_name)
        new_mod._INITIALIZED = False
        new_mod._DYNAMIC_COMMANDS.clear()
        new_mod._load_plugins()
        new_mod._INITIALIZED = True
        msg = "System reload successful. All tools were reloaded with the latest code."
        if stopped:
            msg += " Stopped before reload: " + ", ".join(sorted(stopped)) + "."
        return msg
    except Exception as e:
        return f"Error during system reload: {str(e)}"
