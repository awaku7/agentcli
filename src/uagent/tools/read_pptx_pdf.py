# tools/read_pptx_pdf.py
# -*- coding: utf-8 -*-

# ==============================
# Python 3.11+ 互換レイヤー
# （古いライブラリが collections.Sequence 等を使っていても落ちないようにする）
# ==============================

# --- imports at top ---
import collections
import collections.abc
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import logging

import unicodedata
from collections import Counter

# 外部ライブラリは無い可能性もあるので、ImportError は握りつぶして後でチェック
try:
    import pdfplumber
except ImportError:
    pdfplumber = None  # type: ignore[assignment]

try:
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE
except ImportError:
    Presentation = None  # type: ignore[assignment]
    MSO_SHAPE_TYPE = None  # type: ignore[assignment]

# 互換レイヤー: collections と collections.abc の互換性補完
for name in ("Mapping", "MutableMapping", "Sequence"):
    if not hasattr(collections, name) and hasattr(collections.abc, name):
        setattr(collections, name, getattr(collections.abc, name))

# PDF 関連のログは抑制
logging.getLogger("pdfminer").setLevel(logging.ERROR)  # PDFのWARNINGを抑制

# ツール実行中は Busy 表示にしたいので ON
BUSY_LABEL = True
STATUS_LABEL = "tool:read_pptx_pdf"

# 返す文字列の最大長
DEFAULT_MAX_CHARS = 8000

JSON_SCHEMA_VERSION = "1.1"


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "read_pptx_pdf",
        "description": (
            "PDF / PPTX / その共通JSONスキーマを読み込み、ページ単位のテキストを返します。"
            "path に .pdf / .pptx / .json を指定できます。"
            "PDF/PPTX の場合は、このファイル内の抽出ロジックで共通JSONスキーマに変換します。"
        ),
        "system_prompt": (
            "【重要】PDF/PPTX/JSON を読み込み、ページ単位のテキストを返すツールです。\n"
            "入力: path, page_index, max_chars\n"
            "出力: ページテキスト（全ページ or 指定ページ）\n\n"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "PDF / PPTX / JSON ファイルのパス",
                },
                "page_index": {
                    "type": "integer",
                    "description": (
                        "1始まりのページ番号（PDFのページ or PPTXのスライド番号）。"
                        "省略時は全ページを連結して返します。"
                    ),
                },
                "max_chars": {
                    "type": "integer",
                    "description": (
                        "返却テキストの最大文字数。省略時は 8000 文字で切り詰めます。"
                    ),
                },
            },
            "required": ["path"],
        },
    },
}


# ==============================
# ユーティリティ（文字列・フォント・スタイル）
# ==============================


def normalize_text(s: str) -> str:
    """
    PDF / PPTX から取得したテキストを正規化する。
    - BOM やゼロ幅スペースなどの不可視文字を除去
    - Unicode 正規化（NFKC）を実施
    """
    if not s:
        return ""
    # よく紛れ込む不可視文字を削除
    for ch in ("\ufeff", "\u200b", "\u200c", "\u200d"):
        s = s.replace(ch, "")
    # 全角/半角のゆれなどを整理
    s = unicodedata.normalize("NFKC", s)
    return s


def infer_style_from_fontnames(
    fontnames: List[Optional[str]],
) -> Optional[Dict[str, Optional[bool]]]:
    """
    フォント名のリストから太字/斜体をざっくり推定する。
    - "Bold", "Black", "Heavy" などを含めば bold
    - "Italic", "Oblique", "It" などを含めば italic
    """
    names = [fn.lower() for fn in fontnames if fn]
    if not names:
        return None

    bold_hits = [
        n for n in names if any(k in n for k in ("bold", "black", "heavy", "demi"))
    ]
    italic_hits = [
        n for n in names if any(k in n for k in ("italic", "oblique", "ita", "kursiv"))
    ]

    style: Dict[str, Optional[bool]] = {
        "bold": bool(bold_hits),
        "italic": bool(italic_hits),
    }
    return style


