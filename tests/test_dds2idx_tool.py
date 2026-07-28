from __future__ import annotations

from pathlib import Path

from uagent.tools.dds2idx_tool import run_tool


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def test_dds2idx_pf_free_format(repo_tmp_path: Path) -> None:
    source = (
        "     A                                      UNIQUE\n"
        "     A          R CUSTREC\n"
        "     A            CUSTID        10A\n"
        "     A            CUSTNAME      30A\n"
        "     A            BALANCE        9P 2\n"
        "     A          K CUSTID\n"
    )
    path = repo_tmp_path / "CUSTPF.PF"
    _write(path, source)

    out = run_tool({"path": str(path), "mode": "index"})

    assert "UNIQUE" in out
    assert "R CUSTREC" in out
    assert "CUSTID" in out
    assert "CUSTNAME" in out
    assert "BALANCE" in out
    assert "K CUSTID" in out
    assert "(PF)" in out

    sec = run_tool({"path": str(path), "mode": "section", "section": 2})
    assert "CUSTREC" in sec
    assert "CUSTID" in sec


def test_dds2idx_lf_select_omit(repo_tmp_path: Path) -> None:
    source = (
        "     A          R CUSTREC                   PFILE(CUSTPF)\n"
        "     A          K CUSTNAME\n"
        "     A          K CUSTID\n"
        "     A          S STATUS\n"
        "     A            STATUS                    COMP(EQ 'A')\n"
    )
    path = repo_tmp_path / "CUSTL1.LF"
    _write(path, source)

    out = run_tool({"path": str(path), "mode": "index"})
    assert "R CUSTREC" in out
    assert "PFILE(CUSTPF)" in out
    assert "K CUSTNAME" in out
    assert "S STATUS" in out
    assert "(LF)" in out


def test_dds2idx_dspf_constants_and_sflctl(repo_tmp_path: Path) -> None:
    source = (
        "     A                                      INDARA\n"
        "     A          R HEADER\n"
        "     A                                  1  2'Customer'\n"
        "     A            CUSTID        10A  B  3  2\n"
        "     A          R SFLCTL                   SFLCTL(SFL1)\n"
        "     A                                      SFLSIZ(0010)\n"
        "     A          R SFL1                     SFL\n"
        "     A            LINE          40A  O  5  2\n"
    )
    path = repo_tmp_path / "CUSTD.DSPF"
    _write(path, source)
    out = run_tool({"path": str(path), "mode": "index"})
    assert "(DSPF)" in out
    assert "R HEADER" in out
    assert "const" in out or "Customer" in out
    assert "CUSTID" in out
    assert "SFLCTL" in out
    assert "R SFL1" in out or "SFL1" in out


def test_dds2idx_field_keyword_attach(repo_tmp_path: Path) -> None:
    source = (
        "     A          R REC1\n"
        "     A            FLD1          10A\n"
        "     A                                      TEXT('Hello')\n"
        "     A                                      COLHDG('H1')\n"
    )
    path = repo_tmp_path / "t.pf"
    _write(path, source)
    out = run_tool({"path": str(path), "mode": "index"})
    assert "FLD1" in out
    # keywords attached to field label rather than separate noisy entries
    assert "TEXT" in out or "COLHDG" in out


def test_dds2idx_comments_ignored(repo_tmp_path: Path) -> None:
    path = repo_tmp_path / "x.dds"
    _write(
        path,
        "     A* This is a comment with R FAKE\n"
        "     A          R REALREC\n"
        "     A            FLD1          5A\n",
    )
    out = run_tool({"path": str(path), "mode": "index"})
    assert "R REALREC" in out
    assert "FAKE" not in out


def test_dds2idx_invalid_section(repo_tmp_path: Path) -> None:
    path = repo_tmp_path / "small.pf"
    _write(path, "     A          R R1\n")
    out = run_tool({"path": str(path), "mode": "section", "section": 50})
    assert "50" in out
    assert "not found" in out.lower() or "有効範囲" in out


