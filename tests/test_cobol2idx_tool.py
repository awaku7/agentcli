from __future__ import annotations

from pathlib import Path

from uagent.tools.cobol2idx_tool import run_tool


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def test_cobol2idx_fixed_format_detects_divisions_and_paragraph(
    repo_tmp_path: Path,
) -> None:
    source = (
        "000100 IDENTIFICATION DIVISION.\n"
        "000200 PROGRAM-ID. DEMO-PROGRAM.\n"
        "000300 DATA DIVISION.\n"
        "000400 WORKING-STORAGE SECTION.\n"
        "000500 01  WS-NAME PIC X(10).\n"
        "000600 PROCEDURE DIVISION.\n"
        "000700 MAIN-PARA.\n"
        "000800     DISPLAY WS-NAME.\n"
    )
    path = repo_tmp_path / "fixed.cbl"
    _write(path, source)

    out = run_tool({"path": str(path), "mode": "index"})

    assert "IDENTIFICATION DIVISION" in out
    assert "PROGRAM-ID DEMO-PROGRAM" in out
    assert "WORKING-STORAGE SECTION" in out
    assert "MAIN-PARA." in out
    assert "DEMO-PROGRAM" in run_tool(
        {"path": str(path), "mode": "section", "section": 2}
    )


def test_cobol2idx_free_format_ignores_end_program(
    repo_tmp_path: Path,
) -> None:
    path = repo_tmp_path / "free.cbl"
    _write(
        path,
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. FREE-DEMO.\n"
        "       DATA DIVISION.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           DISPLAY 'HELLO'.\n"
        "       END-PROGRAM.\n",
    )

    out = run_tool({"path": str(path), "mode": "index"})

    assert "PROGRAM-ID FREE-DEMO" in out
    assert "MAIN-PARA." in out
    assert "END-PROGRAM." not in out


def test_cobol2idx_detects_user_defined_section(
    repo_tmp_path: Path,
) -> None:
    path = repo_tmp_path / "custom.cbl"
    _write(
        path,
        "IDENTIFICATION DIVISION.\n"
        "PROGRAM-ID. CUSTOM-DEMO.\n"
        "PROCEDURE DIVISION.\n"
        "CUSTOM-SECTION SECTION.\n"
        "CUSTOM-PARA.\n"
        "    CONTINUE.\n",
    )

    out = run_tool({"path": str(path), "mode": "index"})

    assert "CUSTOM-SECTION" in out
    assert "CUSTOM-PARA." in out


def test_cobol2idx_invalid_section_returns_error_json(
    repo_tmp_path: Path,
) -> None:
    path = repo_tmp_path / "small.cbl"
    _write(path, "IDENTIFICATION DIVISION.\n")

    out = run_tool({"path": str(path), "mode": "section", "section": 999})

    assert "999" in out
    assert "有効範囲" in out or "not found" in out.lower()


def test_cobol2idx_rejects_path_outside_workdir(tmp_path: Path) -> None:
    path = tmp_path / "outside.cbl"
    _write(path, "IDENTIFICATION DIVISION.\n")

    out = run_tool({"path": str(path), "mode": "index"})
    assert "not found" in out.lower() or "outside" in out.lower()


def test_cobol2idx_fixed_format_continuation_and_comments(
    repo_tmp_path: Path,
) -> None:
    path = repo_tmp_path / "continuation.cbl"
    _write(
        path,
        "000100 IDENTIFICATION DIVISION.\n"
        "000200 PROGRAM-ID. CONT-DEMO.\n"
        "000300 ENVIRONMENT DIVISION.\n"
        "000400 INPUT-OUTPUT SECTION.\n"
        "000500 FILE-CONTROL. *> inline comment\n"
        "000600     SELECT INPUT-FILE ASSIGN TO \"input.dat\"\n"
        "000700         ORGANIZATION IS LINE SEQUENTIAL.\n"
        "000800 DATA DIVISION.\n"
        "000900 FILE SECTION.\n"
        "001000 FD INPUT-FILE.\n"
        "001100 01 INPUT-RECORD PIC X(80).\n"
        "001200 PROCEDURE DIVISION.\n"
        "001300 MAIN-PARA.\n"
        "001400     DISPLAY \"PERFORM.\".\n"
        "001500     COPY COMMON-CPY.\n",
    )

    out = run_tool({"path": str(path), "mode": "index"})

    assert "CONT-DEMO" in out
    assert "INPUT-OUTPUT SECTION" in out
    assert "INPUT-FILE" in out
    assert "MAIN-PARA." in out
    assert "COPY COMMON-CPY" in out
    assert 'PERFORM.' not in out


def test_cobol2idx_declaratives_and_multiple_sections(
    repo_tmp_path: Path,
) -> None:
    path = repo_tmp_path / "sections.cbl"
    _write(
        path,
        "IDENTIFICATION DIVISION.\n"
        "PROGRAM-ID. SECTION-DEMO.\n"
        "PROCEDURE DIVISION.\n"
        "DECLARATIVES.\n"
        "ERROR-HANDLER SECTION.\n"
        "ERROR-PARA.\n"
        "    CONTINUE.\n"
        "END-DECLARATIVES.\n"
        "MAIN-SECTION SECTION.\n"
        "MAIN-PARA.\n"
        "    GOBACK.\n",
    )

    out = run_tool({"path": str(path), "mode": "index"})

    assert "DECLARATIVES" in out
    assert "ERROR-HANDLER" in out
    assert "ERROR-PARA." in out
    assert "MAIN-SECTION" in out
    assert "MAIN-PARA." in out
