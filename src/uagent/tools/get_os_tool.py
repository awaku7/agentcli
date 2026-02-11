import platform
from typing import Dict, Any

# ツールのメタ情報を定義 (tools/__init__.py が読み込む)
TOOL_SPEC: Dict[str, Any] = {
    "type": "function",  # ★ OpenAI / Azure に渡すときに必須
    "function": {
        "name": "get_os",
        "description": "現在利用中のOSの種類を取得します（例: Windows, Linux, Darwin など）。",
        "system_prompt": """このツールは次の目的で使われます: 現在利用中のOSの種類を取得します（例: Windows, Linux, Darwin など）。""",
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
    LLM からのツール呼び出しを受け、OS名を取得して JSON 文字列として返します。
    例: {"os_name": "Windows"}
    """
    os_name = platform.system()
    # 必要なら今後フィールドを足せるように JSON 形式で返す
    return f'{{"os_name": "{os_name}"}}'


# 直接実行した場合の動作 (テスト用、ツールチェインからは呼ばれない)
if __name__ == "__main__":
    print(run_tool({}))