def test_dds2idx_ref_follow_same_dir(repo_tmp_path: Path) -> None:
    """REF(file) resolves in same workdir and annotates R / REFFLD fields."""
    _write(
        repo_tmp_path / "CUSTPF.PF",
        (
            "     A                                      UNIQUE\n"
            "     A          R CUSTREC\n"
            "     A            CUSTID        10A\n"
            "     A            CUSTNAME      30A\n"
            "     A            BALANCE        9P 2\n"
            "     A          K CUSTID\n"
        ),
    )
    path = repo_tmp_path / "ORDER.PF"
    _write(
        path,
        (
            "     A                                      REF(CUSTPF)\n"
            "     A          R ORDREC\n"
            "     A            ORDNO          7A\n"
            "     A            CUSTID         R\n"
            "     A            CUSTNAME       R               REFFLD(CUSTNAME)\n"
            "     A            XNAME          R               REFFLD(CUSTNAME CUSTPF)\n"
            "     A          K ORDNO\n"
        ),
    )

    out = run_tool({"path": str(path), "mode": "index"})

    assert "REF(CUSTPF) ->" in out
    assert "CUSTPF.PF" in out
    assert "CUSTID R 10A" in out
    assert "<= CUSTPF.CUSTID" in out
    assert "CUSTNAME R 30A" in out
    assert "XNAME R 30A" in out
    assert "<= CUSTPF.CUSTNAME" in out
    assert "REF follow:" in out
    assert "not found" not in out.lower()


def test_dds2idx_ref_follow_not_found(repo_tmp_path: Path) -> None:
    path = repo_tmp_path / "ORPHAN.PF"
    _write(
        path,
        (
            "     A                                      REF(NOFILE)\n"
            "     A          R R1\n"
            "     A            F1             R\n"
        ),
    )
    out = run_tool({"path": str(path), "mode": "index"})
    assert "REF(NOFILE) [not found]" in out
    assert "F1 R" in out
    assert "ref?" in out.lower() or "NOFILE" in out


def test_dds2idx_ref_lib_qualified_name(repo_tmp_path: Path) -> None:
    """REF(LIB/FILE) strips library and resolves FILE in workdir."""
    _write(
        repo_tmp_path / "ITEM.PF",
        (
            "     A          R ITEMREC\n"
            "     A            ITEMID         5A\n"
            "     A            ITEMDESC      40A\n"
        ),
    )
    path = repo_tmp_path / "LINE.PF"
    _write(
        path,
        (
            "     A                                      REF(MYLIB/ITEM)\n"
            "     A          R LINEREC\n"
            "     A            ITEMID         R\n"
        ),
    )
    out = run_tool({"path": str(path), "mode": "index"})
    assert "REF(MYLIB/ITEM) ->" in out
    assert "ITEMID R 5A" in out
    assert "<= ITEM.ITEMID" in out


def test_dds2idx_dspf_dspatr_and_indicators(repo_tmp_path: Path) -> None:
    """DSPATR args, conditioning indicators, and CF keys are fully decoded."""
    source = (
        "     A                                      INDARA\n"
        "     A                                      CF03(03)\n"
        "     A                                      CF12(12 'Cancel')\n"
        "     A          R DETAIL                    OVERLAY\n"
        "     A            CUSTID        10A  B  3  2\n"
        "     A  01                                  DSPATR(HI UL)\n"
        "     A  N02                                 DSPATR(ND)\n"
        "     A                                      COLOR(RED)\n"
        "     A            STATUS         1A  O  4  2DSPATR(RI)\n"
        "     A  50                                  DSPATR(PC)\n"
        "     A                                  5  2'Name'\n"
        "     A  41N42\n"
    )
    path = repo_tmp_path / "ATTR.DSPF"
    _write(path, source)
    out = run_tool({"path": str(path), "mode": "index"})

    assert "(DSPF)" in out
    assert "INDARA" in out
    # CF keys keep response indicator / text
    assert "CF03(03)" in out
    assert "CF12(12" in out
    # DSPATR fully expanded (not bare name only)
    assert "DSPATR(HI UL)" in out
    assert "DSPATR(ND)" in out
    assert "DSPATR(RI)" in out or "DSPATR(PC)" in out
    # COLOR decoded
    assert "COLOR(RED)" in out
    # conditioning indicators visible
    assert "[01]" in out or "01" in out
    assert "N02" in out
    # indicator-only line retained
    assert "41" in out and "42" in out
    # packed constant line (no space before quote): 5  2'Name' -> layout, not field A
    assert "5,2 const 'Name'" in out
    assert "field A" not in out.lower()
    assert not any(
        line.strip().endswith(" A") or " A " in line
        for line in out.splitlines()
        if "const" in line.lower()
    )


def test_dds2idx_dspf_inline_dspatr_on_field(repo_tmp_path: Path) -> None:
    source = (
        "     A          R R1\n"
        "     A            FLD1          10A  B  2  2DSPATR(HI ND)\n"
        "     A            FLD2           5A  O  3  2\n"
        "     A                                      DSPATR(PR)\n"
    )
    path = repo_tmp_path / "inline.dspf"
    _write(path, source)
    out = run_tool({"path": str(path), "mode": "index"})
    assert "DSPATR(HI ND)" in out
    assert "FLD2" in out
    assert "DSPATR(PR)" in out
