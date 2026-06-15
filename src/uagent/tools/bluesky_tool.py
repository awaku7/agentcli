from __future__ import annotations

import json
import mimetypes
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from ..env_utils import env_get
from .context import get_callbacks
from .i18n_helper import make_tool_translator
from .openers import open_image_with_default_app

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:bluesky"

_API_BASE = "https://bsky.social/xrpc"

TOOL_SPEC: dict[str, Any] = {
    "tool_level": 0,
    "tool_genre": "comm",
    "type": "function",
    "function": {
        "name": "bluesky",
        "description": _(
            "tool.description",
            default=(
                "Interact with Bluesky (AT Protocol). "
                "Supports posting, searching, and more. "
                "Requires UAGENT_BLUESKY_HANDLE and UAGENT_BLUESKY_APP_PASSWORD."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "post",
                        "profile",
                        "search",
                        "timeline",
                        "thread",
                        "like",
                        "notifications",
                    ],
                    "description": _(
                        "param.action.description",
                        default=(
                            "Action to perform. 'post' creates a new text post. "
                            "'profile' gets profile info. 'search' searches posts. "
                            "'timeline' gets your home feed. 'thread' gets a post thread. "
                            "'like' likes a post. 'notifications' lists your notifications."
                        ),
                    ),
                },
                "text": {
                    "type": "string",
                    "description": _(
                        "param.text.description",
                        default=(
                            "Post content (plain text, max 300 chars). "
                            "Required for 'post'."
                        ),
                    ),
                },
                "image_path": {
                    "type": "string",
                    "description": _(
                        "param.image_path.description",
                        default=(
                            "Local path to an image file to attach. "
                            "Supported: JPEG, PNG. Max 1 MB. "
                            "Used by 'post'."
                        ),
                    ),
                },
                "alt": {
                    "type": "string",
                    "description": _(
                        "param.alt.description",
                        default=(
                            "Alt text for the attached image. "
                            "Used together with image_path for 'post'."
                        ),
                    ),
                },
                "save_images": {
                    "type": "boolean",
                    "description": _(
                        "param.save_images.description",
                        default=(
                            "Download images from posts and save locally. "
                            "Used by 'timeline', 'search', 'thread', 'notifications'."
                        ),
                    ),
                },
                "actor": {
                    "type": "string",
                    "description": _(
                        "param.actor.description",
                        default=(
                            "Bluesky handle or DID. "
                            "Used by 'profile' (optional, defaults to self)."
                        ),
                    ),
                },
                "q": {
                    "type": "string",
                    "description": _(
                        "param.q.description",
                        default="Search query string. Required for 'search'.",
                    ),
                },
                "uri": {
                    "type": "string",
                    "description": _(
                        "param.uri.description",
                        default="AT URI of a post. Used by 'thread' and 'like'.",
                    ),
                },
                "cid": {
                    "type": "string",
                    "description": _(
                        "param.cid.description",
                        default="CID of a post. Required for 'like'.",
                    ),
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 20,
                    "description": _(
                        "param.limit.description",
                        default="Maximum number of results. Used by 'search', 'timeline', 'notifications'. Default: 20.",
                    ),
                },
            },
            "required": ["action"],
            "additionalProperties": False,
        },
    },
}


def _get_credentials() -> tuple[str | None, str | None]:
    handle = os.environ.get("UAGENT_BLUESKY_HANDLE") or os.environ.get("BLUESKY_HANDLE")
    password = (
        os.environ.get("UAGENT_BLUESKY_APP_PASSWORD")
        or os.environ.get("BLUESKY_APP_PASSWORD")
    )
    return handle, password