def summarize_font_from_words(
    words: List[Dict[str, Any]],
) -> Optional[Dict[str, Optional[Any]]]:
    """
    pdfplumber の word dict 群から代表的なフォント名・サイズを決める。
    """
    if not words:
        return None

    name_counter: Counter = Counter()
    size_counter: Counter = Counter()

    for w in words:
        fn = w.get("fontname")
        if fn:
            name_counter[fn] += 1
        sz = w.get("size")
        if sz:
            try:
                size_counter[round(float(sz), 1)] += 1
            except Exception:
                pass

    font_name: Optional[str] = None
    font_size: Optional[float] = None

    if name_counter:
        font_name = name_counter.most_common(1)[0][0]
    if size_counter:
        font_size = size_counter.most_common(1)[0][0]

    if font_name is None and font_size is None:
        return None

    return {"name": font_name, "size": font_size}


def estimate_pdf_alignment(
    left: float, right: float, page_width: float
) -> Optional[str]:
    """
    段落の bbox とページ幅から、ざっくりと left / center / right を推定。
    """
    if page_width <= 0:
        return None

    center_x = (left + right) / 2.0
    page_center = page_width / 2.0

    if abs(center_x - page_center) <= page_width * 0.05:
        return "center"

    margin_left = left
    margin_right = page_width - right

    # 右揃えらしさを少し強めに判定
    if margin_right < margin_left * 0.5:
        return "right"

    return "left"


# ==============================
# PDF → blocks（段落推定付き）
# ==============================


