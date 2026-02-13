#!/usr/bin/env python3
"""Upload a wheel file to GitLab **Generic Package Registry** and optionally attach it to a GitLab Release.

This script is **GitLab-only**.
It uploads *.whl as a *generic file* (NOT a PyPI package), so it will not appear
as a "PyPI" package in GitLab.

Usage:
  python upload_whl_http.py path/to/package.whl [--project-id <id>] [--release-tag <tag>] [--create-release]
  python upload_whl_http.py --latest [dist_dir] [--project-id <id>] [--release-tag <tag>] [--create-release]

Required environment variables:
  GITLAB_HOST        Examples (all accepted):
                     - wgspace.sbc.nttdata-sbc.co.jp
                     - http://wgspace.sbc.nttdata-sbc.co.jp
                     - http://wgspace.sbc.nttdata-sbc.co.jp/gitlab
                     - http://wgspace.sbc.nttdata-sbc.co.jp/gitlab/
  GITLAB_PROJECT_ID  e.g. 340
  GITLAB_TOKEN       Private Access Token used as "Private-Token" header

Optional environment variables:
  GITLAB_GENERIC_PACKAGE_NAME
                     Default: "scheck"
                     Generic package name path segment.
  GITLAB_GENERIC_VERSION
                     If set, overrides auto-detected version.
                     If not set, version is extracted from wheel filename.
  GITLAB_GENERIC_REPO_BASE
                     If set, this URL is used as the base directly.
                     (Takes precedence over GITLAB_HOST/GITLAB_PROJECT_ID)
                     Example:
                       http://<host>[/<subpath>]/api/v4/projects/<id>/packages/generic

What URL is used
  Upload URL (PUT):
    http(s)://<gitlab-host>[/<subpath>]/api/v4/projects/<project_id>/packages/generic/
      <package_name>/<version>/<filename>

Release API (optional)
  Create Release (POST):
    http(s)://<gitlab-host>[/<subpath>]/api/v4/projects/<project_id>/releases

  Release asset link API (POST):
    http(s)://<gitlab-host>[/<subpath>]/api/v4/projects/<project_id>/releases/<tag>/assets/links

Examples
  # Upload latest wheel under dist/ as generic package
  python upload_whl_http.py --latest dist

  # Upload latest wheel AND attach link to release
  python upload_whl_http.py --latest dist --release-tag v0.2.13

  # Upload latest wheel, create a GitLab Release (fails if already exists),
  # then attach link to the release
  python upload_whl_http.py --latest dist --release-tag v0.2.13 --create-release

Notes
- Standard library only (urllib). No twine.
- If your Generic package URL is public, the Release link works without auth.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
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
    pkg_name = os.environ.get("GITLAB_GENERIC_PACKAGE_NAME", "scheck").strip()
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


def _http_post_form(url: str, token: str, form: dict) -> None:
    payload = urlencode(form, doseq=True).encode("utf-8")
    req = Request(url=url, data=payload, method="POST")
    req.add_header("Private-Token", token)
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urlopen(req) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            status = getattr(resp, "status", None)
            reason = getattr(resp, "reason", "")
            print(f"HTTP {status} {reason}".strip())
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


def _add_release_asset_link(
    project_id: str, token: str, tag: str, link_name: str, link_url: str
) -> None:
    api_base = _get_api_base()
    url = _join_url(api_base, f"projects/{project_id}/releases/{tag}/assets/links")

    print("Adding release asset link:")
    print(f"  tag : {tag}")
    print(f"  name: {link_name}")
    print(f"  url : {link_url}")

    _http_post_form(
        url,
        token,
        {"name": link_name, "url": link_url, "link_type": "other"},
    )


def _create_release(project_id: str, token: str, tag: str) -> None:
    api_base = _get_api_base()
    url = _join_url(api_base, f"projects/{project_id}/releases")

    print("Creating GitLab Release:")
    print(f"  tag : {tag}")

    _http_post_form(
        url,
        token,
        {
            "tag_name": tag,
            "name": tag,
            "description": DEFAULT_RELEASE_DESCRIPTION,
        },
    )


def _parse_args(argv: list[str]) -> dict:
    if len(argv) < 2:
        raise SystemExit(
            "Usage:\n"
            "  python upload_whl_http.py path/to/package.whl [--release-tag <tag>] [--create-release]\n"
            "  python upload_whl_http.py --latest [dist_dir] [--release-tag <tag>] [--create-release]\n"
        )

    out = {
        "whl": None,
        "latest": False,
        "dist_dir": None,
        "project_id": None,
        "release_tag": None,
        "create_release": False,
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
        elif a == "--release-tag":
            if i + 1 >= len(argv):
                raise SystemExit("--release-tag requires a value")
            out["release_tag"] = argv[i + 1]
            i += 2
        elif a == "--create-release":
            out["create_release"] = True
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

    if out.get("create_release") and not out.get("release_tag"):
        raise SystemExit("--create-release requires --release-tag")

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

    project_id = (args.get("project_id") or "").strip() or _require_env("GITLAB_PROJECT_ID")
    token = _require_env("GITLAB_TOKEN")

    wheel_url = _build_generic_wheel_url(whl_path, project_id=project_id)

    print("Upload URL:")
    print(wheel_url)
    print("Uploading (PUT) ...")
    _http_put_file(wheel_url, token, whl_path)
    print("Upload done.")

    release_tag = args["release_tag"]
    if release_tag:
        if args.get("create_release"):
            _create_release(project_id, token, release_tag)
        _add_release_asset_link(project_id, token, release_tag, whl_path.name, wheel_url)
        print("Release link added.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
