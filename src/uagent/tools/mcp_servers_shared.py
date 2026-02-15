# MCP configuration shared utilities
from __future__ import annotations

import os
import json


def get_default_mcp_config_path() -> str:
    """
    MCP サーバー設定ファイルのデフォルトパスを返します。
    優先順位:
    1. 環境変数 UAGENT_MCP_CONFIG
    2. <state>/mcps/mcp_servers.json (既定: ~/.uag（旧: ~/.scheck）/mcps/mcp_servers.json)
    """
    from uagent.utils.paths import get_mcp_servers_json_path

    return str(get_mcp_servers_json_path())


def ensure_mcp_config_template() -> str:
    """
    標準の場所 (<state>/mcps/mcp_servers.json。既定: ~/.uag（旧: ~/.scheck）/mcps/mcp_servers.json) が存在しない場合のみ、
    デフォルトの雛形を作成します。
    作成した（または既に存在していた）パスを返します。
    """
    # NOTE: テンプレートは『標準の場所』にのみ作成する（従来挙動維持）。
    # env(UAGENT_MCP_CONFIG) 指定先へ勝手に書き込まない。
    from uagent.utils.paths import get_mcps_dir

    path = str(get_mcps_dir() / "mcp_servers.json")

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
