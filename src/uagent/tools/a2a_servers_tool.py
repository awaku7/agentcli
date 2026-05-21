from __future__ import annotations

# src/uagent/tools/a2a_servers_tool.py

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from ..utils.paths import get_state_dir
from .arg_util import get_bool, get_int, get_str
from .context import get_callbacks
from .i18n_helper import make_tool_translator
from .secrets_tool import decrypt_from_b64, encrypt_to_b64
from . import secrets_tool

_ = make_tool_translator(__file__)


def _cfg_path() -> Path:
    return get_state_dir() / "a2a" / "a2a_servers.json"


def _ensure_parent(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)


def _json_ok(**obj: Any) -> str:
    out: Dict[str, Any] = {"ok": True}
    out.update(obj)
    return json.dumps(out, ensure_ascii=False)


def _json_err(message: str, **extra: Any) -> str:
    out: Dict[str, Any] = {"ok": False, "error": message}
    out.update(extra)
    return json.dumps(out, ensure_ascii=False)


def _load_cfg(create_if_missing: bool = False) -> Dict[str, Any]:
    p = _cfg_path()
    if not p.exists():
        if create_if_missing:
            return {"version": 1, "default": None, "servers": []}
        raise FileNotFoundError(str(p))
    return json.loads(p.read_text(encoding="utf-8"))


def _write_cfg(cfg: Dict[str, Any]) -> None:
    p = _cfg_path()
    _ensure_parent(p)
    p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _find_server(cfg: Dict[str, Any], name: str) -> Tuple[Dict[str, Any], int]:
    for i, s in enumerate(cfg.get("servers") or []):
        if (s.get("name") or "") == name:
            return s, i
    raise KeyError(name)


def _parse_a2a_uri(s: str) -> Optional[str]:
    ss = (s or "").strip()
    if ss.lower().startswith("a2a://"):
        rest = ss[6:].lstrip("/")
        return rest or None
    return None


def resolve_profile(name_or_uri: Optional[str]) -> Dict[str, Any]:
    cfg = _load_cfg(create_if_missing=False)

    target = name_or_uri
    if not target:
        target = cfg.get("default")
    if not target:
        raise ValueError("No default profile")

    name = _parse_a2a_uri(str(target)) or str(target)
    name = name.strip()
    if not name:
        raise ValueError("Empty name")

    s, _i = _find_server(cfg, name)

    out = dict(s)
    out.setdefault("timeout_s", 300)
    out.setdefault("interval_ms", 500)

    # Decrypt token if present in enc_v1 form.
    tok = out.get("token")
    if isinstance(tok, dict) and isinstance(tok.get("enc_v1"), str):
        out["token"] = decrypt_from_b64(tok["enc_v1"])

    return out


