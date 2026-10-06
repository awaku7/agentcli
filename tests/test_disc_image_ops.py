from __future__ import annotations

import ast
import json
from io import BytesIO
from pathlib import Path

import pycdlib

from uagent.tools import disc_image_ops_tool as disc


def _rel(path: Path) -> str:
    return path.relative_to(Path.cwd()).as_posix()


def _make_iso(path: Path) -> None:
    iso = pycdlib.PyCdlib()
    iso.new(vol_ident="UAGTEST")
    payload = b"hello from iso\n"
    iso.add_fp(BytesIO(payload), len(payload), iso_path="/HELLO.TXT;1")
    iso.write(str(path))
    iso.close()


def test_iso_info_list_verify_extract(repo_tmp_path: Path) -> None:
    iso_path = repo_tmp_path / "sample.iso"
    _make_iso(iso_path)
    iso_rel = _rel(iso_path)

    info = json.loads(disc.run_tool({"action": "info", "path": iso_rel}))
    assert info["ok"] is True
    assert info["format"] == "iso"
    assert info["backend"] == "pycdlib"
    assert info["volume_id"] == "UAGTEST"
    assert info["file_count"] == 1

    listed = json.loads(disc.run_tool({"action": "list", "path": iso_rel}))
    assert listed["ok"] is True
    assert any(item["path"] == "/HELLO.TXT;1" for item in listed["entries"])

    verified = json.loads(
        disc.run_tool({"action": "verify", "path": iso_rel, "deep": True})
    )
    assert verified["ok"] is True
    assert verified["bytes_read"] == len(b"hello from iso\n")

    out_dir = repo_tmp_path / "out"
    extracted = json.loads(
        disc.run_tool({"action": "extract", "path": iso_rel, "output": _rel(out_dir)})
    )
    assert extracted["ok"] is True
    assert extracted["extracted_count"] == 1
    assert (out_dir / "HELLO.TXT;1").read_bytes() == b"hello from iso\n"


def test_runtime_dependency_install_contract(monkeypatch) -> None:
    calls: list[tuple[str, str | None, str | None]] = []

    def fake_install(
        package_name: str,
        module_name: str | None = None,
        **kwargs: object,
    ) -> bool:
        calls.append((package_name, module_name, str(kwargs.get("version_spec"))))
        return True

    monkeypatch.setattr(disc, "install_with_status", fake_install)

    assert disc._ensure_pycdlib() is True
    assert disc._ensure_xverter() is True
    assert calls == [
        ("pycdlib", "pycdlib", ">=1.21.0"),
        ("xverter", "xverter", ">=1.5.0"),
    ]


def test_chd_info_uses_xverter_backend(repo_tmp_path: Path, monkeypatch) -> None:
    chd_path = repo_tmp_path / "sample.chd"
    chd_path.write_bytes(b"MComprHD" + b"\0" * 128)
    seen: list[tuple[list[str], int]] = []

    def fake_run(argv: list[str], timeout_seconds: int) -> dict[str, object]:
        seen.append((argv, timeout_seconds))
        return {
            "ok": True,
            "backend": "xverter",
            "returncode": 0,
            "stdout": "CHD v5",
            "stderr": "",
        }

    monkeypatch.setattr(disc, "_run_xverter", fake_run)

    result = json.loads(
        disc.run_tool(
            {
                "action": "info",
                "path": _rel(chd_path),
                "timeout_seconds": 123,
            }
        )
    )

    assert result["ok"] is True
    assert result["format"] == "chd"
    assert result["backend"] == "xverter"
    assert seen == [(["info", str(chd_path.resolve())], 123)]


def test_iso_to_chd_convert_uses_xverter(repo_tmp_path: Path, monkeypatch) -> None:
    iso_path = repo_tmp_path / "sample.iso"
    _make_iso(iso_path)
    out_path = repo_tmp_path / "sample.chd"
    seen: list[list[str]] = []

    def fake_run(argv: list[str], timeout_seconds: int) -> dict[str, object]:
        seen.append(argv)
        Path(argv[-1]).write_bytes(b"converted")
        return {
            "ok": True,
            "backend": "xverter",
            "returncode": 0,
            "stdout": "converted",
            "stderr": "",
        }

    monkeypatch.setattr(disc, "_run_xverter", fake_run)

    result = json.loads(
        disc.run_tool(
            {
                "action": "convert",
                "path": _rel(iso_path),
                "output": _rel(out_path),
            }
        )
    )

    assert result["ok"] is True
    assert result["output"] == str(out_path.resolve())
    assert out_path.read_bytes() == b"converted"
    assert len(seen) == 1
    assert seen[0][:3] == ["convert", str(iso_path.resolve()), "-o"]
    assert Path(seen[0][3]).suffix == ".chd"
    assert Path(seen[0][3]) != out_path


