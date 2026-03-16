# ui/app.py — PySide6, Dark Theme (Catppuccin Mocha)

import os
import sys
import random
import numpy as np

from PySide6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QProgressBar, QTextEdit, QGroupBox,
    QComboBox, QStatusBar, QFileDialog, QFrame, QDialog, QMessageBox,
    QSizePolicy
)
from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtGui import QFont, QTextCursor

from stains import available_stains, get_stain
from ui.analysis_worker import Sox9Worker
from ui.batch_worker import BatchWorker
from ui.threshold_dialog import ThresholdDialog
from ui.roi_dialog import ROIDialog
from analysis.sox9_pipeline import find_images_in_folder
from analysis.batch_runner import find_sox9_folders

# ── Stylesheet ────────────────────────────────────────────────────────
STYLESHEET = """
* {
    font-family: 'Segoe UI', system-ui, sans-serif;
    font-size: 13px;
}
QMainWindow, QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
}
QGroupBox {
    border: 1px solid #313244;
    border-radius: 8px;
    margin-top: 14px;
    padding: 10px 8px 8px 8px;
    font-weight: 600;
    color: #89b4fa;
    font-size: 12px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
}
QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 7px 14px;
    text-align: left;
}
QPushButton:hover {
    background-color: #45475a;
    border-color: #89b4fa;
    color: #ffffff;
}
QPushButton:pressed {
    background-color: #585b70;
}
QPushButton:disabled {
    background-color: #1e1e2e;
    color: #45475a;
    border-color: #313244;
}
QPushButton#primary {
    background-color: #89b4fa;
    color: #1e1e2e;
    font-weight: 700;
    font-size: 14px;
    border: none;
    text-align: center;
    border-radius: 8px;
}
QPushButton#primary:hover {
    background-color: #b4befe;
}
QPushButton#primary:disabled {
    background-color: #313244;
    color: #585b70;
}
QPushButton#success {
    background-color: #a6e3a1;
    color: #1e1e2e;
    font-weight: 600;
    border: none;
    text-align: left;
}
QPushButton#success:hover {
    background-color: #94e2d5;
}
QPushButton#warning {
    background-color: #fab387;
    color: #1e1e2e;
    font-weight: 600;
    border: none;
    text-align: left;
}
QComboBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 10px;
    min-height: 28px;
}
QComboBox:hover { border-color: #89b4fa; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    selection-background-color: #45475a;
    outline: none;
}
QProgressBar {
    background-color: #313244;
    border: none;
    border-radius: 4px;
    max-height: 6px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background-color: #89b4fa;
    border-radius: 4px;
}
QProgressBar#tile_bar::chunk {
    background-color: #a6e3a1;
}
QTextEdit {
    background-color: #11111b;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 6px;
    font-family: 'Cascadia Code', 'Consolas', 'Courier New', monospace;
    font-size: 12px;
    padding: 6px;
    selection-background-color: #45475a;
}
QStatusBar {
    background-color: #181825;
    color: #6c7086;
    font-size: 11px;
    border-top: 1px solid #313244;
    padding: 2px 8px;
}
QLabel#header {
    font-size: 20px;
    font-weight: 700;
    color: #cdd6f4;
    letter-spacing: 1px;
}
QLabel#subheader {
    font-size: 11px;
    color: #6c7086;
    letter-spacing: 2px;
}
QLabel#section {
    font-size: 11px;
    font-weight: 600;
    color: #6c7086;
    letter-spacing: 1px;
    text-transform: uppercase;
}
QLabel#info {
    color: #a6adc8;
    font-size: 12px;
}
QFrame#separator {
    background-color: #313244;
    max-height: 1px;
    border: none;
}
QFrame#sidebar {
    background-color: #181825;
    border-right: 1px solid #313244;
}
"""


class HistologyUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.threadpool        = QThreadPool()
        self.confirmed_threshold = 60
        self.folder            = None
        self._use_roi          = False
        self._roi_points       = None
        self._batch_worker     = None

        self.setWindowTitle("Histo Analyzer")
        self.setMinimumSize(960, 680)

        # Statusleiste
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._set_status("Bereit", "idle")

        # Hauptlayout
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Sidebar ───────────────────────────────────────────────────
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(270)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 20, 16, 16)
        sidebar_layout.setSpacing(4)

        # Logo
        lbl_logo = QLabel("🔬 HISTO")
        lbl_logo.setObjectName("header")
        lbl_sub  = QLabel("ANALYZER  ·  v2.0")
        lbl_sub.setObjectName("subheader")
        sidebar_layout.addWidget(lbl_logo)
        sidebar_layout.addWidget(lbl_sub)
        sidebar_layout.addSpacing(16)
        sidebar_layout.addWidget(self._separator())

        # Färbung
        sidebar_layout.addSpacing(12)
        sidebar_layout.addWidget(self._section_label("Färbung"))
        self.stain_box = QComboBox()
        self.stain_box.addItems(available_stains())
        self.stain_box.currentTextChanged.connect(self._on_stain_changed)
        sidebar_layout.addWidget(self.stain_box)

        # Ordner
        sidebar_layout.addSpacing(12)
        sidebar_layout.addWidget(self._section_label("Ordner"))
        self.folder_label = QLabel("Kein Ordner gewählt")
        self.folder_label.setObjectName("info")
        self.folder_label.setWordWrap(True)
        btn_folder = QPushButton("📁   Ordner wählen")
        btn_folder.clicked.connect(self._select_folder)
        sidebar_layout.addWidget(btn_folder)
        sidebar_layout.addWidget(self.folder_label)

        # Einstellungen
        sidebar_layout.addSpacing(12)
        sidebar_layout.addWidget(self._section_label("Einstellungen"))

        self.btn_threshold = QPushButton("🔬   Threshold einstellen...")
        self.btn_threshold.clicked.connect(self._open_threshold_dialog)
        self.threshold_info = QLabel(f"Threshold: {self.confirmed_threshold}")
        self.threshold_info.setObjectName("info")

        self.btn_roi = QPushButton("📐   ROI einzeichnen...")
        self.btn_roi.clicked.connect(self._open_roi_dialog)

        self.btn_roi_mode = QPushButton("🔍   Modus: Ganzes Bild")
        self.btn_roi_mode.clicked.connect(self._toggle_roi_mode)

        for w in [self.btn_threshold, self.threshold_info,
                  self.btn_roi, self.btn_roi_mode]:
            sidebar_layout.addWidget(w)

        sidebar_layout.addStretch()
        sidebar_layout.addWidget(self._separator())
        sidebar_layout.addSpacing(8)

        # Analyse-Button
        self.btn_analyze = QPushButton("▶   Analyse starten")
        self.btn_analyze.setObjectName("primary")
        self.btn_analyze.setMinimumHeight(44)
        self.btn_analyze.clicked.connect(self._start_analysis)
        sidebar_layout.addWidget(self.btn_analyze)

        # ── Hauptbereich ──────────────────────────────────────────────
        main_area = QWidget()
        main_layout = QVBoxLayout(main_area)
        main_layout.setContentsMargins(20, 20, 20, 16)
        main_layout.setSpacing(12)

        # Log
        log_label = QLabel("Analyse-Log")
        log_label.setObjectName("section")
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText(
            "Der Analyse-Log erscheint hier...\n\n"
            "1. Ordner wählen\n"
            "2. Färbung auswählen\n"
            "3. Optional: Threshold und ROI einstellen\n"
            "4. Analyse starten"
        )
        main_layout.addWidget(log_label)
        main_layout.addWidget(self.log_view, stretch=1)

        # Fortschritt
        progress_group = QGroupBox("Fortschritt")
        pg_layout = QVBoxLayout(progress_group)
        pg_layout.setSpacing(6)

        self.label_global = QLabel("Gesamt  0%")
        self.label_global.setObjectName("info")
        self.progress_global = QProgressBar()
        self.progress_global.setValue(0)

        self.label_current = QLabel("Aktueller Schritt  0%")
        self.label_current.setObjectName("info")
        self.progress_current = QProgressBar()
        self.progress_current.setObjectName("tile_bar")
        self.progress_current.setValue(0)

        pg_layout.addWidget(self.label_global)
        pg_layout.addWidget(self.progress_global)
        pg_layout.addSpacing(4)
        pg_layout.addWidget(self.label_current)
        pg_layout.addWidget(self.progress_current)
        main_layout.addWidget(progress_group)

        root.addWidget(sidebar)
        root.addWidget(main_area, stretch=1)

        # Initial Stain-abhängige Buttons
        self._on_stain_changed(self.stain_box.currentText())

    # ── Helpers ───────────────────────────────────────────────────────
    def _separator(self):
        f = QFrame()
        f.setObjectName("separator")
        f.setFrameShape(QFrame.HLine)
        return f

    def _section_label(self, text):
        lbl = QLabel(text.upper())
        lbl.setObjectName("section")
        return lbl

    def _set_status(self, msg, state="idle"):
        colors = {
            "idle":    "#6c7086",
            "running": "#89b4fa",
            "ok":      "#a6e3a1",
            "error":   "#f38ba8",
        }
        color = colors.get(state, "#6c7086")
        self.status_bar.setStyleSheet(
            f"QStatusBar {{ background: #181825; color: {color}; "
            f"font-size: 11px; border-top: 1px solid #313244; padding: 2px 8px; }}"
        )
        self.status_bar.showMessage(msg)

    def _log(self, msg, color=None):
        """Fügt eine Zeile zum Log hinzu, optional eingefärbt."""
        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.End)

        if "✔" in msg or "Fertig" in msg:
            color = "#a6e3a1"
        elif "✗" in msg or "Fehler" in msg or "Error" in msg:
            color = "#f38ba8"
        elif "⚠" in msg or "Warnung" in msg:
            color = "#fab387"
        elif msg.startswith("──"):
            color = "#89b4fa"

        if color:
            self.log_view.append(
                f'<span style="color:{color};">{msg}</span>'
            )
        else:
            self.log_view.append(msg)

        self.log_view.ensureCursorVisible()

    # ── Ordner ────────────────────────────────────────────────────────
    def _select_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Ordner wählen")
        if path:
            self.folder = path
            short = os.path.basename(path)
            self.folder_label.setText(f"📂 {short}")
            self.folder_label.setToolTip(path)
            self._set_status(f"Ordner: {short}", "idle")

    # ── Stain-abhängige UI ────────────────────────────────────────────
    def _on_stain_changed(self, name):
        is_sox9 = name == "Sox9/DAPI"
        for w in [self.btn_threshold, self.threshold_info,
                  self.btn_roi, self.btn_roi_mode]:
            w.setVisible(is_sox9)

    # ── Threshold ─────────────────────────────────────────────────────
    def _open_threshold_dialog(self):
        if not self.folder:
            QMessageBox.warning(self, "Fehler", "Bitte zuerst Ordner wählen.")
            return
        dlg = ThresholdDialog(
            folder=self.folder,
            initial_threshold=self.confirmed_threshold,
            parent=self
        )
        if dlg.exec() == QDialog.Accepted:
            self.confirmed_threshold = dlg.confirmed_threshold
            self.threshold_info.setText(f"Threshold: {self.confirmed_threshold}")
            self._log(f"Threshold gesetzt: {self.confirmed_threshold}")

    # ── ROI ───────────────────────────────────────────────────────────
    def _open_roi_dialog(self):
        dapi_path = self._find_dapi_path()
        if not dapi_path:
            return
        dlg = ROIDialog(dapi_path, parent=self)
        dlg.roi_confirmed.connect(self._on_roi_confirmed)
        dlg.exec()

    def _on_roi_confirmed(self, points):
        self._roi_points = points
        self.btn_roi.setText(f"📐   ROI ✓  ({len(points)} Punkte)")
        self.btn_roi.setObjectName("success")
        self.btn_roi.style().unpolish(self.btn_roi)
        self.btn_roi.style().polish(self.btn_roi)
        self._log(f"ROI gesetzt: {len(points)} Punkte")

    def _toggle_roi_mode(self):
        self._use_roi = not self._use_roi
        if self._use_roi:
            self.btn_roi_mode.setText("✂️   Modus: Mit ROI")
            self.btn_roi_mode.setObjectName("success")
        else:
            self.btn_roi_mode.setText("🔍   Modus: Ganzes Bild")
            self.btn_roi_mode.setObjectName("")
        self.btn_roi_mode.style().unpolish(self.btn_roi_mode)
        self.btn_roi_mode.style().polish(self.btn_roi_mode)

    def _find_dapi_path(self):
        if not self.folder:
            QMessageBox.warning(self, "Fehler", "Bitte zuerst Ordner wählen.")
            return None
        try:
            _, dapi_path = find_images_in_folder(self.folder)
            return dapi_path
        except Exception:
            # Unterordner probieren
            folders = find_sox9_folders(self.folder)
            if folders:
                try:
                    _, dapi_path = find_images_in_folder(folders[0])
                    return dapi_path
                except Exception:
                    pass
        QMessageBox.warning(self, "Fehler", "Kein DAPI-Bild gefunden.")
        return None

    # ── Analyse ───────────────────────────────────────────────────────
    def _start_analysis(self):
        if not self.folder:
            QMessageBox.warning(self, "Fehler", "Bitte Ordner wählen.")
            return

        stain_name = self.stain_box.currentText()

        # Nicht implementierte Färbungen abfangen
        if stain_name != "Sox9/DAPI":
            try:
                stain = get_stain(stain_name)
                stain.analyze(None, None, None)
            except NotImplementedError as e:
                QMessageBox.information(
                    self, "In Entwicklung",
                    f"'{stain_name}' ist noch nicht implementiert.\n\n"
                    f"Aktuell verfügbar: Sox9/DAPI"
                )
            return

        self.run_sox9_analysis()

    def run_sox9_analysis(self):
        folders = find_sox9_folders(self.folder)

        if not folders:
            self._run_single()
            return

        reply = QMessageBox.question(
            self, "Batch-Analyse",
            f"{len(folders)} Sox9-Unterordner gefunden.\nAlle analysieren?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self._start_batch(folders)

    def _run_single(self):
        self.log_view.clear()
        self._set_status("Analyse läuft...", "running")
        self.btn_analyze.setEnabled(False)

        worker = Sox9Worker(
            folder=self.folder,
            threshold=self.confirmed_threshold
        )
        worker.signals.progress_global.connect(self._on_global_progress)
        worker.signals.progress_tile.connect(self._on_tile_progress)
        worker.signals.finished.connect(self._on_single_finished)
        self.threadpool.start(worker)

    def _start_batch(self, folders):
        self.log_view.clear()
        self.progress_global.setValue(0)
        self.progress_current.setValue(0)
        self.btn_analyze.setEnabled(False)
        self._set_status(f"Batch: {len(folders)} Ordner...", "running")

        self._batch_worker = BatchWorker(
            root_folder=self.folder,
            threshold=self.confirmed_threshold,
            use_roi=self._use_roi,
        )
        self._batch_worker.signals.progress.connect(self._on_global_progress)
        self._batch_worker.signals.log.connect(self._log)
        self._batch_worker.signals.folder_done.connect(self._on_folder_done)
        self._batch_worker.signals.folder_error.connect(self._on_folder_error)
        self._batch_worker.signals.finished.connect(self._on_batch_finished)
        self.threadpool.start(self._batch_worker)

    # ── Callbacks ─────────────────────────────────────────────────────
    def _on_global_progress(self, val):
        self.progress_global.setValue(val)
        self.label_global.setText(f"Gesamt  {val}%")

    def _on_tile_progress(self, val):
        self.progress_current.setValue(val)
        self.label_current.setText(f"Aktueller Schritt  {val}%")

    def _on_single_finished(self, text):
        self.btn_analyze.setEnabled(True)
        self.progress_global.setValue(100)
        self._set_status("✔ Analyse abgeschlossen", "ok")
        self._log(f"✔ {text}")

    def _on_folder_done(self, name, result):
        self.progress_current.setValue(100)
        self._set_status(f"✔ {name}", "running")

    def _on_folder_error(self, name, error):
        self._log(f"✗ {name}: {error}")
        self._set_status(f"✗ Fehler: {name}", "error")

    def _on_batch_finished(self, csv_path, plot_path):
        self.btn_analyze.setEnabled(True)
        self.progress_global.setValue(100)
        self._set_status("✔ Batch abgeschlossen", "ok")
        self._log("── Batch-Analyse abgeschlossen ──")
        if csv_path:
            self._log(f"✔ CSV:  {csv_path}")
        if plot_path:
            self._log(f"✔ Plot: {plot_path}")
        QMessageBox.information(
            self, "Fertig",
            f"Batch-Analyse abgeschlossen!\n\n"
            f"Ergebnisse in:\n{self.folder}/Results/"
        )


def run_ui():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    ui = HistologyUI()
    ui.show()
    sys.exit(app.exec())