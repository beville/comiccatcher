"""
BaseReaderView — shared comic reader UI for OPDS and local CBZ sources.

Features:
  - Auto-hiding header / footer overlays (mouse-activity timer)
  - Page slider with on-demand thumbnail previews (toggleable)
  - Fit modes: Fit Page, Fit Width, Fit Height, 1:1
  - Page layout: 1-page, 2-page spread, or Auto (viewport-aspect-driven)
  - LtR / RtL reading direction (flips arrow-key and click-zone behaviour)
  - Mouse-wheel page navigation (passthrough in scroll modes)
  - Click-zone navigation: left third = prev, right third = next, centre = toggle overlays
  - Cursor auto-hide after inactivity
  - Keyboard: arrows, Space, PgUp/Dn, Home/End, Escape, F (fit), R (dir), L (layout)
  - Fullscreen: F11 / ⛶ button; Escape exits fullscreen before exiting reader
"""

import asyncio
import enum
from typing import Optional

from PyQt6.QtCore import Qt, QEvent, QPoint, QTimer
from PyQt6.QtGui import QKeyEvent, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QFrame, QGraphicsPixmapItem, QGraphicsScene, QGraphicsView,
    QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget,
)

from logger import get_logger

logger = get_logger("ui.base_reader")


# ---------------------------------------------------------------------------
# Fit mode
# ---------------------------------------------------------------------------

class FitMode(enum.Enum):
    FIT_PAGE   = "fit_page"
    FIT_WIDTH  = "fit_width"
    FIT_HEIGHT = "fit_height"
    ORIGINAL   = "original"


_FIT_LABELS = {
    FitMode.FIT_PAGE:   "Fit Page",
    FitMode.FIT_WIDTH:  "Fit Width",
    FitMode.FIT_HEIGHT: "Fit Height",
    FitMode.ORIGINAL:   "1:1",
}
_FIT_CYCLE = [FitMode.FIT_PAGE, FitMode.FIT_WIDTH, FitMode.FIT_HEIGHT, FitMode.ORIGINAL]


# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------

class PageLayout(enum.Enum):
    SINGLE = "single"
    DOUBLE = "double"
    AUTO   = "auto"


_LAYOUT_LABELS = {
    PageLayout.SINGLE: "1 Page",
    PageLayout.DOUBLE: "2 Pages",
    PageLayout.AUTO:   "Auto",
}
_LAYOUT_CYCLE = [PageLayout.SINGLE, PageLayout.DOUBLE, PageLayout.AUTO]