def _create_session(handle: str, password: str, timeout: int) -> dict[str, Any] | None:
    url = f"{_API_BASE}/com.atproto.server.createSession"
    body = {"identifier": handle, "password": password}
    try:
        resp = requests.post(url, json=body, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return None


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _get_auth(path: str, access_jwt: str, params: dict[str, Any] | None = None, timeout: int = 15) -> dict[str, Any] | None:
    url = f"{_API_BASE}{path}"
    headers = {"Authorization": f"Bearer {access_jwt}"}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return None


def _post_auth(path: str, access_jwt: str, body: dict[str, Any] | bytes, content_type: str | None = None, timeout: int = 15) -> dict[str, Any] | None:
    """POST with Bearer auth. Accepts dict (JSON) or bytes (raw blob)."""
    url = f"{_API_BASE}{path}"
    headers = {"Authorization": f"Bearer {access_jwt}"}
    if content_type:
        headers["Content-Type"] = content_type
        data = body if isinstance(body, bytes) else None
        json_body = None if isinstance(body, bytes) else body
    else:
        headers["Content-Type"] = "application/json"
        data = None
        json_body = body if isinstance(body, dict) else None
    try:
        resp = requests.post(url, headers=headers, json=json_body, data=data, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return None


def _ensure_session() -> dict[str, Any] | None:
    handle, password = _get_credentials()
    if not handle or not password:
        return None
    return _create_session(handle, password, timeout=15)


# ---------------------------------------------------------------------------
# image helpers
# ---------------------------------------------------------------------------


def _upload_blob(access_jwt: str, image_path: str, timeout: int = 30) -> dict[str, Any] | None:
    """Upload an image blob to Bluesky. Returns the blob reference dict."""
    path = Path(image_path)
    if not path.is_file():
        return None
    data = path.read_bytes()
    if len(data) > 1_000_000:  # 1 MB limit per image
        return None
    mime, _ = mimetypes.guess_type(str(path))
    if mime not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        return None
    return _post_auth("/com.atproto.repo.uploadBlob", access_jwt, data, content_type=mime, timeout=timeout)


def _extract_images(record: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Extract image info from a post record's embed."""
    if not isinstance(record, dict):
        return []
    embed = record.get("embed") or record
    if isinstance(embed, dict) and embed.get("$type") == "app.bsky.embed.images":
        images = embed.get("images") or []
        return [
            {
                "alt": img.get("alt", ""),
                "fullsize": img.get("image", {}).get("ref", {}).get("$link", ""),
                "thumb": img.get("thumb", ""),
            }
            for img in images if isinstance(img, dict)
        ]
    return []


def _resolve_image_url(did: str, cid: str) -> str:
    """Resolve a CDN URL for a Bluesky image blob."""
    return f"https://cdn.bsky.app/img/feed_fullsize/plain/{did}/{cid}@jpeg"


def _download_and_save(url: str, prefix: str, index: int) -> str | None:
    """Download an image and save to outputs/. Returns saved path or None."""
    out_dir = Path("outputs/bluesky_images")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"{prefix}_{ts}_{index}.jpg"
    out_path = out_dir / fname
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        out_path.write_bytes(resp.content)
        return str(out_path)
    except requests.RequestException:
        return None


# ---------------------------------------------------------------------------
# post
# ---------------------------------------------------------------------------


def _handle_post(args: dict[str, Any], output_format: str) -> str:
    text = (args.get("text") or "").strip()
    image_path = (args.get("image_path") or "").strip()
    alt_text = (args.get("alt") or "").strip()

    if not text and not image_path:
        return _err_json("invalid_argument", "Text or image_path is required for post action.", output_format)

    if len(text) > 300:
        text = text[:300]

    session = _ensure_session()
    if not session or not session.get("accessJwt"):
        return _err_json("auth_failed", "Authentication failed. Check your Bluesky credentials.", output_format)

    started = time.perf_counter()
    did = session.get("did", "")
    access_jwt = session.get("accessJwt", "")

    # Build record
    record: dict[str, Any] = {
        "$type": "app.bsky.feed.post",
        "text": text or "",
        "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }

    # Upload image if provided
    saved_images: list[str] = []
    if image_path:
        blob = _upload_blob(access_jwt, image_path)
        if not blob:
            return _err_json("image_upload_failed", f"Failed to upload image: {image_path}. Check file exists, is JPEG/PNG, and under 1 MB.", output_format)
        blb = blob.get("blob") or {}
        images = [{"alt": alt_text, "image": blb}]
        record["embed"] = {"$type": "app.bsky.embed.images", "images": images}

    post_result = _post_auth("/com.atproto.repo.createRecord", access_jwt, record, timeout=15)
    if not post_result:
        return _err_json("post_failed", "Failed to create post on Bluesky.", output_format)

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    result = {
        "ok": True, "action": "post",
        "text": text,
        "has_image": bool(image_path),
        "uri": post_result.get("uri"),
        "cid": post_result.get("cid"),
        "handle": session.get("handle"),
        "did": did,
        "elapsed_ms": elapsed_ms,
    }
    if output_format == "text":
        lines = [f"Posted to Bluesky: {text[:60]}..."]
        if image_path:
            lines.append(f"  With image: {image_path}")
        lines.append(f"URI: {result['uri']}")
        return "\n".join(lines)
    return json.dumps(result, ensure_ascii=False)


# ---------------------------------------------------------------------------
# profile
# ---------------------------------------------------------------------------


def _handle_profile(args: dict[str, Any], output_format: str) -> str:
    actor = (args.get("actor") or "").strip()
    session = _ensure_session()
    if not session or not session.get("accessJwt"):
        return _err_json("auth_failed", "Authentication failed.", output_format)

    started = time.perf_counter()
    target = actor if actor else session.get("handle", "")
    data = _get_auth("/app.bsky.actor.getProfile", session["accessJwt"], {"actor": target})
    if not data:
        return _err_json("profile_failed", f"Failed to get profile for: {target}.", output_format)

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    result = {
        "ok": True, "action": "profile",
        "did": data.get("did"),
        "handle": data.get("handle"),
        "display_name": data.get("displayName"),
        "description": data.get("description"),
        "avatar": data.get("avatar"),
        "banner": data.get("banner"),
        "followers_count": data.get("followersCount"),
        "follows_count": data.get("followsCount"),
        "posts_count": data.get("postsCount"),
        "created_at": data.get("createdAt"),
        "elapsed_ms": elapsed_ms,
    }
    if output_format == "text":
        bio = (result.get("description") or "-")[:80]
        return "\n".join([
            f"Profile: {result.get('display_name', '-')} (@{result.get('handle', '-')})",
            f"  DID: {result.get('did', '-')}",
            f"  Bio: {bio}",
            f"  Followers: {result.get('followers_count', 0)}",
            f"  Following: {result.get('follows_count', 0)}",
            f"  Posts: {result.get('posts_count', 0)}",
            f"  Created: {result.get('created_at', '-')}",
        ])
    return json.dumps(result, ensure_ascii=False)


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


def _handle_search(args: dict[str, Any], output_format: str) -> str:
    q = (args.get("q") or "").strip()
    if not q:
        return _err_json("invalid_argument", "Query (q) is required for search.", output_format)
    session = _ensure_session()
    if not session or not session.get("accessJwt"):
        return _err_json("auth_failed", "Authentication failed.", output_format)
    limit = min(max(int(args.get("limit", 20)), 1), 100)
    started = time.perf_counter()
    data = _get_auth("/app.bsky.feed.searchPosts", session["accessJwt"], {"q": q, "limit": str(limit)})
    if not data:
        return _err_json("search_failed", "Search request failed.", output_format)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    posts = data.get("posts") or []
    items = [_compact_post(p, args.get("save_images"), session.get("did")) for p in posts[:limit]]
    attachments = _collect_attachments(items)
    result = {"ok": True, "action": "search", "q": q, "count": len(items), "items": items, "elapsed_ms": elapsed_ms, "attachments": attachments}
    _open_saved_images(result)
    if output_format == "text":
        return _fmt_posts(result, title=f"Search results for '{q}':")
    return json.dumps(result, ensure_ascii=False)


# ---------------------------------------------------------------------------
# timeline
# ---------------------------------------------------------------------------


def _handle_timeline(args: dict[str, Any], output_format: str) -> str:
    session = _ensure_session()
    if not session or not session.get("accessJwt"):
        return _err_json("auth_failed", "Authentication failed.", output_format)
    limit = min(max(int(args.get("limit", 20)), 1), 100)
    started = time.perf_counter()
    data = _get_auth("/app.bsky.feed.getTimeline", session["accessJwt"], {"limit": str(limit)})
    if not data:
        return _err_json("timeline_failed", "Failed to get timeline.", output_format)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    feed = data.get("feed") or []
    items = []
    for entry in feed[:limit]:
        item = _compact_post(entry.get("post") or {}, args.get("save_images"), session.get("did"))
        item["reason"] = entry.get("reason")
        items.append(item)
    attachments = _collect_attachments(items)
    result = {"ok": True, "action": "timeline", "count": len(items), "items": items, "elapsed_ms": elapsed_ms, "attachments": attachments}
    _open_saved_images(result)
    if output_format == "text":
        return _fmt_posts(result, title="Timeline:")
    return json.dumps(result, ensure_ascii=False)


# ---------------------------------------------------------------------------
# thread
# ---------------------------------------------------------------------------


def _handle_thread(args: dict[str, Any], output_format: str) -> str:
    uri = (args.get("uri") or "").strip()
    if not uri:
        return _err_json("invalid_argument", "URI is required for thread.", output_format)
    session = _ensure_session()
    if not session or not session.get("accessJwt"):
        return _err_json("auth_failed", "Authentication failed.", output_format)
    started = time.perf_counter()
    data = _get_auth("/app.bsky.feed.getPostThread", session["accessJwt"], {"uri": uri})
    if not data:
        return _err_json("thread_failed", f"Failed to get thread for: {uri}.", output_format)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    save = args.get("save_images")
    did = session.get("did")
    thread = data.get("thread") or {}
    compact = _compact_thread(thread, save, did)
    attachments = _collect_attachments([compact])
    result = {
        "ok": True, "action": "thread", "uri": uri,
        "thread": compact,
        "attachments": attachments,
        "elapsed_ms": elapsed_ms,
    }
    _open_saved_images(result)
    if output_format == "text":
        return _fmt_thread(result)
    return json.dumps(result, ensure_ascii=False)


def _compact_thread(thread: dict[str, Any], save_images: bool = False, my_did: str | None = None) -> dict[str, Any]:
    post_data = thread.get("post") or thread
    out = {"post": _compact_post(post_data, save_images, my_did)}
    replies = thread.get("replies")
    if isinstance(replies, list):
        out["replies"] = [_compact_thread(r, save_images, my_did) if isinstance(r, dict) else r for r in replies[:5]]
    return out


# ---------------------------------------------------------------------------
# like
# ---------------------------------------------------------------------------


def _handle_like(args: dict[str, Any], output_format: str) -> str:
    uri = (args.get("uri") or "").strip()
    cid = (args.get("cid") or "").strip()
    if not uri or not cid:
        return _err_json("invalid_argument", "Both uri and cid are required for like.", output_format)
    session = _ensure_session()
    if not session or not session.get("accessJwt"):
        return _err_json("auth_failed", "Authentication failed.", output_format)
    started = time.perf_counter()
    did = session.get("did", "")
    access_jwt = session.get("accessJwt", "")
    record = {
        "$type": "app.bsky.feed.like",
        "subject": {"uri": uri, "cid": cid},
        "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    body = {"repo": did, "collection": "app.bsky.feed.like", "record": record}
    like_result = _post_auth("/com.atproto.repo.createRecord", access_jwt, body)
    if not like_result:
        return _err_json("like_failed", "Failed to like the post.", output_format)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    result = {"ok": True, "action": "like", "uri": uri, "like_uri": like_result.get("uri"), "like_cid": like_result.get("cid"), "elapsed_ms": elapsed_ms}
    if output_format == "text":
        return f"Liked: {uri}\nLike URI: {like_result.get('uri', '-')}"
    return json.dumps(result, ensure_ascii=False)


# ---------------------------------------------------------------------------
# notifications
# ---------------------------------------------------------------------------


def _handle_notifications(args: dict[str, Any], output_format: str) -> str:
    session = _ensure_session()
    if not session or not session.get("accessJwt"):
        return _err_json("auth_failed", "Authentication failed.", output_format)
    limit = min(max(int(args.get("limit", 20)), 1), 100)
    started = time.perf_counter()
    data = _get_auth("/app.bsky.notification.listNotifications", session["accessJwt"], {"limit": str(limit)})
    if not data:
        return _err_json("notifications_failed", "Failed to get notifications.", output_format)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    notifs = data.get("notifications") or []
    items = []
    for n in notifs[:limit]:
        record = n.get("record") or {}
        images = _extract_images(record)
        saved: list[str] = []
        if args.get("save_images") and images:
            for idx, img in enumerate(images):
                cid = img.get("fullsize", "")
                if cid:
                    url = _resolve_image_url(n.get("author", {}).get("did", ""), cid)
                    sp = _download_and_save(url, "notif", idx + 1)
                    if sp:
                        saved.append(sp)
        items.append({
            "uri": n.get("uri"),
            "cid": n.get("cid"),
            "author": n.get("author", {}).get("handle"),
            "reason": n.get("reason"),
            "reason_subject": n.get("reasonSubject"),
            "record_text": record.get("text", "") if isinstance(record, dict) else "",
            "is_read": n.get("isRead"),
            "indexed_at": n.get("indexedAt"),
            "images": images,
            "saved_images": saved if saved else None,
        })
    result = {"ok": True, "action": "notifications", "count": len(items), "items": items, "elapsed_ms": elapsed_ms}
    _open_saved_images(result)
    if output_format == "text":
        lines = [f"Notifications ({result['count']}):"]
        for n in items:
            label = "READ" if n.get("is_read") else "NEW"
            txt = (n.get("record_text") or "")[:60]
            lines.append(f"  [{label}] {n.get('reason', '?')} from @{n.get('author', '?')}: {txt}")
            if n.get("saved_images"):
                for sp in n["saved_images"]:
                    lines.append(f"         Image: {sp}")
        return "\n".join(lines)
    return json.dumps(result, ensure_ascii=False)


# ---------------------------------------------------------------------------
# compact helpers
# ---------------------------------------------------------------------------


def _compact_post(post: dict[str, Any], save_images: bool = False, my_did: str | None = None) -> dict[str, Any]:
    author = post.get("author") or {}
    record = post.get("record") or {}
    images = _extract_images(record)
    saved: list[str] = []
    if save_images and images and my_did:
        for idx, img in enumerate(images):
            cid = img.get("fullsize", "")
            if cid:
                url = _resolve_image_url(author.get("did", my_did), cid)
                sp = _download_and_save(url, "img", idx + 1)
                if sp:
                    saved.append(sp)
    return {
        "uri": post.get("uri"),
        "cid": post.get("cid"),
        "text": record.get("text", "") if isinstance(record, dict) else "",
        "author_handle": author.get("handle"),
        "author_display": author.get("displayName"),
        "created_at": record.get("createdAt") if isinstance(record, dict) else None,
        "indexed_at": post.get("indexedAt"),
        "like_count": post.get("likeCount"),
        "reply_count": post.get("replyCount"),
        "repost_count": post.get("repostCount"),
        "images": images,
        "saved_images": saved if saved else None,
        "attachments": [{"type": "image", "saved_path": sp} for sp in saved] if saved else None,
    }


# ---------------------------------------------------------------------------
# output helpers
# ---------------------------------------------------------------------------


def _open_saved_images(result: dict[str, Any]) -> None:
    """Open saved images with default app (CLI mode only)."""
    cb = get_callbacks()
    if bool(getattr(cb, "is_gui", False)):
        return
    open_flag = (env_get("UAGENT_IMAGE_OPEN") or "").strip().lower()
    if open_flag in ("0", "false", "no", "off"):
        return
    seen: set[str] = set()
    for att in (result.get("attachments") or []):
        sp = att.get("saved_path", "")
        if sp and sp not in seen:
            seen.add(sp)
            if open_image_with_default_app(sp):
                print(
                    _("log.opened_app", default="[INFO] Opened image with default app."),
                    file=sys.stderr,
                )


def _collect_attachments(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collect all image attachments from items into a flat list."""
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        for att in (item.get("attachments") or []):
            sp = att.get("saved_path", "")
            if sp and sp not in seen:
                seen.add(sp)
                result.append(att)
        # Also check nested items (thread replies)
        for reply in (item.get("replies") or []):
            if isinstance(reply, dict):
                result.extend(_collect_attachments([reply]))
    return result


def _err_json(code: str, message: str, output_format: str) -> str:
    payload = {"ok": False, "error": {"code": code, "message": message}}
    return json.dumps(payload, ensure_ascii=False, indent=2) if output_format == "text" else json.dumps(payload, ensure_ascii=False)


def _fmt(template: str, **kw: Any) -> str:
    return template.format(**kw)


def _fmt_posts(result: dict[str, Any], title: str) -> str:
    lines = [f"{title} ({result['count']}):"]
    for item in result.get("items", []):
        author = item.get("author_display") or item.get("author_handle") or "?"
        text = (item.get("text") or "")[:60]
        has_img = " [img]" if item.get("images") else ""
        lines.append(f"  @{author}{has_img}: {text}")
        if item.get("saved_images"):
            for sp in item["saved_images"]:
                lines.append(f"         Image: {sp}")
    return "\n".join(lines)


def _fmt_thread(result: dict[str, Any]) -> str:
    lines = ["Thread:"]
    _fmt_thread_recursive(result.get("thread", {}), lines, 0)
    return "\n".join(lines)


def _fmt_thread_recursive(thread: dict[str, Any], lines: list[str], depth: int) -> None:
    post = thread.get("post") or {}
    indent = "  " * depth
    author = post.get("author_display") or post.get("author_handle") or "?"
    text = (post.get("text") or "")[:80]
    has_img = " [img]" if post.get("images") else ""
    lines.append(f"{indent}@{author}{has_img}: {text}")
    if post.get("saved_images"):
        for sp in post["saved_images"]:
            lines.append(f"{indent}   Image: {sp}")
    for reply in thread.get("replies") or []:
        _fmt_thread_recursive(reply, lines, depth + 1)


# ---------------------------------------------------------------------------
# router
# ---------------------------------------------------------------------------


def run_tool(args: dict[str, Any]) -> str:
    output_format = str(args.get("output_format") or "json").lower()
    action = (args.get("action") or "").strip().lower()
    if not action:
        return _err_json("invalid_argument", "The action field is required.", output_format)
    handlers = {
        "post": _handle_post,
        "profile": _handle_profile,
        "search": _handle_search,
        "timeline": _handle_timeline,
        "thread": _handle_thread,
        "like": _handle_like,
        "notifications": _handle_notifications,
    }
    handler = handlers.get(action)
    if handler:
        return handler(args, output_format)
    return _err_json("invalid_argument", f"Unsupported action: {action}.", output_format)
