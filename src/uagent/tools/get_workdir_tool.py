from .i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)

from typing import Dict, Any

# ツールのメタ情報を定義 (tools/__init__.py が読み込む)
TOOL_SPEC: Dict[str, Any] = {
    "type": "function",  # ★ OpenAI / Azure に渡すときに必須
    "function": {
        "name": "get_workdir",
        "description": "現在の作業ディレクトリを取得します。",
        "system_prompt": """このツールは次の目的で使われます: 現在の作業ディレクトリを取得します。""",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
    # このツールはユーザーに直接見せるコンテンツを生成しない、というメタ情報（任意）
    "is_agent_content": False,
}

# Busy 状態にするかどうか (このツールは高速なので False に設定)
BUSY_LABEL = False


def run_tool(args: Dict[str, Any]) -> str:
    """
    LLM からのツール呼び出しを受け、現在の作業ディレクトリを取得して返します。
    """
    import os

    return os.getcwd()


# 直接実行した場合の動作 (テスト用、ツールチェインからは呼ばれない)
if __name__ == "__main__":
    print(run_tool({}))
