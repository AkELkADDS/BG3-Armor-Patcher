from __future__ import annotations

import math
import sys
from pathlib import Path

from bg3_patcher import lsx
from bg3_patcher.merger import run_patch
from bg3_patcher.models import PatchConfig, PatchValidationError, RaceAssignment
from bg3_patcher.presets import load_preset, save_preset
from bg3_patcher.scanner import (
    VANILLA_EQUIPMENT_RACES,
    VANILLA_EQUIPMENT_RACES_FILENAME,
    format_vanilla_equipment_races_search_hint,
    mod_equipment_race_files,
    resolve_vanilla_equipment_races_path,
    source_label,
)

_PRIORITY_ROW_MIME = "application/x-bg3-priority-row-index"

# Patreon link for the PATREON button (edit slug if yours differs).
_PATREON_PAGE_URL = "https://www.patreon.com/AkELkA"

__author__ = "AkELkA"


def _resource_bundle_dir() -> Path | None:
    """PyInstaller one-file extract root (read-only); None when running from source."""
    if not getattr(sys, "frozen", False):
        return None
    me = getattr(sys, "_MEIPASS", None)
    return Path(me) if me else None


def _preset_is_bundled(path: Path) -> bool:
    bundle = _resource_bundle_dir()
    if bundle is None:
        return False
    try:
        path.resolve().relative_to(bundle.resolve())
    except ValueError:
        return False
    return True


def _preset_stem_exists_on_disk(stem: str, writable_presets: Path) -> bool:
    if (writable_presets / f"{stem}.json").is_file():
        return True
    bundle = _resource_bundle_dir()
    if bundle is not None and (bundle / "presets" / f"{stem}.json").is_file():
        return True
    return False


try:
    from PySide6.QtCore import (
        QEvent,
        QObject,
        QMimeData,
        QPoint,
        QPointF,
        QElapsedTimer,
        QRect,
        QRectF,
        QSize,
        Qt,
        QThread,
        QTimer,
        QUrl,
        Signal,
    )
    from PySide6.QtGui import (
        QBrush,
        QColor,
        QConicalGradient,
        QDesktopServices,
        QDrag,
        QDragEnterEvent,
        QDragLeaveEvent,
        QDragMoveEvent,
        QDropEvent,
        QEnterEvent,
        QFont,
        QIcon,
        QLinearGradient,
        QMouseEvent,
        QPainter,
        QPainterPath,
        QPen,
        QKeySequence,
        QPaintEvent,
        QPalette,
        QPixmap,
        QResizeEvent,
        QShortcut,
        QCloseEvent,
    )
    from PySide6.QtWidgets import (
        QApplication,
        QAbstractItemView,
        QComboBox,
        QDialog,
        QFileDialog,
        QFrame,
        QGraphicsBlurEffect,
        QGraphicsDropShadowEffect,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QInputDialog,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMenu,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QStyle,
        QStyleFactory,
        QStyleOptionComboBox,
        QToolButton,
        QVBoxLayout,
        QWidget,
    )
except ImportError as exc:  # pragma: no cover - exercised only when UI dependency is missing.
    raise SystemExit("PySide6 is required for the UI. Install with: python -m pip install -e .") from exc


def _pixmap_save_glyph(side: int = 64) -> QPixmap:
    """Flat floppy-disk silhouette for preset Save (fill #f0f0f0)."""
    transparent = QColor(0, 0, 0, 0)
    fill = QColor(240, 240, 240)
    pm = QPixmap(side, side)
    pm.fill(transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    m = side * 0.12
    body = QRectF(m, m, side - 2 * m, side - 2 * m)
    notch = side * 0.17
    outer = QPainterPath()
    outer.moveTo(body.left(), body.top())
    outer.lineTo(body.right() - notch, body.top())
    outer.lineTo(body.right(), body.top() + notch)
    outer.lineTo(body.right(), body.bottom())
    outer.lineTo(body.left(), body.bottom())
    outer.closeSubpath()
    painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
    painter.setBrush(fill)
    painter.drawPath(outer)
    painter.setCompositionMode(QPainter.CompositionMode_DestinationOut)
    painter.setBrush(QColor(255, 255, 255))
    painter.drawRoundedRect(
        QRectF(body.left() + side * 0.10, body.top() + side * 0.09, side * 0.36, side * 0.11),
        side * 0.025,
        side * 0.025,
    )
    painter.drawRoundedRect(
        QRectF(body.center().x() - side * 0.125, body.bottom() - side * 0.29, side * 0.25, side * 0.13),
        side * 0.03,
        side * 0.03,
    )
    painter.end()
    return pm


_SMALL_ROW_BTN_SIDE = 36
_SMALL_ROW_GLYPH_PX = 17
_SMALL_ROW_GLYPH_UP_NUDGE = 2


def _row_glyph_icon(glyph: str, *, side: int = _SMALL_ROW_BTN_SIDE, pixel: int = _SMALL_ROW_GLYPH_PX) -> QIcon:
    """Centered +/− on transparent pixmap so the button shows a square glyph without label offset."""
    pm = QPixmap(side, side)
    pm.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    font = QFont("Segoe UI")
    font.setPixelSize(pixel)
    font.setWeight(QFont.Weight.Black)
    painter.setFont(font)
    painter.setPen(QColor(240, 240, 240))
    painter.translate(0, -_SMALL_ROW_GLYPH_UP_NUDGE)
    painter.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, glyph)
    painter.end()
    return QIcon(pm)


def _setup_small_row_btn(btn: QPushButton, glyph: str) -> None:
    s = _SMALL_ROW_BTN_SIDE
    btn.setText("")
    btn.setIcon(_row_glyph_icon(glyph, side=s, pixel=_SMALL_ROW_GLYPH_PX))
    btn.setIconSize(QSize(s, s))
    btn.setFixedSize(s, s)


def _style_preset_save_button(btn: QPushButton) -> None:
    btn.setIcon(QIcon(_pixmap_save_glyph(64)))
    btn.setText("")
    btn.setIconSize(QSize(20, 20))
    btn.setFixedSize(40, 40)


def _safe_preset_stem(name: str) -> str | None:
    safe = "".join(c for c in name if c.isalnum() or c in (" ", "-", "_")).strip().replace(" ", "_")
    return safe or None


# Combo itemData for the synthetic “new preset” row (not a filesystem path).
_PRESET_COMBO_NEW_MARKER = "__PRESET_NEW__"


APP_STYLESHEET = """
QWidget {
    background-color: #121212;
    color: #f0f0f0;
    font-family: "Segoe UI", "Arial", sans-serif;
    font-size: 13px;
}
QScrollArea { border: none; background-color: #121212; }
QScrollArea > QWidget > QWidget { background-color: #121212; }
/* Hairline flat scrollbars (no arrows, no 3D chrome) */
QScrollBar:vertical {
    background: transparent;
    width: 4px;
    margin: 0;
    border: none;
}
QScrollBar::handle:vertical {
    background-color: #4a4a4a;
    border-radius: 2px;
    min-height: 28px;
    margin: 2px 1px 2px 1px;
}
QScrollBar::handle:vertical:hover {
    background-color: #6a6a6a;
}
QScrollBar::handle:vertical:pressed {
    background-color: #888888;
}
QScrollBar::groove:vertical {
    background-color: #1e1e1e;
    border-radius: 2px;
    margin: 0;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    border: none;
    background: transparent;
    height: 0px;
    width: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
QScrollBar:horizontal {
    background: transparent;
    height: 4px;
    margin: 0;
    border: none;
}
QScrollBar::handle:horizontal {
    background-color: #4a4a4a;
    border-radius: 2px;
    min-width: 28px;
    margin: 1px 2px 1px 2px;
}
QScrollBar::handle:horizontal:hover {
    background-color: #6a6a6a;
}
QScrollBar::handle:horizontal:pressed {
    background-color: #888888;
}
QScrollBar::groove:horizontal {
    background-color: #1e1e1e;
    border-radius: 2px;
    margin: 0;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    border: none;
    background: transparent;
    height: 0px;
    width: 0px;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}
QAbstractScrollArea::corner {
    background: #121212;
    border: none;
}
QLineEdit, QComboBox {
    background-color: #000000;
    border: none;
    border-radius: 6px;
    padding: 8px 10px;
    color: #f0f0f0;
    selection-background-color: #404040;
}
QLineEdit:focus, QComboBox:focus {
    background-color: #1a1a1a;
    border: none;
    outline: none;
}
QLineEdit:read-only {
    background-color: #000000;
    color: #c8c8c8;
}
QLineEdit:read-only:focus {
    background-color: #000000;
}
QComboBox QLineEdit {
    border: none;
    padding: 0px 4px;
    margin: 0px;
    background-color: transparent;
    border-radius: 0px;
}
QComboBox QLineEdit:focus {
    background-color: transparent;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 32px;
    border: none;
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
    background-color: #000000;
}
QComboBox::drop-down:hover {
    background-color: #1a1a1a;
}
QComboBox QAbstractItemView {
    background-color: #000000;
    color: #f0f0f0;
    border: none;
    outline: none;
    selection-background-color: #333333;
}
QComboBox:disabled {
    color: #8a8a8a;
    background-color: #141414;
}
QComboBox::drop-down:disabled {
    background-color: #141414;
}
QPushButton#eqrMultiPick {
    background-color: #000000;
    border: none;
    border-radius: 6px;
    padding: 8px 30px 8px 10px;
    color: #f0f0f0;
    text-align: left;
}
QPushButton#eqrMultiPick:hover {
    background-color: #1a1a1a;
}
QPushButton#eqrMultiPick:pressed {
    background-color: #222222;
}
QPushButton#eqrMultiPick:focus {
    border: none;
    outline: none;
}
QPushButton#eqrMultiPick:disabled {
    color: #8a8a8a;
    background-color: #141414;
}
QFrame#eqrPickPopup {
    background-color: #000000;
    border: 1px solid #2a2a2a;
    border-radius: 6px;
}
QFrame#eqrPickPopup QListWidget {
    background-color: #000000;
    color: #f0f0f0;
    border: none;
    outline: none;
    padding-left: 0px;
}
QFrame#eqrPickPopup QListWidget::item {
    padding: 6px 8px 6px 2px;
}
QFrame#eqrPickPopup QListWidget::indicator {
    width: 10px;
    height: 10px;
    margin-left: 3px;
    margin-right: 6px;
    border: none;
    outline: none;
}
QFrame#eqrPickPopup QListWidget::indicator:unchecked {
    background-color: #3a3a3a;
    border: none;
    border-radius: 5px;
    image: none;
}
QFrame#eqrPickPopup QListWidget::indicator:unchecked:hover {
    background-color: #4a4a4a;
    border: none;
    border-radius: 5px;
    image: none;
}
QFrame#eqrPickPopup QListWidget::indicator:checked {
    background-color: #ffffff;
    border: none;
    border-radius: 5px;
    image: none;
}
QFrame#eqrPickPopup QListWidget::indicator:checked:hover {
    background-color: #f0f0f0;
    border: none;
    border-radius: 5px;
    image: none;
}
QFrame#eqrPickPopup QListWidget::indicator:disabled {
    background-color: #141414;
    border: none;
    border-radius: 5px;
    image: none;
}
QFrame#eqrPickPopup QListWidget::indicator:checked:disabled {
    background-color: #707070;
    border: none;
    border-radius: 5px;
    image: none;
}
QFrame#eqrPickPopup QListWidget::item:hover {
    background-color: #222222;
}
QFrame#eqrPickPopup QListWidget::item:focus {
    border: none;
    outline: none;
}
QMenu {
    background-color: #000000;
    color: #f0f0f0;
    border: 1px solid #2a2a2a;
}
QMenu::item {
    padding: 8px 24px 8px 12px;
}
QMenu::item:selected {
    background-color: #333333;
}
QPushButton {
    background-color: #000000;
    border: none;
    border-radius: 6px;
    padding: 8px 14px;
    color: #f0f0f0;
}
QPushButton:hover { background-color: #1a1a1a; }
QPushButton:pressed { background-color: #222222; }
QPushButton:focus {
    border: none;
    outline: none;
}
QPushButton#pathRowBrowseBtn {
    padding: 5px 12px;
    min-height: 0px;
}
QPushButton#patchButton {
    background-color: transparent;
    border: none;
    padding: 0px;
    font-weight: 900;
}
QPushButton#patchButton:hover, QPushButton#patchButton:pressed {
    background-color: transparent;
}
QPushButton#patchButton:focus {
    border: none;
    outline: none;
}
QPushButton#patreonButton {
    background-color: transparent;
    border: none;
    padding: 0px;
    font-weight: 900;
}
QPushButton#patreonButton:hover, QPushButton#patreonButton:pressed {
    background-color: transparent;
}
QPushButton#patreonButton:focus {
    border: none;
    outline: none;
}
QWidget#basementBar {
    background-color: #060607;
    border: none;
}
QPushButton#iconButton, QToolButton#iconButton {
    background-color: #000000;
    border: none;
    border-radius: 6px;
    min-width: 36px;
    min-height: 36px;
}
QPushButton#iconButton {
    padding: 0px 2px;
    font-size: 17px;
    font-weight: bold;
}
QToolButton#iconButton {
    padding: 6px 10px;
}
QPushButton#iconButton:hover, QToolButton#iconButton:hover { background-color: #1a1a1a; }
QPushButton#iconButton:pressed, QToolButton#iconButton:pressed { background-color: #222222; }
QPushButton#iconButton:focus, QToolButton#iconButton:focus { border: none; outline: none; }
QPushButton#smallRowBtn {
    min-width: 36px;
    max-width: 36px;
    min-height: 36px;
    max-height: 36px;
    padding: 0px;
    border: none;
    border-radius: 6px;
}
QLabel#sectionTitle {
    font-size: 20.7px;
    font-weight: bold;
    color: #ffffff;
    margin-top: 8px;
    margin-bottom: 4px;
}
QLabel#appTitle {
    font-size: 22px;
    font-weight: bold;
    color: #ffffff;
    letter-spacing: 1px;
}
QLabel#hint {
    font-size: 11px;
    color: #9a9a9a;
}
QWidget#vanillaScanDetailsBlock {
    background-color: transparent;
}
QFrame#vanillaScanDebugPanel {
    background-color: #000000;
    border: none;
    border-radius: 6px;
    margin-top: 2px;
}
QToolButton#vanillaScanToggle {
    background-color: transparent;
    color: #888888;
    font-size: 11px;
    border: none;
    padding: 2px 4px;
    text-align: left;
}
QToolButton#vanillaScanToggle:hover {
    color: #c0c0c0;
}
QToolButton#vanillaScanToggle:focus {
    border: none;
    outline: none;
}
/* Inner log area: override global QWidget #121212 so it matches the black panel */
QWidget#vanillaScanSummaryWrap {
    background-color: #000000;
}
QLabel#vanillaScanSummary {
    font-size: 11px;
    color: #9a9a9a;
    padding: 0px;
    background-color: #000000;
}
QLabel#columnHeader {
    font-size: 12px;
    font-weight: bold;
    color: #e0e0e0;
}
QFrame#separator {
    background-color: #2a2a2a;
    max-height: 1px;
    min-height: 1px;
}
QDialog#appMessageDialog {
    background-color: #121212;
}
QLabel#appMessageHeadline {
    font-size: 19px;
    font-weight: bold;
    color: #ffffff;
    background-color: transparent;
    border: none;
    padding: 0px;
}
QLabel#appMessageBody {
    font-size: 13px;
    font-weight: normal;
    color: #e8e8e8;
    background-color: transparent;
    border: none;
    padding: 0px;
}
"""


