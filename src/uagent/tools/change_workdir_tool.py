from typing import Dict, Any

# ツールのメタ情報を定義 (tools/__init__.py が読み込む)
TOOL_SPEC: Dict[str, Any] = {
    "type": "function",  # ★ OpenAI / Azure に渡すときに必須
    "function": {
        "name": "change_workdir",
        "description": "現在の作業ディレクトリをユーザー確認の後変更します。",
        "system_prompt": """このツールは次の目的で使われます: 現在の作業ディレクトリをユーザー確認の後変更します。""",
        "parameters": {
            "type": "object",
            "properties": {
                "new_dir": {
                    "type": "string",
                    "description": "変更先の新しいディレクトリパス。必須。",
                },
                "confirm": {
                    "type": "boolean",
                    "description": "ユーザー確認を行うかどうか。デフォルトは True。",
                    "default": True,
                },
            },
            "required": ["new_dir"],
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
    LLM からのツール呼び出しを受け、現在の作業ディレクトリを変更します。
    """
    import os
    import json

    new_dir = args.get("new_dir")
    confirm = args.get("confirm", True)

    if confirm:
        from .human_ask_tool import run_tool as human_ask_run

        message = f"作業ディレクトリを '{new_dir}' に変更しますか？ (yes/no)"
        response = human_ask_run({"message": message})
        payload = json.loads(response)
        user_reply = payload.get("user_reply", "").strip().lower()
        cancelled = payload.get("cancelled", False)
        if cancelled or user_reply not in ["yes", "y", "はい"]:
            return "変更をキャンセルしました。"

    os.chdir(new_dir)
    return f"作業ディレクトリを '{new_dir}' に変更しました。"


# 直接実行した場合の動作 (テスト用、ツールチェインからは呼ばれない)
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        new_dir = sys.argv[1]
        confirm = len(sys.argv) > 2 and sys.argv[2].lower() == "true"
        print(run_tool({"new_dir": new_dir, "confirm": confirm}))
    else:
        print("Usage: python change_workdir.py <new_dir> [confirm]")
