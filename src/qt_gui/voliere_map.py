#!/usr/bin/env python3
#
# voliere_map.py
#
# Top-down 2D map panel for the operator window: the PprzGCS VOLIERE plan
# (media/voliere_plan.png, cropped to the room) as a backdrop, with the
# live drone positions drawn on top -- a small "radar" of the cage.
#
# Alignment (operator request: align by cage dimensions, not lat/lon): the
# plan image is cropped exactly to the room, so its edges map onto the ENU
# rectangle VOLIERE_ENU below. Tune those four numbers until the drones sit
# where they really are in the cage.
#
import os

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QBrush
from PySide6.QtWidgets import QWidget, QSizePolicy

_PLAN = os.path.join(os.path.dirname(__file__), 'media', 'voliere_plan.png')

# ENU rectangle (metres) the plan image spans: (x_min, x_max, y_min, y_max).
# Cropped to the room, so image left/right -> x_min/x_max, top/bottom ->
# y_max/y_min (ENU y points up = image top). Adjust to line up the drones.
VOLIERE_ENU = (-4.0, 4.0, -5.0, 5.0)


class VoliereMapWidget(QWidget):
    """Top-down view of the volière plan with live drone dots."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._plan = QPixmap(_PLAN)
        self._drones = []   # list of (x_enu, y_enu, color_hex, label)
        self.setMinimumSize(190, 240)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        self.setStyleSheet("background:#131715; border:1px solid #2A312D;"
                           " border-radius:6px;")

    def set_drones(self, drones):
        """drones: iterable of (x_enu, y_enu, color_hex, label)."""
        self._drones = list(drones)
        self.update()

    def _plan_rect(self):
        """The image drawn centred and aspect-fit inside the widget."""
        m = 8
        w, h = self.width() - 2 * m, self.height() - 2 * m
        if self._plan.isNull() or w <= 0 or h <= 0:
            return QRectF(m, m, max(1, w), max(1, h))
        iw, ih = self._plan.width(), self._plan.height()
        s = min(w / iw, h / ih)
        dw, dh = iw * s, ih * s
        return QRectF(m + (w - dw) / 2, m + (h - dh) / 2, dw, dh)

    def _enu_to_px(self, x, y, r):
        x0, x1, y0, y1 = VOLIERE_ENU
        nx = (x - x0) / (x1 - x0)
        ny = (y - y0) / (y1 - y0)
        return QPointF(r.left() + nx * r.width(),
                       r.bottom() - ny * r.height())   # ENU y up -> image top

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self._plan_rect()
        if not self._plan.isNull():
            p.drawPixmap(r.toRect(), self._plan)
        for x, y, color, label in self._drones:
            pt = self._enu_to_px(x, y, r)
            p.setPen(QPen(QColor("#131715"), 1.5))
            p.setBrush(QBrush(QColor(color)))
            p.drawEllipse(pt, 6, 6)
            p.setPen(QColor("#FFFFFF"))
            p.drawText(pt + QPointF(9, 4), str(label))
        p.end()