def build_pdf_blocks(
    words_raw: List[Dict[str, Any]], page_width: float
) -> List[Dict[str, Any]]:
    """
    pdfplumber.extract_words() の結果から段落ブロックを構築する。
    - 行間と x 座標から段落を推定
    - 段落ごとに行間情報（平均行高・行間）を推定
    - 段落ごとに揃え (left/center/right) を推定
    - 段落ごとにフォント・太字/斜体を推定
    """

    # まずテキスト正規化＆不要な word を削る
    norm_words: List[Dict[str, Any]] = []
    for w in words_raw:
        t = normalize_text(w.get("text", ""))
        if not t:
            continue
        w2 = dict(w)
        w2["text"] = t
        norm_words.append(w2)

    if not norm_words:
        return []

    # 一応 top, x0 でソート（pdfplumber はだいたいそうなっているが念のため）
    norm_words.sort(key=lambda w: (w.get("top", 0.0), w.get("x0", 0.0)))

    heights = [
        (float(w["bottom"]) - float(w["top"]))
        for w in norm_words
        if "bottom" in w and "top" in w
    ]
    avg_height = sum(heights) / len(heights) if heights else 10.0

    # しきい値（経験的）
    line_gap_threshold = avg_height * 0.7
    paragraph_gap_threshold = avg_height * 1.8
    indent_threshold = avg_height * 0.8

    blocks: List[Dict[str, Any]] = []

    current_words: List[Dict[str, Any]] = []
    current_lines: List[Dict[str, float]] = []  # {"top":..., "bottom":...}
    current_line_top: Optional[float] = None
    current_line_bottom: Optional[float] = None
    current_indent_x0: Optional[float] = None

    def finalize_block() -> None:
        nonlocal current_words, current_lines, current_line_top, current_line_bottom, current_indent_x0

        if not current_words:
            return

        # 最終行を追加
        lines = list(current_lines)
        if current_line_top is not None and current_line_bottom is not None:
            lines.append({"top": current_line_top, "bottom": current_line_bottom})

        # bbox
        xs0 = [float(w["x0"]) for w in current_words]
        xs1 = [float(w["x1"]) for w in current_words]
        ys0 = [float(w["top"]) for w in current_words]
        ys1 = [float(w["bottom"]) for w in current_words]

        left = min(xs0)
        right = max(xs1)
        top = min(ys0)
        bottom = max(ys1)

        # 段落テキスト
        text = " ".join(w["text"] for w in current_words)

        # 行間情報
        line_spacing: Optional[Dict[str, float]] = None
        if len(lines) >= 2:
            heights_local = [ln["bottom"] - ln["top"] for ln in lines]
            gaps = [
                lines[i + 1]["top"] - lines[i]["bottom"] for i in range(len(lines) - 1)
            ]
            avg_h = sum(heights_local) / len(heights_local) if heights_local else 0.0
            avg_gap = sum(gaps) / len(gaps) if gaps else 0.0
            line_spacing = {
                "avg_line_height": float(avg_h),
                "avg_line_gap": float(avg_gap),
            }

        # 段落フォント／スタイル
        font = summarize_font_from_words(current_words)
        style = infer_style_from_fontnames([w.get("fontname") for w in current_words])

        # 揃え推定
        align = estimate_pdf_alignment(left, right, page_width)

        # 箇条書きっぽいか（先頭文字で簡易判定）
        stripped = text.lstrip()
        bullet: Optional[bool] = None
        if stripped:
            bullet = stripped[0] in ("-", "・", "●", "○", "■", "□", "◆", "•", "※")

        paragraph = {
            "text": text,
            "font": font,
            "style": style,
            "align": align,
            "line_spacing": line_spacing,
            "bullet": bullet,
            "runs": [],  # PDF では run 単位情報までは取っていない
        }

        block = {
            "text": text,
            "bbox": [float(left), float(top), float(right), float(bottom)],
            "font": font,
            "style": style,
            "paragraphs": [paragraph],
        }
        blocks.append(block)

        # リセット
        current_words = []
        current_lines = []
        current_line_top = None
        current_line_bottom = None
        current_indent_x0 = None

    # メインループ
    for w in norm_words:
        x0 = float(w["x0"])
        top = float(w["top"])
        bottom = float(w["bottom"])

        if not current_words:
            # 新しい段落開始
            current_words = [w]
            current_line_top = top
            current_line_bottom = bottom
            current_indent_x0 = x0
            current_lines = []
            continue

        # 直前行との関係
        assert current_line_bottom is not None
        vertical_gap = top - current_line_bottom
        same_indent = (
            current_indent_x0 is not None
            and abs(x0 - current_indent_x0) <= indent_threshold
        )

        new_paragraph = False
        # 行間が明らかに広い → 段落区切り
        if vertical_gap > paragraph_gap_threshold:
            new_paragraph = True
        # インデントが変わり、かつ少し間が空く → 段落の可能性
        elif (not same_indent) and vertical_gap > line_gap_threshold:
            new_paragraph = True

        if new_paragraph:
            finalize_block()
            # 新しい段落スタート
            current_words = [w]
            current_line_top = top
            current_line_bottom = bottom
            current_indent_x0 = x0
            current_lines = []
            continue

        # 同一段落内
        # 行をまたいだかどうか
        if vertical_gap > line_gap_threshold:
            # これまでの行を記録
            if current_line_top is not None and current_line_bottom is not None:
                current_lines.append(
                    {"top": current_line_top, "bottom": current_line_bottom}
                )
            # 新しい行
            current_line_top = top
            current_line_bottom = bottom
        else:
            # 同じ行（行の bbox を拡張）
            if current_line_top is not None:
                current_line_top = min(current_line_top, top)
            else:
                current_line_top = top
            if current_line_bottom is not None:
                current_line_bottom = max(current_line_bottom, bottom)
            else:
                current_line_bottom = bottom

        current_words.append(w)

    # 最後の段落
    finalize_block()

    return blocks


# ==============================
# PDF → 共通JSON
# ==============================


