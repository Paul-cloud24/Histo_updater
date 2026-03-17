import os
import time
from PySide6.QtCore import Qt, QThreadPool, QRunnable, QObject, Signal, QWaitCondition, QMutex
from sklearn import pipeline
from analysis.core_pipeline import CoreStainPipeline, find_images_in_folder

class WorkerSignals(QObject):
    progress_global = Signal(int)
    progress_tile   = Signal(int)
    finished        = Signal(str)
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
        sox9_path, dapi_path = find_images_in_folder(self.folder)

        if sox9_path is None:
            self.signals.finished.emit("Kein Sox9-Bild gefunden.")
            return
        if dapi_path is None:
            self.signals.finished.emit("Kein DAPI-Bild gefunden.")
            return

        self.signals.progress_global.emit(10)

        pipeline = CoreStainPipeline(worker=self, threshold=self.threshold, nucleus_diameter=60, positive_fraction=0.10)
        result = pipeline.run(sox9_path, dapi_path,
                           output_folder=self.folder)

        self.signals.progress_global.emit(100)
        self.signals.progress_tile.emit(100)
        self.signals.finished.emit(
            f"Analyse abgeschlossen.\n\n"
            f"DAPI-Kerne gesamt:     {result['n_dapi_total']}\n"
            f"Sox9-positiv:          {result['n_positive']}\n"
            f"──────────────────────\n"
            f"Sox9+/DAPI-Ratio:      {result['ratio']:.1f} %\n\n"
            f"Ergebnisse in: {self.folder}/results/"
        )