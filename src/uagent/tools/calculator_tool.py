# src/scheck/tools/calculator_tool.py
from .i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)

from typing import Any, Dict
import math
from .context import get_callbacks

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "calculator",
        "description": "数式を計算して結果を返します。LLMが苦手な複雑な計算や精度の必要な計算に使用してください。",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "計算したい数式（例: '123 * (45 + 67)', 'sqrt(144)', 'sin(pi/2)'）。Pythonのmathモジュールの関数が使用可能です。",
                }
            },
            "required": ["expression"],
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    cb = get_callbacks()
    expression = args.get("expression", "")
    if not expression:
        return "[calculator]\nError: No expression provided."

    # mathモジュールの関数と定数を公開
    allowed_names = {k: v for k, v in math.__dict__.items() if not k.startswith("__")}
    # 基本的な組み込み関数も許可
    allowed_names.update(
        {
            "abs": abs,
            "round": round,
            "min": min,
            "max": max,
            "pow": pow,
            "sum": sum,
            "len": len,
        }
    )

    try:
        # eval を制限された環境で実行
        result = eval(expression, {"__builtins__": {}}, allowed_names)
        output = f"[calculator]\nExpression: {expression}\nResult: {result}"
    except Exception as e:
        output = f"[calculator]\nError: {type(e).__name__}: {e}"

    if cb.truncate_output:
        return cb.truncate_output("calculator", output, limit=1000)
    return output