def _compose_spread(pm1: QPixmap, pm2: QPixmap) -> QPixmap:
    """Composite two pages side-by-side, centred vertically, on a black canvas."""
    total_w = pm1.width() + pm2.width()
    max_h   = max(pm1.height(), pm2.height())
    result  = QPixmap(total_w, max_h)
    result.fill(Qt.GlobalColor.black)
    painter = QPainter(result)
    painter.drawPixmap(0,           (max_h - pm1.height()) // 2, pm1)
    painter.drawPixmap(pm1.width(), (max_h - pm2.height()) // 2, pm2)
    painter.end()
    return result


# ---------------------------------------------------------------------------
# Thumbnail slider
# ---------------------------------------------------------------------------

class ThumbnailSlider(QWidget):
    """
    A horizontal QSlider with a floating thumbnail popup that appears while
    the user hovers or drags over the slider track.

    The popup widget is parented to `popup_parent` (the reader window) so it
    can float above the footer overlay.
    """

    def __init__(self, popup_parent: QWidget):
        super().__init__(popup_parent)
        self._popup_parent = popup_parent
        self._cache: dict[int, QPixmap] = {}   # idx -> scaled thumbnail
        self._loading: set[int] = set()
        self._thumb_loader = None              # async callable: idx -> Optional[QPixmap]

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setCursor(Qt.CursorShape.PointingHandCursor)
        # We use theme-aware colors for the slider
        self.slider.setObjectName("reader_slider")
        layout.addWidget(self.slider)

        # Popup label — child of popup_parent for correct z-order
        self._popup = QLabel(popup_parent)
        self._popup.setFixedSize(100, 150)
        self._popup.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._popup.setStyleSheet(
            "background: rgba(0,0,0,230); border: 1px solid #555; border-radius: 4px;"
            "color: white; font-size: 11px;"
        )
        self._popup.setVisible(False)

        self.slider.installEventFilter(self)

    def set_thumb_loader(self, fn):
        """Set an async callable ``async def fn(idx) -> Optional[QPixmap]``."""
        self._thumb_loader = fn

    def store_thumb(self, idx: int, pixmap: QPixmap):
        if not pixmap.isNull():
            self._cache[idx] = pixmap.scaled(
                96, 136,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

    def hide_popup(self):
        self._popup.setVisible(False)

    # ------------------------------------------------------------------ #

    def eventFilter(self, source, event):
        if source is self.slider:
            t = event.type()
            if t in (QEvent.Type.MouseMove, QEvent.Type.MouseButtonPress):
                self._show_at(event.position().x())
            elif t in (QEvent.Type.Leave, QEvent.Type.MouseButtonRelease):
                self._popup.setVisible(False)
        return super().eventFilter(source, event)

    def _page_at(self, x: float) -> int:
        mx = self.slider.maximum()
        if mx <= 0:
            return 0
        ratio = max(0.0, min(1.0, x / max(1, self.slider.width())))
        return round(ratio * mx)

    def _show_at(self, x: float):
        idx = self._page_at(x)

        thumb = self._cache.get(idx)
        if thumb:
            self._popup.setPixmap(thumb)
            self._popup.setText("")
        else:
            self._popup.setPixmap(QPixmap())
            self._popup.setText(f"Page\n{idx + 1}")
            if self._thumb_loader and idx not in self._loading:
                asyncio.create_task(self._async_load(idx))

        # Position popup above the hover point in the parent's coordinate space
        pos_in_parent = self.slider.mapTo(self._popup_parent, QPoint(int(x), 0))
        px = max(0, min(pos_in_parent.x() - 50,
                        self._popup_parent.width() - self._popup.width()))
        py = max(0, pos_in_parent.y() - self._popup.height() - 10)
        self._popup.move(px, py)
        self._popup.setVisible(True)
        self._popup.raise_()

    async def _async_load(self, idx: int):
        if idx in self._loading:
            return
        self._loading.add(idx)
        try:
            pixmap = await self._thumb_loader(idx)
            if pixmap and not pixmap.isNull():
                self.store_thumb(idx, pixmap)
                # Refresh popup if it's currently showing this page
                if self._popup.isVisible():
                    thumb = self._cache.get(idx)
                    if thumb:
                        self._popup.setPixmap(thumb)
                        self._popup.setText("")
        except Exception:
            pass
        finally:
            self._loading.discard(idx)


# ---------------------------------------------------------------------------
# Base reader
# ---------------------------------------------------------------------------

class BaseReaderView(QWidget):
    """
    Shared reader base.  Subclasses implement:
      - ``async _load_page_pixmap(idx) -> Optional[QPixmap]``
      - ``async _do_prefetch(idx)``          (optional, default no-op)
      - ``_on_page_changed(idx)``            (optional hook, e.g. progression sync)
    """

    OVERLAY_HIDE_MS = 3000
    CURSOR_HIDE_MS  = 2000
    PREFETCH_AHEAD  = 3
    PREFETCH_BEHIND = 1

    def __init__(self, on_exit):
        super().__init__()
        self.on_exit = on_exit
        self._index   = 0
        self._total   = 0
        self._fit_mode    = FitMode.FIT_PAGE
        self._page_layout = PageLayout.SINGLE
        self._rtl         = False
        self._overlays_visible = True
        self._slider_dragging  = False
        self._thumb_visible    = True

        self.setStyleSheet("background-color: black; color: white;")
        self.setMouseTracking(True)

        # --- Graphics view (fills the whole widget) ---
        self.scene = QGraphicsScene()
        self.view  = QGraphicsView(self.scene)
        self.view.setFrameShape(QFrame.Shape.NoFrame)
        self.view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.view.setStyleSheet("border: none; background-color: black;")
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setMouseTracking(True)
        self.view.viewport().setMouseTracking(True)

        self.pixmap_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmap_item)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self.view)

        # --- Header overlay ---
        self.header = QFrame(self)
        self.header.setStyleSheet(
            "background-color: rgba(0,0,0,210); border-bottom: 1px solid #444;"
        )
        hdr = QHBoxLayout(self.header)
        hdr.setContentsMargins(8, 4, 8, 4)

        self.btn_back = QPushButton("← Back")
        self.btn_back.setFixedWidth(70)
        self.btn_back.clicked.connect(self._do_exit)

        self.title_label = QLabel("")
        self.title_label.setStyleSheet("color: white; font-weight: bold; font-size: 13px;")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.counter_label = QLabel("0 / 0")
        self.counter_label.setStyleSheet("color: #aaa; font-size: 12px;")
        self.counter_label.setFixedWidth(75)
        self.counter_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        self.btn_fullscreen = QPushButton("⛶")
        self.btn_fullscreen.setFixedWidth(32)
        self.btn_fullscreen.setToolTip("Toggle fullscreen  [F11]")
        self.btn_fullscreen.clicked.connect(self._toggle_fullscreen)

        hdr.addWidget(self.btn_back)
        hdr.addWidget(self.title_label, 1)
        hdr.addWidget(self.counter_label)
        hdr.addWidget(self.btn_fullscreen)

        # --- Footer overlay ---
        self.footer = QFrame(self)
        self.footer.setStyleSheet(
            "background-color: rgba(0,0,0,210); border-top: 1px solid #444;"
        )
        ftr = QVBoxLayout(self.footer)
        ftr.setContentsMargins(10, 6, 10, 8)
        ftr.setSpacing(5)

        self.thumb_slider = ThumbnailSlider(self)
        self.thumb_slider.slider.sliderPressed.connect(self._on_slider_pressed)
        self.thumb_slider.slider.sliderReleased.connect(self._on_slider_released)
        self.thumb_slider.slider.valueChanged.connect(self._on_slider_value_changed)
        ftr.addWidget(self.thumb_slider)

        ctrl = QHBoxLayout()
        ctrl.setSpacing(8)

        _btn_css = (
            "QPushButton { background:#333; color:white; border-radius:4px;"
            " padding:3px 10px; }"
            "QPushButton:hover { background:#555; }"
            "QPushButton:disabled { color:#555; }"
        )

        self.btn_prev = QPushButton("‹ Prev")
        self.btn_prev.setFixedWidth(70)
        self.btn_prev.clicked.connect(self._prev)

        self.btn_next = QPushButton("Next ›")
        self.btn_next.setFixedWidth(70)
        self.btn_next.clicked.connect(self._next)

        self.btn_fit = QPushButton(_FIT_LABELS[self._fit_mode])
        self.btn_fit.setFixedWidth(88)
        self.btn_fit.setToolTip("Cycle fit mode  [F]")
        self.btn_fit.clicked.connect(self._cycle_fit)

        self.btn_dir = QPushButton("LtR")
        self.btn_dir.setFixedWidth(50)
        self.btn_dir.setToolTip("Toggle reading direction  [R]")
        self.btn_dir.clicked.connect(self._toggle_dir)

        self.btn_layout = QPushButton(_LAYOUT_LABELS[self._page_layout])
        self.btn_layout.setFixedWidth(72)
        self.btn_layout.setToolTip("Cycle page layout  [L]")
        self.btn_layout.clicked.connect(self._cycle_layout)

        self.btn_thumb = QPushButton("Thumbs ✓")
        self.btn_thumb.setFixedWidth(80)
        self.btn_thumb.setToolTip("Toggle thumbnail slider")
        self.btn_thumb.clicked.connect(self._toggle_thumb_slider)

        for b in (self.btn_back, self.btn_prev, self.btn_next, self.btn_fit,
                  self.btn_dir, self.btn_layout, self.btn_thumb, self.btn_fullscreen):
            b.setStyleSheet(_btn_css)

        ctrl.addWidget(self.btn_prev)
        ctrl.addStretch()
        ctrl.addWidget(self.btn_fit)
        ctrl.addWidget(self.btn_dir)
        ctrl.addWidget(self.btn_layout)
        ctrl.addWidget(self.btn_thumb)
        ctrl.addStretch()
        ctrl.addWidget(self.btn_next)
        ftr.addLayout(ctrl)

        # --- Timers ---
        self._overlay_timer = QTimer(self)
        self._overlay_timer.setSingleShot(True)
        self._overlay_timer.setInterval(self.OVERLAY_HIDE_MS)
        self._overlay_timer.timeout.connect(self._hide_overlays)

        self._cursor_timer = QTimer(self)
        self._cursor_timer.setSingleShot(True)
        self._cursor_timer.setInterval(self.CURSOR_HIDE_MS)
        self._cursor_timer.timeout.connect(lambda: self.setCursor(Qt.CursorShape.BlankCursor))

        self.view.viewport().installEventFilter(self)
        self.view.installEventFilter(self)

        self._bump_activity()

    # ------------------------------------------------------------------ #
    # Subclass contract                                                    #
    # ------------------------------------------------------------------ #

    async def _load_page_pixmap(self, idx: int) -> Optional[QPixmap]:
        raise NotImplementedError

    async def _do_prefetch(self, idx: int):
        pass

    def _on_page_changed(self, idx: int):
        pass

    # ------------------------------------------------------------------ #
    # Geometry                                                             #
    # ------------------------------------------------------------------ #

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._layout_overlays()
        self._apply_fit()

    def _layout_overlays(self):
        w     = self.width()
        ftr_h = 78 if self._thumb_visible else 50
        self.header.setGeometry(0, 0, w, 38)
        self.footer.setGeometry(0, self.height() - ftr_h, w, ftr_h)

    # ------------------------------------------------------------------ #
    # Activity / overlay visibility                                        #
    # ------------------------------------------------------------------ #

    def _bump_activity(self):
        if self.cursor().shape() == Qt.CursorShape.BlankCursor:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        if not self._overlays_visible:
            self._show_overlays()
        self._overlay_timer.start()
        self._cursor_timer.start()

    def _show_overlays(self):
        self._overlays_visible = True
        self.header.setVisible(True)
        self.footer.setVisible(True)

    def _hide_overlays(self):
        self._overlays_visible = False
        self.header.setVisible(False)
        self.footer.setVisible(False)
        self.thumb_slider.hide_popup()

    # ------------------------------------------------------------------ #
    # Event handling                                                       #
    # ------------------------------------------------------------------ #

    def eventFilter(self, source, event):
        t = event.type()
        vp = self.view.viewport()

        if t in (QEvent.Type.MouseMove, QEvent.Type.MouseButtonPress):
            self._bump_activity()

        if t == QEvent.Type.Resize and source is vp:
            self._apply_fit()

        if t == QEvent.Type.MouseButtonPress and source is vp:
            self._handle_click(event)

        if t == QEvent.Type.Wheel and source is vp:
            # Pass through to view's scrollbar in scrollable fit modes
            if self._fit_mode in (FitMode.FIT_WIDTH, FitMode.FIT_HEIGHT, FitMode.ORIGINAL):
                return False
            if event.angleDelta().y() < 0:
                self._next()
            else:
                self._prev()
            return True

        return super().eventFilter(source, event)

    def _handle_click(self, event):
        w = self.view.viewport().width()
        x = event.position().x()
        if x < w / 3:
            self._next() if self._rtl else self._prev()
        elif x > w * 2 / 3:
            self._prev() if self._rtl else self._next()
        else:
            # Centre tap: toggle overlay visibility
            if self._overlays_visible:
                self._hide_overlays()
                self._overlay_timer.stop()
            else:
                self._bump_activity()

    def keyPressEvent(self, event: QKeyEvent):
        self._bump_activity()
        key = event.key()

        # Flip horizontal arrow keys for RtL
        if self._rtl:
            if   key == Qt.Key.Key_Right: key = Qt.Key.Key_Left
            elif key == Qt.Key.Key_Left:  key = Qt.Key.Key_Right

        if key in (Qt.Key.Key_Right, Qt.Key.Key_Space, Qt.Key.Key_PageDown):
            self._next()
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_PageUp):
            self._prev()
        elif key == Qt.Key.Key_F11:
            self._toggle_fullscreen()
        elif key == Qt.Key.Key_Escape:
            if self.window().isFullScreen():
                self._toggle_fullscreen()
            else:
                self._do_exit()
        elif key == Qt.Key.Key_F:
            self._cycle_fit()
        elif key == Qt.Key.Key_R:
            self._toggle_dir()
        elif key == Qt.Key.Key_L:
            self._cycle_layout()
        elif key == Qt.Key.Key_Home:
            self._go_to(0)
        elif key == Qt.Key.Key_End:
            self._go_to(self._total - 1)
        super().keyPressEvent(event)

    # ------------------------------------------------------------------ #
    # Fullscreen / exit                                                    #
    # ------------------------------------------------------------------ #

    def _do_exit(self):
        if self.window().isFullScreen():
            self.window().showNormal()
        self.on_exit()

    def _toggle_fullscreen(self):
        win = self.window()
        if win.isFullScreen():
            win.showNormal()
            self.btn_fullscreen.setText("⛶")
            self.btn_fullscreen.setToolTip("Enter fullscreen  [F11]")
        else:
            win.showFullScreen()
            self.btn_fullscreen.setText("⊡")
            self.btn_fullscreen.setToolTip("Exit fullscreen  [F11]")

    # ------------------------------------------------------------------ #
    # Navigation                                                           #
    # ------------------------------------------------------------------ #

    def _prev(self):
        if self._index > 0:
            step = 2 if self._effective_layout() == PageLayout.DOUBLE else 1
            self._go_to(self._index - step)

    def _next(self):
        if self._index < self._total - 1:
            step = 2 if self._effective_layout() == PageLayout.DOUBLE else 1
            self._go_to(self._index + step)

    def _go_to(self, idx: int):
        idx = max(0, min(idx, self._total - 1))
        self._index = idx
        asyncio.create_task(self._show_page())

    def _on_slider_pressed(self):
        self._slider_dragging = True

    def _on_slider_released(self):
        self._slider_dragging = False
        self._go_to(self.thumb_slider.slider.value())

    def _on_slider_value_changed(self, value: int):
        # While dragging: update counter only, no page load
        if self._slider_dragging:
            self.counter_label.setText(f"{value + 1} / {self._total}")

    # ------------------------------------------------------------------ #
    # Fit mode                                                             #
    # ------------------------------------------------------------------ #

    def _cycle_fit(self):
        i = _FIT_CYCLE.index(self._fit_mode)
        self._fit_mode = _FIT_CYCLE[(i + 1) % len(_FIT_CYCLE)]
        self.btn_fit.setText(_FIT_LABELS[self._fit_mode])
        self._apply_fit()

    def _apply_fit(self):
        if self.pixmap_item.pixmap().isNull():
            return
        pm  = self.pixmap_item.pixmap()
        vp  = self.view.viewport()
        off = Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        on  = Qt.ScrollBarPolicy.ScrollBarAsNeeded

        if self._fit_mode == FitMode.FIT_PAGE:
            self.view.setHorizontalScrollBarPolicy(off)
            self.view.setVerticalScrollBarPolicy(off)
            self.view.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

        elif self._fit_mode == FitMode.FIT_WIDTH:
            self.view.setHorizontalScrollBarPolicy(off)
            self.view.setVerticalScrollBarPolicy(on)
            if pm.width() > 0:
                self.view.resetTransform()
                self.view.scale(vp.width() / pm.width(), vp.width() / pm.width())

        elif self._fit_mode == FitMode.FIT_HEIGHT:
            self.view.setHorizontalScrollBarPolicy(on)
            self.view.setVerticalScrollBarPolicy(off)
            if pm.height() > 0:
                self.view.resetTransform()
                self.view.scale(vp.height() / pm.height(), vp.height() / pm.height())

        elif self._fit_mode == FitMode.ORIGINAL:
            self.view.setHorizontalScrollBarPolicy(on)
            self.view.setVerticalScrollBarPolicy(on)
            self.view.resetTransform()

    # ------------------------------------------------------------------ #
    # Page layout                                                          #
    # ------------------------------------------------------------------ #

    def _effective_layout(self) -> PageLayout:
        """Resolve AUTO to SINGLE or DOUBLE based on current viewport shape."""
        if self._page_layout == PageLayout.AUTO:
            vp = self.view.viewport()
            return PageLayout.DOUBLE if vp.width() > vp.height() else PageLayout.SINGLE
        return self._page_layout

    def _cycle_layout(self):
        i = _LAYOUT_CYCLE.index(self._page_layout)
        self._page_layout = _LAYOUT_CYCLE[(i + 1) % len(_LAYOUT_CYCLE)]
        self.btn_layout.setText(_LAYOUT_LABELS[self._page_layout])
        asyncio.create_task(self._show_page())

    # ------------------------------------------------------------------ #
    # Thumbnail slider toggle                                              #
    # ------------------------------------------------------------------ #

    def _toggle_thumb_slider(self):
        self._thumb_visible = not self._thumb_visible
        self.thumb_slider.setVisible(self._thumb_visible)
        if not self._thumb_visible:
            self.thumb_slider.hide_popup()
        self.btn_thumb.setText("Thumbs ✓" if self._thumb_visible else "Thumbs")
        self._layout_overlays()

    # ------------------------------------------------------------------ #
    # Direction                                                            #
    # ------------------------------------------------------------------ #

    def _toggle_dir(self):
        self._rtl = not self._rtl
        self.btn_dir.setText("RtL" if self._rtl else "LtR")

    # ------------------------------------------------------------------ #
    # Page display (called by subclasses after data is ready)             #
    # ------------------------------------------------------------------ #

    def _setup_reader(self, title: str, total: int):
        """Call once the page list / reading order is known."""
        self._total = total
        self._index = 0
        self.title_label.setText(title)
        self.thumb_slider.slider.setRange(0, max(0, total - 1))
        self.thumb_slider.slider.setValue(0)

    async def _show_page(self):
        idx = self._index
        if not (0 <= idx < self._total):
            return

        layout    = self._effective_layout()
        double    = layout == PageLayout.DOUBLE
        idx2      = idx + 1 if double and idx + 1 < self._total else None
        page_desc = (f"{idx + 1}–{idx2 + 1}" if idx2 is not None else str(idx + 1))
        self.counter_label.setText(f"{page_desc} / {self._total}")
        self.btn_prev.setEnabled(idx > 0)
        self.btn_next.setEnabled(idx < self._total - 1)

        self.thumb_slider.slider.blockSignals(True)
        self.thumb_slider.slider.setValue(idx)
        self.thumb_slider.slider.blockSignals(False)

        if idx2 is not None:
            pm1, pm2 = await asyncio.gather(
                self._load_page_pixmap(idx),
                self._load_page_pixmap(idx2),
            )
            if idx != self._index:
                return
            if pm1 and pm2 and not pm1.isNull() and not pm2.isNull():
                pixmap = _compose_spread(pm1, pm2)
                self.thumb_slider.store_thumb(idx, pm1)
                self.thumb_slider.store_thumb(idx2, pm2)
            else:
                pixmap = pm1  # fallback to single if second page missing
                if pm1 and not pm1.isNull():
                    self.thumb_slider.store_thumb(idx, pm1)
        else:
            pixmap = await self._load_page_pixmap(idx)
            if idx != self._index:
                return
            if pixmap and not pixmap.isNull():
                self.thumb_slider.store_thumb(idx, pixmap)

        if pixmap and not pixmap.isNull():
            self.pixmap_item.setPixmap(pixmap)
            self.scene.setSceneRect(self.pixmap_item.boundingRect())
            self._apply_fit()

        # Prefetch ahead and one behind for back-navigation
        ahead_start = (idx2 or idx) + 1
        for j in range(ahead_start, min(self._total, ahead_start + self.PREFETCH_AHEAD)):
            asyncio.create_task(self._do_prefetch(j))
        if idx > 0:
            asyncio.create_task(self._do_prefetch(idx - 1))

        self._on_page_changed(idx)
