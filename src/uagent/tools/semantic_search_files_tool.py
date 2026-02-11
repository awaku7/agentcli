import os
import json
import sqlite3
import math
import hashlib
import requests
from typing import List, Dict, Any

# numpy は標準ではない可能性があるため、ベクトル計算は自前実装またはインポート試行
try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

EMBEDDING_API_URL = ""
EMBEDDING_MODEL = "embeddinggemma:latest"

# 起動時（import時）に Embedding API が見えない場合はツールをロード対象から除外する。
# tools/__init__.py のローダは TOOL_SPEC が dict でない場合に登録しない（analyze_image_tool.py と同じ方式）。
#
# 挙動は環境変数で制御可能:
# - UAGENT_SEMANTIC_SEARCH_DISABLE_IF_UNREACHABLE=1/true/yes : 疎通失敗時に無効化する
# - UAGENT_EMBEDDING_API_URL : Embedding API URL 上書き
# - UAGENT_EMBEDDING_API_HEALTHCHECK_PATH : ヘルスチェックパス（既定 /v1/models）
#
# NOTE: 既定では無効化する（UAGENT_SEMANTIC_SEARCH_DISABLE_IF_UNREACHABLE 未設定時は "1" 扱い）。
#       起動直後のネットワーク未確立等で困る場合は、UAGENT_SEMANTIC_SEARCH_DISABLE_IF_UNREACHABLE=0 を指定して
#       ツール表示だけ維持し、後から疎通が回復したタイミングで利用できるようにしてください。

# 接続先の上書き（後方互換のため、既存定数を上書きする）
EMBEDDING_API_URL = os.environ.get("UAGENT_EMBEDDING_API_URL") or EMBEDDING_API_URL

_DISABLE_IF_UNREACHABLE = (
    os.environ.get("UAGENT_SEMANTIC_SEARCH_DISABLE_IF_UNREACHABLE") or "1"
).strip().lower() in (
    "1",
    "true",
    "yes",
)
_HEALTHCHECK_PATH = os.environ.get(
    "UAGENT_EMBEDDING_API_HEALTHCHECK_PATH", "/v1/models"
)


def _is_embedding_api_reachable() -> bool:
    """起動時疎通確認。

    - 失敗しても例外は投げず False を返す
    - 起動遅延を避けるためタイムアウト短め
    - /v1/models が使えない実装もあり得るため / のGETもフォールバック

    NOTE:
    - disable 条件でツールを非表示にする場合でも、原因が分かるように stderr に1回だけ出す。
    """

    base = EMBEDDING_API_URL
    # 例: http://host/v1/embeddings -> http://host
    if "/v1/" in base:
        base_root = base.split("/v1/", 1)[0]
    else:
        base_root = base.rstrip("/")

    hc_url = base_root.rstrip("/") + _HEALTHCHECK_PATH

    try:
        r = requests.get(hc_url, timeout=3)
        # 401/403/404 でも「到達できている」のでOK（=ネットワーク的に見えている）
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
    """Embedding API が到達不能でツールを無効化する場合に、理由を1回だけ表示する。"""
    try:
        # Avoid duplicate logs on reload.
        if getattr(_emit_embedding_disabled_reason, "_done", False):
            return
        setattr(_emit_embedding_disabled_reason, "_done", True)

        base = EMBEDDING_API_URL
        if "/v1/" in base:
            base_root = base.split("/v1/", 1)[0]
        else:
            base_root = base.rstrip("/")

        hc_url = base_root.rstrip("/") + _HEALTHCHECK_PATH
        msg = (
            "[tools] semantic_search_files is disabled: Embedding API is unreachable.\n"
            f"[tools] EMBEDDING_API_URL={EMBEDDING_API_URL}\n"
            f"[tools] healthcheck={hc_url}\n"
            "[tools] Set UAGENT_SEMANTIC_SEARCH_DISABLE_IF_UNREACHABLE=0 to keep the tool visible.\n"
        )
        try:
            import sys

            sys.stderr.write(msg)
            sys.stderr.flush()
        except Exception:
            # fallback
            print(msg, flush=True)
    except Exception:
        return


# NOTE: EMBEDDING_MODEL は上で再定義済み


