from __future__ import annotations

from pathlib import Path

from uagent.tools.rpg2idx_tool import run_tool, _RpgIndexBuilder


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def test_rpg2idx_free_form_proc_and_ds(repo_tmp_path: Path) -> None:
    src = """**free
ctl-opt dftactgrp(*no) actgrp(*caller);

dcl-f CUSTPF disk usage(*input);

dcl-ds custDs qualified;
  custId char(10);
  name   char(30);
end-ds;

dcl-proc getCust export;
  dcl-pi *n ind;
    id char(10) const;
  end-pi;

  dcl-s ok ind inz(*off);

  begsr validate;
    // check
  endsr;

  return ok;
end-proc;

/copy QRPGLESRC,COMMON
"""
    path = repo_tmp_path / "GETCUST.RPGLE"
    _write(path, src)
    out = run_tool({"path": str(path), "mode": "index"})
    assert "**free" in out
    assert "ctl-opt" in out
    assert "dcl-f CUSTPF" in out
    assert "dcl-ds custDs" in out
    assert "dcl-proc getCust" in out
    assert "export" in out
    assert "begsr validate" in out
    assert "/copy" in out
    assert "COMMON" in out

    b = _RpgIndexBuilder(src)
    flat = b._flatten()
    idx = next(i for i, x in enumerate(flat, 1) if "getCust" in x["label"])
    body = b.get_section(idx)
    assert body is not None
    assert "dcl-proc getCust" in body
    assert "end-proc" in body
    assert "begsr validate" in body


def test_rpg2idx_fixed_format_f_and_begsr(repo_tmp_path: Path) -> None:
    src = (
        "     FCUSTPF    IF   E           K DISK\n"
        "     D myVar           S             10A\n"
        "     C     main          BEGSR\n"
        "     C                   ENDSR\n"
    )
    path = repo_tmp_path / "OLD.RPG"
    _write(path, src)
    out = run_tool({"path": str(path), "mode": "index"})
    assert "CUSTPF" in out
    assert "main" in out


def test_rpg2idx_comments_ignored(repo_tmp_path: Path) -> None:
    src = "**free\n" "// dcl-proc hidden\n" "dcl-proc visible;\n" "end-proc;\n"
    path = repo_tmp_path / "c.rpgle"
    _write(path, src)
    out = run_tool({"path": str(path), "mode": "index"})
    assert "visible" in out
    assert "hidden" not in out


def test_rpg2idx_invalid_section(repo_tmp_path: Path) -> None:
    path = repo_tmp_path / "s.rpgle"
    _write(path, "**free\ndcl-s x ind;\n")
    out = run_tool({"path": str(path), "mode": "section", "section": 99})
    assert "99" in out


def test_rpg2idx_rejects_path_outside_workdir(tmp_path: Path) -> None:
    path = tmp_path / "outside.rpgle"
    _write(path, "**free\n")
    out = run_tool({"path": str(path), "mode": "index"})
    assert (
        "not found" in out.lower()
        or "見つかりません" in out
        or "Error" in out
        or "エラー" in out
    )


def test_rpg2idx_embedded_sql_free_and_directive(repo_tmp_path: Path) -> None:
    src = """**free
ctl-opt datfmt(*iso);

dcl-s custId char(10);

exec sql
  select cust_id into :custId
  from custpf
  where active = '1';

/exec sql
  update custpf set name = :name
  where cust_id = :custId
/end-exec

dcl-proc runSql;
  exec sql commit;
end-proc;
"""
    path = repo_tmp_path / "SQLCUST.SQLRPGLE"
    _write(path, src)
    out = run_tool({"path": str(path), "mode": "index"})
    assert "EXEC SQL" in out
    assert "SELECT" in out.upper()
    assert "UPDATE" in out.upper() or "update" in out.lower()
    assert "COMMIT" in out.upper() or "commit" in out.lower()

    b = _RpgIndexBuilder(src)
    flat = b._flatten()
    sql_entries = [x for x in flat if x["kind"] == "sql"]
    assert len(sql_entries) >= 3
    # multi-line select should span more than one line
    sel = next(x for x in sql_entries if "SELECT" in x["label"].upper())
    assert sel["end_line"] > sel["line"]


def test_rpg2idx_conditional_compile(repo_tmp_path: Path) -> None:
    src = """**free
/IF DEFINED(DEBUG)
  dcl-s dbg ind inz(*on);
/ELSEIF DEFINED(TRACE)
  dcl-s dbg ind inz(*off);
/ELSE
  dcl-s dbg ind inz(*off);
/ENDIF
/DEFINE PROD
/UNDEFINE DEBUG
dcl-proc main;
end-proc;
"""
    path = repo_tmp_path / "cond.rpgle"
    _write(path, src)
    out = run_tool({"path": str(path), "mode": "index"})
    assert "/if" in out.lower()
    assert "/elseif" in out.lower()
    assert "/else" in out.lower()
    assert "/endif" in out.lower()
    assert "/define" in out.lower()
    assert "/undefine" in out.lower()
    assert "dcl-proc main" in out


def test_rpg2idx_fixed_d_spec_kinds_and_calc(repo_tmp_path: Path) -> None:
    # Fixed-form with classic column layout (form type at col 6)
    src = (
        "     H DEBUG(*YES)\n"
        "     FCUSTPF    IF   E           K DISK\n"
        "     D myDs            DS\n"
        "     D  field1                       10A\n"
        "     D myVar           S             10A\n"
        "     D myConst         C                   CONST('X')\n"
        "     C     main          BEGSR\n"
        "     C                   EVAL      x = 1\n"
        "     C                   CALL      'OTHERPGM'\n"
        "     C                   ENDSR\n"
    )
    path = repo_tmp_path / "FIXED2.RPGLE"
    _write(path, src)
    out = run_tool({"path": str(path), "mode": "index"})
    assert "CUSTPF" in out
    assert "main" in out
    # D-spec structured kinds or labels
    assert "myDs" in out or "DS" in out
    assert "myVar" in out
    # calc opcodes indexed
    assert "EVAL" in out or "CALL" in out


def test_rpg2idx_ebcdic_cp037_source(repo_tmp_path: Path) -> None:
    # Minimal free-form RPG encoded as EBCDIC cp037
    ascii_src = "**free\ndcl-proc ebcdicProc;\nend-proc;\n"
    data = ascii_src.encode("cp037")
    path = repo_tmp_path / "EBCDIC.RPGLE"
    path.write_bytes(data)
    out = run_tool({"path": str(path), "mode": "index"})
    assert "ebcdicProc" in out or "dcl-proc" in out
