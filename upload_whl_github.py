#!/usr/bin/env python3
"""Upload a wheel file to **GitHub Releases** as a release asset.

This script is a GitHub counterpart of upload_whl_http.py (GitLab-only).

What it does
- Select a wheel file (*.whl) explicitly or pick the latest from a dist directory.
- Ensure a GitHub Release exists for the given tag.
  - Optionally create the tag (git ref) via GitHub API (no local git required).
  - Optionally create the Release if it does not exist.
- Upload the wheel file as a Release asset.

Key differences from the GitLab version
- Uses GitHub REST API.
- Uploads to GitHub Releases (assets), not to GitHub Packages.

Usage:
  python upload_whl_github.py path/to/package.whl --tag <tag> [--create-tag] [--target <sha>] [--create-release]
  python upload_whl_github.py --latest [dist_dir] --tag <tag> [--create-tag] [--target <sha>] [--create-release]

Required environment variables:
  GITHUB_REPO    GitHub repository in the form "owner/repo". Example: awaku7/agentcli
  GITHUB_TOKEN   GitHub token with appropriate permissions.
                - For local execution: a PAT with "repo" scope (classic) is simplest.
                - For GitHub Actions: use the provided token (usually in env GITHUB_TOKEN) with
                  permissions:
                    permissions:
                      contents: write

Notes on permissions
- Creating tag refs and releases requires "contents: write".
- Uploading release assets requires "contents: write".

Tag / Release creation behavior
- The script needs a tag name via --tag.
- If --create-tag is specified, the script will create refs/tags/<tag> pointing to --target SHA.
  - If --target is omitted, the script uses the repository default branch HEAD commit.
- If --create-release is specified, the script will create a Release for the tag if missing.
  - If the Release already exists, it will continue.

Idempotency
- If an asset with the same name already exists, the script deletes it first (requires permission).

Standard library only
- urllib only. No requests.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

GITHUB_API = "https://api.github.com"
GITHUB_UPLOADS = "https://uploads.github.com"
DEFAULT_RELEASE_BODY = "Automated release created by upload_whl_github.py"


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


def _json_loads(b: bytes) -> Any:
    return json.loads(b.decode("utf-8", errors="strict"))


def _request_json(method: str, url: str, token: str, payload: dict | None = None) -> Any:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = Request(url=url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data is not None:
        req.add_header("Content-Type", "application/json")
        req.add_header("Content-Length", str(len(data)))

    try:
        with urlopen(req) as resp:
            body = resp.read()
            if not body:
                return None
            return _json_loads(body)
    except HTTPError as e:
        body = b""
        try:
            body = e.read()
        except Exception:
            pass
        text = body.decode("utf-8", errors="replace") if body else ""
        raise SystemExit(
            f"GitHub API request failed: {method} {url}\nHTTP {e.code} {e.reason}\n{text}".strip()
        )
    except URLError as e:
        raise SystemExit(f"GitHub API request failed: {method} {url}\n{e}".strip())


def _request_raw(method: str, url: str, token: str, data: bytes | None = None, content_type: str | None = None) -> bytes:
    req = Request(url=url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
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
            f"GitHub API request failed: {method} {url}\nHTTP {e.code} {e.reason}\n{text}".strip()
        )
    except URLError as e:
        raise SystemExit(f"GitHub API request failed: {method} {url}\n{e}".strip())


def _parse_repo(repo: str) -> tuple[str, str]:
    repo = repo.strip()
    if not repo or "/" not in repo:
        raise SystemExit("GITHUB_REPO must be in form 'owner/repo' (e.g. awaku7/agentcli)")
    owner, name = repo.split("/", 1)
    owner = owner.strip()
    name = name.strip()
    if not owner or not name:
        raise SystemExit("GITHUB_REPO must be in form 'owner/repo' (e.g. awaku7/agentcli)")
    return owner, name


def _get_default_branch(owner: str, repo: str, token: str) -> str:
    url = f"{GITHUB_API}/repos/{owner}/{repo}"
    j = _request_json("GET", url, token)
    return j["default_branch"]


def _get_branch_head_sha(owner: str, repo: str, token: str, branch: str) -> str:
    # Get a ref. Response has object.sha
    ref = quote(f"heads/{branch}", safe="")
    url = f"{GITHUB_API}/repos/{owner}/{repo}/git/ref/{ref}"
    j = _request_json("GET", url, token)
    return j["object"]["sha"]


def _ensure_tag_ref(owner: str, repo: str, token: str, tag: str, target_sha: str) -> None:
    ref = f"refs/tags/{tag}"

    # Check if tag ref exists
    ref_q = quote(f"tags/{tag}", safe="")
    url_get = f"{GITHUB_API}/repos/{owner}/{repo}/git/ref/{ref_q}"
    try:
        _request_json("GET", url_get, token)
        print(f"Tag ref already exists: {ref}")
        return
    except SystemExit as e:
        # If it's 404, create. Otherwise re-raise.
        msg = str(e)
        if "HTTP 404" not in msg:
            raise

    url_create = f"{GITHUB_API}/repos/{owner}/{repo}/git/refs"
    payload = {"ref": ref, "sha": target_sha}
    print("Creating tag ref:")
    print(f"  ref : {ref}")
    print(f"  sha : {target_sha}")
    _request_json("POST", url_create, token, payload)


def _get_release_by_tag(owner: str, repo: str, token: str, tag: str) -> dict:
    url = f"{GITHUB_API}/repos/{owner}/{repo}/releases/tags/{quote(tag, safe='')}"
    return _request_json("GET", url, token)


def _create_release(owner: str, repo: str, token: str, tag: str, name: str, body: str) -> dict:
    url = f"{GITHUB_API}/repos/{owner}/{repo}/releases"
    payload = {
        "tag_name": tag,
        "name": name,
        "body": body,
        "draft": False,
        "prerelease": False,
    }
    print("Creating GitHub Release:")
    print(f"  tag : {tag}")
    return _request_json("POST", url, token, payload)


def _ensure_release(owner: str, repo: str, token: str, tag: str, create_release: bool) -> dict:
    try:
        rel = _get_release_by_tag(owner, repo, token, tag)
        print(f"Release already exists for tag: {tag} (id={rel.get('id')})")
        return rel
    except SystemExit as e:
        msg = str(e)
        if "HTTP 404" not in msg:
            raise
        if not create_release:
            raise SystemExit(
                f"Release for tag '{tag}' not found. Create it first, or pass --create-release.\n"
                f"(API: GET /releases/tags/{tag})"
            )
        return _create_release(owner, repo, token, tag, tag, DEFAULT_RELEASE_BODY)


def _delete_asset(owner: str, repo: str, token: str, asset_id: int) -> None:
    url = f"{GITHUB_API}/repos/{owner}/{repo}/releases/assets/{asset_id}"
    print(f"Deleting existing asset id={asset_id} ...")
    _request_raw("DELETE", url, token)


def _upload_release_asset(owner: str, repo: str, token: str, release: dict, file_path: Path) -> None:
    upload_url = release.get("upload_url")
    if not upload_url:
        raise SystemExit("Release response missing upload_url")

    # upload_url is a URI template like:
    #   https://uploads.github.com/repos/{owner}/{repo}/releases/{id}/assets{?name,label}
    # We must strip the template part.
    upload_url = re.sub(r"\{\?.*\}$", "", upload_url)

    # If asset exists, delete first
    assets = release.get("assets", [])
    for a in assets:
        if a.get("name") == file_path.name:
            _delete_asset(owner, repo, token, int(a["id"]))
            break

    data = file_path.read_bytes()
    url = f"{upload_url}?name={quote(file_path.name, safe='')}"

    print("Uploading Release asset:")
    print(f"  file: {file_path}")
    print(f"  url : {url}")

    # Upload endpoint requires application/octet-stream
    _request_raw("POST", url, token, data=data, content_type="application/octet-stream")
    print("Upload done.")


def _parse_args(argv: list[str]) -> dict:
    if len(argv) < 2:
        raise SystemExit(
            "Usage:\n"
            "  python upload_whl_github.py path/to/package.whl --tag <tag> [--create-tag] [--target <sha>] [--create-release]\n"
            "  python upload_whl_github.py --latest [dist_dir] --tag <tag> [--create-tag] [--target <sha>] [--create-release]\n"
        )

    out = {
        "whl": None,
        "latest": False,
        "dist_dir": None,
        "tag": None,
        "create_tag": False,
        "target": None,
        "create_release": False,
        "release_name": None,
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
        elif a == "--tag":
            if i + 1 >= len(argv):
                raise SystemExit("--tag requires a value")
            out["tag"] = argv[i + 1]
            i += 2
        elif a == "--create-tag":
            out["create_tag"] = True
            i += 1
        elif a == "--target":
            if i + 1 >= len(argv):
                raise SystemExit("--target requires a value")
            out["target"] = argv[i + 1]
            i += 2
        elif a == "--create-release":
            out["create_release"] = True
            i += 1
        elif a == "--release-name":
            if i + 1 >= len(argv):
                raise SystemExit("--release-name requires a value")
            out["release_name"] = argv[i + 1]
            i += 2
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

    if not out.get("tag"):
        raise SystemExit("--tag is required")

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

    repo_full = _require_env("GITHUB_REPO")
    token = _require_env("GITHUB_TOKEN")
    owner, repo = _parse_repo(repo_full)

    tag = args["tag"]

    # Optional auto-create tag ref
    if args.get("create_tag"):
        target = args.get("target")
        if target:
            target_sha = target
        else:
            default_branch = _get_default_branch(owner, repo, token)
            target_sha = _get_branch_head_sha(owner, repo, token, default_branch)
            print("Resolved target SHA from default branch HEAD:")
            print(f"  branch: {default_branch}")
            print(f"  sha   : {target_sha}")

        _ensure_tag_ref(owner, repo, token, tag, target_sha)

    # Ensure release exists (by tag)
    release = _ensure_release(owner, repo, token, tag, bool(args.get("create_release")))

    # Upload asset
    _upload_release_asset(owner, repo, token, release, whl_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
