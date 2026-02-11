# tools/exstruct_tool.py
"""exstruct_tool

Excel構造抽出ライブラリ exstruct を使って、Excelファイル(.xlsx)から
構造化データ(JSON/YAML)を生成するツール。

方針:
- 既存の excel_ops_tool.py (pandas) とは分離し、用途で使い分ける。
- exstruct が未インストールの場合は、その旨を分かりやすく返す。
- COM依存の auto page-break 抽出は Windows + Excel 環境に依存するため、
  オプションで有効化し、失敗時はエラーを返す（黙って無視しない）。

バックアップ方針（追加仕様）:
- action=export_file で output_path に保存する際、output_path が既に存在する場合は
  保存直前に同名のバックアップ（<output_path>.org / <output_path>.org1 / ...）を作成する。
- sheets_dir / print_areas_dir / auto_page_breaks_dir 等で生成される個別ファイルについては
  このツールではバックアップ対象外（output_path のみ）。

戻り値:
- action=extract: WorkbookData を Python側で export して JSON 文字列として返す。
- action=export_file: ファイルへエクスポートして成功メッセージを返す。

注意:
- このツールは巨大なExcelをJSON化すると出力が大きくなる可能性がある。

互換性メモ:
- exstruct の一部バージョンでは `FormatOptions` が `exstruct.__init__` から
  re-export されておらず、`from exstruct import FormatOptions` が失敗します。
  その場合は `from exstruct.engine import FormatOptions` にフォールバックします。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "exstruct",
        "description": "exstruct を使って Excel(.xlsx) を構造化抽出し、JSON/YAMLで返す/保存します。export_file の output_path が既存の場合、保存直前にバックアップ（<output_path>.org / <output_path>.org1 / <output_path>.org2 ...）を作成します。",
        "system_prompt": """このツールは次の目的で使われます: exstruct を使って Excel(.xlsx) を構造化抽出し、JSON/YAMLで返す/保存します。export_file の output_path が既存の場合、保存直前にバックアップ（<output_path>.org / <output_path>.org1 / <output_path>.org2 ...）を作成します。""",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["extract", "export_file"],
                    "description": "実行する操作。extract=抽出して文字列で返す / export_file=ファイルへ保存",
                },
                "file_path": {
                    "type": "string",
                    "description": "入力Excelファイルのパス（絶対パス推奨）。",
                },
                "mode": {
                    "type": "string",
                    "enum": ["light", "standard", "verbose"],
                    "description": "抽出モード。省略時 standard。",
                },
                "include_shapes": {
                    "type": "boolean",
                    "description": "図形(Shapes)を出力に含めるか。省略時 false。",
                },
                "include_cell_links": {
                    "type": "boolean",
                    "description": "セルのハイパーリンクを含めるか。省略時は mode に従う。",
                },
                "pretty": {
                    "type": "boolean",
                    "description": "整形出力（pretty print）。省略時 false。",
                },
                "format": {
                    "type": "string",
                    "enum": ["json", "yaml"],
                    "description": "戻り/保存フォーマット。省略時 json。",
                },
                "output_path": {
                    "type": "string",
                    "description": "action=export_file の出力先パス。拡張子で自動判定も可能だが format が優先。",
                },
                "sheets_dir": {
                    "type": "string",
                    "description": "シート別ファイルも保存する場合のディレクトリ。",
                },
                "print_areas_dir": {
                    "type": "string",
                    "description": "印刷範囲ごとに保存する場合のディレクトリ。",
                },
                "auto_page_breaks_dir": {
                    "type": "string",
                    "description": "自動改ページ領域を保存するディレクトリ（COMのみ）。",
                },
                "table_score_threshold": {
                    "type": "number",
                    "description": "表検出の閾値。未指定なら exstruct デフォルト。",
                },
                "density_min": {
                    "type": "number",
                    "description": "表検出の密度閾値。未指定なら exstruct デフォルト。",
                },
            },
            "required": ["action", "file_path"],
        },
    },
}


def _safe_bool(v: Any, default: bool) -> bool:
    if v is None:
        return default
    return bool(v)


def _import_exstruct():
    """exstruct の import をまとめて行い、バージョン差分を吸収する。

    Returns:
        tuple: (DestinationOptions, ExStructEngine, FilterOptions, FormatOptions, OutputOptions,
                StructOptions, export_print_areas_as, set_table_detection_params)

    Raises:
        Exception: import に失敗した場合
    """

    from exstruct import (  # type: ignore
        DestinationOptions,
        ExStructEngine,
        FilterOptions,
        OutputOptions,
        StructOptions,
        export_print_areas_as,
        set_table_detection_params,
    )

    # FormatOptions は exstruct.__init__ から import できないバージョンがあるためフォールバック
    try:
        from exstruct import FormatOptions  # type: ignore
    except Exception:
        from exstruct.engine import FormatOptions  # type: ignore

    return (
        DestinationOptions,
        ExStructEngine,
        FilterOptions,
        FormatOptions,
        OutputOptions,
        StructOptions,
        export_print_areas_as,
        set_table_detection_params,
    )


def _next_backup_name(filename: str) -> str:
    base = filename + ".org"
    if not os.path.exists(base):
        return base

    i = 1
    while True:
        cand = f"{base}{i}"
        if not os.path.exists(cand):
            return cand
        i += 1


def _make_backup_if_needed(output_path: str) -> str | None:
    """Create a backup for an existing output file.

    - Only when output_path already exists.
    - Backup name: <output_path>.org / .org1 / ...
    - Copy bytes as-is.

    Returns backup path if created, otherwise None.
    """
    if not os.path.exists(output_path):
        return None

    backup_path = _next_backup_name(output_path)
    Path(backup_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "rb") as rf, open(backup_path, "wb") as wf:
        wf.write(rf.read())
    return backup_path


def run_tool(args: Dict[str, Any]) -> str:
    action = (args.get("action") or "").strip()
    file_path = (args.get("file_path") or "").strip()

    if not file_path:
        return "[exstruct error] file_path is required."

    in_path = Path(file_path)
    if not in_path.exists():
        return f"[exstruct error] File not found: {in_path}"

    # Lazy import: exstruct is optional dependency
    try:
        (
            DestinationOptions,
            ExStructEngine,
            FilterOptions,
            FormatOptions,
            OutputOptions,
            StructOptions,
            export_print_areas_as,
            set_table_detection_params,
        ) = _import_exstruct()
    except Exception as e:
        return (
            "[exstruct error] exstruct が利用できません（未インストール、または import 失敗）。\n"
            f"details: {e}"
        )

    mode = (args.get("mode") or "standard").strip()
    out_format = (args.get("format") or "json").strip()
    pretty = _safe_bool(args.get("pretty"), False)

    include_shapes = _safe_bool(args.get("include_shapes"), False)
    include_cell_links: Optional[bool] = args.get("include_cell_links")

    table_score_threshold = args.get("table_score_threshold")
    density_min = args.get("density_min")

    # Optional: tune table detection
    try:
        kw = {}
        if table_score_threshold is not None:
            kw["table_score_threshold"] = float(table_score_threshold)
        if density_min is not None:
            kw["density_min"] = float(density_min)
        if kw:
            set_table_detection_params(**kw)
    except Exception as e:
        return f"[exstruct error] Failed to set table detection params: {e}"

    # Engine config
    if include_cell_links is not None:
        struct_opts = StructOptions(
            mode=mode, include_cell_links=bool(include_cell_links)
        )
    else:
        struct_opts = StructOptions(mode=mode)

    destinations = DestinationOptions(
        sheets_dir=Path(args["sheets_dir"]) if args.get("sheets_dir") else None,
        auto_page_breaks_dir=(
            Path(args["auto_page_breaks_dir"])
            if args.get("auto_page_breaks_dir")
            else None
        ),
    )

    output_opts = OutputOptions(
        format=FormatOptions(pretty=pretty),
        filters=FilterOptions(include_shapes=include_shapes),
        destinations=destinations,
    )

    engine = ExStructEngine(options=struct_opts, output=output_opts)

    try:
        wb = engine.extract(str(in_path))
    except Exception as e:
        return f"[exstruct error] extract failed: {e}"

    # Optional: export print areas as separate files
    # Note: this uses the workbook model, and requires print areas exist.
    if args.get("print_areas_dir"):
        try:
            export_print_areas_as(
                wb,
                args["print_areas_dir"],
                fmt="json" if out_format == "json" else "yaml",
                pretty=pretty,
            )
        except Exception as e:
            return f"[exstruct error] export_print_areas_as failed: {e}"

    if action == "extract":
        try:
            if out_format == "yaml":
                # Some exstruct models provide to_yaml
                if hasattr(wb, "to_yaml"):
                    return wb.to_yaml()  # type: ignore[attr-defined]
                return "[exstruct error] YAML output requested but WorkbookData.to_yaml() is not available."

            # JSON: prefer model's serializer if available
            if hasattr(wb, "to_json"):
                return wb.to_json(pretty=pretty)  # type: ignore[attr-defined]

            # fallback: save to temp file and read back
            if hasattr(wb, "save"):
                import tempfile

                with tempfile.TemporaryDirectory() as td:
                    p = Path(td) / "out.json"
                    wb.save(str(p), pretty=pretty)  # type: ignore[attr-defined]
                    return p.read_text(encoding="utf-8")

            return "[exstruct error] WorkbookData serialization method not found (to_json/save)."

        except Exception as e:
            return f"[exstruct error] serialize failed: {e}"

    if action == "export_file":
        output_path = (args.get("output_path") or "").strip()
        if not output_path:
            return "[exstruct error] output_path is required for export_file action."
        out_path = Path(output_path)

        backup_path = None
        try:
            backup_path = _make_backup_if_needed(str(out_path))
        except Exception as e:
            return f"[exstruct error] バックアップ作成に失敗しました: {type(e).__name__}: {e}"

        try:
            # Prefer engine.export to keep destination outputs consistent
            engine.export(wb, out_path)
        except Exception as e:
            return f"[exstruct error] export failed: {e}"

        msg = f"[exstruct] Successfully exported to {out_path}"
        if backup_path:
            msg += f" / バックアップ作成: {backup_path}"
        return msg

    return f"[exstruct error] Unknown action: {action}"
