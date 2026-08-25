"""GUI icon painting helpers (split from scheckgui.py)."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets


def _paint_icon_attach(color: QtGui.QColor, size: int = 24) -> QtGui.QIcon:
    """Paint a paperclip icon."""
    pm = QtGui.QPixmap(size, size)
    pm.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    pen = QtGui.QPen(color, max(2, size // 10))
    pen.setCapStyle(QtCore.Qt.RoundCap)
    p.setPen(pen)
    cx, cy = size / 2, size / 2
    # Top loop
    p.drawArc(
        int(cx - size * 0.15),
        int(cy - size * 0.45),
        int(size * 0.3),
        int(size * 0.3),
        0,
        16 * 180,
    )
    # Stem
    p.drawLine(
        int(cx + size * 0.15),
        int(cy - size * 0.3),
        int(cx + size * 0.15),
        int(cy + size * 0.35),
    )
    # Bottom hook
    p.drawArc(
        int(cx + size * 0.05),
        int(cy + size * 0.15),
        int(size * 0.2),
        int(size * 0.2),
        0,
        16 * 180,
    )
    p.end()
    return QtGui.QIcon(pm)


def _paint_icon_send(color: QtGui.QColor, size: int = 24) -> QtGui.QIcon:
    """Paint a recognizable paper-plane send icon."""
    pm = QtGui.QPixmap(size, size)
    pm.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    p.setPen(
        QtGui.QPen(
            color,
            max(1, size // 12),
            QtCore.Qt.SolidLine,
            QtCore.Qt.RoundCap,
            QtCore.Qt.RoundJoin,
        )
    )
    p.setBrush(QtGui.QBrush(color))
    m = size * 0.14
    plane = QtGui.QPolygonF(
        [
            QtCore.QPointF(m, size * 0.48),
            QtCore.QPointF(size - m, m),
            QtCore.QPointF(size * 0.68, size - m),
            QtCore.QPointF(size * 0.53, size * 0.56),
            QtCore.QPointF(m, size * 0.48),
        ]
    )
    p.drawPolygon(plane)
    p.setPen(
        QtGui.QPen(
            QtGui.QColor("#ffffff"),
            max(1, size // 14),
            QtCore.Qt.SolidLine,
            QtCore.Qt.RoundCap,
        )
    )
    p.drawLine(
        QtCore.QPointF(m + size * 0.08, size * 0.48),
        QtCore.QPointF(size * 0.54, size * 0.55),
    )
    p.end()
    return QtGui.QIcon(pm)


def _make_attach_icon(size: int = 24) -> QtGui.QIcon:
    """Create a recognizable attach/paperclip icon."""
    try:
        try:
            app = QtWidgets.QApplication.instance()
            if app:
                c = app.palette().color(QtGui.QPalette.ButtonText)
            else:
                c = QtGui.QColor("#ffffff")
        except Exception:
            c = QtGui.QColor("#ffffff")
        return _paint_icon_attach(c, size)
    except Exception:
        return QtGui.QIcon()


def _make_send_icon(size: int = 24) -> QtGui.QIcon:
    """Create a recognizable send/arrow icon."""
    try:
        try:
            app = QtWidgets.QApplication.instance()
            if app:
                c = app.palette().color(QtGui.QPalette.ButtonText)
            else:
                c = QtGui.QColor("#ffffff")
        except Exception:
            c = QtGui.QColor("#ffffff")
        return _paint_icon_send(c, size)
    except Exception:
        return QtGui.QIcon()


def _menu_icon_color() -> QtGui.QColor:
    """Return icon color adapting to system palette (high contrast safe)."""
    try:
        app = QtWidgets.QApplication.instance()
        if app:
            return app.palette().color(QtGui.QPalette.WindowText)
    except Exception:
        pass
    return QtGui.QColor("#374151")


def _make_stop_icon(size: int = 18) -> QtGui.QIcon:
    """Create a clear stop-square icon for destructive/cancel actions."""
    pm = QtGui.QPixmap(size, size)
    pm.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    p.setPen(QtCore.Qt.NoPen)
    p.setBrush(QtGui.QColor("#ffffff"))
    margin = max(3, size // 5)
    p.drawRoundedRect(margin, margin, size - margin * 2, size - margin * 2, 2, 2)
    p.end()
    return QtGui.QIcon(pm)


def _make_close_icon(size: int = 18) -> QtGui.QIcon:
    """Create a clean close/cancel cross icon."""
    pm = QtGui.QPixmap(size, size)
    pm.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    pen = QtGui.QPen(QtGui.QColor("#ffffff"), max(2, size // 7))
    pen.setCapStyle(QtCore.Qt.RoundCap)
    p.setPen(pen)
    margin = max(4, size // 4)
    p.drawLine(margin, margin, size - margin, size - margin)
    p.drawLine(size - margin, margin, margin, size - margin)
    p.end()
    return QtGui.QIcon(pm)


def _make_font_icon(size: int = 18, point_size: int = 12) -> QtGui.QIcon:
    """Create an A-shaped font-size icon; the glyph size conveys the level."""
    pm = QtGui.QPixmap(size, size)
    pm.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    p.setPen(_menu_icon_color())
    font = QtGui.QFont("sans-serif", point_size, QtGui.QFont.Bold)
    p.setFont(font)
    p.drawText(pm.rect(), QtCore.Qt.AlignCenter, "A")
    p.end()
    return QtGui.QIcon(pm)


def _make_reasoning_icon(size: int = 18) -> QtGui.QIcon:
    """Create a brain-like icon for model reasoning controls."""
    pm = QtGui.QPixmap(size, size)
    pm.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    color = _menu_icon_color()
    pen = QtGui.QPen(color, max(1, size // 9), QtCore.Qt.SolidLine, QtCore.Qt.RoundCap)
    p.setPen(pen)
    p.drawArc(
        int(size * 0.08),
        int(size * 0.22),
        int(size * 0.48),
        int(size * 0.58),
        70 * 16,
        230 * 16,
    )
    p.drawArc(
        int(size * 0.44),
        int(size * 0.22),
        int(size * 0.48),
        int(size * 0.58),
        -120 * 16,
        230 * 16,
    )
    p.drawLine(size / 2, size * 0.2, size / 2, size * 0.8)
    p.drawLine(size * 0.25, size * 0.42, size * 0.42, size * 0.5)
    p.drawLine(size * 0.75, size * 0.42, size * 0.58, size * 0.5)
    p.end()
    return QtGui.QIcon(pm)


def _make_detail_icon(size: int = 18) -> QtGui.QIcon:
    """Create a detail/verbosity icon with graduated text lines."""
    pm = QtGui.QPixmap(size, size)
    pm.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    pen = QtGui.QPen(
        _menu_icon_color(), max(1, size // 8), QtCore.Qt.SolidLine, QtCore.Qt.RoundCap
    )
    p.setPen(pen)
    for i, width in enumerate((0.42, 0.68, 0.88)):
        y = size * (0.24 + i * 0.27)
        p.drawLine(size * 0.08, y, size * width, y)
    p.end()
    return QtGui.QIcon(pm)


def _make_genre_icon(size: int = 18) -> QtGui.QIcon:
    """Create a grouped-tools icon for tool genre selection."""
    pm = QtGui.QPixmap(size, size)
    pm.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    color = _menu_icon_color()
    p.setPen(QtGui.QPen(color, max(1, size // 10)))
    p.setBrush(QtCore.Qt.NoBrush)
    for i, x in enumerate((0.12, 0.38, 0.64)):
        p.drawRoundedRect(
            int(size * x),
            int(size * (0.24 + i * 0.08)),
            int(size * 0.24),
            int(size * 0.24),
            2,
            2,
        )
    p.drawLine(size * 0.25, size * 0.75, size * 0.75, size * 0.75)
    p.end()
    return QtGui.QIcon(pm)


def _make_help_icon(size: int = 16) -> QtGui.QIcon:
    try:
        pm = QtGui.QPixmap(size, size)
        pm.fill(QtCore.Qt.transparent)
        p = QtGui.QPainter(pm)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        pen = QtGui.QPen(_menu_icon_color(), max(2, size // 8))
        pen.setCapStyle(QtCore.Qt.RoundCap)
        p.setPen(pen)
        cx, cy = size / 2, size / 2
        p.drawEllipse(
            int(cx - size * 0.35),
            int(cy - size * 0.35),
            int(size * 0.7),
            int(size * 0.7),
        )
        _f = QtGui.QFont("sans-serif", size * 3 // 5, QtGui.QFont.Bold)
        p.setFont(_f)
        p.drawText(0, 0, size, size, QtCore.Qt.AlignCenter, "?")
        p.end()
        return QtGui.QIcon(pm)
    except Exception:
        return QtGui.QIcon()


def _make_view_icon(size: int = 16) -> QtGui.QIcon:
    try:
        pm = QtGui.QPixmap(size, size)
        pm.fill(QtCore.Qt.transparent)
        p = QtGui.QPainter(pm)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        pen = QtGui.QPen(_menu_icon_color(), max(2, size // 8))
        pen.setCapStyle(QtCore.Qt.RoundCap)
        p.setPen(pen)
        cx, cy = size / 2, size / 2
        # Eye outline: an ellipse
        br, sr = size * 0.35, size * 0.22
        p.drawEllipse(int(cx - br), int(cy - sr), int(br * 2), int(sr * 2))
        # Pupil: filled circle
        brush = QtGui.QBrush(_menu_icon_color())
        p.setBrush(brush)
        pr = size * 0.08
        p.drawEllipse(int(cx - pr), int(cy - pr), int(pr * 2), int(pr * 2))
        p.end()
        return QtGui.QIcon(pm)
    except Exception:
        return QtGui.QIcon()


def _make_mode_icon(size: int = 16) -> QtGui.QIcon:
    try:
        pm = QtGui.QPixmap(size, size)
        pm.fill(QtCore.Qt.transparent)
        p = QtGui.QPainter(pm)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        pen = QtGui.QPen(_menu_icon_color(), max(2, size // 8))
        pen.setCapStyle(QtCore.Qt.RoundCap)
        p.setPen(pen)
        cx, cy = size / 2, size / 2
        # Three horizontal bars (sliders config icon)
        for i, wf in enumerate([0.9, 0.6, 0.75]):
            y = cy + (i - 1) * size * 0.22
            hw = size * wf * 0.4
            p.drawLine(int(cx - hw), int(y), int(cx + hw), int(y))
            # Small circle at right end of each bar
            brush = QtGui.QBrush(_menu_icon_color())
            p.setBrush(brush)
            p.drawEllipse(
                int(cx + hw - size * 0.06),
                int(y - size * 0.06),
                int(size * 0.12),
                int(size * 0.12),
            )
            p.setBrush(QtCore.Qt.NoBrush)
        p.end()
        return QtGui.QIcon(pm)
    except Exception:
        return QtGui.QIcon()


def _make_tools_icon(size: int = 16) -> QtGui.QIcon:
    try:
        pm = QtGui.QPixmap(size, size)
        pm.fill(QtCore.Qt.transparent)
        p = QtGui.QPainter(pm)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        pen = QtGui.QPen(_menu_icon_color(), max(2, size // 8))
        pen.setCapStyle(QtCore.Qt.RoundCap)
        p.setPen(pen)
        cx, cy = size / 2, size / 2
        # Toolbox/drawer icon: simple rectangle with handle
        bw, bh = size * 0.45, size * 0.25
        # Box body
        p.drawRoundedRect(
            int(cx - bw),
            int(cy - bh * 0.3),
            int(bw * 2),
            int(bh * 1.3),
            size * 0.08,
            size * 0.08,
        )
        # Handle on top
        p.drawLine(
            int(cx - bw * 0.5),
            int(cy - bh * 0.3),
            int(cx + bw * 0.5),
            int(cy - bh * 0.3),
        )
        p.end()
        return QtGui.QIcon(pm)
    except Exception:
        return QtGui.QIcon()
