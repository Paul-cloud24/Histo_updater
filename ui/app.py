import os
import random
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QVBoxLayout,
    QFileDialog, QComboBox, QMessageBox, QProgressBar
)
from PyQt5.QtCore import Qt, QThreadPool
from stains import col1, col2, safranin_o, tunel
from inference.infer_single import SingleStainInference
# Worker für Sox9 Pipeline
from ui.analysis_worker import Sox9Worker
from ui.dl_worker import DLWorker

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
        self.setWindowTitle("Histology Analysis – UI")
        self.setGeometry(200, 200, 450, 450)
        layout = QVBoxLayout()
        # --------------------------
        # Stain selection
        # --------------------------
        self.stain_box = QComboBox()
        self.stain_box.addItems(list(STAIN_MAP.keys()))
        layout.addWidget(QLabel("Färbung auswählen:"))
        layout.addWidget(self.stain_box)
        # --------------------------
        # Folder selection
        # --------------------------
        self.folder_label = QLabel("Kein Ordner ausgewählt")
        self.folder_btn = QPushButton("Ordner auswählen")
        self.folder_btn.clicked.connect(self.select_folder)
        layout.addWidget(self.folder_btn)
        layout.addWidget(self.folder_label)
        # --------------------------
        # DL stain analysis
        # --------------------------
        self.start_btn = QPushButton("DL‑Analyse starten")
        self.start_btn.clicked.connect(self.start_analysis)
        layout.addWidget(self.start_btn)
        # --------------------------
        # Random preview
        # --------------------------
        self.preview_btn = QPushButton("Vorschau (1 zufälliges Bild)")
        self.preview_btn.clicked.connect(self.preview_image)
        layout.addWidget(self.preview_btn)
        # --------------------------
        # Sox9/DAPI Analysis
        # --------------------------
        self.sox9_btn = QPushButton("Sox9/DAPI Analyse starten")
        self.sox9_btn.clicked.connect(self.run_sox9_analysis)
        layout.addWidget(self.sox9_btn)
        # --------------------------
        # Progress Bars
        # --------------------------
        self.progress_global = QProgressBar()
        self.progress_current = QProgressBar()
        self.progress_global.setValue(0)
        self.progress_current.setValue(0)
        layout.addWidget(QLabel("Gesamtfortschritt"))
        layout.addWidget(self.progress_global)
        layout.addWidget(QLabel("Aktuelles Bild (Tile‑Fortschritt)"))
        layout.addWidget(self.progress_current)
        self.setLayout(layout)
        self.folder = None
    # ---------------------------------------------------------
    # Folder selection
    # ---------------------------------------------------------
    def select_folder(self):
        dlg = QFileDialog()
        path = dlg.getExistingDirectory(self, "Ordner wählen")
        if path:
            self.folder = path
            self.folder_label.setText(f"Ordner: {path}")
    
    def show_results(self, text):
        self.progress.setValue(100)
        QMessageBox.information(self, "Ergebnisse", text)
    
    # ---------------------------------------------------------
    # Standard stain DL analysis
    # ---------------------------------------------------------
    def start_analysis(self):
        if not self.folder:
            QMessageBox.warning(self, "Fehler", "Bitte Ordner auswählen.")
            return
        stain_name = self.stain_box.currentText()
        stain_model = STAIN_MAP[stain_name]()
        worker = DLWorker(self.folder, stain_model)
        worker.signals.progress.connect(self.progress.setValue)
        worker.signals.finished.connect(self.show_results)
        self.threadpool.start(worker)
        QMessageBox.information(self, "Analyse gestartet", "DL‑Analyse läuft...")
    # ---------------------------------------------------------
    # Preview mode
    # ---------------------------------------------------------
    def preview_image(self):
        if not self.folder:
            QMessageBox.warning(self, "Fehler", "Bitte Ordner wählen.")
            return
        stain_name = self.stain_box.currentText()
        stain_model = STAIN_MAP[stain_name]()
        try:
            model = stain_model.load_for_inference()
        except FileNotFoundError:
            QMessageBox.warning(
                self,
                "Kein Modell gefunden",
                "Für diese Färbung existiert noch kein trainiertes Modell.\n"
                "Bitte zuerst trainieren oder eine andere Färbung wählen."
            )
            return
        images = [
            f for f in os.listdir(self.folder)
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".tif"))
        ]
        if not images:
            QMessageBox.warning(self, "Fehler", "Keine Bilder im Ordner.")
            return
        img = random.choice(images)
        pred = model.predict(os.path.join(self.folder, img))
        cls = pred.argmax(1).item()
        QMessageBox.information(self, "Preview",
                                f"Zufallsbild:\n{img}\n→ Klasse {cls}")
    # ---------------------------------------------------------
    # Sox9 worker analysis
    # ---------------------------------------------------------
    def run_sox9_analysis(self):
        if not self.folder:
            QMessageBox.warning(self, "Fehler", "Bitte Ordner wählen.")
            return
        # Worker erstellen
        worker = Sox9Worker(self.folder)
        # Signale verbinden
        worker.signals.progress_global.connect(self.progress_global.setValue)
        worker.signals.progress_tile.connect(self.progress_current.setValue)
        worker.signals.finished.connect(self.analysis_finished)
        # Worker starten
        self.threadpool.start(worker)
        QMessageBox.information(self, "Analyse gestartet",
                                "Die Sox9 Analyse läuft...")
    def analysis_finished(self, text):
        self.progress_global.setValue(100)
        self.progress_current.setValue(100)
        QMessageBox.information(self, "Analyse abgeschlossen", text)
def run_ui():
    app = QApplication([])
    ui = HistologyUI()
    ui.show()
    app.exec_()