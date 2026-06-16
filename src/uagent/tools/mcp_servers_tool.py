from __future__ import annotations

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

import json
import os
from typing import Any

try:
    from .mcp_servers_shared import get_default_mcp_config_path
except Exception:  # pragma: no cover

    def get_default_mcp_config_path() -> str:
        return "mcp_servers.json"


TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "tool_genre": "external",
    "function": {
        "name": "mcp_servers",
        "description": _(
            "tool.description",
            default="Manage MCP server definitions in mcp_servers.json (list/add/remove/set_default/validate/init_template).",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "mcp_servers",
                "mcp servers",
                "mcp server",
                "manage servers",
                "server profile",
                "mcp config",
            ],
        ),
        "x_search_terms_en": [
            "mcp_servers",
            "mcp servers",
            "mcp server",
            "manage servers",
            "server profile",
            "mcp config",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": _(
                        "param.action.description",
                        default=(
                            "Operation to perform. One of: list/add/remove/set_default/validate/init_template."
                        ),
                    ),
                    "enum": [
                        "list",
                        "add",
                        "remove",
                        "set_default",
                        "validate",
                        "init_template",
                    ],
                },
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Path to mcp_servers.json. If omitted, uses the default location.",
                    ),
                },
                "pretty": {
                    "type": "boolean",
                    "description": _(
                        "param.pretty.description",
                        default="If true, pretty-print JSON output (default: true).",
                    ),
                    "default": True,
                },
                # list
                "validate": {
                    "type": "boolean",
                    "description": _(
                        "param.validate.description",
                        default="(list) If true, add basic validation warnings (default: true).",
                    ),
                    "default": True,
                },
                "default_only": {
                    "type": "boolean",
                    "description": _(
                        "param.default_only.description",
                        default="(list) If true, return only the default server (index 0).",
                    ),
                    "default": False,
                },
                # validate
                "fail_on_warning": {
                    "type": "boolean",
                    "description": _(
                        "param.fail_on_warning.description",
                        default="(validate) If true, overall=FAIL when there is any warning.",
                    ),
                    "default": False,
                },
                # add
                "name": {
                    "type": "string",
                    "description": _(
                        "param.name.description",
                        default="(add/remove) Server name (mcp_servers[].name).",
                    ),
                },
                "url": {
                    "type": "string",
                    "description": _(
                        "param.url.description",
                        default="(add) MCP endpoint URL for HTTP(SSE) servers.",
                    ),
                },
                "command": {
                    "type": "string",
                    "description": _(
                        "param.command.description",
                        default="(add) Command for stdio servers.",
                    ),
                },
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": _(
                        "param.args.description",
                        default="(add) Args for stdio servers.",
                    ),
                },
                "env": {
                    "type": "object",
                    "description": _(
                        "param.env.description",
                        default="(add) Env vars mapping for stdio servers.",
                    ),
                    "additionalProperties": True,
                },
                "transport": {
                    "type": "string",
                    "description": _(
                        "param.transport.description",
                        default="(add/init_template) Transport (informational).",
                    ),
                    "default": "streamable-http",
                },
                "set_default": {
                    "type": "boolean",
                    "description": _(
                        "param.set_default.description",
                        default="(add) If true, move the added/updated server to index 0.",
                    ),
                    "default": False,
                },
                "replace": {
                    "type": "boolean",
                    "description": _(
                        "param.replace.description",
                        default="(add) If true, overwrite an existing entry with the same name.",
                    ),
                    "default": False,
                },
                "create_if_missing": {
                    "type": "boolean",
                    "description": _(
                        "param.create_if_missing.description",
                        default="(add/set_default) If true, create missing config as empty.",
                    ),
                    "default": True,
                },
                # remove
                "index": {
                    "type": "integer",
                    "description": _(
                        "param.index.description",
                        default="(remove) Index to remove. If specified with name, index takes priority.",
                    ),
                },
                "require_nonempty": {
                    "type": "boolean",
                    "description": _(
                        "param.require_nonempty.description",
                        default="(remove) If true, prevent removal if it would make the list empty.",
                    ),
                    "default": False,
                },
                # set_default
                "server_name": {
                    "type": "string",
                    "description": _(
                        "param.server_name.description",
                        default="(set_default) The server name to set as default.",
                    ),
                },
                # init_template
                "default_name": {
                    "type": "string",
                    "description": _(
                        "param.default_name.description",
                        default="(init_template) Default server name.",
                    ),
                    "default": "bluesky-local",
                },
                "default_url": {
                    "type": "string",
                    "description": _(
                        "param.default_url.description",
                        default="(init_template) Default URL.",
                    ),
                    "default": "",
                },
            },
            "required": ["action"],
        },
    },
}


