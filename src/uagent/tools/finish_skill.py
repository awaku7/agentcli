import json

def run_tool(args):
    """
    現在実行中のスキルのタスクが完了したことを宣言し、スキルに関連するシステム命令を解除します。
    このツールを呼び出した後は、追加の操作を行わずに終了してください。
    """
    return json.dumps({
        "status": "success",
        "message": "Skill session finished. System instructions for the skill have been cleared."
    })
