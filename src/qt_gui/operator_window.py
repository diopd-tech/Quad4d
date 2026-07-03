#!/usr/bin/env python3


import logging
from PySide6.QtWidgets import (QMainWindow, QWidget, QLabel, QPushButton,
                               QProgressBar, QPlainTextEdit, QGroupBox,
                               QVBoxLayout, QHBoxLayout, QFrame, QScrollArea)
from drones_panel import DronesPanel
import view_three_d as vtd
import view_chronograms as view_chrono

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

    QMenuBar { background-color: #131715; color: #C7D0CB; }
    QMenuBar::item { background: transparent; padding: 4px 10px; }
    QMenuBar::item:selected { background-color: #232925; border-radius: 4px; }
    QMenu { background-color: #1B201D; color: #E8ECEA; border: 1px solid #2A312D; }
    QMenu::item { padding: 6px 20px; }
    QMenu::item:selected { background-color: #232925; }
"""


class OperatorWindow(QMainWindow):

    def __init__(self, app_controller, model, fd):
        super().__init__()
        self.app = app_controller
        self.model = model
        self.fd = fd

        self.setWindowTitle("Click'n Fly - Operator Control Center")
        self.resize(1200, 760)

        scen_menu = self.menuBar().addMenu("Scenario")
        change_scen_action = scen_menu.addAction("Change scenario...")
        change_scen_action.triggered.connect(self.app.on_change_scenario_clicked)

        # Chronograms: reuse the editor's plot widgets. They show the planned
        # trajectory profile (position/velocity/attitude over time), computed
        # from the model, in separate windows toggled from the View menu.
        self._chrono_windows = {}
        self._chrono_specs = {
            'full_state_chrono': (view_chrono.FullStateChronogram, 'Full state chronogram'),
        }
        view_menu = self.menuBar().addMenu("View")
        for key, (_cls, title) in self._chrono_specs.items():
            act = view_menu.addAction(title)
            act.setCheckable(True)
            act.toggled.connect(lambda checked, k=key: self._toggle_chronogram(k, checked))

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
        body.addLayout(left, stretch=4)

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
        right.setMinimumWidth(360)
        right.setLayout(panels)
        body.addWidget(right, stretch=1)

        outer.addLayout(body, stretch=1)

        self.setStyleSheet(STYLE)
        self._set_safety_state("Unverified", "warn")

    def _open_chronogram(self, key):
        cls, title = self._chrono_specs[key]
        win = view_chrono.ChronogramWindow(cls, title)
        for i in range(self.model.trajectory_nb()):
            win.display_new_trajectory(self.model, idx=i)
        self._chrono_windows[key] = win
        win.show()
        win.raise_()

    def _toggle_chronogram(self, key, checked):
        # always tear down and rebuild fresh: the chronogram widgets add new
        # plot lines on each display_new_trajectory, so reusing a window would
        # accumulate stale lines across scenario changes
        existing = self._chrono_windows.pop(key, None)
        if existing is not None:
            existing.close()
        if checked:
            self._open_chronogram(key)

    def _refresh_chronograms(self):
        for key in list(self._chrono_windows.keys()):
            win = self._chrono_windows.pop(key)
            visible = win.isVisible()
            win.close()
            if visible:
                self._open_chronogram(key)

    def closeEvent(self, event):
        for win in self._chrono_windows.values():
            win.close()
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

        self.label_scen = QLabel()
        self.label_scen.setObjectName("scenName")

        self.label_scen_info = QLabel()
        self.label_scen_info.setObjectName("scenInfo")

        v.addWidget(self.label_scen)
        v.addWidget(self.label_scen_info)
        self._update_scenario_labels(getattr(self.app, "scenario", None))
        return group

    def _update_scenario_labels(self, scen):
        if scen is not None:
            scen_name = getattr(scen, "name", None) or scen.__class__.__name__
            if getattr(scen, "desc", None):
                scen_name += f" — {scen.desc}"
        else:
            scen_name = "?"
        ids = list(getattr(scen, "ids", []) or [])
        self.label_scen.setText(scen_name)
        self.label_scen_info.setText(
            f"{len(ids)} drone(s)   |   IDs: "
            f"{', '.join(str(i) for i in ids) if ids else '-'}")

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

        self.button_stop = QPushButton("Stop Show")
        self.button_stop.setObjectName("warning")
        self.button_stop.setEnabled(False)
        self.button_stop.clicked.connect(self.app.on_stop_clicked)

        self.progress = QProgressBar()
        self.progress.setValue(0)


        v.addWidget(self.button_guide)
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

    def load_show(self, model, fd, scenario):
        """Swap in a different model/flight director (used when the
        operator changes scenario at runtime, after the current show
        has been stopped)."""
        self.model, self.fd = model, fd

        self.tdw.set_trajectories(model, show_details=False,
                                  show_quad=True, show_ref_quad=True)

        colors = ['#%02X%02X%02X' % (int(c[0] * 255), int(c[1] * 255), int(c[2] * 255))
                  for c in vtd.TrajItem._colors]
        trajs = [model.get_trajectory(i).name for i in range(model.trajectory_nb())]
        self._replace_drones_panel(fd.ids, colors, trajs)

        self._update_scenario_labels(scenario)
        self._refresh_chronograms()
        self._reset_controls()

    def _replace_drones_panel(self, ids, colors, trajs):
        layout = self.drones_panel.parentWidget().layout()
        idx = layout.indexOf(self.drones_panel)
        old_panel = self.drones_panel
        self.drones_panel = DronesPanel(ids, colors, trajs)
        layout.insertWidget(idx, self.drones_panel)
        layout.removeWidget(old_panel)
        old_panel.deleteLater()

    def _reset_controls(self):
        self.button_guide.setEnabled(False)
        self.button_stop.setEnabled(False)
        self.progress.setValue(0)
        self._set_safety_state("Unverified", "warn")