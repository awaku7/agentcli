# tools/__init__.py
import os
import sys
import json
import re
from datetime import datetime
import importlib.util
from importlib import import_module, reload
from pkgutil import iter_modules
from typing import Any, Dict, List, Callable

from .context import ToolCallbacks, get_callbacks, init_callbacks as _init_callbacks

# LLM に渡すための生のツール定義一覧
TOOL_SPECS: List[Dict[str, Any]] = []

# 実行用ランナー
_RUNNERS: Dict[str, Callable[[Dict[str, Any]], str]] = {}

# Busy 状態ラベルを立てるツール
#  key: tool_name, value: status_label (例: "tool:cmd_exec")
_BUSY_LABEL_TOOLS: Dict[str, str] = {}


# ------------------------------
# Tool trace (stdout only)
# ------------------------------

_SECRET_KEY_PATTERNS = [
    re.compile(pat, re.IGNORECASE)
    for pat in (
        r"pass(word)?",
        r"pwd",
        r"token",
        r"secret",
        r"api[_-]?key",
        r"access[_-]?key",
        r"private[_-]?key",
        r"bearer",
        r"authorization",
        r"auth[_-]?token",
        r"credential",
        r"cookie",
        r"session",
        r"sas",
        r"signature",
        r"user[_-]?reply",  # human_ask の生回答
    )
]


def _looks_like_secret_key(key: str) -> bool:
    if not key:
        return False
    ks = str(key).lower()
    if ks in ("is_password", "use_password", "enable_password", "mask"):
        return False
    return any(p.search(ks) for p in _SECRET_KEY_PATTERNS)


def _mask_value(v: Any) -> Any:
    if v is None:
        return None
    return "********"


def _mask_args(args: Any) -> Any:
    """引数を再帰的に走査し、機密情報をマスクする。"""
    if isinstance(args, dict):
        out: Dict[str, Any] = {}
        for k, v in args.items():
            ks = str(k)
            if _looks_like_secret_key(ks):
                out[k] = _mask_value(v)
            else:
                out[k] = _mask_args(v)
        return out
    elif isinstance(args, list):
        return [_mask_args(item) for item in args]
    elif isinstance(args, str) and len(args) > 300:
        return args[:20] + "...(truncated)..." + args[-20:]
    else:
        return args


def _emit_tool_trace(name: str, args: Dict[str, Any]) -> None:
    """ツール実行前に『何をするか』を1行で標準出力へ出す。"""
    try:
        masked = _mask_args(args or {})
        try:
            arg_str = json.dumps(
                masked, ensure_ascii=False, separators=(",", ":"), sort_keys=True
            )
        except Exception:
            arg_str = str(masked)

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[TOOL] {ts} name={name} args={arg_str}", flush=True)
    except Exception:
        return


# ------------------------------
# framework
# ------------------------------


def init_callbacks(callbacks: ToolCallbacks) -> None:
    """ホスト側からコールバック群を注入する。"""
    _init_callbacks(callbacks)


def _safe_set_status(busy: bool, label: str = "") -> None:
    cb = get_callbacks().set_status
    if cb is None:
        return
    try:
        cb(busy, label)
    except Exception:
        # UI 表示に失敗してもツール実行自体は継続
        return


def _register_tool_module(mod: Any, mod_name: str) -> bool:
    """モジュールをツールとして登録する。"""
    spec = getattr(mod, "TOOL_SPEC", None)
    runner = getattr(mod, "run_tool", None)

    if not isinstance(spec, dict) or not callable(runner):
        return False

    func_info = spec.get("function", {})
    tool_name = func_info.get("name")
    if not tool_name:
        return False

    # 既存の同名ツールがあれば削除して上書き
    for i, existing in enumerate(TOOL_SPECS):
        if existing.get("function", {}).get("name") == tool_name:
            TOOL_SPECS.pop(i)
            break

    TOOL_SPECS.append(spec)
    _RUNNERS[tool_name] = runner

    # Busy ラベル設定
    busy_flag = getattr(mod, "BUSY_LABEL", False)
    if busy_flag:
        status_label = getattr(mod, "STATUS_LABEL", f"tool:{tool_name}")
        _BUSY_LABEL_TOOLS[tool_name] = status_label
    return True


