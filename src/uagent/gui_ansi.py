# -*- coding: utf-8 -*-
"""ANSI to HTML conversion helpers for GUI output."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Optional

_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
_URL_RE = re.compile(r"\b(https?://[^\s<>\"']+|www\.[^\s<>\"']+)", re.IGNORECASE)


@dataclass
class _StyleState:
    fg: Optional[str] = None
    bg: Optional[str] = None
    bold: bool = False
    italic: bool = False
    underline: bool = False

    def copy(self) -> "_StyleState":
        return _StyleState(
            fg=self.fg,
            bg=self.bg,
            bold=self.bold,
            italic=self.italic,
            underline=self.underline,
        )


_SGR_FG = {
    30: "#000000",
    31: "#dc2626",
    32: "#16a34a",
    33: "#ca8a04",
    34: "#2563eb",
    35: "#a855f7",
    36: "#0891b2",
    37: "#d1d5db",
    90: "#6b7280",
    91: "#f87171",
    92: "#4ade80",
    93: "#facc15",
    94: "#60a5fa",
    95: "#d8b4fe",
    96: "#22d3ee",
    97: "#ffffff",
}

_SGR_BG = {
    40: "#000000",
    41: "#dc2626",
    42: "#16a34a",
    43: "#ca8a04",
    44: "#2563eb",
    45: "#a855f7",
    46: "#0891b2",
    47: "#d1d5db",
    100: "#6b7280",
    101: "#f87171",
    102: "#4ade80",
    103: "#facc15",
    104: "#60a5fa",
    105: "#d8b4fe",
    106: "#22d3ee",
    107: "#ffffff",
}


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text or "")


def _style_to_css(st: _StyleState) -> str:
    parts: list[str] = []
    if st.fg:
        parts.append(f"color:{st.fg}")
    if st.bg:
        parts.append(f"background-color:{st.bg}")
    if st.bold:
        parts.append("font-weight:700")
    if st.italic:
        parts.append("font-style:italic")
    if st.underline:
        parts.append("text-decoration:underline")
    return "; ".join(parts)


def _xterm256_to_hex(n: int) -> str:
    n = max(0, min(255, int(n)))
    base = [
        "#000000",
        "#800000",
        "#008000",
        "#808000",
        "#000080",
        "#800080",
        "#008080",
        "#c0c0c0",
        "#808080",
        "#ff0000",
        "#00ff00",
        "#ffff00",
        "#0000ff",
        "#ff00ff",
        "#00ffff",
        "#ffffff",
    ]
    if n < 16:
        return base[n]
    if n < 232:
        n -= 16
        r = n // 36
        g = (n % 36) // 6
        b = n % 6

        def _c(v: int) -> int:
            return 0 if v == 0 else 55 + 40 * v

        return f"#{_c(r):02x}{_c(g):02x}{_c(b):02x}"
    v = 8 + (n - 232) * 10
    return f"#{v:02x}{v:02x}{v:02x}"


def _apply_sgr(st: _StyleState, params: list[int]) -> _StyleState:
    if not params:
        params = [0]
    out = st.copy()
    i = 0
    while i < len(params):
        p = params[i]
        if p == 0:
            out = _StyleState()
        elif p == 1:
            out.bold = True
        elif p == 3:
            out.italic = True
        elif p == 4:
            out.underline = True
        elif p == 22:
            out.bold = False
        elif p == 23:
            out.italic = False
        elif p == 24:
            out.underline = False
        elif 30 <= p <= 37 or 90 <= p <= 97:
            out.fg = _SGR_FG.get(p)
        elif p == 39:
            out.fg = None
        elif 40 <= p <= 47 or 100 <= p <= 107:
            out.bg = _SGR_BG.get(p)
        elif p == 49:
            out.bg = None
        elif p == 38 and i + 2 < len(params) and params[i + 1] == 5:
            out.fg = _xterm256_to_hex(params[i + 2])
            i += 2
        elif p == 48 and i + 2 < len(params) and params[i + 1] == 5:
            out.bg = _xterm256_to_hex(params[i + 2])
            i += 2
        i += 1
    return out


def _linkify_escaped_html(text: str) -> str:
    def _repl(m: re.Match) -> str:
        raw = m.group(0)
        href = raw
        if raw.lower().startswith("www."):
            href = "https://" + raw
        return f'<a href="{href}" style="color:#2563eb; text-decoration: underline;">{raw}</a>'

    return _URL_RE.sub(_repl, text)


def _render_text(text: str, st: _StyleState, *, linkify: bool) -> str:
    escaped = html.escape(text).replace("\n", "<br>")
    if linkify:
        escaped = _linkify_escaped_html(escaped)
    css = _style_to_css(st)
    if css:
        return f'<span style="{css}">{escaped}</span>'
    return escaped


def ansi_to_html(text: str, *, linkify: bool = True) -> str:
    """Convert ANSI-colored text to HTML suitable for QTextBrowser."""
    text = text or ""
    pieces: list[str] = []
    st = _StyleState()
    cur = 0

    for m in _ANSI_RE.finditer(text):
        chunk = text[cur : m.start()]
        if chunk:
            pieces.append(_render_text(chunk, st, linkify=linkify))
        code = m.group(0)
        params: list[int] = []
        try:
            inner = code[2:-1]
            if inner.startswith("["):
                inner = inner[1:]
            if inner.startswith("?"):
                inner = inner[1:]
            for p in inner.rstrip("m").split(";"):
                if p.strip():
                    params.append(int(p))
        except Exception:
            params = [0]
        st = _apply_sgr(st, params)
        cur = m.end()

    tail = text[cur:]
    if tail:
        pieces.append(_render_text(tail, st, linkify=linkify))

    return "".join(pieces)


def wrap_pre(text: str) -> str:
    return (
        '<div style="font-family: Consolas, Menlo, Monaco, monospace; white-space: pre;">'
        + html.escape(text or "")
        + "</div>"
    )
