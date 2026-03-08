from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

import os
from ..env_utils import env_get
import json
import sqlite3
import math
import hashlib
import requests
from typing import List, Dict, Any

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

EMBEDDING_API_URL = ""
EMBEDDING_MODEL = "embeddinggemma:latest"

EMBEDDING_API_URL = env_get("UAGENT_EMBEDDING_API_URL") or EMBEDDING_API_URL

_DISABLE_IF_UNREACHABLE = (
    env_get("UAGENT_SEMANTIC_SEARCH_DISABLE_IF_UNREACHABLE") or "1"
).strip().lower() in ("1", "true", "yes")
_HEALTHCHECK_PATH = env_get(
    "UAGENT_EMBEDDING_API_HEALTHCHECK_PATH", "/v1/models"
)


def _is_embedding_api_reachable() -> bool:
    base = EMBEDDING_API_URL
    if "/v1/" in base:
        base_root = base.split("/v1/", 1)[0]
    else:
        base_root = base.rstrip("/")

    hc_url = base_root.rstrip("/") + _HEALTHCHECK_PATH

    try:
        r = requests.get(hc_url, timeout=3)
        if 200 <= r.status_code < 500:
            return True
    except Exception:
        pass

    try:
        r = requests.get(base_root + "/", timeout=3)
        if 200 <= r.status_code < 500:
            return True
    except Exception:
        return False

    return False


def _emit_embedding_disabled_reason() -> None:
    try:
        if getattr(_emit_embedding_disabled_reason, "_done", False):
            return
        setattr(_emit_embedding_disabled_reason, "_done", True)

        base = EMBEDDING_API_URL
        if "/v1/" in base:
            base_root = base.split("/v1/", 1)[0]
        else:
            base_root = base.rstrip("/")

        hc_url = base_root.rstrip("/") + _HEALTHCHECK_PATH
        msg = _(
            "err.disabled",
            default=(
                "[tools] semantic_search_files is disabled: Embedding API is unreachable.\n"
                "[tools] EMBEDDING_API_URL={url}\n"
                "[tools] healthcheck={hc_url}\n"
                "[tools] Set UAGENT_SEMANTIC_SEARCH_DISABLE_IF_UNREACHABLE=0 to keep the tool visible.\n"
            ),
        ).format(url=EMBEDDING_API_URL, hc_url=hc_url)
        try:
            import sys

            sys.stderr.write(msg)
            sys.stderr.flush()
        except Exception:
            print(msg, flush=True)
    except Exception:
        return


def _get_db_path(root_dir: str) -> str:
    from uagent.utils.paths import get_dbs_dir

    dbs_dir = str(get_dbs_dir())
    os.makedirs(dbs_dir, exist_ok=True)
    root_abs = os.path.abspath(root_dir)
    root_hash = hashlib.sha256(root_abs.encode("utf-8")).hexdigest()[:12]
    return os.path.join(dbs_dir, f"vectors_{root_hash}.db")


def _init_db(db_path: str):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE,
            mtime REAL,
            file_size INTEGER
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS vectors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER,
            chunk_index INTEGER,
            text_content TEXT,
            embedding_json TEXT,
            FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()


