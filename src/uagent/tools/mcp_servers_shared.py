# MCP configuration shared utilities
from __future__ import annotations

import os
import json


def get_default_mcp_config_path() -> str:
    """
    MCP サーバー設定ファイルのデフォルトパスを返します。
    優先順位:
    1. 環境変数 UAGENT_MCP_CONFIG
    2. ~/.scheck/mcps/mcp_servers.json
    """
    # 1. 環境変数
    env_path = os.environ.get("UAGENT_MCP_CONFIG")
    if env_path:
        return os.path.abspath(os.path.expanduser(env_path))

    # 2. 標準の場所: ~/.scheck/mcps/mcp_servers.json
    # core.py の BASE_LOG_DIR 構成に合わせる
    base_dir = os.path.abspath(os.path.join(os.path.expanduser("~"), ".scheck", "mcps"))
    return os.path.join(base_dir, "mcp_servers.json")


def ensure_mcp_config_template() -> str:
    """
    標準の場所 (~/.scheck/mcps/mcp_servers.json) が存在しない場合のみ、
    デフォルトの雛形を作成します。
    作成した（または既に存在していた）パスを返します。
    """
    path = os.path.abspath(
        os.path.join(os.path.expanduser("~"), ".scheck", "mcps", "mcp_servers.json")
    )

    if os.path.exists(path):
        return path

    os.makedirs(os.path.dirname(path), exist_ok=True)

    data = {"mcp_servers": []}

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return path
