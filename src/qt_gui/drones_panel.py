#!/usr/bin/env python3
#
# drones_panel.py  
#
# Read-only "Drones" panel for the Click'n Fly operator window.
#
import time
import numpy as np

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QGroupBox, QFrame, QLabel, QSizePolicy,
                               QPushButton, QVBoxLayout, QHBoxLayout, QWidget)


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

# Battery pack: Gens Ace Soaring 2700mAh 3S (11.1V nominal, 12.6V full)
_BATT_CELLS  = 3
_BATT_LOW_V  = 3.5 * _BATT_CELLS   # 10.5V: plan to land
_BATT_CRIT_V = 3.3 * _BATT_CELLS   # 9.9V: land now
_BATT_LOW_COLOR  = "#F2A33C"
_BATT_CRIT_COLOR = "#F85149"       # same red as the HMI error state

# --- Pre-flight checklist -----------------------------------------------
# The GCS "green icons", brought into the operator's window (ConOps §4):
# per drone, is the mocap pose flowing, is the RC link up, is the
# telemetry downlink alive. Grey = never heard, green = good, red = was
# there and is gone (the dangerous case).
_CHECK_COLORS = {"ok": "#3FB950", "warn": _BATT_LOW_COLOR,
                 "bad": _BATT_CRIT_COLOR, "unknown": _MUTED}
_MOCAP_STALE_S  = 1.0   # EXTERNAL_POSE flows at mocap rate: >1s = chain down
_STATUS_STALE_S = 5.0   # ROTORCRAFT_STATUS is slow telemetry: be tolerant

_RC_STATUS_NAMES = {0: "OK", 1: "LOST", 2: "REALLY_LOST"}
_AP_MODE_NAMES = ("KILL", "FAILSAFE", "HOME", "RATE_DIRECT", "ATTITUDE_DIRECT",
                  "RATE_RC_CLIMB", "ATTITUDE_RC_CLIMB", "ATTITUDE_CLIMB",
                  "RATE_Z_HOLD", "ATTITUDE_Z_HOLD", "HOVER_DIRECT",
                  "HOVER_CLIMB", "HOVER_Z_HOLD", "NAV", "RC_DIRECT",
                  "CARE_FREE", "FORWARD", "MODULE", "FLIP", "GUIDED")
_ARMING_NAMES = ("NO_RC", "WAITING", "ARMING", "ARMED", "DISARMING",
                 "KILLED", "YAW_CENTERED", "THROTTLE_DOWN",
                 "NOT_MODE_MANUAL", "UNARMED_IN_AUTO", "THROTTLE_NOT_DOWN",
                 "STICKS_NOT_CENTERED", "PITCH_NOT_CENTERED",
                 "ROLL_NOT_CENTERED", "YAW_NOT_CENTERED",
                 "AHRS_NOT_ALLIGNED", "OUT_OF_GEOFENCE", "LOW_BATTERY")


PANEL_STYLE = """
QGroupBox#dronesPanel {
    background: transparent; border: none;
    margin-top: 0px; padding: 0px;
}
"""

_SPEED_ALPHA = 0.3   # lissage de la vitesse estimee (0..1, plus haut = plus reactif)


_KILL_IDLE  = ("background-color:#7A2B26; color:#FFEDEB; font-weight:700;"
               " font-size:12px; border:none; border-radius:4px; padding:3px 10px;")
_KILL_ARMED = ("background-color:#F85149; color:#FFFFFF; font-weight:700;"
               " font-size:12px; border:none; border-radius:4px; padding:3px 10px;")