class _AppMessageDialog(QDialog):
    """Dark, icon-free message dialog (patch summary, errors, confirmations)."""

    def __init__(self, parent: QWidget | None, *, headline: str, body: str) -> None:
        super().__init__(parent)
        self.setObjectName("appMessageDialog")
        self.setWindowTitle("BG3 ARMOR PATCHER")
        self.setModal(True)
        if parent is not None:
            icon = parent.windowIcon()
            if not icon.isNull():
                self.setWindowIcon(icon)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(28, 24, 28, 22)
        title = QLabel(headline)
        title.setObjectName("appMessageHeadline")
        body_lbl = QLabel(body)
        body_lbl.setObjectName("appMessageBody")
        body_lbl.setWordWrap(True)
        body_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(title)
        layout.addWidget(body_lbl)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        ok = QPushButton("OK")
        ok.setObjectName("pathRowBrowseBtn")
        ok.setMinimumWidth(90)
        ok.setFixedHeight(40)
        ok.clicked.connect(self.accept)
        btn_row.addWidget(ok)
        layout.addLayout(btn_row)


def _paint_down_arrow_triangle(painter: QPainter, arrow: QRect, *, enabled: bool) -> None:
    """Down-pointing triangle in ``arrow`` (same geometry as ``TriangleComboBox``)."""
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setClipRect(arrow)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(240, 240, 240) if enabled else QColor(110, 110, 110))
    cx = float(arrow.center().x())
    m = float(min(arrow.width(), arrow.height()))
    s = 0.55
    half_w = m * 0.32 * s
    base_y = float(arrow.top()) + float(arrow.height()) * 0.30
    tip_y = float(arrow.bottom()) - float(arrow.height()) * 0.22
    mid_y = (base_y + tip_y) / 2.0
    span = (tip_y - base_y) * s
    base_y = mid_y - span * 0.48
    tip_y = mid_y + span * 0.52
    tri = QPainterPath()
    tri.moveTo(cx - half_w, base_y)
    tri.lineTo(cx + half_w, base_y)
    tri.lineTo(cx, tip_y)
    tri.closeSubpath()
    painter.drawPath(tri)


class TriangleComboBox(QComboBox):
    """``QComboBox`` that paints a down-pointing triangle in the arrow slot.

    Stylesheet ``image: url(...)`` for ``QComboBox::down-arrow`` is often ignored on Windows;
    drawing after ``super().paintEvent`` is reliable.
    """

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        opt = QStyleOptionComboBox()
        self.initStyleOption(opt)
        style = self.style()
        if style is None:
            return
        arrow = style.subControlRect(
            QStyle.ComplexControl.CC_ComboBox,
            opt,
            QStyle.SubControl.SC_ComboBoxArrow,
            self,
        )
        if not arrow.isValid() or arrow.width() < 2 or arrow.height() < 2:
            btn_w = style.pixelMetric(QStyle.PixelMetric.PM_ComboBoxButtonWidth, opt, self)
            if btn_w <= 0:
                btn_w = 32
            arrow = QRect(max(0, self.width() - btn_w), 0, min(btn_w, self.width()), self.height())
        painter = QPainter(self)
        _paint_down_arrow_triangle(painter, arrow, enabled=self.isEnabled())
        painter.end()


