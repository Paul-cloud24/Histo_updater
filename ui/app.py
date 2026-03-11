import os
import random
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QVBoxLayout,
    QHBoxLayout, QFileDialog, QComboBox, QMessageBox,
    QProgressBar, QSlider, QGroupBox,QDialog
)
from PyQt5.QtCore import Qt, QThreadPool
from PyQt5.QtGui import QPixmap, QImage
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import io
from PIL import Image

from stains import col1, col2, safranin_o, tunel
from ui.analysis_worker import Sox9Worker
from ui.dl_worker import DLWorker
from analysis.channel_detection import extract_channels
from ui.threshold_dialog import ThresholdDialog

STAIN_MAP = {
    "Col1": col1.get_model,
    "Col2": col2.get_model,
    "Safranin O": safranin_o.get_model,
    "TUNEL": tunel.get_model,
}


class HistologyUI(QWidget):
    def __init__(self):
        super().__init__()
        self.threadpool = QThreadPool()
        self.threshold = 10000
        self.confirmed_threshold = 10000
        self.current_preview_path = None

        self.setWindowTitle("Histology Analysis – UI")
        self.setGeometry(200, 200, 700, 850)

        layout = QVBoxLayout()

        # ── Stain selection ──────────────────────────────────────────
        stain_group = QGroupBox("Färbung")
        stain_layout = QVBoxLayout()
        self.stain_box = QComboBox()
        self.stain_box.addItems(list(STAIN_MAP.keys()))
        stain_layout.addWidget(QLabel("Färbung auswählen:"))
        stain_layout.addWidget(self.stain_box)
        stain_group.setLayout(stain_layout)
        layout.addWidget(stain_group)

        # ── Folder selection ─────────────────────────────────────────
        folder_group = QGroupBox("Ordner")
        folder_layout = QVBoxLayout()
        self.folder_label = QLabel("Kein Ordner ausgewählt")
        self.folder_btn = QPushButton("Ordner auswählen")
        self.folder_btn.clicked.connect(self.select_folder)
        folder_layout.addWidget(self.folder_btn)
        folder_layout.addWidget(self.folder_label)
        folder_group.setLayout(folder_layout)
        layout.addWidget(folder_group)

        # ── DL Analysis ──────────────────────────────────────────────
        self.start_btn = QPushButton("DL‑Analyse starten")
        self.start_btn.clicked.connect(self.start_analysis)
        layout.addWidget(self.start_btn)

        self.threshold_btn = QPushButton("🔬 Threshold einstellen...")
        self.threshold_btn.clicked.connect(self.open_threshold_dialog)
        layout.addWidget(self.threshold_btn)

        self.confirmed_label = QLabel(f"Threshold: {self.confirmed_threshold}")
        self.confirmed_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(self.confirmed_label)

        # ── Sox9/DAPI Analysis ───────────────────────────────────────
        self.sox9_btn = QPushButton("Sox9/DAPI Analyse starten")
        self.sox9_btn.clicked.connect(self.run_sox9_analysis)
        layout.addWidget(self.sox9_btn)

        # ── Progress Bars ────────────────────────────────────────────
        layout.addWidget(QLabel("Gesamtfortschritt"))
        self.progress_global = QProgressBar()
        self.progress_global.setValue(0)
        layout.addWidget(self.progress_global)

        layout.addWidget(QLabel("Aktuelles Bild (Tile‑Fortschritt)"))
        self.progress_current = QProgressBar()
        self.progress_current.setValue(0)
        layout.addWidget(self.progress_current)

        self.setLayout(layout)
        self.folder = None

    # ── Folder ──────────────────────────────────────────────────────
    def select_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Ordner wählen")
        if path:
            self.folder = path
            self.folder_label.setText(f"Ordner: {path}")
            self.current_preview_path = None

    # ── Threshold ───────────────────────────────────────────────────
    def open_threshold_dialog(self):
        if not self.folder:
            QMessageBox.warning(self, "Fehler", "Bitte zuerst einen Ordner wählen.")
            return
        dlg = ThresholdDialog(
            folder=self.folder,
            initial_threshold=self.confirmed_threshold,
            parent=self
        )
        if dlg.exec_() == QDialog.Accepted:
            self.confirmed_threshold = dlg.confirmed_threshold
            self.confirmed_label.setText(f"Threshold: {self.confirmed_threshold}")
    
    def threshold_changed(self):
        self.threshold = self.threshold_slider.value()
        self.threshold_label.setText(f"Threshold: {self.threshold}")

    def confirm_threshold(self):
        self.confirmed_threshold = self.threshold
        self.confirmed_label.setText(f"Bestätigter Threshold: {self.confirmed_threshold}")
        QMessageBox.information(
            self, "Threshold gespeichert",
            f"Threshold {self.confirmed_threshold} wurde gespeichert\nund wird für die Analyse verwendet."
        )

    # ── Live Preview ─────────────────────────────────────────────────
    def preview_threshold(self):
        if not self.folder:
            QMessageBox.warning(self, "Fehler", "Bitte Ordner wählen.")
            return

        # Pick a random image (or reuse the last one)
        if self.current_preview_path is None:
            images = [
                os.path.join(self.folder, f)
                for f in os.listdir(self.folder)
                if f.lower().endswith((".tif", ".tiff", ".png", ".jpg", ".jpeg"))
            ]
            if not images:
                QMessageBox.warning(self, "Fehler", "Keine Bilder im Ordner.")
                return
            self.current_preview_path = random.choice(images)

        try:
            img = extract_channels(self.current_preview_path, "sox9_dapi")
        except Exception as e:
            QMessageBox.warning(self, "Ladefehler", str(e))
            return

        sox9 = img[..., 1].astype(np.float32)
        norm = (sox9 / max(1, sox9.max()) * 255).astype(np.uint8)
        mask = sox9 >= self.threshold

        # Build RGB overlay
        rgb = np.stack([norm, norm, norm], axis=-1)
        rgb[mask, 0] = 255   # rot für positiv
        rgb[mask, 1] = 0
        rgb[mask, 2] = 0

        # Render to QPixmap via matplotlib
        fig, ax = plt.subplots(figsize=(5, 3), dpi=100)
        ax.imshow(rgb)
        ax.set_title(
            f"Sox9-Kanal | Threshold={self.threshold} | "
            f"Positiv: {mask.sum()} px",
            fontsize=9
        )
        ax.axis("off")
        plt.tight_layout(pad=0.2)

        buf = io.BytesIO()
        plt.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)

        pil = Image.open(buf)
        data = pil.tobytes("raw", "RGB")
        qimg = QImage(data, pil.width, pil.height, QImage.Format_RGB888)
        self.preview_label.setPixmap(
            QPixmap.fromImage(qimg).scaled(
                self.preview_label.width(),
                self.preview_label.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )

    # ── DL Analysis ─────────────────────────────────────────────────
    def start_analysis(self):
        if not self.folder:
            QMessageBox.warning(self, "Fehler", "Bitte Ordner auswählen.")
            return
        stain_name = self.stain_box.currentText()
        stain_model = STAIN_MAP[stain_name]()
        worker = DLWorker(self.folder, stain_model)
        worker.signals.progress.connect(self.progress_global.setValue)
        worker.signals.finished.connect(self.show_results)
        self.threadpool.start(worker)
        QMessageBox.information(self, "Analyse gestartet", "DL‑Analyse läuft...")

    def show_results(self, text):
        self.progress_global.setValue(100)
        QMessageBox.information(self, "Ergebnisse", text)

    # ── Sox9/DAPI Analysis ───────────────────────────────────────────
    def run_sox9_analysis(self):
        if not self.folder:
            QMessageBox.warning(self, "Fehler", "Bitte Ordner wählen.")
            return
        worker = Sox9Worker(folder=self.folder, threshold=self.confirmed_threshold)
        worker.signals.progress_global.connect(self.progress_global.setValue)
        worker.signals.progress_tile.connect(self.progress_current.setValue)
        worker.signals.finished.connect(self.analysis_finished)
        self.threadpool.start(worker)
        QMessageBox.information(self, "Analyse gestartet", "Die Sox9/DAPI Analyse läuft...")

    def analysis_finished(self, text):
        self.progress_global.setValue(100)
        self.progress_current.setValue(100)
        QMessageBox.information(self, "Analyse abgeschlossen", text)


def run_ui():
    app = QApplication([])
    ui = HistologyUI()
    ui.show()
    app.exec_()