class _DroneRow(QFrame):

    def __init__(self, drone_id, color, traj_name="", kill_cbk=None):
        super().__init__()
        self.drone_id = drone_id
        self._kill_cbk = kill_cbk
        self._kill_armed = False

        self.setStyleSheet(
            "QFrame { background:#202622; border:1px solid #2A312D;"
            f" border-left:3px solid {color}; border-radius:5px; }}")

        v = QVBoxLayout(self)
        v.setContentsMargins(10, 8, 10, 8)
        v.setSpacing(4)


        top = QHBoxLayout()
        top.setSpacing(8)

        name = QLabel(f"D{drone_id}")
        name.setStyleSheet("color:#E8ECEA; font-size:15px; font-weight:600; border:none;")

        # trajectory name inline with the header: one line less per row,
        # so every drone stays fully visible in the fixed-height window
        self.lbl_traj = QLabel(traj_name)
        self.lbl_traj.setStyleSheet(f"color:{_MUTED}; font-size:13px; border:none;")
        self.lbl_traj.setToolTip(traj_name)

        self.lbl_status = QLabel()
        self.lbl_status.setStyleSheet("font-size:13px; border:none;")
        top.addWidget(name)
        top.addWidget(self.lbl_traj)
        top.addStretch(1)
        top.addWidget(self.lbl_status)

        # per-drone kill (last resort): compact, right in the row so it's
        # next to the drone it acts on. Two clicks within 3s (an accidental
        # kill drops a drone out of the sky).
        self.button_kill = QPushButton("KILL")
        self.button_kill.setStyleSheet(_KILL_IDLE)
        self.button_kill.setToolTip(f"Cut motors of drone {drone_id} (it falls)")
        if kill_cbk is None:
            self.button_kill.setEnabled(False)
        else:
            self.button_kill.clicked.connect(self._on_kill_pressed)
        top.addWidget(self.button_kill)
        v.addLayout(top)

        # never let the column layout squash the row below its natural
        # height (it silently eats the bottom lines)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)


        self.lbl_metrics = QLabel()
        self.lbl_metrics.setWordWrap(True)
        self.lbl_metrics.setStyleSheet(
            f"color:{_MUTED}; font-size:13px; border:none;"
            " font-family:'DejaVu Sans Mono','Menlo','Consolas',monospace;")
        v.addWidget(self.lbl_metrics)

        self.lbl_checklist = QLabel()
        self.lbl_checklist.setStyleSheet(
            f"color:{_MUTED}; font-size:13px; border:none;"
            " font-family:'DejaVu Sans Mono','Menlo','Consolas',monospace;")
        v.addWidget(self.lbl_checklist)

        self.lbl_nav = QLabel()
        self.lbl_nav.setWordWrap(True)
        self.lbl_nav.setStyleSheet(
            f"color:{_MUTED}; font-size:13px; border:none;"
            " font-family:'DejaVu Sans Mono','Menlo','Consolas',monospace;")
        v.addWidget(self.lbl_nav)

        self.set_status("UNKNOWN")
        self.set_values(None, None, None, None)
        self.set_checklist([("mocap", "unknown", "no EXTERNAL_POSE seen yet"),
                            ("RC", "unknown", "no ROTORCRAFT_STATUS seen yet"),
                            ("link", "unknown", "no ROTORCRAFT_STATUS seen yet")])
        self.set_nav("—")


    def _on_kill_pressed(self):
        if not self._kill_armed:
            self._kill_armed = True
            self.button_kill.setText("CONFIRM")
            self.button_kill.setStyleSheet(_KILL_ARMED)
            QTimer.singleShot(3000, self._disarm_kill)
            return
        self._disarm_kill()
        if self._kill_cbk is not None:
            self._kill_cbk(self.drone_id)

    def _disarm_kill(self):
        self._kill_armed = False
        self.button_kill.setText("KILL")
        self.button_kill.setStyleSheet(_KILL_IDLE)

    def set_status(self, status_name):
        col = STATUS_COLOR.get(status_name, _DEFAULT_STATUS_COLOR)
        self.lbl_status.setText(status_name.replace("_", " ").title())
        self.lbl_status.setStyleSheet(f"color:{col}; font-size:13px; border:none;")


    def set_traj_name(self, name):
        self.lbl_traj.setText(name)
        self.lbl_traj.setToolTip(name)


    def set_checklist(self, items):
        """items: list of (label, state, detail) with state in _CHECK_COLORS."""
        parts, tips = [], []
        for label, state, detail in items:
            col = _CHECK_COLORS.get(state, _MUTED)
            parts.append(f'<span style="color:{col};">●</span> {label}')
            tips.append(f"{label}: {detail}")
        self.lbl_checklist.setText("  ".join(parts))
        self.lbl_checklist.setToolTip("\n".join(tips))


    def set_nav(self, html):
        self.lbl_nav.setText(html)


    def set_values(self, alt, spd, dist, batt=None):
        def cell(label, value, unit, fmt, color=_VALUE, bold=False):
            v = (fmt % value + unit) if value is not None else "\u2014"
            weight = "font-weight:700;" if bold else ""
            return f'{label} <span style="color:{color};{weight}">{v}</span>'
        batt_color, batt_bold = _VALUE, False
        if batt is not None:
            if batt < _BATT_CRIT_V:
                batt_color, batt_bold = _BATT_CRIT_COLOR, True
            elif batt < _BATT_LOW_V:
                batt_color = _BATT_LOW_COLOR
        self.lbl_metrics.setText(
            cell("alt", alt, "m", "%.2f") + "   "
            + cell("spd", spd, "m/s", "%.1f") + "   "
            + cell("dist", dist, "m", "%.2f") + "   "
            + cell("batt", batt, "V", "%.1f", batt_color, batt_bold))