class _EqrPickList(QListWidget):
    """Any click on a checkable row toggles once (avoids style double-toggle with tiny indicators)."""

    def __init__(self, picker: "EqrMultiPickButton", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._picker = picker

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and not self._picker._updating_list_checks:
            pos = event.position().toPoint()
            item = self.itemAt(pos)
            if item is not None and item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                cur = item.checkState()
                item.setCheckState(
                    Qt.CheckState.Unchecked
                    if cur == Qt.CheckState.Checked
                    else Qt.CheckState.Checked
                )
                self.setFocus()
                event.accept()
                return
        super().mousePressEvent(event)


class EqrMultiPickButton(QPushButton):
    """Multi-select equipment races: checklist popup stays open; summary on the button."""

    selectionChanged = Signal()

    def __init__(self, mode: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._mode = mode
        self._entries: list[tuple[str, str]] = []
        self._selected: set[str] = set()
        self._popup: QFrame | None = None
        self._list_widget: QListWidget | None = None
        self._updating_list_checks = False
        self.setObjectName("eqrMultiPick")
        self.setMinimumHeight(36)
        self.setMaximumWidth(276)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(self._on_clicked_toggle_popup)
        self._sync_label()

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        btn_w = 26
        arrow = QRect(max(0, self.width() - btn_w), 0, min(btn_w, self.width()), self.height())
        painter = QPainter(self)
        _paint_down_arrow_triangle(painter, arrow, enabled=self.isEnabled())
        painter.end()

    def hideEvent(self, event) -> None:  # noqa: ANN001
        self._hide_popup_if_any()
        super().hideEvent(event)

    def _hide_popup_if_any(self) -> None:
        if self._popup is not None and self._popup.isVisible():
            self._popup.hide()

    def has_entries(self) -> bool:
        return bool(self._entries)

    def snapshot_selection(self) -> tuple[frozenset[str], bool]:
        return (frozenset(self._selected), self.include_all_custom())

    def include_all_custom(self) -> bool:
        return self._mode == "custom" and "__all__" in self._selected

    def selected_ordered(self) -> tuple[str, ...]:
        """Race GUIDs in list order (excludes ``__all__`` sentinel)."""
        return tuple(d for _n, d in self._entries if d in self._selected and d != "__all__")

    def set_invalid_path_custom(self) -> None:
        self._hide_popup_if_any()
        self._entries = []
        self._selected = set()
        self.setText("— choose mod folder first —")
        self.setEnabled(False)

    def refresh_summary(self) -> None:
        self._sync_label()

    def set_entries(self, entries: list[tuple[str, str]], preserve: tuple[frozenset[str], bool] | None) -> None:
        self._entries = list(entries)
        valid = {d for _n, d in self._entries}
        if preserve is not None:
            self._restore_selection_from_snapshot(preserve, valid)
        else:
            self._selected = {d for d in self._selected if d in valid}
        self._sync_popup_list_if_visible()
        self._sync_label()

    def set_selection(self, guids: tuple[str, ...], *, include_all: bool) -> None:
        self._selected = set()
        if self._mode == "custom" and include_all and "__all__" in {d for _n, d in self._entries}:
            self._selected.add("__all__")
        else:
            valid = {d for _n, d in self._entries}
            for g in guids:
                if g in valid:
                    self._selected.add(g)
        self._sync_popup_list_if_visible()
        self._sync_label()

    def _restore_selection_from_snapshot(self, snap: tuple[frozenset[str], bool], valid_datas: set[str]) -> None:
        self._selected = set()
        frozen_sel, inc_all = snap
        if self._mode == "custom" and inc_all and "__all__" in valid_datas:
            self._selected.add("__all__")
        else:
            for g in frozen_sel:
                if g in valid_datas and g != "__all__":
                    self._selected.add(g)

    def _display_for_data(self, data: str) -> str:
        for name, d in self._entries:
            if d == data:
                return name
        return data

    def _ensure_popup(self) -> None:
        if self._popup is not None:
            return
        self._popup = QFrame(None, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self._popup.setObjectName("eqrPickPopup")
        lay = QVBoxLayout(self._popup)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(0)
        self._list_widget = _EqrPickList(self, self._popup)
        self._list_widget.setObjectName("eqrPickList")
        self._list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list_widget.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._list_widget.setMaximumHeight(320)
        self._list_widget.itemChanged.connect(self._on_list_item_changed)
        lay.addWidget(self._list_widget)

    def _populate_list_widget(self) -> None:
        self._ensure_popup()
        assert self._list_widget is not None
        self._updating_list_checks = True
        self._list_widget.blockSignals(True)
        self._list_widget.clear()
        for name, data in self._entries:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, data)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if data in self._selected else Qt.CheckState.Unchecked
            )
            self._list_widget.addItem(item)
        self._list_widget.blockSignals(False)
        self._updating_list_checks = False

    def _sync_popup_list_if_visible(self) -> None:
        if self._popup is None or self._list_widget is None or not self._popup.isVisible():
            return
        self._populate_list_widget()

    def _apply_list_checks_from_selection(self) -> None:
        if self._list_widget is None:
            return
        self._updating_list_checks = True
        try:
            self._list_widget.blockSignals(True)
            for i in range(self._list_widget.count()):
                it = self._list_widget.item(i)
                if it is None:
                    continue
                d = it.data(Qt.ItemDataRole.UserRole)
                if not isinstance(d, str):
                    continue
                it.setCheckState(
                    Qt.CheckState.Checked if d in self._selected else Qt.CheckState.Unchecked
                )
        finally:
            self._list_widget.blockSignals(False)
            self._updating_list_checks = False

    def _on_list_item_changed(self, item: QListWidgetItem) -> None:
        if self._updating_list_checks or item is None:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(data, str):
            return
        checked = item.checkState() == Qt.CheckState.Checked

        if self._mode == "custom" and data == "__all__":
            if checked:
                self._selected = {"__all__"}
            else:
                self._selected.discard("__all__")
        else:
            if checked:
                self._selected.discard("__all__")
                self._selected.add(data)
            else:
                self._selected.discard(data)

        self._apply_list_checks_from_selection()
        self._sync_label()
        self.selectionChanged.emit()

    def _on_clicked_toggle_popup(self) -> None:
        if not self.isEnabled() or not self._entries:
            return
        if self._popup is not None and self._popup.isVisible():
            self._popup.hide()
            return
        self._show_popup()

    def _show_popup(self) -> None:
        self._ensure_popup()
        self._populate_list_widget()
        assert self._popup is not None and self._list_widget is not None
        self._popup.setFixedWidth(self.width())
        self._list_widget.setFixedWidth(self.width() - 8)
        self._popup.adjustSize()
        pos = self.mapToGlobal(self.rect().bottomLeft())
        self._popup.move(pos)
        self._popup.show()
        self._list_widget.setFocus()

    def _sync_label(self) -> None:
        if self._mode == "vanilla":
            if not self._selected:
                self.setText("SELECT EXISTING EQR HERE")
                return
            if len(self._selected) == 1:
                sole = next(iter(self._selected))
                self.setText(self._display_for_data(sole))
                return
            n = len(self._selected)
            self.setText(f"{n} equipment races selected")
            return
        if "__all__" in self._selected:
            self.setText("Use all custom EQR")
            return
        if not self._selected:
            self.setText("SELECT CUSTOM EQR HERE")
            return
        if len(self._selected) == 1:
            sole = next(iter(self._selected))
            self.setText(self._display_for_data(sole))
            return
        n = len(self._selected)
        self.setText(f"{n} custom equipment races selected")


def _lerp_qcolor(a: QColor, b: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(
        int(a.red() + (b.red() - a.red()) * t),
        int(a.green() + (b.green() - a.green()) * t),
        int(a.blue() + (b.blue() - a.blue()) * t),
        int(a.alpha() + (b.alpha() - a.alpha()) * t),
    )


def _scale_alpha_color(c: QColor, factor: float) -> QColor:
    factor = max(0.0, min(1.0, factor))
    out = QColor(c)
    out.setAlpha(int(round(c.alpha() * factor)))
    return out


class NeonPatchButton(QPushButton):
    """PATCH: sweep + short subtle squash–stretch on the label; light temporal smear."""

    _SWEEP_FRAMES = 22
    _SWEEP_STEP_DEG = 360.0 / float(_SWEEP_FRAMES)
    _TEXT_POP_FRAMES = 22
    _TEXT_POP_STEP = 1.0 / float(_TEXT_POP_FRAMES)
    _BLUR_SAMPLES_MAX = 14
    _BLUR_SAMPLES_MIN = 5

    def __init__(
        self,
        text: str,
        parent: QWidget | None = None,
        *,
        muted: bool = False,
        neon_theme: str = "default",
        basement_strip: bool = False,
    ) -> None:
        super().__init__(text, parent)
        self._muted = muted
        self._basement_strip = basement_strip
        self._neon_theme = neon_theme if neon_theme in ("default", "magenta") else "default"
        if self._neon_theme == "magenta" or muted:
            self.setObjectName("patreonButton")
        else:
            self.setObjectName("patchButton")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hover = False
        self._anim_phase = 0.0
        self._text_pop_t: float | None = None
        self._blur_pose_prev: tuple[float, float, float] = (1.0, 1.0, 0.0)
        self._blur_pose_curr: tuple[float, float, float] = (1.0, 1.0, 0.0)
        self._glow: QGraphicsDropShadowEffect | None = None
        self.setGraphicsEffect(None)
        self._hover_anim = QTimer(self)
        # Magenta (Patreon): slower sweep / label pop and slightly slower tick rate.
        if self._neon_theme == "magenta":
            self._hover_anim.setInterval(26)
            _slow_frames = 46
            self._sweep_step_deg = 360.0 / float(_slow_frames)
            self._text_pop_step = 1.0 / float(_slow_frames)
        else:
            self._hover_anim.setInterval(16)
            self._sweep_step_deg = NeonPatchButton._SWEEP_STEP_DEG
            self._text_pop_step = NeonPatchButton._TEXT_POP_STEP
        self._hover_anim.timeout.connect(self._tick_hover_anim)
        self._hover_blend = 0.0
        self._blend_fade_timer = QTimer(self)
        self._blend_fade_timer.setInterval(16)
        self._blend_fade_timer.timeout.connect(self._tick_blend_fade)
        self._blend_elapsed = QElapsedTimer()
        self._blend_fade_start_v = 0.0
        self._blend_fade_end = 0.0
        self._blend_fade_duration_ms = 200
        self._blend_fade_ease_out = True

    def _sync_glow_opacity(self) -> None:
        if self._glow is None:
            return
        opacity = (
            self._hover_blend
            if (self._basement_strip and self._neon_theme == "magenta")
            else 1.0
        )
        setter = getattr(self._glow, "setOpacity", None)
        if callable(setter):
            setter(opacity)

    def _tick_blend_fade(self) -> None:
        if not (self._basement_strip and self._neon_theme == "magenta"):
            self._blend_fade_timer.stop()
            return
        t = min(1.0, self._blend_elapsed.elapsed() / float(max(1, self._blend_fade_duration_ms)))
        if self._blend_fade_ease_out:
            u = 1.0 - (1.0 - t) ** 3
        else:
            u = t * t * t
        self._hover_blend = self._blend_fade_start_v + (self._blend_fade_end - self._blend_fade_start_v) * u
        self._hover_blend = max(0.0, min(1.0, self._hover_blend))
        self._sync_glow_opacity()
        self.update()
        if t >= 1.0:
            self._hover_blend = self._blend_fade_end
            self._blend_fade_timer.stop()
            self._sync_glow_opacity()
            if self._hover_blend <= 0.05:
                self.setGraphicsEffect(None)
                self._glow = None
            self.update()

    def _start_basement_hover_fade(self, *, fade_in: bool) -> None:
        self._blend_fade_timer.stop()
        self._blend_fade_end = 1.0 if fade_in else 0.0
        self._blend_fade_start_v = self._hover_blend
        self._blend_fade_duration_ms = 200 if fade_in else 260
        self._blend_fade_ease_out = fade_in
        self._blend_elapsed.restart()
        self._blend_fade_timer.start()

    def _attach_hover_glow(self) -> None:
        # Must build a new effect each hover: setGraphicsEffect(None) deletes the old one.
        g = QGraphicsDropShadowEffect(self)
        if self._neon_theme == "magenta":
            g.setBlurRadius(30)
            g.setColor(QColor(209, 0, 86, 98))
        elif self._muted:
            g.setBlurRadius(19)
            g.setColor(QColor(155, 72, 195, 76))
        else:
            g.setBlurRadius(26)
            g.setColor(QColor(205, 35, 105, 120))
        g.setOffset(0, 0)
        self._glow = g
        self.setGraphicsEffect(g)
        self._sync_glow_opacity()

    def _tick_hover_anim(self) -> None:
        if not self._hover:
            self._hover_anim.stop()
            if not (self._basement_strip and self._neon_theme == "magenta"):
                self.setGraphicsEffect(None)
                self._glow = None
            return

        self._blur_pose_prev = self._blur_pose_curr

        if self._anim_phase < 360.0:
            self._anim_phase = min(360.0, self._anim_phase + self._sweep_step_deg)

        if self._text_pop_t is not None and self._text_pop_t < 1.0:
            self._text_pop_t = min(1.0, self._text_pop_t + self._text_pop_step)
            if self._text_pop_t >= 1.0:
                self._text_pop_t = None

        if self._text_pop_t is not None:
            self._blur_pose_curr = NeonPatchButton._text_pop_pose(self._text_pop_t)
        else:
            self._blur_pose_curr = (1.0, 1.0, 0.0)

        self.update()

        sweep_done = self._anim_phase >= 360.0
        text_done = self._text_pop_t is None
        if sweep_done and text_done:
            self._hover_anim.stop()
            self._blur_pose_prev = self._blur_pose_curr

    def enterEvent(self, event: QEnterEvent) -> None:
        self._hover = True
        self._anim_phase = 0.0
        self._text_pop_t = 0.0
        self._blur_pose_prev = (1.0, 1.0, 0.0)
        self._blur_pose_curr = NeonPatchButton._text_pop_pose(0.0)
        self._attach_hover_glow()
        if self._basement_strip and self._neon_theme == "magenta":
            self._start_basement_hover_fade(fade_in=True)
        self._hover_anim.start()
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        if self._basement_strip and self._neon_theme == "magenta":
            self._hover = False
            self._hover_anim.stop()
            self._anim_phase = 0.0
            self._text_pop_t = None
            self._blur_pose_prev = (1.0, 1.0, 0.0)
            self._blur_pose_curr = (1.0, 1.0, 0.0)
            self._start_basement_hover_fade(fade_in=False)
            self.update()
            super().leaveEvent(event)
            return
        self._hover = False
        self._hover_anim.stop()
        self._anim_phase = 0.0
        self._text_pop_t = None
        self._blur_pose_prev = (1.0, 1.0, 0.0)
        self._blur_pose_curr = (1.0, 1.0, 0.0)
        self.setGraphicsEffect(None)
        self._glow = None
        self.update()
        super().leaveEvent(event)

    @staticmethod
    def _text_pop_pose(t: float) -> tuple[float, float, float]:
        """Short squash → slight stretch → settle; small vertical motion, no bounce tail."""
        t = max(0.0, min(1.0, t))
        if t >= 1.0:
            return (1.0, 1.0, 0.0)

        def ez5(u: float) -> float:
            u = max(0.0, min(1.0, u))
            return u * u * u * (u * (u * 6.0 - 15.0) + 10.0)

        sx, sy, ty = 1.0, 1.0, 0.0
        if t < 0.36:
            u = ez5(t / 0.36)
            sx = 1.0 + 0.08 * u
            sy = 1.0 - 0.10 * u
            ty = 0.6 * u
        elif t < 0.58:
            u = ez5((t - 0.36) / 0.22)
            sx = 1.08 - 0.08 * u
            sy = 0.90 + 0.10 * u
            ty = 0.6 - 3.2 * u
        else:
            u = ez5((t - 0.58) / 0.42)
            sx, sy = 1.0, 1.0
            ty = -2.6 + 2.6 * u
        return (sx, sy, ty)

    @staticmethod
    def _pose_motion_metric(prev: tuple[float, float, float], curr: tuple[float, float, float]) -> float:
        psx, psy, pty = prev
        csx, csy, cty = curr
        return abs(csx - psx) * 18.0 + abs(csy - psy) * 18.0 + abs(cty - pty) * 1.35

    def _paint_pop_label_motion_blur(
        self,
        painter: QPainter,
        tr: QRect,
        base: QColor,
        label: str,
        *,
        heavy: bool,
    ) -> None:
        prev = self._blur_pose_prev
        curr = self._blur_pose_curr
        motion = NeonPatchButton._pose_motion_metric(prev, curr)
        nmax = NeonPatchButton._BLUR_SAMPLES_MAX
        nmin = NeonPatchButton._BLUR_SAMPLES_MIN
        if heavy:
            n = max(8, min(nmax, int(6.0 + motion * 0.65)))
        elif motion < 0.035:
            n = max(nmin, min(nmax, 8))
        else:
            n = max(nmin, min(nmax, int(5.0 + motion * 0.55)))

        cx = float(tr.center().x())
        cy = float(tr.center().y())

        for k in range(n):
            u = k / max(1, n - 1)
            sx = prev[0] + (curr[0] - prev[0]) * u
            sy = prev[1] + (curr[1] - prev[1]) * u
            ty = prev[2] + (curr[2] - prev[2]) * u
            a = int(8 + 247 * math.pow(u, 0.38))
            a = min(255, max(6, a))
            c = QColor(base)
            c.setAlpha(a)
            painter.setPen(c)
            painter.save()
            painter.translate(cx, cy + ty)
            painter.scale(sx, sy)
            painter.translate(-cx, -cy)
            painter.drawText(tr, int(Qt.AlignmentFlag.AlignCenter), label)
            painter.restore()

    def _fill_c(self, r: int, g: int, b: int) -> QColor:
        if not self._muted or self._neon_theme == "magenta":
            return QColor(r, g, b)
        return QColor(int(r * 0.91), int(g * 0.91), int(b * 0.91))

    def _neon_c(self, r: int, g: int, b: int, a: int = 255) -> QColor:
        if not self._muted or self._neon_theme == "magenta":
            return QColor(r, g, b, a)
        return QColor(int(r * 0.66), int(g * 0.66), int(b * 0.66), int(a * 0.76))

    def paintEvent(self, event: QPaintEvent) -> None:
        del event  # fully custom
        is_mag = self._neon_theme == "magenta"
        down = self.isDown()
        if self._basement_strip and is_mag and not down:
            t_h = self._hover_blend
        elif self._hover and not down:
            t_h = 1.0
        else:
            t_h = 0.0
        active = (t_h > 0.001) and (not down)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self._basement_strip:
            inset = 0
            r = self.rect()
            rf = QRectF(r)
            radius = 0.0
        else:
            inset = 1
            r = self.rect().adjusted(inset, inset, -inset, -inset)
            rf = QRectF(r)
            radius = 7.0
        path = QPainterPath()
        path.addRoundedRect(rf, radius, radius)

        # Dark interior
        fill = QLinearGradient(rf.topLeft(), rf.bottomRight())
        if is_mag:
            if self.isDown():
                fill.setColorAt(0.0, QColor(16, 7, 12))
                fill.setColorAt(1.0, QColor(22, 10, 14))
            elif active:
                if self._basement_strip:
                    fill.setColorAt(0.0, _lerp_qcolor(QColor(9, 8, 11), QColor(52, 12, 34), t_h))
                    fill.setColorAt(0.5, _lerp_qcolor(QColor(7, 6, 9), QColor(38, 8, 26), t_h))
                    fill.setColorAt(1.0, _lerp_qcolor(QColor(11, 9, 12), QColor(58, 14, 38), t_h))
                else:
                    fill.setColorAt(0.0, QColor(52, 12, 34))
                    fill.setColorAt(0.5, QColor(38, 8, 26))
                    fill.setColorAt(1.0, QColor(58, 14, 38))
            else:
                fill.setColorAt(0.0, QColor(9, 8, 11))
                fill.setColorAt(0.5, QColor(7, 6, 9))
                fill.setColorAt(1.0, QColor(11, 9, 12))
        elif active:
            fill.setColorAt(0.0, self._fill_c(46, 12, 32))
            fill.setColorAt(0.5, self._fill_c(32, 8, 24))
            fill.setColorAt(1.0, self._fill_c(52, 14, 36))
        else:
            fill.setColorAt(0.0, self._fill_c(18, 9, 14))
            fill.setColorAt(0.5, self._fill_c(12, 6, 11))
            fill.setColorAt(1.0, self._fill_c(22, 10, 16))
        if not is_mag and self.isDown():
            fill.setColorAt(0.0, self._fill_c(12, 6, 9))
            fill.setColorAt(1.0, self._fill_c(16, 8, 11))
        painter.fillPath(path, fill)

        if active:
            # Fixed soft halo (no breathing)
            halo = (
                QColor(209, 0, 86, int(52 * t_h))
                if is_mag
                else QColor(198, 20, 88, int(44 * t_h))
            )
            painter.strokePath(path, QPen(halo, 4.0))

            # One-shot diagonal sweep while phase runs 0 → 360°
            if self._anim_phase < 359.99:
                painter.save()
                painter.setClipPath(path)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)
                t = min(1.0, self._anim_phase / 360.0)
                band_len = max(52.0, rf.width() * 0.55)
                travel = rf.width() + band_len * 1.65
                base_x = rf.left() - band_len * 0.28 + t * travel
                tilt = math.radians(28)
                dx = band_len * math.cos(tilt)
                dy = band_len * math.sin(tilt)
                mid_y = rf.center().y() + (t - 0.5) * rf.height() * 0.12
                x0, y0 = base_x, mid_y - dy * 0.5
                x1, y1 = base_x + dx, mid_y + dy * 0.5
                sh = QLinearGradient(x0, y0, x1, y1)
                swe_alpha = t_h if (self._basement_strip and is_mag) else 1.0
                if is_mag:
                    sh.setColorAt(0.0, _scale_alpha_color(QColor(25, 0, 18, 0), swe_alpha))
                    sh.setColorAt(0.12, _scale_alpha_color(QColor(139, 0, 75, 38), swe_alpha))
                    sh.setColorAt(0.28, _scale_alpha_color(QColor(209, 0, 86, 95), swe_alpha))
                    sh.setColorAt(0.46, _scale_alpha_color(QColor(255, 55, 65, 130), swe_alpha))
                    sh.setColorAt(0.52, _scale_alpha_color(QColor(220, 70, 120, 155), swe_alpha))
                    sh.setColorAt(0.62, _scale_alpha_color(QColor(165, 235, 242, 72), swe_alpha))
                    sh.setColorAt(0.78, _scale_alpha_color(QColor(180, 0, 72, 85), swe_alpha))
                    sh.setColorAt(1.0, _scale_alpha_color(QColor(40, 0, 28, 0), swe_alpha))
                else:
                    sh.setColorAt(0.0, _scale_alpha_color(QColor(25, 0, 18, 0), swe_alpha))
                    sh.setColorAt(0.12, _scale_alpha_color(QColor(139, 0, 75, 38), swe_alpha))
                    sh.setColorAt(0.28, _scale_alpha_color(QColor(209, 0, 86, 95), swe_alpha))
                    sh.setColorAt(0.46, _scale_alpha_color(QColor(255, 55, 65, 130), swe_alpha))
                    sh.setColorAt(0.52, _scale_alpha_color(QColor(220, 70, 120, 155), swe_alpha))
                    sh.setColorAt(0.62, _scale_alpha_color(QColor(165, 235, 242, 72), swe_alpha))
                    sh.setColorAt(0.78, _scale_alpha_color(QColor(180, 0, 72, 85), swe_alpha))
                    sh.setColorAt(1.0, _scale_alpha_color(QColor(40, 0, 28, 0), swe_alpha))
                painter.fillPath(path, QBrush(sh))
                painter.restore()

        # Conic neon rim - angle follows the same one-shot phase while hovered
        cx, cy = rf.center().x(), rf.center().y()
        spin = min(360.0, self._anim_phase) if active else 0.0
        cg = QConicalGradient(cx, cy, spin)

        if is_mag:
            if self.isDown():
                cg.setColorAt(0.0, QColor(72, 22, 44))
                cg.setColorAt(0.5, QColor(48, 14, 30))
                cg.setColorAt(1.0, QColor(82, 28, 48))
            elif active:
                idle_c = QColor(22, 18, 24)

                def rim(c: QColor) -> QColor:
                    return _lerp_qcolor(idle_c, c, t_h) if self._basement_strip else c

                cg.setColorAt(0.0, rim(QColor(209, 0, 86)))
                cg.setColorAt(0.17, rim(QColor(110, 0, 58)))
                cg.setColorAt(0.36, rim(QColor(255, 49, 49)))
                cg.setColorAt(0.54, rim(QColor(165, 242, 243)))
                cg.setColorAt(0.71, rim(QColor(139, 0, 75)))
                cg.setColorAt(1.0, rim(QColor(209, 0, 86)))
            else:
                cg.setColorAt(0.0, QColor(22, 18, 24))
                cg.setColorAt(1.0, QColor(22, 18, 24))
        elif active:
            cg.setColorAt(0.0, self._neon_c(209, 0, 86))
            cg.setColorAt(0.17, self._neon_c(110, 0, 58))
            cg.setColorAt(0.36, self._neon_c(255, 49, 49))
            cg.setColorAt(0.54, self._neon_c(165, 242, 243))
            cg.setColorAt(0.71, self._neon_c(139, 0, 75))
            cg.setColorAt(1.0, self._neon_c(209, 0, 86))
        else:
            cg.setColorAt(0.0, self._neon_c(58, 12, 34))
            cg.setColorAt(0.24, self._neon_c(38, 8, 24))
            cg.setColorAt(0.5, self._neon_c(72, 16, 40))
            cg.setColorAt(0.76, self._neon_c(48, 10, 28))
            cg.setColorAt(1.0, self._neon_c(58, 12, 34))
        if self._basement_strip and is_mag:
            w = 2.2 + (3.05 - 2.2) * t_h
        else:
            w = 3.05 if self._hover else 2.2
        if self.isDown():
            w *= 0.82
        if self._muted and not is_mag:
            w *= 0.9
        if is_mag and not active and not self.isDown():
            painter.strokePath(path, QPen(QColor(44, 32, 48, 58), 1.05))
        elif is_mag and self.isDown():
            painter.strokePath(path, QPen(QBrush(cg), max(1.85, w * 0.74)))
        else:
            painter.strokePath(path, QPen(QBrush(cg), w))

        # Inner trace - steady when hovered (no sine wobble)
        inner_adj = 1.2 if self._basement_strip else 2.4
        irf = rf.adjusted(inner_adj, inner_adj, -inner_adj, -inner_adj)
        ir = max(1.0, radius - 2.2) if not self._basement_strip else 0.0
        inner = QPainterPath()
        inner.addRoundedRect(irf, ir, ir)
        if self._basement_strip and is_mag:
            a = int(78 + (118 - 78) * t_h)
        else:
            a = 118 if self._hover else 78
        if self.isDown():
            a = int(a * 0.72)
        if is_mag and not active and not self.isDown():
            inner_col = QColor(42, 36, 46, 22)
        elif is_mag:
            if active and not self.isDown():
                inner_col = QColor(255, 105, 95, a)
            else:
                inner_col = QColor(105, 52, 65, int(a * 0.88))
        else:
            if active:
                inner_col = self._neon_c(255, 118, 125, a)
            else:
                inner_col = self._neon_c(72, 28, 42, int(a * 0.42))
        painter.strokePath(inner, QPen(inner_col, 1.12))

        # Label - fixed metrics; temporal motion blur while the pop runs (+ one settle smear)
        if self._muted and not is_mag:
            tc = QColor(212, 206, 222) if self._hover else QColor(188, 180, 202)
            if self.isDown():
                tc = QColor(168, 162, 182)
        elif is_mag:
            if not active and not self.isDown():
                tc = QColor(74, 66, 80)
            elif active and not self.isDown():
                tc = (
                    _lerp_qcolor(QColor(74, 66, 80), QColor(255, 245, 247), t_h)
                    if self._basement_strip
                    else QColor(255, 245, 247)
                )
            else:
                tc = QColor(190, 155, 165)
        else:
            tc = QColor(255, 244, 247) if self._hover else QColor(178, 168, 178)
            if self.isDown():
                tc = QColor(228, 198, 208)
        f = self.font()
        f.setWeight(QFont.Weight.Black)
        if self._muted and not is_mag:
            px, sp = 14, 1.35
        elif is_mag:
            px, sp = 15, 1.22
        else:
            px, sp = 16, 1.5
        f.setPixelSize(px)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, sp)
        painter.setFont(f)
        tr = self.rect()
        motion_m = NeonPatchButton._pose_motion_metric(self._blur_pose_prev, self._blur_pose_curr)
        use_blur = active and (self._text_pop_t is not None or motion_m > 0.028)
        if use_blur:
            self._paint_pop_label_motion_blur(
                painter, tr, tc, self.text(), heavy=self._text_pop_t is not None
            )
        else:
            painter.setPen(tc)
            painter.drawText(tr, int(Qt.AlignmentFlag.AlignCenter), self.text())
        painter.end()