TOOL_SPEC: Dict[str, Any] = {
    "load_order": 9000,
    "type": "function",
    "function": {
        "name": "a2a_servers",
        "description": _(
            "tool.description",
            default="Manage A2A server profiles under the uagent state dir (~/.uag/a2a/a2a_servers.json).",
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default="Operate on A2A server profile list. Return JSON only.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "a2a_servers",
                "a2a servers",
                "server profile",
                "server profiles",
                "profile manager",
                "manage profiles",
                "profile list",
                "server list",
                "profile settings",
                "a2a profile",
            ],
        ),
        "x_search_terms_en": [
            "a2a_servers",
            "a2a servers",
            "server profile",
            "server profiles",
            "profile manager",
            "manage profiles",
            "profile list",
            "server list",
            "profile settings",
            "a2a profile",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": _(
                        "param.action.description",
                        default="Action: init/list/add/remove/set_default/get/resolve",
                    ),
                },
                "name": {
                    "type": "string",
                    "description": _(
                        "param.name.description",
                        default="Profile name (or a2a://name for get/resolve).",
                    ),
                },
                "base_url": {
                    "type": "string",
                    "description": _(
                        "param.base_url.description",
                        default="Server base URL (e.g. http://127.0.0.1:8765).",
                    ),
                },
                "token": {
                    "type": "string",
                    "description": _(
                        "param.token.description",
                        default="Bearer token (plaintext). It will be encrypted before storing.",
                    ),
                },
                "timeout_s": {
                    "type": "integer",
                    "description": _(
                        "param.timeout_s.description",
                        default="Profile timeout in seconds.",
                    ),
                },
                "interval_ms": {
                    "type": "integer",
                    "description": _(
                        "param.interval_ms.description",
                        default="Polling interval in milliseconds.",
                    ),
                },
                "set_default": {
                    "type": "boolean",
                    "description": _(
                        "param.set_default.description",
                        default="(add) Set as default profile.",
                    ),
                    "default": False,
                },
                "force": {
                    "type": "boolean",
                    "description": _(
                        "param.force.description",
                        default="(init) Overwrite existing config.",
                    ),
                    "default": False,
                },
            },
            "required": ["action"],
            "additionalProperties": False,
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    cb = get_callbacks()
    if cb.set_status:
        cb.set_status(True, "tool:a2a_servers")
    try:
        action = get_str(args, "action", "").lower()

        if action == "init":
            force = get_bool(args, "force", False)
            p = _cfg_path()
            if p.exists() and not force:
                return _json_ok(path=str(p), existed=True)

            cfg: Dict[str, Any] = {"version": 1, "default": "local", "servers": []}
            cfg["servers"].append(
                {
                    "name": "local",
                    "base_url": "http://127.0.0.1:8765",
                    "token": None,
                    "timeout_s": 300,
                    "interval_ms": 500,
                }
            )
            _write_cfg(cfg)
            return _json_ok(path=str(p), created=True)

        if action == "list":
            cfg = _load_cfg(create_if_missing=False)
            servers = []
            for s in cfg.get("servers") or []:
                servers.append(
                    {
                        "name": s.get("name"),
                        "base_url": s.get("base_url"),
                        "has_token": bool(s.get("token")),
                        "timeout_s": s.get("timeout_s"),
                        "interval_ms": s.get("interval_ms"),
                    }
                )
            return _json_ok(
                path=str(_cfg_path()), default=cfg.get("default"), servers=servers
            )

        if action == "add":
            cfg = _load_cfg(create_if_missing=True)
            name = get_str(args, "name", "")
            base_url = get_str(args, "base_url", "")
            if not name or not base_url:
                return _json_err(
                    _(
                        "err.missing_name_or_base_url",
                        default="Missing 'name' or 'base_url'.",
                    )
                )

            token_plain = get_str(args, "token", "")
            token_obj = None
            if token_plain:
                try:
                    token_obj = {"enc_v1": encrypt_to_b64(token_plain)}
                except FileNotFoundError:
                    # Secret key missing; initialize and retry.
                    # Do not overwrite if it already exists.
                    secrets_tool.run_tool({"action": "init", "overwrite": False})
                    token_obj = {"enc_v1": encrypt_to_b64(token_plain)}

            timeout_s = get_int(args, "timeout_s", 300)
            interval_ms = get_int(args, "interval_ms", 500)
            set_default = get_bool(args, "set_default", False)

            new_obj: Dict[str, Any] = {
                "name": name,
                "base_url": base_url,
                "token": token_obj,
                "timeout_s": int(timeout_s),
                "interval_ms": int(interval_ms),
            }

            servers = cfg.get("servers") or []
            replaced = False
            for i, s in enumerate(servers):
                if (s.get("name") or "") == name:
                    servers[i] = new_obj
                    replaced = True
                    break
            if not replaced:
                servers.append(new_obj)
            cfg["servers"] = servers

            if set_default or not cfg.get("default"):
                cfg["default"] = name

            _write_cfg(cfg)
            return _json_ok(
                path=str(_cfg_path()), replaced=replaced, default=cfg.get("default")
            )

        if action == "remove":
            cfg = _load_cfg(create_if_missing=False)
            name = get_str(args, "name", "")
            if not name:
                return _json_err(_("err.missing_name", default="Missing 'name'."))
            before = len(cfg.get("servers") or [])
            servers = [
                s for s in (cfg.get("servers") or []) if (s.get("name") or "") != name
            ]
            if len(servers) == before:
                return _json_err(_("err.not_found", default="Not found."), name=name)
            cfg["servers"] = servers
            if cfg.get("default") == name:
                cfg["default"] = servers[0]["name"] if servers else None
            _write_cfg(cfg)
            return _json_ok(default=cfg.get("default"))

        if action == "set_default":
            cfg = _load_cfg(create_if_missing=False)
            name = get_str(args, "name", "")
            if not name:
                return _json_err(_("err.missing_name", default="Missing 'name'."))
            _find_server(cfg, name)
            cfg["default"] = name
            _write_cfg(cfg)
            return _json_ok(default=cfg.get("default"))

        if action in ("get", "resolve"):
            name_or_uri = get_str(args, "name", "")
            prof = resolve_profile(name_or_uri or None)
            # return decrypted token too (caller may need it)
            return _json_ok(profile=prof)

        return _json_err(
            _("err.unknown_action", default="Unknown action."), action=action
        )

    except FileNotFoundError:
        return _json_err(
            _(
                "err.config_not_found",
                default="Config not found. Run action=init first.",
            ),
            path=str(_cfg_path()),
        )
    except Exception as e:
        return _json_err(
            _("err.exception", default="Exception"),
            exception=type(e).__name__,
            detail=str(e),
        )
    finally:
        if cb.set_status:
            cb.set_status(False, "tool:a2a_servers")