def _json_out(obj: dict[str, Any], *, pretty: bool) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2 if pretty else None) + (
        "\n" if pretty else ""
    )


def _load_config(
    path: str,
    *,
    create_if_missing: bool,
    missing_is_error: bool,
) -> tuple[dict[str, Any], list[str], list[str]]:
    """Load config.

    Returns: (data, warnings, errors)

    - When missing_is_error=False, missing file is treated as empty list with WARNING.
    """

    warnings: list[str] = []
    errors: list[str] = []

    if not os.path.exists(path):
        if missing_is_error and not create_if_missing:
            errors.append(
                _("err.not_exists", default="ERROR: {path!r} does not exist").format(
                    path=path
                )
            )
            return {"mcp_servers": []}, warnings, errors

        if missing_is_error and create_if_missing:
            warnings.append(
                _(
                    "warn.not_exists_new",
                    default="WARNING: {path!r} does not exist; treating as empty/new.",
                ).format(path=path)
            )
            return {"mcp_servers": []}, warnings, errors

        warnings.append(
            _(
                "warn.not_exists",
                default="WARNING: {path!r} does not exist (treating as empty list).",
            ).format(path=path)
        )
        return {"mcp_servers": []}, warnings, errors

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        errors.append(
            _(
                "err.load_fail",
                default="ERROR: Failed to load {path!r}: {err}",
            ).format(path=path, err=e)
        )
        return {"mcp_servers": []}, warnings, errors

    if not isinstance(data, dict):
        errors.append(_("err.root_not_dict", default="ERROR: root is not a dictionary"))
        return {"mcp_servers": []}, warnings, errors

    servers = data.get("mcp_servers")
    if servers is None:
        warnings.append(
            _(
                "warn.no_mcp_servers",
                default="WARNING: 'mcp_servers' key is missing (treating as empty list).",
            )
        )
        servers = []

    if not isinstance(servers, list):
        errors.append(
            _("err.mcp_servers_not_list", default="ERROR: 'mcp_servers' is not a list")
        )
        servers = []

    data["mcp_servers"] = servers
    return data, warnings, errors


