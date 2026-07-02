#!/usr/bin/env python3


import logging
from PySide6.QtWidgets import (QMainWindow, QWidget, QLabel, QPushButton,
                               QProgressBar, QPlainTextEdit, QGroupBox,
                               QVBoxLayout, QHBoxLayout, QFrame, QScrollArea)
from drones_panel import DronesPanel
import view_three_d as vtd

logger = logging.getLogger(__name__)

STYLE = """

    QWidget#root { background-color: #131715; }

    QLabel { color: #E8ECEA; font-size: 13px; }
    QLabel#appTitle    { color: #FFFFFF; font-size: 18px; font-weight: 600; }
    QLabel#appSubtitle { color: #8B938F; font-size: 11px; }
    QLabel#scenName    { color: #E8ECEA; font-size: 13px; font-weight: 600; }
    QLabel#scenInfo    { color: #8B938F; font-size: 11px; }

    QGroupBox {
        background-color: #1B201D;
        border: 1px solid #2A312D;
        border-radius: 6px;
        margin-top: 10px;
        padding: 10px;
        font-size: 11px;
        font-weight: 600;
        color: #6E7770;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 10px;
        padding: 2px 6px;
        color: #6E7770;
    }
    QGroupBox#compact { margin-top: 8px; padding: 8px; }

    QPushButton {
        background-color: #232925;
        color: #E8ECEA;
        border: 1px solid #353D38;
        border-radius: 6px;
        padding: 8px 12px;
        font-size: 13px;
        font-weight: 600;
    }
    QPushButton:hover   { background-color: #2B322D; }
    QPushButton:pressed { background-color: #1C211E; }
    QPushButton:disabled {
        background-color: #1A1F1C; color: #565E59; border: 1px solid #262C28;
    }

    /* Primary button: launch the show */
    QPushButton#primary {
        background-color: #E8ECEA; border: 1px solid #E8ECEA;
        color: #131715; font-size: 14px; padding: 8px;
    }
    QPushButton#primary:hover    { background-color: #FFFFFF; }
    QPushButton#primary:disabled {
        background-color: #2A312D; border: 1px solid #2A312D; color: #565E59;
    }

    /* Stop button: graceful stop (back to NAV mode) */
    QPushButton#warning {
        background-color: #232925; border: 1px solid #353D38; color: #C7D0CB;
    }
    QPushButton#warning:hover    { background-color: #2B322D; }
    QPushButton#warning:disabled {
        background-color: #1A1F1C; color: #565E59; border: 1px solid #262C28;
    }

    QProgressBar {
        background-color: #0E110F; border: 1px solid #2A312D;
        border-radius: 5px; height: 10px; text-align: center;
        color: #8B938F; font-size: 11px;
    }
    QProgressBar::chunk { background-color: #8B938F; border-radius: 4px; }

    QPlainTextEdit {
        background-color: #0E110F; color: #C7D0CB;
        border: 1px solid #2A312D; border-radius: 6px;
        font-family: "DejaVu Sans Mono", "Menlo", "Consolas", monospace;
        font-size: 12px; padding: 6px;
    }
"""