class _MainScrollHost(QWidget):
    """Scroll area plus optional full-width bottom strip; modal overlay covers both."""

    def __init__(self, scroll: QScrollArea, basement: QWidget | None = None) -> None:
        super().__init__()
        self._scroll = scroll
        self._basement = basement
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(scroll, 1)
        if basement is not None:
            root.addWidget(basement, 0)
        self.overlay = PatchLoadingOverlay(self)
        self.overlay.hide()
        self.overlay.raise_()

    def resizeEvent(self, event: QResizeEvent) -> None:
        self.overlay.setGeometry(self.rect())
        super().resizeEvent(event)


class PatchLoadingOverlay(QWidget):
    """Dimmed full-area veil, blurred content behind (see MainWindow), neon card + smooth progress fill."""

    _FINISH_LERP = 0.22

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._elapsed_ms = 0
        self._prog = 0.0
        self._aim_cap = 0.88
        self._completing = False
        self._sheen = 0.0
        self._finish_cb: object | None = None
        self._panel_rect = QRectF()
        self._tick = QTimer(self)
        self._tick.setInterval(16)
        self._tick.timeout.connect(self._on_tick)

    def begin(self) -> None:
        self._elapsed_ms = 0
        self._prog = 0.0
        self._aim_cap = 0.88
        self._completing = False
        self._sheen = 0.0
        self._finish_cb = None
        self._tick.start()
        self.show()
        self.raise_()
        self.update()

    def request_finish(self, callback: object) -> None:
        """Ease progress to 100% then run ``callback`` (no arguments)."""
        self._completing = True
        self._finish_cb = callback

    def shutdown(self) -> None:
        self._tick.stop()
        self._finish_cb = None
        self._completing = False
        self._prog = 0.0
        self.hide()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        w = min(440.0, max(300.0, self.width() - 48.0))
        h = 118.0
        x = (self.width() - w) / 2.0
        y = (self.height() - h) / 2.0
        self._panel_rect = QRectF(x, y, w, h)

    def _on_tick(self) -> None:
        self._elapsed_ms += self._tick.interval()
        self._sheen = (self._sheen + 0.055) % (math.pi * 2.0)

        if self._completing:
            self._prog += (1.0 - self._prog) * PatchLoadingOverlay._FINISH_LERP
            if self._prog >= 0.998:
                self._prog = 1.0
                self._tick.stop()
                cb = self._finish_cb
                self._finish_cb = None
                self._completing = False
                if callable(cb):
                    cb()
        else:
            t = self._elapsed_ms / 1000.0
            self._aim_cap = min(0.88, 0.14 + t * 0.11)
            self._prog += (self._aim_cap - self._prog) * 0.045

        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(12, 6, 10, 172))

        rf = self._panel_rect
        if rf.width() < 8 or rf.height() < 8:
            painter.end()
            return

        radius = 8.0
        path = QPainterPath()
        path.addRoundedRect(rf, radius, radius)

        fill = QLinearGradient(rf.topLeft(), rf.bottomRight())
        fill.setColorAt(0.0, QColor(44, 10, 30))
        fill.setColorAt(0.5, QColor(28, 8, 22))
        fill.setColorAt(1.0, QColor(52, 14, 36))
        painter.fillPath(path, fill)

        cx, cy = rf.center().x(), rf.center().y()
        cg = QConicalGradient(cx, cy, (self._sheen * 180.0 / math.pi) % 360.0)
        cg.setColorAt(0.0, QColor(209, 0, 86))
        cg.setColorAt(0.17, QColor(110, 0, 58))
        cg.setColorAt(0.36, QColor(255, 49, 49))
        cg.setColorAt(0.54, QColor(165, 242, 243))
        cg.setColorAt(0.71, QColor(139, 0, 75))
        cg.setColorAt(1.0, QColor(209, 0, 86))
        painter.strokePath(path, QPen(QBrush(cg), 2.85))

        irf = rf.adjusted(3.2, 3.2, -3.2, -3.2)
        ir = max(1.0, radius - 2.4)
        inner = QPainterPath()
        inner.addRoundedRect(irf, ir, ir)
        painter.strokePath(inner, QPen(QColor(255, 115, 125, 100), 1.05))

        margin_x = 22.0
        margin_top = 16.0
        title_y = rf.top() + margin_top
        f = self.font()
        f.setWeight(QFont.Weight.Black)
        f.setPixelSize(14)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.5)
        painter.setFont(f)
        painter.setPen(QColor(255, 244, 246))
        title_r = QRectF(rf.left() + margin_x, title_y, rf.width() - 2 * margin_x, 22)
        painter.drawText(title_r, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), "PATCHING…")

        f2 = QFont(self.font())
        f2.setWeight(QFont.Weight.Normal)
        f2.setPixelSize(11)
        f2.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.3)
        painter.setFont(f2)
        painter.setPen(QColor(195, 165, 178))
        sub_r = QRectF(rf.left() + margin_x, title_y + 20, rf.width() - 2 * margin_x, 18)
        painter.drawText(sub_r, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), "Merging mods - please wait")

        bar_margin = 18.0
        bar_y = rf.bottom() - bar_margin - 22.0
        bar_w = rf.width() - 2 * bar_margin
        bar_x = rf.left() + bar_margin
        bar_h = 20.0
        bar_rf = QRectF(bar_x, bar_y, bar_w, bar_h)
        br = 6.0
        track = QPainterPath()
        track.addRoundedRect(bar_rf, br, br)
        painter.fillPath(track, QColor(8, 4, 8))

        pw = max(0.0, min(1.0, self._prog)) * bar_rf.width()
        if pw > 1.2:
            painter.save()
            painter.setClipPath(track)
            prog_rf = QRectF(bar_rf.left(), bar_rf.top(), pw, bar_rf.height())
            prog_path = QPainterPath()
            prog_path.addRoundedRect(prog_rf, br, br)
            pg = QLinearGradient(prog_rf.left(), prog_rf.center().y(), prog_rf.right(), prog_rf.center().y())
            sh = 0.5 + 0.5 * math.sin(self._sheen)
            pg.setColorAt(0.0, QColor(95, 0, 52, 220))
            pg.setColorAt(0.18 + 0.06 * sh, QColor(175, 0, 88, 235))
            pg.setColorAt(0.42, QColor(235, 35, 95, 245))
            pg.setColorAt(0.62, QColor(255, 110, 120, 238))
            pg.setColorAt(0.78 - 0.05 * sh, QColor(165, 232, 240, 130))
            pg.setColorAt(1.0, QColor(200, 0, 95, 225))
            painter.fillPath(prog_path, pg)

            sweep_w = max(48.0, bar_rf.width() * 0.38)
            travel = bar_rf.width() + sweep_w
            u = (self._sheen * 0.31) % 1.0
            sx = bar_rf.left() - sweep_w * 0.35 + u * travel
            tilt = math.radians(24)
            dx = sweep_w * math.cos(tilt)
            dy = sweep_w * math.sin(tilt)
            mid_y = bar_rf.center().y()
            x0, y0 = sx, mid_y - dy * 0.5
            x1, y1 = sx + dx, mid_y + dy * 0.5
            sh2 = QLinearGradient(x0, y0, x1, y1)
            sh2.setColorAt(0.0, QColor(255, 255, 255, 0))
            sh2.setColorAt(0.45, QColor(255, 255, 255, 0))
            sh2.setColorAt(0.52, QColor(255, 220, 235, 118))
            sh2.setColorAt(0.58, QColor(255, 255, 255, 0))
            sh2.setColorAt(1.0, QColor(255, 180, 210, 0))
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)
            painter.fillPath(prog_path, QBrush(sh2))
            painter.restore()

        painter.strokePath(track, QPen(QColor(209, 0, 86, 62), 1.0))
        painter.end()


class _PatchRunner(QObject):
    """Runs ``run_patch`` on a ``QThread``; emits a ``(tag, data)`` payload then quits the thread."""

    finished = Signal(object)

    def __init__(self, config: PatchConfig) -> None:
        super().__init__()
        self._config = config

    def run(self) -> None:
        try:
            report = run_patch(self._config)
            payload: object = ("ok", report)
        except PatchValidationError as exc:
            payload = ("validation", exc)
        except Exception as exc:  # noqa: BLE001
            payload = ("error", exc)
        # Do not call thread.quit() here: emitting then quitting immediately can let
        # thread.finished (runner.deleteLater) run before the queued finished-slot on
        # the main thread, so the UI never unlocks. Quit is connected after the UI slot.
        self.finished.emit(payload)