class DronesPanel(QGroupBox):
    def __init__(self, ids, colors=None, trajs=None, kill_cbk=None):
        super().__init__()
        self.setObjectName("dronesPanel")
        self.setStyleSheet(PANEL_STYLE)
        self.ids = list(ids)
        self.colors = list(colors) if colors else list(_DEFAULT_COLORS)
        self._kill_cbk = kill_cbk
        trajs = list(trajs) if trajs else []

        v = QVBoxLayout(self)
        v.setContentsMargins(2, 2, 2, 2)
        v.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("DRONES")
        title.setStyleSheet("color:#6E7770; font-size:11px; letter-spacing:1.5px; border:none;")
        self.lbl_flight_time = QLabel()
        self.lbl_flight_time.setStyleSheet(
            "color:#8B938F; font-size:12px; border:none;"
            " font-family:'DejaVu Sans Mono','Menlo','Consolas',monospace;")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.lbl_flight_time)
        v.addLayout(header)
        self._set_flight_time(None)

        # no scroll area: every drone stays visible at all times (this
        # panel doubles as pre-flight checklist and in-show health view),
        # the panel simply grows with the number of drones
        self.rows = {}
        rows_box = QWidget()
        rows_box.setStyleSheet("background:transparent; border:none;")
        rows_lay = QVBoxLayout(rows_box)
        rows_lay.setContentsMargins(0, 0, 0, 0)
        rows_lay.setSpacing(8)
        for i, _id in enumerate(self.ids):
            color = self.colors[i % len(self.colors)]
            tname = trajs[i] if i < len(trajs) else ""
            row = _DroneRow(_id, color, tname, kill_cbk=kill_cbk)
            self.rows[_id] = row
            rows_lay.addWidget(row)
        v.addWidget(rows_box)

        self._prev = {}
        self._speed = {}

    def _set_flight_time(self, text):
        self.lbl_flight_time.setText(text if text is not None else "\u2014")

    @staticmethod
    def _checklist_items(ac, now):
        items = []

        # mocap: is the ground->drone EXTERNAL_POSE uplink flowing on the bus
        t_ext = getattr(ac, "t_last_ext_pose", None)
        if t_ext is None:
            items.append(("mocap", "unknown", "no EXTERNAL_POSE seen yet"))
        elif now - t_ext < _MOCAP_STALE_S:
            items.append(("mocap", "ok", "EXTERNAL_POSE flowing"))
        else:
            items.append(("mocap", "bad", f"EXTERNAL_POSE lost {now - t_ext:.0f}s ago"))

        # RC: last rc_status reported by the drone (arming needs RC OK)
        rc = getattr(ac, "rc_status", None)
        arming = getattr(ac, "arming_status", None)
        arming_name = (_ARMING_NAMES[arming]
                       if arming is not None and 0 <= arming < len(_ARMING_NAMES)
                       else "?")
        if rc is None:
            items.append(("RC", "unknown", "no ROTORCRAFT_STATUS seen yet"))
        else:
            state = {0: "ok", 1: "warn"}.get(rc, "bad")
            items.append(("RC", state,
                          f"rc {_RC_STATUS_NAMES.get(rc, rc)}, arming {arming_name}"))

        # link: is the telemetry downlink alive
        t_status = getattr(ac, "t_last_status", None)
        if t_status is None:
            items.append(("link", "unknown", "no ROTORCRAFT_STATUS seen yet"))
        elif now - t_status < _STATUS_STALE_S:
            items.append(("link", "ok", "telemetry alive"))
        else:
            items.append(("link", "bad", f"telemetry lost {now - t_status:.0f}s ago"))

        return items

    @staticmethod
    def _nav_html(ac, now):
        """Flight plan / autopilot state line: what the GCS strip shows.
        e.g.  NAV · Takeoff · motors ON · airborne"""
        # a silent drone must not keep showing its last known state
        # (pool-reused drones would display a stale "motors ON" forever)
        t_status = getattr(ac, "t_last_status", None)
        if t_status is None or now - t_status >= _STATUS_STALE_S:
            return "—"

        parts = []

        mode = getattr(ac, "ap_mode", None)
        if mode is None:
            parts.append("—")
        else:
            name = (_AP_MODE_NAMES[mode] if 0 <= mode < len(_AP_MODE_NAMES)
                    else f"mode {mode}")
            if name in ("KILL", "FAILSAFE"):
                parts.append(f'<span style="color:{_BATT_CRIT_COLOR};'
                             f' font-weight:700;">{name}</span>')
            else:
                parts.append(f'<span style="color:{_VALUE};">{name}</span>')

        cur_block = getattr(ac, "cur_block", None)
        if cur_block is not None:
            names = getattr(getattr(ac, "blocks", None), "names", [])
            block = (names[cur_block] if 0 <= cur_block < len(names)
                     else f"block {cur_block}")
            parts.append(f'<span style="color:{_VALUE};">{block}</span>')

        motors = getattr(ac, "ap_motors_on", None)
        if motors is not None:
            parts.append(f'<span style="color:{_CHECK_COLORS["ok"]};">motors ON</span>'
                         if motors else "motors off")

        in_flight = getattr(ac, "ap_in_flight", None)
        if in_flight is not None:
            parts.append(f'<span style="color:{_VALUE};">airborne</span>'
                         if in_flight else "on ground")

        return " · ".join(parts)

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
            row.set_checklist(self._checklist_items(ac, now))
            row.set_nav(self._nav_html(ac, now))

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