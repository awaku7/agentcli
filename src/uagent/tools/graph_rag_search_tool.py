# -*- coding: utf-8 -*-
"""graph_rag_search_tool

GraphRAG (Graph + Vector hybrid retrieval) for local files.
"""

from __future__ import annotations
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


import ast
import glob
import json
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Reuse embedding + DB path from semantic_search_files_tool
from . import semantic_search_files_tool as vec_tool

# -------------------------
# DB schema (graph tables)
# -------------------------


def _init_graph_tables(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Nodes
    cur.execute("""
        CREATE TABLE IF NOT EXISTS entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            norm_name TEXT NOT NULL,
            UNIQUE(norm_name, type)
        )
        """)

    # Chunk <-> Entity mapping
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chunk_entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vector_id INTEGER NOT NULL,
            entity_id INTEGER NOT NULL,
            weight REAL DEFAULT 1.0,
            FOREIGN KEY(vector_id) REFERENCES vectors(id) ON DELETE CASCADE,
            FOREIGN KEY(entity_id) REFERENCES entities(id) ON DELETE CASCADE
        )
        """)
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_chunk_entities_entity ON chunk_entities(entity_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_chunk_entities_vector ON chunk_entities(vector_id)"
    )

    # Relations (edges)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS relations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            src_entity_id INTEGER NOT NULL,
            rel_type TEXT NOT NULL,
            dst_entity_id INTEGER NOT NULL,
            vector_id INTEGER,
            confidence REAL DEFAULT 0.5,
            FOREIGN KEY(src_entity_id) REFERENCES entities(id) ON DELETE CASCADE,
            FOREIGN KEY(dst_entity_id) REFERENCES entities(id) ON DELETE CASCADE,
            FOREIGN KEY(vector_id) REFERENCES vectors(id) ON DELETE CASCADE
        )
        """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_rel_src ON relations(src_entity_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_rel_dst ON relations(dst_entity_id)")

    # Per chunk meta (file type / page / sheet)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS vector_meta (
            vector_id INTEGER PRIMARY KEY,
            file_kind TEXT,
            page_index INTEGER,
            sheet_name TEXT,
            extra_json TEXT,
            FOREIGN KEY(vector_id) REFERENCES vectors(id) ON DELETE CASCADE
        )
        """)

    # Track indexing version per file to avoid rebuilding graph unnecessarily
    cur.execute("""
        CREATE TABLE IF NOT EXISTS graph_files (
            file_id INTEGER PRIMARY KEY,
            graph_mtime REAL,
            graph_version INTEGER,
            FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE
        )
        """)

    conn.commit()
    conn.close()


# -------------------------
# Text extraction
# -------------------------


def _read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def _extract_pdf_pptx_text(path: str) -> Tuple[str, List[Tuple[int, str]], List[str]]:
    """Return (all_text, pages[(page_index, text)], warnings)."""

    warnings: List[str] = []
    try:
        from . import read_pptx_pdf as rpp
    except Exception as e:  # pragma: no cover
        return "", [], [f"Failed to import read_pptx_pdf: {e}"]

    try:
        text_all = rpp.run_tool({"path": path, "page_index": 0, "max_chars": 2000000})
        if not isinstance(text_all, str):
            text_all = str(text_all)
        text_all = text_all.strip()
        if not text_all:
            warnings.append("Could not extract text from PDF/PPTX (empty).")
        # No page boundaries available -> one pseudo page
        pages = [(1, text_all)] if text_all else []
        return text_all, pages, warnings
    except Exception as e:
        return "", [], [f"Failed to execute read_pptx_pdf: {e}"]


def _extract_xlsx_text(path: str) -> Tuple[str, List[Tuple[str, str]], List[str]]:
    """Return (all_text, sheets[(sheet_name,text)], warnings)."""

    warnings: List[str] = []
    try:
        from . import exstruct_tool

        _ = exstruct_tool.TOOL_SPEC
        (
            DestinationOptions,
            ExStructEngine,
            FilterOptions,
            FormatOptions,
            OutputOptions,
            StructOptions,
            export_print_areas_as,
            set_table_detection_params,
        ) = exstruct_tool._import_exstruct()  # type: ignore[attr-defined]

        engine = ExStructEngine(
            options=StructOptions(),
            output=OutputOptions(
                format=FormatOptions(),
                filters=FilterOptions(),
            ),
        )
        wb = engine.extract(str(path))
        exported = wb.export(format="json", pretty=False)
        data = json.loads(exported)
        sheets: List[Tuple[str, str]] = []
        for sheet_name, sh in (data.get("sheets", {}) or {}).items():
            name = sheet_name
            parts: List[str] = [f"[SHEET] {name}"]
            for tbl in sh.get("tables", []) or []:
                title = tbl.get("title")
                if title:
                    parts.append(f"[TABLE] {title}")
                header = tbl.get("header")
                if header:
                    parts.append("[HEADER] " + " | ".join(str(x) for x in header))
                rows = tbl.get("rows") or []
                for r in rows[:200]:
                    parts.append("[ROW] " + " | ".join(str(x) for x in r))
            rows = sh.get("rows", [])
            if isinstance(rows, list):
                for row in rows[:500]:
                    v = row.get("value")
                    if v is None:
                        continue
                    parts.append(f"[CELL] {row}: {v}")
            text = "\n".join(parts).strip()
            if text:
                sheets.append((name, text))

        all_text = "\n\n".join(t for _, t in sheets).strip()
        if not all_text:
            warnings.append("Extracted text from exstruct was empty.")
        return all_text, sheets, warnings

    except Exception as e:
        warnings.append(f"Failed to extract using exstruct: {e}")

    return "", [], warnings


# -------------------------
# Chunking & indexing
# -------------------------


def _chunk_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    return vec_tool._chunk_text(text, chunk_size=chunk_size, overlap=overlap)


def _ensure_vector_index_for_text(
    *,
    db_path: str,
    file_id: int,
    file_kind: str,
    text: str,
    page_index: Optional[int] = None,
    sheet_name: Optional[str] = None,
    chunk_size: int = 800,
    overlap: int = 150,
) -> List[int]:
    """Insert vectors rows for the given (text) and return inserted vector ids."""

    chunks = _chunk_text(text, chunk_size=chunk_size, overlap=overlap)
    if not chunks:
        return []

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    inserted_ids: List[int] = []
    for idx, chunk in enumerate(chunks):
        vec = vec_tool._get_embedding(chunk)
        embedding_json = json.dumps(vec) if vec else None

        cur.execute(
            "INSERT INTO vectors (file_id, chunk_index, text_content, embedding_json) VALUES (?, ?, ?, ?)",
            (file_id, idx, chunk, embedding_json),
        )
        vector_id = int(cur.lastrowid)
        inserted_ids.append(vector_id)

        cur.execute(
            "INSERT OR REPLACE INTO vector_meta (vector_id, file_kind, page_index, sheet_name, extra_json) VALUES (?, ?, ?, ?, ?)",
            (vector_id, file_kind, page_index, sheet_name, None),
        )

    conn.commit()
    conn.close()
    return inserted_ids


# -------------------------
# Entity extraction
# -------------------------


_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
_CAMEL_RE = re.compile(r"\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+\b")
_QUALNAME_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_\.]*\b")
_FILE_RE = re.compile(r"\b[^\s]+\.(py|md|txt|pdf|pptx|xlsx)\b", re.IGNORECASE)


def _norm(s: str) -> str:
    return s.strip().lower()


def _extract_entities_from_text(text: str) -> List[Tuple[str, str]]:
    """Return list of (name,type)."""
    found: List[Tuple[str, str]] = []
    for m in _QUALNAME_RE.finditer(text or ""):
        found.append((m.group(0), "qualname"))
    for m in _CAMEL_RE.finditer(text or ""):
        found.append((m.group(0), "term"))
    for m in _WORD_RE.finditer(text or ""):
        tok = m.group(0)
        found.append((tok, "term"))
    for m in _FILE_RE.finditer(text or ""):
        found.append((m.group(0), "file"))
    seen = set()
    out: List[Tuple[str, str]] = []
    for name, typ in found:
        key = (name, typ)
        if key in seen:
            continue
        seen.add(key)
        out.append((name, typ))
    return out[:500]


def _upsert_entity(cur: sqlite3.Cursor, name: str, typ: str) -> int:
    n = _norm(name)
    cur.execute(
        "INSERT OR IGNORE INTO entities (name, type, norm_name) VALUES (?, ?, ?)",
        (name, typ, n),
    )
    cur.execute("SELECT id FROM entities WHERE norm_name=? AND type=?", (n, typ))
    row = cur.fetchone()
    if not row:
        raise RuntimeError("entity upsert failed")
    return int(row[0])


def _link_chunk_entities(
    db_path: str,
    vector_id: int,
    entities: List[Tuple[str, str]],
    cur: sqlite3.Cursor = None,
) -> List[int]:
    if cur is None:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        close_conn = True
    else:
        close_conn = False
    entity_ids: List[int] = []
    for name, typ in entities:
        eid = _upsert_entity(cur, name, typ)
        entity_ids.append(eid)
        cur.execute(
            "INSERT INTO chunk_entities (vector_id, entity_id, weight) VALUES (?, ?, ?)",
            (vector_id, eid, 1.0),
        )
    if close_conn:
        cur.connection.commit()
        cur.connection.close()
    return entity_ids


def _add_relation(
    cur: sqlite3.Cursor,
    src_eid: int,
    rel_type: str,
    dst_eid: int,
    vector_id: Optional[int],
    confidence: float,
) -> None:
    cur.execute(
        "INSERT INTO relations (src_entity_id, rel_type, dst_entity_id, vector_id, confidence) VALUES (?, ?, ?, ?, ?)",
        (src_eid, rel_type, dst_eid, vector_id, confidence),
    )


# -------------------------
# AST graph extraction (.py)
# -------------------------


class _CallVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.calls: List[str] = []

    def visit_Call(self, node: ast.Call) -> Any:
        name = None
        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            parts: List[str] = []
            cur = node.func
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value  # type: ignore[assignment]
            if isinstance(cur, ast.Name):
                parts.append(cur.id)
                parts.reverse()
                name = ".".join(parts)
        if name:
            self.calls.append(name)
        self.generic_visit(node)


def _extract_py_entities_relations(
    path: str, source: str
) -> Tuple[List[Tuple[str, str]], List[Tuple[Tuple[str, str], str, Tuple[str, str]]]]:
    """Return (entities, relations[(src,rel,dst)]), using (name,type) tuples."""

    entities: List[Tuple[str, str]] = []
    relations: List[Tuple[Tuple[str, str], str, Tuple[str, str]]] = []

    module_name = Path(path).stem
    module_ent = (module_name, "module")
    entities.append(module_ent)

    try:
        tree = ast.parse(source)
    except Exception:
        return entities, relations

    # imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                dst = (alias.name, "module")
                entities.append(dst)
                relations.append((module_ent, "imports", dst))
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod:
                dst = (mod, "module")
                entities.append(dst)
                relations.append((module_ent, "imports", dst))

    # definitions
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            fn = (node.name, "function")
            entities.append(fn)
            relations.append((module_ent, "defines", fn))
            cv = _CallVisitor()
            cv.visit(node)
            for call in cv.calls[:200]:
                callee = (call, "callable")
                entities.append(callee)
                relations.append((fn, "calls", callee))
        elif isinstance(node, ast.ClassDef):
            cl = (node.name, "class")
            entities.append(cl)
            relations.append((module_ent, "defines", cl))
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef):
                    m = (f"{node.name}.{sub.name}", "method")
                    entities.append(m)
                    relations.append((cl, "defines", m))

    seen = set()
    ent_out: List[Tuple[str, str]] = []
    for e in entities:
        if e in seen:
            continue
        seen.add(e)
        ent_out.append(e)

    return ent_out, relations


# -------------------------
# Index builders
# -------------------------


def _sync_file_all_types(
    *,
    fpath: str,
    root_abs: str,
    db_path: str,
    chunk_size: int,
    overlap: int,
) -> List[str]:
    """Sync one file into vectors + graph."""

    warnings: List[str] = []
    fpath_abs = os.path.abspath(fpath)
    if not os.path.isfile(fpath_abs):
        return [f"not a file: {fpath}"]

    vec_tool._init_db(db_path)
    _init_graph_tables(db_path)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    mtime = os.path.getmtime(fpath_abs)
    size = os.path.getsize(fpath_abs)

    cur.execute("SELECT id, mtime FROM files WHERE path=?", (fpath_abs,))
    row = cur.fetchone()

    file_id: Optional[int] = None
    needs_update = False
    if row:
        file_id = int(row[0])
        if abs(mtime - float(row[1])) > 1.0:
            needs_update = True
    else:
        needs_update = True

    if needs_update:
        if file_id:
            cur.execute("DELETE FROM vectors WHERE file_id=?", (file_id,))
            cur.execute("DELETE FROM graph_files WHERE file_id=?", (file_id,))
            cur.execute(
                "UPDATE files SET mtime=?, file_size=? WHERE id=?",
                (mtime, size, file_id),
            )
        else:
            cur.execute(
                "INSERT INTO files (path, mtime, file_size) VALUES (?, ?, ?)",
                (fpath_abs, mtime, size),
            )
            file_id = int(cur.lastrowid)

        conn.commit()
        ext = Path(fpath_abs).suffix.lower()
        inserted_vector_ids: List[int] = []

        if ext in (".md", ".txt", ".py"):
            try:
                content = _read_text_file(fpath_abs)
            except Exception as e:
                warnings.append(f"text read failed: {e}")
                content = ""
            inserted_vector_ids = _ensure_vector_index_for_text(
                db_path=db_path,
                file_id=file_id,
                file_kind=ext.lstrip("."),
                text=content,
                chunk_size=chunk_size,
                overlap=overlap,
            )

            if ext == ".py" and content:
                ents, rels = _extract_py_entities_relations(fpath_abs, content)
                evidence_vector_id = (
                    inserted_vector_ids[0] if inserted_vector_ids else None
                )
                cur2 = conn.cursor()
                ent_ids: Dict[Tuple[str, str], int] = {}
                for name, typ in ents:
                    ent_ids[(name, typ)] = _upsert_entity(cur2, name, typ)
                for src, rtype, dst in rels:
                    src_id = ent_ids.get(src) or _upsert_entity(cur2, src[0], src[1])
                    dst_id = ent_ids.get(dst) or _upsert_entity(cur2, dst[0], dst[1])
                    _add_relation(cur2, src_id, rtype, dst_id, evidence_vector_id, 0.7)
                if evidence_vector_id is not None:
                    _link_chunk_entities(db_path, evidence_vector_id, ents, cur=cur2)
                conn.commit()

        elif ext in (".pdf", ".pptx"):
            text_all, pages, w = _extract_pdf_pptx_text(fpath_abs)
            warnings.extend(w)
            if pages:
                for page_index, ptext in pages:
                    inserted_vector_ids.extend(
                        _ensure_vector_index_for_text(
                            db_path=db_path,
                            file_id=file_id,
                            file_kind=ext.lstrip("."),
                            text=ptext,
                            page_index=page_index,
                            chunk_size=chunk_size,
                            overlap=overlap,
                        )
                    )
            elif text_all:
                inserted_vector_ids = _ensure_vector_index_for_text(
                    db_path=db_path,
                    file_id=file_id,
                    file_kind=ext.lstrip("."),
                    text=text_all,
                    chunk_size=chunk_size,
                    overlap=overlap,
                )

            for vid in inserted_vector_ids:
                cur.execute("SELECT text_content FROM vectors WHERE id=?", (vid,))
                r = cur.fetchone()
                if not r:
                    continue
                ents = _extract_entities_from_text(str(r[0]))
                _link_chunk_entities(db_path, vid, ents, cur=cur)

            conn2 = sqlite3.connect(db_path)
            c2 = conn2.cursor()
            for vid in inserted_vector_ids:
                c2.execute(
                    "SELECT e.id, e.name, e.type FROM chunk_entities ce JOIN entities e ON ce.entity_id=e.id WHERE ce.vector_id=?",
                    (vid,),
                )
                eids = [int(x[0]) for x in (c2.fetchall() or [])]
                for i in range(min(len(eids), 30)):
                    for j in range(i + 1, min(len(eids), 30)):
                        _add_relation(c2, eids[i], "related_to", eids[j], vid, 0.3)
                conn2.commit()
            conn2.close()

        elif ext == ".xlsx":
            text_all, sheets, w = _extract_xlsx_text(fpath_abs)
            warnings.extend(w)
            if sheets:
                for sname, stext in sheets:
                    inserted_vector_ids.extend(
                        _ensure_vector_index_for_text(
                            db_path=db_path,
                            file_id=file_id,
                            file_kind="xlsx",
                            text=stext,
                            sheet_name=sname,
                            chunk_size=chunk_size,
                            overlap=overlap,
                        )
                    )
            elif text_all:
                inserted_vector_ids = _ensure_vector_index_for_text(
                    db_path=db_path,
                    file_id=file_id,
                    file_kind="xlsx",
                    text=text_all,
                    chunk_size=chunk_size,
                    overlap=overlap,
                )

            for vid in inserted_vector_ids:
                cur.execute("SELECT text_content FROM vectors WHERE id=?", (vid,))
                r = cur.fetchone()
                if not r:
                    continue
                ents = _extract_entities_from_text(str(r[0]))
                _link_chunk_entities(db_path, vid, ents, cur=cur)

            conn2 = sqlite3.connect(db_path)
            c2 = conn2.cursor()
            for vid in inserted_vector_ids:
                c2.execute(
                    "SELECT e.id FROM chunk_entities ce JOIN entities e ON ce.entity_id=e.id WHERE ce.vector_id=?",
                    (vid,),
                )
                eids = [int(x[0]) for x in (c2.fetchall() or [])]
                for i in range(min(len(eids), 30)):
                    for j in range(i + 1, min(len(eids), 30)):
                        _add_relation(c2, eids[i], "related_to", eids[j], vid, 0.3)
                conn2.commit()
            conn2.close()

        else:
            warnings.append(f"unsupported extension: {ext}")

        cur.execute(
            "INSERT OR REPLACE INTO graph_files (file_id, graph_mtime, graph_version) VALUES (?, ?, ?)",
            (file_id, mtime, 1),
        )
        conn.commit()

    conn.close()
    return warnings


# -------------------------
# Retrieval (vector + graph)
# -------------------------


@dataclass
class _ChunkHit:
    source: str
    score: float
    file_id: int
    vector_id: int
    text: str


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    return vec_tool._cosine_similarity(vec_a, vec_b)


def _vector_retrieve(db_path: str, query: str, top_k: int) -> List[_ChunkHit]:
    qv = vec_tool._get_embedding(query)
    if not qv:
        return []

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id, file_id, text_content, embedding_json FROM vectors")
    rows = cur.fetchall()
    hits: List[_ChunkHit] = []
    for vid, fid, text, emb_json in rows:
        try:
            score = _cosine_similarity(qv, json.loads(emb_json))
        except Exception:
            continue
        hits.append(
            _ChunkHit(
                source="vector",
                score=float(score),
                file_id=int(fid),
                vector_id=int(vid),
                text=str(text),
            )
        )

    hits.sort(key=lambda x: x.score, reverse=True)
    conn.close()
    return hits[:top_k]


def _extract_query_entities(query: str) -> List[str]:
    ents: List[str] = []
    for m in _QUALNAME_RE.finditer(query or ""):
        ents.append(m.group(0))
    for m in _CAMEL_RE.finditer(query or ""):
        ents.append(m.group(0))
    for m in _WORD_RE.finditer(query or ""):
        ents.append(m.group(0))
    for m in _FILE_RE.finditer(query or ""):
        ents.append(m.group(0))
    out: List[str] = []
    seen = set()
    for e in ents:
        ne = _norm(e)
        if ne in seen:
            continue
        seen.add(ne)
        out.append(e)
    return out[:50]


def _graph_seed_entities(db_path: str, query: str) -> List[int]:
    tokens = _extract_query_entities(query)
    if not tokens:
        return []

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    seed_ids: List[int] = []
    for t in tokens:
        n = _norm(t)
        cur.execute("SELECT id FROM entities WHERE norm_name=? LIMIT 5", (n,))
        for (eid,) in cur.fetchall() or []:
            seed_ids.append(int(eid))
        cur.execute(
            "SELECT id FROM entities WHERE norm_name LIKE ? LIMIT 5", (f"%{n}%",)
        )
        for (eid,) in cur.fetchall() or []:
            seed_ids.append(int(eid))

    conn.close()
    out: List[int] = []
    seen = set()
    for x in seed_ids:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out[:50]


def _graph_bfs(
    db_path: str, seed_entity_ids: List[int], hops: int, max_nodes: int
) -> Tuple[List[int], List[Tuple[int, str, int]]]:
    """Return (visited_entity_ids, traversed_edges[(src,rel,dst)])."""

    if not seed_entity_ids:
        return [], []

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    visited = set(seed_entity_ids)
    frontier = list(seed_entity_ids)
    edges: List[Tuple[int, str, int]] = []

    for _ in range(max(0, hops)):
        if not frontier:
            break
        next_frontier: List[int] = []
        for src in frontier:
            cur.execute(
                "SELECT rel_type, dst_entity_id FROM relations WHERE src_entity_id=? LIMIT 200",
                (src,),
            )
            for rel_type, dst in cur.fetchall() or []:
                dst = int(dst)
                edges.append((src, str(rel_type), dst))
                if dst not in visited:
                    visited.add(dst)
                    next_frontier.append(dst)
                    if len(visited) >= max_nodes:
                        break
            if len(visited) >= max_nodes:
                break
        frontier = next_frontier
        if len(visited) >= max_nodes:
            break

    conn.close()
    return list(visited), edges


def _graph_retrieve(
    db_path: str, query: str, hops: int, top_k: int
) -> Tuple[List[_ChunkHit], Dict[str, Any]]:
    """Return (hits, trace)."""

    seeds = _graph_seed_entities(db_path, query)
    visited, edges = _graph_bfs(db_path, seeds, hops=hops, max_nodes=200)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    if not visited:
        conn.close()
        return [], {"seed_entity_ids": [], "visited_entity_ids": [], "edges": []}

    qmarks = ",".join(["?"] * len(visited))
    cur.execute(
        f"""
        SELECT DISTINCT ce.vector_id
        FROM chunk_entities ce
        WHERE ce.entity_id IN ({qmarks})
        LIMIT 2000
        """,
        tuple(visited),
    )
    vector_ids = [int(r[0]) for r in (cur.fetchall() or [])]

    hits: List[_ChunkHit] = []
    for vid in vector_ids:
        cur.execute("SELECT file_id, text_content FROM vectors WHERE id=?", (vid,))
        r = cur.fetchone()
        if not r:
            continue
        fid, text = int(r[0]), str(r[1])
        hits.append(
            _ChunkHit(source="graph", score=1.0, file_id=fid, vector_id=vid, text=text)
        )

    conn.close()

    uniq: Dict[int, _ChunkHit] = {}
    for h in hits:
        if h.vector_id not in uniq:
            uniq[h.vector_id] = h
    out = list(uniq.values())[:top_k]

    trace = {
        "seed_entity_ids": seeds,
        "visited_entity_ids": visited,
        "edges": edges[:200],
    }
    return out, trace


# -------------------------
# Public tool
# -------------------------


def graph_rag_search(
    query: str,
    root_path: str = ".",
    file_pattern: str = "*.md,*.txt,*.py,*.pdf,*.pptx,*.xlsx",
    top_k_vector: int = 5,
    top_k_graph: int = 5,
    hops: int = 2,
    chunk_size: int = 800,
    overlap: int = 150,
) -> str:
    root_abs = os.path.abspath(root_path)
    if not os.path.isdir(root_abs):
        return _(
            "err.dir_not_found", default="Error: Directory not found: {root_path}"
        ).format(root_path=root_path)

    db_path = vec_tool._get_db_path(root_abs)
    vec_tool._init_db(db_path)
    _init_graph_tables(db_path)

    patterns = [p.strip() for p in (file_pattern or "").split(",") if p.strip()]
    target_files: List[str] = []
    for p in patterns:
        search_path = os.path.join(root_abs, "**", p)
        try:
            target_files.extend(glob.glob(search_path, recursive=True))
        except Exception:
            target_files.extend(glob.glob(os.path.join(root_abs, p)))

    from uagent.utils.scan_filters import is_ignored_path

    target_files = [
        f
        for f in sorted(set(target_files))
        if os.path.isfile(f) and (not is_ignored_path(f))
    ]

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id, path FROM files")
    db_files = {str(p): int(fid) for fid, p in (cur.fetchall() or [])}
    removed = set(db_files.keys()) - set(os.path.abspath(f) for f in target_files)
    for p in removed:
        fid = db_files[p]
        cur.execute("DELETE FROM vectors WHERE file_id=?", (fid,))
        cur.execute("DELETE FROM files WHERE id=?", (fid,))
    conn.commit()
    conn.close()

    all_warnings: List[str] = []
    synced_count = 0
    for f in target_files:
        all_warnings.extend(
            _sync_file_all_types(
                fpath=f,
                root_abs=root_abs,
                db_path=db_path,
                chunk_size=chunk_size,
                overlap=overlap,
            )
        )
        synced_count += 1

    vec_hits = _vector_retrieve(db_path, query, top_k=top_k_vector)
    graph_hits, trace = _graph_retrieve(db_path, query, hops=hops, top_k=top_k_graph)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id, path FROM files")
    id_to_path = {int(r[0]): str(r[1]) for r in (cur.fetchall() or [])}
    conn.close()

    merged: List[_ChunkHit] = []
    seen_vid = set()
    for h in vec_hits + graph_hits:
        if h.vector_id in seen_vid:
            continue
        seen_vid.add(h.vector_id)
        merged.append(h)

    merged.sort(key=lambda x: (0 if x.source == "vector" else 1, -x.score))

    out: List[str] = []
    out.append(_("out.query", default="Search Query: {query}").format(query=query))
    out.append(
        _("out.target_dir", default="Target Directory: {root_path}").format(
            root_path=root_path
        )
    )
    out.append(_("out.db", default="DB: {db_path}").format(db_path=db_path))
    out.append(
        _(
            "out.hits_summary",
            default="vector_hits: {v} / graph_hits: {g} / merged: {m}",
        ).format(v=len(vec_hits), g=len(graph_hits), m=len(merged))
    )

    if all_warnings:
        uniq_w = []
        s = set()
        for w in all_warnings:
            if w in s:
                continue
            s.add(w)
            uniq_w.append(w)
        out.append(
            _(
                "warn.indexing_title",
                default="\n[WARN] Indexing warnings (de-duplicated, top 50):",
            )
        )
        for w in uniq_w[:50]:
            out.append(f"- {w}")

    out.append("\n[Graph trace] (ids only, summary)")
    out.append(json.dumps(trace, ensure_ascii=False, indent=2)[:4000])

    out.append(_("out.results_title", default="\n[Results]"))
    for rank, h in enumerate(merged, 1):
        fpath = id_to_path.get(h.file_id, "unknown")
        rel_path = os.path.relpath(fpath, root_abs) if fpath != "unknown" else "unknown"
        snippet = h.text.replace("\n", " ")[:240] + ("..." if len(h.text) > 240 else "")
        out.append(
            f"[{rank}] source={h.source} score={h.score:.4f} file={rel_path} (vector_id={h.vector_id})"
        )
        out.append(
            _("out.result_content", default="Content: {snippet}\n").format(
                snippet=snippet
            )
        )

    if not merged:
        out.append(_("out.no_docs", default="No relevant documents found."))

    return "\n".join(out)


def run_tool(args: Dict[str, Any]) -> str:
    query = args.get("query")
    if not query:
        return _("err.query_required", default="Error: query is required.")

    return graph_rag_search(
        query=str(query),
        root_path=str(args.get("root_path", ".")),
        file_pattern=str(
            args.get("file_pattern", "*.md,*.txt,*.py,*.pdf,*.pptx,*.xlsx")
        ),
        top_k_vector=int(args.get("top_k_vector", 5)),
        top_k_graph=int(args.get("top_k_graph", 5)),
        hops=int(args.get("hops", 2)),
        chunk_size=int(args.get("chunk_size", 800)),
        overlap=int(args.get("overlap", 150)),
    )


if getattr(vec_tool, "TOOL_SPEC", None) is None and getattr(vec_tool, "_DISABLE_IF_UNREACHABLE", False):
    # semantic_search_files_tool already decided to hide itself because embedding API is unreachable.
    # Keep graph_rag_search hidden as well, since it depends on embeddings.
    TOOL_SPEC = None  # type: ignore[assignment]
else:
    TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "graph_rag_search",
        "description": _(
            "tool.description",
            default=(
                "Search local files using GraphRAG (Graph + Vector hybrid). "
                "Supported: py/md/txt/pdf/pptx/xlsx. "
                "Builds a lightweight knowledge graph (entities/relations) in SQLite, "
                "retrieves relevant chunks via graph traversal (hops), and returns them along with vector search results."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": _(
                        "param.query.description", default="Search query (required)."
                    ),
                },
                "root_path": {
                    "type": "string",
                    "description": _(
                        "param.root_path.description",
                        default="Target directory for search.",
                    ),
                },
                "file_pattern": {
                    "type": "string",
                    "description": _(
                        "param.file_pattern.description",
                        default="Target pattern (comma-separated glob).",
                    ),
                },
                "top_k_vector": {
                    "type": "integer",
                    "description": _(
                        "param.top_k_vector.description",
                        default="Number of top results from vector search.",
                    ),
                },
                "top_k_graph": {
                    "type": "integer",
                    "description": _(
                        "param.top_k_graph.description",
                        default="Number of results to retrieve via graph traversal.",
                    ),
                },
                "hops": {
                    "type": "integer",
                    "description": _(
                        "param.hops.description",
                        default="Number of hops for graph traversal.",
                    ),
                },
                "chunk_size": {
                    "type": "integer",
                    "description": _(
                        "param.chunk_size.description", default="Chunk size."
                    ),
                },
                "overlap": {
                    "type": "integer",
                    "description": _(
                        "param.overlap.description", default="Chunk overlap."
                    ),
                },
            },
            "required": ["query"],
        },
    },
}
