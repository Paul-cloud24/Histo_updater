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
from torch import layout
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import io
from PIL import Image

from stains import col1, col2, safranin_o, tunel
from ui.analysis_worker import Sox9Worker
from ui.dl_worker import DLWorker
from analysis.channel_detection import extract_channels
from ui.threshold_dialog import ThresholdDialog
from ui.roi_dialog import ROIDialog

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
        self.threshold = 60
        self.confirmed_threshold = 60
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

        self.btn_roi = QPushButton("📐 ROI einzeichnen...")
        self.btn_roi.clicked.connect(self._open_roi_dialog)
        layout.addWidget(self.btn_roi)  
        self._use_roi = False   # Startzustand: ganzes Bild

        self.btn_roi_mode = QPushButton("🔍 Modus: Ganzes Bild")
        self.btn_roi_mode.setStyleSheet("color: gray;")
        self.btn_roi_mode.clicked.connect(self._toggle_roi_mode)
        layout.addWidget(self.btn_roi_mode)

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

    def _toggle_roi_mode(self):
        self._use_roi = not self._use_roi
        if self._use_roi:
            self.btn_roi_mode.setText("✂️ Modus: Mit ROI")
            self.btn_roi_mode.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.btn_roi_mode.setText("🔍 Modus: Ganzes Bild")
            self.btn_roi_mode.setStyleSheet("color: gray;")   
   
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

    def _open_roi_dialog(self):
        dapi_path = self._current_dapi_path()   # wie du den DAPI-Pfad holst
        if not dapi_path:
            return
        dlg = ROIDialog(dapi_path, parent=self)
        dlg.roi_confirmed.connect(self._on_roi_confirmed)
        dlg.exec_()

    def _current_dapi_path(self):
        """Findet den DAPI-Pfad im aktuell gewählten Ordner."""
        if not self.folder:
            QMessageBox.warning(self, "Fehler", "Bitte zuerst einen Ordner wählen.")
            return None

        from analysis.sox9_pipeline import find_images_in_folder
        try:
            sox9_path, dapi_path = find_images_in_folder(self.folder)
            return dapi_path
        except Exception as e:
            QMessageBox.warning(self, "Fehler", f"Kein DAPI-Bild gefunden:\n{e}")
            return None

    def _on_roi_confirmed(self, points_normalized):
        self._roi_points = points_normalized
        self.btn_roi.setText(f"📐 ROI ✓ ({len(points_normalized)} Punkte)")
        self.btn_roi.setStyleSheet("color: green; font-weight: bold;")
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
    # Änderungen in ui/app.py
# run_sox9_analysis() und Hilfsmethoden ersetzen/ergänzen

    # ── Sox9/DAPI Batch-Analyse ──────────────────────────────────────
    def run_sox9_analysis(self):
        if not self.folder:
            QMessageBox.warning(self, "Fehler", "Bitte Ordner wählen.")
            return

        from ui.batch_worker       import BatchWorker
        from analysis.batch_runner import find_sox9_folders

        folders = find_sox9_folders(self.folder)

        if not folders:
            # Kein Unterordner → aktuellen Ordner direkt analysieren
            self._run_single_folder(self.folder)
            return

        reply = QMessageBox.question(
            self, "Batch-Analyse",
            f"{len(folders)} Sox9-Unterordner gefunden.\nAlle analysieren?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self.progress_global.setValue(0)
        self.progress_current.setValue(0)
        self.sox9_btn.setEnabled(False)

        # Worker speichern damit roi_confirmed() erreichbar bleibt
        self._batch_worker = BatchWorker(
            root_folder=self.folder,
            threshold=self.confirmed_threshold,
            use_roi=self._use_roi,
        )
        self._batch_worker.signals.progress.connect(
            self.progress_global.setValue)
        self._batch_worker.signals.log.connect(
            self._on_batch_log)
        self._batch_worker.signals.folder_done.connect(
            self._on_folder_done)
        self._batch_worker.signals.folder_error.connect(
            self._on_folder_error)
        self._batch_worker.signals.finished.connect(
            self._on_batch_finished)

        # ROI-Pause-Signal → im UI-Thread öffnet Dialog
        self._batch_worker.signals.roi_needed.connect(
            self._on_roi_needed)

        self.threadpool.start(self._batch_worker)
        QMessageBox.information(
            self, "Batch gestartet",
            f"Analyse von {len(folders)} Ordner(n) läuft...\n"
            "Bei fehlender ROI wird die Analyse pausiert."
        )

    def _run_single_folder(self, folder: str):
        """Einzelordner analysieren (bisheriges Verhalten)."""
        from ui.analysis_worker import Sox9Worker
        worker = Sox9Worker(
            folder=folder,
            threshold=self.confirmed_threshold
        )
        worker.signals.progress_global.connect(self.progress_global.setValue)
        worker.signals.progress_tile.connect(self.progress_current.setValue)
        worker.signals.finished.connect(self.analysis_finished)
        self.threadpool.start(worker)
        QMessageBox.information(
            self, "Analyse gestartet", "Sox9/DAPI Analyse läuft...")

    # ── ROI-Pause während Batch ──────────────────────────────────────
    def _on_roi_needed(self, folder_name: str, dapi_path: str):
        """
        Wird im UI-Thread aufgerufen wenn ein Ordner keine ROI hat.
        Öffnet ROI-Dialog, wartet auf Bestätigung, gibt Worker frei.
        """
        QMessageBox.information(
            self, "ROI benötigt",
            f"Für den Ordner\n'{folder_name}'\nwurde noch keine ROI definiert.\n\n"
            "Bitte ROI einzeichnen und auf 'Übernehmen' klicken."
        )
        dlg = ROIDialog(dapi_path, parent=self)

        def on_confirmed(pts):
            # ROI gespeichert → Worker-Thread fortsetzen
            self._batch_worker.roi_confirmed()

        def on_rejected():
            # Abgebrochen → Worker trotzdem fortsetzen (wird dann übersprungen)
            self._batch_worker.roi_confirmed()

        dlg.roi_confirmed.connect(on_confirmed)
        dlg.rejected.connect(on_rejected)
        dlg.exec_()   # blockiert UI-Thread bis Dialog geschlossen

    # ── Batch-Callbacks ─────────────────────────────────────────────
    def _on_batch_log(self, msg: str):
        print(msg)

    def _on_folder_done(self, folder_name: str, result: dict):
        self.progress_current.setValue(100)

    def _on_folder_error(self, folder_name: str, error: str):
        print(f"✗ {folder_name}: {error}")

    def _on_batch_finished(self, csv_path: str, plot_path: str):
        self.sox9_btn.setEnabled(True)
        self.progress_global.setValue(100)

        msg = "Batch-Analyse abgeschlossen!\n\n"
        if csv_path:
            msg += f"CSV:   {csv_path}\n"
        if plot_path:
            msg += f"Plot:  {plot_path}\n"
        msg += f"\nAlle Ergebnisse in:\n{self.folder}/Results/"
        QMessageBox.information(self, "Fertig", msg)

    def analysis_finished(self, text):
        self.progress_global.setValue(100)
        self.progress_current.setValue(100)
        QMessageBox.information(self, "Analyse abgeschlossen", text)


def run_ui():
    app = QApplication([])
    ui = HistologyUI()
    ui.show()
    app.exec_()