def pdf_to_pages_json(pdf_path: str) -> Dict[str, Any]:
    if pdfplumber is None:
        raise RuntimeError(
            "pdfplumber がインストールされていません。pip install pdfplumber を実行してください。"
        )

    pdf_file = Path(pdf_path)

    result: Dict[str, Any] = {
        "schema_version": JSON_SCHEMA_VERSION,
        "file": pdf_file.name,
        "type": "pdf",
        "meta": {},
        "masters": [],  # PDFにはマスター概念がないので空リスト
        "layouts": [],
        "pages": [],
    }

    with pdfplumber.open(pdf_file) as pdf:  # type: ignore[call-arg]
        page_count = len(pdf.pages)
        result["meta"]["page_count"] = page_count

        if page_count > 0:
            result["meta"]["width"] = float(pdf.pages[0].width)
            result["meta"]["height"] = float(pdf.pages[0].height)

        for idx, page in enumerate(pdf.pages):
            index = idx + 1

            # word 単位情報（フォント付き）
            words = page.extract_words(
                keep_blank_chars=False,
                use_text_flow=True,
                extra_attrs=["fontname", "size"],
            )

            blocks = build_pdf_blocks(words, page_width=float(page.width))

            if blocks:
                text = "\n\n".join(b["text"] for b in blocks)
            else:
                # fallback
                text = normalize_text(page.extract_text() or "")

            # テーブル（bbox推定付き）
            tables_json: List[Dict[str, Any]] = []
            try:
                tables = page.find_tables()
                if tables:
                    for t in tables:
                        cells = t.extract()
                        # セル文字列も正規化
                        cells_norm = [
                            [normalize_text(c or "") for c in row] if row else []
                            for row in cells
                        ]
                        bbox = t.bbox  # (x0, top, x1, bottom)
                        tables_json.append(
                            {
                                "bbox": [float(b) for b in bbox] if bbox else None,
                                "cells": cells_norm,
                                # PDF では cell フォント情報は未対応（pdfplumber 単体では bbox が取れないため）
                                "cell_fonts": None,
                                "cell_styles": None,
                            }
                        )
                else:
                    # fallback: extract_tables() だけ（bboxは取れない）
                    raw_tables = page.extract_tables()
                    for tbl in raw_tables:
                        cells_norm = [
                            [normalize_text(c or "") for c in row] if row else []
                            for row in tbl
                        ]
                        tables_json.append(
                            {
                                "bbox": None,
                                "cells": cells_norm,
                                "cell_fonts": None,
                                "cell_styles": None,
                            }
                        )
            except Exception as e:
                tables_json.append({"error": str(e)})

            # 画像のbboxだけ
            images_json: List[Dict[str, Any]] = []
            try:
                for img in page.images:
                    images_json.append(
                        {
                            "bbox": [
                                float(img["x0"]),
                                float(img["top"]),
                                float(img["x1"]),
                                float(img["bottom"]),
                            ],
                            "name": img.get("name"),
                            "width": float(img["width"]),
                            "height": float(img["height"]),
                        }
                    )
            except Exception as e:
                images_json.append({"error": str(e)})

            page_info = {
                "index": index,
                "label": str(index),
                "width": float(page.width),
                "height": float(page.height),
                "text": text,
                "blocks": blocks,
                "tables": tables_json,
                "images": images_json,
                "source": {
                    "page_number": index,
                },
            }

            result["pages"].append(page_info)

    return result


# ==============================
# PPTX 側のヘルパ
# ==============================


