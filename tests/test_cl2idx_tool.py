from __future__ import annotations

from pathlib import Path

from uagent.tools.cl2idx_tool import run_tool, _ClIndexBuilder


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def test_cl2idx_basic_pgm_structure(repo_tmp_path: Path) -> None:
    source = (
        "/* Batch sample */\n"
        "             PGM        PARM(&MODE)\n"
        "             DCL        VAR(&MODE) TYPE(*CHAR) LEN(1)\n"
        "             DCL        VAR(&RTN) TYPE(*CHAR) LEN(7)\n"
        "             DCLF       FILE(CUSTPF)\n"
        " INIT:       CHGVAR     VAR(&MODE) VALUE('A')\n"
        "             CALL       PGM(CUSTRPT) PARM(&MODE &RTN)\n"
        "             MONMSG     MSGID(CPF0000) EXEC(GOTO CMDLBL(DONE))\n"
        "             IF         COND(&MODE *EQ 'X') THEN(DO)\n"
        "             ENDDO\n"
        " DONE:       RETURN\n"
        "             ENDPGM\n"
    )
    path = repo_tmp_path / "BATCH01.CLLE"
    _write(path, source)

    out = run_tool({"path": str(path), "mode": "index"})

    assert "PGM" in out
    assert "DCL &MODE" in out
    assert "DCL &RTN" in out
    assert "DCLF FILE(CUSTPF)" in out
    assert "INIT:" in out
    assert "CALL PGM(CUSTRPT)" in out
    assert "MONMSG" in out
    assert "ENDPGM" in out

    sec = run_tool({"path": str(path), "mode": "section", "section": 1})
    assert "PGM" in sec
    assert "DCL" in sec


def test_cl2idx_comments_ignored(repo_tmp_path: Path) -> None:
    path = repo_tmp_path / "c.clp"
    _write(
        path,
        "/* PGM fake */\n"
        "             PGM\n"
        "             /* DCL VAR(&X) TYPE(*CHAR) LEN(1) */\n"
        "             DCL        VAR(&Y) TYPE(*DEC) LEN(5 0)\n"
        "             ENDPGM\n",
    )
    out = run_tool({"path": str(path), "mode": "index"})
    assert "DCL &Y" in out
    assert "DCL &X" not in out
    assert out.count("PGM") >= 1


def test_cl2idx_continuation_lines(repo_tmp_path: Path) -> None:
    src = (
        "             PGM\n"
        "             DCL        VAR(&LONG) TYPE(*CHAR) +\n"
        "                          LEN(100)\n"
        "             CALL       PGM(MYPGM) +\n"
        "                          PARM(&LONG)\n"
        "             ENDPGM\n"
    )
    path = repo_tmp_path / "cont.clle"
    _write(path, src)
    out = run_tool({"path": str(path), "mode": "index"})
    assert "DCL &LONG" in out
    assert "CALL PGM(MYPGM)" in out


def test_cl2idx_if_do_block_end_line() -> None:
    src = (
        "PGM\n"
        "IF COND(&A *EQ '1') THEN(DO)\n"
        "CHGVAR VAR(&B) VALUE('X')\n"
        "CALL PGM(INNER)\n"
        "ENDDO\n"
        "RETURN\n"
        "ENDPGM\n"
    )
    b = _ClIndexBuilder(src)
    flat = []
    for e in b.entries:
        flat.append(e)
        flat.extend(e.get("members", []))
    if_item = next(x for x in flat if x["label"].startswith("IF "))
    assert if_item["end_line"] >= 5
    idx = next(i for i, x in enumerate(flat, 1) if x["label"].startswith("IF "))
    body = b.get_section(idx)
    assert body is not None
    assert "IF " in body
    assert "ENDDO" in body
    assert "CALL PGM(INNER)" in body


def test_cl2idx_multiline_comment_span(repo_tmp_path: Path) -> None:
    src = (
        "PGM\n"
        "/* start comment\n"
        "   CALL PGM(HIDDEN)\n"
        "   end comment */\n"
        "CALL PGM(VISIBLE)\n"
        "ENDPGM\n"
    )
    path = repo_tmp_path / "mc.cl"
    _write(path, src)
    out = run_tool({"path": str(path), "mode": "index"})
    assert "VISIBLE" in out
    assert "HIDDEN" not in out


def test_cl2idx_invalid_section(repo_tmp_path: Path) -> None:
    path = repo_tmp_path / "small.cl"
    _write(path, "             PGM\n             ENDPGM\n")
    out = run_tool({"path": str(path), "mode": "section", "section": 99})
    assert "99" in out
    assert "not found" in out.lower() or "有効範囲" in out


def test_cl2idx_rejects_path_outside_workdir(tmp_path: Path) -> None:
    path = tmp_path / "outside.cl"
    _write(path, "PGM\nENDPGM\n")
    out = run_tool({"path": str(path), "mode": "index"})
    assert "not found" in out.lower() or "outside" in out.lower()