def _load_plugins() -> None:
    """
    tools/ 以下のプラグインモジュールを走査して、
    TOOL_SPECS / _RUNNERS / _BUSY_LABEL_TOOLS を構築する。
    """
    TOOL_SPECS.clear()
    _RUNNERS.clear()
    _BUSY_LABEL_TOOLS.clear()

    # 1. 内部ツールのロード
    pkg_dir = os.path.dirname(__file__)
    for m in iter_modules([pkg_dir]):
        if m.name.startswith("_") or m.name == "context":
            continue

        mod_name = f"{__name__}.{m.name}"
        try:
            if mod_name in sys.modules:
                mod = reload(sys.modules[mod_name])
            else:
                mod = import_module(mod_name)
            _register_tool_module(mod, mod_name)
        except Exception as e:
            print(
                f"[tools] 内部プラグイン {mod_name} のロード失敗: {e!r}",
                file=sys.stderr,
            )

    # 2. 外部ツールのロード (UAGENT_EXTERNAL_TOOLS_DIR)
    ext_dir = os.environ.get("UAGENT_EXTERNAL_TOOLS_DIR")
    if ext_dir and os.path.isdir(ext_dir):
        for entry in os.scandir(ext_dir):
            if (
                entry.is_file()
                and entry.name.endswith(".py")
                and not entry.name.startswith("_")
            ):
                mod_name = f"external_tool_{entry.name[:-3]}"
                try:
                    spec = importlib.util.spec_from_file_location(mod_name, entry.path)
                    if spec and spec.loader:
                        mod = importlib.util.module_from_spec(spec)
                        sys.modules[mod_name] = mod
                        spec.loader.exec_module(mod)
                        if _register_tool_module(mod, mod_name):
                            print(
                                f"[tools] 外部ツールをロードしました: {entry.name}",
                                file=sys.stderr,
                            )
                except Exception as e:
                    print(
                        f"[tools] 外部プラグイン {entry.path} のロード失敗: {e!r}",
                        file=sys.stderr,
                    )

    if TOOL_SPECS:
        names = [s["function"]["name"] for s in TOOL_SPECS]
        print(f"[tools] ロードされたツール: {', '.join(names)}", file=sys.stderr)
    else:
        print("[tools] 有効なツールが見つかりませんでした。", file=sys.stderr)


def get_tool_specs() -> List[Dict[str, Any]]:
    """LLM 用のツール定義一覧を取得する。"""
    # OpenAI/Azure API スキーマに準拠するため、独自拡張フィールド(system_prompt等)を除去する。
    #
    # 重要:
    # - Chat Completions / Responses のどちらも "tools" はトップレベルに "name" を持たない。
    #   正式な形は: {"type":"function","function":{"name":..., ...}}
    # - しかし一部SDK/プロキシ/互換層で "tools[i].name" を要求するケースがある。
    #   （今回の 400: Missing required parameter: 'tools[0].name' がそれ）
    #   その場合でも壊れないよう、冗長だがトップレベルに name を付与しておく。
    clean_specs: List[Dict[str, Any]] = []
    for spec in TOOL_SPECS:
        # 浅いコピーでトップレベルを複製
        spec_copy = spec.copy()
        if "function" in spec_copy and isinstance(spec_copy["function"], dict):
            # function 辞書も複製して編集
            func_copy = spec_copy["function"].copy()
            func_copy.pop("system_prompt", None)
            spec_copy["function"] = func_copy

            # --- compatibility: mirror name to top-level ---
            fn_name = func_copy.get("name")
            if fn_name and not spec_copy.get("name"):
                spec_copy["name"] = fn_name

        clean_specs.append(spec_copy)
    return clean_specs


def reload_plugins() -> None:
    """将来の拡張用: ツールプラグイン群を再ロードする。"""
    _load_plugins()


def run_tool(name: str, args: Dict[str, Any]) -> str:
    """ChatCompletion からの tool_call を実際に実行するエントリポイント。"""
    runner = _RUNNERS.get(name)
    if runner is None:
        return f"[tool error] unknown tool: {name}"

    # ---- trace (pre) ----
    # TOOL_SPEC 側の拡張フラグで [TOOL] ログを抑制できるようにする。
    # 既定: 抑制しない（従来互換）
    try:
        spec = next(
            (s for s in TOOL_SPECS if s.get("function", {}).get("name") == name),
            None,
        )
        x_scheck = (spec or {}).get("function", {}).get("x_scheck", {})
        emit_trace = True
        if isinstance(x_scheck, dict):
            if x_scheck.get("emit_tool_trace") is False:
                emit_trace = False
        if emit_trace:
            _emit_tool_trace(name, args)
    except Exception:
        # ここでの例外はツール実行を妨げない
        _emit_tool_trace(name, args)

    # human_ask 中は Busy を解除（入力待ちになるため）。
    # ただし、実行後は LLM に復帰させないと GUI 側が IDLE のままに見える。
    if name == "human_ask":
        # human_ask は内部で active 状態を立ててから Busy を解除する必要があるため、
        # ここでは自動で解除せず、runner 側の実装に任せる。
        try:
            return runner(args)
        finally:
            # human_ask 完了後は LLM に戻す（GUI が IDLE 固定に見えるのを防ぐ）
            _safe_set_status(True, "LLM")

    # Busy ラベル付きツール
    status_label = _BUSY_LABEL_TOOLS.get(name)
    if status_label is not None:
        _safe_set_status(True, status_label)
        try:
            return runner(args)
        finally:
            # ツール呼び出しが終わったら、LLM 処理中に戻す
            _safe_set_status(True, "LLM")

    # それ以外はステータスをいじらずそのまま
    return runner(args)


# モジュール import 時に一度だけ読み込む
_load_plugins()
