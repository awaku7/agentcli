from __future__ import annotations

import base64
import io
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from .i18n_helper import make_tool_translator
from .response_util import make_response

_ = make_tool_translator(__file__)

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "tool_genre": "media",
    "x_parallel_safe": True,
    "function": {
        "name": "mermaid_render",
        "description": _(
            "tool.description",
            default="Render Mermaid diagrams to PNG, SVG, or PDF completely offline using a Python-native renderer.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "Mermaid",
                "flowchart",
                "diagram",
                "offline renderer",
                "PNG",
                "SVG",
            ],
        ),
        "x_search_terms_en": [
            "Mermaid",
            "flowchart",
            "diagram",
            "offline renderer",
            "PNG",
            "SVG",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": _(
                        "param.source.description", default="Mermaid source text."
                    ),
                },
                "input_path": {
                    "type": "string",
                    "description": _(
                        "param.input_path.description",
                        default="Optional Mermaid file path.",
                    ),
                },
                "output_path": {
                    "type": "string",
                    "description": _(
                        "param.output_path.description",
                        default="Output .png, .svg, or .pdf path.",
                    ),
                },
                "scale": {
                    "type": "number",
                    "minimum": 0.25,
                    "default": 1.0,
                    "description": _(
                        "param.scale.description", default="PNG scale factor."
                    ),
                },
                "background": {
                    "type": "string",
                    "default": "white",
                    "description": _(
                        "param.background.description", default="Background color."
                    ),
                },
                "theme": {
                    "type": "string",
                    "enum": ["default", "forest", "dark", "neutral"],
                    "default": "default",
                    "description": _(
                        "param.theme.description", default="Mermaid theme."
                    ),
                },
                "include_base64": {
                    "type": "boolean",
                    "description": _(
                        "param.include_base64.description",
                        default="Include base64 data for remote clients.",
                    ),
                    "default": True,
                },
            },
            "required": ["output_path"],
            "additionalProperties": False,
        },
    },
    "is_agent_content": False,
}

BUSY_LABEL = False


def _load_mermaidx():
    try:
        import mermaidx

        return mermaidx
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "mermaidx"])
        import mermaidx

        return mermaidx


def _font_file(source: str) -> Path | None:
    # Prefer broad CJK fonts for mixed-language diagrams, then use
    # platform-specific fonts for Japanese/Chinese/Korean text.
    broad = [
        Path(r"C:\Windows\Fonts\NotoSansCJK-Regular.ttc"),
        Path(r"C:\Windows\Fonts\NotoSansCJKjp-Regular.otf"),
        Path.home() / ".fonts" / "NotoSansCJK-Regular.ttc",
    ]
    japanese = [
        Path(r"C:\Windows\Fonts\meiryo.ttc"),
        Path(r"C:\Windows\Fonts\YuGothM.ttc"),
        Path(r"C:\Windows\Fonts\msgothic.ttc"),
    ]
    chinese = [Path(r"C:\Windows\Fonts\msyh.ttc"), Path(r"C:\Windows\Fonts\simsun.ttc")]
    korean = [
        Path(r"C:\Windows\Fonts\malgun.ttf"),
        Path(r"C:\Windows\Fonts\malgunbd.ttf"),
    ]
    arabic = [
        Path(r"C:\Windows\Fonts\NotoSansArabic-Regular.ttf"),
        Path(r"C:\Windows\Fonts\trado.ttf"),
        Path(r"C:\Windows\Fonts\arial.ttf"),
    ]
    hebrew = [
        Path(r"C:\Windows\Fonts\NotoSansHebrew-Regular.ttf"),
        Path(r"C:\Windows\Fonts\arial.ttf"),
    ]
    devanagari = [
        Path(r"C:\Windows\Fonts\NotoSansDevanagari-Regular.ttf"),
        Path(r"C:\Windows\Fonts\Nirmala.ttf"),
    ]
    thai = [
        Path(r"C:\Windows\Fonts\NotoSansThai-Regular.ttf"),
        Path(r"C:\Windows\Fonts\LeelawUI.ttf"),
    ]
    bengali = [
        Path(r"C:\Windows\Fonts\NotoSansBengali-Regular.ttf"),
        Path(r"C:\Windows\Fonts\Nirmala.ttf"),
    ]
    if re.search(r"[ぁ-ゖァ-ヺ々〆〄]", source):
        candidates = broad + japanese
    elif re.search(r"[가-힣]", source):
        candidates = broad + korean
    elif re.search(r"[一-龥]", source):
        candidates = broad + chinese
    elif re.search(r"[؀-ۿݐ-ݿ]", source):
        candidates = arabic
    elif re.search(r"[֐-׿]", source):
        candidates = hebrew
    elif re.search(r"[ऀ-ॿ]", source):
        candidates = devanagari
    elif re.search(r"[ก-๛]", source):
        candidates = thai
    elif re.search(r"[ঀ-৿]", source):
        candidates = bengali
    else:
        candidates = [
            Path(r"C:\Windows\Fonts\arial.ttf"),
            Path(r"C:\Windows\Fonts\DejaVuSans.ttf"),
        ]
    source = next((p for p in candidates if p.exists()), None)
    if source is None:
        return None
    out = Path.home() / ".uag" / "cache" / f"mermaid_{source.stem}.ttf"
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists() or out.stat().st_mtime < source.stat().st_mtime:
        if source.suffix.lower() == ".ttc":
            try:
                from fontTools.ttLib import TTCollection
            except ImportError:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", "fonttools"]
                )
                from fontTools.ttLib import TTCollection
            collection = TTCollection(source)
            buffer = io.BytesIO()
            collection.fonts[0].save(buffer)
            out.write_bytes(buffer.getvalue())
        else:
            out.write_bytes(source.read_bytes())
    return out