class RaceRow(QWidget):
    """One mapping row: equipment races (multi-pick) + mod folder (line edit) + browse."""

    def __init__(self, mode: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.mode = mode
        self.remove_btn = QPushButton()
        self.remove_btn.setObjectName("smallRowBtn")
        _setup_small_row_btn(self.remove_btn, "−")
        self.remove_btn.setToolTip("Remove row")

        self.race_combo = EqrMultiPickButton(mode)
        self.race_combo.setMinimumHeight(36)
        self.race_combo.setMaximumWidth(276)
        self.race_combo.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.path_edit = QLineEdit()
        self.path_edit.setMinimumHeight(36)
        self.path_edit.setMaximumWidth(414)
        self.path_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.path_edit.setPlaceholderText("select path to unpacked mod folder here")

        self.browse_button = QPushButton("…")
        self.browse_button.setObjectName("iconButton")
        self.browse_button.setToolTip("Browse mod folder")
        self.browse_button.setFixedSize(_SMALL_ROW_BTN_SIDE, _SMALL_ROW_BTN_SIDE)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(8)
        layout.addWidget(self.remove_btn, 0)
        layout.addWidget(self.race_combo, 1)
        layout.addWidget(self.path_edit, 2)
        layout.addWidget(self.browse_button, 0)

    def source_path(self) -> Path | None:
        text = self.path_edit.text().strip()
        return Path(text) if text else None


class PriorityRow(QWidget):
    """Single merge-order entry: remove, index, grip, path display, reorder."""

    def __init__(self, main: MainWindow, path: Path, display_label: str | None = None) -> None:
        super().__init__(main.priority_rows_container)
        self.setObjectName("priorityMergeRow")
        self._main = main
        self.path = path
        self._drag_press_global: QPoint | None = None
        self._drag_hotspot: QPoint | None = None
        self.setAcceptDrops(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._drop_line_top = QFrame()
        self._drop_line_top.setFixedHeight(2)
        self._drop_line_top.setStyleSheet("background-color: #c8c8c8; border: none;")
        self._drop_line_top.hide()
        root.addWidget(self._drop_line_top)

        self._row_surface = QWidget()
        row = QHBoxLayout(self._row_surface)
        row.setContentsMargins(0, 3, 0, 3)
        row.setSpacing(8)

        self.remove_btn = QPushButton()
        self.remove_btn.setObjectName("smallRowBtn")
        _setup_small_row_btn(self.remove_btn, "−")
        self.remove_btn.setToolTip("Remove from merge order")
        self.remove_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.remove_btn.clicked.connect(lambda: self._main._remove_priority_row(self))

        self.index_label = QLabel("1")
        self.index_label.setFixedWidth(22)
        self.index_label.setAlignment(Qt.AlignCenter)
        self.index_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.index_label.setStyleSheet("color: #b0b0b0; font-weight: bold;")

        self.grip_label = QLabel("≡")
        self.grip_label.setFixedWidth(24)
        self.grip_label.setAlignment(Qt.AlignCenter)
        self.grip_label.setToolTip("Drag row onto another row to reorder (lower in list wins)")
        self.grip_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.grip_label.setStyleSheet("color: #888888; font-size: 16px;")

        self.path_edit = QLineEdit(display_label or source_label(path))
        self.path_edit.setReadOnly(True)
        self.path_edit.setToolTip(str(path))
        self.path_edit.setMinimumHeight(36)
        self.path_edit.setMinimumWidth(280)
        self.path_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        row.addWidget(self.remove_btn, 0)
        row.addWidget(self.index_label, 0)
        row.addWidget(self.grip_label, 0)
        row.addWidget(self.path_edit, 1)
        self._row_surface.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        root.addWidget(self._row_surface)

        self._drop_line_bottom = QFrame()
        self._drop_line_bottom.setFixedHeight(2)
        self._drop_line_bottom.setStyleSheet("background-color: #c8c8c8; border: none;")
        self._drop_line_bottom.hide()
        root.addWidget(self._drop_line_bottom)

        for w in (self.index_label, self.grip_label, self.path_edit):
            w.installEventFilter(self)

    def _apply_drag_source_outline(self, active: bool) -> None:
        """Highlight the row slot left behind while a merge-order drag is in progress."""
        if active:
            self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            self.setStyleSheet(
                "#priorityMergeRow { border: 2px solid #c8c8c8; border-radius: 6px; background-color: #161616; }"
            )
        else:
            self.setStyleSheet("")
            self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

    def clear_drop_indicator(self) -> None:
        self._drop_line_top.hide()
        self._drop_line_bottom.hide()

    def show_drop_indicator(self, insert_before: bool) -> None:
        self._drop_line_top.setVisible(insert_before)
        self._drop_line_bottom.setVisible(not insert_before)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: ARG002
        if event.type() == QEvent.Type.MouseButtonPress:
            me = event
            if isinstance(me, QMouseEvent) and me.button() == Qt.MouseButton.LeftButton:
                self._drag_press_global = me.globalPosition().toPoint()
                if isinstance(watched, QWidget):
                    local = QPoint(int(me.position().x()), int(me.position().y()))
                    self._drag_hotspot = watched.mapTo(self._row_surface, local)
                else:
                    self._drag_hotspot = QPoint(0, 0)
                self.grabMouse()
                return True
        return False

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_press_global is not None and event.buttons() & Qt.MouseButton.LeftButton:
            dist = (event.globalPosition().toPoint() - self._drag_press_global).manhattanLength()
            if dist >= QApplication.startDragDistance():
                self.releaseMouse()
                self._drag_press_global = None
                self._start_row_drag()
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if QWidget.mouseGrabber() is self:
                self.releaseMouse()
            self._drag_press_global = None
            self._drag_hotspot = None
        super().mouseReleaseEvent(event)

    def _start_row_drag(self) -> None:
        try:
            idx = self._main.priority_row_widgets.index(self)
        except ValueError:
            self._drag_hotspot = None
            return
        self._main._clear_priority_drop_indicators()
        mime = QMimeData()
        mime.setData(_PRIORITY_ROW_MIME, str(idx).encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        pix = self._row_surface.grab()
        if not pix.isNull():
            drag.setPixmap(pix)
            hs = self._drag_hotspot if self._drag_hotspot is not None else QPoint(0, 0)
            hx = max(0, min(hs.x(), pix.width() - 1))
            hy = max(0, min(hs.y(), pix.height() - 1))
            drag.setHotSpot(QPoint(hx, hy))
        self._drag_hotspot = None
        self._apply_drag_source_outline(True)
        try:
            drag.exec(Qt.DropAction.MoveAction)
        finally:
            self._apply_drag_source_outline(False)
            self._main._clear_priority_drop_indicators()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasFormat(_PRIORITY_ROW_MIME):
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if event.mimeData().hasFormat(_PRIORITY_ROW_MIME):
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
            insert_before = float(event.position().y()) < self.height() / 2
            self._main._set_priority_drop_indicator(self, insert_before)
            return
        super().dragMoveEvent(event)

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self._main._clear_priority_drop_indicators()
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        if not event.mimeData().hasFormat(_PRIORITY_ROW_MIME):
            super().dropEvent(event)
            return
        self._main._clear_priority_drop_indicators()
        raw = event.mimeData().data(_PRIORITY_ROW_MIME)
        try:
            source_idx = int(bytes(raw).decode("utf-8"))
        except (TypeError, ValueError):
            event.ignore()
            return
        pos_y = float(event.position().y())
        insert_before = pos_y < self.height() / 2
        self._main._move_priority_row_drop(source_idx, self, insert_before)
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("BG3 ARMOR PATCHER")
        self.resize(820, 819)
        self.vanilla_rows: list[RaceRow] = []
        self.custom_rows: list[RaceRow] = []
        self.priority_row_widgets: list[PriorityRow] = []

        self._vanilla_path_debounce = QTimer(self)
        self._vanilla_path_debounce.setSingleShot(True)
        self._vanilla_path_debounce.setInterval(400)
        self._vanilla_path_debounce.timeout.connect(self._debounced_refresh_vanilla_eqr_combos)
        self._merge_order_debounce = QTimer(self)
        self._merge_order_debounce.setSingleShot(True)
        self._merge_order_debounce.setInterval(350)
        self._merge_order_debounce.timeout.connect(self._sync_merge_order_from_assignment_rows)
        self._custom_scan_debounce = QTimer(self)
        self._custom_scan_debounce.setSingleShot(True)
        self._custom_scan_debounce.setInterval(450)
        self._custom_scan_debounce.timeout.connect(self._debounced_custom_row_scan)
        self._pending_custom_scan_row: RaceRow | None = None
        self._vanilla_scan_details_expanded = False
        self._patch_name = "GeneratedPatch"
        self._patch_thread: QThread | None = None
        self._patch_runner: _PatchRunner | None = None
        self._patch_btn: NeonPatchButton | None = None

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        self._scroll_content = content
        self._scroll_content.setMaximumWidth(800)
        outer = QVBoxLayout(content)
        outer.setContentsMargins(16, 16, 16, 20)
        outer.setSpacing(0)

        title = QLabel("BG3 ARMOR PATCHER")
        title.setObjectName("appTitle")
        outer.addWidget(title)
        outer.addSpacing(16)

        self._build_vanilla_section(outer)
        outer.addSpacing(20)
        self._build_vanilla_race_section(outer)
        outer.addSpacing(20)
        self._build_custom_race_section(outer)
        outer.addSpacing(20)
        self._build_priority_section(outer)
        outer.addSpacing(20)
        self._build_patch_button(outer)
        outer.addSpacing(20)
        self._build_presets_section(outer)
        outer.addStretch(1)

        scroll.setWidget(content)
        self._scroll = scroll

        self._basement_bar = QWidget()
        self._basement_bar.setObjectName("basementBar")
        basement_lay = QVBoxLayout(self._basement_bar)
        basement_lay.setContentsMargins(0, 0, 0, 0)
        basement_lay.setSpacing(0)
        self._madness_btn = NeonPatchButton(
            "SUPPORT THE MADNESS",
            neon_theme="magenta",
            basement_strip=True,
        )
        self._madness_btn.setMinimumHeight(52)
        self._madness_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._madness_btn.setToolTip(f"Patreon — support the madness\n{_PATREON_PAGE_URL}")
        self._madness_btn.clicked.connect(self._open_patreon_page)
        basement_lay.addWidget(self._madness_btn, 0)

        self._content_host = _MainScrollHost(scroll, self._basement_bar)
        self._patch_overlay = self._content_host.overlay
        self.setCentralWidget(self._content_host)

    def _build_vanilla_section(self, outer: QVBoxLayout) -> None:
        _vanilla_path_prereq_tip = (
            "You need to unpack game files with Baldur's Gate 3 Modder's Multitool first\n"
            "Root Template files should be converted from LSF to LSX with LSLib Toolkit"
        )
        h = QLabel("Vanilla Path")
        h.setObjectName("sectionTitle")
        outer.addWidget(h)

        path_prereq_hint = QLabel(_vanilla_path_prereq_tip)
        path_prereq_hint.setObjectName("hint")
        path_prereq_hint.setWordWrap(True)
        outer.addWidget(path_prereq_hint)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.vanilla_path_edit = QLineEdit()
        self.vanilla_path_edit.setPlaceholderText(
            "Select the path to unpacked Vanilla folders (UnpackedData)"
        )
        self.vanilla_path_edit.setFixedHeight(40)
        self.vanilla_path_edit.editingFinished.connect(self._on_vanilla_path_changed)
        self.vanilla_path_edit.textChanged.connect(self._schedule_vanilla_eqr_combo_refresh)
        browse = QPushButton("Browse")
        browse.setObjectName("pathRowBrowseBtn")
        browse.setMinimumWidth(90)
        browse.setFixedHeight(40)
        browse.clicked.connect(self._browse_vanilla_path)
        self.open_vanilla_eqr_btn = QPushButton("Open EQR")
        self.open_vanilla_eqr_btn.setObjectName("pathRowBrowseBtn")
        self.open_vanilla_eqr_btn.setMinimumWidth(90)
        self.open_vanilla_eqr_btn.setFixedHeight(40)
        self.open_vanilla_eqr_btn.setEnabled(False)
        self.open_vanilla_eqr_btn.setToolTip("Opens the resolved vanilla EquipmentRaces.lsx (after path is recognized)")
        self.open_vanilla_eqr_btn.clicked.connect(self._open_resolved_vanilla_eqr)
        row.addWidget(self.vanilla_path_edit, 1)
        row.addWidget(browse, 0)
        row.addWidget(self.open_vanilla_eqr_btn, 0)
        outer.addLayout(row)
        self.vanilla_path_hint = QLabel()
        self.vanilla_path_hint.setObjectName("hint")
        self.vanilla_path_hint.setWordWrap(True)
        self.vanilla_path_hint.hide()
        outer.addWidget(self.vanilla_path_hint)

        self.vanilla_scan_outer = QWidget()
        self.vanilla_scan_outer.setObjectName("vanillaScanDetailsBlock")
        block_layout = QVBoxLayout(self.vanilla_scan_outer)
        block_layout.setContentsMargins(0, 0, 0, 0)
        block_layout.setSpacing(4)

        self.vanilla_scan_toggle = QToolButton()
        self.vanilla_scan_toggle.setObjectName("vanillaScanToggle")
        self.vanilla_scan_toggle.setCheckable(True)
        self.vanilla_scan_toggle.setChecked(False)
        self.vanilla_scan_toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.vanilla_scan_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.vanilla_scan_toggle.setText("EQR parse details")
        self.vanilla_scan_toggle.setAutoRaise(True)
        self.vanilla_scan_toggle.toggled.connect(self._on_vanilla_scan_toggle)
        block_layout.addWidget(self.vanilla_scan_toggle, 0)

        self.vanilla_scan_debug_frame = QFrame()
        self.vanilla_scan_debug_frame.setObjectName("vanillaScanDebugPanel")
        panel_layout = QVBoxLayout(self.vanilla_scan_debug_frame)
        panel_layout.setContentsMargins(8, 6, 8, 8)
        panel_layout.setSpacing(0)

        self.vanilla_eqr_scan_wrap = QWidget()
        self.vanilla_eqr_scan_wrap.setObjectName("vanillaScanSummaryWrap")
        self.vanilla_eqr_scan_wrap.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        wrap_layout = QVBoxLayout(self.vanilla_eqr_scan_wrap)
        wrap_layout.setContentsMargins(0, 0, 0, 0)
        wrap_layout.setSpacing(0)
        self.vanilla_eqr_scan_label = QLabel()
        self.vanilla_eqr_scan_label.setObjectName("vanillaScanSummary")
        self.vanilla_eqr_scan_label.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.vanilla_eqr_scan_label.setWordWrap(True)
        wrap_layout.addWidget(self.vanilla_eqr_scan_label)
        panel_layout.addWidget(self.vanilla_eqr_scan_wrap)

        block_layout.addWidget(self.vanilla_scan_debug_frame)
        self.vanilla_scan_debug_frame.hide()

        self.vanilla_scan_outer.hide()
        outer.addWidget(self.vanilla_scan_outer)

    def _on_vanilla_scan_toggle(self, checked: bool) -> None:
        self._vanilla_scan_details_expanded = checked
        self.vanilla_scan_toggle.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
        self.vanilla_scan_debug_frame.setVisible(checked)

    def _hide_vanilla_scan_debug_panel(self) -> None:
        self.vanilla_scan_outer.hide()
        self.vanilla_eqr_scan_label.clear()
        self.vanilla_scan_debug_frame.hide()
        self.vanilla_scan_toggle.blockSignals(True)
        self.vanilla_scan_toggle.setChecked(False)
        self.vanilla_scan_toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.vanilla_scan_toggle.blockSignals(False)

    def _show_vanilla_scan_debug_panel(self) -> None:
        self.vanilla_scan_outer.show()
        self.vanilla_scan_toggle.blockSignals(True)
        self.vanilla_scan_toggle.setChecked(self._vanilla_scan_details_expanded)
        self.vanilla_scan_toggle.setArrowType(
            Qt.ArrowType.DownArrow if self._vanilla_scan_details_expanded else Qt.ArrowType.RightArrow
        )
        self.vanilla_scan_toggle.blockSignals(False)
        self.vanilla_scan_debug_frame.setVisible(self._vanilla_scan_details_expanded)

    def _update_vanilla_eqr_scan_summary(
        self,
        vanilla_path: Path | None,
        *,
        load_error: str | None = None,
    ) -> None:
        """Parse result in a collapsible black panel (toggle with arrow)."""
        if vanilla_path is None or not str(vanilla_path).strip():
            self._hide_vanilla_scan_debug_panel()
            return

        resolved = resolve_vanilla_equipment_races_path(vanilla_path)
        if resolved is None:
            self._hide_vanilla_scan_debug_panel()
            return

        if load_error is not None:
            self.vanilla_eqr_scan_label.setText(f"EquipmentRaces.lsx - read error:\n{resolved}\n\n{load_error}")
            self._show_vanilla_scan_debug_panel()
            return

        try:
            root = lsx.load_root(resolved)
            races = lsx.extract_equipment_races(root, "Vanilla", vanilla_path)
        except Exception as exc:  # noqa: BLE001
            self.vanilla_eqr_scan_label.setText(f"EquipmentRaces.lsx - read error:\n{resolved}\n\n{exc}")
            self._show_vanilla_scan_debug_panel()
            return

        names = [r.name for r in sorted(races, key=lambda item: item.name.lower())]
        if not names:
            self.vanilla_eqr_scan_label.setText(
                f"EquipmentRaces.lsx - loaded file:\n{resolved}\n\n"
                "Parsed 0 equipment races (no Name + GUID pairs found). "
                "If this file has races, send a snippet of one <node id=\"EquipmentRace\"> block."
            )
            self._show_vanilla_scan_debug_panel()
            return

        max_lines = 120
        lines = [
            f"EquipmentRaces.lsx - loaded:\n{resolved}",
            f"Parsed {len(names)} races (dropdown uses these Name → GUID):",
            "",
        ]
        lines.extend(names[:max_lines])
        if len(names) > max_lines:
            lines.append(f"… +{len(names) - max_lines} more not shown.")
        self.vanilla_eqr_scan_label.setText("\n".join(lines))
        self._show_vanilla_scan_debug_panel()

    def _sync_vanilla_eqr_aux_ui(self, vanilla_path: Path | None) -> None:
        """Hint text + Open EQR button state."""
        self._update_vanilla_path_hint(vanilla_path)
        resolved = resolve_vanilla_equipment_races_path(vanilla_path) if vanilla_path else None
        self.open_vanilla_eqr_btn.setEnabled(resolved is not None)
        self.open_vanilla_eqr_btn.setToolTip(
            f"Open resolved file:\n{resolved}" if resolved else "Resolve EquipmentRaces.lsx first (see hint below)"
        )
        self._update_vanilla_eqr_scan_summary(vanilla_path)

    def _open_resolved_vanilla_eqr(self) -> None:
        vanilla_path = self._vanilla_path()
        if vanilla_path is None:
            return
        resolved = resolve_vanilla_equipment_races_path(vanilla_path)
        if resolved is None:
            self._error("Could not resolve vanilla EquipmentRaces.lsx from the current Vanilla Path.")
            return
        url = QUrl.fromLocalFile(str(resolved.resolve()))
        if not QDesktopServices.openUrl(url):
            self._error(f"Could not open:\n{resolved}")

    def _open_patreon_page(self) -> None:
        url = QUrl(_PATREON_PAGE_URL)
        if not url.isValid():
            self._error("Patreon link is not configured.")
            return
        if not QDesktopServices.openUrl(url):
            self._error(f"Could not open:\n{_PATREON_PAGE_URL}")

    def _update_vanilla_path_hint(self, vanilla_path: Path | None) -> None:
        """Explain empty vanilla EQR dropdown (wrong folder type or missing game data)."""
        if vanilla_path is None or not str(vanilla_path).strip():
            self.vanilla_path_hint.hide()
            self.vanilla_path_hint.setText("")
            return
        try:
            exists = vanilla_path.exists()
        except OSError:
            exists = False
        if not exists:
            self.vanilla_path_hint.show()
            self.vanilla_path_hint.setText("Vanilla Path does not exist.")
            return
        resolved = resolve_vanilla_equipment_races_path(vanilla_path)
        if resolved is not None:
            self.vanilla_path_hint.hide()
            self.vanilla_path_hint.setText("")
            return
        rel = str(VANILLA_EQUIPMENT_RACES).replace("\\", "/")
        self.vanilla_path_hint.show()
        if not vanilla_path.is_dir() and not vanilla_path.is_file():
            self.vanilla_path_hint.setText("Vanilla Path must be a file or folder.")
            return
        if vanilla_path.is_file():
            self.vanilla_path_hint.setText(
                "This file is not EquipmentRaces.lsx. "
                f"Expected name {VANILLA_EQUIPMENT_RACES_FILENAME!r}, or use UnpackedData / EquipmentSettings folder."
            )
            return
        if mod_equipment_race_files(vanilla_path):
            self.vanilla_path_hint.setText(
                "This folder looks like an unpacked mod (it has Mods/…/EquipmentSettings/EquipmentRaces.lsx). "
                "Vanilla Path must be the unpacked BG3 Data directory that contains "
                f"{rel}. Put this folder in the Mod column of a vanilla row, not in Vanilla Path."
            )
            return
        self.vanilla_path_hint.setText(
            "No vanilla EquipmentRaces.lsx found. Tried:\n"
            + format_vanilla_equipment_races_search_hint(vanilla_path)
            + "\n\nTip: you can paste the folder …\\EquipmentSettings or the full path to EquipmentRaces.lsx."
        )

    def _build_vanilla_race_section(self, outer: QVBoxLayout) -> None:
        _vanilla_eqr_tip = "Unpacked mods with Vanilla equipment races"
        h = QLabel("Vanilla EQR")
        h.setObjectName("sectionTitle")
        h.setToolTip(_vanilla_eqr_tip)
        outer.addWidget(h)

        hint = QLabel(
            f"{_vanilla_eqr_tip}. Races from the list + mod folder per row"
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        hint.setToolTip(_vanilla_eqr_tip)
        outer.addWidget(hint)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        self.vanilla_rows_layout = QVBoxLayout()
        grid.addLayout(self.vanilla_rows_layout, 0, 0, 1, 2)
        outer.addLayout(grid)

        add_row = QHBoxLayout()
        add_row.setSpacing(8)
        add_plus = QPushButton()
        add_plus.setObjectName("smallRowBtn")
        _setup_small_row_btn(add_plus, "+")
        add_plus.setToolTip("Add vanilla EQR mapping row")
        add_plus.clicked.connect(self._add_vanilla_row)
        add_label = QLabel("Pick one or more EQR from the list (click to toggle), then choose mod folder")
        add_label.setObjectName("hint")
        add_row.addWidget(add_plus, 0)
        add_row.addWidget(add_label, 1)
        outer.addLayout(add_row)

    def _build_custom_race_section(self, outer: QVBoxLayout) -> None:
        h = QLabel("Custom EQR")
        h.setObjectName("sectionTitle")
        outer.addWidget(h)

        hint = QLabel(
            "Unpacked mods with custom equipment races. Scans the mod’s EquipmentRaces file. "
            "Pick one, multiple, or “Use all custom EQR”"
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        outer.addWidget(hint)

        self.custom_rows_layout = QVBoxLayout()
        outer.addLayout(self.custom_rows_layout)

        add_row = QHBoxLayout()
        add_row.setSpacing(8)
        add_plus = QPushButton()
        add_plus.setObjectName("smallRowBtn")
        _setup_small_row_btn(add_plus, "+")
        add_plus.setToolTip("Add mod with custom equipment race")
        add_plus.clicked.connect(self._add_custom_row)
        add_label = QLabel("Select mod folder, then pick custom EQR (toggle several, or “Use all custom EQR”)")
        add_label.setObjectName("hint")
        add_row.addWidget(add_plus, 0)
        add_row.addWidget(add_label, 1)
        outer.addLayout(add_row)

    def _build_priority_section(self, outer: QVBoxLayout) -> None:
        h = QLabel("Merge Order")
        h.setObjectName("sectionTitle")
        outer.addWidget(h)

        hint = QLabel(
            "Lower in the list = higher priority (wins over rows above). "
            "Vanilla path and each mod folder from Vanilla / Custom EQR rows are added here automatically "
            "(paste paths or browse). Drag rows or use Up / Down-drop on another row’s top/bottom half to insert."
        )
        hint.setObjectName("hint")
        outer.addWidget(hint)

        self.priority_rows_container = QWidget()
        self.priority_rows_layout = QVBoxLayout(self.priority_rows_container)
        self.priority_rows_layout.setContentsMargins(0, 4, 0, 4)
        self.priority_rows_layout.setSpacing(0)
        outer.addWidget(self.priority_rows_container)

        add_pri = QHBoxLayout()
        add_pri.setSpacing(8)
        add_btn = QPushButton()
        add_btn.setObjectName("smallRowBtn")
        _setup_small_row_btn(add_btn, "+")
        add_btn.setToolTip("Add folder to merge order")
        add_btn.clicked.connect(self._add_priority_row_dialog)
        add_pri.addWidget(add_btn, 0)
        merge_add_label = QLabel("Add unpacked mod or folder to merge list")
        merge_add_label.setObjectName("hint")
        add_pri.addWidget(merge_add_label, 1)
        outer.addLayout(add_pri)

    def _build_patch_button(self, outer: QVBoxLayout) -> None:
        h = QLabel("Patch Folder")
        h.setObjectName("sectionTitle")
        outer.addWidget(h)

        row = QHBoxLayout()
        row.setSpacing(10)
        row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.patch_folder_edit = QLineEdit()
        self.patch_folder_edit.setPlaceholderText("Select path for Patch")
        self.patch_folder_edit.setText("")
        self.patch_folder_edit.setFixedHeight(40)
        self.patch_folder_edit.setToolTip(
            "Picked preset name = the mod folder name in the patch\n\n"
            "If you don't use a preset, the default name is PatchPresetName\n\n"
            "The merged mod is written under this folder (preset .json files live in presets/ next to the app)"
        )
        self.patch_folder_edit.editingFinished.connect(self._refresh_preset_combo)

        browse_patch_dir = QPushButton("…")
        browse_patch_dir.setObjectName("iconButton")
        browse_patch_dir.setFixedSize(40, 40)
        browse_patch_dir.setToolTip("Choose working folder for patch output (not where presets are stored)")
        browse_patch_dir.clicked.connect(self._browse_patch_job_folder)

        patch = NeonPatchButton("PATCH")
        patch.setFixedWidth(172)
        patch.setFixedHeight(40)
        patch.setMinimumHeight(40)
        patch.clicked.connect(self._patch)
        self._patch_btn = patch

        row.addWidget(self.patch_folder_edit, 1, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(browse_patch_dir, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(patch, 0, Qt.AlignmentFlag.AlignVCenter)
        outer.addLayout(row)

    def _build_presets_section(self, outer: QVBoxLayout) -> None:
        h = QLabel("Presets")
        h.setObjectName("sectionTitle")
        outer.addWidget(h)

        hint = QLabel(
            "Picked preset name = the mod folder name in the patch. "
            "If you don't use a preset, the default name is PatchPresetName"
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        outer.addWidget(hint)

        preset_row = QHBoxLayout()
        preset_row.setSpacing(10)
        self.rename_preset_btn = QPushButton("Rename")
        self.rename_preset_btn.setObjectName("pathRowBrowseBtn")
        self.rename_preset_btn.setFixedHeight(40)
        self.rename_preset_btn.setMinimumWidth(76)
        self.rename_preset_btn.setToolTip("Rename the selected preset file on disk")
        self.rename_preset_btn.clicked.connect(self._rename_selected_preset)

        self.preset_combo = TriangleComboBox()
        self.preset_combo.setEditable(False)
        self.preset_combo.setFixedHeight(40)
        self.preset_combo.setToolTip(
            "Picked preset name = the mod folder name in the patch\n\n"
            "If you don't use a preset, the default name is PatchPresetName"
        )
        self.preset_combo.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.preset_combo.customContextMenuRequested.connect(self._on_preset_combo_context_menu)
        self.preset_combo.activated.connect(self._on_preset_activated)
        self.preset_combo.currentIndexChanged.connect(self._sync_rename_preset_button)
        self._preset_rename_shortcut = QShortcut(QKeySequence(Qt.Key.Key_F2), self.preset_combo)
        self._preset_rename_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._preset_rename_shortcut.activated.connect(self._rename_selected_preset)

        save_preset_btn = QPushButton()
        save_preset_btn.setObjectName("iconButton")
        _style_preset_save_button(save_preset_btn)
        save_preset_btn.setToolTip(
            "Save preset: overwrites the selected JSON, or asks for a name if “- choose preset -” or “+ New preset…” is selected"
        )
        save_preset_btn.clicked.connect(self._save_preset_named)

        preset_row.addWidget(self.rename_preset_btn, 0)
        preset_row.addWidget(self.preset_combo, 1)
        preset_row.addWidget(save_preset_btn, 0)
        outer.addLayout(preset_row)

        self._refresh_preset_combo()
        self._sync_rename_preset_button()

    def _sync_rename_preset_button(self, _index: int = -1) -> None:
        path = self._preset_combo_selected_preset_path()
        self.rename_preset_btn.setEnabled(
            path is not None and path.is_file() and not _preset_is_bundled(path)
        )

    def _refresh_preset_combo(self) -> None:
        prev_data = self.preset_combo.currentData()
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        self.preset_combo.addItem("- choose preset -", None)
        self.preset_combo.addItem("+ New preset…", _PRESET_COMBO_NEW_MARKER)
        by_stem: dict[str, Path] = {}
        bundle = _resource_bundle_dir()
        if bundle is not None:
            bundled = bundle / "presets"
            if bundled.is_dir():
                for path in sorted(bundled.glob("*.json")):
                    by_stem[path.stem] = path
        presets_dir = self._presets_dir()
        if presets_dir.exists():
            for path in sorted(presets_dir.glob("*.json")):
                by_stem[path.stem] = path
        for _stem, path in sorted(by_stem.items(), key=lambda kv: kv[0].casefold()):
            self.preset_combo.addItem(path.stem, str(path))
        self.preset_combo.blockSignals(False)
        if prev_data:
            idx = self.preset_combo.findData(prev_data)
            if idx >= 0:
                self.preset_combo.setCurrentIndex(idx)
                self._sync_rename_preset_button()
                return
        stem = self._patch_name.strip()
        if stem:
            idx = self.preset_combo.findText(stem)
            if idx >= 0:
                self.preset_combo.setCurrentIndex(idx)
                self._sync_rename_preset_button()
                return
        self.preset_combo.setCurrentIndex(0)
        self._sync_rename_preset_button()

    def _preset_combo_selected_preset_path(self) -> Path | None:
        idx = self.preset_combo.currentIndex()
        if idx <= 0:
            return None
        raw = self.preset_combo.itemData(idx)
        if raw is None or raw == _PRESET_COMBO_NEW_MARKER:
            return None
        return Path(str(raw))

    def _on_preset_activated(self, index: int) -> None:
        if index <= 0:
            return
        data = self.preset_combo.itemData(index)
        if data == _PRESET_COMBO_NEW_MARKER:
            path = self._prompt_new_preset_path()
            if path is None:
                self.preset_combo.blockSignals(True)
                self.preset_combo.setCurrentIndex(0)
                self.preset_combo.blockSignals(False)
                return
            self._save_preset_to_disk(path)
            return
        path_str = data
        if not path_str:
            return
        p = Path(str(path_str))
        if p.is_file():
            try:
                config = load_preset(p)
                self._apply_config(config)
                self._patch_name = p.stem
            except Exception as exc:  # noqa: BLE001
                self._error(f"Could not load preset:\n{exc}")

    def _prompt_new_preset_path(self) -> Path | None:
        name, ok = QInputDialog.getText(
            self,
            "BG3 ARMOR PATCHER",
            "New preset name:",
            text=self._patch_name,
        )
        if not ok:
            return None
        name = name.strip()
        if not name:
            self._error("Enter a preset name.")
            return None
        safe = _safe_preset_stem(name)
        if not safe:
            self._error("Invalid preset name.")
            return None
        path = self._presets_dir() / f"{safe}.json"
        if _preset_stem_exists_on_disk(safe, self._presets_dir()):
            self._error(f"A preset already exists:\n{path}")
            return None
        return path

    def _save_preset_to_disk(self, path: Path) -> bool:
        target = path
        if _preset_is_bundled(path):
            target = self._presets_dir() / path.name
            target.parent.mkdir(parents=True, exist_ok=True)
        try:
            save_preset(
                self._build_config(
                    preset_path_for_folder_name=target,
                    preset_save_path_for_output_dir_fallback=target,
                ),
                target,
            )
        except PatchValidationError as exc:
            self._error("Cannot save:\n\n" + "\n".join(f"- {m}" for m in exc.messages))
            return False
        except Exception as exc:  # noqa: BLE001
            self._error(str(exc))
            return False
        self._refresh_preset_combo()
        sel = self.preset_combo.findData(str(target))
        if sel >= 0:
            self.preset_combo.setCurrentIndex(sel)
        _AppMessageDialog(self, headline="Preset saved", body=str(target)).exec()
        return True

    def _save_preset_named(self) -> None:
        path = self._preset_combo_selected_preset_path()
        if path is None:
            path = self._prompt_new_preset_path()
            if path is None:
                return
        self._save_preset_to_disk(path)

    def _on_preset_combo_context_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        path = self._preset_combo_selected_preset_path()
        rename_act = menu.addAction("Rename preset…")
        rename_act.setEnabled(
            path is not None and path.is_file() and not _preset_is_bundled(path)
        )
        chosen = menu.exec(self.preset_combo.mapToGlobal(pos))
        if chosen == rename_act:
            self._rename_selected_preset()

    def _rename_selected_preset(self) -> None:
        old_path = self._preset_combo_selected_preset_path()
        if old_path is None or not old_path.is_file():
            self._error(
                "Select a preset file in the list (not “- choose preset -” or “+ New preset…”). "
                "Then press F2 or use Rename in the right-click menu."
            )
            return
        if _preset_is_bundled(old_path):
            self._error(
                "Built-in presets cannot be renamed. Save a copy with Save (writes next to the app) "
                "or use “+ New preset…”."
            )
            return
        old_stem = old_path.stem
        new_name, ok = QInputDialog.getText(
            self,
            "BG3 ARMOR PATCHER",
            "Rename preset (file on disk):",
            text=old_stem,
        )
        if not ok:
            return
        safe = _safe_preset_stem(new_name)
        if not safe:
            self._error("Invalid preset name.")
            return
        new_path = old_path.with_name(f"{safe}.json")
        if new_path == old_path:
            return
        if new_path.exists():
            self._error(f"A preset file already exists:\n{new_path}")
            return
        if safe != old_stem and _preset_stem_exists_on_disk(safe, self._presets_dir()):
            self._error(f"A preset named “{safe}” already exists (built-in or on disk).")
            return
        try:
            old_path.rename(new_path)
        except OSError as exc:
            self._error(f"Could not rename preset:\n{exc}")
            return
        if self._patch_name == old_stem:
            self._patch_name = safe
        self._refresh_preset_combo()
        sel = self.preset_combo.findData(str(new_path))
        if sel >= 0:
            self.preset_combo.setCurrentIndex(sel)

    def _schedule_vanilla_eqr_combo_refresh(self) -> None:
        """Repoll EquipmentRaces while typing/pasting path so dropdown updates without pressing Enter."""
        self._vanilla_path_debounce.start()

    def _debounced_refresh_vanilla_eqr_combos(self) -> None:
        vanilla_path = self._vanilla_path()
        self._sync_vanilla_eqr_aux_ui(vanilla_path)
        self._sync_merge_order_from_assignment_rows()
        for row in self.vanilla_rows:
            self._fill_vanilla_combo(row.race_combo)

    def _sync_merge_order_from_assignment_rows(self) -> None:
        """Append merge-order rows for vanilla + every mod folder used in Vanilla / Custom EQR rows.

        Existing merge rows are left as-is (no removal, no reorder); only missing paths are appended.
        """
        vanilla_path = self._vanilla_path()
        if vanilla_path is not None and str(vanilla_path).strip():
            try:
                if vanilla_path.exists():
                    self._add_priority_path(vanilla_path, "Vanilla folder path")
            except OSError:
                pass

        for row in self.vanilla_rows:
            p = row.source_path()
            if p is None or not str(p).strip():
                continue
            try:
                self._add_priority_path(p)
            except OSError:
                continue

        for row in self.custom_rows:
            p = row.source_path()
            if p is None or not str(p).strip():
                continue
            try:
                self._add_priority_path(p)
            except OSError:
                continue

    def _connect_row_path_merge_sync(self, row: RaceRow) -> None:
        row.path_edit.editingFinished.connect(self._sync_merge_order_from_assignment_rows)
        row.path_edit.textChanged.connect(lambda _t: self._merge_order_debounce.start())
        if row.mode == "custom":
            row.path_edit.textChanged.connect(lambda _t, r=row: self._sync_custom_row_race_combo_ui(r))
            row.path_edit.textChanged.connect(lambda _t, r=row: self._schedule_custom_row_scan(r))
            row.path_edit.editingFinished.connect(lambda r=row: self._flush_custom_row_scan(r))

    def _schedule_custom_row_scan(self, row: RaceRow) -> None:
        if row not in self.custom_rows:
            return
        self._pending_custom_scan_row = row
        self._custom_scan_debounce.start()

    def _debounced_custom_row_scan(self) -> None:
        row = self._pending_custom_scan_row
        self._pending_custom_scan_row = None
        self._run_custom_row_scan_if_ready(row)

    def _flush_custom_row_scan(self, row: RaceRow) -> None:
        self._custom_scan_debounce.stop()
        if self._pending_custom_scan_row is row:
            self._pending_custom_scan_row = None
        self._run_custom_row_scan_if_ready(row)

    def _custom_row_path_is_valid_dir(self, row: RaceRow) -> bool:
        path = row.source_path()
        if path is None or not str(path).strip():
            return False
        try:
            return path.is_dir()
        except OSError:
            return False

    def _sync_custom_row_race_combo_ui(self, row: RaceRow) -> None:
        """Disable (gray) custom EQR picker until a valid mod folder path is set and races are loaded."""
        if row.mode != "custom" or row not in self.custom_rows:
            return
        pick = row.race_combo
        valid_dir = self._custom_row_path_is_valid_dir(row)
        if not valid_dir:
            pick.set_invalid_path_custom()
            return
        if not pick.has_entries():
            pick.setEnabled(False)
            pick.refresh_summary()
            return
        pick.setEnabled(True)

    def _run_custom_row_scan_if_ready(self, row: RaceRow | None) -> None:
        if row is None or row not in self.custom_rows:
            return
        path = row.source_path()
        if path is None or not str(path).strip():
            self._sync_custom_row_race_combo_ui(row)
            return
        try:
            if not path.is_dir():
                self._sync_custom_row_race_combo_ui(row)
                return
        except OSError:
            self._sync_custom_row_race_combo_ui(row)
            return
        try:
            self._scan_custom_row(row)
        except Exception:  # noqa: BLE001
            pass
        self._sync_custom_row_race_combo_ui(row)

    def _browse_vanilla_path(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self, "Select UnpackedData folder", self.vanilla_path_edit.text() or str(Path.cwd())
        )
        if selected:
            self.vanilla_path_edit.setText(selected)
            self._on_vanilla_path_changed()

    def _on_vanilla_path_changed(self) -> None:
        vanilla_path = self._vanilla_path()
        self._sync_vanilla_eqr_aux_ui(vanilla_path)
        self._sync_merge_order_from_assignment_rows()
        if vanilla_path is None:
            for row in self.vanilla_rows:
                self._fill_vanilla_combo(row.race_combo)
            return
        for row in self.vanilla_rows:
            self._fill_vanilla_combo(row.race_combo)

    def _add_vanilla_row(self) -> None:
        row = RaceRow("vanilla")
        row.remove_btn.clicked.connect(lambda checked=False, r=row: self._remove_vanilla_row(r))
        row.browse_button.clicked.connect(lambda checked=False, r=row: self._browse_mod_for_row(r))
        self._connect_row_path_merge_sync(row)
        self._fill_vanilla_combo(row.race_combo)
        self.vanilla_rows.append(row)
        self.vanilla_rows_layout.addWidget(row)

    def _remove_vanilla_row(self, row: RaceRow) -> None:
        if row in self.vanilla_rows:
            self.vanilla_rows.remove(row)
            row.deleteLater()

    def _add_custom_row(self) -> None:
        row = RaceRow("custom")
        row.remove_btn.clicked.connect(lambda checked=False, r=row: self._remove_custom_row(r))
        row.browse_button.clicked.connect(lambda checked=False, r=row: self._browse_mod_for_row(r))
        self._connect_row_path_merge_sync(row)
        self.custom_rows.append(row)
        self.custom_rows_layout.addWidget(row)
        self._sync_custom_row_race_combo_ui(row)

    def _remove_custom_row(self, row: RaceRow) -> None:
        if row in self.custom_rows:
            self.custom_rows.remove(row)
            row.deleteLater()

    def _browse_folder(self, target: QLineEdit) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Select folder", target.text() or str(Path.cwd()))
        if selected:
            target.setText(selected)

    def _browse_mod_for_row(self, row: RaceRow) -> None:
        self._browse_folder(row.path_edit)
        self._sync_merge_order_from_assignment_rows()
        if row.mode == "custom":
            self._custom_scan_debounce.stop()
            self._pending_custom_scan_row = None
            self._run_custom_row_scan_if_ready(row)

    def _fill_vanilla_combo(self, pick: EqrMultiPickButton) -> None:
        prev = pick.snapshot_selection()
        vanilla_path = self._vanilla_path()
        if vanilla_path is None:
            pick.set_entries([], preserve=None)
            pick.setEnabled(True)
            return
        races_path = resolve_vanilla_equipment_races_path(vanilla_path)
        if races_path is None:
            pick.set_entries([], preserve=None)
            pick.setEnabled(True)
            return
        try:
            races = lsx.extract_equipment_races(lsx.load_root(races_path), "Vanilla", vanilla_path)
        except Exception as exc:  # noqa: BLE001
            pick.set_entries([], preserve=None)
            pick.setEnabled(True)
            self._update_vanilla_eqr_scan_summary(vanilla_path, load_error=str(exc))
            return
        entries = [(race.name, race.guid) for race in sorted(races, key=lambda item: item.name.lower())]
        pick.set_entries(entries, preserve=prev)
        pick.setEnabled(True)

    def _scan_custom_row(self, row: RaceRow) -> None:
        path = row.source_path()
        if path is None:
            self._sync_custom_row_race_combo_ui(row)
            return
        prev = row.race_combo.snapshot_selection()
        pick = row.race_combo
        entries: list[tuple[str, str]] = [("Use all custom EQR", "__all__")]
        for race_file in mod_equipment_race_files(path):
            races = lsx.extract_equipment_races(lsx.load_root(race_file), source_label(path), path)
            for race in sorted(races, key=lambda item: item.name.lower()):
                entries.append((race.name, race.guid))
        pick.set_entries(entries, preserve=prev)
        self._sync_custom_row_race_combo_ui(row)

    def _patch(self) -> None:
        """Worker thread + animated overlay (same look as before); guarded against overlapping runs."""
        th = self._patch_thread
        if th is not None and th.isRunning():
            return
        btn = self._patch_btn
        if btn is not None:
            btn.setEnabled(False)

        self._patch_overlay.shutdown()
        self._scroll.setGraphicsEffect(None)
        try:
            config = self._build_config()
        except PatchValidationError as exc:
            if btn is not None:
                btn.setEnabled(True)
            self._error("Validation failed:\n\n" + "\n".join(f"- {message}" for message in exc.messages))
            return

        # Fresh blur each run: setGraphicsEffect(None) destroys the previous effect (Qt ownership).
        blur = QGraphicsBlurEffect(self._scroll)
        blur.setBlurRadius(18)
        self._scroll.setGraphicsEffect(blur)
        self._patch_overlay.begin()

        thread = QThread()
        runner = _PatchRunner(config)
        runner.moveToThread(thread)
        thread.started.connect(runner.run)
        # Order matters: main-thread UI handler must run before quit/deleteLater chain.
        runner.finished.connect(self._on_patch_worker_finished)
        runner.finished.connect(thread.quit, Qt.ConnectionType.QueuedConnection)
        thread.finished.connect(runner.deleteLater)
        thread.finished.connect(lambda finished=thread: self._on_patch_thread_finished(finished))
        thread.finished.connect(thread.deleteLater)

        self._patch_thread = thread
        self._patch_runner = runner
        thread.start()

    def _on_patch_thread_finished(self, finished: QThread) -> None:
        """Clear handles only for this ``QThread`` (avoids a stale ``finished`` wiping a newer run)."""
        if self._patch_thread is finished:
            self._patch_thread = None
            self._patch_runner = None

    def _on_patch_worker_finished(self, payload: object) -> None:
        self._patch_overlay.request_finish(
            lambda p=payload: QTimer.singleShot(0, lambda: self._apply_patch_result(p))
        )

    def _apply_patch_result(self, payload: object) -> None:
        self._scroll.setGraphicsEffect(None)
        self._patch_overlay.shutdown()
        btn = self._patch_btn
        try:
            if not isinstance(payload, tuple) or len(payload) != 2:
                self._error("Patch finished with an unexpected result.")
                return
            tag, data = payload[0], payload[1]
            if tag == "ok":
                report = data
                _AppMessageDialog(
                    self,
                    headline="Patch complete",
                    body=f"Written files: {len(report.written_files)}\nWarnings: {len(report.warnings)}",
                ).exec()
            elif tag == "validation":
                if isinstance(data, PatchValidationError):
                    self._error(
                        "Validation failed:\n\n" + "\n".join(f"- {message}" for message in data.messages)
                    )
                else:
                    self._error("Validation failed.")
            elif tag == "error":
                self._error(str(data))
            else:
                self._error("Patch finished with an unexpected result.")
        finally:
            if btn is not None:
                btn.setEnabled(True)

    def _patch_output_folder_name(self, preset_path_for_folder_name: Path | None = None) -> str:
        """BG3 mod folder name under Public/… and Mods/… (matches selected preset .json stem if any)."""
        path = (
            preset_path_for_folder_name
            if preset_path_for_folder_name is not None
            else self._preset_combo_selected_preset_path()
        )
        if path is not None:
            stem = path.stem.strip()
            if stem:
                return stem
        return "PatchPresetName"

    def _build_config(
        self,
        preset_path_for_folder_name: Path | None = None,
        *,
        preset_save_path_for_output_dir_fallback: Path | None = None,
    ) -> PatchConfig:
        vanilla_path = self._vanilla_path()
        if vanilla_path is None:
            raise PatchValidationError(["Vanilla path is required."])

        mod_paths: list[Path] = []
        assignments: list[RaceAssignment] = []

        for row in self.vanilla_rows:
            mod_path = row.source_path()
            guids = row.race_combo.selected_ordered()
            if mod_path and guids:
                mod_paths.append(mod_path)
                assignments.append(
                    RaceAssignment(
                        source_label=source_label(mod_path),
                        source_path=mod_path,
                        race_guids=guids,
                        use_vanilla_races=True,
                    )
                )

        for row in self.custom_rows:
            mod_path = row.source_path()
            if not mod_path:
                continue
            pick = row.race_combo
            if pick.include_all_custom():
                mod_paths.append(mod_path)
                assignments.append(
                    RaceAssignment(
                        source_label=source_label(mod_path),
                        source_path=mod_path,
                        race_guids=(),
                        include_all=True,
                    )
                )
                continue
            guids = pick.selected_ordered()
            if not guids:
                continue
            mod_paths.append(mod_path)
            assignments.append(
                RaceAssignment(
                    source_label=source_label(mod_path),
                    source_path=mod_path,
                    race_guids=guids,
                    include_all=False,
                )
            )

        output_dir = self._resolved_patch_output_dir(preset_save_path_for_output_dir_fallback)
        if output_dir is None:
            raise PatchValidationError(["Select a patch output folder (Patch folder field)."])

        return PatchConfig(
            vanilla_path=vanilla_path,
            output_dir=output_dir,
            patch_name=self._patch_output_folder_name(preset_path_for_folder_name),
            mod_paths=_unique_paths(mod_paths),
            priority_order=self._priority_paths(),
            race_assignments=assignments,
        )

    def _clear_assignment_rows(self) -> None:
        for row in list(self.vanilla_rows):
            self._remove_vanilla_row(row)
        for row in list(self.custom_rows):
            self._remove_custom_row(row)

    def _restore_assignment_rows_from_config(self, config: PatchConfig) -> None:
        """Rebuild Vanilla EQR / Custom EQR rows from ``race_assignments`` (preset round-trip)."""
        self._clear_assignment_rows()
        for assignment in config.race_assignments:
            if assignment.use_vanilla_races:
                self._add_vanilla_row()
                row = self.vanilla_rows[-1]
                row.path_edit.blockSignals(True)
                row.path_edit.setText(str(assignment.source_path))
                row.path_edit.blockSignals(False)
                self._fill_vanilla_combo(row.race_combo)
                row.race_combo.set_selection(assignment.race_guids, include_all=False)
            else:
                self._add_custom_row()
                row = self.custom_rows[-1]
                row.path_edit.blockSignals(True)
                row.path_edit.setText(str(assignment.source_path))
                row.path_edit.blockSignals(False)
                self._run_custom_row_scan_if_ready(row)
                if assignment.include_all:
                    row.race_combo.set_selection((), include_all=True)
                else:
                    row.race_combo.set_selection(assignment.race_guids, include_all=False)

    def _apply_config(self, config: PatchConfig) -> None:
        self.vanilla_path_edit.setText(str(config.vanilla_path))
        self.patch_folder_edit.blockSignals(True)
        self.patch_folder_edit.setText(str(config.output_dir))
        self.patch_folder_edit.blockSignals(False)
        self._patch_name = config.patch_name
        self._clear_priority_rows()
        for path in config.priority_order:
            self._add_priority_path(path, "Vanilla folder path" if path == config.vanilla_path else None)
        self._restore_assignment_rows_from_config(config)
        self._on_vanilla_path_changed()
        self._refresh_preset_combo()

    def _clear_priority_rows(self) -> None:
        for w in list(self.priority_row_widgets):
            self._remove_priority_row(w, skip_renumber=False)
        self.priority_row_widgets.clear()
        self._renumber_priority_rows()

    def _add_priority_path(self, path: Path, label: str | None = None) -> None:
        resolved = path.resolve()
        for w in self.priority_row_widgets:
            if w.path.resolve() == resolved:
                return
        row = PriorityRow(self, path, label)
        self.priority_row_widgets.append(row)
        self.priority_rows_layout.addWidget(row)
        self._renumber_priority_rows()

    def _add_priority_row_dialog(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Add to merge order", str(Path.cwd()))
        if selected:
            self._add_priority_path(Path(selected))

    def _remove_priority_row(self, widget: PriorityRow, skip_renumber: bool = False) -> None:
        if widget in self.priority_row_widgets:
            self.priority_row_widgets.remove(widget)
            self.priority_rows_layout.removeWidget(widget)
            widget.deleteLater()
            if not skip_renumber:
                self._renumber_priority_rows()

    def _clear_priority_drop_indicators(self) -> None:
        for w in self.priority_row_widgets:
            w.clear_drop_indicator()

    def _set_priority_drop_indicator(self, target: PriorityRow, insert_before: bool) -> None:
        for w in self.priority_row_widgets:
            if w is target:
                w.show_drop_indicator(insert_before)
            else:
                w.clear_drop_indicator()

    def _move_priority_row_drop(self, source_idx: int, target: PriorityRow, insert_before: bool) -> None:
        self._clear_priority_drop_indicators()
        widgets = self.priority_row_widgets
        if not (0 <= source_idx < len(widgets)):
            return
        source = widgets[source_idx]
        if source is target:
            return
        try:
            widgets.index(target)
        except ValueError:
            return
        widgets.pop(source_idx)
        target_idx = widgets.index(target)
        insert_at = target_idx if insert_before else target_idx + 1
        insert_at = max(0, min(insert_at, len(widgets)))
        widgets.insert(insert_at, source)
        self._sync_priority_layout_from_list()
        self._renumber_priority_rows()

    def _sync_priority_layout_from_list(self) -> None:
        for w in self.priority_row_widgets:
            self.priority_rows_layout.removeWidget(w)
        for w in self.priority_row_widgets:
            self.priority_rows_layout.addWidget(w)

    def _renumber_priority_rows(self) -> None:
        for i, w in enumerate(self.priority_row_widgets, start=1):
            w.index_label.setText(str(i))

    def _priority_paths(self) -> list[Path]:
        return [w.path for w in self.priority_row_widgets]

    def _vanilla_path(self) -> Path | None:
        text = self.vanilla_path_edit.text().strip()
        return Path(text) if text else None

    def _patch_job_dir(self) -> Path | None:
        text = self.patch_folder_edit.text().strip()
        if not text:
            return None
        return Path(text).expanduser().resolve()

    def _resolved_patch_output_dir(self, preset_save_path_for_fallback: Path | None) -> Path | None:
        """Patch folder from the UI, or when saving over an existing preset, the file’s stored output_dir."""
        direct = self._patch_job_dir()
        if direct is not None:
            return direct
        if preset_save_path_for_fallback is not None and preset_save_path_for_fallback.is_file():
            try:
                return load_preset(preset_save_path_for_fallback).output_dir
            except Exception:  # noqa: BLE001
                return None
        return None

    def _presets_dir(self) -> Path:
        p = _project_root() / "presets"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _browse_patch_job_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "Choose patch folder",
            self.patch_folder_edit.text().strip() or str(Path.cwd()),
        )
        if selected:
            self.patch_folder_edit.setText(selected)
            self._refresh_preset_combo()

    def _error(self, message: str) -> None:
        _AppMessageDialog(self, headline="Error", body=message).exec()

    def closeEvent(self, event: QCloseEvent) -> None:
        th = self._patch_thread
        if th is not None and th.isRunning():
            event.ignore()
            self._error("A patch is still running. Wait until it finishes before closing the window.")
            return
        super().closeEvent(event)


def _unique_paths(paths: list[Path]) -> list[Path]:
    unique: list[Path] = []
    for path in paths:
        if path not in unique:
            unique.append(path)
    return unique


def _project_root() -> Path:
    """Program / install root: exe directory if frozen, else directory that contains pyproject.toml."""
    if getattr(sys, "frozen", False):
        exe = getattr(sys, "executable", None) or sys.argv[0]
        return Path(exe).resolve().parent
    here = Path(__file__).resolve()
    for p in here.parents:
        if (p / "pyproject.toml").is_file():
            return p
    return here.parents[3]


def _windows_taskbar_identity() -> None:
    """Avoid the generic pythonw.exe taskbar icon on Windows (must run before QApplication)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AkELkA.BG3ArmorPatcher.Desktop.1")
    except (AttributeError, OSError):
        pass


def _apply_window_icon(app: QApplication, window: QMainWindow | None = None) -> None:
    candidates: list[Path] = [_project_root()]
    bundle = _resource_bundle_dir()
    if bundle is not None:
        candidates.append(bundle)
    for base in candidates:
        icon_path = base / "favicon.ico"
        if icon_path.is_file():
            icon = QIcon(str(icon_path))
            app.setWindowIcon(icon)
            if window is not None:
                window.setWindowIcon(icon)
            return


def main() -> int:
    _windows_taskbar_identity()
    app = QApplication(sys.argv)
    app.setApplicationName("BG3 Armor Patcher")
    app.setOrganizationName("AkELkA")
    fusion = QStyleFactory.create("Fusion")
    if fusion is not None:
        app.setStyle(fusion)
    app.setStyleSheet(APP_STYLESHEET)
    pal = app.palette()
    pal.setColor(QPalette.ColorGroup.Active, QPalette.ColorRole.PlaceholderText, QColor("#8a8a8a"))
    pal.setColor(QPalette.ColorGroup.Inactive, QPalette.ColorRole.PlaceholderText, QColor("#8a8a8a"))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.PlaceholderText, QColor("#555555"))
    app.setPalette(pal)
    _apply_window_icon(app)
    window = MainWindow()
    _apply_window_icon(app, window)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
