from __future__ import annotations

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

import os
from ..env_utils import env_get
import json
import sqlite3
import math
import threading
import hashlib
import requests
from typing import Any

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

EMBEDDING_PROVIDER = (
    (env_get("UAGENT_EMBEDDING_PROVIDER") or env_get("UAGENT_PROVIDER") or "")
    .strip()
    .lower()
)

_ENABLE_SEMANTIC_SEARCH = str(
    env_get("UAGENT_ENABLE_SEMANTIC_SEARCH") or ""
).strip().lower() in {"1", "true", "yes", "on"}

_BM25_MODE = (
    str(env_get("UAGENT_SEMANTIC_SEARCH_MODE") or "").strip().lower() == "bm25"
)

_ALLOWED_PROVIDERS = {
    "openai",
    "azure",
    "bedrock",
    "openrouter",
    "ollama",
    "nvidia",
    "gemini",
    "vertexai",
}
_DEFAULT_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "azure": "https://api.openai.com/v1",
    "bedrock": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "ollama": "http://localhost:11434/v1",
    "nvidia": "https://integrate.api.nvidia.com/v1",
}

LOAD_DISABLED_REASON = ""

_DB_LOCK = threading.RLock()


def _embedding_env(provider: str, suffix: str, *, default: str = "") -> str:
    key = f"UAGENT_{provider.upper()}_EMBEDDING_{suffix.upper()}"
    value = env_get(key)
    if not value and provider == "openai":
        if suffix == "api_key":
            value = env_get("UAGENT_OPENAI_API_KEY") or env_get("UAGENT_API_KEY")
        elif suffix == "base_url":
            value = env_get("UAGENT_OPENAI_BASE_URL")
    return (value or default).strip()


def _resolve_embedding_config() -> dict[str, Any]:
    provider = EMBEDDING_PROVIDER
    if provider not in _ALLOWED_PROVIDERS:
        return {}

    cfg: dict[str, Any] = {"provider": provider}

    if provider == "azure":
        base_url = _embedding_env(provider, "base_url")
        api_key = _embedding_env(provider, "api_key")
        api_version = _embedding_env(provider, "api_version")
        depname = _embedding_env(provider, "depname")
        if not (base_url and api_key and api_version and depname):
            return {}
        cfg.update(
            {
                "base_url": base_url,
                "api_key": api_key,
                "api_version": api_version,
                "depname": depname,
                "endpoint": base_url.rstrip("/")
                + f"/openai/deployments/{depname}/embeddings?api-version={api_version}",
                "headers": {"Content-Type": "application/json", "api-key": api_key},
                "payload_base": {},
            }
        )
        return cfg

    if provider in {"gemini", "vertexai"}:
        api_key = _embedding_env(provider, "api_key")
        depname = _embedding_env(provider, "depname")
        if not (api_key and depname):
            return {}
        cfg.update(
            {
                "api_key": api_key,
                "depname": depname,
            }
        )
        return cfg

    base_url = _embedding_env(
        provider,
        "base_url",
        default=_DEFAULT_BASE_URLS.get(provider, "https://api.openai.com/v1"),
    )
    api_key = _embedding_env(provider, "api_key")
    depname = _embedding_env(provider, "depname")

    if provider in {"openai", "bedrock", "openrouter", "ollama", "nvidia"}:
        if not depname:
            return {}
    if provider in {"openai", "nvidia", "openrouter", "bedrock"} and not api_key:
        return {}
    if provider == "ollama":
        api_key = api_key or ""

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    cfg.update(
        {
            "base_url": base_url,
            "api_key": api_key,
            "depname": depname,
            "endpoint": base_url.rstrip("/") + "/embeddings",
            "headers": headers,
            "payload_base": {"model": depname} if depname else {},
        }
    )
    return cfg


