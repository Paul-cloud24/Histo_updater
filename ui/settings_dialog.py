# ui/settings_dialog.py  –  Pipeline-Parameter einstellen

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QDoubleSpinBox, QSpinBox,
    QGroupBox, QFrame
)
from PySide6.QtCore import Qt


class SettingsDialog(QDialog):
    """
    Popup-Dialog für erweiterte Pipeline-Parameter:
      - positive_fraction   (0.0 – 1.0)
      - min_nucleus_area    (px²)
      - use_stardist        (bool → QComboBox)
    """

    def __init__(self, params: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pipeline-Einstellungen")
        self.setMinimumWidth(420)
        self.setModal(True)

        # ── Defaults ──────────────────────────────────────────────────
        self._params = dict(params)   # Kopie, damit Abbrechen nichts kaputt macht

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # ── Gruppe: Klassifikation ────────────────────────────────────
        grp_class = QGroupBox("Klassifikation")
        grid = QGridLayout(grp_class)
        grid.setSpacing(8)

        # positive_fraction
        grid.addWidget(self._label(
            "Positive Fraction",
            "Mindestanteil der Pixel pro Kern, die über dem\n"
            "Threshold liegen müssen, damit der Kern als positiv gilt."
        ), 0, 0)
        self.spin_frac = QDoubleSpinBox()
        self.spin_frac.setRange(0.01, 1.0)
        self.spin_frac.setSingleStep(0.01)
        self.spin_frac.setDecimals(2)
        self.spin_frac.setValue(self._params.get("positive_fraction", 0.10))
        self.spin_frac.setSuffix("  (0–1)")
        grid.addWidget(self.spin_frac, 0, 1)

        layout.addWidget(grp_class)

        # ── Gruppe: Segmentierung ─────────────────────────────────────
        grp_seg = QGroupBox("Segmentierung")
        grid2 = QGridLayout(grp_seg)
        grid2.setSpacing(8)

        # min_nucleus_area
        grid2.addWidget(self._label(
            "Min. Kerngröße (px²)",
            "Mindesfläche eines segmentierten Objekts in Pixel².\n"
            "Kleinere Objekte werden als Rauschen verworfen."
        ), 0, 0)
        self.spin_min_area = QSpinBox()
        self.spin_min_area.setRange(1, 5000)
        self.spin_min_area.setSingleStep(5)
        self.spin_min_area.setValue(self._params.get("min_nucleus_area", 40))
        self.spin_min_area.setSuffix(" px²")
        grid2.addWidget(self.spin_min_area, 0, 1)

        # max_nucleus_area  (neu – bisher nur in Watershed hardcoded)
        grid2.addWidget(self._label(
            "Max. Kerngröße (px²)",
            "Maximale Fläche eines Kerns.\n"
            "Sehr große Objekte (z.B. Zellhaufen) werden verworfen."
        ), 1, 0)
        self.spin_max_area = QSpinBox()
        self.spin_max_area.setRange(100, 100_000)
        self.spin_max_area.setSingleStep(100)
        self.spin_max_area.setValue(self._params.get("max_nucleus_area", 3000))
        self.spin_max_area.setSuffix(" px²")
        grid2.addWidget(self.spin_max_area, 1, 1)

        layout.addWidget(grp_seg)

        # ── Separator ─────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background:#313244; max-height:1px; border:none;")
        layout.addWidget(sep)

        # ── Reset & Buttons ───────────────────────────────────────────
        btn_row = QHBoxLayout()

        btn_reset = QPushButton("↺ Zurücksetzen")
        btn_reset.clicked.connect(self._reset)

        btn_cancel = QPushButton("Abbrechen")
        btn_cancel.clicked.connect(self.reject)

        btn_ok = QPushButton("✔  Übernehmen")
        btn_ok.setObjectName("primary")
        btn_ok.setMinimumHeight(36)
        btn_ok.clicked.connect(self._accept)

        btn_row.addWidget(btn_reset)
        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _label(title: str, tooltip: str = "") -> QLabel:
        lbl = QLabel(title)
        lbl.setToolTip(tooltip)
        lbl.setCursor(Qt.WhatsThisCursor)
        return lbl

    def _reset(self):
        self.spin_frac.setValue(0.10)
        self.spin_min_area.setValue(40)
        self.spin_max_area.setValue(3000)

    def _accept(self):
        self._params["positive_fraction"] = round(self.spin_frac.value(), 3)
        self._params["min_nucleus_area"]   = self.spin_min_area.value()
        self._params["max_nucleus_area"]   = self.spin_max_area.value()
        self.accept()

    def get_params(self) -> dict:
        """Gibt die bestätigten Parameter zurück."""
        return dict(self._params)