def _get_db_path(root_dir: str) -> str:
    """ユーザーホームの .scheck/dbs 配下に、root_dirごとのハッシュ付きDBパスを返す"""
    home = os.path.expanduser("~")
    # 環境変数があれば優先
    base_dir = os.environ.get("UAGENT_CACHE_DIR") or os.environ.get("UAGENT_LOG_DIR")
    if base_dir:
        dbs_dir = os.path.join(os.path.dirname(base_dir), "dbs")
    else:
        dbs_dir = os.path.join(home, ".scheck", "dbs")

    os.makedirs(dbs_dir, exist_ok=True)

    # root_dir の絶対パスからハッシュを生成して識別
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
    """APIを叩いてEmbeddingを取得"""
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
        # print(f"[WARN] Embedding取得失敗: {e}")
        return []


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    if HAS_NUMPY:
        a = np.array(vec_a)
        b = np.array(vec_b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
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
    """単一ファイルのインデックスを同期（新規または更新があれば）"""
    fpath_abs = os.path.abspath(fpath)
    if not os.path.isfile(fpath_abs):
        return

    # ルートディレクトリの解決（指定がなければファイルの親）
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
        # print(f"DEBUG sync_file: row {row}, mtime {mtime}")

        needs_update = False
        file_id = None
        if row:
            if abs(mtime - row[1]) > 1.0:
                needs_update = True
                file_id = row[0]
        else:
            needs_update = True
        # print(f"DEBUG sync_file: needs_update {needs_update}")

        if needs_update:
            with open(fpath_abs, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            #            print(f"DEBUG sync_file: content len {len(content)} for {fpath_abs}")

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
            # print(f"DEBUG sync_file: file_id {file_id}")

            chunks = _chunk_text(content)
            #            print(f"DEBUG sync_file: chunks {len(chunks)}")
            for i, chunk in enumerate(chunks):
                vec = _get_embedding(chunk)
                embedding_json = (
                    json.dumps(vec) if vec else None
                )  # Allow NULL if no embedding
                #                print(
                #                    f"DEBUG sync_file: chunk {i} len {len(chunk)}, vec len {len(vec)}"
                #                )
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
        return f"エラー: ディレクトリが見つかりません: {root_path}"

    db_path = _get_db_path(root_abs)
    _init_db(db_path)

    # 全体同期（既存ロジック）
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

    target_files = [
        f
        for f in sorted(list(set(target_files)))
        if ".scheck" not in f and os.path.isfile(f)
    ]

    # 削除チェック
    cur.execute("SELECT id, path FROM files")
    db_files = {row[1]: row[0] for row in cur.fetchall()}
    removed = set(db_files.keys()) - set(os.path.abspath(f) for f in target_files)
    for p in removed:
        fid = db_files[p]
        cur.execute("DELETE FROM vectors WHERE file_id=?", (fid,))
        cur.execute("DELETE FROM files WHERE id=?", (fid,))
    conn.commit()
    conn.close()

    # 個別に同期
    for f in target_files:
        sync_file(f, root_abs)

    # 検索
    query_vec = _get_embedding(query)
    if not query_vec:
        return "エラー: クエリのベクトル化に失敗しました。"

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
        return "関連するドキュメントは見つかりませんでした。"

    output = [
        f"検索クエリ: {query}",
        f"対象ディレクトリ: {root_path}",
        f"ヒット件数: {len(top_results)}\n",
    ]
    for rank, res in enumerate(top_results, 1):
        fpath = id_to_path.get(res["file_id"], "unknown")
        rel_path = os.path.relpath(fpath, root_abs)
        snippet = res["text"].replace("\n", " ")[:200] + "..."
        output.append(f"[{rank}] スコア: {res['score']:.4f} | ファイル: {rel_path}")
        output.append(f"内容: {snippet}\n")

    return "\n".join(output)


def run_tool(args: Dict[str, Any]) -> str:
    query = args.get("query")
    if not query:
        return "エラー: query は必須です。"
    return semantic_search_files(
        query,
        args.get("root_path", "."),
        args.get("file_pattern", "*.md,*.txt,*.py"),
        args.get("top_k", 5),
    )


# 疎通失敗時はツール登録しない（analyze_image_tool.py と同じ方式）
if _DISABLE_IF_UNREACHABLE and not _is_embedding_api_reachable():
    _emit_embedding_disabled_reason()
    TOOL_SPEC = None  # type: ignore[assignment]
else:
    TOOL_SPEC = {
        "type": "function",
        "function": {
            "name": "semantic_search_files",
            "description": "ローカルファイルに対して意味検索（ベクトル検索）を行います。Embedding APIを使用してファイル内容をベクトル化し、質問に関連するドキュメント箇所を抽出します。初回実行時やファイル更新時はインデックス作成処理が走ります。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "検索キーワード。"},
                    "root_path": {
                        "type": "string",
                        "description": "検索対象ディレクトリ。",
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "対象拡張子（カンマ区切り）。",
                    },
                    "top_k": {"type": "integer", "description": "件数。"},
                },
                "required": ["query"],
            },
        },
    }