def _save_config(path: str, data: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _validate_servers_for_list(servers: list[Any]) -> list[str]:
    warnings: list[str] = []
    seen: dict[str, int] = {}

    for idx, s in enumerate(servers):
        if not isinstance(s, dict):
            warnings.append(
                _(
                    "warn.item_not_dict",
                    default="WARNING: mcp_servers[{idx}] is not a dictionary.",
                ).format(idx=idx)
            )
            continue

        name = s.get("name")
        url = s.get("url")
        command = s.get("command")

        if not isinstance(name, str) or not name.strip():
            warnings.append(
                _(
                    "warn.name_missing",
                    default="WARNING: mcp_servers[{idx}].name is missing or empty.",
                ).format(idx=idx)
            )
        else:
            seen[name] = seen.get(name, 0) + 1

        # http server
        if isinstance(url, str) and url.strip():
            if not url.rstrip().endswith("/mcp"):
                warnings.append(
                    _(
                        "warn.url_no_mcp",
                        default="WARNING: mcp_servers[{idx}].url={url!r} does not end with '/mcp'. (handle_mcp_v2 / mcp_tools_list will auto-append, but explicit suffix is recommended)",
                    ).format(idx=idx, url=url)
                )
        # stdio server
        elif isinstance(command, str) and command.strip():
            pass
        else:
            warnings.append(
                _(
                    "warn.endpoint_missing",
                    default="WARNING: mcp_servers[{idx}] has neither url nor command.",
                ).format(idx=idx)
            )

    for n, c in seen.items():
        if c > 1:
            warnings.append(
                _(
                    "warn.name_duplicate",
                    default="WARNING: name={name!r} is duplicated ({count} times).",
                ).format(name=n, count=c)
            )

    return warnings


def _validate_servers_strict(servers: list[Any]) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []

    seen: dict[str, int] = {}

    for idx, s in enumerate(servers):
        if not isinstance(s, dict):
            errors.append(
                _(
                    "err.item_not_dict",
                    default="ERROR: mcp_servers[{idx}] is not a dictionary",
                ).format(idx=idx)
            )
            continue

        name = s.get("name")
        url = s.get("url")
        command = s.get("command")

        if not isinstance(name, str) or not name.strip():
            errors.append(
                _(
                    "err.name_missing",
                    default="ERROR: mcp_servers[{idx}].name is missing or empty",
                ).format(idx=idx)
            )
        else:
            seen[name] = seen.get(name, 0) + 1

        has_http = isinstance(url, str) and url.strip()
        has_stdio = isinstance(command, str) and command.strip()

        if not has_http and not has_stdio:
            errors.append(
                _(
                    "err.endpoint_missing",
                    default="ERROR: mcp_servers[{idx}] must have either url or command",
                ).format(idx=idx)
            )

        if has_http and not str(url).rstrip().endswith("/mcp"):
            warnings.append(
                _(
                    "warn.url_no_mcp",
                    default="WARNING: mcp_servers[{idx}].url={url!r} does not end with '/mcp'. (handle_mcp_v2 / mcp_tools_list will auto-append, but explicit suffix is recommended)",
                ).format(idx=idx, url=url)
            )

    for n, c in seen.items():
        if c > 1:
            errors.append(
                _(
                    "err.name_duplicate",
                    default="ERROR: name={name!r} is duplicated ({count} times)",
                ).format(name=n, count=c)
            )

    return warnings, errors


def _run_action_init_template(
    args: dict[str, Any], *, pretty: bool, config_path: str
) -> str:
    action = "init_template"
    default_name = (
        str(args.get("default_name", "bluesky-local")).strip() or "bluesky-local"
    )
    default_url = str(args.get("default_url", "")).strip() or ""
    default_transport = (
        str(args.get("transport", "streamable-http")).strip() or "streamable-http"
    )

    if os.path.exists(config_path):
        return _json_out(
            {
                "ok": False,
                "action": action,
                "path": config_path,
                "error": "already exists",
            },
            pretty=pretty,
        )

    data: dict[str, Any] = {
        "mcp_servers": [
            {
                "name": default_name,
                "url": default_url,
                "transport": default_transport,
            }
        ]
    }

    try:
        _save_config(config_path, data)
    except Exception as e:
        return _json_out(
            {
                "ok": False,
                "action": action,
                "path": config_path,
                "error": f"failed to write: {type(e).__name__}: {e}",
            },
            pretty=pretty,
        )

    return _json_out(
        {
            "ok": True,
            "action": action,
            "path": config_path,
            "created": True,
            "default": data["mcp_servers"][0],
        },
        pretty=pretty,
    )


def _run_action_list(args: dict[str, Any], *, pretty: bool, config_path: str) -> str:
    action = "list"
    do_validate = bool(args.get("validate", True))
    default_only = bool(args.get("default_only", False))

    data, load_warn, load_err = _load_config(
        config_path, create_if_missing=False, missing_is_error=False
    )
    servers = data.get("mcp_servers") or []

    warnings = list(load_warn)
    errors = list(load_err)

    if do_validate:
        warnings.extend(_validate_servers_for_list(servers))

    view_servers = servers[:1] if default_only else servers

    out_obj: dict[str, Any] = {
        "ok": len(errors) == 0,
        "action": action,
        "path": config_path,
        "default_index": 0,
        "count": len(servers),
        "default": servers[0] if servers else None,
        "servers": view_servers,
        "warnings": warnings,
        "errors": errors,
    }

    return _json_out(out_obj, pretty=pretty)


def _run_action_validate(
    args: dict[str, Any], *, pretty: bool, config_path: str
) -> str:
    action = "validate"
    fail_on_warning = bool(args.get("fail_on_warning", False))

    data, load_warn, load_err = _load_config(
        config_path, create_if_missing=False, missing_is_error=True
    )
    servers: list[Any] = data.get("mcp_servers") or []

    warnings = list(load_warn)
    errors = list(load_err)

    v_warn, v_err = _validate_servers_strict(servers)
    warnings.extend(v_warn)
    errors.extend(v_err)

    overall = "OK"
    if errors:
        overall = "FAIL"
    elif warnings and fail_on_warning:
        overall = "FAIL"

    return _json_out(
        {
            "ok": overall == "OK",
            "action": action,
            "path": config_path,
            "overall": overall,
            "count": len(servers),
            "warnings": warnings,
            "errors": errors,
        },
        pretty=pretty,
    )


def _mcp_find_server_index_by_name(servers: list[Any], name: str) -> int | None:
    for i, s in enumerate(servers):
        if isinstance(s, dict) and s.get("name") == name:
            return i
    return None


def _mcp_build_server_entry(
    *,
    name: str,
    transport: str,
    url: Any,
    command: Any,
    arg_list: list[Any],
    env: dict[Any, Any],
) -> dict[str, Any]:
    new_entry: dict[str, Any] = {
        "name": name,
        "transport": transport,
    }
    if url:
        new_entry["url"] = str(url)
    if command:
        new_entry["command"] = str(command)
    if arg_list:
        new_entry["args"] = [str(x) for x in arg_list]
    if env:
        new_entry["env"] = {str(k): str(v) for k, v in env.items()}
    return new_entry


def _mcp_add_validate_and_normalize(
    *,
    action: str,
    pretty: bool,
    name: str,
    url: Any,
    command: Any,
    arg_list: Any,
    env: Any,
) -> tuple[list[Any] | None, dict[Any, Any] | None, str | None]:
    if not name:
        return (
            None,
            None,
            _json_out(
                {"ok": False, "action": action, "error": "name is required"},
                pretty=pretty,
            ),
        )

    if not url and not command:
        return (
            None,
            None,
            _json_out(
                {
                    "ok": False,
                    "action": action,
                    "error": "either url or command is required",
                },
                pretty=pretty,
            ),
        )

    normalized_args = [] if arg_list is None else arg_list
    normalized_env = {} if env is None else env

    if not isinstance(normalized_args, list):
        return (
            None,
            None,
            _json_out(
                {"ok": False, "action": action, "error": "args must be an array"},
                pretty=pretty,
            ),
        )
    if not isinstance(normalized_env, dict):
        return (
            None,
            None,
            _json_out(
                {"ok": False, "action": action, "error": "env must be an object"},
                pretty=pretty,
            ),
        )

    return normalized_args, normalized_env, None


def _mcp_upsert_server_entry(
    *,
    servers: list[Any],
    name: str,
    new_entry: dict[str, Any],
    replace: bool,
    action: str,
    pretty: bool,
    config_path: str,
) -> tuple[int | None, str | None]:
    idx = _mcp_find_server_index_by_name(servers, name)
    if idx is None:
        servers.append(new_entry)
        return len(servers) - 1, None

    if not replace:
        return None, _json_out(
            {
                "ok": False,
                "action": action,
                "error": "already exists (set replace=true to overwrite)",
                "path": config_path,
            },
            pretty=pretty,
        )

    servers[idx] = new_entry
    return idx, None


def _mcp_move_default_if_requested(
    servers: list[Any], *, idx: int, set_default: bool
) -> None:
    if set_default and idx != 0:
        servers.insert(0, servers.pop(idx))


def _mcp_load_servers_or_error(
    *,
    action: str,
    pretty: bool,
    config_path: str,
    create_if_missing: bool,
) -> tuple[dict[str, Any] | None, list[Any] | None, list[str], str | None]:
    data, load_warn, load_err = _load_config(
        config_path,
        create_if_missing=create_if_missing,
        missing_is_error=True,
    )
    if load_err:
        return (
            None,
            None,
            load_warn,
            _json_out(
                {
                    "ok": False,
                    "action": action,
                    "path": config_path,
                    "warnings": load_warn,
                    "errors": load_err,
                },
                pretty=pretty,
            ),
        )

    return data, data.get("mcp_servers") or [], load_warn, None


def _mcp_error_if_empty_servers(
    *,
    action: str,
    pretty: bool,
    config_path: str,
    load_warn: list[str],
    servers: list[Any],
) -> str | None:
    if servers:
        return None
    return _json_out(
        {
            "ok": False,
            "action": action,
            "path": config_path,
            "error": "mcp_servers is empty",
            "warnings": load_warn,
        },
        pretty=pretty,
    )


def _mcp_save_or_error(
    *,
    action: str,
    pretty: bool,
    config_path: str,
    data: dict[str, Any],
) -> str | None:
    try:
        _save_config(config_path, data)
    except Exception as e:
        return _json_out(
            {
                "ok": False,
                "action": action,
                "path": config_path,
                "error": f"failed to write: {type(e).__name__}: {e}",
            },
            pretty=pretty,
        )
    return None


def _run_action_add(args: dict[str, Any], *, pretty: bool, config_path: str) -> str:
    action = "add"
    name = str(args.get("name") or "").strip()
    url = args.get("url")
    command = args.get("command")
    arg_list = args.get("args")
    env = args.get("env")
    transport = str(args.get("transport") or "streamable-http")

    set_default = bool(args.get("set_default", False))
    replace = bool(args.get("replace", False))
    create_if_missing = bool(args.get("create_if_missing", True))

    normalized_args, normalized_env, input_err = _mcp_add_validate_and_normalize(
        action=action,
        pretty=pretty,
        name=name,
        url=url,
        command=command,
        arg_list=arg_list,
        env=env,
    )
    if input_err is not None:
        return input_err

    assert normalized_args is not None
    assert normalized_env is not None

    data, load_warn, _load_err = _load_config(
        config_path,
        create_if_missing=create_if_missing,
        missing_is_error=False,
    )
    servers = data.get("mcp_servers") or []

    new_entry = _mcp_build_server_entry(
        name=name,
        transport=transport,
        url=url,
        command=command,
        arg_list=normalized_args,
        env=normalized_env,
    )

    idx, upsert_err = _mcp_upsert_server_entry(
        servers=servers,
        name=name,
        new_entry=new_entry,
        replace=replace,
        action=action,
        pretty=pretty,
        config_path=config_path,
    )
    if upsert_err is not None:
        return upsert_err

    assert idx is not None
    _mcp_move_default_if_requested(servers, idx=idx, set_default=set_default)

    data["mcp_servers"] = servers
    write_err = _mcp_save_or_error(
        action=action,
        pretty=pretty,
        config_path=config_path,
        data=data,
    )
    if write_err is not None:
        return write_err

    return _json_out(
        {
            "ok": True,
            "action": action,
            "path": config_path,
            "count": len(servers),
            "warnings": load_warn,
        },
        pretty=pretty,
    )


def _mcp_resolve_remove_index(
    servers: list[Any],
    *,
    name: Any,
    index: Any,
    action: str,
    pretty: bool,
) -> tuple[int | None, str | None]:
    if index is not None:
        try:
            idx = int(index)
        except Exception:
            return None, _json_out(
                {"ok": False, "action": action, "error": "index must be int"},
                pretty=pretty,
            )
        if idx < 0 or idx >= len(servers):
            return None, _json_out(
                {
                    "ok": False,
                    "action": action,
                    "error": "index out of range",
                    "index": idx,
                },
                pretty=pretty,
            )
        return idx, None

    target = str(name).strip()
    for i, s in enumerate(servers):
        if isinstance(s, dict) and s.get("name") == target:
            return i, None

    return None, _json_out(
        {
            "ok": False,
            "action": action,
            "error": "name not found",
            "name": target,
        },
        pretty=pretty,
    )


def _run_action_remove(args: dict[str, Any], *, pretty: bool, config_path: str) -> str:
    action = "remove"
    name = args.get("name")
    index = args.get("index")
    require_nonempty = bool(args.get("require_nonempty", False))

    if index is None and (not isinstance(name, str) or not str(name).strip()):
        return _json_out(
            {
                "ok": False,
                "action": action,
                "error": "specify name or index",
            },
            pretty=pretty,
        )

    data, servers, load_warn, load_err_json = _mcp_load_servers_or_error(
        action=action,
        pretty=pretty,
        config_path=config_path,
        create_if_missing=False,
    )
    if load_err_json is not None:
        return load_err_json

    assert data is not None
    assert servers is not None

    empty_err = _mcp_error_if_empty_servers(
        action=action,
        pretty=pretty,
        config_path=config_path,
        load_warn=load_warn,
        servers=servers,
    )
    if empty_err is not None:
        return empty_err

    removed_idx, resolve_err = _mcp_resolve_remove_index(
        servers,
        name=name,
        index=index,
        action=action,
        pretty=pretty,
    )
    if resolve_err is not None:
        return resolve_err

    assert removed_idx is not None
    removed = servers.pop(removed_idx)

    if require_nonempty and not servers:
        return _json_out(
            {
                "ok": False,
                "action": action,
                "error": "require_nonempty=true prevents removing last item",
            },
            pretty=pretty,
        )

    data["mcp_servers"] = servers
    write_err = _mcp_save_or_error(
        action=action,
        pretty=pretty,
        config_path=config_path,
        data=data,
    )
    if write_err is not None:
        return write_err

    return _json_out(
        {
            "ok": True,
            "action": action,
            "path": config_path,
            "removed_index": removed_idx,
            "removed": removed,
            "count": len(servers),
            "default": servers[0] if servers else None,
            "warnings": load_warn,
        },
        pretty=pretty,
    )


def _run_action_set_default(
    args: dict[str, Any], *, pretty: bool, config_path: str
) -> str:
    action = "set_default"
    server_name = str(args.get("server_name") or "").strip()
    create_if_missing = bool(args.get("create_if_missing", True))

    if not server_name:
        return _json_out(
            {"ok": False, "action": action, "error": "server_name is required"},
            pretty=pretty,
        )

    data, servers, load_warn, load_err_json = _mcp_load_servers_or_error(
        action=action,
        pretty=pretty,
        config_path=config_path,
        create_if_missing=create_if_missing,
    )
    if load_err_json is not None:
        return load_err_json

    assert data is not None
    assert servers is not None

    empty_err = _mcp_error_if_empty_servers(
        action=action,
        pretty=pretty,
        config_path=config_path,
        load_warn=load_warn,
        servers=servers,
    )
    if empty_err is not None:
        return empty_err

    idx = _mcp_find_server_index_by_name(servers, server_name)
    if idx is None:
        return _json_out(
            {
                "ok": False,
                "action": action,
                "path": config_path,
                "error": "server_name not found",
                "server_name": server_name,
            },
            pretty=pretty,
        )

    if idx != 0:
        item = servers.pop(idx)
        servers.insert(0, item)
        data["mcp_servers"] = servers
        write_err = _mcp_save_or_error(
            action=action,
            pretty=pretty,
            config_path=config_path,
            data=data,
        )
        if write_err is not None:
            return write_err

    return _json_out(
        {
            "ok": True,
            "action": action,
            "path": config_path,
            "default": servers[0] if servers else None,
            "count": len(servers),
            "warnings": load_warn,
        },
        pretty=pretty,
    )


def run_tool(args: dict[str, Any]) -> str:
    args = args or {}

    action = str(args.get("action") or "").strip()
    pretty = bool(args.get("pretty", True))

    path = args.get("path")
    config_path = str(path or get_default_mcp_config_path())

    handlers = {
        "init_template": _run_action_init_template,
        "list": _run_action_list,
        "validate": _run_action_validate,
        "add": _run_action_add,
        "remove": _run_action_remove,
        "set_default": _run_action_set_default,
    }

    handler = handlers.get(action)
    if handler is None:
        return _json_out(
            {"ok": False, "error": "invalid action", "action": action}, pretty=pretty
        )

    return handler(args, pretty=pretty, config_path=config_path)