class OperatorWindow(QMainWindow):

    def __init__(self, app_controller, model, fd):
        super().__init__()
        self.app = app_controller
        self.model = model
        self.fd = fd

        self.setWindowTitle("Click'n Fly - Operator Control Center")
        self.resize(1200, 760)

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)
        outer.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setSpacing(10)

        # left: 3D view (clone of the spectator view) + console below
        left = QVBoxLayout()
        left.setSpacing(10)
        self.tdw = vtd.ThreeDWidget(self.model)
        for i in range(self.model.trajectory_nb()):
            self.tdw.display_new_trajectory(self.model, i, show_details=False,
                                            show_quad=True, show_ref_quad=True)
        left.addWidget(self.tdw, stretch=1)
        left.addWidget(self._build_console_group())
        body.addLayout(left, stretch=3)

        # right: column of panels
        panels = QVBoxLayout()
        panels.setSpacing(10)
        panels.addWidget(self._build_scenario_group())
        colors = ['#%02X%02X%02X' % (int(c[0] * 255), int(c[1] * 255), int(c[2] * 255))
                  for c in vtd.TrajItem._colors]

        trajs = [self.model.get_trajectory(i).name
                 for i in range(self.model.trajectory_nb())]

        self.drones_panel = DronesPanel(self.fd.ids, colors, trajs)
        panels.addWidget(self.drones_panel)
        panels.addWidget(self._build_safety_group())
        panels.addWidget(self._build_controls_group())
        panels.addStretch(1)

        right = QWidget()
        right.setMinimumWidth(300)
        right.setLayout(panels)
        body.addWidget(right)

        outer.addLayout(body, stretch=1)

        self.setStyleSheet(STYLE)
        self._set_safety_state("Unverified", "warn")

    def closeEvent(self, event):
        self.app.on_quit()
        event.accept()

    def _build_header(self):
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        title = QLabel("CLICK'N FLY")
        title.setObjectName("appTitle")
        subtitle = QLabel("Operator Control Center")
        subtitle.setObjectName("appSubtitle")
        v.addWidget(title)
        v.addWidget(subtitle)
        return box

    def _build_scenario_group(self):
        group = QGroupBox("SHOW CONFIGURATION")
        group.setObjectName("compact")
        v = QVBoxLayout(group)
        v.setSpacing(2)

        scen = getattr(self.app, "scenario", None)
        scen_name = scen.__class__.__name__ if scen is not None else "?"
        ids = list(getattr(scen, "ids", []) or [])

        self.label_scen = QLabel(scen_name)
        self.label_scen.setObjectName("scenName")

        info = QLabel(f"{len(ids)} drone(s)   |   IDs: "
                      f"{', '.join(str(i) for i in ids) if ids else '-'}")
        info.setObjectName("scenInfo")

        v.addWidget(self.label_scen)
        v.addWidget(info)
        return group

    def _build_safety_group(self):
        group = QGroupBox("SAFETY CHECK")
        v = QVBoxLayout(group)
        v.setSpacing(10)

        self.btn_check_safety = QPushButton("Trajectory analysis "
                                            "& collision avoidance")
        self.btn_check_safety.clicked.connect(self.run_safety_check)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(QLabel("Status:"))
        self.label_safety_status = QLabel("Unverified")
        row.addWidget(self.label_safety_status)
        row.addStretch(1)

        v.addWidget(self.btn_check_safety)
        v.addLayout(row)
        return group

    def _build_controls_group(self):
        group = QGroupBox("FLIGHT CONTROLS")
        group.setObjectName("compact")
        v = QVBoxLayout(group)
        v.setSpacing(8)

        self.button_guide = QPushButton("LAUNCH SHOW")
        self.button_guide.setObjectName("primary")
        self.button_guide.setEnabled(False)
        self.button_guide.clicked.connect(self.app.on_guide_clicked)

        self.button_restart = QPushButton("Restart Show")
        self.button_restart.setEnabled(False)
        self.button_restart.clicked.connect(self.app.on_restart_clicked)

        self.button_stop = QPushButton("Stop Show")
        self.button_stop.setObjectName("warning")
        self.button_stop.setEnabled(False)
        self.button_stop.clicked.connect(self.app.on_stop_clicked)

        self.progress = QProgressBar()
        self.progress.setValue(0)


        v.addWidget(self.button_guide)
        v.addWidget(self.button_restart)
        v.addWidget(self.button_stop)
        v.addWidget(self.progress)
        return group

    def _build_console_group(self):
        group = QGroupBox("PAPARAZZI TELEMETRY CONSOLE")
        v = QVBoxLayout(group)
        self.textedit_wid = QPlainTextEdit()
        self.textedit_wid.setReadOnly(True)
        self.textedit_wid.setMaximumBlockCount(500)  # avoid unbounded growth
        v.addWidget(self.textedit_wid)
        return group

    def _set_safety_state(self, text, kind):
        """kind: 'warn' (pending, neutral) | 'ok' (neutral) | 'err' (red)."""
        palette = {
            "warn": ("transparent", "#8B938F"),
            "ok":   ("transparent", "#C7D0CB"),
            "err":  ("#3A1518", "#F85149"),
        }
        bg, fg = palette.get(kind, palette["warn"])
        self.label_safety_status.setText(text)
        self.label_safety_status.setStyleSheet(
            f"background-color:{bg}; color:{fg}; border-radius:4px;"
            f"padding:2px 6px; font-weight:600;")


    """ def run_safety_check(self):
        self.log_text("Trajectory analysis in progress...")
        self.model.resolve_conflicts(safety_distance=1.0, delay_increment=2.0)
        self._set_safety_state("Anti-collision applied", "ok")
        self.button_guide.setEnabled(True)
        self.log_text("0 conflict detected. Ready for take-off.") """

    def run_safety_check(self):
        self.log_text("Trajectory analysis in progress...")
        # >>> MODIF (TEST repulsion) : NO delay-based resolution.
        # Leave the planned conflicts in so they reach the controller and the
        # reactive avoidance actually has something to push apart.
        conflicts = self.model.detect_conflicts(safety_distance=1.0)
        if conflicts:
            self._set_safety_state(
                f"{len(conflicts)} planned conflict(s) - reactive only", "warn")
            self.log_text(
                f"{len(conflicts)} conflict(s) left in on purpose (delays disabled).")
        else:
            self._set_safety_state("No planned conflict", "ok")
            self.log_text("0 conflict detected.")
        self.button_guide.setEnabled(True)
        # self.model.resolve_conflicts(safety_distance=1.0, delay_increment=2.0)  # disabled for test

    def show_progress(self, value):
        self.progress.setValue(value)

    def log_text(self, txt):
        self.textedit_wid.appendPlainText(txt)