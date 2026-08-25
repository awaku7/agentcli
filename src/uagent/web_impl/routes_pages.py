"""Web frontend routes (split from web.py)."""

from __future__ import annotations

from datetime import datetime
import os
import re
import shutil
from typing import Any
from uuid import uuid4

from fastapi import File, Form, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from ..i18n import _
from .. import util_tools as tools_util
from .app import STATIC_DIR, app
from .rooms import web_manager


@app.get("/")
async def get_root():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    # Fallback: create room and redirect (legacy template)
    room_id = uuid4().hex
    return RedirectResponse(url=f"/room/{room_id}")


@app.get("/room/{room_id}")
async def get_room(room_id: str):
    # Ensure room exists
    web_manager.get_room(room_id)
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("Room created. SPA not built.", status_code=200)


@app.post("/upload")
async def upload_files(
    room: str = Form(""),
    files: list[UploadFile] = File(...),
):
    try:
        raw_room_id = (
            re.sub(r"[^A-Za-z0-9._-]+", "_", str(room or "").strip()) or "default"
        )
        room_obj = web_manager.get_room(raw_room_id)
        base = os.path.abspath(room_obj.base_dir)
        upload_root = os.path.join(base, ".uagent_web_uploads", raw_room_id)
        os.makedirs(upload_root, exist_ok=True)

        saved: list[dict[str, Any]] = []
        for upload in files or []:
            if upload is None:
                continue
            original_name = os.path.basename(
                str(getattr(upload, "filename", "") or "upload")
            )
            safe_name = (
                re.sub(r"[^A-Za-z0-9._-]+", "_", original_name).strip("._") or "upload"
            )
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            dst_path = os.path.join(upload_root, f"{stamp}_{safe_name}")
            with open(dst_path, "wb") as out_f:
                shutil.copyfileobj(upload.file, out_f)

            mime = str(getattr(upload, "content_type", "") or "").lower().strip()
            is_image = mime.startswith("image/")
            is_video = (
                mime.startswith("video/") and os.path.getsize(dst_path) <= 50_000_000
            )
            item: dict[str, Any] = {
                "name": original_name,
                "saved_path": dst_path,
                "path": dst_path,
                "mime": mime,
                "type": "image" if is_image else ("video" if is_video else "file"),
            }
            if is_image:
                try:
                    item["data_url"] = tools_util.image_file_to_data_url(dst_path)
                except Exception:
                    pass
            saved.append(item)

        return {"ok": True, "files": saved}
    except Exception as e:
        return {"ok": False, "error": repr(e)}


@app.get("/local-file")
async def get_local_file(path: str, room_id: str = ""):
    try:
        raw_room_id = re.sub(r"[^A-Za-z0-9._-]+", "_", str(room_id or "").strip())
        if raw_room_id:
            room_obj = web_manager.get_room(raw_room_id)
            base_dir = os.path.abspath(room_obj.base_dir)
        else:
            base_dir = os.path.abspath(os.getcwd())
        raw = str(path or "").strip()
        if not raw:
            raise ValueError(_("missing path"))
        full = os.path.abspath(raw)
        if not os.path.isabs(raw):
            full = os.path.abspath(os.path.join(base_dir, raw))
        full_norm = os.path.normpath(full)
        base_norm = os.path.normpath(base_dir)
        if not (full_norm == base_norm or full_norm.startswith(base_norm + os.sep)):
            raise ValueError(_("path outside workdir"))
        if not os.path.isfile(full_norm):
            raise FileNotFoundError(full_norm)
        return FileResponse(full_norm)
    except Exception:
        raise