def _is_embedding_api_reachable() -> bool:
    cfg = _resolve_embedding_config()
    if not cfg:
        return False

    provider = cfg.get("provider")
    if provider in {"gemini", "vertexai"}:
        # gemini / vertexai の場合は API キーとモデル名があれば疎通可能とみなす
        return bool(cfg.get("api_key") and cfg.get("depname"))

    base_url = str(cfg.get("base_url") or "").rstrip("/")
    candidates = [base_url, base_url + "/"]
    if provider == "azure":
        api_version = str(cfg.get("api_version") or "")
        depname = str(cfg.get("depname") or "")
        if api_version and depname:
            candidates.append(
                base_url + f"/openai/deployments/{depname}?api-version={api_version}"
            )

    for url in candidates:
        if not url:
            continue
        try:
            r = requests.get(url, timeout=3)
            if 200 <= r.status_code < 500:
                return True
        except Exception:
            continue
    return False


def _embedding_identity() -> str:
    cfg = _resolve_embedding_config()
    if not cfg:
        return "no-embedding"
    identity = {
        "provider": str(cfg.get("provider") or ""),
        "base_url": str(cfg.get("base_url") or ""),
        "api_version": str(cfg.get("api_version") or ""),
        "depname": str(cfg.get("depname") or ""),
    }
    raw = json.dumps(identity, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def _get_db_path(root_dir: str) -> str:
    from uagent.utils.paths import get_dbs_dir

    dbs_dir = str(get_dbs_dir())
    os.makedirs(dbs_dir, exist_ok=True)
    root_abs = os.path.abspath(root_dir)
    root_hash = hashlib.sha256(root_abs.encode("utf-8")).hexdigest()[:12]
    if _BM25_MODE:
        return os.path.join(dbs_dir, f"bm25_{root_hash}.db")
    embed_hash = _embedding_identity()
    return os.path.join(dbs_dir, f"vectors_{root_hash}_{embed_hash}.db")


def _init_db(db_path: str):
    with _DB_LOCK:
        conn = sqlite3.connect(db_path, timeout=30)
        cur = conn.cursor()
        try:
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA busy_timeout=30000")
        except Exception:
            pass
        cur.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE,
                mtime REAL,
                file_size INTEGER
            )
        """)
        if _BM25_MODE:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id INTEGER,
                    chunk_index INTEGER,
                    text_content TEXT,
                    num_tokens INTEGER DEFAULT 0,
                    FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS terms (
                    term TEXT NOT NULL,
                    chunk_id INTEGER NOT NULL,
                    frequency INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY (term, chunk_id),
                    FOREIGN KEY(chunk_id) REFERENCES chunks(id) ON DELETE CASCADE
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_terms_term ON terms(term)")
        else:
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


def _get_embedding(text: str) -> list[float]:
    cfg = _resolve_embedding_config()
    if not cfg:
        raise RuntimeError("Embedding config is not set")

    provider = cfg.get("provider")
    if provider in {"gemini", "vertexai"}:
        try:
            from google import genai
        except ImportError:
            raise RuntimeError(
                "google-genai package is required for gemini/vertexai embeddings"
            )

        api_key = cfg.get("api_key")
        depname = cfg.get("depname")
        if not (api_key and depname):
            raise RuntimeError(
                "Gemini/VertexAI embedding API key or model name is missing"
            )

        # google-genai SDK を使用して埋め込みを生成
        if provider == "vertexai":
            # Vertex AI の場合は http_options または環境変数経由で初期化されることが多いが、
            # google-genai SDK では vertexai=True を指定して初期化します
            client = genai.Client(api_key=api_key, vertexai=True)
        else:
            client = genai.Client(api_key=api_key)

        response = client.models.embed_content(
            model=depname,
            contents=text,
        )
        if response and response.embeddings:
            # 1つのテキストに対する埋め込みなので、最初の要素の values を取得
            emb = response.embeddings[0].values
            if isinstance(emb, list):
                return [float(v) for v in emb]
        raise RuntimeError(
            "Gemini/VertexAI embedding response did not contain a vector"
        )

    payload = dict(cfg.get("payload_base") or {})
    payload["input"] = text
    resp = requests.post(
        str(cfg["endpoint"]),
        json=payload,
        headers=dict(cfg.get("headers") or {}),
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict):
        rows = data.get("data")
        if isinstance(rows, list) and rows:
            emb = rows[0].get("embedding") if isinstance(rows[0], dict) else None
            if isinstance(emb, list):
                return emb
        emb = data.get("embedding")
        if isinstance(emb, list):
            return emb
    raise RuntimeError("Embedding response did not contain a vector")


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    if HAS_NUMPY:
        a = np.array(vec_a)
        b = np.array(vec_b)
        norm_a = float(np.linalg.norm(a))
        norm_b = float(np.linalg.norm(b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))
    else:
        dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=False))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


def _bm25_tokenize(text: str) -> list[str]:
    """Simple multilingual tokenizer for BM25. Handles CJK by unigram."""
    import re
    text = text.lower()
    tokens: list[str] = []
    # Split into alphanumeric words and CJK characters
    for part in re.findall(r"[a-z0-9]+|[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af\u0e00-\u0e7f]", text):
        if re.match(r"^[a-z0-9]+$", part):
            tokens.append(part)
        else:
            # CJK/Thai: unigram
            tokens.extend(list(part))
    return tokens


def _bm25_score(
    query_tokens: list[str],
    doc_freqs: dict[str, int],
    doc_len: int,
    avg_doc_len: float,
    total_docs: int,
    doc_count_with_term: dict[str, int],
    k1: float = 1.2,
    b: float = 0.75,
) -> float:
    """Compute BM25 score for a single document."""
    score = 0.0
    for term in query_tokens:
        tf = doc_freqs.get(term, 0)
        if tf == 0:
            continue
        df = doc_count_with_term.get(term, 0)
        idf = math.log((total_docs - df + 0.5) / (df + 0.5) + 1.0)
        score += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_len / avg_doc_len))
    return score


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> list[str]:
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


def _sync_file_bm25(fpath_abs: str, root_abs: str, db_path: str):
    """Index a file using BM25 tokenization (no embedding API call)."""
    import time

    _init_db(db_path)
    max_attempts = 5
    backoff_s = 0.2

    for attempt in range(1, max_attempts + 1):
        with _DB_LOCK:
            conn = sqlite3.connect(db_path, timeout=30)
            cur = conn.cursor()
            try:
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA busy_timeout=30000")
            except Exception:
                pass
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
                        # Remove old chunks and terms
                        cur.execute("DELETE FROM chunks WHERE file_id=?", (file_id,))
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
                        tokens = _bm25_tokenize(chunk)
                        if not tokens:
                            continue
                        from collections import Counter
                        term_counts = Counter(tokens)
                        cur.execute(
                            "INSERT INTO chunks (file_id, chunk_index, text_content, num_tokens) VALUES (?, ?, ?, ?)",
                            (file_id, i, chunk, len(tokens)),
                        )
                        chunk_id = cur.lastrowid
                        for term, freq in term_counts.items():
                            cur.execute(
                                "INSERT OR REPLACE INTO terms (term, chunk_id, frequency) VALUES (?, ?, ?)",
                                (term, chunk_id, freq),
                            )
                    conn.commit()
                return
            except sqlite3.OperationalError as e:
                msg = str(e).lower()
                if "database is locked" in msg or "database table is locked" in msg:
                    if attempt < max_attempts:
                        time.sleep(backoff_s * attempt)
                        continue
                raise RuntimeError(f"Failed to index {fpath_abs}: {e}") from e
            except Exception as e:
                raise RuntimeError(f"Failed to index {fpath_abs}: {e}") from e
            finally:
                conn.close()


def sync_file(fpath: str, root_dir: str = "."):
    if not _ENABLE_SEMANTIC_SEARCH:
        return None

    fpath_abs = os.path.abspath(fpath)
    if not os.path.isfile(fpath_abs):
        return

    root_abs = os.path.abspath(root_dir)
    db_path = _get_db_path(root_abs)

    if _BM25_MODE:
        return _sync_file_bm25(fpath_abs, root_abs, db_path)

    import time

    _init_db(db_path)

    max_attempts = 5
    backoff_s = 0.2

    for attempt in range(1, max_attempts + 1):
        with _DB_LOCK:
            conn = sqlite3.connect(db_path, timeout=30)
            cur = conn.cursor()
            try:
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA busy_timeout=30000")
            except Exception:
                pass

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
                        try:
                            vec = _get_embedding(chunk)
                        except Exception:
                            continue
                        if not vec:
                            continue
                        embedding_json = json.dumps(vec)
                        cur.execute(
                            "INSERT INTO vectors (file_id, chunk_index, text_content, embedding_json) VALUES (?, ?, ?, ?)",
                            (file_id, i, chunk, embedding_json),
                        )

                    conn.commit()
                return
            except sqlite3.OperationalError as e:
                msg = str(e).lower()
                if "database is locked" in msg or "database table is locked" in msg:
                    if attempt < max_attempts:
                        time.sleep(backoff_s * attempt)
                        continue
                raise RuntimeError(f"Failed to index {fpath_abs}: {e}") from e
            except Exception as e:
                raise RuntimeError(f"Failed to index {fpath_abs}: {e}") from e
            finally:
                conn.close()


def _semantic_search_bm25(
    query: str,
    root_abs: str,
    db_path: str,
    patterns: list[str],
    top_k: int,
) -> str:
    """BM25 search (no embedding API call)."""
    import glob

    _init_db(db_path)

    with _DB_LOCK:
        conn = sqlite3.connect(db_path, timeout=30)
        cur = conn.cursor()
        try:
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA busy_timeout=30000")
        except Exception:
            pass

        target_files = []
        for p in patterns:
            search_path = os.path.join(root_abs, "**", p)
            try:
                target_files.extend(glob.glob(search_path, recursive=True))
            except Exception:
                target_files.extend(glob.glob(os.path.join(root_abs, p)))

        from uagent.utils.scan_filters import is_ignored_path
        target_files = [
            f for f in sorted(list(set(target_files)))
            if (not is_ignored_path(f)) and os.path.isfile(f)
        ]

        cur.execute("SELECT id, path FROM files")
        db_files = {row[1]: row[0] for row in cur.fetchall()}
        removed = set(db_files.keys()) - set(os.path.abspath(f) for f in target_files)
        for p in removed:
            fid = db_files[p]
            cur.execute("DELETE FROM chunks WHERE file_id=?", (fid,))
            cur.execute("DELETE FROM files WHERE id=?", (fid,))

        cur.execute("SELECT COUNT(*) FROM chunks")
        chunk_count = int(cur.fetchone()[0] or 0)
        conn.commit()

    if chunk_count == 0:
        return _(
            "err.no_index",
            default="Error: No indexed vectors found. Run index_files first.",
        )

    # Tokenize query
    query_tokens = _bm25_tokenize(query)
    if not query_tokens:
        return _("err.vec_fail", default="Error: Failed to vectorize the query.")

    with _DB_LOCK:
        conn = sqlite3.connect(db_path, timeout=30)
        cur = conn.cursor()
        try:
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA busy_timeout=30000")
        except Exception:
            pass

        # Get total document count and average length
        cur.execute("SELECT COUNT(*), COALESCE(AVG(num_tokens), 0) FROM chunks")
        total_docs, avg_doc_len = cur.fetchone()
        total_docs = int(total_docs)
        avg_doc_len = float(avg_doc_len)

        # Get document frequency for each query term
        doc_count_with_term: dict[str, int] = {}
        placeholders = ",".join("?" for _ in query_tokens)
        cur.execute(
            f"SELECT term, COUNT(DISTINCT chunk_id) FROM terms WHERE term IN ({placeholders}) GROUP BY term",
            query_tokens,
        )
        for term, df in cur.fetchall():
            doc_count_with_term[term] = df

        # Get all chunks with their term frequencies for scoring
        cur.execute("""
            SELECT c.id, c.file_id, c.text_content, c.num_tokens,
                   t.term, t.frequency
            FROM chunks c
            LEFT JOIN terms t ON t.chunk_id = c.id
            ORDER BY c.id
        """)
        rows = cur.fetchall()

    # Aggregate by chunk and compute BM25 scores
    from collections import defaultdict
    chunk_data: dict[int, dict] = {}
    for row in rows:
        cid, fid, text, nt, term, freq = row
        if cid not in chunk_data:
            chunk_data[cid] = {
                "file_id": fid,
                "text": text,
                "num_tokens": nt,
                "term_freqs": {},
            }
        if term:
            chunk_data[cid]["term_freqs"][term] = freq

    results = []
    for cid, data in chunk_data.items():
        score = _bm25_score(
            query_tokens,
            data["term_freqs"],
            data["num_tokens"] or 1,
            avg_doc_len,
            total_docs,
            doc_count_with_term,
        )
        if score > 0:
            results.append({"score": score, "file_id": data["file_id"], "text": data["text"]})

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
            root_path=root_abs
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


def semantic_search_files(
    query: str,
    root_path: str = ".",
    file_pattern: str = "*.md,*.txt,*.py",
    top_k: int = 5,
) -> str:
    if not _ENABLE_SEMANTIC_SEARCH:
        return ""
    import glob

    root_abs = os.path.abspath(root_path)
    if not os.path.isdir(root_abs):
        return _(
            "err.dir_not_found", default="Error: Directory not found: {root_path}"
        ).format(root_path=root_path)

    db_path = _get_db_path(root_abs)

    patterns = [p.strip() for p in file_pattern.split(",")]

    if _BM25_MODE:
        return _semantic_search_bm25(query, root_abs, db_path, patterns, top_k)

    _init_db(db_path)

    with _DB_LOCK:
        conn = sqlite3.connect(db_path, timeout=30)
        cur = conn.cursor()
        try:
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA busy_timeout=30000")
        except Exception:
            pass
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
        cur.execute("SELECT COUNT(*) FROM vectors")
        vector_count = int(cur.fetchone()[0] or 0)
        conn.commit()
        conn.close()

    if vector_count == 0:
        return _(
            "err.no_index",
            default="Error: No indexed vectors found. Run index_files first.",
        )

    query_vec = _get_embedding(query)
    if not query_vec:
        return _("err.vec_fail", default="Error: Failed to vectorize the query.")

    with _DB_LOCK:
        conn = sqlite3.connect(db_path, timeout=30)
        cur = conn.cursor()
        try:
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA busy_timeout=30000")
        except Exception:
            pass
        cur.execute("SELECT file_id, text_content, embedding_json FROM vectors")
        rows = cur.fetchall()

    results = []
    for row in rows:
        fid, text, vec_json = row
        if not vec_json:
            continue
        try:
            vec = json.loads(vec_json)
        except Exception:
            continue
        score = _cosine_similarity(query_vec, vec)
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


def run_tool(args: dict[str, Any]) -> str:
    query = args.get("query")
    if not query:
        return _("err.query_required", default="Error: query is required.")
    return semantic_search_files(
        query,
        args.get("root_path", "."),
        args.get("file_pattern", "*.md,*.txt,*.py"),
        args.get("top_k", 5),
    )


if not _ENABLE_SEMANTIC_SEARCH:
    TOOL_SPEC = None  # type: ignore[assignment]
else:
    TOOL_SPEC = {
        "type": "function",
        "tool_genre": "devel",
        "function": {
            "name": "semantic_search_files",
            "description": _(
                "tool.description",
                default="Performs a semantic search (vector search) against local files. Uses the Embedding API to vectorize file contents and extracts relevant document passages.",
            ),
            "x_search_terms": _(
                "x_search_terms",
                default=[
                    "semantic_search_files",
                    "semantic search files",
                    "semantic search",
                    "vector search",
                    "embedding search",
                    "local file search",
                    "search files",
                    "document search",
                    "file retrieval",
                    "semantic retrieval",
                ],
            ),
            "x_search_terms_en": [
                "semantic_search_files",
                "semantic search files",
                "semantic search",
                "vector search",
                "embedding search",
                "local file search",
                "search files",
                "document search",
                "file retrieval",
                "semantic retrieval",
            ],
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