def _extract_paragraphs_from_shape(shape) -> List[Dict[str, Any]]:
    """
    PPTX のテキスト付き shape から段落＋run 情報を抽出する。
    """
    if not getattr(shape, "has_text_frame", False):
        return []

    paragraphs_json: List[Dict[str, Any]] = []

    try:
        text_frame = shape.text_frame
    except Exception:
        return []

    for p in text_frame.paragraphs:
        # 段落テキスト＆ run 情報
        runs_json: List[Dict[str, Any]] = []
        run_fontnames: List[str] = []
        run_sizes: List[float] = []

        for run in p.runs:
            t = normalize_text(run.text or "")
            if not t:
                continue

            f = run.font
            run_font: Optional[Dict[str, Any]] = {}
            if f is not None:
                if f.name:
                    run_font["name"] = f.name
                    run_fontnames.append(f.name)
                if f.size:
                    try:
                        run_font["size"] = float(f.size.pt)
                        run_sizes.append(float(f.size.pt))
                    except Exception:
                        pass
            if not run_font:
                run_font = None

            run_style: Optional[Dict[str, Any]] = {}
            if f is not None:
                if f.bold is not None:
                    run_style["bold"] = bool(f.bold)
                if f.italic is not None:
                    run_style["italic"] = bool(f.italic)
            if not run_style:
                run_style = None

            runs_json.append(
                {
                    "text": t,
                    "font": run_font,
                    "style": run_style,
                }
            )

        para_text = normalize_text("".join(r["text"] for r in runs_json))
        if not para_text:
            continue

        # 段落代表フォント
        font_name = None
        font_size = None
        if run_fontnames:
            font_name = Counter(run_fontnames).most_common(1)[0][0]
        if run_sizes:
            font_size = Counter(run_sizes).most_common(1)[0][0]
        para_font = None
        if font_name is not None or font_size is not None:
            para_font = {"name": font_name, "size": font_size}

        para_style = infer_style_from_fontnames(run_fontnames)

        # 揃え
        align = None
        try:
            if p.alignment is not None:
                # e.g. PP_ALIGN.LEFT → "left"
                align = str(p.alignment).split(".")[-1].lower()
        except Exception:
            pass

        # 行間情報（line_spacing / space_before / space_after）
        line_spacing_info: Dict[str, float] = {}
        try:
            if p.line_spacing is not None:
                if hasattr(p.line_spacing, "pt"):
                    line_spacing_info["line_spacing_pt"] = float(p.line_spacing.pt)
                else:
                    line_spacing_info["line_spacing"] = float(p.line_spacing)
        except Exception:
            pass
        try:
            if p.space_before is not None and hasattr(p.space_before, "pt"):
                line_spacing_info["space_before_pt"] = float(p.space_before.pt)
        except Exception:
            pass
        try:
            if p.space_after is not None and hasattr(p.space_after, "pt"):
                line_spacing_info["space_after_pt"] = float(p.space_after.pt)
        except Exception:
            pass
        if not line_spacing_info:
            line_spacing: Optional[Dict[str, float]] = None
        else:
            line_spacing = line_spacing_info

        # 箇条書きっぽいか（テキストの先頭文字で判定）
        bullet: Optional[bool] = None
        stripped = para_text.lstrip()
        if stripped:
            bullet = stripped[0] in ("-", "・", "●", "○", "■", "□", "◆", "•", "※")

        paragraphs_json.append(
            {
                "text": para_text,
                "font": para_font,
                "style": para_style,
                "align": align,
                "line_spacing": line_spacing,
                "bullet": bullet,
                "runs": runs_json,
            }
        )

    return paragraphs_json