def test_chd_convert_rejects_source_output_alias(
    repo_tmp_path: Path, monkeypatch
) -> None:
    chd_path = repo_tmp_path / "same.chd"
    original = b"MComprHD" + b"source-data"
    chd_path.write_bytes(original)

    called = False

    def fake_run(argv: list[str], timeout_seconds: int) -> dict[str, object]:
        nonlocal called
        called = True
        return {"ok": True, "backend": "xverter", "returncode": 0}

    monkeypatch.setattr(disc, "_run_xverter", fake_run)
    monkeypatch.setattr(disc, "_confirm_overwrite", lambda message: True)

    result = json.loads(
        disc.run_tool(
            {
                "action": "convert",
                "path": _rel(chd_path),
                "output": _rel(chd_path),
                "overwrite": True,
            }
        )
    )

    assert result["ok"] is False
    assert result["error_type"] == "ValueError"
    assert called is False
    assert chd_path.read_bytes() == original


def test_chd_convert_failure_preserves_existing_destination(
    repo_tmp_path: Path, monkeypatch
) -> None:
    chd_path = repo_tmp_path / "source.chd"
    chd_path.write_bytes(b"MComprHD" + b"source-data")
    out_path = repo_tmp_path / "existing.iso"
    out_path.write_bytes(b"keep-me")

    seen_output: list[Path] = []

    def fake_run(argv: list[str], timeout_seconds: int) -> dict[str, object]:
        temp_path = Path(argv[-1])
        seen_output.append(temp_path)
        temp_path.write_bytes(b"partial-output")
        return {
            "ok": False,
            "backend": "xverter",
            "returncode": 1,
            "stdout": "",
            "stderr": "conversion failed",
        }

    monkeypatch.setattr(disc, "_run_xverter", fake_run)
    monkeypatch.setattr(disc, "_confirm_overwrite", lambda message: True)

    result = json.loads(
        disc.run_tool(
            {
                "action": "convert",
                "path": _rel(chd_path),
                "output": _rel(out_path),
                "overwrite": True,
            }
        )
    )

    assert result["ok"] is False
    assert out_path.read_bytes() == b"keep-me"
    assert len(seen_output) == 1
    assert seen_output[0] != out_path
    assert not seen_output[0].exists()


def test_chd_convert_success_replaces_existing_destination_atomically(
    repo_tmp_path: Path, monkeypatch
) -> None:
    chd_path = repo_tmp_path / "source.chd"
    chd_path.write_bytes(b"MComprHD" + b"source-data")
    out_path = repo_tmp_path / "existing.iso"
    out_path.write_bytes(b"old-output")

    seen_output: list[Path] = []

    def fake_run(argv: list[str], timeout_seconds: int) -> dict[str, object]:
        temp_path = Path(argv[-1])
        seen_output.append(temp_path)
        temp_path.write_bytes(b"new-output")
        return {
            "ok": True,
            "backend": "xverter",
            "returncode": 0,
            "stdout": "converted",
            "stderr": "",
        }

    monkeypatch.setattr(disc, "_run_xverter", fake_run)
    monkeypatch.setattr(disc, "_confirm_overwrite", lambda message: True)

    result = json.loads(
        disc.run_tool(
            {
                "action": "convert",
                "path": _rel(chd_path),
                "output": _rel(out_path),
                "overwrite": True,
            }
        )
    )

    assert result["ok"] is True
    assert out_path.read_bytes() == b"new-output"
    assert len(seen_output) == 1
    assert seen_output[0] != out_path
    assert not seen_output[0].exists()


def test_i18n_catalog_has_all_non_english_locales_and_matching_keys() -> None:
    root = Path(__file__).parents[1]
    catalog_path = root / "src/uagent/tools/disc_image_ops_tool.json"
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    shipped = {
        "ar",
        "bn",
        "cs",
        "da",
        "de",
        "el",
        "es",
        "fa",
        "fi",
        "fil",
        "fr",
        "he",
        "hi",
        "hu",
        "id",
        "it",
        "ja",
        "ko",
        "mn",
        "mr",
        "ms",
        "nb",
        "nl",
        "nn",
        "pl",
        "pt",
        "pt_BR",
        "ro",
        "ru",
        "sv",
        "sw",
        "th",
        "tr",
        "uk",
        "vi",
        "zh_CN",
        "zh_TW",
    }
    assert set(data) == shipped

    source_path = root / "src/uagent/tools/disc_image_ops_tool.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    english_keys = {
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    }
    assert english_keys

    for lang in shipped:
        assert set(data[lang]) == english_keys
        assert "%(path)s" in data[lang]["confirm.file_overwrite"]
        assert "%(seconds)s" in data[lang]["err.timeout"]