def _get_embedding(text: str) -> List[float]:
    payload = {"model": EMBEDDING_MODEL, "input": text}
    try:
        resp = requests.post(
            EMBEDDING_API_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["data"][0]["embedding"]
    except Exception:
        return []


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    if HAS_NUMPY:
        a = np.array(vec_a)
        b = np.array(vec_b)
        norm_a = float(np.linalg.norm(a))
        norm_b = float(np.linalg.norm(b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))
    else:
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> List[str]:
    if not text:
        return []
    chunks = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunks.append(text[start:end])
        if end == text_len:
            break
        start += chunk_size - overlap
    return chunks


def sync_file(fpath: str, root_dir: str = "."):
    fpath_abs = os.path.abspath(fpath)
    if not os.path.isfile(fpath_abs):
        return

    root_abs = os.path.abspath(root_dir)
    db_path = _get_db_path(root_abs)
    _init_db(db_path)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    try:
        mtime = os.path.getmtime(fpath_abs)
        size = os.path.getsize(fpath_abs)

        cur.execute("SELECT id, mtime FROM files WHERE path=?", (fpath_abs,))
        row = cur.fetchone()

        needs_update = False
        file_id = None
        if row:
            if abs(mtime - row[1]) > 1.0:
                needs_update = True
                file_id = row[0]
        else:
            needs_update = True

        if needs_update:
            with open(fpath_abs, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            if file_id:
                cur.execute("DELETE FROM vectors WHERE file_id=?", (file_id,))
                cur.execute(
                    "UPDATE files SET mtime=?, file_size=? WHERE id=?",
                    (mtime, size, file_id),
                )
            else:
                cur.execute(
                    "INSERT INTO files (path, mtime, file_size) VALUES (?, ?, ?)",
                    (fpath_abs, mtime, size),
                )
                file_id = cur.lastrowid

            chunks = _chunk_text(content)
            for i, chunk in enumerate(chunks):
                vec = _get_embedding(chunk)
                embedding_json = json.dumps(vec) if vec else None
                cur.execute(
                    "INSERT INTO vectors (file_id, chunk_index, text_content, embedding_json) VALUES (?, ?, ?, ?)",
                    (file_id, i, chunk, embedding_json),
                )

            conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def semantic_search_files(
    query: str,
    root_path: str = ".",
    file_pattern: str = "*.md,*.txt,*.py",
    top_k: int = 5,
) -> str:
    import glob

    root_abs = os.path.abspath(root_path)
    if not os.path.isdir(root_abs):
        return _(
            "err.dir_not_found", default="Error: Directory not found: {root_path}"
        ).format(root_path=root_path)

    db_path = _get_db_path(root_abs)
    _init_db(db_path)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    patterns = [p.strip() for p in file_pattern.split(",")]
    target_files = []
    for p in patterns:
        search_path = os.path.join(root_abs, "**", p)
        try:
            target_files.extend(glob.glob(search_path, recursive=True))
        except Exception:
            target_files.extend(glob.glob(os.path.join(root_abs, p)))

    from uagent.utils.scan_filters import is_ignored_path

    target_files = [
        f
        for f in sorted(list(set(target_files)))
        if (not is_ignored_path(f)) and os.path.isfile(f)
    ]

    cur.execute("SELECT id, path FROM files")
    db_files = {row[1]: row[0] for row in cur.fetchall()}
    removed = set(db_files.keys()) - set(os.path.abspath(f) for f in target_files)
    for p in removed:
        fid = db_files[p]
        cur.execute("DELETE FROM vectors WHERE file_id=?", (fid,))
        cur.execute("DELETE FROM files WHERE id=?", (fid,))
    conn.commit()
    conn.close()

    for f in target_files:
        sync_file(f, root_abs)

    query_vec = _get_embedding(query)
    if not query_vec:
        return _("err.vec_fail", default="Error: Failed to vectorize the query.")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT file_id, text_content, embedding_json FROM vectors")
    rows = cur.fetchall()

    results = []
    for row in rows:
        fid, text, vec_json = row
        score = _cosine_similarity(query_vec, json.loads(vec_json))
        results.append({"score": score, "file_id": fid, "text": text})

    results.sort(key=lambda x: x["score"], reverse=True)
    top_results = results[:top_k]

    cur.execute("SELECT id, path FROM files")
    id_to_path = {row[0]: row[1] for row in cur.fetchall()}
    conn.close()

    if not top_results:
        return _("out.not_found", default="No relevant documents were found.")

    output = [
        _("out.query", default="Search Query: {query}").format(query=query),
        _("out.target_dir", default="Target Directory: {root_path}").format(
            root_path=root_path
        ),
        _("out.hits", default="Hits: {count}\n").format(count=len(top_results)),
    ]
    for rank, res in enumerate(top_results, 1):
        fpath = id_to_path.get(res["file_id"], "unknown")
        rel_path = os.path.relpath(fpath, root_abs)
        snippet = res["text"].replace("\n", " ")[:200] + "..."
        output.append(
            _(
                "out.result_item",
                default="[{rank}] Score: {score:.4f} | File: {rel_path}",
            ).format(rank=rank, score=res["score"], rel_path=rel_path)
        )
        output.append(
            _("out.result_content", default="Content: {snippet}\n").format(
                snippet=snippet
            )
        )

    return "\n".join(output)


def run_tool(args: Dict[str, Any]) -> str:
    query = args.get("query")
    if not query:
        return _("err.query_required", default="Error: query is required.")
    return semantic_search_files(
        query,
        args.get("root_path", "."),
        args.get("file_pattern", "*.md,*.txt,*.py"),
        args.get("top_k", 5),
    )


if _DISABLE_IF_UNREACHABLE and not _is_embedding_api_reachable():
    _emit_embedding_disabled_reason()
    TOOL_SPEC = None  # type: ignore[assignment]
else:
    TOOL_SPEC = {
        "type": "function",
        "function": {
            "name": "semantic_search_files",
            "description": _(
                "tool.description",
                default="Performs a semantic search (vector search) against local files. Uses the Embedding API to vectorize file contents and extracts relevant document parts. Indexing is performed on the first run or when files are updated.",
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": _(
                            "param.query.description", default="Search query keyword."
                        ),
                    },
                    "root_path": {
                        "type": "string",
                        "description": _(
                            "param.root_path.description",
                            default="Search target directory.",
                        ),
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": _(
                            "param.file_pattern.description",
                            default="Target extensions (comma-separated).",
                        ),
                    },
                    "top_k": {
                        "type": "integer",
                        "description": _(
                            "param.top_k.description", default="Number of results."
                        ),
                    },
                },
                "required": ["query"],
            },
        },
    }
