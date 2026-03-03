#!/usr/bin/env python3
"""Upload a wheel file to GitLab **Generic Package Registry** and optionally attach it to a GitLab Release.

This script is **GitLab-only**.
It uploads *.whl as a *generic file* (NOT a PyPI package), so it will not appear
as a "PyPI" package in GitLab.

Compared to the earlier version, this script adds GitHub-like convenience features:
- A) Optionally create a git tag via GitLab API (no local git required)
- B) Ensure a GitLab Release exists (idempotent create)
- C) Optionally generate a simple release description from commit history between tags
- D) Overwrite (delete+recreate) an existing Release asset link with the same name

Usage:
  python upload_whl_http.py path/to/package.whl [--project-id <id>]
    [--tag <tag>] [--create-tag] [--tag-ref <ref>]
    [--ensure-release] [--create-release]
    [--release-ref <ref>] [--release-description <text>]
    [--generate-description] [--base-tag <tag>] [--max-commits <n>]
    [--overwrite-link]

  python upload_whl_http.py --latest [dist_dir] [--project-id <id>]
    [--tag <tag>] [--create-tag] [--tag-ref <ref>]
    [--ensure-release] [--create-release]
    [--release-ref <ref>] [--release-description <text>]
    [--generate-description] [--base-tag <tag>] [--max-commits <n>]
    [--overwrite-link]

Environment variables:
  Required:
    GITLAB_HOST        Examples (all accepted):
                       - wgspace.sbc.nttdata-sbc.co.jp
                       - http://wgspace.sbc.nttdata-sbc.co.jp
                       - http://wgspace.sbc.nttdata-sbc.co.jp/gitlab
                       - http://wgspace.sbc.nttdata-sbc.co.jp/gitlab/
    GITLAB_PROJECT_ID  e.g. 340 (can be overridden by --project-id)
    GITLAB_TOKEN       Private Access Token used as "Private-Token" header

  Optional:
    GITLAB_GENERIC_PACKAGE_NAME
                       Default: "uag"
                       Generic package name path segment.
    GITLAB_GENERIC_VERSION
                       If set, overrides auto-detected version.
                       If not set, version is extracted from wheel filename.
    GITLAB_GENERIC_REPO_BASE
                       If set, this URL is used as the base directly.
                       (Takes precedence over GITLAB_HOST/GITLAB_PROJECT_ID)
                       Example:
                         http://<host>[/<subpath>]/api/v4/projects/<id>/packages/generic

What URL is used:
  Upload URL (PUT):
    http(s)://<gitlab-host>[/<subpath>]/api/v4/projects/<project_id>/packages/generic/
      <package_name>/<version>/<filename>

Release API (optional):
  Get Release (GET):
    http(s)://<gitlab-host>[/<subpath>]/api/v4/projects/<project_id>/releases/<tag>

  Create Release (POST):
    http(s)://<gitlab-host>[/<subpath>]/api/v4/projects/<project_id>/releases

  Release asset link API:
    List links is included in release JSON (assets.links)
    Create link (POST):
      http(s)://<gitlab-host>[/<subpath>]/api/v4/projects/<project_id>/releases/<tag>/assets/links
    Delete link (DELETE):
      http(s)://<gitlab-host>[/<subpath>]/api/v4/projects/<project_id>/releases/<tag>/assets/links/<link_id>

  Create Tag (POST):
    http(s)://<gitlab-host>[/<subpath>]/api/v4/projects/<project_id>/repository/tags

Notes:
- Standard library only (urllib). No requests/twine.
- "Release asset link" is a link to the uploaded Generic package URL (not an embedded file).
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

DEFAULT_RELEASE_DESCRIPTION = "Automated release created by upload_whl_http.py"


def _require_env(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise SystemExit(
            f"Missing required environment variable: {name}\n"
            f"Set it like:\n"
            f"  Linux/macOS: export {name}=...\n"
            f"  Windows PS : $env:{name}=...\n"
        )
    return v


def _pick_latest_whl(dist_dir: Path) -> Path:
    whls = sorted(dist_dir.glob("*.whl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not whls:
        raise SystemExit(f"No .whl found in: {dist_dir}")
    return whls[0]


def _normalize_gitlab_base(raw: str) -> str:
    s = raw.strip()
    if not s:
        raise SystemExit("GITLAB_HOST is empty")

    # Fix duplicated schemes like "https://http://...".
    s = re.sub(r"^(https?://)+(https?://)", r"\\2", s, flags=re.IGNORECASE)

    # Default to http when scheme is absent.
    if not re.match(r"^https?://", s, flags=re.IGNORECASE):
        s = "http://" + s

    return s.rstrip("/")


def _join_url(base: str, path: str) -> str:
    return base.rstrip("/") + "/" + path.lstrip("/")


def _detect_version_from_wheel(filename: str) -> str:
    if not filename.lower().endswith(".whl"):
        raise SystemExit(f"Not a .whl file: {filename}")

    stem = filename[:-4]
    parts = stem.split("-")
    if len(parts) < 5:
        raise SystemExit(
            "Wheel filename does not look valid (expected >= 5 '-' separated parts): "
            + filename
        )
    version = parts[1]
    if not version:
        raise SystemExit(f"Failed to detect version from wheel filename: {filename}")
    return version


def _get_generic_base_url(project_id: str | None = None) -> str:
    base_override = os.environ.get("GITLAB_GENERIC_REPO_BASE")
    if base_override:
        return base_override.strip().rstrip("/")

    gitlab_host_raw = _require_env("GITLAB_HOST")

    pid = (project_id or "").strip() if project_id is not None else ""
    if not pid:
        pid = _require_env("GITLAB_PROJECT_ID")

    base = _normalize_gitlab_base(gitlab_host_raw)
    return _join_url(base, f"api/v4/projects/{pid}/packages/generic")


def _build_generic_wheel_url(whl_path: Path, project_id: str | None = None) -> str:
    pkg_name = os.environ.get("GITLAB_GENERIC_PACKAGE_NAME", "uag").strip()
    if not pkg_name:
        raise SystemExit("GITLAB_GENERIC_PACKAGE_NAME is empty")

    version = os.environ.get("GITLAB_GENERIC_VERSION")
    if version:
        version = version.strip()
    if not version:
        version = _detect_version_from_wheel(whl_path.name)

    base = _get_generic_base_url(project_id=project_id)
    return _join_url(base, f"{pkg_name}/{version}/{whl_path.name}")


def _get_api_base() -> str:
    base = _normalize_gitlab_base(_require_env("GITLAB_HOST"))
    return _join_url(base, "api/v4")


def _http_put_file(url: str, token: str, file_path: Path) -> None:
    data = file_path.read_bytes()

    req = Request(url=url, data=data, method="PUT")
    req.add_header("Private-Token", token)
    req.add_header("Content-Type", "application/octet-stream")
    req.add_header("Content-Length", str(len(data)))

    try:
        with urlopen(req) as resp:
            status = getattr(resp, "status", None)
            reason = getattr(resp, "reason", "")
            print(f"HTTP {status} {reason}".strip())
    except HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise SystemExit(
            f"Upload failed: HTTP {e.code} {e.reason}\nURL: {url}\n{body}".strip()
        )
    except URLError as e:
        raise SystemExit(f"Upload failed: {e}\nURL: {url}")


def _request_raw(
    method: str,
    url: str,
    token: str,
    data: bytes | None = None,
    content_type: str | None = None,
) -> bytes:
    req = Request(url=url, data=data, method=method)
    req.add_header("Private-Token", token)
    if content_type:
        req.add_header("Content-Type", content_type)
    if data is not None:
        req.add_header("Content-Length", str(len(data)))

    try:
        with urlopen(req) as resp:
            return resp.read()
    except HTTPError as e:
        body = b""
        try:
            body = e.read()
        except Exception:
            pass
        text = body.decode("utf-8", errors="replace") if body else ""
        raise SystemExit(
            f"GitLab API request failed: {method} {url}\nHTTP {e.code} {e.reason}\n{text}".strip()
        )
    except URLError as e:
        raise SystemExit(f"GitLab API request failed: {method} {url}\n{e}".strip())


def _request_json(
    method: str,
    url: str,
    token: str,
    payload: dict | None = None,
    *,
    allow_404: bool = False,
) -> Any:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    try:
        raw = _request_raw(
            method,
            url,
            token,
            data=data,
            content_type=("application/json" if data is not None else None),
        )
        if not raw:
            return None
        return json.loads(raw.decode("utf-8", errors="strict"))
    except SystemExit as e:
        msg = str(e)
        if allow_404 and "HTTP 404" in msg:
            return None
        raise


def _get_release(project_id: str, token: str, tag: str) -> Optional[dict]:
    api_base = _get_api_base()
    url = _join_url(
        api_base,
        f"projects/{quote(project_id, safe='')}/releases/{quote(tag, safe='')}",
    )
    j = _request_json("GET", url, token, allow_404=True)
    if j is None:
        return None
    if not isinstance(j, dict):
        raise SystemExit("Unexpected API response for release")
    return j


def _create_release(
    project_id: str,
    token: str,
    tag: str,
    ref: str,
    *,
    description: str,
) -> dict:
    api_base = _get_api_base()
    url = _join_url(api_base, f"projects/{quote(project_id, safe='')}/releases")

    print("Creating GitLab Release:")
    print(f"  tag : {tag}")

    payload = {
        "tag_name": tag,
        "ref": ref,
        "name": tag,
        "description": description,
    }
    j = _request_json("POST", url, token, payload)
    if not isinstance(j, dict):
        # GitLab may return empty body on success in some setups, but usually returns JSON.
        return {}
    return j


def _ensure_release(
    project_id: str,
    token: str,
    tag: str,
    *,
    create_release: bool,
    ref: str,
    description: str,
) -> dict:
    rel = _get_release(project_id, token, tag)
    if rel is not None:
        rid = rel.get("tag_name") or rel.get("name") or "?"
        print(f"Release already exists for tag: {tag} ({rid})")
        return rel

    if not create_release:
        raise SystemExit(
            f"Release for tag '{tag}' not found. Create it first, or pass --create-release/--ensure-release."
        )

    _create_release(project_id, token, tag, ref, description=description)
    rel2 = _get_release(project_id, token, tag)
    return rel2 or {}


def _create_tag(project_id: str, token: str, tag: str, ref: str) -> None:
    api_base = _get_api_base()
    url = _join_url(api_base, f"projects/{quote(project_id, safe='')}/repository/tags")

    # GitLab accepts x-www-form-urlencoded for this endpoint.
    payload = urlencode({"tag_name": tag, "ref": ref}, doseq=True).encode("utf-8")
    req = Request(url=url, data=payload, method="POST")
    req.add_header("Private-Token", token)
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    print("Creating tag:")
    print(f"  tag: {tag}")
    print(f"  ref: {ref}")

    try:
        with urlopen(req) as resp:
            status = getattr(resp, "status", None)
            reason = getattr(resp, "reason", "")
            print(f"HTTP {status} {reason}".strip())
            _ = resp.read()  # drain
    except HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        # If already exists, GitLab returns 400 with a message like "Tag already exists".
        if e.code in (400, 409) and "exists" in body.lower():
            print(f"Tag already exists: {tag}")
            return
        raise SystemExit(
            f"Tag creation failed: HTTP {e.code} {e.reason}\nURL: {url}\n{body}".strip()
        )
    except URLError as e:
        raise SystemExit(f"Tag creation failed: {e}\nURL: {url}")


def _extract_links_from_release(release_json: dict) -> list[dict]:
    assets = release_json.get("assets")
    if not isinstance(assets, dict):
        return []
    links = assets.get("links")
    if not isinstance(links, list):
        return []
    out: list[dict] = []
    for item in links:
        if isinstance(item, dict):
            out.append(item)
    return out


def _delete_release_asset_link(
    project_id: str,
    token: str,
    tag: str,
    link_id: int,
) -> None:
    api_base = _get_api_base()
    url = _join_url(
        api_base,
        f"projects/{quote(project_id, safe='')}/releases/{quote(tag, safe='')}/assets/links/{link_id}",
    )
    print(f"Deleting existing release asset link id={link_id}")
    _request_raw("DELETE", url, token)


def _add_release_asset_link(
    project_id: str,
    token: str,
    tag: str,
    link_name: str,
    link_url: str,
    *,
    overwrite: bool,
) -> None:
    rel = _get_release(project_id, token, tag)
    if rel is None:
        raise SystemExit(f"Release not found for tag '{tag}'.")

    if overwrite:
        for link in _extract_links_from_release(rel):
            if str(link.get("name") or "") == link_name:
                lid = link.get("id")
                if isinstance(lid, int):
                    _delete_release_asset_link(project_id, token, tag, lid)

    api_base = _get_api_base()
    url = _join_url(
        api_base,
        f"projects/{quote(project_id, safe='')}/releases/{quote(tag, safe='')}/assets/links",
    )

    print("Adding release asset link:")
    print(f"  tag : {tag}")
    print(f"  name: {link_name}")
    print(f"  url : {link_url}")

    # GitLab accepts x-www-form-urlencoded
    payload = urlencode(
        {"name": link_name, "url": link_url, "link_type": "other"}, doseq=True
    ).encode("utf-8")
    req = Request(url=url, data=payload, method="POST")
    req.add_header("Private-Token", token)
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urlopen(req) as resp:
            status = getattr(resp, "status", None)
            reason = getattr(resp, "reason", "")
            print(f"HTTP {status} {reason}".strip())
            body = resp.read().decode("utf-8", errors="replace")
            if body.strip():
                print(body)
    except HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise SystemExit(
            f"Request failed: HTTP {e.code} {e.reason}\nURL: {url}\n{body}".strip()
        )
    except URLError as e:
        raise SystemExit(f"Request failed: {e}\nURL: {url}")


def _list_repository_tags(
    project_id: str, token: str, per_page: int = 100
) -> list[dict]:
    api_base = _get_api_base()
    url = _join_url(
        api_base,
        f"projects/{quote(project_id, safe='')}/repository/tags?per_page={per_page}",
    )
    j = _request_json("GET", url, token)
    if not isinstance(j, list):
        raise SystemExit("Unexpected API response for tags list")
    return [x for x in j if isinstance(x, dict)]


def _find_previous_tag(project_id: str, token: str, current_tag: str) -> Optional[str]:
    tags = _list_repository_tags(project_id, token, per_page=100)
    names: list[str] = []
    for t in tags:
        n = t.get("name")
        if isinstance(n, str) and n:
            names.append(n)

    if current_tag not in names:
        return None
    idx = names.index(current_tag)
    if idx + 1 >= len(names):
        return None
    return names[idx + 1]


def _compare(project_id: str, token: str, base: str, head: str) -> dict:
    api_base = _get_api_base()
    # GitLab compare API: GET /projects/:id/repository/compare?from=...&to=...
    q = urlencode({"from": base, "to": head}, doseq=True)
    url = _join_url(
        api_base,
        f"projects/{quote(project_id, safe='')}/repository/compare?{q}",
    )
    j = _request_json("GET", url, token)
    if not isinstance(j, dict):
        raise SystemExit("Unexpected API response for compare")
    return j


def _build_description_from_compare(
    compare: dict, *, base: str, head: str, max_commits: int
) -> str:
    commits = compare.get("commits")
    lines: list[str] = []
    lines.append("## Changes")
    lines.append("")
    lines.append(f"From {base} to {head}")
    lines.append("")

    if not isinstance(commits, list) or not commits:
        lines.append(f"(No commits found between {base} and {head}.)")
        return "\n".join(lines).strip() + "\n"

    count = 0
    for c in commits:
        if count >= max_commits:
            remaining = len(commits) - max_commits
            if remaining > 0:
                lines.append(f"- ... and {remaining} more commits")
            break

        if not isinstance(c, dict):
            continue

        sha = str(c.get("id") or c.get("sha") or "")
        sha7 = sha[:7] if sha else ""
        msg = str(c.get("title") or "").strip()
        author = ""
        a = c.get("author_name")
        if isinstance(a, str) and a:
            author = a

        item = f"- {sha7} {msg}".rstrip()
        if author:
            item += f" ({author})"
        lines.append(item)
        count += 1

    return "\n".join(lines).strip() + "\n"


def _generate_description(
    project_id: str,
    token: str,
    *,
    tag: str,
    base_tag: Optional[str],
    max_commits: int,
) -> str:
    base = base_tag
    if not base:
        base = _find_previous_tag(project_id, token, tag)

    if not base:
        return (
            f"## Release {tag}\n\n(Previous tag not found; no commit list generated.)\n"
        )

    cmp = _compare(project_id, token, base=base, head=tag)
    return _build_description_from_compare(
        cmp, base=base, head=tag, max_commits=max_commits
    )


def _parse_args(argv: list[str]) -> dict:
    if len(argv) < 2:
        raise SystemExit(
            "Usage:\n"
            "  python upload_whl_http.py path/to/package.whl [--project-id <id>] [--tag <tag>] ...\n"
            "  python upload_whl_http.py --latest [dist_dir] [--project-id <id>] [--tag <tag>] ...\n"
        )

    out: dict[str, Any] = {
        "whl": None,
        "latest": False,
        "dist_dir": None,
        "project_id": None,
        "tag": None,
        "create_tag": False,
        "tag_ref": "main",
        "ensure_release": False,
        "create_release": False,
        "release_ref": "main",
        "release_description": None,
        "generate_description": False,
        "base_tag": None,
        "max_commits": 50,
        "overwrite_link": False,
    }

    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--latest":
            out["latest"] = True
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                out["dist_dir"] = argv[i + 1]
                i += 2
            else:
                i += 1
        elif a == "--project-id":
            if i + 1 >= len(argv):
                raise SystemExit("--project-id requires a value")
            out["project_id"] = argv[i + 1]
            i += 2
        elif a == "--tag":
            if i + 1 >= len(argv):
                raise SystemExit("--tag requires a value")
            out["tag"] = argv[i + 1]
            i += 2
        elif a == "--release-tag":
            # Backward compatibility
            if i + 1 >= len(argv):
                raise SystemExit("--release-tag requires a value")
            out["tag"] = argv[i + 1]
            i += 2
        elif a == "--create-tag":
            out["create_tag"] = True
            i += 1
        elif a == "--tag-ref":
            if i + 1 >= len(argv):
                raise SystemExit("--tag-ref requires a value")
            out["tag_ref"] = argv[i + 1]
            i += 2
        elif a == "--ensure-release":
            out["ensure_release"] = True
            i += 1
        elif a == "--create-release":
            out["create_release"] = True
            i += 1
        elif a == "--release-ref":
            if i + 1 >= len(argv):
                raise SystemExit("--release-ref requires a value")
            out["release_ref"] = argv[i + 1]
            i += 2
        elif a == "--release-description":
            if i + 1 >= len(argv):
                raise SystemExit("--release-description requires a value")
            out["release_description"] = argv[i + 1]
            i += 2
        elif a == "--generate-description":
            out["generate_description"] = True
            i += 1
        elif a == "--base-tag":
            if i + 1 >= len(argv):
                raise SystemExit("--base-tag requires a value")
            out["base_tag"] = argv[i + 1]
            i += 2
        elif a == "--max-commits":
            if i + 1 >= len(argv):
                raise SystemExit("--max-commits requires a value")
            try:
                out["max_commits"] = int(argv[i + 1])
            except ValueError:
                raise SystemExit("--max-commits must be an integer")
            i += 2
        elif a == "--overwrite-link":
            out["overwrite_link"] = True
            i += 1
        elif a.startswith("--"):
            raise SystemExit(f"Unknown argument: {a}")
        else:
            if out["whl"] is not None:
                raise SystemExit("Only one wheel path is supported")
            out["whl"] = a
            i += 1

    if out["latest"] and out["whl"] is not None:
        raise SystemExit("Use either --latest or an explicit wheel path, not both")

    if not out["latest"] and out["whl"] is None:
        raise SystemExit("Wheel path is required (or use --latest)")

    if out["create_release"] and not out.get("tag"):
        raise SystemExit("--create-release requires --tag")

    if out["ensure_release"] and not out.get("tag"):
        raise SystemExit("--ensure-release requires --tag")

    if out["create_tag"] and not out.get("tag"):
        raise SystemExit("--create-tag requires --tag")

    if out["generate_description"] and not out.get("tag"):
        raise SystemExit("--generate-description requires --tag")

    return out


def main(argv: list[str]) -> int:
    args = _parse_args(argv)

    if args["latest"]:
        dist_dir = Path(args["dist_dir"] or "dist")
        whl_path = _pick_latest_whl(dist_dir)
        print(f"Selected latest wheel: {whl_path}")
    else:
        whl_path = Path(args["whl"])  # type: ignore[arg-type]

    if not whl_path.exists():
        raise SystemExit(f"File not found: {whl_path}")
    if whl_path.suffix.lower() != ".whl":
        raise SystemExit(f"Not a .whl file: {whl_path}")

    project_id = (args.get("project_id") or "").strip() or _require_env(
        "GITLAB_PROJECT_ID"
    )
    token = _require_env("GITLAB_TOKEN")

    tag = args.get("tag")

    # A) Create tag (optional)
    if tag and args.get("create_tag"):
        tag_ref = (args.get("tag_ref") or "").strip() or "main"
        _create_tag(project_id, token, tag, tag_ref)

    wheel_url = _build_generic_wheel_url(whl_path, project_id=project_id)

    print("Upload URL:")
    print(wheel_url)
    print("Uploading (PUT) ...")
    _http_put_file(wheel_url, token, whl_path)
    print("Upload done.")

    # B/C/D) Release operations (optional)
    if tag:
        # Determine release description
        desc = args.get("release_description")
        if not desc and args.get("generate_description"):
            desc = _generate_description(
                project_id,
                token,
                tag=tag,
                base_tag=args.get("base_tag"),
                max_commits=int(args.get("max_commits") or 50),
            )
        if not desc:
            desc = DEFAULT_RELEASE_DESCRIPTION

        need_release = bool(args.get("ensure_release") or args.get("create_release"))
        if need_release:
            release_ref = (args.get("release_ref") or "").strip() or "main"
            _ensure_release(
                project_id,
                token,
                tag,
                create_release=True,
                ref=release_ref,
                description=desc,
            )
        else:
            # If not ensuring/creating release, still try to fetch it for link add.
            rel = _get_release(project_id, token, tag)
            if rel is None:
                raise SystemExit(
                    f"Release for tag '{tag}' not found. Create it first, or pass --ensure-release/--create-release."
                )

        _add_release_asset_link(
            project_id,
            token,
            tag,
            whl_path.name,
            wheel_url,
            overwrite=bool(args.get("overwrite_link")),
        )
        print("Release link added.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