def _japanese_svg(svg: str, font_path: Path | None) -> str:
    family = "Meiryo"
    if font_path:
        encoded = base64.b64encode(font_path.read_bytes()).decode("ascii")
        css = (
            f"<style>@font-face{{font-family:'{family}';src:url(data:font/ttf;base64,{encoded})}}"
            f"*{{font-family:'{family}' !important}}</style>"
        )
        svg = svg.replace(">", ">" + css, 1)
    return re.sub(
        r"trebuchet ms,?verdana,?arial,sans-serif",
        f"'{family}', sans-serif",
        svg,
        flags=re.I,
    )


def run_tool(args: dict[str, Any]) -> str:
    source = str(args.get("source") or "")
    input_path = str(args.get("input_path") or "")
    if bool(source) == bool(input_path):
        raise ValueError("source または input_path のどちらか一方を指定してください")
    if input_path:
        source = Path(input_path).read_text(encoding="utf-8")
    output = Path(str(args.get("output_path") or ""))
    if output.suffix.lower() not in {".png", ".svg", ".pdf"}:
        raise ValueError("output_path は .png / .svg / .pdf で指定してください")
    output.parent.mkdir(parents=True, exist_ok=True)
    mermaidx = _load_mermaidx()
    diagram = mermaidx.render(source, theme=str(args.get("theme") or "default"))
    font_path = _font_file(source)
    svg = _japanese_svg(diagram.svg(), font_path)
    if output.suffix.lower() == ".svg":
        output.write_text(svg, encoding="utf-8")
    elif output.suffix.lower() == ".png":
        import resvg_py

        rendered = resvg_py.svg_to_bytes(
            svg_string=svg,
            background=str(args.get("background") or "white"),
            font_files=[str(font_path)] if font_path else None,
            sans_serif_family="Meiryo",
            font_family="Meiryo",
        )
        output.write_bytes(bytes(rendered))
    else:
        diagram.save(str(output), format="pdf")
    suffix = output.suffix.lower()
    mime = {".png": "image/png", ".svg": "image/svg+xml", ".pdf": "application/pdf"}[
        suffix
    ]
    attachment: dict[str, Any] = {
        "type": "image" if suffix in {".png", ".svg"} else "file",
        "mime": mime,
        "name": output.name,
        "path": str(output),
    }
    if bool(args.get("include_base64", True)):
        attachment["data_base64"] = base64.b64encode(output.read_bytes()).decode(
            "ascii"
        )
    try:
        from ..runtime.artifact_helpers import register_artifacts

        artifacts = register_artifacts(
            [str(output)],
            metadata={"kind": "mermaid_render", "format": suffix.lstrip(".")},
        )
    except Exception:
        artifacts = []
    data = {
        "artifacts": artifacts,
        "saved_files": [str(output)],
        "attachments": [attachment],
    }
    return make_response(
        True, _("ok.rendered", default="[OK] Mermaid rendered"), data=data
    )


if __name__ == "__main__":
    print(
        run_tool(
            {"source": "flowchart TD; A[Start]-->B[Done]", "output_path": "mermaid.png"}
        )
    )
