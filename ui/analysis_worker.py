import os
import time
from PyQt5.QtCore import QObject, pyqtSignal, QRunnable
from analysis.sox9_pipeline import Sox9Pipeline
class WorkerSignals(QObject):
    progress_global = pyqtSignal(int)
    progress_tile   = pyqtSignal(int)
    finished        = pyqtSignal(str)
class Sox9Worker(QRunnable):
    def __init__(self, folder, threshold= 10000):
        super().__init__()
        self.folder = folder
        self.threshold = threshold
        self.signals = WorkerSignals()
        self.current_tile = 0
        self.total_tiles = 1
        self.running = True
    def update_tile_progress(self):
        if self.total_tiles > 0:
            percent = int((self.current_tile / self.total_tiles) * 100)
            percent = min(percent, 100)
            self.signals.progress_tile.emit(percent)
    def run(self):
        print("Sox9 Worker gestartet")
        images = [
            os.path.join(self.folder, f)
            for f in os.listdir(self.folder)
            if f.lower().endswith((".tif", ".tiff", ".png", ".jpg", ".jpeg"))
        ]
        total_images = len(images)
        if total_images == 0:
            self.signals.finished.emit("Keine geeigneten Bilder gefunden.")
            return
        
        results_folder = os.path.join(self.folder, "results")
        pipeline = Sox9Pipeline(worker=self, threshold=self.threshold)

        for idx, img_path in enumerate(images):
            # GLOBALER FORTSCHRITT
            progress_global = int((idx / total_images) * 100)
            self.signals.progress_global.emit(progress_global)
            # Reset Tile Fortschritt
            self.current_tile = 0
            self.total_tiles = 1
            self.signals.progress_tile.emit(0)
            print(f"Analysiere Bild: {os.path.basename(img_path)}")
            pipeline.run(img_path, output_folder=self.folder)
            self.signals.progress_tile.emit(100)
        self.signals.progress_global.emit(100)
        self.signals.progress_tile.emit(100)
        self.signals.finished.emit(
            f"Analyse abgeschlossen.\nErgebnisse gespeichert in:\n{results_folder}"
        )