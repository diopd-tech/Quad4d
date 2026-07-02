#!/usr/bin/env python3
#
# drones_panel.py  
#
# Read-only "Drones" panel for the Click'n Fly operator window.
#
import time
import numpy as np

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QGroupBox, QFrame, QLabel,
                               QVBoxLayout, QHBoxLayout, QWidget, QScrollArea)


STATUS_COLOR = {
    "UNKNOWN":   "#8B938F",
    "CONNECTED": "#8B938F",
    "READY":     "#8B938F",
    "CRUISING":  "#C7D0CB",
    "ARRIVED":   "#C7D0CB",
}
_DEFAULT_STATUS_COLOR = "#8B938F"


_DEFAULT_COLORS = ["#1E78B3", "#FF800E", "#2BA02B"]

_VALUE = "#C7D0CB"
_MUTED = "#8B938F"


PANEL_STYLE = """
QGroupBox#dronesPanel {
    background-color: #1B201D; border: 1px solid #2A312D;
    border-radius: 6px; margin-top: 0px; padding: 7px;
}
"""

_SPEED_ALPHA = 0.3   # lissage de la vitesse estimee (0..1, plus haut = plus reactif)


class _DroneRow(QFrame):

    def __init__(self, drone_id, color, traj_name=""):
        super().__init__()
       
        self.setStyleSheet(
            "QFrame { background:#202622; border:1px solid #2A312D;"
            f" border-left:3px solid {color}; border-radius:5px; }}")

        v = QVBoxLayout(self)
        v.setContentsMargins(7, 5, 7, 5)
        v.setSpacing(2)

       
        top = QHBoxLayout()
        top.setSpacing(6)
  
        name = QLabel(f"D{drone_id}")
        name.setStyleSheet("color:#E8ECEA; font-size:12px; font-weight:600; border:none;")
    
        self.lbl_status = QLabel()
        self.lbl_status.setStyleSheet("font-size:11px; border:none;")
        top.addWidget(name)
        top.addStretch(1)
        top.addWidget(self.lbl_status)
        v.addLayout(top)


        self.lbl_traj = QLabel(traj_name)
        self.lbl_traj.setStyleSheet(f"color:{_MUTED}; font-size:11px; border:none;")
        self.lbl_traj.setToolTip(traj_name)
        v.addWidget(self.lbl_traj)


        self.lbl_metrics = QLabel()
        self.lbl_metrics.setStyleSheet(
            f"color:{_MUTED}; font-size:11px; border:none;"
            " font-family:'DejaVu Sans Mono','Menlo','Consolas',monospace;")
        v.addWidget(self.lbl_metrics)

        self.set_status("UNKNOWN")
        self.set_values(None, None, None, None)


    def set_status(self, status_name):
        col = STATUS_COLOR.get(status_name, _DEFAULT_STATUS_COLOR)
        self.lbl_status.setText(status_name.replace("_", " ").title())
        self.lbl_status.setStyleSheet(f"color:{col}; font-size:11px; border:none;")


    def set_traj_name(self, name):
        self.lbl_traj.setText(name)
        self.lbl_traj.setToolTip(name)


    def set_values(self, alt, spd, dist, batt=None):
        def cell(label, value, unit, fmt, color=_VALUE):
            v = (fmt % value + unit) if value is not None else "\u2014"
            return f'{label} <span style="color:{color}">{v}</span>'
        # TODO: color batt red below a low-voltage threshold once the
        # battery's cell count is known (need volts/cell, not just pack V).
        self.lbl_metrics.setText(
            cell("alt", alt, "m", "%.2f") + "   "
            + cell("spd", spd, "m/s", "%.1f") + "   "
            + cell("dist", dist, "m", "%.2f") + "   "
            + cell("batt", batt, "V", "%.1f"))


class DronesPanel(QGroupBox):
    def __init__(self, ids, colors=None, trajs=None):
        super().__init__()                    
        self.setObjectName("dronesPanel")
        self.setStyleSheet(PANEL_STYLE)
        self.ids = list(ids)
        self.colors = list(colors) if colors else list(_DEFAULT_COLORS)
        trajs = list(trajs) if trajs else []     

        v = QVBoxLayout(self)
        v.setContentsMargins(2, 2, 2, 2)
        v.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("DRONES")
        title.setStyleSheet("color:#6E7770; font-size:9px; letter-spacing:1.5px; border:none;")
        self.lbl_flight_time = QLabel()
        self.lbl_flight_time.setStyleSheet(
            "color:#8B938F; font-size:10px; border:none;"
            " font-family:'DejaVu Sans Mono','Menlo','Consolas',monospace;")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.lbl_flight_time)
        v.addLayout(header)
        self._set_flight_time(None)

        self.rows = {}
        rows_box = QWidget()
        rows_box.setStyleSheet("background:transparent; border:none;")
        rows_lay = QVBoxLayout(rows_box)
        rows_lay.setContentsMargins(0, 0, 0, 0)
        rows_lay.setSpacing(5)
        for i, _id in enumerate(self.ids):
            color = self.colors[i % len(self.colors)]
            tname = trajs[i] if i < len(trajs) else "" 
            row = _DroneRow(_id, color, tname)         
            self.rows[_id] = row
            rows_lay.addWidget(row)
        rows_lay.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(rows_box)
        scroll.setMaximumHeight(220)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border:none; background:transparent; }")
        v.addWidget(scroll)

        self._prev = {}
        self._speed = {}

    def _set_flight_time(self, text):
        self.lbl_flight_time.setText(text if text is not None else "\u2014")

    def set_traj_name(self, idx, name):
        if 0 <= idx < len(self.ids):
            self.rows[self.ids[idx]].set_traj_name(name)

    def update_from_fd(self, fd):
        now = time.time()

        ft = None
        if getattr(fd.status, "name", "") == "GUIDING":
            m, s = divmod(int(now - fd.t0), 60)
            ft = f"{m:02d}:{s:02d}"
        self._set_flight_time(ft)

        for _id in self.ids:
            ac = fd.acs.get(_id)
            row = self.rows[_id]
            if ac is None:
                continue

            row.set_status(getattr(ac.status, "name", "UNKNOWN"))
            batt = getattr(ac, "battery_v", None)

            if not ac.vehicle_traj:                 # aucune pose recue encore
                row.set_values(None, None, None, batt)
                self._prev.pop(_id, None)
                continue

            pos = np.asarray(ac.T[:3, 3], dtype=float)
            alt = pos[2]                           
            dist = ac.dist_to_ref()

            # vitesse: derivee numerique lissee de la position (estimation)
            v_est = self._speed.get(_id, 0.0)
            prev = self._prev.get(_id)
            if prev is not None:
                dt = now - prev[1]
                if dt > 1e-3:
                    inst = np.linalg.norm(pos - prev[0]) / dt
                    v_est = _SPEED_ALPHA * inst + (1 - _SPEED_ALPHA) * v_est
                    self._speed[_id] = v_est
            self._prev[_id] = (pos, now)

            row.set_values(alt, v_est, dist, batt)