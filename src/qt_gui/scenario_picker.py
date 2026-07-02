#!/usr/bin/env python3

import logging
from PySide6.QtWidgets import (QDialog, QWidget, QLabel, QPushButton, QSpinBox,
                               QVBoxLayout, QHBoxLayout, QListWidget, QGroupBox,
                               QScrollArea)

logger = logging.getLogger(__name__)

STYLE = """
    QDialog { background-color: #131715; }
    QLabel { color: #E8ECEA; font-size: 13px; }
    QLabel#title { color: #FFFFFF; font-size: 16px; font-weight: 600; }
    QLabel#scenInfo { color: #8B938F; font-size: 12px; }

    QListWidget {
        background-color: #1B201D; border: 1px solid #2A312D;
        border-radius: 6px; color: #E8ECEA; font-size: 12px; padding: 4px;
    }
    QListWidget::item { padding: 7px 8px; border-radius: 4px; color: #B7BEB9; }
    QListWidget::item:hover { background-color: #232925; }
    QListWidget::item:selected {
        background-color: #3A423D; color: #FFFFFF;
        border-left: 3px solid #E8ECEA;
    }

    QGroupBox {
        background-color: #1B201D; border: 1px solid #2A312D;
        border-radius: 6px; margin-top: 10px; padding: 10px;
        font-size: 11px; font-weight: 600; color: #6E7770;
    }
    QGroupBox::title {
        subcontrol-origin: margin; subcontrol-position: top left;
        left: 10px; padding: 2px 6px; color: #6E7770;
    }

    QSpinBox {
        background-color: #232925; color: #E8ECEA;
        border: 1px solid #353D38; border-radius: 5px; padding: 3px 4px;
    }

    QPushButton {
        background-color: #232925; color: #E8ECEA;
        border: 1px solid #353D38; border-radius: 6px;
        padding: 8px 16px; font-size: 13px; font-weight: 600;
    }
    QPushButton:hover { background-color: #2B322D; }
    QPushButton:pressed { background-color: #1C211E; }
    QPushButton#primary {
        background-color: #E8ECEA; border: 1px solid #E8ECEA; color: #131715;
    }
    QPushButton#primary:hover { background-color: #FFFFFF; }
"""


class ScenarioResult:
    """Everything Application needs to start a show, independent of how
    it was put together (a predefined Scenario class or a future
    custom-built one)."""
    def __init__(self, name, desc, ids, trajs, arena=None):
        self.name, self.desc, self.ids, self.trajs = name, desc, list(ids), list(trajs)
        if arena is not None:
            self.arena = arena


class ScenarioPickerDialog(QDialog):
    """Modal dialog shown at startup: pick one of the predefined
    scenarios and optionally remap which physical drone ID plays
    which role in it."""

    def __init__(self, scenarios, preselect=0, parent=None):
        super().__init__(parent)
        self.scenarios = scenarios
        self._id_spins = []

        self.setWindowTitle("Click'n Fly - Select scenario")
        self.resize(720, 440)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(10)

        title = QLabel("SELECT SCENARIO")
        title.setObjectName("title")
        outer.addWidget(title)

        body = QHBoxLayout()
        body.setSpacing(10)

        self.list = QListWidget()
        for cls in scenarios:
            label = cls.__name__
            desc = getattr(cls, "desc", None)
            if desc:
                label += f" — {desc}"
            label += f"   ({len(cls.ids)} drone(s))"
            self.list.addItem(label)
        self.list.setMinimumWidth(300)
        self.list.currentRowChanged.connect(self._on_selection_changed)
        body.addWidget(self.list, stretch=1)

        self.detail_group = QGroupBox("DRONES")
        self.detail_layout = QVBoxLayout(self.detail_group)
        self.detail_layout.setSpacing(6)
        detail_scroll = QScrollArea()
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setWidget(self.detail_group)
        detail_scroll.setStyleSheet("QScrollArea { border:none; background:transparent; }")
        body.addWidget(detail_scroll, stretch=1)

        outer.addLayout(body, stretch=1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.button_quit = QPushButton("Quit")
        self.button_quit.clicked.connect(self.reject)
        self.button_start = QPushButton("Start")
        self.button_start.setObjectName("primary")
        self.button_start.clicked.connect(self.accept)
        buttons.addWidget(self.button_quit)
        buttons.addWidget(self.button_start)
        outer.addLayout(buttons)

        self.setStyleSheet(STYLE)

        preselect = preselect if 0 <= preselect < len(scenarios) else 0
        self.list.setCurrentRow(preselect)

    def _on_selection_changed(self, row):
        while self.detail_layout.count():
            item = self.detail_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._id_spins = []

        if row < 0:
            return
        cls = self.scenarios[row]
        for _id, traj in zip(cls.ids, cls.trajs):
            row_box = QHBoxLayout()
            spin = QSpinBox()
            spin.setRange(0, 999)
            spin.setValue(_id)
            spin.setFixedWidth(70)
            traj_lbl = QLabel(traj)
            traj_lbl.setObjectName("scenInfo")
            traj_lbl.setWordWrap(True)
            row_box.addWidget(spin)
            row_box.addWidget(traj_lbl, stretch=1)
            self._id_spins.append(spin)
            container = QWidget()
            container.setLayout(row_box)
            self.detail_layout.addWidget(container)
        self.detail_layout.addStretch(1)

    def get_scenario(self):
        cls = self.scenarios[self.list.currentRow()]
        ids = [spin.value() for spin in self._id_spins]
        return ScenarioResult(
            name=cls.__name__,
            desc=getattr(cls, "desc", None),
            ids=ids,
            trajs=cls.trajs,
            arena=getattr(cls, "arena", None),
        )