def _summarize_cell_font(
    cell,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    PPTX の table cell から代表フォント＆スタイル（太字/斜体）を抽出。
    """
    try:
        tf = cell.text_frame
    except Exception:
        return None, None

    if tf is None:
        return None, None

    fontnames: List[str] = []
    sizes: List[float] = []

    for p in tf.paragraphs:
        for run in p.runs:
            f = run.font
            if f is None:
                continue
            if f.name:
                fontnames.append(f.name)
            if f.size:
                try:
                    sizes.append(float(f.size.pt))
                except Exception:
                    pass

    if not fontnames and not sizes:
        return None, None

    font_name = Counter(fontnames).most_common(1)[0][0] if fontnames else None
    font_size = Counter(sizes).most_common(1)[0][0] if sizes else None

    font = {"name": font_name, "size": font_size}
    style = infer_style_from_fontnames(fontnames)

    return font, style


# ==============================
# PPTX → 共通JSON
# ==============================


def pptx_to_pages_json(pptx_path: str) -> Dict[str, Any]:
    if Presentation is None:
        raise RuntimeError(
            "python-pptx がインストールされていません。pip install python-pptx を実行してください。"
        )

    prs = Presentation(pptx_path)
    pptx_file = Path(pptx_path)

    result: Dict[str, Any] = {
        "schema_version": JSON_SCHEMA_VERSION,
        "file": pptx_file.name,
        "type": "pptx",
        "meta": {
            "slide_count": len(prs.slides),
            "width": int(prs.slide_width),
            "height": int(prs.slide_height),
        },
        "masters": [],
        "layouts": [],
        "pages": [],
    }

    # --- Master 情報 ---
    for m in prs.slide_masters:
        master_texts: List[str] = []
        for shape in m.shapes:
            if hasattr(shape, "text"):
                t = normalize_text(shape.text or "")
                if t:
                    master_texts.append(t)

        result["masters"].append(
            {
                "name": m.name,
                "slide_layout_count": len(m.slide_layouts),
                "text": master_texts,
            }
        )

    # --- Layout 情報 ---
    for layout in prs.slide_layouts:
        layout_texts: List[str] = []
        for shape in layout.shapes:
            if hasattr(shape, "text"):
                t = normalize_text(shape.text or "")
                if t:
                    layout_texts.append(t)

        result["layouts"].append(
            {
                "name": layout.name,
                "text": layout_texts,
            }
        )

    # --- Slides → pages ---
    for idx, slide in enumerate(prs.slides):
        index = idx + 1

        blocks: List[Dict[str, Any]] = []
        tables_json: List[Dict[str, Any]] = []
        images_json: List[Dict[str, Any]] = []

        for shape in slide.shapes:
            # テキストブロック
            if getattr(shape, "has_text_frame", False):
                paragraphs = _extract_paragraphs_from_shape(shape)
                if paragraphs:
                    block_text = "\n".join(p["text"] for p in paragraphs)
                    # 代表フォント・スタイルは 1 段落目から
                    block_font = paragraphs[0].get("font")
                    block_style = paragraphs[0].get("style")

                    blocks.append(
                        {
                            "text": block_text,
                            "bbox": [
                                int(shape.left),
                                int(shape.top),
                                int(shape.left + shape.width),
                                int(shape.top + shape.height),
                            ],
                            "font": block_font,
                            "style": block_style,
                            "paragraphs": paragraphs,
                        }
                    )

            # テーブル
            if getattr(shape, "has_table", False):
                cells_text: List[List[str]] = []
                cell_fonts: List[List[Optional[Dict[str, Any]]]] = []
                cell_styles: List[List[Optional[Dict[str, Any]]]] = []

                for row in shape.table.rows:
                    row_texts: List[str] = []
                    row_fonts: List[Optional[Dict[str, Any]]] = []
                    row_styles: List[Optional[Dict[str, Any]]] = []
                    for cell in row.cells:
                        cell_text = normalize_text(cell.text or "")
                        row_texts.append(cell_text)

                        font, style = _summarize_cell_font(cell)
                        row_fonts.append(font)
                        row_styles.append(style)

                    cells_text.append(row_texts)
                    cell_fonts.append(row_fonts)
                    cell_styles.append(row_styles)

                tables_json.append(
                    {
                        "bbox": [
                            int(shape.left),
                            int(shape.top),
                            int(shape.left + shape.width),
                            int(shape.top + shape.height),
                        ],
                        "cells": cells_text,
                        "cell_fonts": cell_fonts,
                        "cell_styles": cell_styles,
                    }
                )

            # 画像
            if (
                MSO_SHAPE_TYPE is not None
                and shape.shape_type == MSO_SHAPE_TYPE.PICTURE
            ):
                images_json.append(
                    {
                        "bbox": [
                            int(shape.left),
                            int(shape.top),
                            int(shape.left + shape.width),
                            int(shape.top + shape.height),
                        ],
                        "name": getattr(shape, "name", None),
                        "width": int(shape.width),
                        "height": int(shape.height),
                    }
                )

        # スライド全体のテキストは blocks の text を結合
        full_text = "\n".join(b["text"] for b in blocks)

        page_info = {
            "index": index,
            "label": str(index),
            "width": int(prs.slide_width),
            "height": int(prs.slide_height),
            "text": full_text,
            "blocks": blocks,
            "tables": tables_json,
            "images": images_json,
            "source": {
                "slide_number": index,
                "layout": slide.slide_layout.name,
            },
        }

        result["pages"].append(page_info)

    return result


# ==============================
# 統一エントリポイント（ツール内部用）
# ==============================


def _document_to_json(path: str) -> Dict[str, Any]:
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        return pdf_to_pages_json(path)
    elif suffix == ".pptx":
        return pptx_to_pages_json(path)
    elif suffix == ".json":
        return _load_json(path)
    else:
        raise ValueError("Unsupported file type: expected .pdf, .pptx, or .json")


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ==============================
# JSON → テキスト抽出
# ==============================


def _extract_page_text(page: Dict[str, Any]) -> str:
    """
    1ページ分のテキストを共通スキーマから抽出する。
    - page["text"] があればそれを優先
    - なければ blocks[].text を連結
    """
    text = (page.get("text") or "").strip()
    if text:
        return text

    blocks: List[Dict[str, Any]] = page.get("blocks") or []
    parts: List[str] = []
    for blk in blocks:
        t = (blk.get("text") or "").strip()
        if t:
            parts.append(t)
    return "\n".join(parts)


def _build_all_pages_text(data: Dict[str, Any]) -> str:
    """
    全ページ分のテキストを:
      [Page 1]
      ...
      [Page 2]
      ...
    のように連結した文字列にする。
    """
    pages: List[Dict[str, Any]] = data.get("pages") or []
    if not pages:
        return "[read_pptx_pdf] JSON に pages がありません。"

    parts: List[str] = []
    for page in pages:
        idx: Optional[int] = page.get("index")
        label: Optional[str] = page.get("label")
        header = f"[Page {idx if idx is not None else label}]"
        body = _extract_page_text(page)
        if not body:
            continue
        parts.append(header)
        parts.append(body)

    if not parts:
        return "[read_pptx_pdf] 抽出できるテキストがありません。"

    return "\n".join(parts)


def _build_single_page_text(data: Dict[str, Any], page_index: int) -> str:
    """
    指定ページ（1始まり / index or label）だけを文字列にする。
    """
    pages: List[Dict[str, Any]] = data.get("pages") or []
    if not pages:
        return "[read_pptx_pdf] JSON に pages がありません。"

    target: Optional[Dict[str, Any]] = None
    for page in pages:
        idx = page.get("index")
        label = page.get("label")
        if idx == page_index or str(label) == str(page_index):
            target = page
            break

    if target is None:
        return f"[read_pptx_pdf] 指定ページが見つかりません: {page_index}"

    header = f"[Page {page_index}]"
    body = _extract_page_text(target)
    if not body:
        return header + "\n(テキストが見つかりませんでした)"
    return header + "\n" + body


# ==============================
# ツールエントリポイント
# ==============================


def run_tool(args: Dict[str, Any]) -> str:
    """
    tools/__init__.py から呼ばれるエントリポイント。
    args には LLM から渡された JSON 引数が入る。
    """
    path = args.get("path")
    if not path:
        return "[read_pptx_pdf] 'path' 引数が指定されていません。"

    max_chars = args.get("max_chars") or DEFAULT_MAX_CHARS
    try:
        max_chars_int = int(max_chars)
    except Exception:
        max_chars_int = DEFAULT_MAX_CHARS

    if not os.path.exists(path):
        return f"[read_pptx_pdf] ファイルが見つかりません: {path}"

    try:
        data = _document_to_json(path)
    except Exception as e:
        return f"[read_pptx_pdf] 文書の読み込み/抽出に失敗しました: {e!r}"

    page_index = args.get("page_index")
    if page_index is not None:
        try:
            page_index_int = int(page_index)
        except Exception:
            return "[read_pptx_pdf] page_index は整数で指定してください。"
        text = _build_single_page_text(data, page_index_int)
    else:
        text = _build_all_pages_text(data)

    if len(text) > max_chars_int:
        text = text[:max_chars_int] + "\n…(truncated)…"

    return text
